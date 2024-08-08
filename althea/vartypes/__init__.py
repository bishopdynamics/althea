"""
Althea - Var Types

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from inspect import isclass
from pkgutil import iter_modules
from importlib import import_module
from pathlib import Path, PosixPath, WindowsPath

from .base import *
from .color import *
from .vector import *
from .table import *
from .select import *

from ..common import get_program_dir


DEBUG_VARTYPE_VALIDATION = False


def validate_vartype(value: Any, vartype: VarType) -> bool:
    """
    Check that the given value is of the given VarType
        for types like List and Select, cannot verify that values are of correct type
    """
    if DEBUG_VARTYPE_VALIDATION:
        try:
            value_str = value.__class__.__name__
        except Exception:
            try:
                value_str = str(value)
            except Exception:
                value_str = '(failed to make str)'

        if value_str.strip() == '':
            value_str = '(empty? huh...)'

        log.debug(f'Validating type, expecting: {vartype.name}, got: {value_str}')

    # TODO: ugh this is a crappy way to handle this,
    #   but sometimes values on-disk are None because the associated UI element (like a select) was never viewed prior to save
    #   realistically, we need fix THAT instead
    if value is None:
        log.warning(f'VarType validation bypassed for: {vartype.name}, because value is: None -- This bug needs to be fixed elsewhere!!!')
        return True

    match vartype:
        case VarType.Any:
            return True
        case VarType.Bool:
            if isinstance(value, bool):
                return True
        case VarType.Integer:
            if isinstance(value, int):
                return True
        case VarType.Float:
            if isinstance(value, float):
                return True
        case VarType.Number:
            if isinstance(value, (int, float)):
                return True
        case VarType.String:
            if isinstance(value, str):
                return True
        case VarType.List:
            if isinstance(value, list):
                return True
        case VarType.Path:
            if isinstance(value, Path):
                return True
        case VarType.Table:
            if isinstance(value, Table):
                return True
        case VarType.Vec2:
            if isinstance(value, Vec2):
                return True
        case VarType.Vec4:
            if isinstance(value, Vec4):
                return True
        case VarType.NormalizedColorRGB:
            if isinstance(value, NormalizedColorRGB):
                return True
        case VarType.NormalizedColorRGBA:
            if isinstance(value, NormalizedColorRGBA):
                return True
        case VarType.Select:
            if isinstance(value, Select):
                return True
        case VarType.VarType:
            if isinstance(value, Select):
                return True
        case VarType.Sheet:
            if isinstance(value, Select):
                return True
    return False


def _get_package_dir():
    """figure out absolute path to this package folder"""
    # NOTE: dont forget to include ./althea folder when building app using pyinstaller/nuitka
    program_dir = get_program_dir()
    package_dir = program_dir.joinpath('althea').joinpath('vartypes')
    # print(f'vartypespkg dir: {str(package_dir)}')
    return package_dir


def collect_special_vartype_classes() -> dict[str, type[SpecialVarType]]:
    """Collect all SpecialVarType classes"""
    special_vartypes: dict[str, type[SpecialVarType]] = {}
    package_dir = _get_package_dir()
    for (_, module_name, _) in iter_modules([package_dir]):

        # import the module and iterate through its attributes
        module = import_module(f"{__name__}.{module_name}")

        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)

            if isclass(attribute) and issubclass(attribute, SpecialVarType):
                if attribute.__name__ != 'SpecialVarType':
                    globals()[attribute_name] = attribute
                    special_vartypes[attribute_name] = attribute
    if 'IOPinInfo' not in special_vartypes:
        special_vartypes['IOPinInfo'] = IOPinInfo
    return special_vartypes


def get_vartype_default(var: VarType) -> Any:
    """Get default value for given VarType"""
    all_special_vartypes = collect_special_vartype_classes()
    if var.name not in VarTypeDefaults:
        if var.name not in all_special_vartypes:
            raise ValueError(f'VarType {var.name} is missing from VarTypeDefaults and collection of special vartypes !')
        special_var_type = all_special_vartypes[var.name]
        default = special_var_type.default()
    else:
        default = VarTypeDefaults[var.name]
    return default


@ensure_serializable
def make_serializable(values: Any) -> Any:
    """
    Helper to any supported value into something serializable
        if the thing is already serializable it will be returned unmodified
        if extra work is done, the result will be a dict with a key named "__special_var_marker__" to help identify it in unmake_serializable()
    """
    # NOTE: in order to handle the possibility of value being a list, we treat value as always being a list,
    #   and then put it back if it was originally not a list
    #   we also have to do the same thing in set_dict(), to restore lists
    was_a_list = True
    if not isinstance(values, list):
        values = [values,]
        was_a_list = False

    serializable_values: list = []
    for value in values:
        if issubclass(value.__class__, SpecialVarType) or isinstance(value, SpecialVarType):
            value_s = {
                '__special_var_marker__': True,  # this is our marker to help us identify special types that need to_dict/from_dict treatment
                'vartype': value.__class__.__name__,
                'value': value.to_dict(),
            }
        elif isinstance(value, (PosixPath, WindowsPath)):
            # NOTE: we tried making our own sub-class of Path, but it always becomes a PosixPath or WindowsPath, so we need to handle this one special
            # TODO: we should wrap this into our own path class, instead of subclassing Path, eliminate this special case
            value_s = {
                '__special_var_marker__': True,  # this is our marker to help us identify special types that need to_dict/from_dict treatment
                'vartype': 'Path',
                'value': str(value),
            }
        else:
            value_s = value
        serializable_values.append(value_s)

    if was_a_list:
        return serializable_values
    return serializable_values[0]


def unmake_serializable(values: Any) -> Any:
    """Helper to reverse what was done by make_serializable, to get a real object back if applicable"""
    _all_special_vartypes = collect_special_vartype_classes()
    was_a_list = True
    if not isinstance(values, list):
        values = [values,]
        was_a_list = False
    deserialized_values: list = []
    for value in values:
        if isinstance(value, dict):
            if '__special_var_marker__' in value:
                if value['vartype'] == 'Path':
                    # NOTE: see comment in get_dict above, about why Path is handled special
                    value = Path(value['value'])
                else:
                    special_var_type = _all_special_vartypes[value['vartype']]
                    value = special_var_type.from_dict(value['value'])
        deserialized_values.append(value)

    if was_a_list:
        return deserialized_values
    return deserialized_values[0]


class IOPinInfo(SpecialVarType):
    """Information to create an Input or Output pin"""

    def __init__(self, io_type: VarType, label: str, description: str, static_value: Any = None, static_list_item_type: VarType = VarType.String) -> None:
        super().__init__()
        self.io_type = io_type
        """Type of data this pin provides/accepts"""
        self.label = label
        """Label to show next to this pin"""
        self.description = description
        """Description of this pin, used in tooltip on hover"""
        self.static_value: Any = static_value
        """
        For StaticValuesNode output pins only: Static value assigned to this pin
            by default, this is hidden and not used. 
            You must set input widgets flag edit_static_value=True for an input widget to be created based on io_type
        """
        self.static_list_item_type: VarType = static_list_item_type
        """For StaticValuesNode output pins only: if the static value is a list, this is the type for items in that list"""

    @ensure_serializable
    def to_dict(self) -> dict:
        the_dict = {
            'io_type': self.io_type.name,
            'label': self.label,
            'description': self.description,
            'static_value': None,
            'static_list_item_type': self.static_list_item_type.name
        }
        the_dict['static_value'] = make_serializable(self.static_value)
        return the_dict

    @staticmethod
    def from_dict(data: dict) -> IOPinInfo:
        vt = get_vartype(data['io_type'])
        static_value = unmake_serializable(data['static_value'])
        static_list_item_type = get_vartype(data['static_list_item_type'])
        the_obj = IOPinInfo(vt, data['label'], data['description'], static_value, static_list_item_type)
        return the_obj

    @staticmethod
    def default() -> IOPinInfo:
        return IOPinInfo(VarType.String, '', '', None)
