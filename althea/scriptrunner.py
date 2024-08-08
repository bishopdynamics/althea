"""
Althea - Python Script Runner

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

# Reference: https://restrictedpython.readthedocs.io/en/latest/usage/policy.html#implementing-a-policy

# NOTE: RestrictedPython helps enforce a lot of restrictions upon scripts to be executed,
#   however those restrictions are... restrictive. As such, many of these restrictions have been undone in the name of more interesting functionality
#   if you wish to make script execution slightly safer (it will always be a little risky), you can re-apply restrictions as needed
#       the majority of this is undone via: LessRestrictingNodeTransformer, details are clearly commented there
#       there are also 4 methods in ScriptManager that should be scrutinized when tightening up restrictions:
#           _safe_import    - restrict allowed imports
#           _unsafe_write   - restrict writing to some objects/files/etc
#           _apply          - restrict access to args and kwargs
#           _inplacevar     - restrict usage in-place operators, such as +=

from __future__ import annotations

import ast
import warnings
import traceback


from typing import TYPE_CHECKING, Union, Any, Literal
from types import ModuleType, CodeType
from dataclasses import dataclass
from hashlib import md5
from copy import copy

# NOTE: a list of ScriptCache objects is shared between backend threads/processes,
#   but we need some help from dill to properly pickle/unpickle CodeType objects
from dill import dumps, loads

from RestrictedPython import safe_globals
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
from RestrictedPython.Guards import guarded_iter_unpack_sequence
from RestrictedPython.compile import _compile_restricted_mode
from RestrictedPython.transformer import IS_PY38_OR_GREATER, INSPECT_ATTRIBUTES
from RestrictedPython.transformer import RestrictingNodeTransformer, copy_locations, FORBIDDEN_FUNC_NAMES
from RestrictedPython.PrintCollector import PrintCollector

from .common import log, LogEmulator, time_nano, time_seconds


if TYPE_CHECKING:
    from logging import Logger


SAFE_SCRIPT_MODULES = frozenset(('math', 'time', 'typing', 'abc', 'inspect', 'collections', 'traceback', 'pandas', 'json', 'csv', 'numpy', 'numba'))
"""These are the modules which are allowed for scripts to attempt to import; attempts to import other modules will raise an exception"""


class ScriptManagerException(Exception):
    """Exception specific to script manager"""


class LessRestrictingNodeTransformer(RestrictingNodeTransformer):
    """
    This is the ast node transformer, which applies most of the restrictions to user-supplied scripts
        here we overwrite a few methods to be slightly less restricting than default
    """

    def check_name(self, node, name, allow_magic_methods=True):
        """Check names if they are allowed.

        Note: Change: removed check for names starting with _ to allow use in scripts

        """
        if name is None:
            return
        if name.endswith('__roles__'):
            self.error(node, f'"{name}" is an invalid variable name because it ends with "__roles__".')
        elif name in FORBIDDEN_FUNC_NAMES:
            self.error(node, f'"{name}" is a reserved name.')

    def visit_Attribute(self, node):
        """Checks and mutates attribute access/assignment.

        'a.b' becomes '_getattr_(a, "b")'
        'a.b = c' becomes '_write_(a).b = c'
        'del a.b' becomes 'del _write_(a).b'

        The _write_ function should return a security proxy.
        """
        # NOTE: Change: disabled, to allow __init__ methods to be called directly, like in super().__init__()
        # if node.attr.startswith('_') and node.attr != '_':
        #     self.error(
        #         node,
        #         '"{name}" is an invalid attribute name because it starts '
        #         'with "_".'.format(name=node.attr))

        if node.attr.endswith('__roles__'):
            self.error(
                node,
                f'"{node.attr}" is an invalid attribute name because it ends with "__roles__".')

        if node.attr in INSPECT_ATTRIBUTES:
            self.error(
                node,
                f'"{node.attr}" is a restricted name,'
                ' that is forbidden to access in RestrictedPython.',
            )

        if isinstance(node.ctx, ast.Load):
            node = self.node_contents_visit(node)
            new_node = ast.Call(
                func=ast.Name('_getattr_', ast.Load()),
                args=[node.value, ast.Str(node.attr)],
                keywords=[])

            copy_locations(new_node, node)
            return new_node

        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            node = self.node_contents_visit(node)
            new_value = ast.Call(
                func=ast.Name('_write_', ast.Load()),
                args=[node.value],
                keywords=[])

            copy_locations(new_value, node.value)
            node.value = new_value
            return node

        else:  # pragma: no cover
            # Impossible Case only ctx Load, Store and Del are defined in ast.
            raise NotImplementedError(
                f"Unknown ctx type: {type(node.ctx)}")

    def visit_AnnAssign(self, node):
        """
        NOTE: New Method: Allow AnnAssign statements without restrictions
            this covers vars declared with type annotations like: self.name: str = ''
        """
        return self.node_contents_visit(node)

    def inject_print_collector(self, node, position=0):
        """
        This is used to ensure calls to print() are properly redirected
            you also need to add things to globals for this to work:
                # add our global logger
                script_globals['log'] = LogEmulator()
                # enable print() through logger
                print_collector = ScriptPrintCollector(script_globals['log'])
                script_globals['_print_'] = print_collector.get_printer
        """
        print_used = self.print_info.print_used
        printed_used = self.print_info.printed_used

        if print_used or printed_used:
            # Add '_print = _print_(_getattr_)' add the top of a
            # function/module.
            _print = ast.Assign(
                targets=[ast.Name('_print', ast.Store())],
                value=ast.Call(
                    func=ast.Name("_print_", ast.Load()),
                    args=[ast.Name("_getattr_", ast.Load())],
                    keywords=[]))

            if isinstance(node, ast.Module):
                _print.lineno = position
                _print.col_offset = position
                if IS_PY38_OR_GREATER:
                    _print.end_lineno = position
                    _print.end_col_offset = position
                ast.fix_missing_locations(_print)
            else:
                copy_locations(_print, node)

            node.body.insert(position, _print)

            # NOTE: Change: Ignore warnings related to the usage of print() in scripts because we are redirecting print to the log
            # https://code.activestate.com/pypm/restrictedpython/#print
            # if not printed_used:
            #     self.warn(node, "Prints, but never reads 'printed' variable.")
            # elif not print_used:
            #     self.warn(node, "Doesn't print, but reads 'printed' variable.")


class ScriptPrintCollector(PrintCollector):
    """
    Print Collector used by scripts to route any calls to print() to our logging system
    """

    def __init__(self, logger: Logger, _getattr_=None):
        super().__init__(_getattr_)
        self.log = logger

    def get_printer(self, _thing) -> PrintCollector:
        """
        print handler needs to be returned by calling a function/method
        """
        return self

    def _call_print(self, *objects, **kwargs) -> None:
        """
        print handler needs _call_print method which does the actual printing work
            We send anything printed as log level info
        """
        self.log.info(str(*objects))


@dataclass
class ScriptResult:
    """Result of running a script with ScriptManager"""
    outputs: list[Any]
    """Output values"""
    error: bool = False
    """Was an error encountered?"""
    error_message: str = ''
    """Simple one-line error message"""
    error_traceback: str = ''
    """Full error stack trace"""
    log_messages: list[tuple[Literal['debug', 'info', 'warning', 'error']], str] = None


@dataclass
class ScriptCache:
    """A cached, precompiled script"""
    client_id: int
    """Unique ID of the client requesting execution; we only keep one cached object per client"""
    script_hash: int
    """Hash of original script text"""
    bytecode: CodeType
    """Compiled script as bytecode"""
    created: int
    """Time, in milliseconds, when this cache entry was created; used to evict entries past a configured max age"""


class ScriptManager:
    """
    The Script Manager handles execution of a single script, general steps of which are:
        * validate script content
        * compile script to bytecode
        * prepare dict of global vars
        * execute bytecode with globals dict
        * intercept any print() or log.*() calls, store them
        * catch any exceptions and prepare a traceback
        * grab output values from globals dict
        * if error:
            * return ScriptResult with: error message, traceback, and log messages
        * if success:
            * return ScriptResult with: output values, and log messages
    """
    cache_max_age = 10
    """Seconds, how long to keep around cached pre-compiled scripts"""

    def __init__(self, cache: list, lock) -> None:
        log.debug('Initializing ScriptManager instance')
        self._cache: list[ScriptCache] = cache
        """(internal) Cache of pre-compiled scripts"""
        self._lock = lock
        """(internal) Lock to guard cache lookups"""

    def get_hash(self, script: str):
        """Get md5 hash of script content"""
        scr_bytes = script.encode()
        chksum = md5(scr_bytes).hexdigest()
        return chksum

    def check_cache(self, script_hash: str, client_id: int) -> Union[CodeType, None]:
        """
        Check for an appropriate cached version of the bytecode and return it
            returns None if no appropriate found;
                Any entries which are too old are removed;
                Any entries for this client_id with different hash, are removed
        """
        cache_copy = copy(self._cache)
        self._lock.acquire()
        for cobj in cache_copy:
            obj_age = round(time_seconds() - cobj.created, 2)
            if obj_age > self.cache_max_age:
                log.warning(f'Evicting an old cached script, age: {obj_age}s')
                self._cache.remove(cobj)
                continue

            if cobj.client_id == client_id:
                if cobj.script_hash == script_hash:
                    self._lock.release()
                    return loads(cobj.bytecode)
                # hash as changed, we need to throw away the cached object for this client
                self._cache.remove(cobj)

        self._lock.release()
        return None

    def validate_script(self, _content: str) -> bool:
        """
        Validate script content before we compile
            returns success:bool
        """
        # TODO perform some kind of static analysis of the script before even attempting to compile it
        return True

    def compile_script(self, content: str) -> Union[CodeType, None]:
        """
        Compile given script to bytecode, applying ast node transforming policy as we go
        """
        try:
            result = _compile_restricted_mode(
                content,
                filename='_exec_.py',
                mode='exec',
                flags=0,
                dont_inherit=False,
                policy=LessRestrictingNodeTransformer)
            for warning in result.warnings:
                warnings.warn(
                    warning,
                    SyntaxWarning
                )
            if result.errors:
                raise SyntaxError(result.errors)
        except Exception as ex:
            log.error(f'Exception encountered while compiling script: {ex}')
            return None
        return result.code

    def create_globals(self, inputs: list[Any]) -> dict[str, Any]:
        """
        Create the globals context that will be passed to the script
            We need to manually define everything that will be available to scripts
        """
        script_globals = safe_globals.copy()
        # setup other globals so that we can use classes and iterators
        script_globals['__metaclass__'] = type
        script_globals['_getiter_'] = default_guarded_getiter  # iterate over items
        script_globals['_getitem_'] = default_guarded_getitem  # access items of arrays and dicts
        script_globals['_apply_'] = self._apply  # access args and kwargs
        script_globals['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
        # remove restrictions on getattr, allows attributes starting with _ and __
        script_globals['getattr'] = getattr
        script_globals['__builtins__']['_getattr_'] = getattr
        # must declare __name__ for OOP to work
        script_globals['__name__'] = '__script__'
        # restrict what can be imported
        script_globals['__builtins__']['__import__'] = self._safe_import
        # allow modifying data, such as object attributes
        script_globals['_write_'] = self._unsafe_write
        # make "sum" available
        script_globals['sum'] = sum
        # make "dict" available as a type
        script_globals['dict'] = dict
        # enable some in-place operators like +=
        script_globals['_inplacevar_'] = self._inplacevar
        # add our global logger
        script_globals['log'] = LogEmulator()
        # enable print() through logger
        print_collector = ScriptPrintCollector(script_globals['log'])
        script_globals['_print_'] = print_collector.get_printer
        # add input and output
        script_globals['inputs'] = inputs
        script_globals['outputs'] = []
        return script_globals

    def run_script(self, script: str, inputs: list[Any], client_id: int) -> ScriptResult:
        """
        Validate, compile, and execute the script, returning result
        """
        c_start = time_nano()
        script_hash = self.get_hash(script)
        script_bytecode = self.check_cache(script_hash, client_id)
        if script_bytecode is None:
            c_start = time_nano()
            log.debug('Validating script')
            if not self.validate_script(script):
                return ScriptResult([], True, 'Failed to validate script')
            log.debug('Compiling script')
            script_bytecode = self.compile_script(script)
            if script_bytecode is None:
                return ScriptResult([], True, 'Failed to compile script to bytecode!')
            c_duration = time_nano() - c_start
            with self._lock:
                self._cache.append(ScriptCache(client_id, script_hash, dumps(script_bytecode), time_seconds()))
            log.debug(f'Verification and Compile took: {c_duration}ns')
        else:
            c_duration = time_nano() - c_start
            log.debug('Using cached pre-compiled script')
            log.debug(f'Cache load took: {c_duration}ns')

        script_globals = self.create_globals(inputs)
        log.debug('Executing script')
        try:
            exec(script_bytecode, script_globals)  # pylint: disable=exec-used
        except Exception as ex:
            log.error('Script execution failed!')
            traceb = self.create_traceback(script)
            return ScriptResult(
                outputs=[],
                error=True,
                error_message=f'Exception while running script: {ex}',
                error_traceback=traceb,
                log_messages=script_globals['log'].get_messages()
            )
        log.debug('Script execution success!')
        return ScriptResult(
            outputs=script_globals['outputs'],
            log_messages=script_globals['log'].get_messages()
        )

    def create_traceback(self, script: str) -> str:
        """
        Create a useful traceback for exceptions that occur inside scripts
            Since scripts are complied to bytecode, traceback does not have access to the original script, so it can only provide line numbers
                We have to re-create our own stack trace from those numbers, by referencing the original script text
        """
        output = '\n'
        try:
            extra_lines = 5
            linenums = []
            stacktrace = traceback.format_exc()
            for line in stacktrace.splitlines():
                if 'File "_exec_.py", line' in line:
                    linesplit = line.split(' ')
                    linenums.append(int(linesplit[5].rstrip(',')))
            # output += stacktrace
            for linenum in linenums:
                output += '\n'
                script_content = '\n' + script
                script_content_lines = script_content.splitlines()
                output += '########## Script Content  ############\n\n'
                startline = linenum - extra_lines
                startline = max(startline, 0)  # dont wrap back to bottom if startline is negative
                for i in range(startline, linenum + extra_lines):
                    try:
                        linecontent = script_content_lines[i]
                    except IndexError:
                        continue  # we went past end, just skip it
                    if i == linenum:
                        # mark the offending line with an arrow
                        output += f'->{i}: {linecontent}\n'
                    else:
                        output += f'   {i}: {linecontent}\n'
            output += '\n########## End Script Content ############\n'
        except Exception as ex:
            log.error(f'Failed to create traceback: {str(ex)}')
        return output

    # these methods are used to modify builtin behavior of certain calls, within the script execution context

    @staticmethod
    def _safe_import(name: str, *args, **kwargs) -> ModuleType:
        """
        Guard for import within scripts; allow scripts to import only certain modules
        """
        # enable access to engine modules
        if name not in SAFE_SCRIPT_MODULES:
            raise ScriptManagerException(f'Attempted Illegal import: {name}')
        return __import__(name, *args, **kwargs)

    @staticmethod
    def _unsafe_write(obj) -> Any:
        """
        Allow scripts to write to certain objects
            NOTE: no filtering implemented
        """
        return obj

    @staticmethod
    def _apply(f, *a, **kw):
        """
        Enable scripts to access args and kwargs
        """
        return f(*a, **kw)

    @staticmethod
    def _inplacevar(op, x, y):
        """
        Allow certain in-place operations
        """
        if op == '+=':
            return x + y
        if op == '-=':
            return x - y
        raise ScriptManagerException(f'_inplacevar does not allow operator: {op}')
