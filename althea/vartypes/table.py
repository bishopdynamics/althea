"""
Althea - Special VarTypes: Table

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from pandas import DataFrame

from ..common import ensure_serializable

from .base import SpecialVarType
from .vector import Vec2


class Table(SpecialVarType):
    """Table of data, implemented on top of pandas.DataFrame for speed"""

    def __init__(self, *args) -> None:
        super().__init__()
        self.df = DataFrame(*args)

    @staticmethod
    def default() -> Table:
        return Table({'first': ['', ''], 'second': ['', '']})

    @staticmethod
    def from_dict(data: dict) -> Table:
        return Table(data)

    @ensure_serializable
    def to_dict(self) -> dict:
        return self.df.to_dict()

    def add_row(self) -> Table:
        """Add a new empty row; returns new Table object"""
        value_dict = self.to_dict()
        for col, rowdict in value_dict.items():
            last_row_str = '0'
            for row_str, _val in rowdict.items():
                last_row_str = row_str
            break
        new_last_row_str = str(int(last_row_str) + 1)
        for col, rowdict in value_dict.items():
            value_dict[col][new_last_row_str] = ''  # pylint: disable=unsubscriptable-object
        return Table.from_dict(value_dict)

    def add_column(self) -> Table:
        """Add a new empty column; returns new Table object"""
        value_dict = self.to_dict()
        new_col_name = 'new'
        count = 0
        while new_col_name in value_dict.keys():
            count += 1
            new_col_name = 'new' + str(count)
        for _key, val in value_dict.items():
            first_val: list = val
            break
        new_val = {}
        for key, _val in first_val.items():
            new_val[key] = ''
        value_dict[new_col_name] = new_val  # pylint: disable=unsupported-assignment-operation
        return Table.from_dict(value_dict)

    def rename_column(self, old_name: str, new_name: str) -> Table:
        """rename a column, returning new Table object"""
        value_dict = self.to_dict()
        new_dict = {}
        for col_name, data in value_dict.items():
            if col_name == new_name:
                raise ValueError(f'A column named: {new_name} already exists!')
        for col_name, data in value_dict.items():
            if col_name == old_name:
                new_dict[new_name] = data
            else:
                new_dict[col_name] = data
        return Table.from_dict(new_dict)

    def get_size(self) -> Vec2:
        """Get the size of this table as Vec2[rows, cols]"""
        return Vec2(self.df.shape[0], self.df.shape[1])
