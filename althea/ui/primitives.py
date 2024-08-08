"""
Althea - UI Widgets: primitives

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import enum

from copy import copy
from abc import abstractmethod
from typing import Union

from imgui_bundle import imgui

from ..vartypes import Region, Vec2, Select

from .ids import IDContext


class LayoutGroupContext:
    """Context returned by HorizontalGroup and VerticalGroup, with lots of useful data"""

    def __init__(self) -> None:
        self.fqid: str = None
        """Fully-qualified, stable and unique, ID provided by IDContext"""
        self.parent_region: Region = None
        """Parent region"""
        self.group_region: Region = None
        """Region of the group; may be same as parent if not affected by LayoutGroupModifier"""


class CollapsibleLayoutGroupContext(LayoutGroupContext):
    """Context returned by a collapsible layout group"""

    def __init__(self) -> None:
        self.open: bool = False
        """Is this collapsible group open? (otherwise collapsed)"""
        super().__init__()


class LayoutModState(enum.Enum):
    """States at which a layout mod might want to inject tasks"""
    BeforeGroup = enum.auto()
    """before begin_group()"""
    AfterGroupStart = enum.auto()
    """after begin_group()"""
    BeforeGroupEnd = enum.auto()
    """before end_group()"""
    AfterGroupEnd = enum.auto()
    """after end_group()"""


class LayoutGroupModifier:
    """
    Base class for modifiers to HorizontalGroup and VerticalGroup layout context managers
    """

    @abstractmethod
    def handle_state(self, state: LayoutModState, context: LayoutGroupContext):
        """Handle tasks for the given state"""
        raise NotImplementedError('subclasses must implement this method!')


class BaseLayoutGroup(IDContext):
    """A base context manager for layout groups; returns a LayoutGroupContext"""

    def __init__(self, mods: Union[list[LayoutGroupModifier], LayoutGroupModifier] = None) -> None:
        super().__init__('Group')
        self.mods = mods
        """Modifications to layout"""
        self.context = LayoutGroupContext()
        """This layout group's local context"""

    def _handle_mods(self, state: LayoutModState, context: LayoutGroupContext):
        if self.mods is not None:
            if isinstance(self.mods, list):
                if len(self.mods) > 0:
                    for this_mod in self.mods:
                        this_mod.handle_state(state, context)
            if isinstance(self.mods, LayoutGroupModifier):
                self.mods.handle_state(state, context)

    def __enter__(self) -> LayoutGroupContext:
        # TODO figure out parent region values
        self.context.parent_region = Region.default()
        self.context.fqid = super().__enter__()

        self._handle_mods(LayoutModState.BeforeGroup, self.context)
        imgui.begin_group()
        # TODO figure out group region values
        self.context.group_region = Region.default()
        self._handle_mods(LayoutModState.AfterGroupStart, self.context)

        return self.context

    def __exit__(self, _type, _value, _traceback):
        self._handle_mods(LayoutModState.BeforeGroupEnd, self.context)
        imgui.end_group()
        self._handle_mods(LayoutModState.AfterGroupEnd, self.context)
        super().__exit__(_type, _value, _traceback)


class BaseCollapsableThing(IDContext):
    """
    Base context manager for things that can be collapsed
        NOTE: this is intentionally not implemented as a layout group
    """

    def __init__(self, label: str, description: str) -> None:
        super().__init__(label)
        self.label = label
        self.description = description
        self.open: bool = False

    def __enter__(self) -> bool:
        _id = super().__enter__()
        self.before_thing()
        self.open = self.draw_collapsable_thing()
        return self.open

    def __exit__(self, _type, _value, _traceback):
        self.after_thing()
        super().__exit__(_type, _value, _traceback)

    def before_thing(self):
        """Tasks to perform before drawing the thing"""

    @abstractmethod
    def draw_collapsable_thing(self) -> bool:
        """Draw the collapsable thing, and return is_open:bool"""
        raise NotImplementedError('subclasses must implement this method!')

    def after_thing(self):
        """Tasks to perform after drawing the thing"""


