"""
Althea - Base Node object

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import time
import json

from traceback import format_exc

from abc import abstractmethod
from typing import TYPE_CHECKING, Union, Any, Literal, Callable
from copy import copy, deepcopy
from pathlib import Path

from ..common import WORKSPACE_FILE_EXT, log, IdProviders, time_millis, ensure_serializable, time_nano
from ..common import imgui, ed

from ..vartypes import VARTYPE_NUMBER_TYPES, VarType, Vec2, Select, SelectOption, get_vartype, IOPinInfo, NormalizedColorRGBA
from ..ui import imfd, global_ui_state, Button, InputWidgetTweaks
from ..backend import CalcJob, CalcJobResult
from ..config import ConfigParamRenderer, ConfigParameter

from .primitives import IOPin, PinId, NodeKind, NodeId, NodeCalcStatus, IOKind, WorkspaceSheetId, LinkInfo, LinkId
from .config import WorkspaceConfig, WorkspaceSheetConfig, NodeConfig, CommonNodeConfig, SpecialCommonNodeConfig

if TYPE_CHECKING:
    from .. import state


class NodeException(Exception):
    """Exception specific to node or node editor"""


class WorkspaceException(Exception):
    """Exception in workspace actions"""


class CircularDependencyException(Exception):
    """Exception specific to Node Circular Dependency"""


class Node:
    """
    A Node in the node graph
    """
    node_kind: NodeKind = NodeKind.Simple
    """The node kind determines how calculation is handled by the backend"""
    node_display: str = 'Unknown'
    """The display name for this node; shown in node title; if this is "Unknown" then node will not be included in any internal or UI lists of all nodes"""
    node_desc: str = 'Unknown node type'
    """Description of this node's purpose; usually shown in italics below node title"""
    node_category: str = 'Unknown'
    """First-level organizational unit; used for building node registry, and building UI for selecting from available nodes"""
    node_subcategory: str = 'Unknown'
    """Second-level organizational unit; used for building node registry, and building UI for selecting from available nodes"""
    hidden: bool = False
    """Hide the node when building UI, listing available nodes to user"""
    deletable: bool = True
    """Allow or prevent this node from being deleted"""
    config: NodeConfig = NodeConfig()
    """Configuration specific to this node, available for the user to modify"""
    common_config: CommonNodeConfig
    """Common config shared by all nodes; subclasses should NOT override this attribute"""
    inputs: list[IOPin] = []
    """List of node inputs, including information about type and link state"""
    outputs: list[IOPin] = []
    """List of node outputs, including information about type and link state"""
    configurable_inputs: bool = False
    """If True, allow user to configure the inputs for this node"""
    configurable_outputs: bool = False
    """If True, allow user to configure the outputs for this node"""
    reconfigure_io_anyway: bool = False
    """
    If True, will reconfigure inputs and outputs if config values have changed,
        regardless of if inputs/outputs are configurable by the user
            this is used primarily by the Function node, which needs to sync its I/O with the I/O of the configured Function sheet
    """
    special_common_config: bool = False
    """For StaticValuesNode: If True, use the special common node config schema, which allows user to provide static values for outputs"""
    debug_ids: bool = False
    """If True, show IDs for nodes and pins; this is intended to be used at by the Node baseclass only, and obviously only for debugging"""
    required_keys = ['id', 'class', 'common_config', 'config', 'pos_x', 'pos_y', 'inputs', 'outputs']
    """When calling set_dict, these keys must be present or will fail"""

    def __init__(self, id_: int, id_providers: IdProviders, app_state: state.AppState, position: Vec2 = None, init_pin_ids: bool = True) -> None:
        self.id_providers = id_providers
        """Local pointer to workspace-wide id providers instance"""
        self.app_state = app_state
        """Local pointer to global app state"""
        self.position: Vec2 = position
        """Position to place the node, on the canvas; if None, will place at center of current canvas view"""
        self.node_id: NodeId = NodeId(id_)
        """The unique ID of this node; this is kept in sync with IMGUI backend IDs, and must be both unique and stable"""
        self._calc_status: NodeCalcStatus = NodeCalcStatus.Idle
        """(internal) Calculation status"""
        self._calc_message: str = ''
        """(internal) Calculation status: message returned from last completed calculation"""
        self._calc_traceback: str = ''
        """(internal) Calculation status: stack traceback returned from last completed calculation"""
        self._changed = True
        """(internal) track if this node has changed (config, common config, position, pin links, value from a pin link)"""
        self.need_propagate = False
        """(internal) flag indicating that we need to propagate the changed flag to dendencies, at the top of the next frame"""
        self.dimensions: Vec2 = Vec2(10, 10)
        """Current dimensions of the node"""
        self.first_frame = True
        """(internal) flag indicating if this is the first frame for this node; position is only set on first frame after creation"""
        self.calc_time: int = None
        """Duration, in nanoseconds, of the last re-calculation of this node"""
        self.color: NormalizedColorRGBA = None
        """Color applied to this node's titlebar, footer, etc; assigned automatically at runtime based on node_category"""
        self.last_cfg_inputs = None
        """(internal) track the current (last applied) input pin configuration, so we can check if config has changed"""
        self.last_cfg_outputs = None
        """(internal) track the current (last applied) output pin configuration, so we can check if config has changed"""

        # convert these into instance attributes so we can modify at runtime
        self.inputs = deepcopy(self.inputs)
        self.outputs = deepcopy(self.outputs)
        self.config = deepcopy(self.config)

        # For StaticValuesNode
        if self.special_common_config:
            self.common_config = SpecialCommonNodeConfig()
        else:
            self.common_config = CommonNodeConfig()

        # Configure input and output pins
        if self.configurable_inputs:
            self.common_config.unhide('input_iopininfos')
            self.configure_io(io_kind=IOKind.Input, init_pin_ids=init_pin_ids)
        else:
            self.common_config.hide('input_iopininfos')
            for input_ in self.inputs:
                input_.node_id = self.node_id
                if init_pin_ids:
                    input_.pin_id = PinId(self.id_providers.Pin.next_id())
        if self.configurable_outputs:
            self.common_config.unhide('output_iopininfos')
            self.configure_io(io_kind=IOKind.Output, init_pin_ids=init_pin_ids)
        else:
            self.common_config.hide('output_iopininfos')
            for output in self.outputs:
                output.node_id = self.node_id
                if init_pin_ids:
                    output.pin_id = PinId(self.id_providers.Pin.next_id())

    def configure_io(self, io_kind: IOKind, init_pin_ids: bool = True):
        """Setup inputs or outputs per configuration"""
        # phase 1: do we need to update anything?
        if io_kind == IOKind.Input:
            config_key = 'input_iopininfos'
            previous_cfg = self.last_cfg_inputs
        else:
            config_key = 'output_iopininfos'
            previous_cfg = self.last_cfg_outputs
        new_cfg: list[IOPinInfo] = self.common_config.get(config_key)
        if new_cfg == previous_cfg:
            return  # nothing to do!

        # phase 2: capture existing state (pinids and types), and then clear that state
        #   we want to re-use pinids for any pins where type did not change
        if io_kind == IOKind.Input:
            self.last_cfg_inputs = new_cfg
            previous_state = self.inputs
            self.inputs = []
        else:
            self.last_cfg_outputs = new_cfg
            previous_state = self.outputs
            self.outputs = []
        existing_details: list[dict[str, Any]] = []
        for pin in previous_state:
            if pin.pin_id is None:
                break  # no reason to continue, all subsequent indexes will be invalid
            existing_details.append({
                'pin_id': pin.pin_id.id(),
                'io_type': pin.io_type,
            })

        # phase 3: rebuild pins from new configuration, re-using pinids where type has not changed
        for count, pin_info in enumerate(new_cfg):
            # first create the new pin
            pin_label = f'{io_kind.name} {count}'
            pin_desc = f'{io_kind.name} {count} - {pin_info.io_type.name}'
            if pin_info.label.strip() != '':
                pin_label = pin_info.label
            if pin_info.description.strip() != '':
                pin_desc = pin_info.description
            new_pin = IOPin(pin_label, pin_desc, pin_info.io_type, io_kind)
            new_pin.node_id = self.node_id
            # optionally assign it a pin_id, try to preserve previous pinids if type has not changed
            if init_pin_ids:
                # there may not even be an entry for this pin in existing details
                try:
                    prev_type = existing_details[count]['io_type']
                except Exception:
                    prev_type = None
                if prev_type is not None and prev_type == pin_info.io_type:
                    # this pin is the same type as previous, so we can keep the same pin_id, and thus existing links will be preserved
                    new_pin.pin_id = PinId(existing_details[count]['pin_id'])
                else:
                    # we have to make a new pin_id; any existing links will be lost
                    new_pin.pin_id = PinId(self.id_providers.Pin.next_id())
            if io_kind == IOKind.Input:
                self.inputs.append(new_pin)
            else:
                self.outputs.append(new_pin)

    @ensure_serializable
    def get_dict(self) -> dict:
        """Get this node as a json serializable dict, to write to file"""
        if self.position is None:
            self.position = Vec2(150, 100)
        data = {
            'id': self.node_id.id(),
            'class': self.__class__.__name__,
            'pos_x': self.position.x,
            'pos_y': self.position.y,
            'common_config': self.common_config.to_dict(),
            'config': self.config.to_dict(),
            'inputs': [],
            'outputs': [],
        }
        for idx, input_ in enumerate(self.inputs):
            data['inputs'].append({
                'index': idx,
                'id': input_.pin_id.id(),
            })
        for odx, output in enumerate(self.outputs):
            data['outputs'].append({
                'index': odx,
                'id': output.pin_id.id(),
            })
        return data

    def set_dict(self, data: dict):
        """Set this node's state from dict"""
        # NOTE: if renumbering was needed, it already happened prior to this point
        try:
            for keyname in self.required_keys:
                if keyname not in data:
                    raise KeyError(f'Missing required key: {keyname}')
            self.config.set_dict(data['config'])
            self.common_config.set_dict(data['common_config'])

            # NOTE: it is important to NOT init pin_ids here, because we are going to restore pin_ids from from given data
            self.last_cfg_inputs = None
            self.last_cfg_outputs = None
            if self.configurable_inputs or self.reconfigure_io_anyway:
                self.configure_io(io_kind=IOKind.Input, init_pin_ids=False)

            if self.configurable_outputs or self.reconfigure_io_anyway:
                self.configure_io(io_kind=IOKind.Output, init_pin_ids=False)

            # restore pin ids
            for ipindata in data['inputs']:
                try:
                    self.inputs[ipindata['index']].pin_id = PinId(ipindata['id'])
                except IndexError:
                    log.warning(f'Skipping PinId recreation for id: {ipindata["id"]} because there is no pin at index: {ipindata["index"]}')
            for opindata in data['outputs']:
                try:
                    self.outputs[opindata['index']].pin_id = PinId(opindata['id'])
                except IndexError:
                    log.warning(f'Skipping PinId recreation for id: {opindata["id"]} because there is no pin at index: {opindata["index"]}')
        except Exception as ex:
            raise WorkspaceException('Failed to set node state from dict!') from ex

    # every frame: these methods will/must be called within on_frame method

    def on_frame(self):
        """Do per-frame tasks, before drawing anything"""

    def draw_middle(self):
        """
        Draw something in the middle, if there is any
        """

    def has_changed(self) -> bool:
        """Check if this node has changes and needs a re-calculation; """
        # NOTE since this is called every frame, this is where we sync need_propagate
        havechanges = self._changed or self.config.has_changes() or self.common_config.has_changes()
        if havechanges:
            self.need_propagate = True
        return havechanges

    # almost every frame: these methods have the potential to be called every frame
    #   but will likely be called much less frequently

    def mark_changed(self):
        """Mark this node as having changes, and in need of a re-calculation"""
        if not self._changed:
            self._changed = True
            self.need_propagate = True

    def mark_unchanged(self):
        """Mark this node as not having any un-applied changes"""
        if self._changed:
            self._changed = False
            self.config.mark_unchanged()
            self.common_config.mark_unchanged()

    # on-demand: these methods will be called asynchronously to our frame loop

    @ staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        """Define the action for this node to perform. Always return a list, even if one or zero outputs
        """
        raise NotImplementedError('Node subclass must implement method execute() !')

    def refresh(self) -> list:
        """Refresh the static value"""
        return []

    def set_calc_status(self, status: NodeCalcStatus, message: str = '', traceback: str = ''):
        """Set the status of node calc, including an optional additional message, and stack traceback"""
        self._calc_status = status
        self._calc_message = message
        self._calc_traceback = traceback

    def get_calc_status(self) -> NodeCalcStatus:
        """Get the status of node calc; only returns the status, no additional info"""
        return self._calc_status


