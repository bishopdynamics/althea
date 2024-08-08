"""
Althea - Object Config System - Base

    Within a config, parameters are organized within sections and groups, 
        however the values are stored in a flat dictionary
"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import json

from typing import Callable, Any, Union
from copy import deepcopy
from pathlib import Path


from ..common import log, ensure_serializable
from ..vartypes import VarType, Vec2, Select, SelectOption, make_serializable, unmake_serializable
from ..vartypes import get_vartype_default, validate_vartype, collect_special_vartype_classes

from ..ui.input import InputWidgetTweaks, InputWidgetTweaks_Bool, InputWidgetTweaks_Float, InputWidgetTweaks_String
from ..ui.input import InputWidgetTweaks_Integer, InputWidgetTweaks_Color, InputWidgetTweaks_Path, InputWidgetTweaks_List
from ..ui.input import InputWidgetTweaks_Table, InputWidgetTweaks_Select, InputWidgetTweaks_Sheet, InputWidgetTweaks_VarType


class ConfigException(Exception):
    """Config exception"""


class ConfigParameter:
    """A configuration parameter"""
    label: str
    """Label to show in UI next to input/display for this data"""
    description: str
    """Description shown in tooltip on hover"""
    key: str
    """Unique key name for config dict when passing it around"""
    type: VarType
    """What kind of data is this? (determines which InputWidget is used to edit)"""
    default: Any = None
    """Default value; if None is provided, will use the default value corresponding to the VarType"""
    tweaks: InputWidgetTweaks = None
    """Tweaks to pass to input widget for this VarType; tweaks allow you to further control how an input widget behaves"""
    hidden: bool = False
    """
    Hide this parameter by default; an on_change function may hide or unhide parameters
        being hidden only affects the UI, the value is unaffected
    """
    on_change: Callable[[str, Any, Config]] = None
    """
    Callback for mutating other config values in response to a change in this one
        signature: (param_key: str, new_value: Any, config: Config) -> None
    """
    comment: str = ''
    """
    Additional comment (in markdown format) to place in a block before / above the input widget
        this is a great place to put instructions or further explanation
    """

    def __init__(self, label: str, description: str, key: str, type_: VarType, default: Any = None, tweaks: InputWidgetTweaks = None,
                 hidden: bool = False, on_change: Callable[[str, Any, Config]] = None, comment: str = '') -> None:
        self.label = label
        self.description = description
        self.key = key
        self.type = type_
        self.tweaks = tweaks
        self.hidden = hidden
        self.on_change = on_change
        self.comment = comment
        self.default = get_vartype_default(self.type)
        if default is not None:
            self.default = default


class ConfigGroup:
    """A second-level grouping, visualized as a collapsable node in a tree"""

    def __init__(self, label: str, description: str, parameters: list[ConfigParameter]) -> None:
        self.label = label
        """Label to show in UI in group header"""
        self.description = description
        """Description to show in tooltip on hover over group header"""
        self.parameters = parameters
        """Individual config parameters, in the order to be listed"""


class ConfigSection:
    """A high-level grouping, visualized as a collapsable section"""

    def __init__(self, label: str, description: str, groups: list[ConfigGroup]) -> None:
        self.label = label
        """Label to show in UI in section header"""
        self.description = description
        """Description to show in tooltip on hover over section header"""
        self.groups = groups
        """Config Groups, in the order to be listed"""


class Config:
    """
    A top-level grouping, full config for an object
        Sub-class this, and define sections
        Within a specific Config, all config parameter keys must be unique, 
            regardless of which group or section they belong to
    """
    sections: list[ConfigSection] = []
    """Config Sections, in the order to be listed"""
    max_on_change_stack = 4
    """Maximum depth of on_change -> another on_change -> another etc"""
    _all_special_vartypes = collect_special_vartype_classes()
    """A dict to lookup special vartypes by name (class name)"""

    def __init__(self) -> None:
        self._config_dict: dict[str, Any] = {}
        """Internal storage for current config values"""
        self._changed = False
        """Internal tracking: have any values in this config changed?"""
        self._on_change_stack = []
        """
        Track currently in-progress on_change callbacks as a stack
            when callback is complete, it will be popped from the stack.
                we do this so that we can keep an eye on how deep this stack gets, and abort if it gets too deep
        """
        self.sections = deepcopy(self.sections)
        self.check_for_duplicates()
        self.set_default_values()

    def check_for_duplicates(self):
        """Check for any duplicate keys"""
        seen_keys: list[str] = []
        for section in self.sections:
            for group in section.groups:
                for param in group.parameters:
                    if param.key in seen_keys:
                        raise ConfigException(f'Duplicate config parameter key: {param.key}')
                    seen_keys.append(param.key)

    def set_default_values(self):
        """Apply default values for all parameters, and then go back and call on_change for any applicable parameters"""
        for section in self.sections:
            for group in section.groups:
                for param in group.parameters:
                    self._config_dict[param.key] = param.default
        # we do this in two passes so that an on_change can affect
        #   other parameter values without risking being overwritten by default
        for section in self.sections:
            for group in section.groups:
                for param in group.parameters:
                    self.do_on_change(param.key, self._config_dict[param.key])

    def get_param(self, param_key: str) -> ConfigParameter:
        """Get the parameter with given key"""
        for section in self.sections:
            for group in section.groups:
                for param in group.parameters:
                    if param.key == param_key:
                        return param
        raise ConfigException(f'Could not find parameter with key: {param_key}')

    @ensure_serializable
    def to_dict(self) -> dict[str, Any]:
        """Get this config as dictionary, ready to be pickled"""
        pdict = {}
        for key, values in self._config_dict.items():
            s_values = make_serializable(values)
            pdict[key] = s_values
        return pdict

    def set_dict(self, config: dict[str, Any]):
        """Set config from a dictionary, the output of to_dict()"""
        updict = {}
        for key, values in config.items():
            ds_values = unmake_serializable(values)
            updict[key] = ds_values
        for key, value in updict.items():
            self._set(key, value)
        self.mark_unchanged()

    def get(self, param_key: str) -> Any:
        """Get value of an individual config parameter"""
        for key, value in self._config_dict.items():
            if key == param_key:
                return value
        raise ConfigException(f'Could not get config parameter with key: {param_key}; not found!')

    def _set(self, param_key: str, value: Any):
        """(internal) Set value of individual config parameter"""
        if param_key not in self._config_dict:
            # raise ConfigException(f'Cannot set config parameter with key: {param_key}; not found!')
            log.warning((f'Cannot set config parameter with key: {param_key}; not found! Value from file discarded'))
        else:
            param = self.get_param(param_key)
            if not validate_vartype(value, param.type):
                raise ConfigException(f'Value type mismatch, expecting: {param.type.name}')
            self._config_dict[param_key] = value
            self.do_on_change(param_key, value)

    def set(self, param_key: str, value: Any):
        """Set value of individual config parameter"""
        current_value = self.get(param_key)
        # TODO: Some datatypes (like pandas.DataFrame) cannot be compared for equality without more complicated steps
        #   for now, we simply consider all those types to always have changed when set
        #   any type that derives from SpecialVarType should work correctly automatically
        value_changed = False
        try:
            if value != current_value:
                value_changed = True
        except Exception:
            value_changed = True
        if value_changed:
            self._set(param_key, value)
            self.mark_changed()

    def do_on_change(self, param_key: str, value: Any):
        """Do the on_change action for given config parameter with new value"""
        for section in self.sections:
            for group in section.groups:
                for param in group.parameters:
                    if param.key == param_key:
                        if param.on_change is not None:
                            self._on_change_stack.append(param_key)
                            if len(self._on_change_stack) > self.max_on_change_stack:
                                self._on_change_stack.pop(-1)
                                raise ConfigException(f'Config parameter on_change callback stack has grown beyond {self.max_on_change_stack}, potentially indicating infinite loop!')

                            try:
                                # log.debug(f'Calling callback for config param change: {param_key}')
                                param.on_change(param_key, value, self)
                            except Exception as ex:
                                self._on_change_stack.pop(-1)
                                raise ConfigException(f'Failed to perform on_change tasks for param: {param_key}') from ex
                            self._on_change_stack.pop(-1)
                        break

    def has_changes(self) -> bool:
        """Check if config has changes; it is up to the checker to call mark_unchanged() once changes have been applied/saved/acknowledged"""
        return self._changed

    def mark_changed(self):
        """Mark this config as having un-applied changes"""
        self._changed = True

    def mark_unchanged(self):
        """Mark this config as not having any un-applied changes"""
        self._changed = False

    def _set_hidden(self, param_key: str, hidden: bool):
        """(internal) helper for setting hidden attribute of a parameter"""
        for section in self.sections:
            for group in section.groups:
                for param in group.parameters:
                    if param.key == param_key:
                        param.hidden = hidden
                        return
        raise ConfigException(f'Could not find parameter with key: {param_key}')

    def hide(self, param_key: Union[str, list[str]]):
        """Mark the given config parameter as hidden"""
        if isinstance(param_key, str):
            param_key = [param_key]
        for key in param_key:
            self._set_hidden(key, True)

    def unhide(self, param_key: Union[str, list[str]]):
        """Un-Mark the given config parameter as hidden"""
        if isinstance(param_key, str):
            param_key = [param_key]
        for key in param_key:
            self._set_hidden(key, False)


class FileConfig(Config):
    """Config associated with a file, which is written any time a parameter is changed"""
    extension = 'json'
    """File extension, without the leading ."""
    file_name = 'Config'
    """File name to use, when writing to disk. Just the name, no extension, no path"""

    def __init__(self, base_path: Path = Path().cwd()) -> None:
        log.debug(f'Initializing FileConfig: {self.__class__.__name__}')
        super().__init__()
        self.file_path = base_path.joinpath(f'{self.file_name}.{self.extension}')
        """Full path to the file, where we will save this config on disk"""

    def save(self):
        """Save config to file"""
        log.debug(f'Saving FileConfig: {self.__class__.__name__} to: {str(self.file_path)}')
        try:
            # break up steps into separate "dict", "json", "write",
            #   so that we don't try to write anything to disk if to_dict or json.dumps fails
            config_dict = self.to_dict()
            config_json = json.dumps(config_dict)
            with open(self.file_path, 'wt', encoding='utf-8') as cf:
                cf.write(config_json)
            self.mark_unchanged()
        except Exception as ex:
            log.error(f'Exception while saving from file: {ex}')
            log.error(f'{self.__class__.__name__} parameter values will not be saved!')

    def load(self):
        """Load config from file"""
        log.debug(f'Loading FileConfig: {self.__class__.__name__} from: {str(self.file_path)}')
        try:
            with open(self.file_path, 'rt', encoding='utf-8') as cf:
                config_json = json.load(cf)
            self.set_dict(config_json)
            # set_dict will call mark_unchanged()
        except Exception as ex:
            log.error(f'Exception while loading from file: {ex}')
            log.error(f'Default {self.__class__.__name__} parameter values will be loaded instead')

    def set(self, param_key: str, value: Any):
        """Set value of individual config parameter, and save to file if changed"""
        current_value = self.get(param_key)
        if value != current_value:
            super().set(param_key, value)
            self.save()


class TestConfig(Config):
    """Testing Config, which uses all VarTypes and touches every applicable tweak for each"""
    sections = []
    test_tweaks: dict[VarType, list[InputWidgetTweaks]] = {
        VarType.Bool: [
            InputWidgetTweaks_Bool(),
            InputWidgetTweaks_Bool(show_helpmarker=False),
            InputWidgetTweaks_Bool(read_only=True),
            InputWidgetTweaks_Bool(button=True),
            InputWidgetTweaks_Bool(button=True, button_true='On', button_false='Off'),
            InputWidgetTweaks_Bool(button=True, button_true='Load', button_false='Do Not Load'),
            InputWidgetTweaks_Bool(button=True, button_true='<--', button_false='-->'),
        ],
        VarType.Integer: [
            InputWidgetTweaks_Integer(),
            InputWidgetTweaks_Integer(show_helpmarker=False),
            InputWidgetTweaks_Integer(read_only=True),
            InputWidgetTweaks_Integer(enforce_range=True, min=0, max=255),
            InputWidgetTweaks_Integer(enforce_range=True, min=0, max=100, format='%d%%'),
            InputWidgetTweaks_Integer(enforce_range=True, min=32, max=212, format='+%d°F'),
            InputWidgetTweaks_Integer(increment=2),
            InputWidgetTweaks_Integer(increment=4),
            InputWidgetTweaks_Integer(logarithmic=True, increment=0),
        ],
        VarType.Float: [
            InputWidgetTweaks_Float(),
            InputWidgetTweaks_Float(show_helpmarker=False),
            InputWidgetTweaks_Float(read_only=True),
            InputWidgetTweaks_Float(enforce_range=True, min=0.0, max=255.0, increment=0.25),
            InputWidgetTweaks_Float(enforce_range=True, min=0.0, max=1.0, increment=0.125),
            InputWidgetTweaks_Float(enforce_range=True, min=-1.0, max=1.0, increment=0.125),
            InputWidgetTweaks_Float(enforce_range=True, min=0.0, max=100.0, increment=0.25, format='%.3f%%'),
            InputWidgetTweaks_Float(enforce_range=True, min=0.0, max=100.0, increment=0.25, format='+%.3f°F'),
            InputWidgetTweaks_Float(increment=0.125),
            InputWidgetTweaks_Float(increment=0.00125),
            InputWidgetTweaks_Float(logarithmic=True, increment=0),
            InputWidgetTweaks_Float(round=True, round_digits=0, increment=0.001),  # intentionally bad increment should get rounded
            InputWidgetTweaks_Float(round=True, round_digits=2, increment=0.001),  # this should get rounded up to 0.01
            InputWidgetTweaks_Float(round=True, round_digits=3, increment=0.001),  # this is fine
            InputWidgetTweaks_Float(round=True, round_digits=3, increment=0.01),   # this increment is fine
        ],
        VarType.String: [
            InputWidgetTweaks_String(),
            InputWidgetTweaks_String(show_helpmarker=False),
            InputWidgetTweaks_String(read_only=True),
            InputWidgetTweaks_String(multiline=True),
            InputWidgetTweaks_String(multiline=True, multiline_size=Vec2(300, 400)),
            InputWidgetTweaks_String(multiline=True, multiline_size=Vec2(300, 400), read_only=True),
            InputWidgetTweaks_String(multiline=True, multiline_size=Vec2(400, 50)),
            InputWidgetTweaks_String(noblank=True),
            InputWidgetTweaks_String(secret=True),
            InputWidgetTweaks_String(allow_tab=True),
            InputWidgetTweaks_String(multiline=True, allow_tab=True),
        ],
        VarType.NormalizedColorRGB: [
            InputWidgetTweaks_Color(),
            InputWidgetTweaks_Color(show_helpmarker=False),
            InputWidgetTweaks_Color(read_only=True),
        ],
        VarType.NormalizedColorRGBA: [
            InputWidgetTweaks_Color(),
            InputWidgetTweaks_Color(show_helpmarker=False),
            InputWidgetTweaks_Color(read_only=True),
            InputWidgetTweaks_Color(alpha_preview=False),
        ],
        VarType.Path: [
            InputWidgetTweaks_Path(),
            InputWidgetTweaks_Path(show_helpmarker=False),
            InputWidgetTweaks_Path(read_only=True),
            InputWidgetTweaks_Path(path_type='folder'),
            InputWidgetTweaks_Path(path_filter='Workspace file (*.althwk){.althwk}, Text file (*.txt){.txt}'),
        ],
        VarType.List: [
            InputWidgetTweaks_List(item_type=VarType.Integer, tweaks=InputWidgetTweaks_Integer(enforce_range=True, min=1, max=42, increment=1), item_min=2, item_max=4),
            InputWidgetTweaks_List(item_type=VarType.Integer, tweaks=InputWidgetTweaks_Integer(show_helpmarker=False, enforce_range=True, min=1, max=42, increment=1), item_min=2, item_max=4),
            InputWidgetTweaks_List(read_only=True, item_type=VarType.Integer, tweaks=InputWidgetTweaks_Integer(read_only=True, enforce_range=True, min=1, max=42, increment=1), item_min=2, item_max=4),
            InputWidgetTweaks_List(item_type=VarType.Float, tweaks=InputWidgetTweaks_Float(enforce_range=True, min=0.0, max=4.2, increment=0.1), item_min=1, item_max=6),
            InputWidgetTweaks_List(item_type=VarType.Bool, tweaks=InputWidgetTweaks_Bool(button=True, button_true='On', button_false='Off'), item_min=1, item_max=6),
            InputWidgetTweaks_List(item_type=VarType.Bool, tweaks=InputWidgetTweaks_Bool(button=True, button_true='Load Thing', button_false='Do not Load'), item_min=1, item_max=6),
            InputWidgetTweaks_List(item_type=VarType.String, tweaks=InputWidgetTweaks_String(), item_min=1, item_max=6),
            InputWidgetTweaks_List(item_type=VarType.Path, tweaks=InputWidgetTweaks_Path(), item_min=1, item_max=6),
            InputWidgetTweaks_List(item_type=VarType.NormalizedColorRGB, tweaks=InputWidgetTweaks_Color(), item_min=1, item_max=3),
            InputWidgetTweaks_List(item_type=VarType.NormalizedColorRGBA, tweaks=InputWidgetTweaks_Color(), item_min=1, item_max=3),
        ],
        VarType.Table: [
            InputWidgetTweaks_Table(),
            InputWidgetTweaks_Table(show_helpmarker=False),
            InputWidgetTweaks_Table(read_only=True),
        ],
        VarType.Select: [
            InputWidgetTweaks_Select(),
            InputWidgetTweaks_Select(show_helpmarker=False),
            InputWidgetTweaks_Select(read_only=True),
        ],
        VarType.VarType: [
            InputWidgetTweaks_VarType(),
            InputWidgetTweaks_VarType(show_helpmarker=False),
            InputWidgetTweaks_VarType(read_only=True),
        ],
        VarType.Sheet: [
            InputWidgetTweaks_Sheet(),
            InputWidgetTweaks_Sheet(show_helpmarker=False),
            InputWidgetTweaks_Sheet(read_only=True),
            InputWidgetTweaks_Sheet(variant='Sheet'),
            InputWidgetTweaks_Sheet(variant='Function'),
        ],
    }

    def __init__(self) -> None:
        self.generate_config()
        super().__init__()

    def generate_param(self, param_key: str, vtype: VarType, tweak: InputWidgetTweaks) -> tuple[ConfigParameter, ConfigParameter]:
        """Generate a parameter entry, along with a comment displaying applied tweaks"""
        param_desc = str(tweak)
        value = None
        if isinstance(tweak, InputWidgetTweaks_String):
            # Populate string inputs with something to visualize
            if tweak.multiline:
                value = 'Chapter 1: I am Born\n It all began on a cold winter day.\n And by cold I mean the kind of day that\n made your fingers stop working.\n And it has been downhill from there.'
            else:
                value = 'Sample text!'

        if isinstance(tweak, InputWidgetTweaks_Select) and not isinstance(tweak, InputWidgetTweaks_VarType):
            # The default value for Select is intentionally empty list of options, and selected=None
            #   so we need to build a demo Select value ourselves
            value = Select([
                SelectOption(1, 'Option 1', 'The first option'),
                SelectOption(2, 'Option 2', 'The second option'),
                SelectOption(3, 'Option 3', 'The third option'),
            ], 1)
        tweak_desc = json.dumps(tweak.to_dict(), indent=4)
        param = ConfigParameter('Value', param_desc, param_key, vtype, value, tweak, comment=f'## Tweaks Applied for {vtype.name}\n```json\n' + tweak_desc + '\n```')

        return param

    def generate_config(self):
        """Generate config sections all input widget variations"""
        # first pass: header for each VarType, group for each tweak
        for vtype in VarType:
            if vtype in [VarType.Number, VarType.Any]:
                continue  # these types are only for use with Input IOPins
            section_name = f'VarType.{vtype.name}'
            section_desc = f'Testing variations on VarType.{vtype.name}'
            section_groups: list[ConfigGroup] = []

            vtype_lookup = vtype
            if vtype in [VarType.Vec2, VarType.Vec4]:
                vtype_lookup = VarType.Float

            if vtype_lookup in self.test_tweaks:
                tweaks_list = self.test_tweaks[vtype_lookup]
            else:
                tweaks_list = [InputWidgetTweaks(),]

            for idx, tweak in enumerate(tweaks_list):
                group_name = f'Tweak: {tweak.__class__.__name__} {idx}'
                group_desc = f'Tweak: {tweak.__class__.__name__} {idx} ({str(tweak)})'
                param_key = f'ByVarType.{section_name}.{group_name}.{idx}'
                param = self.generate_param(param_key, vtype, tweak)
                grp = ConfigGroup(group_name, group_desc, [param,])
                section_groups.append(grp)

            sct = ConfigSection(section_name, section_desc, section_groups)
            self.sections.append(sct)

        # Second pass: header for each tweak index (up to longest), group for each VarType
        longest_list = 0
        for vtype, tweaks in self.test_tweaks.items():
            if len(tweaks) > longest_list:
                longest_list = len(tweaks)
        for idx in range(0, longest_list):
            section_name = f'Tweak # {idx}'
            section_desc = f'Testing index {idx}'
            section_groups: list[ConfigGroup] = []
            for vtype in VarType:
                if vtype in [VarType.Number, VarType.Any]:
                    continue  # these types are only for use with Input IOPins
                tweak = None
                vtype_lookup = vtype
                if vtype in [VarType.Vec2, VarType.Vec4]:
                    vtype_lookup = VarType.Float
                if idx == 0 and vtype_lookup not in self.test_tweaks:
                    tweak = InputWidgetTweaks()
                if vtype_lookup in self.test_tweaks:
                    tweaks = self.test_tweaks[vtype_lookup]
                    if idx < len(tweaks):
                        tweak = tweaks[idx]
                if tweak is not None:
                    group_name = f'{vtype.name} - Tweak # {idx}'
                    group_desc = f'{vtype.name} - Tweak # {idx} ({str(tweak)})'
                    param_key = f'ByTweak.{section_name}.{group_name}.{idx}'
                    param = self.generate_param(param_key, vtype, tweak)
                    grp = ConfigGroup(group_name, group_desc, [param,])
                    section_groups.append(grp)

            sct = ConfigSection(section_name, section_desc, section_groups)
            self.sections.append(sct)
