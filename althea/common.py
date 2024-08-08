"""
Althea - Common imports and utilities

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

# pylint: disable=unused-import

from __future__ import annotations

import os
import sys
import time
import inspect
import logging
import enum
import sqlite3
import platform
import json

from contextlib import nullcontext
from pathlib import Path

from copy import copy, deepcopy
from collections import deque

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union, Any, Callable, Literal

from functools import wraps
from traceback import format_exc

import freetype
import pandas
import numpy

from imgui_bundle import (
    imgui,
    hello_imgui,  # pyright: ignore[reportMissingModuleSource]
    imgui_node_editor as ed,  # pyright: ignore[reportMissingModuleSource]
    icons_fontawesome,
    immapp,
    im_file_dialog,  # pyright: ignore[reportMissingModuleSource]
    imgui_color_text_edit,  # pyright: ignore[reportMissingModuleSource]
    imgui_md,  # pyright: ignore[reportMissingModuleSource]
    implot,
)


# Name of application, used in title bar, etc
APP_NAME = "Althea"

# extension (without .) used for workspace files
WORKSPACE_FILE_EXT = 'althwk'


# Alpha chars
CHARS_ALPHA: set[str] = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z')

# Numeric chars
CHARS_NUMERIC: set[str] = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')

# AlphaNumeric chars
CHARS_ALPHANUMERIC: set[str] = CHARS_ALPHA + CHARS_NUMERIC


# Map log levels from python logging module, to hello_imgui log levels
IMGUI_LOGLEVEL_MAP: dict[logging._Level, hello_imgui.LogLevel] = {
    logging.DEBUG: hello_imgui.LogLevel.debug,
    logging.INFO: hello_imgui.LogLevel.info,
    logging.WARNING: hello_imgui.LogLevel.warning,
    logging.ERROR: hello_imgui.LogLevel.error,
    logging.CRITICAL: hello_imgui.LogLevel.error,
}


# Used by file prompts for tabular data, to restrict selectable files
SUPPORTED_TABULAR_FILETYPES = (
    ("CSV files", "*.csv"),
    ("TSV files", "*.tsv"),
    ("Excel files", "*.xls"),
    ("Excel files", "*.xlsx"),
    ("OpenOffice files", "*.ods"),
    ("Sqlite3 databases", "*.db"),
    ("Sqlite3 databases", "*.sqlite"),
    ("Sqlite3 databases", "*.sqlite3"),
)

# All supported file suffixes for tabular data
SUPPORTED_TABULAR_FILE_SUFFIXES = ['.csv', '.tsv', '.xlsx', '.xls', '.ods', '.db', '.sqlite', '.sqlite3']

# file suffixes for tabular data, which potentially have multiple sub-items (sheets/tables)
SUPPORTED_TABULAR_FILE_SUFFIXES_SUBITEMS = ['.xlsx', '.xls', '.ods', '.db', '.sqlite', '.sqlite3']

LOG_FORMAT = "%(asctime)s [%(processName)-14s] [%(threadName)-14s] [%(levelname)-5.5s] {%(relativepath)s->%(funcName)s:%(lineno)d}  %(message)s"


def clamp(x, min_, max_):
    """Clamp value x between min_ and max_"""
    return max(min_, min(x, max_))


class Subscriptable:
    """Helper base class for objects with members that can be accesed using obj[member]"""

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def has(self, key) -> bool:
        """Check if key exists"""
        return key in self.__dict__


class UnsupportedError(Exception):
    """Error indicating something is unsupported"""

# Logging


class IMGUILogHandler(logging.StreamHandler):
    """Log Handler to send messages to imgui logging"""

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            im_loglevel = IMGUI_LOGLEVEL_MAP[record.levelno]
            hello_imgui.log(im_loglevel, msg)
        except (KeyboardInterrupt, SystemExit):  # pylint: disable=W0706
            raise
        except Exception:
            self.handleError(record)


class PackagePathFilter(logging.Filter):
    """Filter to add relativepath to log records"""

    def filter(self, record):
        pathname = record.pathname
        record.relativepath = None
        abs_sys_paths = map(os.path.abspath, sys.path)
        for path in sorted(abs_sys_paths, key=len, reverse=True):  # longer paths first
            if not path.endswith(os.sep):
                path += os.sep
            if pathname.startswith(path):
                record.relativepath = os.path.relpath(pathname, path)
                break
        return True


class TerminalColors:
    """Colors for terminals"""
    # reference: https://www.lihaoyi.com/post/BuildyourownCommandLinewithANSIescapecodes.html
    # reference: https://i.stack.imgur.com/9UVnC.png
    Black = '\x1b[30m'
    Red = '\x1b[31m'
    Green = '\x1b[32m'
    Yellow = '\x1b[33m'
    Blue = '\x1b[34m'
    Magenta = '\x1b[35m'
    Cyan = '\x1b[36m'
    White = '\x1b[37m'
    BrightBlack = '\x1b[90m'
    BrightRed = '\x1b[91m'
    BrightGreen = '\x1b[92m'
    BrightYellow = '\x1b[93m'
    BrightBlue = '\x1b[94m'
    BrightMagenta = '\x1b[95m'
    BrightCyan = '\x1b[96m'
    BrightWhite = '\x1b[97m'
    BoldBlack = '\x1b[30;1m'
    BoldRed = '\x1b[31;1m'
    BoldGreen = '\x1b[32;1m'
    BoldYellow = '\x1b[33;1m'
    BoldBlue = '\x1b[34;1m'
    BoldMagenta = '\x1b[35;1m'
    BoldCyan = '\x1b[36;1m'
    BoldWhite = '\x1b[37;1m'
    BoldBrightBlack = '\x1b[90;1m'
    BoldBrightRed = '\x1b[91;1m'
    BoldBrightGreen = '\x1b[92;1m'
    BoldBrightYellow = '\x1b[93;1m'
    BoldBrightBlue = '\x1b[94;1m'
    BoldBrightMagenta = '\x1b[95;1m'
    BoldBrightCyan = '\x1b[96;1m'
    BoldBrightWhite = '\x1b[97;1m'

    Reset = '\x1b[0m'


class TerminalBackgroundColors:
    """Background colors for terminals"""
    BackgroundBlack = '\u001b[40m'
    BackgroundRed = '\u001b[41m'
    BackgroundGreen = '\u001b[42m'
    BackgroundYellow = '\u001b[43m'
    BackgroundBlue = '\u001b[44m'
    BackgroundMagenta = '\u001b[45m'
    BackgroundCyan = '\u001b[46m'
    BackgroundWhite = '\u001b[47m'
    BackgroundBrightBlack = '\u001b[40;1m'
    BackgroundBrightRed = '\u001b[41;1m'
    BackgroundBrightGreen = '\u001b[42;1m'
    BackgroundBrightYellow = '\u001b[43;1m'
    BackgroundBrightBlue = '\u001b[44;1m'
    BackgroundBrightMagenta = '\u001b[45;1m'
    BackgroundBrightCyan = '\u001b[46;1m'
    BackgroundBrightWhite = '\u001b[47;1m'


class ColoredFormatter(logging.Formatter):
    """Log formatter which applies colors based on log level"""

    def __init__(self, fmt):
        super().__init__()
        print('Terminal log formatter will assign colors based on: record.levelno')
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: TerminalColors.Blue + self.fmt + TerminalColors.Reset,
            logging.INFO: TerminalColors.Cyan + self.fmt + TerminalColors.Reset,
            logging.WARNING: TerminalColors.BrightYellow + self.fmt + TerminalColors.Reset,
            logging.ERROR: TerminalColors.Red + self.fmt + TerminalColors.Reset,
            logging.CRITICAL: TerminalColors.BoldBrightRed + self.fmt + TerminalColors.Reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class ColoredFormatter_Module(logging.Formatter):
    """
    Log formatter which applies colors based on the relative path of the originating file
        must be used in combination with PackagePathFilter, in order to add relativepath attribute to records
    """
    _color_set = [TerminalColors.Red, TerminalColors.BrightYellow, TerminalColors.Blue, TerminalColors.Cyan, TerminalColors.Magenta, TerminalColors.BoldWhite, TerminalColors.BoldBrightGreen, TerminalColors.BoldBrightBlue]

    def __init__(self, fmt):
        super().__init__()
        print('Terminal log formatter will assign colors based on: record.relativepath')
        self.fmt = fmt
        self.assigned_colors: dict[str, str] = {}
        self.counter = 0

    def format(self, record):
        if record.relativepath not in self.assigned_colors:
            self.assigned_colors[record.relativepath] = self._color_set[self.counter]
            self.counter += 1
            if self.counter >= len(self._color_set):
                self.counter = 0
        color = self.assigned_colors[record.relativepath]
        log_fmt = color + self.fmt + TerminalColors.Reset
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging() -> logging.Logger:
    """Setup logging system to print to stdout AND send to imgui logging, returns logger instance"""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(ColoredFormatter(LOG_FORMAT))
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.addFilter(PackagePathFilter())
    logger.addHandler(_console_handler)

    _imgui_handler = IMGUILogHandler()
    _imgui_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    _imgui_handler.setLevel(logging.DEBUG)
    _imgui_handler.addFilter(PackagePathFilter())
    logger.addHandler(_imgui_handler)

    return logger


log = setup_logging()
"""Global pointer to logging interface"""


# Everything else


class IdProvider:
    """A simple utility to obtain unique ids, and to be able to restore them at each frame"""

    def __init__(self, start: int = 1) -> None:
        self.base = start
        self._next_id: int = self.base

    def next_id(self):
        """Gets a new unique id"""
        r = self._next_id
        self._next_id += 1
        return r

    def reset(self):
        """Resets the counter (called at each frame)"""
        self._next_id = self.base

    def rebase(self, newbase: int):
        """Change starting point and reset"""
        self.base = newbase
        self.reset()


class IdProviders:
    """
    ID providers for the whole app
        each block can handle 10,000,000 unique ids before overlap
    """
    _block_offset = 10000000
    _block_num = 0

    def __init__(self) -> None:
        self.Sheet = IdProvider(self.next_block_start())
        self.Node = IdProvider(self.next_block_start())
        self.Link = IdProvider(self.next_block_start())
        self.Pin = IdProvider(self.next_block_start())

    def next_block_start(self) -> int:
        """Get the start of the next block"""
        block_num = self._block_num
        self._block_num += 1
        return block_num * self._block_offset

    def reset(self):
        """Reset all id providers"""
        self.Sheet.reset()
        self.Node.reset()
        self.Link.reset()
        self.Pin.reset()

# NOTE: on macOS, time_ns() always returns 000 as the last 3 digits, because it only ticks in microseconds
# https://stackoverflow.com/questions/53868389/time-time-ns-is-not-returing-nanoseconds-correctly-on-macos


def time_millis() -> float:
    """Get current time as floating point milliseconds, with nanosecond accuracy (supposedly)"""
    if platform.system() == 'Windows':
        return time.time_ns() / 1_000_000
    return time.monotonic_ns() / 1_000_000


def time_nano() -> int:
    """Get current time as integer nanoseconds"""
    if platform.system() == 'Windows':
        return time.time_ns()
    return time.monotonic_ns()


def time_seconds() -> float:
    """Get current time as float seconds"""
    if platform.system() == 'Windows':
        return (time.time_ns() / 1_000_000) / 1000
    return (time.monotonic_ns() / 1_000_000) / 1000


def time_nano_pretty(t: int) -> str:
    """Turn a time in nanoseconds into a string using seconds, milliseconds, or nanoseconds as needed
        * greater than 0.5 seconds = seconds
        * greater than 0.5 milliseconds = milliseconds
        * otherwise nanoseconds
        * always rounds to 4 decimal places
    """
    sec_lower = 1_000_000 * 500
    ms_lower = 500_000
    word = 'ns'

    if t > sec_lower:
        # greater than 0.5 seconds
        t = (t / 1_000_000) / 1000
        word = 's'
    elif t > ms_lower:
        # greater than 0.5 milliseconds
        t = t / 1_000_000
        word = 'ms'

    t_round = round(t, 4)
    return f'{t_round} {word}'


# set to True to perform runtime type checking and print out lots of info about it
#   if False, runtime_debug_types decorator will have no effect
DEBUG_TYPE_CHECKING = False


def runtime_debug_types(func):
    """Decorator to enable runtime type checking on function/method arguments"""
    def wrapper(*args, **kwargs):
        if not DEBUG_TYPE_CHECKING:
            # Call the original function
            return func(*args, **kwargs)
        # Get the function signature and parameter names
        signature = inspect.signature(func)
        parameters = signature.parameters

        def get_type_from_string(name: str) -> type:
            """get type from a string"""
            if name.startswith('type['):
                # TODO when the type annotation is type[SomeClass], we currently only check that arg is a type, but we should validate the right type
                name = 'type'
            q = deque([object])
            while q:
                t = q.popleft()
                if t.__name__ == name:
                    return t
                try:
                    q.extend(t.__subclasses__())
                except TypeError:
                    if t is type:
                        continue
                    # raise

            raise ValueError(f'No such type: {name}')

        def check_arg(param_name, arg):
            """check given parameter name and value"""
            if param_name == 'self':
                return  # skip object pointer
            param_type: Union[type, str] = parameters[param_name].annotation
            if isinstance(param_type, str):
                # type annotation is a literal string
                param_type_str = param_type
                if DEBUG_TYPE_CHECKING:
                    log.debug(f'Type: checking {param_name}: "{param_type_str}" against {arg.__class__.__name__}')
                param_type = get_type_from_string(param_type_str)
                if param_type is None:
                    raise TypeError(f"Type: could not locate type class associated with argument '{param_name}' annotation is string literal: '{param_type_str}'")
            else:
                if DEBUG_TYPE_CHECKING:
                    log.debug(f'Type: checking {param_name}: {param_type.__name__} against {arg.__class__.__name__}')
            if param_type == Any:
                return  # dont check things annotated as Any
            if not isinstance(arg, param_type):
                raise TypeError(f"Argument '{param_name}' must be of type: {param_type.__name__}, but got: {arg.__class__.__name__}")

        # Iterate over the positional arguments
        for i, arg in enumerate(args):
            param_name = list(parameters.keys())[i]
            check_arg(param_name, arg)

        # Iterate over the keyword arguments
        for param_name, arg in kwargs.items():
            check_arg(param_name, arg)

        # Call the original function
        return func(*args, **kwargs)

    return wrapper


class SerializabilityException(Exception):
    """Exception indicating that something is not serializable"""


def ensure_serializable(func):
    """Decorator to ensure that the output of function can be serialized using json.dumps()"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Call the original function
        output_data = func(*args, **kwargs)
        try:
            _test = json.dumps(output_data)
        except Exception as jex:
            raise SerializabilityException(f'Output of function is not Serializable: {jex}') from jex

        return output_data
    return wrapper


