"""
Althea - Sheet Editor

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

# reference:
#   https://github.com/pthom/imgui_bundle/blob/main/bindings/imgui_bundle/demos_python/demos_node_editor/demo_node_editor_basic.py

from __future__ import annotations

import tempfile

from uuid import uuid4
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from threading import Thread
from copy import copy

from ..common import log, imgui, ed, time_nano_pretty
from ..vartypes import Vec2, VarType, NormalizedColorRGBA

from ..nodes import create_node_registry
from ..nodes.base import WorkspaceSheet, Node, ViewBookmark
from ..nodes.primitives import NodeId, PinId, LinkId, WorkspaceSheetId, IOKind, PinKind, IOPin, NodeKind
from ..nodes.value import StaticValuesNode

from ..ui import global_ui_state, DISTINCT_COLORS, CursorPosition
from ..ui import estimate_text_size, estimate_icon_size, get_canvas_origin, get_view_center, draw_rectangle, draw_icon
from ..ui import FontSize, FontVariation, HorizontalGroup, VerticalGroup, Button, draw_text
from ..ui import InputWidget_Select, InputWidgetTweaks_Select, InputWidgetTweaks_Integer


from ..icons import MaterialIcons

from .base import Pane

if TYPE_CHECKING:
    from .. import state


class SheetEditorException(Exception):
    """Exception specific to Node Editor"""


class CircularDependencyException(SheetEditorException):
    """Exception specific to Node Circular Dependency"""


class NodeRenderer():
    """Renderer for nodes"""
    debug: bool = True
    """If True, show IDs for nodes and pins; this is intended to be used at by the Node baseclass only, and obviously only for debugging"""
    default_pin_color = NormalizedColorRGBA(1.0, 1.0, 1.0, 1.0)
    """Initial pin color, before specific color is applied (if there is one)"""
    header_height: int = 70
    footer_height: int = 25
    rect_rounding: int = 15
    node_color_alpha: float = 0.25

    def __init__(self, app_state: state.AppState) -> None:
        self.app_state = app_state
        """Local pointer to global app state"""
        self.node: Node = None
        """Pointer to the node currently being rendered"""
        self.node_colors = self.populate_node_colors(self.node_color_alpha)
        """Colors assigned to each node category"""
        self.debug = self.app_state.app_config.get('debug_node_rendering')
        self.icon_size: Vec2 = None

    # Utilities

    def populate_node_colors(self, alpha: float = 0.25) -> dict[str, NormalizedColorRGBA]:
        """Populate colors for each Node Category by cycling through a list of distinct colors"""
        # NOTE: this is not in global_ui_state like VarType colors, due to import loop that would be needed
        node_colors: dict[str, NormalizedColorRGBA] = {}
        node_registry = create_node_registry()
        counter = 0
        for node_cat in node_registry:
            dist_color = NormalizedColorRGBA.from_hexstr(DISTINCT_COLORS[counter])
            dist_color.a = alpha
            node_colors[node_cat] = dist_color
            counter += 1
            if counter >= len(DISTINCT_COLORS):
                counter = 0
        return node_colors

    def estimate_io_widths(self) -> tuple[int, int]:
        """Estimate the widest text string (in pixels) used in inputs and outputs, respectively"""

        iter_data = [
            {
                'pins': self.node.inputs,
                'longest': 0
            },
            {
                'pins': self.node.outputs,
                'longest': 0
            }
        ]

        for this_data in iter_data:
            this_pin: IOPin
            for this_pin in this_data['pins']:
                # label
                label_len = estimate_text_size(this_pin.label, FontSize.Normal, FontVariation.Regular).x
                if label_len > this_data['longest']:
                    this_data['longest'] = label_len

                # sublabel (vartype, potentially pin id)
                sublabel_text = this_pin.io_type.name
                if self.debug:
                    sublabel_text = f'({this_pin.pin_id.id()}) ' + sublabel_text
                sublabel_len = estimate_text_size(sublabel_text, FontSize.Small, FontVariation.Italic).x
                if sublabel_len > this_data['longest']:
                    this_data['longest'] = sublabel_len

                # value (in very specific circumstance)
                if this_pin.io_kind == IOKind.Output and isinstance(self.node, StaticValuesNode):
                    try:
                        val_string = str(this_pin.value)
                        this_len = estimate_text_size(val_string, FontSize.VeryLarge, FontVariation.Regular).x
                        if this_len > this_data['longest']:
                            this_data['longest'] = this_len
                    except Exception:
                        pass

        return (iter_data[0]['longest'], iter_data[1]['longest'])

    def place_center(self):
        """Place this node at the current center of node editor view, regardless of pan and zoom"""
        origin_canvas = get_canvas_origin()
        view_center = get_view_center()
        offset = Vec2(150, 100)  # NOTE this is to account for node height and width

        self.node.position = origin_canvas + view_center - offset
        self.place()

    def place(self):
        """Place this node at configured position"""
        ed.set_node_position(self.node.node_id, self.node.position)

    def do_housekeeping(self):
        """Do per-frame housekeeping tasks"""

        if self.node.first_frame:
            # on the first frame, we need to place the node in its intended location
            if self.node.position is None:
                self.place_center()
            else:
                self.place()
            self.node.first_frame = False
        else:
            # after the first frame, we keep track of the position
            self.node.position = Vec2.convert(ed.get_node_position(self.node.node_id))

        self.debug = self.app_state.app_config.get('debug_node_rendering')

        # figure out icon size
        if self.icon_size is None:
            self.icon_size = estimate_icon_size(MaterialIcons.radio_button_checked, FontSize.Huge)

        # assign node color
        if self.node.color is None:
            self.node.color = NormalizedColorRGBA(0, 0, 0, 0.0)  # dont apply any color if none found
            if self.node.node_category in self.node_colors:
                self.node.color = self.node_colors[self.node.node_category]

        # track current node dimensions
        self.node.dimensions = ed.get_node_size(self.node.node_id)

        # let node run its own per-frame tasks
        self.node.on_frame()

    # draw pieces of node

    def draw_header(self):
        """Draw the header / titlebar for this node"""

        with CursorPosition(pos=self.node.position):
            draw_rectangle(Vec2(self.node.dimensions.x, self.header_height), self.node.color, True, self.rect_rounding, flags=imgui.ImDrawFlags_.round_corners_top.value)

        if self.node.common_config.get('name') == '':
            title_text = f'{self.node.node_display}'
        else:
            title_text = f'{self.node.node_display}: {self.node.common_config.get("name")}'

        total_title_width = 0

        title_text = '    ' + title_text + '    '  # add some padding, otherwise title walkd
        title_width = draw_text(title_text, size=FontSize.Medium, variation=FontVariation.Bold, align='center', container_width=self.node.dimensions.x)
        total_title_width += title_width

        if self.node.has_changed() and self.node.node_kind != NodeKind.Display:
            with CursorPosition(pos=self.node.position + Vec2(5, 0)):
                draw_icon(MaterialIcons.change_circle, size=FontSize.Large)

        draw_text('    ' + self.node.node_desc + '    ', size=FontSize.Small, variation=FontVariation.Italic, align='center', container_width=self.node.dimensions.x)

    def draw_pin_connection(self, iopin: IOPin):
        """Draw the connection point for a pin"""
        pin_kind = PinKind.input
        if iopin.io_kind == IOKind.Output:
            pin_kind = PinKind.output

        ed.begin_pin(iopin.pin_id, pin_kind)
        color = self.default_pin_color
        if iopin.io_type in global_ui_state.vartype_colors:
            color = global_ui_state.vartype_colors[iopin.io_type]

        icon = MaterialIcons.radio_button_unchecked
        if iopin.linked:
            icon = MaterialIcons.radio_button_checked

        draw_icon(icon, color)

        ed.end_pin()

    def draw_offset_text(self, text: str, offset_x: int, size: FontSize, variation: FontVariation):
        """Draw text offset by text width to the left of given origin"""
        # imgui.text(' ')
        est_width = estimate_text_size(text, size, variation).x
        padding = 10  # space between pin and text
        with CursorPosition(x=offset_x - padding - est_width):
            draw_text(text, size, variation)
        # need this so that we occuply the correct amount of vertical space
        draw_text('', size, variation)

    def draw_a_pin(self, iopin: IOPin, widest_input: int, widest_output: int):
        """Draw an IO Pin, with label, VarType"""

        widest_input = max(widest_input, estimate_text_size('XXXXXX').x)
        widest_output = max(widest_output, estimate_text_size('XXXXXX').x)

        # NOTE here we estimate minimum node width based on the widest text from inputs and outputs,
        #   plus icon size, plus a 100px in between inputs and outputs
        #   if the current node width value is wider than the estimate,
        #       then that means middle() content (or title, or whatever) caused node to end up wider than just i/o pins and their labels
        #   it is important for node.dimensions to be updated at the TOP of the frame (in housekeeping) or node size will "shimmer" between two dimensions
        est_node_width = widest_input + 100 + widest_output + (2 * self.icon_size.x)
        if self.node.dimensions.x - est_node_width > 0:
            est_node_width = self.node.dimensions.x

        output_pin_origin = (self.node.position.x + est_node_width - 10) - (self.icon_size.x + 10)

        label_text = iopin.label
        sublabel_text = iopin.io_type.name
        if self.debug:
            if iopin.io_kind == IOKind.Input:
                sublabel_text = sublabel_text + f' ({iopin.pin_id.id()})'
            else:
                sublabel_text = f'({iopin.pin_id.id()}) ' + sublabel_text

        value_text = ''
        if iopin.io_kind == IOKind.Output and isinstance(self.node, StaticValuesNode):
            value_text = '(None)'
            if iopin.value is not None:
                value_text = str(iopin.value)

        # start drawing stuff
        if iopin.io_kind == IOKind.Input:
            self.draw_pin_connection(iopin)
            imgui.same_line()
        else:
            imgui.text(' ')
            imgui.same_line()

        with HorizontalGroup():
            if iopin.io_kind == IOKind.Output:
                self.draw_offset_text(label_text, output_pin_origin, FontSize.Normal, FontVariation.Regular)
                self.draw_offset_text(sublabel_text, output_pin_origin, FontSize.Tiny, FontVariation.Italic)

                if isinstance(self.node, StaticValuesNode):
                    # Display current values for outputs, for static value nodes
                    self.draw_offset_text(value_text, output_pin_origin, FontSize.VeryLarge, FontVariation.Regular)
            else:
                draw_text(label_text, FontSize.Normal, FontVariation.Regular)
                draw_text(sublabel_text, FontSize.Small, FontVariation.Italic)

        if iopin.io_kind == IOKind.Output:
            imgui.same_line()

            with CursorPosition(x=output_pin_origin):
                self.draw_pin_connection(iopin)

            imgui.same_line()
            imgui.text('')

    def draw_footer(self):
        """Draw the footer for this node"""
        footer_origin = self.node.position + Vec2(0, self.node.dimensions.y - self.footer_height)
        with CursorPosition(pos=footer_origin):
            draw_rectangle(Vec2(self.node.dimensions.x, self.footer_height), self.node.color, True, self.rect_rounding, flags=imgui.ImDrawFlags_.round_corners_bottom.value)

        footer_text = ''

        if self.node.calc_time is not None:
            # time is in nanoseconds
            time_pretty = 'Calc: ' + time_nano_pretty(self.node.calc_time)
            footer_text += time_pretty

        if self.debug:
            footer_text += f' Position: {int(self.node.position.x)},{int(self.node.position.y)} Size: {int(self.node.dimensions.x)}x{int(self.node.dimensions.y)}, NodeId: {self.node.node_id.id()}'
        imgui.text(footer_text)

    # render the whole node

    def render_node(self, node: Node):
        """Render the given node"""
        self.node = node
        self.do_housekeeping()

        # Draw the node
        ed.begin_node(self.node.node_id)
        with HorizontalGroup():
            # Header
            self.draw_header()

        # Inputs and Outputs
        imgui.text('')
        imgui.text('')
        with HorizontalGroup():
            widest_input, widest_output = self.estimate_io_widths()
            for io_list in [self.node.inputs, self.node.outputs]:
                with VerticalGroup():
                    if len(io_list) == 0:
                        imgui.text(' ')
                    else:
                        for this_io_pin in io_list:
                            self.draw_a_pin(this_io_pin, widest_input, widest_output)
                            imgui.text(' ')

        # Middle content
        imgui.text(' ')
        with HorizontalGroup():
            with VerticalGroup():
                imgui.text('')
            with VerticalGroup():
                try:
                    self.node.draw_middle()
                except Exception as ex:
                    imgui.text('Failed to render content')
                    imgui.text('Invalid data or config')
                    imgui.text(f'Error: {str(ex)}')
            with VerticalGroup():
                imgui.text('')

        imgui.text('')
        with HorizontalGroup():
            # Footer
            self.draw_footer()

        ed.end_node()
        self.node = None


class SheetEditorContext:
    """Running vars for sheet editor"""
    selected_nodes: list[NodeId] = []
    """List of currently selected NodeIDs"""
    selected_links: list[LinkId] = []
    """List of currently selected LinkIDs"""

    def remove_link(self, link_id: LinkId):
        """Remove given link from context if selected"""
        for link_id_act in self.selected_links:
            if link_id_act == link_id:
                self.selected_links.remove(link_id_act)

    def remove_node(self, node_id: NodeId):
        """Remove given node from context if selected"""
        for node_id_act in self.selected_nodes:
            if node_id_act == node_id:
                self.selected_nodes.remove(node_id_act)


class SheetEditorPane(Pane):
    """Editor for a sheets of nodes"""

    def __init__(self, app_state: state.AppState, variant: Literal['Sheet', 'Function'] = 'Sheet'):
        super().__init__(app_state)
        self._uuid = str(uuid4())
        self.variant = variant
        """Sheet variant; the Sheet object is used to implement several very similar objects, like Functions; variant determines how this object will behave"""
        self.sheet: WorkspaceSheet = None
        """Pointer to the currently selected sheet; if no sheet selected (like if there are zero sheets) this will be None"""
        self.context = SheetEditorContext()
        """Editor context, holds information about currently selected objects"""
        self.node_renderer = NodeRenderer(self.app_state)
        """Node Renderer - handles all node drawing"""
        self.editor_context: ed.EditorContext = None
        """imgui node editor context"""
        self.editor_config: ed.Config = None
        """imgui node editor config"""
        self.temp_settings_file = Path(tempfile.gettempdir()).joinpath(f'{self._uuid}_NodeEditor.json')
        """Temporary config file for node editor because we wont be using it, but want to clean it up on shutdown"""
        self._zoom: float = 1.0
        """(internal) current editor view zoom"""
        self._dimensions: Vec2 = Vec2(0, 0)
        """(internal) current editor view dimensions"""
        self._canvas_origin: Vec2 = Vec2(0, 0)
        """(internal) current editor canvas origin (top left corner)"""
        self._window_origin: Vec2 = Vec2(0, 0)
        """(internal) current window origin, on which the canvas resides"""
        self._request_view: ViewBookmark = None
        """(internal) requested view, which will be handled at top of next frame; value stays until animation is complete, then set to None"""
        self._view_animating: bool = False
        """(internal) flag indicating if we are currently animating to a requested view"""
        self._request_view_all: bool = True
        """(internal) flag indicating that we would like to zoom out to view all nodes, on the next frame"""
        self._request_view_selected: bool = True
        """(internal) flag indicating that we would like to zoom out to view currently selected nodes, on the next frame"""
        self._request_view_bookmark: ViewBookmark = None
        """(internal) view bookmark to apply, on the next frame"""
        self._view_animation_time: float = 1.0
        """(internal) seconds, animate between views over this time"""
        self._request_new_view_bookmark: bool = False
        """(internal) flag indicating we want to capture a view bookmark on next frame"""

    def setup(self):
        self.editor_config = ed.Config()
        self.editor_config.settings_file = str(self.temp_settings_file)
        self.editor_context = ed.create_editor(self.editor_config)

    def cleanup(self):
        log.debug('Cleaning up temporary files')
        if self.temp_settings_file.is_file():
            self.temp_settings_file.unlink()

    def clear(self):
        """Clear this sheet editor"""
        self.context = SheetEditorContext()
        self.sheet = None
        self._request_view_all = True

    def get_sheets(self) -> list[WorkspaceSheet]:
        """Get the list of all sheets, within this editor's variant"""
        if self.variant == 'Sheet':
            return self.app_state.workspace.sheets
        if self.variant == 'Function':
            return self.app_state.workspace.function_sheets
        raise SheetEditorException(f'Failed to get sheets for variant: {self.variant}')

    def set_sheet(self, sheet_id: WorkspaceSheetId):
        """Set the sheet to edit with this Sheet Editor"""
        self.context = SheetEditorContext()
        self.sheet = self.app_state.workspace.find_sheet(sheet_id, variant=self.variant)

    def select_first_sheet(self):
        """Set the sheet to the first sheet"""
        sheets = self.get_sheets()
        if len(sheets) > 0:
            self.set_sheet(sheets[0].id)

    # User Actions

    def recalc_all(self):
        """Re-Calculate all nodes"""
        workthread = Thread(target=self.sheet.recalc_all, args=(), daemon=True)
        workthread.start()

    def recalc_changed(self):
        """Re-Calculate all nodes with changes (or dependent on those with changes)"""
        workthread = Thread(target=self.sheet.recalc_changed, args=(), daemon=True)
        workthread.start()

    def new_view_bookmark(self):
        """Create a new view bookmark, from this editor's current view"""
        # we have to queue a request for next frame,
        #   because we must read current view details at specific point in the frame loop
        self._request_new_view_bookmark = True

    def request_view(self, view: ViewBookmark):
        """Request a view bookmark be applied on next frame"""
        log.debug(f'Requesting view: {view.label}')
        self._request_view_bookmark = view

    # Rendering loop (called every frame)

    def do_housekeeping(self):
        """perform housekeeping tasks at top of frame"""
        if imgui.is_window_focused() and self.app_state.get_focused_editor() != self.variant:
            print(f'New window focus: {self.variant}')
            self.app_state.set_focused_editor(self.variant)
        self._view_animation_time = self.app_state.app_config.get('view_animation_time')

    def draw_toolbar(self):
        """Draw the toolbar with buttons at the top of the sheet editor"""
        with HorizontalGroup():

            # if Button('Re-Calculate All'):
            #     self.recalc_all()

            # imgui.same_line()
            # if Button('Re-Calculate Changed'):
            #     self.recalc_changed()

            # imgui.same_line()
            if Button(f'New {self.variant}'):
                self.app_state.workspace.new_sheet(variant=self.variant)

            imgui.same_line()
            if Button('New View Bookmark'):
                self.new_view_bookmark()

            imgui.same_line()
            if Button('View Selected'):
                self._request_view_selected = True

            imgui.same_line()
            if Button('View All Nodes'):
                self._request_view_all = True

            imgui.same_line()
            if len(self.get_sheets()) > 0:
                current_selection = None
                if self.sheet is not None:
                    current_selection = self.sheet.id.id()
                sel_obj = self.app_state.workspace.get_sheet_select(selected=current_selection, variant=self.variant)
                changed, new_sel_obj = InputWidget_Select(sel_obj, '', f'Select a {self.variant}',
                                                          tweaks=InputWidgetTweaks_Select(
                                                              item_type=VarType.Integer,
                                                              tweaks=InputWidgetTweaks_Integer())
                                                          ).on_frame()

                if changed:
                    if new_sel_obj.selected is not None:
                        sheet = self.app_state.workspace.find_sheet(new_sel_obj.selected, variant=self.variant)
                        self.set_sheet(sheet.id)
            else:
                imgui.text(f'No {self.variant}s')

            imgui.same_line()
            imgui.text(' ')

    def update_context(self):
        """update context"""
        self.context.selected_nodes = []
        for node in self.sheet.nodes:
            if ed.is_node_selected(node.node_id):
                self.context.selected_nodes.append(node.node_id)
            if not self.app_state.unsaved_changes:
                if node.config.has_changes():
                    self.app_state.unsaved_changes = True
        self.context.selected_links = []
        for lnk in self.sheet.links:
            if ed.is_link_selected(lnk.id):
                self.context.selected_links.append(lnk.id)

    def update_view_details(self):
        """Update view details like zoom, canvas origin, etc"""
        self._zoom = ed.get_current_zoom()
        self._canvas_origin = Vec2.convert(ed.screen_to_canvas(imgui.get_window_content_region_min()))
        self._dimensions = Vec2.convert(ed.get_screen_size())
        self._window_origin = Vec2(imgui.get_window_content_region_min())

    def draw_view_details(self):
        """Draw view details like zoom, canvas origin, etc"""
        try:
            with CursorPosition(y=30 + self._window_origin.y):
                # with HorizontalGroup():
                draw_text(f'Zoom: {round(self._zoom, 2)}', size=FontSize.Tiny)
                draw_text(f'Dimensions: {round(self._dimensions.x, 2)} x {round(self._dimensions.y, 2)}', size=FontSize.Tiny)
                draw_text(f'Origin: {round(self._canvas_origin.x, 2)}, {round(self._canvas_origin.y, 2)}', size=FontSize.Tiny)
        except Exception:
            pass

    def commit_known_data(self):
        """Commit known data to editor"""
        for this_node in self.sheet.nodes:
            # check and reconfigure I/O if needed
            if this_node.configurable_inputs or this_node.reconfigure_io_anyway:
                if this_node.last_cfg_inputs != this_node.common_config.get('input_iopininfos'):
                    this_node.configure_io(io_kind=IOKind.Input)

            if this_node.configurable_outputs or this_node.reconfigure_io_anyway:
                if this_node.last_cfg_outputs != this_node.common_config.get('output_iopininfos'):
                    this_node.configure_io(io_kind=IOKind.Output)

            # check and mark changed if needed
            if this_node.config.has_changes() and not this_node.has_changed():
                this_node.mark_changed()

            # forward need for change propagation to app_state
            if this_node.need_propagate:
                this_node.need_propagate = False
                self.app_state.need_change_propagate = True

            # finally, render the node
            self.node_renderer.render_node(this_node)

        # mark dependent nodes as changed too
        if self.app_state.need_change_propagate:
            self.app_state.need_change_propagate = False
            self.sheet.propagate_changed()

        # clear linked state for all iopins, then check them again
        for node in self.sheet.nodes:
            for ipin in node.inputs:
                ipin.linked = False
            for opin in node.outputs:
                opin.linked = False

        # Submit Links, pruning any orphaned ones
        list_of_links = copy(self.sheet.links)
        for link_info in list_of_links:
            try:
                _in_pin = self.sheet.find_iopin(link_info.input_id)
            except ValueError:
                log.warning(f'Cleaning up orphaned link: {link_info.id.id()}; input pin {link_info.input_id.id()} no longer exists!')
                self.sheet.delete_link(link_info.id)
                continue
            try:
                _out_pin = self.sheet.find_iopin(link_info.output_id)
            except ValueError:
                log.warning(f'Cleaning up orphaned link: {link_info.id.id()}; output pin {link_info.output_id.id()} no longer exists!')
                self.sheet.delete_link(link_info.id)
                continue
            ed.link(link_info.id, link_info.input_id, link_info.output_id, link_info.color.to_imcolor())
            _in_pin.linked = True
            _out_pin.linked = True

        # Set selected node, if needed (like if we just added a new node)
        if self.sheet.next_selected is not None:
            ed.select_node(self.sheet.next_selected)
            self.sheet.next_selected = None

    def handle_interactions(self):
        """Handle interactions, such as creating a new node or link"""

        # Handle creation action, returns true if editor wants to create new object (node or link)
        if ed.begin_create():

            from_pinid = PinId()
            to_pinid = PinId()

            if ed.query_new_link(from_pinid, to_pinid):
                # QueryNewLink returns true if editor want to create new link between pins.
                #
                # Link can be created only for two valid pins, it is up to you to
                # validate if connection make sense. Editor is happy to make any.
                if from_pinid and to_pinid:  # both are valid, let's evaluate a link
                    self.sheet.attempt_link(from_pinid, to_pinid, self.app_state)

            ed.end_create()  # Wraps up object creation action handling.

        # Handle deletion action
        if ed.begin_delete():

            # There may be many links marked for deletion, let's loop over them.
            deleted_link_id = LinkId()
            while ed.query_deleted_link(deleted_link_id):
                if self.sheet.ok_to_delete_link(deleted_link_id):
                    # If you agree that link can be deleted, accept deletion.
                    if ed.accept_deleted_item():
                        self.context.remove_link(deleted_link_id)
                        self.sheet.delete_link(deleted_link_id)
                else:
                    # You may reject link deletion by calling:
                    ed.reject_deleted_item()

            # There may be nodes marked for deleteion, lets loop over them
            deleted_node_id = NodeId()
            while ed.query_deleted_node(deleted_node_id):
                if self.sheet.ok_to_delete_node(deleted_node_id):
                    # If you agree that node can be deleted, accept deletion.
                    if ed.accept_deleted_item():
                        self.context.remove_node(deleted_node_id)
                        self.sheet.delete_node(deleted_node_id)
                else:
                    # You may reject node deletion by calling:
                    ed.reject_deleted_item()

            ed.end_delete()  # Wrap up deletion action

    def handle_requested_new_view_bookmark(self):
        """handle request for new view bookkmark"""
        if self._request_new_view_bookmark:
            new_bk = ViewBookmark(self.variant, self.sheet.id, self.context.selected_nodes, label='New View Bookmark')
            self.app_state.workspace.view_bookmarks.append(new_bk)
            self._request_new_view_bookmark = False

    def handle_requested_view(self):
        """Handle any pending view requests"""
        if self._request_view_bookmark is not None:
            # We have a requested view bookmark, lets handle that

            # Override any other pending view request
            #   TODO this allows us to set a default view when loading from a file, instead of defaulting to view_all
            self._request_view_all = False
            self._request_view_selected = False

            restore_selection = False
            previous_selection = []

            if self._request_view_bookmark.sheet_id != self.sheet.id:
                self.set_sheet(self._request_view_bookmark.sheet_id)
            else:
                # save currently selected nodes
                previous_selection = copy(self.context.selected_nodes)
                restore_selection = True

            # select nodes from bookmark
            ed.clear_selection()
            for sel_node in self._request_view_bookmark.selected_nodes:
                ed.select_node(sel_node, append=True)

            # navigate to selection
            ed.navigate_to_selection(True, self._view_animation_time)

            ed.clear_selection()
            if restore_selection:
                # restore previously selected nodes
                for sel_node in previous_selection:
                    ed.select_node(sel_node, append=True)
                # profit
                self._request_view_bookmark = None

        else:
            # No requested view bookmark, lets see if we have requests to view all or selected
            if self._request_view_all:
                ed.navigate_to_content(self._view_animation_time)
                self._request_view_all = False

            if self._request_view_selected:
                ed.navigate_to_selection(True, self._view_animation_time)
                self._request_view_selected = False

    def on_frame(self):
        """Tasks to do each frame"""
        self.do_housekeeping()

        self.draw_toolbar()
        self.draw_view_details()

        if self.sheet is None:
            return

        ed.set_current_editor(self.editor_context)
        self.update_context()
        ed.begin(f'NodeEditor_{self._uuid}', Vec2(0.0, 0.0))
        self.update_view_details()

        self.commit_known_data()
        self.handle_interactions()

        # End of interaction with editor.
        ed.end()

        self.handle_requested_new_view_bookmark()
        self.handle_requested_view()

        ed.set_current_editor(None)

        # do sheet's on_frame housekeeping tasks
        self.sheet.on_frame()
