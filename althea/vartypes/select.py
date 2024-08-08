"""
Althea - Special VarTypes: Select

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import Any
from dataclasses import dataclass

from ..common import log, ensure_serializable
from .base import SpecialVarType, VarTypeException


@dataclass
class SelectOption:
    """An individual option for a Select vartype"""
    value: Any
    display: str
    description: str = ''

    @ensure_serializable
    def to_dict(self) -> dict:
        """Convert this option to a dict for serialization"""
        return {
            'value': self.value,
            'display': self.display,
            'description': self.description,
        }

    @staticmethod
    def from_dict(data: dict) -> SelectOption:
        """Create this option from a dict, output of to_dict"""
        return SelectOption(data['value'], data['display'], data['description'])


class Select(SpecialVarType):
    """Select from a limited set of options"""

    def __init__(self, options: list[SelectOption] = None, selected: Any = None) -> None:
        super().__init__()
        if options is None:
            self.options: list[SelectOption] = []
        else:
            self.options: list[SelectOption] = options
        self.selected = selected
        self._check_for_duplicate_options()
        self.ensure_sane_selection()

    def _check_for_duplicate_options(self):
        """Check that all option values are unique"""
        seen_opts = []
        for opt in self.options:
            if opt.value in seen_opts:
                raise VarTypeException(f'Duplicate option value: {str(opt.value)}')
            seen_opts.append(opt.value)

    def ensure_sane_selection(self):
        """
        Try to set self.selected to a sane value
            if there are no options, then value will be None, otherwise will always be a valid selection
        """
        if self.selected is not None:
            valid_selected = False
            for opt in self.options:
                if opt.value == self.selected:
                    valid_selected = True
                    break
            if not valid_selected:
                # log.warning(f'Select: invalid selection: {self.selected}')
                self.selected = None
        if self.selected is None and len(self.options) > 0:
            log.warning(f'Select: invalid selection: {self.selected}, selection reset to first option')
            self.selected = self.options[0].value

    def select(self, value: Any):
        """Set the currently selected value, if it is valid"""
        valid_selected = False
        for opt in self.options:
            if opt.value == value:
                valid_selected = True
                break
        if not valid_selected:
            log.warning(f'Attempted to select invalid option: {str(value)}')
        self.selected = value

    @staticmethod
    def default() -> Select:
        return Select([], None)

    @staticmethod
    def from_dict(data: dict) -> Select:
        opt = []
        for this_opt in data['options']:
            opt.append(SelectOption.from_dict(this_opt))
        return Select(opt, data['selected'])

    @ensure_serializable
    def to_dict(self) -> dict:
        opt = []
        for this_opt in self.options:
            opt.append(this_opt.to_dict())
        return {'options': opt, 'selected': self.selected}

    def get_opt(self, value: Any) -> SelectOption:
        """Get the SelectOption with given value"""
        for opt in self.options:
            if opt.value == value:
                return opt
        raise VarTypeException(f'Could not find option with value: {str(value)}')

    def get_selected(self) -> SelectOption:
        """Get the currently selected SelectOption"""
        if self.selected is None:
            return None
        for opt in self.options:
            if opt.value == self.selected:
                return opt
        raise VarTypeException(f'Could not find option with value: {str(self.selected)}')