def get_sole_string(file: Path) -> str:
    """
    Get the first line of a file, stripped of any leading or trailing whitespace
    """
    with open(file, 'rt', encoding='utf-8') as vf:
        string = vf.read().splitlines()[0].strip()
    return string


def get_program_dir() -> Path:
    """
    Figure out the program dir, even if built into an standalone app using pyinstaller/nuitka
    """
    if getattr(sys, 'frozen', False):
        # application_path = os.path.dirname(sys.executable)
        program_dir = Path(sys._MEIPASS)  # pylint: disable=protected-access
    elif __file__:
        # return parent because this file is within a subfolder
        program_dir = Path(os.path.dirname(__file__)).parent
    program_dir = program_dir.resolve()  # resolve symlinks to absolute real path
    # print(f'Program dir:  {str(program_dir)}')
    return program_dir


def get_version() -> str:
    """
    Read VERSION and COMMIT_ID to create a version string
        these files need to be included when built into an standalone app using pyinstaller/nuitka 
    """
    root_dir = get_program_dir()
    commit_id_file = root_dir.joinpath('COMMIT_ID')
    version_file = root_dir.joinpath('VERSION')
    try:
        version = get_sole_string(version_file)
    except Exception:
        version = 'UNKNOWN'
    try:
        commit_id = get_sole_string(commit_id_file)
    except Exception:
        commit_id = ''
    version_string = version
    if commit_id != '':
        version_string += f'-{commit_id}'
    return version_string


