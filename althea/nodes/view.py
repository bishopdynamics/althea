"""
Althea - Node implementations, Viewing data

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy

from ..common import imgui, implot, imgui_md
from ..vartypes import VarType, Table, Vec2, Select, SelectOption
from ..ui import HorizontalGroup, FontSize, FontVariation, global_ui_state, display_table, draw_text
from ..ui import InputWidgetTweaks_Integer, InputWidgetTweaks_Bool, InputWidgetTweaks_String, InputWidgetTweaks_Float, InputWidgetTweaks_Select
from ..config import ConfigGroup, ConfigSection, ConfigParameter, Config

from .primitives import IOPin, IOKind, NodeKind
from .base import Node
from .config import NodeConfig, CommonNodeConfig


if TYPE_CHECKING:
    from .. import state
    from ..common import IdProviders


class Node_View(Node):
    """A node used to visualize the output of other nodes"""
    node_kind = NodeKind.Display
    node_display = 'View'
    node_desc = 'View Value'
    node_category = 'View'
    node_subcategory = 'General'
    inputs = [
        IOPin('Value', 'Value input', VarType.Any, IOKind.Input),
    ]
    outputs = []

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ViewNode Config', 'Configuration for ViewNode', [
                ConfigGroup('General', 'General configuration', [
                ]),
                ConfigGroup('Table Rendering', 'Viewing Table data', [
                    ConfigParameter('Column Width', 'Width per-column', 'column_width', VarType.Integer, 80, tweaks=InputWidgetTweaks_Integer(min=0, format='%d Pixels')),
                    ConfigParameter('Limit Columns', 'Limit the number of columns displayed in preview', 'limit_cols', VarType.Integer, 6, tweaks=InputWidgetTweaks_Integer(min=1, format='%d Columns')),
                    ConfigParameter('Limit Rows', 'Limit the number of rows displayed in preview', 'limit_rows', VarType.Integer, 8, tweaks=InputWidgetTweaks_Integer(min=1, format='%d Rows')),
                ]),
            ]),
        ]
    config = nodeConfig()

    def draw_middle(self):
        """Draw the center content, if there is any"""
        current_value = self.inputs[0].value
        if isinstance(current_value, Table):
            table_size = current_value.get_size()
            num_cols = self.config.get('limit_cols')
            if table_size.y < num_cols:
                num_cols = table_size.y
            total_width = self.config.get('column_width') * num_cols
            display_table(current_value, limit_rows=self.config.get('limit_rows'), limit_cols=self.config.get('limit_cols'), width=total_width, height=0)
        else:
            imgui.push_font(global_ui_state.fonts.get(FontSize.VeryLarge, FontVariation.Regular))
            imgui.text(str(current_value))
            imgui.pop_font()

    @staticmethod
    def execute(_inputs: list, _config: NodeConfig, common_config: CommonNodeConfig) -> list:
        return []


def node_comment_on_change(key: str, val: Any, config: Config):
    """Handle value change for config values in Node_Table_SelectRegion """
    if key == 'use_markdown':
        if val:
            config.hide(['comment_size', 'comment_variation'])
        else:
            config.unhide(['comment_size', 'comment_variation'])


class Node_Comment(Node):
    """A node used to view comment text"""
    node_kind = NodeKind.Display
    node_display = 'Comment'
    node_desc = ''
    node_category = 'View'
    node_subcategory = 'General'
    inputs = []
    outputs = []

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ViewNode Config', 'Configuration for ViewNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Use Markdown?', 'Use Markdown formatting for this comment?', 'use_markdown', VarType.Bool, tweaks=InputWidgetTweaks_Bool(), on_change=node_comment_on_change, comment='## Add a Comment\n You can style your comment \nusing generic size and style options, \nor you can use Markdown format'),
                    ConfigParameter('Text Size', 'Choose a size to display text',
                                    'comment_size', VarType.Select,
                                    Select([SelectOption(fs.name, fs.name, fs.name) for fs in FontSize], FontSize.Small.name),
                                    tweaks=InputWidgetTweaks_Select(
                                        item_type=VarType.String,
                                        tweaks=InputWidgetTweaks_String()
                                    )),
                    ConfigParameter('Text Style', 'Choose a style to display text',
                                    'comment_variation', VarType.Select,
                                    Select([SelectOption(fs.name, fs.name, fs.name) for fs in FontVariation], FontVariation.Italic.name),
                                    tweaks=InputWidgetTweaks_Select(
                                        item_type=VarType.String,
                                        tweaks=InputWidgetTweaks_String()
                                    )),
                    ConfigParameter('Comment', 'Comment to show on node', 'comment_text', VarType.String, tweaks=InputWidgetTweaks_String(code_editor=True)),
                ]),
            ]),
        ]
    config = nodeConfig()

    def draw_middle(self):
        """Draw the center content, if there is any"""
        # TODO: headers starting with # create horizontal line that goes outside node
        comment_text: str = self.config.get('comment_text')
        use_markdown: bool = self.config.get('use_markdown')
        if use_markdown:
            imgui_md.render(comment_text)
            imgui.text('')

        else:
            comment_size: str = self.config.get('comment_size').selected
            comment_variation: str = self.config.get('comment_variation').selected
            c_size = FontSize.Small
            c_variation = FontVariation.Italic
            for fz in FontSize:
                if fz.name == comment_size:
                    c_size = fz
                    break
            for fv in FontVariation:
                if fv.name == comment_variation:
                    c_variation = fv
                    break

            draw_text(comment_text, c_size, c_variation)

    @staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        return []


def node_viewplot_on_change(key: str, val: Any, config: Config):
    """Handle value change for config values in Node_ViewPlot """
    if key == 'data_as_rows':
        as_cols_keys = ['as_cols_x_row', 'as_cols_x_col_start', 'as_cols_x_col_end', 'as_cols_y_row', 'as_cols_y_col_start', 'as_cols_y_col_end']
        as_rows_keys = ['as_rows_x_col', 'as_rows_x_row_start', 'as_rows_x_row_end', 'as_rows_y_col', 'as_rows_y_row_start', 'as_rows_y_row_end']
        if val:
            config.hide(as_cols_keys)
            config.unhide(as_rows_keys)
        else:
            config.unhide(as_cols_keys)
            config.hide(as_rows_keys)
    if key == 'auto_axis_limits':
        affected_keys = ['x_axis_min', 'x_axis_max', 'y_axis_min', 'y_axis_max']
        if val:
            config.hide(affected_keys)
        else:
            config.unhide(affected_keys)


class Node_ViewPlot(Node):
    """A plot values from a table"""
    node_kind = NodeKind.Display
    node_display = 'Plot'
    node_desc = 'Plot values from a table'
    node_category = 'View'
    node_subcategory = 'Visualize'
    inputs = [
        IOPin('Data', 'Data input as a table', VarType.Table, IOKind.Input),
    ]
    outputs = []

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ViewNode Config', 'Configuration for ViewNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Data as ', 'Rows: each series is a single column, one value per row.\nColumns: each series is a single row, one column per value',
                                    'data_as_rows', VarType.Bool, True, tweaks=InputWidgetTweaks_Bool(button=Table, button_true='Rows', button_false='Columns'), on_change=node_viewplot_on_change),
                    ConfigParameter('Series X: Label', 'Label for X Axis', 'label_x', VarType.String, 'X Axis', tweaks=InputWidgetTweaks_String()),
                    ConfigParameter('Series Y: Label', 'Label for Y Axis', 'label_y', VarType.String, 'Y Axis', tweaks=InputWidgetTweaks_String()),
                    ConfigParameter('Swap Axis', 'Swap X and Y Axis data (and labels)', 'swap_axis', VarType.Bool, False, tweaks=InputWidgetTweaks_Bool()),

                    # as rows
                    ConfigParameter('Series X: Column', 'Column containing data for X axis', 'as_rows_x_col', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Column %d'), comment='# As Rows\n## X Axis:'),
                    ConfigParameter('Series X: First Row', 'Row within column, for X axis data to start', 'as_rows_x_row_start', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Row %d')),
                    ConfigParameter('Series X: Last Row', 'Row within column, for X axis data to end (inclusive)', 'as_rows_x_row_end', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Row %d')),
                    ConfigParameter('Series Y: Column', 'Column containing data for Y axis', 'as_rows_y_col', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Column %d'), comment='## Y Axis:'),
                    ConfigParameter('Series Y: First Row', 'Row within column, for Y axis data to start', 'as_rows_y_row_start', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Row %d')),
                    ConfigParameter('Series Y: Last Row', 'Row within column, for Y axis data to end (inclusive)', 'as_rows_y_row_end', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Row %d')),
                    # as columns
                    ConfigParameter('Series X: Row', 'Row containing data for X axis', 'as_cols_x_row', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Row %d'), comment='# As Columns\n## X Axis:'),
                    ConfigParameter('Series X: First Column', 'Column within row, for X axis data to start', 'as_cols_x_col_start', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Column %d')),
                    ConfigParameter('Series X: Last Column', 'Column within row, for X axis data to end (inclusive)', 'as_cols_x_col_end', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Column %d')),
                    ConfigParameter('Series Y: Row', 'Row containing data for Y axis', 'as_cols_y_row', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Row %d'), comment='## Y Axis:'),
                    ConfigParameter('Series Y: First Column', 'Column within row, for Y axis data to start', 'as_cols_y_col_start', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Column %d')),
                    ConfigParameter('Series Y: Last Column', 'Column within row, for Y axis data to end (inclusive)', 'as_cols_y_col_end', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(min=0, format='Column %d')),
                ]),
                ConfigGroup('Plot Rendering', '', [
                    ConfigParameter('Axis Limits', 'Set limits, or let them be calculated automatically from data', 'auto_axis_limits', VarType.Bool, True, tweaks=InputWidgetTweaks_Bool(button=True, button_true='Auto', button_false='Manual'), on_change=node_viewplot_on_change),
                    # axis limits
                    ConfigParameter('X Axis Min', 'Minimum value for X axis', 'x_axis_min', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(), comment='## X Axis Limits'),
                    ConfigParameter('X Axis Max', 'Maximum value for X axis', 'x_axis_max', VarType.Integer, 50, tweaks=InputWidgetTweaks_Integer()),
                    ConfigParameter('Y Axis Min', 'Minimum value for Y axis', 'y_axis_min', VarType.Integer, 0, tweaks=InputWidgetTweaks_Integer(), comment='## Y Axis Limits'),
                    ConfigParameter('Y Axis Max', 'Maximum value for Y axis', 'y_axis_max', VarType.Integer, 50, tweaks=InputWidgetTweaks_Integer()),
                    # plot size
                    ConfigParameter('Plot Size', 'Size of plot, width, height', 'plot_size', VarType.Vec2, Vec2(400, 200), tweaks=InputWidgetTweaks_Float(enforce_range=True, min=0, round=True, round_digits=0, format='%.0f px')),
                ]),
            ]),
        ]
    config = nodeConfig()

    def __init__(self, id_: int, id_providers: IdProviders, app_state: state.AppState, position: Vec2 = None, init_pin_ids: bool = True) -> None:
        super().__init__(id_, id_providers, app_state, position, init_pin_ids)
        self.implot_context = implot.create_context()
        self._needs_new_context = False
        self.show_values = False

    def mark_changed(self):
        super().mark_changed()
        # we will need to re-create context on the next frame, or config changes affecting plot rendering will not take effect
        self._needs_new_context = True

    def craft_plot_flags(self) -> int:
        """craft implot flags, for overall plot drawing"""
        flags = 0
        # flags |= implot.Flags_.crosshairs.value
        return flags

    def craft_axis_flags(self) -> tuple[int, int]:
        """Create column flags"""
        x_flags = 0
        y_flags = 0
        # x_flags |= implot.AxisFlags_.no_grid_lines.value
        return x_flags, y_flags

    def craft_line_flags(self) -> int:
        """craft flags for drawing line"""
        flags = 0
        return flags

    def draw_middle(self):
        """Draw the center content, the plot"""

        input_table: Table = self.inputs[0].value
        if input_table is not None:
            if isinstance(input_table, Table):
                # if needed, destroy and re-create implot context
                if self._needs_new_context:
                    implot.destroy_context(self.implot_context)
                    self.implot_context = implot.create_context()
                    self._needs_new_context = False
                implot.set_current_context(self.implot_context)
                label_x: str = self.config.get('label_x')
                label_y: str = self.config.get('label_y')
                x_values = []
                y_values = []
                last_row = len(input_table.df.index) - 1
                last_col = len(input_table.df.columns) - 1
                if self.config.get('data_as_rows'):
                    # each series is a single column, one value per row
                    x_col: int = self.config.get('as_rows_x_col')
                    y_col: int = self.config.get('as_rows_y_col')

                    x_start: int = self.config.get('as_rows_x_row_start')
                    x_end: int = self.config.get('as_rows_x_row_end') + 1
                    y_start: int = self.config.get('as_rows_y_row_start')
                    y_end: int = self.config.get('as_rows_y_row_end') + 1

                    # Try to reduce out-of-bounds errors
                    x_start = max(x_start, 0)
                    x_end = min(x_end, last_row)
                    y_start = max(y_start, 0)
                    y_end = min(y_end, last_row)

                    x_rows: int = range(x_start, x_end)
                    y_rows: int = range(y_start, y_end)
                    for row in x_rows:
                        value = input_table.df.iat[row, x_col]
                        x_values.append(float(value))
                    for row in y_rows:
                        value = input_table.df.iat[row, y_col]
                        y_values.append(float(value))

                else:
                    # each series is a single row, one column per value
                    x_row: int = self.config.get('as_cols_x_row')
                    y_row: int = self.config.get('as_cols_y_row')

                    x_start: int = self.config.get('as_cols_x_col_start')
                    x_end: int = self.config.get('as_cols_x_col_end') + 1
                    y_start: int = self.config.get('as_cols_y_col_start')
                    y_end: int = self.config.get('as_cols_y_col_end') + 1

                    # Try to reduce out-of-bounds errors
                    x_start = max(x_start, 0)
                    x_end = min(x_end, last_col)
                    y_start = max(y_start, 0)
                    y_end = min(y_end, last_col)

                    x_cols: int = range(x_start, x_end)
                    y_cols: int = range(y_start, y_end)
                    for col in x_cols:
                        value = input_table.df.iat[x_row, col]
                        x_values.append(float(value))
                    for col in y_cols:
                        value = input_table.df.iat[y_row, col]
                        y_values.append(float(value))

                x_np_data = numpy.array(x_values)
                y_np_data = numpy.array(y_values)
                flags_x, flags_y = self.craft_axis_flags()
                flags_line = self.craft_line_flags()
                flags_plot = self.craft_plot_flags()

                # figure out axis limits
                if self.config.get('auto_axis_limits'):
                    x_min = min(x_values)
                    x_max = max(x_values)
                    y_min = min(y_values)
                    y_max = max(y_values)
                else:
                    x_min = self.config.get('x_axis_min')
                    x_max = self.config.get('x_axis_max')
                    y_min = self.config.get('y_axis_min')
                    y_max = self.config.get('y_axis_max')

                with HorizontalGroup():
                    # implot.set_current_context(self.implot_context)
                    if implot.begin_plot('Plot', self.config.get('plot_size'), flags=flags_plot):
                        if self.config.get('swap_axis'):
                            implot.setup_axes(label_y, label_x, flags_y, flags_x)
                            implot.setup_axes_limits(y_min, y_max, x_min, x_max)
                            implot.plot_line('Plot', y_np_data, x_np_data, flags=flags_line)
                        else:
                            implot.setup_axes(label_x, label_y, flags_x, flags_y)
                            implot.setup_axes_limits(x_min, x_max, y_min, y_max)
                            implot.plot_line('Plot', x_np_data, y_np_data, flags=flags_line)
                        implot.end_plot()

                if self.show_values:
                    if len(x_values) > 10:
                        imgui.text(f'X values: {x_values[:10]}...')
                    else:
                        imgui.text(f'X values: {x_values}')
                    if len(y_values) > 10:
                        imgui.text(f'Y values: {y_values[:10]}...')
                    else:
                        imgui.text(f'Y values: {y_values}')

    @staticmethod
    def execute(_inputs: list, _config: NodeConfig, common_config: CommonNodeConfig) -> list:
        return []
