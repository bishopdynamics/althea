"""
Althea - UI Widgets: ID utilities

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from imgui_bundle import imgui


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


class IDRegistry:
    """Utility to create stable, unique ids"""

    def __init__(self) -> None:
        self.id_providers: dict[str, IdProvider] = {}
        self.id_stack: list[str] = []

    def reset(self):
        """Clear all registered ids"""
        self.id_providers = {}
        self.id_stack = []

    def register(self, id_: str) -> str:
        """Register an id. A unique fully-qualified id will be returned.
        """
        fqid = id_
        parent = self.get_context()
        if parent != '':
            fqid = f'{parent}.{id_}'

        if fqid not in self.id_providers:
            self.id_providers[fqid] = IdProvider()
        idnum = self.id_providers[fqid].next_id()
        self.id_stack.append(f'{id_}-{idnum}')
        full_id = f'{fqid}-{idnum}'
        return full_id

    def get_context(self) -> str:
        """Get the current context, aka the parent context id"""
        if len(self.id_stack) <= 0:
            return ''
        return '.'.join(self.id_stack)

    def pop(self) -> str:
        """Pop the most recent ID off the stack"""
        self.id_stack.pop(-1)


GIDR = IDRegistry()
"""Global Registry for UI Object IDs"""


class IDContext:
    """Context handler, which pushes a unique, but stable id to imgui id stack"""

    def __init__(self, id_: str = 'Something') -> None:
        self.id = GIDR.register(id_)
        imgui.push_id(self.id)

    def __enter__(self) -> str:
        return self.id

    def __exit__(self, _type, _value, _traceback):
        GIDR.pop()
        imgui.pop_id()