def read_tabular_file(filepath: Path) -> dict[str, pandas.DataFrame]:
    """
    Read a tabular data file and return its data, as a dictionary of named Dataframes
      checks file extension to assign a decoder
      if a filetype does not have subitems, there will be a single dataframe named "default"
    """
    # NOTE: use dtype=str to prevent automatic conversion of cell contents into int/float/date/etc
    log.debug(f'Reading data from file: {filepath}')
    filepath_absolute = filepath.resolve()
    file_data = None
    if filepath_absolute.is_file():
        if filepath_absolute.suffix not in SUPPORTED_TABULAR_FILE_SUFFIXES:
            raise UnsupportedError(f'Unsupported file extension for tabular data: {filepath_absolute.suffix}')
        # lets try decoding this with pandas
        # first try to read into dataframe
        dataframes = []  # store dataframes
        dataframe_names = []  # store dataframe names
        if filepath_absolute.suffix == '.csv':
            attempt_data = None
            try:
                attempt_data = pandas.read_csv(filepath_absolute, encoding='utf-8', dtype=str)
            except UnicodeDecodeError:
                log.debug('re-trying with latin/cp1252/ISO-8859-1 encoding')
                attempt_data = pandas.read_csv(filepath_absolute, encoding='latin', dtype=str)
            dataframes.append(attempt_data)
            dataframe_names.append('default')
        elif filepath_absolute.suffix == '.tsv':
            attempt_data = None
            try:
                attempt_data = pandas.read_csv(filepath_absolute, sep='\t', encoding='utf-8', dtype=str)
            except UnicodeDecodeError:
                log.debug('re-trying with latin/cp1252/ISO-8859-1 encoding')
                attempt_data = pandas.read_csv(filepath_absolute, sep='\t', encoding='latin', dtype=str)
            dataframes.append(attempt_data)
            dataframe_names.append('default')
        elif filepath_absolute.suffix in ['.xlsx', '.xls', '.ods']:
            # old xls, new xlsx, and openoffice ods formats
            xlfile = pandas.ExcelFile(filepath_absolute)
            # load all sheets
            log.debug(f'Reading data from {len(xlfile.sheet_names)} sheets')
            for this_sheet in xlfile.sheet_names:
                dataframes.append(pandas.read_excel(filepath_absolute, sheet_name=this_sheet, dtype=str))
                dataframe_names.append(str(this_sheet))
        elif filepath_absolute.suffix in ['.db', '.sqlite', '.sqlite3']:
            # try to read sqlite db
            log.debug(f'Treating as sqlite3 database: {filepath_absolute.suffix}')
            db_conn = sqlite3.connect(filepath_absolute)
            cursor = db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables_raw = cursor.fetchall()
            tables_list = []
            for entry in tables_raw:
                tables_list.append(entry[0])
            # load all tables
            log.debug(f'Reading data from {len(tables_list)} tables')
            for this_table in tables_list:
                dataframes.append(pandas.read_sql_query(f"SELECT * FROM {this_table};", db_conn, dtype=str))
                dataframe_names.append(this_table)
            db_conn.close()
        # now turn our lists into a single dictionary
        file_data = {}
        for (index, df_name) in enumerate(dataframe_names):
            file_data[df_name] = dataframes[index]
    else:
        raise FileNotFoundError(f'Could not find file: {str(filepath)}')
    return file_data