class SpecialNode(Node):
    """
    Base class for special nodes
        special nodes can define additional tasks to do at specific node lifecycle moments
    """
    node_kind = NodeKind.Special

    @ staticmethod
    @ abstractmethod
    def special_precheck(sheet: WorkspaceSheet, app_state: state.AppState) -> bool:
        """check if we are allowed to create a node of this type"""
        raise NotImplementedError('Sub-classes must implement this method!')

    @ abstractmethod
    def special_setup(self, sheet: WorkspaceSheet):
        """Special steps to be done at end of init for this node"""
        raise NotImplementedError('Sub-classes must implement this method!')

    @ abstractmethod
    def special_execute(self, sheet: WorkspaceSheet):
        """Special steps to be done after execute for this node"""
        raise NotImplementedError('Sub-classes must implement this method!')


class WorkspaceSheet:
    """
    A single sheet within a workspace
        A sheet contains a list of Nodes, and a list of Links between pins on those Nodes.
            It handles dependency tracking, and processing of nodes in the correct order
    """
    calc_timeout: int = 30
    """Seconds, how long to wait for calc result to come back before giving up"""
    calc_check_delay: float = 0.001
    """Seconds, how long to wait between checks to backend; the only purpose of this value is to keep from monopolizing the frontend threads, keep it small"""
    required_keys = ['id', 'config', 'nodes', 'links']
    """Calls to set_dict will fail if any of these keys are missing"""

    def __init__(self, variant: Literal['Sheet', 'Function'], id_: int, id_providers: IdProviders, app_state: state.AppState) -> None:
        self.variant = variant
        """Sheet Variant: Sheet or Function"""
        self.id_providers = id_providers
        """Local pointer to workspace-wide id providers instance"""
        self.app_state = app_state
        """Local pointer to global app state"""
        self.id = WorkspaceSheetId(id_)
        """Unique id of this sheet; this ID is NOT synched with IMGUI backend, but we style the object the same for consistency"""
        self.config = WorkspaceSheetConfig()
        """Configuration specific to this sheet"""
        self.nodes: list[Node] = []
        """The list of nodes in this sheet"""
        self.links: list[LinkInfo] = []
        """List of links between pins on nodes in this sheet"""
        self.next_selected = None
        """If set to a NodeId, set that node as focused/selected at top of next frame (and then reset value to None)"""
        self._calc_status: NodeCalcStatus = NodeCalcStatus.Idle
        """
        Status of node calculation for this sheet; reflects the status of Re-Calc All, and Re-Calc Changed
            This is also used to reflect the status of calculation of a Function Sheet
        """
        self._calc_message: str = ''
        """(internal) message returned by last completed calculation"""
        self._calc_traceback: str = ''
        """(internal) stack traceback returned by last completed calculation"""
        # Specific to Function Sheets only
        self.sheet_output_node_id: NodeId = None
        """Function Sheet Only: the NodeId of the Function Outputs node which is mandatory for Function Sheets;
            Highlander rules: There can only be one (per function sheet)!"""
        self.sheet_input_node_id: NodeId = None
        """Function Sheet Only: the NodeId of the Function Inputs node which is mandatory for Function Sheets;
            Highlander rules: There can only be one (per function sheet)!"""
        self.sheet_output_values: list[Any] = []  # sheet output values, to be accessed by other sheets
        """Function Sheet Only: output values of last call to use_sheet()"""
        self.sheet_input_values: list[Any] = []  # sheet input values, to be provided by other sheets
        """Function Sheet Only: input values, used when calling use_sheet()"""
        self.last_recalc: int = 0
        """Last time (in milliseconds) this sheet did a re-calculation"""
        self.min_time_between_recalc: float = self.app_state.app_config.get('auto_recalc_time')
        """Milliseconds, minimum time between automatic recalcs"""

    # Workspace Sheet Lifecycle

    def reset(self):
        """Clear/Reset this sheet to default, empty state"""
        self.id_providers.Node.reset()
        self.id_providers.Link.reset()
        self.id_providers.Pin.reset()
        self.nodes = []
        self.links = []
        self.config = WorkspaceSheetConfig()

    @ensure_serializable
    def get_dict(self) -> dict:
        """Get this sheet as a json serializable dict, to write to file"""
        data = {}
        data['id'] = self.id.id()
        data['config'] = self.config.to_dict()

        data['nodes'] = []
        for node in self.nodes:
            data['nodes'].append(node.get_dict())

        data['links'] = []
        for link in self.links:
            data['links'].append(link.get_dict())

        if self.sheet_output_node_id is not None:
            data['output_node_id'] = self.sheet_output_node_id.id()
        else:
            data['output_node_id'] = None

        if self.sheet_input_node_id is not None:
            data['input_node_id'] = self.sheet_input_node_id.id()
        else:
            data['input_node_id'] = None

        return data

    def set_dict(self, data: dict):
        """Set this sheet's state from dict"""
        try:
            for keyname in self.required_keys:
                if keyname not in data:
                    raise KeyError(f'Missing required key: {keyname}')
            self.config.set_dict(data['config'])
            # TODO renumber ids from local id providers, so we can support importing from another file
            for node in data['nodes']:
                if node['class'] not in self.app_state.all_node_classes:
                    raise WorkspaceException(f'Could not find node class: {node["class"]}')
                node_class: type[Node] = self.app_state.all_node_classes[node['class']]
                node_obj = node_class(node['id'], self.id_providers, self.app_state, position=Vec2(node['pos_x'], node['pos_y']), init_pin_ids=False)
                node_obj.set_dict(node)
                if isinstance(node_obj, SpecialNode):
                    node_obj.special_setup(self)
                self.nodes.append(node_obj)
            for link in data['links']:
                link_color = global_ui_state.vartype_colors[get_vartype(link['var_type'])]
                link_obj = LinkInfo.from_dict(link, link_color)
                self.links.append(link_obj)
            if 'input_node_id' in data:
                if data['input_node_id'] is not None:
                    node = self.find_node(data['input_node_id'])
                    self.sheet_input_node_id = node.node_id
            if 'output_node_id' in data:
                if data['output_node_id'] is not None:
                    node = self.find_node(data['output_node_id'])
                    self.sheet_output_node_id = node.node_id
        except Exception as ex:
            raise WorkspaceException('Failed to set sheet state from dict!') from ex

    def set_calc_status(self, status: NodeCalcStatus, message: str = '', traceback: str = ''):
        """Set the status of sheet calculation"""
        self._calc_status = status
        self._calc_message = message
        self._calc_traceback = traceback

    def get_calc_status(self) -> NodeCalcStatus:
        """Get the status of sheet calculation"""
        return self._calc_status

    def process_nodes(self, nodes: list[set[int]]):
        """
        Process sets of nodes (the output of build_dependency_graph), by submitting to the backend and waiting for members of each set to complete
        """
        try:
            self.last_recalc = time_millis()
            processed_nodes: list[int] = []
            self.app_state.status_text = 'Processing nodes...'
            self.set_calc_status(NodeCalcStatus.Processing)
            start_time = time_millis()
            all_ok = True
            for node_set in nodes:
                # kick off calc jobs in this set
                for node_id in node_set:
                    if node_id in processed_nodes:
                        raise CircularDependencyException(f'Circular dependency detected! Already processed node: {node_id}')
                    this_node = self.find_node(node_id)
                    if this_node.node_kind == NodeKind.Static:
                        # static nodes just get refreshed on this thread, no calcjob needed
                        static_start = time_nano()
                        outputs = this_node.refresh()
                        self.update_outputs(this_node.node_id.id(), outputs)
                        static_duration = time_nano() - static_start
                        this_node.set_calc_status(NodeCalcStatus.Success)
                        this_node.calc_time = static_duration
                        this_node.mark_unchanged()
                    else:

                        input_values = []
                        for ent in this_node.inputs:
                            input_values.append(ent.value)
                        # prepare calcjob
                        new_job = CalcJob(input_values, this_node.__class__, this_node.config, this_node.common_config, node_id)
                        self.app_state.backend.submit(new_job, self.handle_calc_result)
                        processed_nodes.append(node_id)
                        this_node.set_calc_status(NodeCalcStatus.Processing)
                # wait for calc jobs in this set to complete
                for node_id in node_set:
                    this_node = self.find_node(node_id)
                    waited = 0.0
                    self.app_state.backend.check()
                    while this_node.get_calc_status() == NodeCalcStatus.Processing:
                        time.sleep(self.calc_check_delay)
                        waited += self.calc_check_delay
                        if waited > self.calc_timeout:
                            self.app_state.status_text = f'Timed out after {self.calc_timeout}s waiting for calc jobs!'
                            log.error('Timed out waiting for calc jobs!')
                            this_node.set_calc_status(NodeCalcStatus.TimedOut)
                            all_ok = False
                            break
                        self.app_state.backend.check()
                    if this_node.get_calc_status() != NodeCalcStatus.Success:
                        all_ok = False
                        break
                # if not all jobs in this set succeeded, we cannot calculate further sets
                if not all_ok:
                    break
            duration = round(time_millis() - start_time, 2)
            if all_ok:
                self.app_state.status_text = f'Node processing took {duration}ms'
                self.set_calc_status(NodeCalcStatus.Success)
            else:
                self.set_calc_status(NodeCalcStatus.Error)
                self.app_state.status_text = f'Node processing failed after {duration}ms!'
        except Exception as ex:
            self.app_state.status_text = f'Error processing nodes: {str(ex)}'
            log.error(f'Exception while process_nodes: {str(ex)}')
            log.error(format_exc())

    def handle_calc_result(self, result: CalcJobResult):
        """Handler for callback on completed calculation job"""
        this_node = self.find_node(result.node_id)
        if result.error:
            log.error(f'Error while processing job: {result.job_id} for node id: {result.node_id}: {result.error_message}')
            if self.app_state.app_config.get('log_calcjob_error_traceback'):
                log.error(result.error_traceback)
            this_node.set_calc_status(NodeCalcStatus.Error, result.error_message, result.error_traceback)
        else:
            self.update_outputs(result.node_id, result.outputs)

            this_node = self.find_node(result.node_id)
            if isinstance(this_node, SpecialNode):
                log.debug(f'handling special_execute for node type: {this_node.node_display}')
                this_node.special_execute(self)

            this_node.set_calc_status(NodeCalcStatus.Success)
            this_node.calc_time = result.duration
            if this_node.__class__.__name__ == 'ValueNode':
                this_node.config.set('value', result.outputs[0])
            this_node.mark_unchanged()

    def update_outputs(self, node_id: int, output_values: list):
        """Update output values of a node, from the given list of values"""
        this_node = self.find_node(node_id)
        for odx, val in enumerate(output_values):
            this_node.outputs[odx].value = val
            # also update any linked inputs
            lnks = self.find_links_from_pinid(this_node.outputs[odx].pin_id)
            for lnk in lnks:
                that_node = self.find_node(lnk.input_node_id.id())
                for input_ in that_node.inputs:
                    if input_.pin_id == lnk.input_id:
                        input_.value = val

    def recalc_all(self):
        """Re-Calculate all nodes in this sheet"""
        # TODO we need to exclude nodes which cannot be calculated due to missing inputs
        all_nodeids = [n.node_id.id() for n in self.nodes]
        work = self.build_dependency_graph(all_nodeids)
        if self.app_state.app_config.get('log_calcjob_dependency_graphs'):
            self.print_dependency_graph(work)
        self.process_nodes(work)

    def recalc_auto(self):
        """Auto Re-Calculate any changed nodes in this sheet, if enabled"""
        if self.variant == 'Sheet':  # only auto-recalc for top level sheets, no other variants
            if self.app_state.app_config.get('auto_recalc'):
                if time_millis() - self.last_recalc > self.min_time_between_recalc:
                    work = self.find_changed()
                    # print(work)
                    if len(work) > 0:
                        if len(work[0]) > 0:
                            if self.app_state.app_config.get('auto_recalc_log'):
                                log.info('Auto-recalculating due to changes')
                            if self.app_state.app_config.get('log_calcjob_dependency_graphs'):
                                self.print_dependency_graph(work)
                            self.process_nodes(work)

    def find_changed(self) -> list[set[int]]:
        """Find changed nodes that need recalc"""
        changed_nodeids: list[int] = []
        for node in self.nodes:
            if node.has_changed():
                changed_nodeids.append(node.node_id.id())
        all_affected_nodeids = self.build_dependency_list(changed_nodeids)
        work = self.build_dependency_graph(all_affected_nodeids)
        return work

    def recalc_changed(self):
        """Re-Calculate all nodes with changes (or dependent on those with changes)"""
        work = self.find_changed()
        if len(work) > 0:
            if len(work[0]) > 0:
                if self.app_state.app_config.get('log_calcjob_dependency_graphs'):
                    self.print_dependency_graph(work)
                self.process_nodes(work)

    def use_sheet(self, inputs: list[Any]) -> list[Any]:
        """Use this sheet with given set of sheet inputs, and return sheet outputs; this is the how Function Sheets work"""
        previous_values = self.sheet_input_values
        self.sheet_input_values = inputs
        all_nodeids = [n.node_id.id() for n in self.nodes]
        work = self.build_dependency_graph(all_nodeids)
        self.process_nodes(work)
        output = deepcopy(self.sheet_output_values)
        self.sheet_input_values = previous_values
        return output

    def propagate_changed(self):
        """Propagate change flag thru dependency chain"""
        changed_nodeids: list[int] = []
        list_of_nodes = copy(self.nodes)
        for node in list_of_nodes:
            if node.has_changed():
                changed_nodeids.append(node.node_id.id())
        all_affected_nodeids = self.build_affected_list(changed_nodeids)
        for node_id in all_affected_nodeids:
            try:
                node = self.find_node(node_id)
                node.mark_changed()
            except ValueError:
                log.warning(f'Skipping propagation for invalid node id: {node_id}')

    # housekeeping
    def on_frame(self):
        """Do per-frame tasks"""
        self.min_time_between_recalc: float = self.app_state.app_config.get('auto_recalc_time')
        self.recalc_auto()

    # Node Lifecycle

    def new_node(self, node_class: type[Node]):
        """Add a new node to this sheet"""
        node_id = self.id_providers.Node.next_id()
        if issubclass(node_class, SpecialNode):
            allowed = node_class.special_precheck(self, self.app_state)
            if not allowed:
                log.warning(f'Not allowed to create node of type: {node_class.node_display}')
                return
        new_node = node_class(node_id, self.id_providers, self.app_state)
        if isinstance(new_node, SpecialNode):
            new_node.special_setup(self)
        self.nodes.append(new_node)
        self.next_selected = new_node.node_id

    def delete_node(self, node_id: NodeId):
        """Delete given node; checks if deletion is allowed should already have happened before this"""
        # remove any links connected to this node
        for lnk in self.links:
            if node_id in (lnk.output_node_id, lnk.input_node_id):
                self.delete_link(lnk.id)

        # then remove node from your data
        for node in self.nodes:
            if node.node_id == node_id:
                self.nodes.remove(node)
                break

    # Link Lifecycle

    def create_link(self, input_pin_id: PinId, output_pin_id: PinId, app_state: state.AppState):
        """Create a link (no checks performed)"""
        input_iopin = self.find_iopin(input_pin_id)
        output_iopin = self.find_iopin(output_pin_id)

        # ed.AcceptNewItem(): return true when user release mouse button.
        if ed.accept_new_item():
            app_state.status_text = f'Link Created: {output_iopin.io_type.name} -> {input_iopin.io_type.name}'
            log.info(f'Link Created: {output_iopin.io_type.name} -> {input_iopin.io_type.name}')
            # Since we accepted new link, lets add one to our list of links.
            color = NormalizedColorRGBA(1.0, 1.0, 1.0, 1.0)
            if output_iopin.io_type in global_ui_state.vartype_colors:
                color = global_ui_state.vartype_colors[output_iopin.io_type]
            link_info = LinkInfo(
                LinkId(self.id_providers.Link.next_id()), input_iopin.pin_id, input_iopin.node_id, output_iopin.pin_id, output_iopin.node_id, output_iopin.io_type, color
            )
            self.links.append(link_info)

            # Draw new link.
            ed.link(
                self.links[-1].id,
                self.links[-1].input_id,
                self.links[-1].output_id,
                self.links[-1].color.to_imcolor(),
            )

    def attempt_link(self, from_pinid: PinId, to_pinid: PinId, app_state: state.AppState):
        """
        Attempt to create a link between the two pins, performing all checks first
            Checks performed in order: Rules, Safety, Type compatibility
        """
        # NOTE: this runs within ed.query_new_link(from_pinid, to_pinid)
        #   so we MUST call ed.reject_new_item() or self.create_link() within this method
        from_iopin = self.find_iopin(from_pinid)
        to_iopin = self.find_iopin(to_pinid)

        # Identify which pin is output and input
        # NOTE: at this point, we're really checking if the from/to have been swapped
        #   because user can drag from output, or from input
        #   check_link_rules will handle checking that the two input pins are of different kinds (one output, one input)
        if from_iopin.io_kind == IOKind.Output:
            output_iopin = from_iopin
            input_iopin = to_iopin
        else:
            output_iopin = to_iopin
            input_iopin = from_iopin

        # perform link checks
        (valid, reason) = self.check_link_rules(input_iopin.pin_id, output_iopin.pin_id)
        if not valid:
            app_state.status_text = f'Link Rejected: [Rules] {reason}'
            ed.reject_new_item()
            return

        (valid, reason) = self.check_link_safety(input_iopin.pin_id, output_iopin.pin_id)
        if not valid:
            app_state.status_text = f'Link Rejected: [Safety] {reason}'
            ed.reject_new_item()
            return

        (valid, reason) = self.check_link_types(input_iopin.pin_id, output_iopin.pin_id)
        if not valid:
            app_state.status_text = f'Link Rejected: [Types] {reason}'
            ed.reject_new_item()
            return

        app_state.status_text = ''
        self.create_link(input_iopin.pin_id, output_iopin.pin_id, app_state)

    def delete_link(self, link_id: LinkId):
        """Delete given link; checks if deletion is allowed should already have happened before this"""
        # set input values to None (otherwise will keep existing value)
        #   output values remain as is
        lnk = self.find_link(link_id)
        if lnk is not None:
            try:
                that_node = self.find_node(lnk.input_node_id)
                that_node.mark_changed()
                for input_ in that_node.inputs:
                    if input_.pin_id == lnk.input_id:
                        input_.value = None
                        input_.linked = False
            except ValueError:
                pass
        # Then remove link from your data.
        for lnk in self.links:
            if lnk.id == link_id:
                self.links.remove(lnk)
                break

    # Node Utility

    def find_node(self, node_id: Union[NodeId, int]) -> Node:
        """Find and return the node with given node id"""
        if isinstance(node_id, NodeId):
            for entry in self.nodes:
                if node_id == entry.node_id:
                    return entry
            raise ValueError(f'Could not find node with id: {node_id.id()}')
        for entry in self.nodes:
            if node_id == entry.node_id.id():
                return entry
        raise ValueError(f'Could not find node with id: {node_id}')

    def ok_to_delete_node(self, node_id: NodeId) -> bool:
        """Check if allowed to delete this node"""
        node = self.find_node(node_id)
        if not node.deletable:
            return False
        return True

    def is_linked(self, pin_id: Union[PinId, int]) -> bool:
        """Check if given pin is a member of a link"""
        if isinstance(pin_id, PinId):
            for lnk in self.links:
                if pin_id == lnk.input_id:
                    return True
                if pin_id == lnk.output_id:
                    return True
        else:
            for lnk in self.links:
                if pin_id == lnk.input_id.id():
                    return True
                if pin_id == lnk.output_id.id():
                    return True
        return False

    def find_iopin(self, pin_id: Union[PinId, int]) -> IOPin:
        """Find and return IOPin with given pin id"""
        if isinstance(pin_id, PinId):
            for node in self.nodes:
                for input_iopin in node.inputs:
                    if pin_id == input_iopin.pin_id:
                        return input_iopin
                for output_iopin in node.outputs:
                    if pin_id == output_iopin.pin_id:
                        return output_iopin
            raise ValueError(f'Could not find IOPin with pinid: {pin_id.id()}!')
        for node in self.nodes:
            for input_iopin in node.inputs:
                if pin_id == input_iopin.pin_id.id():
                    return input_iopin
            for output_iopin in node.outputs:
                if pin_id == output_iopin.pin_id.id():
                    return output_iopin
        raise ValueError(f'Could not find IOPin with pinid: {pin_id}!')

    def node_exists(self, node_id: NodeId) -> bool:
        """Check if node exists on this sheet"""
        for node in self.nodes:
            if node.node_id == node_id:
                return True
        return False

    # Link Utility

    def find_link(self, link_id: Union[LinkId, int]) -> LinkInfo:
        """Find and return the link with given link id"""
        if isinstance(link_id, LinkId):
            for lnk in self.links:
                if link_id == lnk.id:
                    return lnk
                if link_id == lnk.id:
                    return lnk
            raise ValueError(f'Could not find link with id: {link_id.id()}')
        for lnk in self.links:
            if link_id == lnk.id.id():
                return lnk
            if link_id == lnk.id.id():
                return lnk
        raise ValueError(f'Could not find link with id: {link_id}')

    def find_links_from_pinid(self, pin_id: Union[PinId, int]) -> list[LinkInfo]:
        """Get a list of all links of which the IOPin with given pin id is a member"""
        found_links: list[LinkInfo] = []
        if isinstance(pin_id, PinId):
            for lnk in self.links:
                if pin_id == lnk.input_id:
                    found_links.append(lnk)
                if pin_id == lnk.output_id:
                    found_links.append(lnk)
        else:
            for lnk in self.links:
                if pin_id == lnk.input_id.id():
                    found_links.append(lnk)
                if pin_id == lnk.output_id.id():
                    found_links.append(lnk)
        return found_links

    def check_link_rules(self, input_pin_id: PinId, output_pin_id: PinId) -> tuple[bool, str]:
        """
        Check if a link between the two given pins is allowed, per linking rules
            returns tuple[ok:bool, reason:str]
        """
        input_iopin = self.find_iopin(input_pin_id)
        output_iopin = self.find_iopin(output_pin_id)

        # Rule: pins must be of different kind (cannot both be input or output)
        if input_iopin.io_kind == output_iopin.io_kind:
            return (False, f'Both pins are {input_iopin.io_kind.name}')

        # Rule: an input pin can only be linked to a single output
        #   but an output pin can be linked to several different inputs
        #   this also catches the case where these two particular pins are already linked
        if self.is_linked(input_iopin.pin_id):
            return (False, f'Input pin: {input_iopin.pin_id.id()} is already linked !')

        return (True, '')

    def check_link_safety(self, input_pinid: PinId, output_pinid: PinId) -> tuple[bool, str]:
        """
        Check if a link between the two given pins would be safe, would not cause dependency loop
            returns tuple[ok:bool, reason:str]
        """
        input_iopin = self.find_iopin(input_pinid)
        output_iopin = self.find_iopin(output_pinid)

        # Rule: cannot link two pins from the same node
        if output_iopin.node_id == input_iopin.node_id:
            return (False, f'Both pins are from the same node: {output_iopin.node_id.id()} !')

        # Rule: input pin node dependents cannot include output pin node
        dependent_nodeids = self.build_affected_list([input_iopin.node_id.id()])
        if output_iopin.node_id.id() in dependent_nodeids:
            return (False, 'Output pin node is a dependent of input pin node! Link would cause circular dependency!')

        return (True, '')

    def check_link_types(self, input_pinid: PinId, output_pinid: PinId) -> tuple[bool, str]:
        """
        Check if a link between the two given pins would be valid, based on VarType
            returns tuple[ok:bool, reason:str]
        """
        input_iopin = self.find_iopin(input_pinid)
        output_iopin = self.find_iopin(output_pinid)

        if input_iopin.io_type == output_iopin.io_type:
            return (True, '')
        else:
            if input_iopin.io_type == VarType.Any:
                return (True, '')
            elif input_iopin.io_type == VarType.Number:
                if output_iopin.io_type in VARTYPE_NUMBER_TYPES:
                    return (True, '')

        return (False, f'Incompatible types: {output_iopin.io_type.name} -> {input_iopin.io_type.name}')

    def ok_to_delete_link(self, _link_id: LinkId) -> bool:
        """check if allowed to delete this link"""
        # NOTE: for the moment, we accept all delete attempts
        return True

    # Dependency Tracing: these methods reference nodes by integer id, not NodeId

    @ staticmethod
    def resolve_dependency_groups(arg: dict[int, set[int]]) -> list[set[int]]:
        """
        Resolve dependencies, returning a list of sets of nodes that can be processed in parallel, in the order required
            "arg" is a dependency dictionary in which
            the values are the dependencies of their respective keys.
            https://stackoverflow.com/questions/5287516/dependencies-tree-implementation
            d=dict(
                a=('b','c'),
                b=('c','d'),
                e=(),
                f=('c','e'),
                g=('h','f'),
                i=('f',)
            )
            print dep(d)
            [{'h', 'd', 'c', 'e'}, {'f', 'b'}, {'a', 'g', 'i'}]
        """
        d = dict((k, set(arg[k])) for k in arg)
        r = []
        # found_circle = False
        while d:
            # values not in keys (items without dep)
            t = set(i for v in d.values() for i in v)-set(d.keys())

            # and keys without value (items without dep)
            t.update(k for k, v in d.items() if not v)

            # circular dependency check
            #   NOTE this does not work! it detects circular dependency when there is none!
            #   instead, in process_nodes() we track already-processed nodes, and raise if we process the same nodeid twice
            # Just check if t is empty at any iteration after the t.update() statement.
            #   If it is, then you can imply that there isn't a circular dependency at this stage of the iteration
            # if len(t) > 0:
            #     found_circle = True
            #     break

            # can be done right away
            r.append(t)

            # and cleaned up
            d = dict(((k, v-t) for k, v in d.items() if v))
        # if found_circle:
        #     raise ValueError('Circular dependency detected!')
        return r

    def build_dependency_graph(self, node_ids: list[int]) -> list[set[int]]:
        """
        Build list of sets of nodes, ordered by dependencies so we can process them in correct order
        """
        # first build a dict of nodeids, each a set of all other nodeids it depends on (outputting connections this node inputs)
        dep_dict = {}
        for node_id in node_ids:
            node = self.find_node(node_id)
            node_set = set()
            needs_calc = False
            if len(node.inputs) > 0:
                for input_iopin in node.inputs:
                    lnks = self.find_links_from_pinid(input_iopin.pin_id)
                    if len(lnks) == 1:
                        node_set.add(lnks[0].output_node_id.id())
                        needs_calc = True
                    if len(lnks) > 1:
                        raise ValueError(f'Input pin {input_iopin.pin_id.id()} is a member of more than one link!')
            if len(node.outputs) > 0:
                for output_iopin in node.outputs:
                    if self.is_linked(output_iopin.pin_id):
                        needs_calc = True
            if needs_calc:
                dep_dict[node.node_id.id()] = node_set
        # TODO: analyze dep_dict for circular dependencies prior to resolving
        # if self.app_state.app_config.get('log_calcjob_dependency_graphs'):
        #     self.print_dependency_graph(dep_dict)
        # next, let dependency solver figure out the order and grouping
        dep_groups = self.resolve_dependency_groups(dep_dict)
        # if self.app_state.app_config.get('log_calcjob_dependency_graphs'):
        #     self.print_dependency_graph(dep_groups)
        return dep_groups

    def build_dependency_list(self, node_ids: list[int]) -> set[int]:
        """
        Given a set of node_ids, return a larger set including dependencies
            Left-growing tree: all nodes that the given nodes depend on for INPUT
        """
        # first seed the set with given node ids
        node_set: set[int] = set()
        for nid in node_ids:
            node_set.add(nid)

        # then, loop through, adding dependent node ids until node_set stops being larger than checked_nodeids
        #   track checked nodeids, so we cant go on forever
        checked_nodeids: set[int] = set()
        while len(node_set) > len(checked_nodeids):
            # process any new node ids, which may result in the set growing
            node_set_copy = deepcopy(node_set)  # iterate over a copy, because the set will size will change
            for node_id in node_set_copy:
                if node_id in checked_nodeids:
                    continue
                node = self.find_node(node_id)
                if len(node.inputs) > 0:
                    for input_iopin in node.inputs:
                        lnks = self.find_links_from_pinid(input_iopin.pin_id)
                        if len(lnks) == 1:
                            node_set.add(lnks[0].output_node_id.id())
                        if len(lnks) > 1:
                            raise ValueError(f'Input pin {input_iopin.pin_id.id()} is a member of more than one link!')
                checked_nodeids.add(node_id)

        return node_set

    def build_affected_list(self, node_ids: list[int]) -> set[int]:
        """
        Given a set of node_ids, return a larger set including dependents
            Right-growing tree: all nodes that depend on the given nodes for OUTPUT
        """
        # first seed the set with given node ids
        node_set: set[int] = set()
        for nid in node_ids:
            node_set.add(nid)

        # then, loop through, adding dependent node ids until node_set stops being larger than checked_nodeids
        #   track checked nodeids, so we cant go on forever
        checked_nodeids: set[int] = set()
        while len(node_set) > len(checked_nodeids):
            # process any new node ids, which may result in the set growing
            node_set_copy = deepcopy(node_set)  # iterate over a copy, because the set will size will change
            for node_id in node_set_copy:
                if node_id in checked_nodeids:
                    continue
                try:
                    node = self.find_node(node_id)
                except ValueError:
                    log.warning(f'Skipping invalid node id: {node_id}')
                    checked_nodeids.add(node_id)
                    if node_id in node_set:
                        node_set.remove(node_id)
                    continue
                if len(node.outputs) > 0:
                    for output_iopin in node.outputs:
                        lnks = self.find_links_from_pinid(output_iopin.pin_id)
                        for lnk in lnks:
                            node_set.add(lnk.input_node_id.id())
                checked_nodeids.add(node_id)

        return node_set

    @ staticmethod
    def print_dependency_graph(node_sets: Union[list[set[int]], dict[int, set[int]]]):
        """Helper to visualize contents of dependency list or dict"""
        if isinstance(node_sets, list):
            log.debug('Dependency Graph (second pass):')
            if len(node_sets) == 0:
                log.debug('  (none)')
            for this_set in node_sets:
                log.debug(f'  {this_set}')
        elif isinstance(node_sets, dict):
            log.debug('Dependencies (first pass):')
            for this_node, this_set in node_sets.items():
                if len(this_set) == 0:
                    log.debug(f'  {this_node}: none')
                else:
                    log.debug(f'  {this_node}: {this_set}')


