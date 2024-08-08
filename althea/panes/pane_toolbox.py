"""
Althea - Toolbox

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from ..common import imgui, IdProvider, log
from ..ui import CollapsingHeader, TreeNode, HorizontalGroup, draw_text, FontSize, FontVariation, Button
from ..vartypes import VarType

from .base import Pane

if TYPE_CHECKING:
    from .. import state


class ToolboxPane(Pane):
    """Tree-based menu for commands / creating nodes"""

    def __init__(self, app_state: state.AppState) -> None:
        super().__init__(app_state)
        self.id_provider = IdProvider()

    def on_frame(self):
        """Tasks to do each frame"""

        if self.app_state.get_focused_editor() == 'Sheet':
            editor = self.app_state.panes.SheetEditor
        elif self.app_state.get_focused_editor() == 'Function':
            editor = self.app_state.panes.FunctionEditor
        else:
            editor = None

        self.id_provider.reset()

        imgui.separator_text('Nodes')
        container_width = imgui.get_item_rect_size().x
        for category, subs in self.app_state.node_registry.items():
            with CollapsingHeader(category, f'Node Category: {category}') as h_open:
                if h_open:
                    for subcat, nodesdict in subs.items():
                        with TreeNode(subcat, f'Node Category {category} - {subcat}') as t_open:
                            if t_open:
                                for _classname, actual_class in nodesdict.items():
                                    if actual_class.hidden:
                                        continue
                                    with HorizontalGroup():
                                        draw_text(actual_class.node_display, FontSize.Small, FontVariation.Bold)
                                        imgui.same_line()
                                        draw_text(f'[In: {len(actual_class.inputs)} Out: {len(actual_class.outputs)}]', FontSize.Small, FontVariation.Italic)
                                        imgui.same_line(container_width - 50)
                                        if Button('Add'):
                                            if editor is not None:
                                                if editor.sheet is not None:
                                                    editor.sheet.new_node(actual_class)

                                    imgui.set_item_tooltip(actual_class.node_desc)

        imgui.separator_text('View Bookmarks')
        with CollapsingHeader('Views', 'View Bookmarks') as vb_open:
            if vb_open:
                if len(self.app_state.workspace.view_bookmarks) == 0:
                    draw_text('(No view bookmarks)')
                else:
                    for idx, view in enumerate(self.app_state.workspace.view_bookmarks):
                        with HorizontalGroup():
                            draw_text(f'{view.variant} {idx}. ' + view.label)
                            imgui.same_line()
                            if Button('Go'):
                                if view.variant == 'Sheet':
                                    self.app_state.panes.SheetEditor.request_view(view)
                                if view.variant == 'Function':
                                    self.app_state.panes.FunctionEditor.request_view(view)
                            imgui.same_line()
                            if Button('Update'):
                                log.warning('View Update Not implemented!')
                            imgui.same_line()
                            if Button('Rename'):
                                self.app_state.workspace.prompt_value('Label', 'Create a meaninful name for this View Bookmark', VarType.String, initial_value=view.label, data=idx, callback=self.app_state.workspace.update_view_label)
                            imgui.same_line()
                            if Button('Delete'):
                                log.warning(f'Deleting view: {idx}')
                                self.app_state.workspace.view_bookmarks.pop(idx)