def load_file_to_dataframes(filepath: Path, subitem: Union[str, None] = None) -> dict[str, pandas.DataFrame]:
    """
    Load the given tabular data file into a dict of pandas dataframes
        if a subitem is specified, try to return only that subitem
    """
    file_data = read_tabular_file(filepath)
    if filepath.suffix not in SUPPORTED_TABULAR_FILE_SUFFIXES_SUBITEMS or subitem is None:
        return file_data
    # some formats have sub-items, like xlsx->sheet or sqlite->table
    #   if a subitem is specified we will try to return only that subitem
    subitem_name = None
    subitem_index = None
    if subitem:
        if subitem in file_data:
            # subitem is the name
            subitem_name = subitem
            subitem_index = list(file_data.keys()).index(subitem_name)
        else:
            # try using subitem as index
            try:
                file_data_keys = list(file_data.keys())
                subitem_index = int(subitem)
                subitem_name = file_data_keys[subitem_index]
            except Exception:
                log.warning(f'Failed to find subitem: "{subitem}", loading all subitems')
                subitem_name = None
                subitem_index = None
    if subitem_name is None:
        return file_data
    # only return the requested subitem
    log.debug(f'Filtering for subitem {subitem_index}: "{subitem_name}"')
    filtered_data = {}
    filtered_data[subitem_name] = file_data[subitem_name]
    return filtered_data


