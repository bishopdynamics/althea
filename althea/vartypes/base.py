"""
Althea - Var Types - Base classes

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import enum

from abc import abstractmethod
from pathlib import Path


class VarTypeException(Exception):
    """Exception in vartype processing"""


def get_vartype(name: str) -> VarType:
    """Get VarType from name"""
    for vt in VarType:
        if vt.name == name:
            return vt
    raise ValueError(f'VarType does not exist: {name}')


class VarType(enum.Enum):
    """Supported Types"""

    # standards
    Any = enum.auto()
    """Any type, skip type checking"""
    Bool = enum.auto()
    """A Boolean value (True/False)"""
    Number = enum.auto()
    """Either Integer or Float; should only use on IOPin inputs"""
    Integer = enum.auto()
    """An Integer value"""
    Float = enum.auto()
    """A floating point value"""
    String = enum.auto()
    """A string value (text)"""
    List = enum.auto()
    """A List of (another VarType, not Any, Number, or List)"""

    # special cases that cannot be sub-classed into a SpecialVarType
    Path = enum.auto()
    """A filesystem path"""
    VarType = enum.auto()
    """A variable type; a special form of Select, actually a string name of the VarType"""
    Sheet = enum.auto()
    """A sheet id from current workspace; a special form of Select, actually the id as int"""

    # SpecialVarType sub-classes (not in VarTypeDefaults, use .default() instead)
    Table = enum.auto()
    """Table of data, specifically a pandas.Dataframe"""
    Vec2 = enum.auto()
    """Vector of 2 Floats"""
    Vec4 = enum.auto()
    """Vector of 4 Floats"""
    NormalizedColorRGB = enum.auto()
    """Color as RGB normalized floats (0.0 - 1.0)"""
    NormalizedColorRGBA = enum.auto()
    """Color as RGBA normalized floats (0.0 - 1.0)"""
    Select = enum.auto()
    """Choose from a limited set of options, returning a configurable value type"""
    IOPinInfo = enum.auto()
    """Provide information to create an Input or Output pin; specifically VarType, Label, Description"""


# default values for each VarType, need to keep this in sync with VarType, except for SpecialVarTypes
VarTypeDefaults = {
    # standards
    'Any': None,
    'Bool': False,
    'Number': 0,
    'Integer': 0,
    'Float': 0.0,
    'String': '',
    'List': [],
    # special cases that cannot be sub-classed into a SpecialVarType
    'Path': Path().cwd(),
    'VarType': 'String',
    'Sheet': None,
}

# VarTypes that are compatible with a Number input
VARTYPE_NUMBER_TYPES = [VarType.Integer, VarType.Float]


class SpecialVarType:
    """base class for special vartypes"""

    def __init__(self) -> None:
        self._is_special_vartype = True

    def __reduce__(self):
        """This makes all SpecialVarType pickle-able (as long as they also implement to_dict and from_dict)"""
        return (self.__class__.from_dict, (self.to_dict(),))

    def __eq__(self, other: SpecialVarType) -> bool:
        """
        This makes all SpecialVarType able to be compared for equality with another of the same vartype
            we compare by dumping both objects to dict and comparing keys and values
        """
        if not isinstance(other, SpecialVarType):
            raise VarTypeException(f'Expecting type: SpecialVarType, got: {type(other).__name__}')
        self_data = self.to_dict()
        other_data = other.to_dict()
        for key, val in self_data.items():
            if key not in other_data:
                return False
            if other_data[key] != val:
                return False
        for key in other_data:
            if key not in self_data:
                return False
        return True

    def to_dict(self) -> dict:
        """Create a dict representing this object that we can use for serialization"""
        raise NotImplementedError('Sub-classes must implement this method!')

    @staticmethod
    @abstractmethod
    def from_dict(data: dict) -> SpecialVarType:
        """Create this var type from a dictionary (output of to_dict)"""
        raise NotImplementedError('Sub-classes must implement this method!')

    @staticmethod
    @abstractmethod
    def default() -> SpecialVarType:
        """Create object of this type with the default value"""
        raise NotImplementedError('Sub-classes must implement this method!')
