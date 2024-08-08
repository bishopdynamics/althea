"""
Althea - Object Config System - imgui Editor

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..common import imgui, imgui_md
from ..ui import InputWidget_Fallback, collect_input_widgets
from ..ui import CollapsingHeader, TreeNode, HorizontalGroup

from ..vartypes import Select

from .base import ConfigParameter

if TYPE_CHECKING:
    from .base import Config
    from .. import state
    from ..ui import InputWidget_Sheet


class ConfigEditorException(Exception):
    """config editor exception"""


class ConfigParamRenderer:
    """Render an input widget for a single Config Parameter"""
    _all_widgets, _all_widget_tweaks = collect_input_widgets()

    def __init__(self, app_state: state.AppState) -> None:
        self.app_state = app_state

    def handle_special_sheet(self, initial_value: int, param: ConfigParameter) -> tuple[bool, Select]:
        """Handle special case for Sheet select"""

        active_sheet_id = None
        if param.tweaks.variant == 'Sheet':
            sheet_list = self.app_state.workspace.sheets
            if self.app_state.get_focused_editor() == 'Sheet':
                if self.app_state.panes.SheetEditor.sheet is not None:
                    active_sheet_id = self.app_state.panes.SheetEditor.sheet.id.id()
        elif param.tweaks.variant == 'Function':
            sheet_list = self.app_state.workspace.function_sheets
            if self.app_state.get_focused_editor() == 'Function':
                if self.app_state.panes.FunctionEditor.sheet is not None:
                    active_sheet_id = self.app_state.panes.FunctionEditor.sheet.id.id()

        if isinstance(initial_value, Select):
            initial_value = initial_value.selected

        # select first value if we can
        if initial_value is None and len(sheet_list) > 0:
            selected_value = sheet_list[0].id.id()
        else:
            selected_value = initial_value

        if active_sheet_id is not None:
            sheets_select = self.app_state.workspace.get_sheet_select(selected=selected_value, skip=[active_sheet_id,], variant=param.tweaks.variant)
        else:
            sheets_select = self.app_state.workspace.get_sheet_select(selected=selected_value, variant=param.tweaks.variant)

        widgetclass: type[InputWidget_Sheet] = self._all_widgets['InputWidget_Sheet']
        (changed, value) = widgetclass(sheets_select, param.label, param.description, param.tweaks).on_frame()

        if value.selected != initial_value:
            changed = True
        return changed, value

    def render_input(self, param: ConfigParameter, initial_value: Any = None) -> tuple[bool, Any]:
        """perform per-frame tasks"""
        if initial_value is None:
            initial_value = param.default
        with HorizontalGroup():
            if param.comment != '':
                with HorizontalGroup():
                    imgui_md.render_unindented(param.comment)
                imgui.text(' ')
            widgetclassname = 'InputWidget_' + param.type.name
            if widgetclassname in self._all_widgets:
                if widgetclassname == 'InputWidget_Sheet':
                    (changed, value) = self.handle_special_sheet(initial_value, param)

                else:
                    widgetclass = self._all_widgets[widgetclassname]
                    (changed, value) = widgetclass(initial_value, param.label, param.description, param.tweaks).on_frame()
            else:
                (changed, value) = InputWidget_Fallback(initial_value, param.label, param.description, param.tweaks).on_frame()

        return changed, value


class ConfigEditor:
    """imgui Editor for Config objects"""

    def __init__(self, app_state: state.AppState) -> None:
        self.app_state = app_state
        self.value_editor = ConfigParamRenderer(app_state)

    def evaluate_hidden(self, config: Config) -> list[str]:
        """Figure out if any keys should be hidden"""
        hidden_keys: list[str] = []
        for section in config.sections:
            for group in section.groups:
                for param in group.parameters:
                    if param.hidden:
                        hidden_keys.append(param.key)
        return hidden_keys

    def on_frame(self, config: Config):
        """Run per-frame tasks"""
        hidden_keys = self.evaluate_hidden(config)
        with HorizontalGroup():
            for section in config.sections:
                if len(section.groups) > 0:
                    # check that at least one group has parameters, otherwise skip this section
                    not_empty = False
                    for group in section.groups:
                        if len(group.parameters) > 0:
                            not_empty = True
                            break
                    if not_empty:
                        with CollapsingHeader(section.label, section.description) as h_open:
                            if h_open:
                                for group in section.groups:
                                    if len(group.parameters) > 0:
                                        with TreeNode(group.label, group.description) as t_open:
                                            if t_open:
                                                for param in group.parameters:
                                                    if param.key in hidden_keys:
                                                        continue
                                                    initial_value = config.get(param.key)
                                                    (changed, value) = self.value_editor.render_input(param, initial_value)
                                                    if changed:
                                                        config.set(param.key, value)