class ViewBookmark:
    """A simple view bookmark"""

    def __init__(self, variant: Literal['Sheet', 'Function'] = 'Sheet', sheet_id: WorkspaceSheetId = 0, selected_nodes: list[NodeId] = None, label: str = 'Un-named view') -> None:
        self.variant: Literal['Sheet', 'Function'] = variant
        self.sheet_id: WorkspaceSheetId = sheet_id
        self.selected_nodes: list[NodeId] = selected_nodes
        if self.selected_nodes is None:
            self.selected_nodes = []
        self.label = label

    def get_dict(self) -> dict:
        """Create serializable dict"""
        return {
            'variant': self.variant,
            'sheet_id': self.sheet_id.id(),
            'selected_nodes': [n.id() for n in self.selected_nodes],
            'label': self.label,
        }

    def set_dict(self, data: dict):
        """Set values from dict"""
        self.variant = data['variant']
        self.sheet_id = WorkspaceSheetId(data['sheet_id'])
        self.selected_nodes = [NodeId(n) for n in data['selected_nodes']]
        self.label = data['label']

    def rename(self, label: str):
        """Rename this View Bookmark"""
        self.label = label


class Workspace:
    """
    An entire single Workspace
        A workspace contains a list of Sheets, and a list of Function Sheets, and represents the entire persistent state of the app (minus app config)
        It handles saving/loading/importing of all workspace contents to/from file
    """
    required_keys = ['config', 'sheets']
    """Calls to set_dict() will fail if any of these keys are missing"""

    def __init__(self, app_state: state.AppState) -> None:
        self.app_state = app_state
        """Local pointer to global app state"""
        self._file: Path = None
        """Full path to on-disk file, where this workspace will be saved; None if workspace has never been saved"""
        self.id_providers = IdProviders()
        """Workspace id providers, used by everything to ensure unique and stable ids, particulary for IMGUI"""
        self.sheets: list[WorkspaceSheet] = []
        """List of Sheets in this workspace"""
        self.function_sheets: list[WorkspaceSheet] = []
        """List of special Function Sheets in this workspace; re-usable sheets with their own local inputs and outputs, that can be used as a single node"""
        self.config = WorkspaceConfig()
        """Configuration specific to this workspace"""
        self.new_sheet()  # a workspace always includes at least one Sheet, but may have zero Function Sheets
        self.new_sheet(variant='Function')
        self._pending_save_overwrite_path: Path = None
        """(internal) if there is a pending confirmation dialog to overwrite an existing workspace file, this is the path to that file"""
        self._pending_save_overwrite_details = ''
        """(internal) if there is a pending confirmation dialog to overwrite an existing workspace file, this is the body of that dialog (Are you sure you want to...)"""
        self._pending_save_overwrite_open: bool = False
        """(internal) flag tracking if save overwrite dialog is open"""
        self.view_bookmarks: list[ViewBookmark] = []
        """View Bookmarks"""
        self._pending_single_parameter_param: ConfigParameter = None
        """(internal) pending single parameter input: Config parameter"""
        self._pending_single_parameter_details: str = ''
        """(internal) pending single parameter input: details text to show above input"""
        self._pending_single_parameter_callback: Callable[[Any, Any]] = None
        """(internal) pending single parameter input: function taking: value, data (where data is an optional value passed)"""
        self._pending_single_parameter_callback_data: Any = None
        """(internal) pending single parameter input: optional addional data"""
        self._pending_single_parameter_open: bool = False
        """(internal) flag tracking if single parameter input dialog is open"""
        self._config_input_renderer = ConfigParamRenderer(self.app_state)
        """(internal) Config param renderer for general use"""

    # Workspace lifecycle

    def clear(self):
        """Clear the workspace, in preparation for loading from a file (no default sheets)"""
        self._file = None
        self.sheets = []
        self.function_sheets = []
        self.view_bookmarks = []
        self.id_providers.reset()
        self.app_state.panes.SheetEditor.clear()
        self.app_state.panes.FunctionEditor.clear()
        self.config = WorkspaceConfig()

    def reset_to_default(self):
        """Reset this workspace to a default state, with a single empty Sheet, and single empty Function"""
        self.clear()
        self.config.set('name', 'Untitled Workspace')

        # an empty workspace always starts with one empty sheet, and one empty function; both are selected
        self.new_sheet(variant='Sheet')
        self.new_sheet(variant='Function')
        self.app_state.panes.SheetEditor.select_first_sheet()
        self.app_state.panes.FunctionEditor.select_first_sheet()

    @ensure_serializable
    def get_dict(self) -> dict:
        """Get this workspace as a json serializable dict, to write to file"""
        try:
            data = {}
            data['config'] = self.config.to_dict()

            data['sheets'] = []
            for sheet in self.sheets:
                data['sheets'].append(sheet.get_dict())

            data['function_sheets'] = []
            for sheet in self.function_sheets:
                data['function_sheets'].append(sheet.get_dict())

            data['view_bookmarks'] = []
            for view in self.view_bookmarks:
                data['view_bookmarks'].append(view.get_dict())

            return data
        except Exception as ex:
            raise WorkspaceException('Failed to get json serializable dict from workspace!') from ex

    def set_dict(self, data: dict):
        """Set this sheet's state from dict"""
        try:
            for keyname in self.required_keys:
                if keyname not in data:
                    raise KeyError(f'Missing required key: {keyname}')
            self.config.set_dict(data['config'])
            self.rebase_id_providers(data)
            # function sheets
            if 'function_sheets' in data:
                for sheet in data['function_sheets']:
                    sheet_obj = WorkspaceSheet('Function', sheet['id'], self.id_providers, self.app_state)
                    sheet_obj.set_dict(sheet)
                    self.function_sheets.append(sheet_obj)
                self.app_state.panes.FunctionEditor.select_first_sheet()
            # create sheets using their existing ids
            if 'sheets' in data:
                for sheet in data['sheets']:
                    sheet_obj = WorkspaceSheet('Sheet', sheet['id'], self.id_providers, self.app_state)
                    sheet_obj.set_dict(sheet)
                    self.sheets.append(sheet_obj)
                self.app_state.panes.SheetEditor.select_first_sheet()

            # view bookmarks
            if 'view_bookmarks' in data:
                for view in data['view_bookmarks']:
                    new_view = ViewBookmark()
                    new_view.set_dict(view)
                    self.view_bookmarks.append(new_view)

        except Exception as ex:
            raise WorkspaceException('Failed to set workspace state from dict!') from ex

    def save_as(self):
        """Show a Save As dialog, then save to chosen file path"""
        imfd.save('SaveAsDialog',
                  'Save As...',
                  f'Workspace file (*.{WORKSPACE_FILE_EXT}){{.{WORKSPACE_FILE_EXT}}},',  # remember trailing comma!
                  str(self.app_state.app_config.get('default_workspaces_folder')))

    def save(self):
        """Save to file; if file path is not set, calls save_as() instead"""
        if self._file is None:
            self.save_as()
            return
        file_data = self.get_dict()
        try:
            json_data = json.dumps(file_data)
            with open(self._file, 'wt', encoding='utf-8') as wf:
                wf.write(json_data)
        except Exception as ex:
            raise WorkspaceException('Failed to save workspace to file!') from ex
        log.info(f'Successfully saved workspace: {str(self._file)}')
        self.app_state.unsaved_changes = False

    def open(self):
        """Show an Open File dialog, then open the selected workspace file"""
        # NOTE: followup tasks (after dialog is completed) handled in on_frame()
        imfd.open('OpenFileDialog',
                  'Open file...',
                  f'Workspace file (*.{WORKSPACE_FILE_EXT}){{.{WORKSPACE_FILE_EXT}}},',  # remember trailing comma!
                  False,
                  str(self.app_state.app_config.get('default_workspaces_folder')))

    def rebase_id_providers(self, data: dict):
        """Analyze the highest ids contained in the given data, and adjust global id providers to start above the highest existing ids"""
        highest_sheet_id = 0
        highest_node_id = 0
        highest_pin_id = 0
        highest_link_id = 0
        sheet_list: list = copy(data['sheets'])
        sheet_list.extend(data['function_sheets'])
        for sheet in sheet_list:
            if int(sheet['id']) > highest_sheet_id:
                highest_sheet_id = int(sheet['id'])
            for node in sheet['nodes']:
                if int(node['id']) > highest_node_id:
                    highest_node_id = int(node['id'])
                for pin in node['inputs']:
                    if int(pin['id']) > highest_pin_id:
                        highest_pin_id = int(pin['id'])
                for pin in node['outputs']:
                    if int(pin['id']) > highest_pin_id:
                        highest_pin_id = int(pin['id'])
            for link in sheet['links']:
                if int(link['id']) > highest_link_id:
                    highest_link_id = int(link['id'])
        self.id_providers.Sheet.rebase(highest_sheet_id + 1)
        self.id_providers.Node.rebase(highest_node_id + 1)
        self.id_providers.Pin.rebase(highest_pin_id + 1)
        self.id_providers.Link.rebase(highest_link_id + 1)

    def set_file(self, file: Path):
        """Set file path for saving/loading"""
        self._file = file

    def get_file(self) -> Union[Path, None]:
        """Get current file path used for saving/loading"""
        return self._file

    def import_wk(self):
        """Import sheets from another workspace file"""
        # TODO implement import from other worksheet, after we implement id rewriting
        log.warning('Import from another workspace: not implemented yet!')

    def _load_from_file(self, new_file: Path):
        """Load from file"""
        self.clear()
        self.set_file(new_file)
        try:
            with open(self._file, 'rt', encoding='utf-8') as wf:
                json_data = wf.read()
            file_data = json.loads(json_data)
        except Exception as ex:
            raise WorkspaceException('Failed to load workspace from file!') from ex

        # TODO: re-id file_data before calling set_dict
        self.set_dict(file_data)
        log.info(f'Successfully loaded workspace: {str(self._file)}')
        self.app_state.unsaved_changes = False

    def _import_from(self, file_: Path, config_keys: list[str], sheet_ids: list[int]):
        """From the given file, import given workspace config keys and sheets into current workspace, without clearing"""
        # TODO implement import_from

    # Sheets

    def new_sheet(self, variant: Literal['Sheet', 'Function'] = 'Sheet'):
        """Add a new sheet"""
        sheet_id = self.id_providers.Sheet.next_id()
        new_sheet = WorkspaceSheet(variant, sheet_id, self.id_providers, self.app_state)
        # generate a unique default name, so freshly created sheets dont all end up named "Untitled"
        count = 1
        new_name = f'Untitled {variant} {count}'
        while self.is_sheet_name_taken(new_name):
            count += 1
            new_name = f'Untitled {variant} {count}'
        new_sheet.config.set('name', new_name)
        self.app_state.unsaved_changes = True
        if variant == 'Sheet':
            self.sheets.append(new_sheet)
        elif variant == 'Function':
            # Function Sheets must have Inputs and Outputs nodes, exactly one of each. They are not deletable, and not listed in UI
            new_sheet.new_node(self.app_state.all_node_classes['Node_Function_Outputs'])
            new_sheet.new_node(self.app_state.all_node_classes['Node_Function_Inputs'])  # make inputs last, so it ends up on top
            self.function_sheets.append(new_sheet)

    def is_sheet_name_taken(self, desired_name: str) -> bool:
        """
        Check if another sheet already has given name
            names are purely config, and not required to be unique; this is just to create acceptable default name for the user
        """
        for sheet in self.sheets:
            sheet_name = sheet.config.get('name')
            if sheet_name == desired_name:
                return True
        for sheet in self.function_sheets:
            sheet_name = sheet.config.get('name')
            if sheet_name == desired_name:
                return True
        return False

    def find_sheet(self, sheet_id: Union[WorkspaceSheetId, int], variant: Literal['Sheet', 'Function'] = 'Sheet') -> WorkspaceSheet:
        """Finda nd return the sheet with given id, within the given variant"""
        if variant == 'Sheet':
            sheet_list = self.sheets
        elif variant == 'Function':
            sheet_list = self.function_sheets

        if isinstance(sheet_id, WorkspaceSheetId):
            sheet_id = sheet_id.id()

        for sheet in sheet_list:
            if sheet.id.id() == sheet_id:
                return sheet
        raise IndexError(f'Could not find sheet with id: {sheet_id}')

    def find_view_bookmark(self, view_num: int):
        """Find a view by index"""
        return self.view_bookmarks[view_num]

    def sheet_exists(self, sheet_id: WorkspaceSheetId) -> bool:
        """Check if a sheet exists"""
        for sheet in self.sheets:
            if sheet.id == sheet_id:
                return True
        for sheet in self.function_sheets:
            if sheet.id == sheet_id:
                return True
        return False

    def node_exists(self, node_id: NodeId) -> bool:
        """Check if node exists in any sheets"""
        for sheet in self.sheets:
            if sheet.node_exists(node_id):
                return True
        for sheet in self.function_sheets:
            if sheet.node_exists(node_id):
                return True
        return False

    def update_view_label(self, label: Any, index: int):
        """Update the label of a view"""
        self.view_bookmarks[index].label = label

    # Every frame

    def prompt_value(self, label: str, description: str, vartype: VarType, initial_value: Any, callback: Callable[[Any, Any]], data: Any = None, tweaks: InputWidgetTweaks = None):
        """Show a prompt to edit a single value, with a callback if value changed"""
        print('opening prompt')
        self._pending_single_parameter_param = ConfigParameter(label, description, 'value', vartype, default=initial_value, tweaks=tweaks)
        self._pending_single_parameter_callback = callback
        self._pending_single_parameter_callback_data = data
        self._pending_single_parameter_details = description

    def on_frame(self):
        """Tasks to perform each frame"""
        # NOTE here we handle checking the status of any potentially open dialogs, and handle follow-up tasks as needed

        # handle completion of open file dialog
        if imfd.is_done('OpenFileDialog'):
            imfd.close()
            if imfd.has_result():
                file_path = Path(str(imfd.get_result()))
                if not file_path.is_file():
                    raise WorkspaceException(f'Could not find selected file: {str(file_path)}')
                self._load_from_file(file_path)

        # handle completion of save file dialog
        if imfd.is_done('SaveAsDialog'):
            imfd.close()
            if imfd.has_result():
                file_path = Path(str(imfd.get_result()))
                ok_to_go = True
                if file_path.is_file():
                    self._pending_save_overwrite_path = file_path
                    self._pending_save_overwrite_details = f'A file named {file_path.name} already exists!\n\tAre you sure you want to overwrite the existing file?'
                    ok_to_go = False
                if file_path.is_dir():
                    raise WorkspaceException('File path exists, and is a folder! cannot save!')
                if ok_to_go:
                    self.set_file(file_path)
                    self.save()

        # handle overwrite confirmation dialog
        if self._pending_save_overwrite_path is not None:
            center = imgui.get_main_viewport().get_center()
            imgui.set_next_window_pos(center, imgui.Cond_.appearing.value, Vec2(0.5, 0.5))
            if not self._pending_save_overwrite_open:
                imgui.open_popup('ConfirmOverwrite')
                self._pending_save_overwrite_open = True
            modal_open, _thing = imgui.begin_popup_modal('ConfirmOverwrite', flags=imgui.WindowFlags_.always_auto_resize.value)
            if modal_open:
                imgui.text(self._pending_save_overwrite_details)
                imgui.separator()
                if Button('Overwrite'):
                    imgui.close_current_popup()
                    self._pending_save_overwrite_open = False
                    log.info(f'Overwriting existing file: {self._pending_save_overwrite_path}')
                    self.set_file(self._pending_save_overwrite_path)
                    self.save()
                    self._pending_save_overwrite_path = None
                    self._pending_save_overwrite_details = ''

                imgui.set_item_default_focus()
                imgui.same_line()
                if Button('Cancel'):
                    imgui.close_current_popup()
                    self._pending_save_overwrite_open = False
                    log.warning('Workspace save cancelled!')
                    self._pending_save_overwrite_path = None
                    self._pending_save_overwrite_details = ''
                imgui.end_popup()

        # handle single parameter input dialog
        if self._pending_single_parameter_param is not None:
            center = imgui.get_main_viewport().get_center()
            imgui.set_next_window_pos(center, imgui.Cond_.appearing.value, Vec2(0.5, 0.5))
            if not self._pending_single_parameter_open:
                imgui.open_popup('SingleParameterInput')
                self._pending_single_parameter_open = True
            modal_open, _thing = imgui.begin_popup_modal('SingleParameterInput', flags=imgui.WindowFlags_.always_auto_resize.value)
            if modal_open:
                imgui.text(self._pending_single_parameter_details)
                imgui.separator()
                changed, new_value = self._config_input_renderer.render_input(self._pending_single_parameter_param)
                if changed:
                    self._pending_single_parameter_param.default = new_value
                imgui.separator()
                if Button('Save'):
                    imgui.close_current_popup()
                    self._pending_single_parameter_open = False
                    self._pending_single_parameter_param = None
                    if self._pending_single_parameter_callback is not None:
                        self._pending_single_parameter_callback(new_value, self._pending_single_parameter_callback_data)
                    self._pending_single_parameter_callback = None
                    self._pending_single_parameter_details = ''
                    self._pending_single_parameter_callback_data = None

                imgui.set_item_default_focus()
                imgui.same_line()
                if Button('Cancel'):
                    imgui.close_current_popup()
                    self._pending_single_parameter_open = False
                    self._pending_single_parameter_param = None
                    self._pending_single_parameter_callback = None
                    self._pending_single_parameter_callback_data = None
                    self._pending_single_parameter_details = ''
                imgui.end_popup()

        # Do maintenance on bookmarks
        self.do_view_bookmark_maintenance()

    def do_view_bookmark_maintenance(self):
        """Check all view bookmarks and prune orphaned nodes/views/sheets"""

        # clean up any views which reference invalid sheets
        for idx, view in enumerate(copy(self.view_bookmarks)):
            if not self.sheet_exists(view.sheet_id):
                log.warning(f'Removing view: "{idx}. {view.label}" associated with sheet id: {view.sheet_id.id()}, which no longer exists!')
                self.view_bookmarks.pop(idx)

        # and remove any nodes from views which no longer exist
        for idx, view in enumerate(copy(self.view_bookmarks)):
            for node_id in view.selected_nodes:
                if not self.node_exists(node_id):
                    log.warning(f'Removing node_id: {node_id.id()} from view: "{idx}. {view.label}", because the node no longer exists!')
                    view.selected_nodes.remove(node_id)

            # (delete view with zero remaining nodes)
            if len(view.selected_nodes) == 0:
                log.warning(f'Removing view: "{idx}. {view.label}" because it has zero selected_nodes!')
                self.view_bookmarks.pop(idx)

    def get_sheet_select(self, selected: int = None, skip: list[int] = None, variant: Literal['Sheet', 'Function'] = 'Sheet') -> Select:
        """
        Create a Select object of all current sheets for given variant
        """
        # NOTE: sheet id is an unsupported value type for Select, so we resolve to int,
        #   and then we have to lookup the actual id again after selection is made
        sheet_opts: SelectOption = []
        unnamed_count = 0
        if variant == 'Sheet':
            sheet_list = self.sheets
        elif variant == 'Function':
            sheet_list = self.function_sheets

        for sheet in sheet_list:

            sheet_name = sheet.config.get('name')
            if sheet_name == '':
                sheet_name = f'Blank {unnamed_count}'
                unnamed_count += 1

            if skip is not None:
                if sheet.id.id() in skip:
                    continue

            sheet_opts.append(SelectOption(sheet.id.id(), f'{variant}: ' + sheet_name, ''))

        sel_obj = Select(sheet_opts, selected)
        return sel_obj
