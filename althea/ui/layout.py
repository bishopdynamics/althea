"""
Althea - UI Widgets: layout

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from imgui_bundle import imgui

from .primitives import LayoutGroupContext, LayoutGroupModifier, LayoutModState
from .primitives import BaseCollapsableThing, BaseLayoutGroup


class Padding(LayoutGroupModifier):
    """Add padding to a layout group"""

    def __init__(self, left: float = 0.0, right: float = 0.0, above: float = 0.0, below: float = 0.0) -> None:
        self.left: float = left
        """Padding Left of content"""
        self.right: float = right
        """Padding Right of content"""
        self.above: float = above
        """Padding Above of content"""
        self.below: float = below
        """Padding Below of content"""

    def handle_state(self, state: LayoutModState, _context: LayoutGroupContext):
        if state == LayoutModState.BeforeGroup:
            if self.left != 0:
                imgui.text('')
                imgui.same_line(0, self.left)


class HorizontalGroup(BaseLayoutGroup):
    """A context manager for horizontal layout group; returns a LayoutGroupContext"""


class VerticalGroup(BaseLayoutGroup):
    """A context manager for vertical layout group; returns a LayoutGroupContext"""

    def __enter__(self) -> bool:
        imgui.same_line()
        return super().__enter__()


class CollapsingHeader(BaseCollapsableThing):
    """A collapsing header that manages ids for you"""

    def before_thing(self):
        pass

    def draw_collapsable_thing(self) -> bool:
        is_open = imgui.collapsing_header(self.label)
        if is_open:
            # if it is open, we need to set tooltip here, otherwise we have to set it in after_thing
            if self.description.strip() != '':
                imgui.set_item_tooltip(self.description)
        return is_open

    def after_thing(self):
        if not self.open:
            if self.description.strip() != '':
                imgui.set_item_tooltip(self.description)


class TreeNode(BaseCollapsableThing):
    """A collapsing tree node that manages ids for you"""

    def before_thing(self):
        pass

    def draw_collapsable_thing(self) -> bool:
        is_open = imgui.tree_node(self.label)
        if is_open:
            # if it is open, we need to set tooltip here, otherwise we have to set it in after_thing
            if self.description.strip() != '':
                imgui.set_item_tooltip(self.description)
        return is_open

    def after_thing(self):
        if self.open:
            imgui.tree_pop()
        else:
            if self.description.strip() != '':
                imgui.set_item_tooltip(self.description)
