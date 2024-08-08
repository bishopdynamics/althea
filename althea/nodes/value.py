"""
Althea - Node implementations, Values

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import json

from abc import abstractmethod
from typing import TYPE_CHECKING, Any
from pathlib import Path

from ..common import imgui, load_file_to_dataframes
from ..vartypes import VarType, Table, Select, SelectOption, IOPinInfo
from ..ui import FontSize, FontVariation, draw_text
from ..config import ConfigParameter, ConfigGroup, ConfigSection, Config

from .primitives import IOPin, IOKind, NodeKind
from .base import Node, NodeException
from .config import NodeConfig, CommonNodeConfig

from ..ui import display_table, InputWidgetTweaks_Integer, InputWidgetTweaks_Select, collect_input_widgets

if TYPE_CHECKING:
    from .. import state


class ValueNode(Node):
    """A static value node"""
    node_kind = NodeKind.Static
    node_category = 'Value'
    node_subcategory = 'General'
    inputs = []

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ValueNode Config', 'Configuration for ValueNode', [
                ConfigGroup('General', 'General configuration', []),
            ]),
        ]
    config = nodeConfig()

    def draw_middle(self):
        """Draw the center content, if there is any"""
        draw_text(str(self.config.get('value')), FontSize.VeryLarge, FontVariation.Regular)

    @abstractmethod
    def refresh(self) -> list:
        """Refresh the static value"""
        return []

    @staticmethod
    def execute(_inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        """Return static value from config
            Not applicable for NodeKind.Static
        """
        return []


class StaticValuesNode(ValueNode):
    """A node with configurable outputs, and the ability to set values for those outputs"""
    node_display = 'Static Values'
    node_desc = ''
    outputs = []
    configurable_inputs = False
    configurable_outputs = True
    special_common_config = True  # enable common config with user-editable static output values
    _all_widgets, _all_widget_tweaks = collect_input_widgets()

    def draw_middle(self):
        # override ValueNode's draw_middle
        pass

    def refresh(self) -> list:
        """Refresh values
        """
        outputs_cfg: list[IOPinInfo] = self.common_config.get('output_iopininfos')
        outputs: list = []
        for pin in outputs_cfg:
            outputs.append(pin.static_value)
        return outputs

    def on_frame(self):
        # static nodes get checked for changes every frame
        if self.has_changed():
            outputs = self.refresh()

            for odx, val in enumerate(outputs):
                self.outputs[odx].value = val

            self.mark_unchanged()


def node_value_table_on_change(key: str, val: Any, config: Config):
    """Handle value change for config values in Node_Value_Table """
    if key == 'load_from_file':
        # print(json.dumps(config.to_dict()))
        if val:
            config.hide('value')
            config.unhide(['file_path', 'sub_item'])
        else:
            config.unhide('value')
            config.hide(['file_path', 'sub_item'])
    if key == 'file_path':
        file_path: Path = config.get('file_path')
        if file_path.is_file():
            try:
                dataframes = load_file_to_dataframes(file_path)
                subitem_names = [key for key, _val in dataframes.items()]
                existing_value: Select = config.get('sub_item')
                opts = []
                for name in subitem_names:
                    opts.append(SelectOption(name, name.capitalize(), f'Sub-item: {name}'))
                config.set('sub_item', Select(opts, existing_value.selected))
            except Exception:
                pass


class Node_Value_Table(ValueNode):
    """A node providing a table of data loaded from a file, or provided as a static value"""
    node_display = 'Table'
    node_desc = 'Table Value'
    outputs = [
        IOPin('Out', 'Output Value', VarType.Table, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        # hide_true=['value'], hide_false=['file_path', 'sub_item']
        sections = [
            ConfigSection('ValueNode Config', 'Configuration for ValueNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Load from file?', 'Load data from a file', 'load_from_file', VarType.Bool, False, on_change=node_value_table_on_change),
                    ConfigParameter('File', 'If loading from file: path to source file', 'file_path', VarType.Path, on_change=node_value_table_on_change),
                    ConfigParameter('Sub-Item',
                                    'If loading from file: if file has sub items (sheets/tables) which one should be loaded?',
                                    'sub_item',
                                    VarType.Select,
                                    default=Select([SelectOption('0', 'Default', 'First or only sub-item'),], '0'),
                                    tweaks=InputWidgetTweaks_Select(item_type=VarType.String)),
                    ConfigParameter('Value', 'If NOT loading from file, static value to output', 'value', VarType.Table),
                    # ConfigParameter('Reload file on recalc?', 'If loading from file: reload from source file whenever this node is re-calculated', 'reload_on_recalc', VarType.Bool, False),
                ]),
                ConfigGroup('Table Rendering', 'Viewing Table data', [
                    ConfigParameter('Column Width', 'Width per-column', 'column_width', VarType.Integer, 80, tweaks=InputWidgetTweaks_Integer(min=0, max=1920, format='%d Pixels')),
                    ConfigParameter('Limit Columns', 'Limit the number of columns displayed in preview', 'limit_cols', VarType.Integer, 6, tweaks=InputWidgetTweaks_Integer(min=1, format='%d Columns')),
                    ConfigParameter('Limit Rows', 'Limit the number of rows displayed in preview', 'limit_rows', VarType.Integer, 8, tweaks=InputWidgetTweaks_Integer(min=1, format='%d Rows')),
                ]),
            ]),
        ]
    config = nodeConfig()

    def draw_middle(self):
        """Draw the current table value"""
        current_value = self.config.get('value')
        table_size = current_value.get_size()
        num_cols = self.config.get('limit_cols')
        if table_size.y < num_cols:
            num_cols = table_size.y
        total_width = self.config.get('column_width') * num_cols
        display_table(current_value, limit_rows=self.config.get('limit_rows'), limit_cols=self.config.get('limit_cols'), width=total_width, height=0)
        if self.config.get('load_from_file'):
            file_path: Path = self.config.get('file_path')
            sub_item: str = self.config.get('sub_item').selected
            imgui.text(f'File: {file_path.name}\nSub-Item: {sub_item}')

    def refresh(self) -> list:
        """Refresh output value from configured value, or in this case from file
        """
        if self.config.get('load_from_file'):
            filepath: Path = self.config.get('file_path')
            if not filepath.is_file():
                raise FileNotFoundError(f'Configured file path not found: {str(filepath)}')
            subitem_select: Select = self.config.get('sub_item')
            subitem = subitem_select.selected
            # load file into a dict of dataframes, then select the first (should be subitem we requested)
            dataframes = load_file_to_dataframes(filepath, subitem)
            subitem_names = [key for key, _val in dataframes.items()]
            this_df = dataframes[subitem_names[0]]
            # turn dataframe into a Table
            df_dict = this_df.to_dict()
            this_table = Table.from_dict(df_dict)
            # test that Table can be json serialized
            try:
                tab_data = this_table.to_dict()
                tab_json = json.dumps(tab_data)
            except Exception as ex:
                raise NodeException('Data loaded from file could not be JSON serialized!') from ex
            if len(tab_json) == 0:
                raise NodeException('Data loaded from file could not be JSON serialized!')
            self.config.set('value', this_table)
        return [self.config.get('value')]
