"""
Althea - Node implementations, Special nodes

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING
from traceback import format_exc

from ..common import log, IdProviders

from ..config import ConfigGroup, ConfigSection, ConfigParameter
from ..vartypes import VarType, Select, Vec2, IOPinInfo

from ..ui import InputWidgetTweaks_Sheet

from .primitives import NodeKind
from .base import WorkspaceSheet, SpecialNode
from .config import NodeConfig, CommonNodeConfig


if TYPE_CHECKING:
    from .. import state


class Node_Function_Outputs(SpecialNode):
    """A node used to provide outputs from a function"""
    node_kind = NodeKind.Special
    node_display = 'Function Outputs'
    node_desc = 'Data outputted by this Function'
    node_category = 'Advanced'
    node_subcategory = 'General'
    hidden = True
    deletable = False
    inputs = []
    outputs = []
    configurable_inputs = True

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ViewNode Config', 'Configuration for ViewNode', [
                ConfigGroup('General', 'General configuration', [
                ]),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        return []

    @staticmethod
    def special_precheck(sheet: WorkspaceSheet, _app_state: state.AppState) -> bool:
        if sheet.sheet_output_node_id is not None:
            log.warning('Only one node of type: "Node_Function_Outputs" allowed per sheet!')
            return False
        return True

    def special_setup(self, sheet: WorkspaceSheet):
        sheet.sheet_output_node_id = self.node_id

    def special_execute(self, sheet: WorkspaceSheet):
        """Transfer input values to sheet outputs"""
        sheet.sheet_output_values = []
        for my_input in self.inputs:
            sheet.sheet_output_values.append(my_input.value)


class Node_Function_Inputs(SpecialNode):
    """A node used to provide inputs to a sheet"""
    node_kind = NodeKind.Special
    node_display = 'Function Inputs'
    node_desc = 'Data used as input to this Function'
    node_category = 'Advanced'
    node_subcategory = 'General'
    hidden = True
    deletable = False
    inputs = []
    outputs = []
    configurable_outputs = True

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ViewNode Config', 'Configuration for ViewNode', [
                ConfigGroup('General', 'General configuration', [
                ]),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        return []

    @staticmethod
    def special_precheck(sheet: WorkspaceSheet, _app_state: state.AppState) -> bool:
        if sheet.sheet_input_node_id is not None:
            log.warning('Only one node of type: "Node_Function_Inputs" allowed per sheet!')
            return False
        return True

    def special_setup(self, sheet: WorkspaceSheet):
        sheet.sheet_input_node_id = self.node_id

    def special_execute(self, sheet: WorkspaceSheet):
        """Transfer input values to sheet outputs"""
        sheet.update_outputs(self.node_id.id(), sheet.sheet_input_values)


class Node_Function(SpecialNode):
    """A node which treats another sheet as a single node"""
    node_kind = NodeKind.Special
    node_display = 'Function'
    node_desc = ''
    node_category = 'Advanced'
    node_subcategory = 'General'
    inputs = []
    outputs = []
    reconfigure_io_anyway = True  # keep in sync with target function sheet

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('Function Node Config', 'Configuration for Function Node', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Function', 'Function to use', 'function_id', VarType.Sheet, tweaks=InputWidgetTweaks_Sheet(variant='Function'))
                ]),
            ]),
        ]
    config = nodeConfig()

    def __init__(self, id_: int, id_providers: IdProviders, app_state: state.AppState, position: Vec2 = None, init_pin_ids: bool = True) -> None:
        super().__init__(id_, id_providers, app_state, position, init_pin_ids)
        self._current_sheet_id = None
        """(internal) id of the currently selected Function Sheet"""

    @staticmethod
    def special_precheck(sheet: WorkspaceSheet, app_state: state.AppState) -> bool:
        return True

    def special_setup(self, sheet: WorkspaceSheet):
        sheet_id: Select = self.config.get('function_id')
        if isinstance(sheet_id, Select):
            sheet_id = sheet_id.selected
        self._current_sheet_id = sheet_id

    def check_for_reconfigure(self):
        """Check if we need to reconfigure inputs or outputs, to match configured Function Sheet"""

        sheet_id: Select = self.config.get('function_id')
        if isinstance(sheet_id, Select):
            sheet_id = sheet_id.selected

        if sheet_id is not None:
            try:
                sheet_obj = self.app_state.workspace.find_sheet(sheet_id, variant='Function')
            except Exception:
                sheet_obj = None

            if sheet_obj is not None:
                if sheet_obj.sheet_input_node_id is not None:
                    input_node = sheet_obj.find_node(sheet_obj.sheet_input_node_id)
                    if input_node.has_changed():
                        self.mark_changed()
                if sheet_obj.sheet_output_node_id is not None:
                    output_node = sheet_obj.find_node(sheet_obj.sheet_output_node_id)
                    if output_node.has_changed():
                        self.mark_changed()
                if sheet_id != self._current_sheet_id:
                    self.mark_changed()
                    self._current_sheet_id = sheet_id
                    try:
                        if sheet_obj.sheet_input_node_id is not None:
                            input_node = sheet_obj.find_node(sheet_obj.sheet_input_node_id)
                            input_infos: list[IOPinInfo] = input_node.common_config.get('output_iopininfos')
                            self.common_config.set('input_iopininfos', input_infos)
                        else:
                            self.common_config.set('input_iopininfos', [])
                    except Exception as iex:
                        print(f'Exception while processing input types: {iex}')
                        print(format_exc())

                    try:
                        if sheet_obj.sheet_output_node_id is not None:
                            output_node = sheet_obj.find_node(sheet_obj.sheet_output_node_id)
                            output_infos: list[IOPinInfo] = output_node.common_config.get('input_iopininfos')
                            self.common_config.set('output_iopininfos', output_infos)
                        else:
                            self.common_config.set('output_iopininfos', [])
                    except Exception as oex:
                        print(f'Exception while processing input types: {oex}')
                        print(format_exc())

    def on_frame(self):
        # ensure I/O is in sync with target function
        self.check_for_reconfigure()
        # Override node description to show currently selected function
        self.node_desc = 'Function: (none selected)'
        if self._current_sheet_id is not None:
            try:
                sheet_obj = self.app_state.workspace.find_sheet(self._current_sheet_id, variant='Function')
                self.node_desc = 'Function: ' + sheet_obj.config.get('name')
            except Exception:
                self.node_desc = 'Function: (none selected)'

    def special_execute(self, sheet: WorkspaceSheet):
        """This node does not use the execute() method at all, instead it calls use_sheet on the currently configured Function Sheet, then updates own outputs with returned values"""
        sheet_id: Select = self.config.get('function_id')
        sheet_id_actual = sheet_id.selected
        sheet_obj = self.app_state.workspace.find_sheet(sheet_id_actual, variant='Function')
        in_values = [inp.value for inp in self.inputs]
        out_values = sheet_obj.use_sheet(in_values)
        sheet.update_outputs(self.node_id.id(), out_values)

    @staticmethod
    def execute(_inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        return []
