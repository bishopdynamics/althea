"""
Althea - Config Editor Testing Pane
    This is a pane dedicated to testing out all the various combinations of config editor widgets and tweaks
"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING

from ..common import imgui
from ..config import ConfigEditor, TestConfig

from .base import Pane

if TYPE_CHECKING:
    from .. import state


class TestConfigEditorPane(Pane):
    """Testing config editor"""

    def __init__(self, app_state: state.AppState) -> None:
        super().__init__(app_state)
        self.config = TestConfig()

    def on_frame(self):
        """Tasks to do each frame"""
        imgui.separator_text('Config Editor Testing')

        common_config_editor = ConfigEditor(self.app_state)
        common_config_editor.on_frame(self.config)
