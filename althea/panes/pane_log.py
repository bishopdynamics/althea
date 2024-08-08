"""
Althea - Logging Pane

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from ..common import imgui, hello_imgui
from .base import Pane


class LogPane(Pane):
    """View logging messages"""

    def on_frame(self):
        """Tasks to do each frame"""
        hello_imgui.log_gui()
        if self.app_state.show_metrics:
            imgui.show_metrics_window()
