"""
Althea - Node implementations: Table Manipulation

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING, Union, Any

import pandas
import pandasql
import sqlparse

from ..common import imgui
from ..vartypes import VarType, Table, Select, SelectOption
from ..config import ConfigGroup, ConfigSection, ConfigParameter, Config

from ..ui import global_ui_state, FontSize, FontVariation, HorizontalGroup
from ..ui import InputWidgetTweaks_String, InputWidgetTweaks_List, InputWidgetTweaks_Integer, InputWidgetTweaks_Select

from .primitives import IOPin, IOKind, NodeKind
from .base import Node
from .config import NodeConfig, CommonNodeConfig

if TYPE_CHECKING:
    from . import state


class Node_Table(Node):
    """Base class for nodes which manipulate table data"""
    node_category = 'Tables'
    node_subcategory = 'General'

    @staticmethod
    def execute(inputs: list[Table], config: NodeConfig, common_config: CommonNodeConfig) -> list:
        raise NotImplementedError('Node subclass did not implement method execute() !')


def node_table_selectregion_on_change(key: str, val: Any, config: Config):
    """Handle value change for config values in Node_Table_SelectRegion """
    if key == 'row_range':
        if val:
            config.hide('rows')
            config.unhide(['row_start', 'row_end'])
        else:
            config.unhide('rows')
            config.hide(['row_start', 'row_end'])
    if key == 'filter_columns':
        affected_keys = ['columns']
        if val:
            config.unhide(affected_keys)
        else:
            config.hide(affected_keys)
    if key == 'filter_rows':
        affected_keys = ['row_start', 'row_end', 'row_range', 'rows']
        if val:
            config.unhide(affected_keys)
        else:
            config.hide(affected_keys)


class Node_Table_SelectRegion(Node_Table):
    """A node which selects only the configured rows and columns"""
    node_kind = NodeKind.Simple
    node_display = 'Select Region'
    node_desc = 'Select only the configured rows and columns'
    inputs = [
        IOPin('Original', 'Original Table', VarType.Table, IOKind.Input),
    ]
    outputs = [
        IOPin('Filtered', 'Filtered Table', VarType.Table, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('TableNode Config', 'Configuration for TableNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Filter Columns?', 'Enable column filtering', 'filter_columns', VarType.Bool, False, on_change=node_table_selectregion_on_change),
                    ConfigParameter('Columns', 'Names of columns to keep', 'columns', VarType.List, tweaks=InputWidgetTweaks_List(item_type=VarType.String, tweaks=InputWidgetTweaks_String(), item_min=1)),
                    ConfigParameter('Filter Rows?', 'Enable row filtering', 'filter_rows', VarType.Bool, False, on_change=node_table_selectregion_on_change),
                    ConfigParameter('Row Range?', 'Select a range of rows instead of a list', 'row_range', VarType.Bool, False, on_change=node_table_selectregion_on_change),
                    ConfigParameter('Rows', 'Numbers (zero-indexed) of rows to keep', 'rows', VarType.List, tweaks=InputWidgetTweaks_List(item_type=VarType.Integer, tweaks=InputWidgetTweaks_Integer(min=0, enforce_range=True), item_min=1)),
                    ConfigParameter('Rows Start', 'Row to start with (zero-indexed)', 'row_start', VarType.Integer, tweaks=InputWidgetTweaks_Integer(enforce_range=True, min=0)),
                    ConfigParameter('Rows End', 'Row to end with (zero-indexed) (inclusive)', 'row_end', VarType.Integer, tweaks=InputWidgetTweaks_Integer(enforce_range=True, min=0)),
                ]),
            ]),
        ]
    config = nodeConfig()

    def draw_middle(self):
        """Draw the center content, sumarizing configuration"""
        with HorizontalGroup():
            imgui.push_font(global_ui_state.fonts.get(FontSize.Normal, FontVariation.Regular))
            with HorizontalGroup():
                if self.config.get('filter_rows'):
                    imgui.text('Rows:')
                    if self.config.get('row_range'):
                        row_start: int = self.config.get('row_start')
                        row_end: int = self.config.get('row_end')
                        imgui.text(f'{row_start} - {row_end}')
                    else:
                        sel: list[str] = self.config.get('rows')
                        for count, row in enumerate(sel):
                            if count > 20:
                                imgui.text(f'...{len(sel) - 20} more')
                                break
                            imgui.text(str(row))
                    imgui.text(' ')
            with HorizontalGroup():
                if self.config.get('filter_columns'):
                    imgui.text('Columns:')
                    sel: list[str] = self.config.get('columns')
                    for col in sel:
                        imgui.text(col)

            imgui.pop_font()

    @staticmethod
    def execute(inputs: list[Table], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        input_: Table = inputs[0]

        input_df = input_.df.copy(deep=True)

        if config.get('filter_rows'):
            if config.get('row_range'):
                newitems = range(config.get('row_start'), config.get('row_end') + 1)
            else:
                newitems = []
                for item in config.get('rows'):
                    if item < 0:
                        continue  # skip invalid negative
                    newitems.append(item)

            input_df = input_df.filter(axis='index', items=newitems)

        if config.get('filter_columns'):
            input_df = input_df.filter(axis='columns', items=config.get('columns'))

        new_df_dict = input_df.to_dict()
        return [Table.from_dict(new_df_dict)]


class Node_Table_Merge(Node_Table):
    """A node which merges two tables"""
    # reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html
    node_kind = NodeKind.Simple
    node_display = 'Merge'
    node_desc = 'Merge two tables'
    inputs = [
        IOPin('A', 'Left Table', VarType.Table, IOKind.Input),
        IOPin('B', 'Right Table', VarType.Table, IOKind.Input),
    ]
    outputs = [
        IOPin('Merged', 'Merged Table', VarType.Table, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('TableNode Config', 'Configuration for TableNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Method', 'How to merge the two tables', 'merge_method',
                                    VarType.Select,
                                    Select([
                                        SelectOption('inner', 'Inner', 'use intersection of keys from both frames, similar to a SQL inner join; preserve the order of the left keys.'),
                                        SelectOption('outer', 'Outer', 'use union of keys from both frames, similar to a SQL full outer join; sort keys lexicographically.'),
                                        SelectOption('left', 'Left', 'use only keys from left frame, similar to a SQL left outer join; preserve key order.'),
                                        SelectOption('right', 'Right', 'use only keys from right frame, similar to a SQL right outer join; preserve key order.'),
                                        SelectOption('cross', 'Cross', 'creates the cartesian product from both frames, preserves the order of the left keys.'),
                                    ], 'inner'),
                                    tweaks=InputWidgetTweaks_Select(item_type=VarType.String, tweaks=InputWidgetTweaks_String())
                                    ),
                    ConfigParameter('On Column', 'Columns to use as key for merging, must be present in both input tables', 'on_column', VarType.String),
                    ConfigParameter('Sort?', 'Sort the result by the join keys in lexicographical order', 'sort', VarType.Bool, False),
                    ConfigParameter('Validate Method', 'How to validate', 'validate_method',
                                    VarType.Select,
                                    Select([
                                        SelectOption('None', 'None', 'no validation'),  # NOTE: have to check for this, and actually pass None or just dont pass this arg
                                        SelectOption('one_to_one', 'One to One', 'checks if merge keys are unique in both left and right datasets.'),
                                        SelectOption('one_to_many', 'One to Many', 'checks if merge keys are unique in left dataset.'),
                                        SelectOption('many_to_one', 'Many to One', 'checks if merge keys are unique in right dataset.'),
                                    ], 'None'),
                                    tweaks=InputWidgetTweaks_Select(item_type=VarType.String, tweaks=InputWidgetTweaks_String())
                                    ),
                ]),
            ]),
        ]
    config = nodeConfig()

    def draw_middle(self):
        """Draw the center content, sumarizing configuration"""
        with HorizontalGroup():
            imgui.push_font(global_ui_state.fonts.get(FontSize.Normal, FontVariation.Regular))
            with HorizontalGroup():
                imgui.text(f'Method: {self.config.get("merge_method").selected}')
                imgui.text(f'On: {self.config.get("on_column")}')
                imgui.text(f'Sort?: {self.config.get("sort")}')
                imgui.text(f'Validation: {self.config.get("validate_method").selected}')
            imgui.pop_font()

    @staticmethod
    def execute(inputs: list[Table], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        if config.get('validate_method').selected == 'None':
            new_df = pandas.merge(inputs[0].df, inputs[1].df, how=config.get('merge_method').selected, on=config.get('on_column'), sort=config.get('sort'))
        else:
            new_df = pandas.merge(inputs[0].df, inputs[1].df, how=config.get('merge_method').selected, on=config.get('on_column'), sort=config.get('sort'), validate=config.get('validate_method').selected)

        new_df_dict = new_df.to_dict()
        return [Table.from_dict(new_df_dict)]


def clean_sql_query(query) -> str:
    """
    Clean a sql query string, stripping newlines, tabs, and excessive whitespace
        this allows our config to store a formatted multiline query, but remove all that at execution time
    """
    clean_query = ' '.join(query.splitlines())      # replace newlines with single space
    clean_query = clean_query.replace('\t', ' ')    # replace tabs with single space
    clean_query = ' '.join(clean_query.split())     # replace any instances of more-than-one space, with a single space
    return clean_query


SQL_QUERY_COMMENT = """
# SQL Query