class ChildContext(IDContext):
    """
    Context manager for child windows
    """

    def __init__(self, label: str = 'Child') -> None:
        super().__init__(label)
        self.open: bool = False

    def __enter__(self) -> bool:
        child_id = super().__enter__()
        self.open = imgui.begin_child(child_id)
        return self.open

    def __exit__(self, _type, _value, _traceback):
        if self.open:
            imgui.end_child()
        super().__exit__(_type, _value, _traceback)


class TableContext(IDContext):
    """
    Context manager for creating table
    """

    def __init__(self, num_cols: int, size: Vec2 = Vec2(0, 0), borders: bool = True, rowbg: bool = True) -> None:
        super().__init__('Table')
        self.open: bool = False
        self.size = size
        self.num_cols = num_cols
        self.borders = borders
        self.rowbg = rowbg

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""

        flags = 0

        # NOTE: The following flags are known to break layout/rendering when used within a Node!
        # flags |= imgui.TableFlags_.scroll_x.value
        # flags |= imgui.TableFlags_.scroll_y.value
        # flags |= imgui.TableFlags_.no_host_extend_y.value

        # NOTE: the following flags are REQUIRED or layout/rendering within a node will break!
        flags |= imgui.TableFlags_.no_host_extend_x.value

        # everything else
        flags |= imgui.TableFlags_.highlight_hovered_column.value
        if self.rowbg:
            flags |= imgui.TableFlags_.row_bg.value
        if self.borders:
            flags |= imgui.TableFlags_.borders.value
            flags |= imgui.TableFlags_.borders_h.value
            flags |= imgui.TableFlags_.borders_inner_h.value
            flags |= imgui.TableFlags_.borders_outer_h.value
            flags |= imgui.TableFlags_.borders_v.value
            flags |= imgui.TableFlags_.borders_inner_v.value
            flags |= imgui.TableFlags_.borders_outer_v.value
            flags |= imgui.TableFlags_.borders_outer.value
            flags |= imgui.TableFlags_.borders_inner.value
        return flags

    def __enter__(self) -> bool:
        child_id = super().__enter__()
        if self.num_cols > 0:
            self.open = imgui.begin_table(child_id, self.num_cols, flags=self.craft_flags(), outer_size=self.size)
        else:
            self.open = False
        return self.open

    def __exit__(self, _type, _value, _traceback):
        if self.num_cols > 0:
            imgui.end_table()
        super().__exit__(_type, _value, _traceback)


def select_to_listbox(label: str, selobj: Select, flags: int = 0, item_flags: int = 0) -> tuple[bool, Select]:
    """Create a listbox from a Select object, returning changed, newvalue"""
    initial_selection = selobj.get_selected()
    selobj.ensure_sane_selection()
    current_selection = selobj.get_selected()
    selection_corrected = False
    if initial_selection is None:
        if current_selection is not None:
            selection_corrected = True
    elif initial_selection.value is None:
        if current_selection.value is not None:
            selection_corrected = True

    if current_selection is None:
        # if selection is None after ensure_sane_selection(), then that means the options list is empty
        imgui.text('No options to select from!')
    else:
        current_value = copy(current_selection.value)
        if imgui.begin_combo(label, current_selection.display, flags):
            for opt in selobj.options:
                is_selected = False
                if opt.value == current_value:
                    is_selected = True
                changed, selected = imgui.selectable(opt.display, is_selected, item_flags)
                if opt.description != '':
                    imgui.set_item_tooltip(opt.description)
                if changed:
                    if selected:
                        selobj.select(opt.value)
            imgui.end_combo()

        if selection_corrected:
            # selection changed as result of ensure_sane_selection()
            return (True, selobj)
        if selobj.selected != current_value:
            # selection changed as a result of user interaction
            return (True, selobj)

    return (False, selobj)
