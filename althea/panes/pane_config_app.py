"""
Althea - App Config Pane

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations


from ..common import imgui
from ..config import ConfigEditor

from .base import Pane


class AppConfigPane(Pane):
    """Editor for app configuration"""

    def on_frame(self):
        """Tasks to do each frame"""
        imgui.separator_text('Application Configuration')
        common_config_editor = ConfigEditor(self.app_state)
        common_config_editor.on_frame(self.app_state.app_config)

        imgui.separator_text('Workspace Configuration')
        common_config_editor = ConfigEditor(self.app_state)
        common_config_editor.on_frame(self.app_state.workspace.config)
