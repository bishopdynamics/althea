"""
Althea - Sheet Config Pane

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations


from ..common import imgui
from ..config import ConfigEditor

from .base import Pane


class SheetConfigPane(Pane):
    """
    Editor for sheet configuration
        This editor applies to the currently active Sheet editor (Sheet or Function) 
    """

    def on_frame(self):
        """Tasks to do each frame"""
        imgui.separator_text('Sheet Configuration')

        if self.app_state.get_focused_editor() == 'Sheet':
            editor = self.app_state.panes.SheetEditor
        elif self.app_state.get_focused_editor() == 'Function':
            editor = self.app_state.panes.FunctionEditor
        else:
            editor = None

        if editor is not None:
            if editor.sheet is not None:
                sheet_config_editor = ConfigEditor(self.app_state)
                sheet_config_editor.on_frame(editor.sheet.config)

        imgui.separator_text('Node Configuration')
        if self.app_state.get_focused_editor() == 'Sheet':
            editor = self.app_state.panes.SheetEditor
        elif self.app_state.get_focused_editor() == 'Function':
            editor = self.app_state.panes.FunctionEditor
        else:
            editor = None

        if editor is not None:
            if len(editor.context.selected_nodes) == 1:
                # only one node selected, we can edit its config
                node = editor.sheet.find_node(editor.context.selected_nodes[0].id())
                common_config_editor = ConfigEditor(self.app_state)
                common_config_editor.on_frame(node.common_config)
                config_editor = ConfigEditor(self.app_state)
                config_editor.on_frame(node.config)

        imgui.separator_text('Current Selection')
        imgui.text('Selected Link IDs:')
        for link_id in editor.context.selected_links:
            imgui.text(f'  {link_id.id()}')
        imgui.text('Seleced Node IDs:')
        for node_id in editor.context.selected_nodes:
            imgui.text(f'  {node_id.id()}')