class LogEmulator:
    """Simulate our normal global logger instance, storing messages to be handled later"""

    def __init__(self) -> None:
        self._messages: list[tuple[Literal['debug', 'info', 'warning', 'error'], str]] = []

    def _store_msg(self, level: Literal['debug', 'info', 'warning', 'error'], message: str):
        self._messages.append((level, message))

    def debug(self, msg: str):
        """Log a debug level message"""
        self._store_msg('debug', msg)

    def info(self, msg: str):
        """Log an info level message"""
        self._store_msg('info', msg)

    def warning(self, msg: str):
        """Log a warning level message"""
        self._store_msg('warning', msg)

    def error(self, msg: str):
        """Log an error level message"""
        self._store_msg('error', msg)

    def get_messages(self) -> list[tuple[Literal['debug', 'info', 'warning', 'error'], str]]:
        """Get all messages as list[tuple[Literal['debug', 'info', 'warning', 'error'], str]] """
        return self._messages

    @staticmethod
    def process_messages(messages: list[tuple[Literal['debug', 'info', 'warning', 'error']], str], prefix: str = ''):
        """
        Process given list of messages into the actual log
            run this on the main thread, with messages list returned from other thread
        """
        if messages is None:
            return
        if len(messages) == 0:
            return
        for level, msg in messages:
            if level == 'debug':
                log.debug(prefix + msg)
            if level == 'info':
                log.info(prefix + msg)
            if level == 'warning':
                log.warning(prefix + msg)
            if level == 'error':
                log.error(prefix + msg)


implot_global_context = implot.create_context()
