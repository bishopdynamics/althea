"""
Althea - Pane Base Class

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .. import state


class Pane:
    """Base class for Panes
        A Pane is a dockable window in IMGUI terms
    """

    def __init__(self, app_state: state.AppState) -> None:
        self.app_state = app_state

    def setup(self):
        """Tasks to perform after app init"""

    def cleanup(self):
        """Tasks to perform when shutting down"""

    @abstractmethod
    def on_frame(self):
        """Tasks to do each frame"""