Perform a SQL query on a table, as if it were in a SQLite database.

Supports the [SQLite syntax](http://www.sqlite.org/lang.html), but any changes made to input tables will be discarded

## Input tables available as:

* `table_a`
* `table_b`
* `table_c`
* `table_d`

Newlines, tabs, and excessive whitespace characters will be ignored, so feel free to format as you wish

"""


class Node_Table_SQLQuery(Node_Table):
    """A node which performs a sql query on 1-4 tables, outputting result as another table"""
    node_kind = NodeKind.Simple
    node_display = 'SQLQuery'
    node_desc = 'Run a SQL query against 1-4 tables, outputting result as another table'
    inputs = [
        IOPin('Table A', 'Source table, named "table_a" in SQL', VarType.Table, IOKind.Input),
        IOPin('Table B', 'Source table, named "table_b" in SQL', VarType.Table, IOKind.Input),
        IOPin('Table C', 'Source table, named "table_c" in SQL', VarType.Table, IOKind.Input),
        IOPin('Table D', 'Source table, named "table_d" in SQL', VarType.Table, IOKind.Input),
    ]
    outputs = [
        IOPin('Results', 'Results of query', VarType.Table, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('TableNode Config', 'Configuration for TableNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Query', '',
                                    'query', VarType.String, comment=SQL_QUERY_COMMENT, tweaks=InputWidgetTweaks_String(code_editor=True, code_language='c')),
                ]),
            ]),
        ]
    config = nodeConfig()

    def format_query(self) -> str:
        """Format query string for user viewing"""
        query = clean_sql_query(self.config.get('query'))
        return sqlparse.format(query, reindent=True, keyword_case='upper')

    def draw_middle(self):
        """Draw the center content, if there is any"""
        with HorizontalGroup():
            imgui.push_font(global_ui_state.fonts.get(FontSize.Normal, FontVariation.Regular))
            with HorizontalGroup():
                imgui.text('Query:')
                imgui.text(self.format_query())
            imgui.pop_font()

    @staticmethod
    def execute(inputs: list[Table], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        env_dict = {}
        for in_num, name in enumerate(['table_a', 'table_b', 'table_c', 'table_d']):
            if inputs[in_num] is not None:
                env_dict[name] = inputs[in_num].df
        query = clean_sql_query(config.get('query'))
        new_df = pandasql.sqldf(query, env_dict)
        if new_df is None:
            raise ValueError('pandasql.sqldf returned result: None')
        new_df_dict = new_df.to_dict()
        return [Table.from_dict(new_df_dict)]
