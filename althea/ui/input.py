"""
Althea - UI Widgets: input
    Widgets must be named following: InputWidget_[VarType] so that config editor can pick widgets automatically
"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import json

from typing import Any, Union, Literal
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from copy import deepcopy, copy

from inspect import isclass
from importlib import import_module

from imgui_bundle import imgui

from ..common import clamp
from ..vartypes import Vec2, Vec4, NormalizedColorRGBA, NormalizedColorRGB, VarType, Table, VarTypeDefaults, Select, SelectOption, IOPinInfo, collect_special_vartype_classes, get_vartype, get_vartype_default

from .base import Widget, HelpMarker, imfd, Button, UIException, global_text_editor
from .layout import HorizontalGroup, Padding, CollapsingHeader
from .ids import IDContext

from .primitives import TableContext, select_to_listbox


@dataclass
class InputWidgetTweaks:
    """Base Class for defining tweaks available for a specific input widget class"""
    show_helpmarker: bool = True
    """Show a (?) help marker on the right side of the widget, when hovered shows description tooltip"""
    read_only: bool = False
    """Make this input widget non-editable"""

    def __str__(self) -> str:
        """Render a string describing this set of tweaks and current values"""
        result: list[str] = []
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                if isinstance(value, str):
                    value = f'"{value}"'
                result.append(f'{key}: {value}')

        return ', '.join(result)

    def to_dict(self) -> str:
        """Get a serializable dict representing this set of tweaks and current values"""
        result: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                if isinstance(value, InputWidgetTweaks):
                    value = value.to_dict()
                else:
                    try:
                        _test = json.dumps({'val': value})
                    except Exception:
                        try:
                            value = str(value)
                        except Exception:
                            value = '(could not serialize)'
                result[key] = value
        return result


class InputWidget(Widget):
    """Base class for input widgets"""
    changed: bool
    value: Any
    tweaks = InputWidgetTweaks()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks = None) -> None:
        super().__init__()
        self.value = value
        self.label = label
        self.description = description
        if tweaks is not None:
            self.tweaks = tweaks
        self.changed = False

    def on_frame(self) -> tuple[bool, Any]:
        """Input Widgets on_frame() return tuple (changed, value)"""
        super().on_frame()
        if self.tweaks.show_helpmarker:
            imgui.same_line()
            HelpMarker(self.description).on_frame()
        return (self.changed, self.value)

    @abstractmethod
    def _draw(self):
        raise NotImplementedError


@dataclass
class InputWidgetTweaks_Fallback(InputWidgetTweaks):
    """Tweaks for the Fallback Widget"""
    # There are no special for this widget


class InputWidget_Fallback(InputWidget):
    """Read-Only Fallback widget that tries to display the value as as string"""
    tweaks = InputWidgetTweaks_Fallback()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Fallback = None) -> None:
        super().__init__(value, label, description, tweaks)
        try:
            self.value_str = str(value)
        except Exception:
            self.value_str = '(cannot be converted to string)'

    def _draw(self):
        with HorizontalGroup():
            imgui.text(self.value_str)
            imgui.same_line(250)
            imgui.text(self.label)
            imgui.same_line()


@dataclass
class InputWidgetTweaks_Bool(InputWidgetTweaks):
    """Tweaks for the Bool Widget"""
    button: bool = False
    """Display this value as a toggle button?"""
    button_true: str = 'True'
    """For button=True: button label when value=True"""
    button_false: str = 'False'
    """For button=True: button label when value=False"""


class InputWidget_Bool(InputWidget):
    """Input widget for editing a boolean value"""
    value: bool
    tweaks = InputWidgetTweaks_Bool()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Bool = None) -> None:
        super().__init__(value, label, description, tweaks)

    def _draw(self):
        if self.tweaks.read_only:
            if self.tweaks.button:
                if self.value:
                    value_str = self.tweaks.button_true + ' (True)'
                else:
                    value_str = self.tweaks.button_false + ' (False)'
            else:
                value_str = str(self.value)
            with HorizontalGroup():
                imgui.text(value_str)
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            if self.tweaks.button:
                if self.value:
                    if Button(self.tweaks.button_true):
                        self.value = False
                        self.changed = True
                    else:
                        self.changed = False
                else:
                    if Button(self.tweaks.button_false):
                        self.value = True
                        self.changed = True
                    else:
                        self.changed = False
                imgui.same_line(250)
                imgui.text(self.label)
            else:
                self.changed, self.value = imgui.checkbox(self.label, self.value)


class InputWidgetTweaks_String(InputWidgetTweaks):
    """Tweaks for the String Widget"""
    multiline: bool = False
    """For multi-line text, display a more suitable widget"""
    multiline_size: Vec2 = Vec2(250, 50)
    """For multiline=True: set the dimensions of the text input field"""
    secret: bool = False
    """Hide text input, for sensitive data like passwords"""
    noblank: bool = False
    """Require user to enter something"""
    allow_tab: bool = False
    """Allow user to use the tab key within text field (otherwise navigates to next field)"""
    code_editor: bool = False
    """Edit this text in a nice colorizing text editor"""
    code_language: Literal['none', 'python', 'angel_script', 'c', 'c_plus_plus', 'c_sharp', 'glsl', 'hlsl', 'json', 'lua'] = 'none'
    """For code_editor=True: set the language for syntax highlighting"""

    def __init__(self, show_helpmarker: bool = True, read_only: bool = False, multiline: bool = False, multiline_size: Vec2 = Vec2(250, 50), secret: bool = False, noblank: bool = False, allow_tab: bool = False, code_editor: bool = False, code_language: Literal['none', 'python', 'angel_script', 'c', 'c_plus_plus', 'c_sharp', 'glsl', 'hlsl', 'json', 'lua'] = 'none'):
        super().__init__(show_helpmarker, read_only)
        self.multiline = multiline
        self.multiline_size = multiline_size
        self.secret = secret
        self.noblank = noblank
        self.allow_tab = allow_tab
        self.code_editor = code_editor
        self.code_language = code_language


class InputWidget_String(InputWidget):
    """Input widget for editing a string value"""
    value: str
    tweaks = InputWidgetTweaks_String()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Fallback = None) -> None:
        super().__init__(value, label, description, tweaks)

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""
        flags = 0
        if self.tweaks.secret:
            flags |= imgui.InputTextFlags_.password.value
        if self.tweaks.noblank:
            flags |= imgui.InputTextFlags_.chars_no_blank.value
        if self.tweaks.allow_tab:
            flags |= imgui.InputTextFlags_.allow_tab_input.value
        if self.tweaks.read_only:
            flags |= imgui.InputTextFlags_.read_only.value
        return flags

    def _draw(self):
        if not self.tweaks.code_editor:
            if self.tweaks.multiline:
                self.changed, self.value = imgui.input_text_multiline(self.label, self.value, self.tweaks.multiline_size, self.craft_flags())
            else:
                if not self.tweaks.read_only:
                    self.changed, self.value = imgui.input_text(self.label, self.value, self.craft_flags())
                else:
                    imgui.text(self.value)
                    if self.label.strip() != '':
                        imgui.same_line(250)
                        imgui.text(self.label)
        else:
            # show a neat colorized text editor
            global_text_editor.set_language(self.tweaks.code_language)
            if self.value != global_text_editor.get_text():
                # only change text in editor if we need to
                global_text_editor.set_text(self.value)
            changed, newvalue = global_text_editor.on_frame()
            if changed:
                self.changed = True
                self.value = newvalue


@dataclass
class InputWidgetTweaks_Number(InputWidgetTweaks):
    """
    Common Input Widget tweaks for numbers
        Do not use this directly, sub-class it
    """
    enforce_range: bool = False
    """Require value to be within range defined by min and max"""
    min: Union[float, int] = 0
    """For enforce_range=True: minimum allowed value"""
    max: Union[float, int] = 2147483646  # NOTE: max 32bit value, only applied when enforce_range=True. we could say 0=infinite, but then we could not have a negative max
    """For enforce_range=True: maximum allowed value"""
    logarithmic: bool = False  # TODO this causes input widget to be unusable
    """Make widget value behave logarithmicly, otherwise linear"""


@dataclass
class InputWidgetTweaks_Integer(InputWidgetTweaks_Number):
    """Tweaks for the Integer Widget"""
    increment: int = 1
    """Value will increment by this value when dragged"""
    format: str = '%d'
    """Format string for displaying current value"""


class InputWidget_Integer(InputWidget):
    """Input widget for editing an integer value"""
    value: int
    tweaks = InputWidgetTweaks_Integer()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Integer = None) -> None:
        super().__init__(value, label, description, tweaks)

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""
        flags = 0
        if self.tweaks.enforce_range:
            flags |= imgui.SliderFlags_.always_clamp.value
        if self.tweaks.logarithmic:
            flags |= imgui.SliderFlags_.logarithmic.value
        return flags

    def _draw(self):
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(str(self.value))
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            self.changed, new_value = imgui.drag_int(self.label, self.value,
                                                     v_speed=self.tweaks.increment,
                                                     v_min=self.tweaks.min,
                                                     v_max=self.tweaks.max,
                                                     format=self.tweaks.format,
                                                     flags=self.craft_flags())
            if self.tweaks.enforce_range:
                new_value = clamp(new_value, self.tweaks.min, self.tweaks.max)
            self.value = new_value


@dataclass
class InputWidgetTweaks_Float(InputWidgetTweaks_Number):
    """Tweaks for the Float Widget"""
    round: bool = False
    """Round this value to specific number of digits after the decimal?"""
    round_digits: int = 0
    """For round=True: number of digits to round the value to"""
    increment: float = 1.0
    """Value will increment by this value when dragged"""
    format: str = '%.3f'
    """Format string for displaying current value"""


class InputWidget_Float(InputWidget):
    """Input widget for editing a floating point value"""
    value: float
    tweaks = InputWidgetTweaks_Float()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Float = None) -> None:
        super().__init__(value, label, description, tweaks)

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""
        flags = 0
        # NOTE: by default, the behavior is to round the returned value to match the accuracy displayed on the input widet
        #   we do not want that, so this flag is set
        flags |= imgui.SliderFlags_.no_round_to_format.value
        if self.tweaks.enforce_range:
            flags |= imgui.SliderFlags_.always_clamp.value
        if self.tweaks.logarithmic:
            flags |= imgui.SliderFlags_.logarithmic.value
        if self.tweaks.round:
            # If we are rounding, we need to round the increment as well
            #   but if rounding it makes increment 0, we need to shift a place and append a 1
            if '.' in str(self.tweaks.increment):
                inc_pre = str(self.tweaks.increment).split('.', maxsplit=1)[0]  # portion before decimal point
                inc_post = str(self.tweaks.increment).split('.')[1]  # portion after decimal point
                if int(inc_post) > 0:
                    inc_frac = float('0.' + inc_post)  # post-decimal, turned into 0.xxxxx f
                    while round(inc_frac, self.tweaks.round_digits) == 0:
                        inc_frac = float(str(inc_frac)[:-2] + '1')
                    self.tweaks.increment = float(inc_pre) + inc_frac
        return flags

    def _draw(self):
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(str(self.value))
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            self.changed, new_value = imgui.drag_float(self.label, self.value,
                                                       v_speed=self.tweaks.increment,
                                                       v_min=self.tweaks.min,
                                                       v_max=self.tweaks.max,
                                                       format=self.tweaks.format,
                                                       flags=self.craft_flags())
            if self.tweaks.enforce_range:
                new_value = clamp(new_value, self.tweaks.min, self.tweaks.max)
            if self.tweaks.round:
                new_value = round(new_value, self.tweaks.round_digits)
            self.value = new_value


class InputWidgetTweaks_Vec2(InputWidgetTweaks_Float):
    """Tweaks for the Vec2 Widget"""


class InputWidget_Vec2(InputWidget_Float):
    """Input widget for editing a Vec2 (two floats)"""
    value: Vec2
    tweaks = InputWidgetTweaks_Vec2()

    def _draw(self):
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(f'X: {self.value.x}, Y: {self.value.y}')
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            self.changed, newval = imgui.drag_float2(self.label, [self.value.x, self.value.y],
                                                     v_speed=self.tweaks.increment,
                                                     v_min=self.tweaks.min,
                                                     v_max=self.tweaks.max,
                                                     format=self.tweaks.format,
                                                     flags=self.craft_flags())
            if self.changed:
                self.value.x = newval[0]
                self.value.y = newval[1]


class InputWidgetTweaks_Vec4(InputWidgetTweaks_Float):
    """Tweaks for the Vec4 Widget"""


class InputWidget_Vec4(InputWidget_Float):
    """Input widget for editing a Vec4 (four floats)"""
    value: Vec4
    tweaks = InputWidgetTweaks_Vec4()

    def _draw(self):
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(f'X: {self.value.x}, Y: {self.value.y}, Z: {self.value.z}, W: {self.value.w}')
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            self.changed, newval = imgui.drag_float4(self.label, [self.value.x, self.value.y, self.value.z, self.value.w],
                                                     v_speed=self.tweaks.increment,
                                                     v_min=self.tweaks.min,
                                                     v_max=self.tweaks.max,
                                                     format=self.tweaks.format,
                                                     flags=self.craft_flags())
            if self.changed:
                self.value.x = newval[0]
                self.value.y = newval[1]
                self.value.z = newval[2]
                self.value.w = newval[3]


@dataclass
class InputWidgetTweaks_Color(InputWidgetTweaks):
    """Tweaks for the Color Widgets"""
    alpha_preview: bool = True
    """Show checkered background on half the preview, to visualize alpha value; has no effect on RGB color"""


class InputWidgetTweaks_NormalizedColorRGBA(InputWidgetTweaks_Color):
    """Tweaks for InputWidget_NormalizedColorRGBA"""


class InputWidget_NormalizedColorRGBA(InputWidget):
    """Input widget for editing a normalized RGBA color"""
    value: NormalizedColorRGBA
    tweaks: InputWidgetTweaks_NormalizedColorRGBA

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_NormalizedColorRGBA = InputWidgetTweaks_NormalizedColorRGBA()) -> None:
        super().__init__(value, label, description, tweaks)

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""
        flags = 0
        # NOTE: we do color exclusively as normalized floats internally
        #   if the user right-clicks on the widget, they can switch to other modes for input,
        #   but the final values are still normalized floats
        flags |= imgui.ColorEditFlags_.float.value
        if self.tweaks.alpha_preview:
            flags |= imgui.ColorEditFlags_.alpha_preview.value
        return flags

    def _draw(self):
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(str(self.value))
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            self.changed, float_list = imgui.color_edit4(self.label, self.value.to_list(), flags=self.craft_flags())
            self.value = NormalizedColorRGBA.from_list(float_list)


class InputWidgetTweaks_NormalizedColorRGB(InputWidgetTweaks_Color):
    """Tweaks for InputWidget_NormalizedColorRGB"""


class InputWidget_NormalizedColorRGB(InputWidget):
    """Input widget for editing a normalized RGB color"""
    value: NormalizedColorRGB
    tweaks: InputWidgetTweaks_NormalizedColorRGB

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_NormalizedColorRGB = InputWidgetTweaks_NormalizedColorRGB()) -> None:
        super().__init__(value, label, description, tweaks)

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""
        flags = 0
        # NOTE: we do color exclusively as normalized floats internally
        #   if the user right-clicks on the widget, they can switch to other modes for input,
        #   but the final values are still normalized floats
        flags |= imgui.ColorEditFlags_.float.value
        return flags

    def _draw(self):
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(str(self.value))
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            self.changed, float_list = imgui.color_edit3(self.label, self.value.to_list(), self.craft_flags())
            self.value = NormalizedColorRGB.from_list(float_list)


@dataclass
class InputWidgetTweaks_Path(InputWidgetTweaks):
    """Tweaks for the Path Widget"""
    path_type: Union[Literal['file', 'folder']] = 'file'
    """Type of path: file or folder"""
    path_filter: str = 'All files (*.*)'
    """
    Filter available files to select
        ex: 'Text file (*.txt){.txt}'
        ex: 'Workspace file (*.althwk){.althwk}, Text file (*.txt){.txt}'
    """


class InputWidget_Path(InputWidget):
    """Input widget for editing a filesystem path value"""
    value: Path
    tweaks = InputWidgetTweaks_Path()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Path = None) -> None:
        super().__init__(value, label, description, tweaks)
        self.dialog_context_id: str = ''

    def _draw(self):
        # NOTE: kind of a weird way to get a unique id for this dialog
        if self.dialog_context_id == '':
            with IDContext('SelectPath') as ctx_id:
                self.dialog_context_id = ctx_id
        if self.tweaks.read_only:
            with HorizontalGroup():
                imgui.text(str(self.value))
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            # handle completion of open file dialog
            self.changed = False
            if self.dialog_context_id != '':
                if imfd.is_done(self.dialog_context_id):
                    if imfd.has_result():
                        # the Path object returned by file dialog is... not pathlib.Path, its weird.
                        #   so we cast to string then to proper Path
                        self.value = Path(str(imfd.get_result()))
                        self.changed = True
                    imfd.close()
            imgui.text(str(self.value))
            if self.tweaks.path_type == 'file':
                title = 'Select File'
                filter_ = self.tweaks.path_filter
                if self.value.is_file():
                    str_value = str(self.value.parent)
                else:
                    str_value = str(self.value)
                if not filter_.endswith(','):
                    # NOTE: you must have a trailing comma, or it will mis-interpret the last specified extension pattern
                    filter_ += ','
            else:
                title = 'Select Folder'
                # NOTE: apparently an empty filter is how you say "only folders"
                filter_ = ''
                str_value = str(self.value)

            imgui.same_line()
            if Button('Select'):
                imfd.open(self.dialog_context_id, title, filter_, False, str_value)


class InputWidgetTweaks_Select(InputWidgetTweaks):
    """Tweaks for the Select Widget"""
    item_type: VarType = VarType.String
    """Actual VarType returned from selected item"""

    def __init__(self, show_helpmarker: bool = True, read_only: bool = False, item_type: VarType = VarType.String,
                 tweaks: InputWidgetTweaks = InputWidgetTweaks_String()):
        super().__init__(show_helpmarker=show_helpmarker, read_only=read_only)
        self.item_type = item_type
        self.tweaks = tweaks


class InputWidget_Select(InputWidget):
    """
    Special input widget for picking from a limited set of options
    """
    value: Select
    tweaks: InputWidgetTweaks_Select

    def __init__(self, value: Select, label: str, description: str, tweaks: InputWidgetTweaks_Select = InputWidgetTweaks_Select()) -> None:
        if tweaks is None:
            raise UIException('InputWidget_Select requires that you pass tweaks')
        if tweaks.item_type not in [VarType.Integer, VarType.Float, VarType.String, VarType.Bool]:
            raise UIException(f'InputWidget_Select does not support tweaks.item_type=VarType.{tweaks.item_type.name}')
        if not isinstance(value, Select):
            raise UIException('value should be a Select, not an int!')
        super().__init__(value, label, description, tweaks)

    def craft_flags(self) -> int:
        """Create flags for combo box"""
        flags = 0
        # flags |= imgui.ComboFlags_.no_preview.value
        return flags

    def craft_selectable_flags(self) -> int:
        """Create flags for items"""
        flags = 0
        # flags |= imgui.SelectableFlags_.allow_double_click.value
        return flags

    def _draw(self):
        if self.tweaks.read_only:
            # opts = [x.display for x in self.value.options]
            if self.value.selected is None:
                selected_display = 'None'
            else:
                sel = self.value.get_opt(self.value.selected)
                selected_display = sel.display
            with HorizontalGroup():
                imgui.text(f'Selected: {selected_display}')
                imgui.same_line(250)
                imgui.text(self.label)
                imgui.same_line()
        else:
            # TODO right now we just always report as changed
            #   this is because when a value is corrected from None, it still doesnt seem to get reported as chanced
            _changed, newvalue = select_to_listbox(self.label, self.value, flags=self.craft_flags(), item_flags=self.craft_selectable_flags())
            self.changed = True
            self.value = newvalue

    # pylint: disable=useless-parent-delegation
    def on_frame(self) -> tuple[bool, Select]:
        return super().on_frame()


class InputWidgetTweaks_VarType(InputWidgetTweaks_Select):
    """Tweaks for the VarType Widget"""
    skip_types: list[VarType] = []

    def __init__(self, show_helpmarker: bool = True, read_only: bool = False, item_type: VarType = VarType.String,
                 tweaks: InputWidgetTweaks = InputWidgetTweaks_String(), skip_types: list[VarType] = None):
        super().__init__(show_helpmarker=show_helpmarker, read_only=read_only, item_type=item_type, tweaks=tweaks)
        if skip_types is None:
            self.skip_types = []
        else:
            self.skip_types = skip_types


class InputWidget_VarType(InputWidget_Select):
    """A special Select input widget, for selecting a VarType"""
    value: Select
    tweaks: InputWidgetTweaks_VarType

    def __init__(self, value: str, label: str, description: str, tweaks: InputWidgetTweaks_VarType = InputWidgetTweaks_VarType()) -> None:
        if not isinstance(value, Select):
            var_opts = []
            for v in VarType:
                if v not in tweaks.skip_types:
                    var_opts.append(SelectOption(v.name, v.name, f'VarType: {v.name}'))
            value: Select = Select(var_opts, value)
        super().__init__(value, label, description, tweaks)


class InputWidgetTweaks_Sheet(InputWidgetTweaks_Select):
    """Tweaks for the Sheet Widget"""
    item_type: VarType = VarType.Integer
    """Actual VarType returned from selected item"""
    hide_active: bool = True
    """Do not include the currently active sheet in available options"""
    variant: Literal['Sheet', 'Function'] = 'Sheet'
    """Sheet variant"""

    def __init__(self, show_helpmarker: bool = True, read_only: bool = False, item_type: VarType = VarType.String,
                 tweaks: InputWidgetTweaks = InputWidgetTweaks_String(), hide_active: bool = True, variant: Literal['Sheet', 'Function'] = 'Sheet'):
        super().__init__(show_helpmarker=show_helpmarker, read_only=read_only, item_type=item_type, tweaks=tweaks)
        self.item_type = item_type
        self.hide_active = hide_active
        self.variant = variant


class InputWidget_Sheet(InputWidget_Select):
    """A special Select input widget, for selecting a WorkspaceSheet"""
    value: Select
    tweaks: InputWidgetTweaks_Sheet

    def __init__(self, value: Select, label: str, description: str, tweaks: InputWidgetTweaks_Sheet = InputWidgetTweaks_Sheet()) -> None:
        super().__init__(value, label, description, tweaks)


@dataclass
class InputWidgetTweaks_Table(InputWidgetTweaks):
    """Input widget tweaks for dataframes"""
    limit_rows: int = 0
    """For read_only: limit number of rows displayed"""
    limit_cols: int = 0
    """For read_only: limit number of cols displayed"""
    collapsible: bool = True
    """Place table under a collapsible header?"""
    width: int = 400
    """Table Width"""
    height: int = 200
    """Table Height"""


class InputWidget_Table(InputWidget):
    """Input widget for editing (or just viewing) an dataframe value"""
    value: Table
    tweaks = InputWidgetTweaks_Table()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_Table = None) -> None:
        super().__init__(value, label, description, tweaks)

    def _draw(self):
        if self.tweaks.collapsible:
            with CollapsingHeader(self.label, self.description) as opn:
                if opn:
                    self.draw_table()
        else:
            self.draw_table()

    def draw_table(self):
        """actually draw the table"""
        if not self.tweaks.read_only:
            if Button('Add Row'):
                self.value = self.value.add_row()
                self.changed = True
            imgui.same_line()
            if Button('Add Column'):
                self.value = self.value.add_column()
                self.changed = True

        num_cols = len(self.value.df.columns)
        num_rows = len(self.value.df.index)
        # first, create a header that can be editable
        if not self.tweaks.read_only:
            with TableContext(num_cols, size=Vec2(self.tweaks.width, 0)) as opn:
                if opn:
                    imgui.table_next_row()
                    for col in range(0, num_cols):
                        imgui.table_set_column_index(col)
                        col_name = self.value.df.columns[col]
                        this_tweaks = InputWidgetTweaks_String(
                            show_helpmarker=False,
                            read_only=self.tweaks.read_only)
                        changed, new_value = InputWidget_String(str(col_name), '', f'Name for column {col}', tweaks=this_tweaks).on_frame()
                        if changed:
                            new_table = self.value.rename_column(col_name, new_value)
                            self.value = new_table
                            self.changed = True

        # Then create the actual table, without a header
        num_cols = len(self.value.df.columns)
        num_rows = len(self.value.df.index)

        if self.tweaks.read_only and self.tweaks.limit_cols > 0:
            if num_cols > self.tweaks.limit_cols:
                num_cols = self.tweaks.limit_cols
        if self.tweaks.read_only and self.tweaks.limit_rows > 0:
            if num_rows > self.tweaks.limit_rows:
                num_rows = self.tweaks.limit_rows

        with TableContext(num_cols, size=Vec2(self.tweaks.width, self.tweaks.height)) as opn:
            if opn:
                if self.tweaks.read_only:
                    for col in range(0, num_cols):
                        col_name = self.value.df.columns[col]
                        imgui.table_setup_column(col_name)
                    imgui.table_headers_row()
                for row in range(0, num_rows):
                    imgui.table_next_row()
                    for col in range(0, num_cols):
                        imgui.table_set_column_index(col)
                        col_name = self.value.df.columns[col]
                        value = self.value.df.iloc[row][col_name]  # iloc now requires column name instead of index
                        this_tweaks = InputWidgetTweaks_String(
                            show_helpmarker=False,
                            read_only=self.tweaks.read_only)
                        changed, new_value = InputWidget_String(str(value), '', f'Cell: c: {col}, r: {row}', tweaks=this_tweaks).on_frame()
                        if changed:
                            self.value.df.iat[row, col] = new_value
                            self.changed = True


def display_table(table: Table, limit_rows: int = 8, limit_cols: int = 6, width: int = 400, height: int = 200):
    """Display a table for viewing, by using InputWidget_Table in read_only mode"""
    tweaks = InputWidgetTweaks_Table(read_only=True, show_helpmarker=False,
                                     collapsible=False, limit_rows=limit_rows, limit_cols=limit_cols,
                                     width=width, height=height)
    InputWidget_Table(table, '', 'Current value', tweaks=tweaks).on_frame()
    imgui.text(f'Data: {len(table.df.index)} rows x {len(table.df.columns)} columns')
    if len(table.df.index) > limit_rows or len(table.df.columns) > limit_cols:
        imgui.text(f'View limited to: {limit_rows} rows x {limit_cols} columns')


@dataclass
class InputWidgetTweaks_IOPinInfo(InputWidgetTweaks):
    """Tweaks for the IOPinInfo Widget"""
    edit_static_value: bool = False
    """
    For StaticValuesNode output pins only: allow user to input a static value for this pin
        This will cause another input widget to appear, based on io_type
            It is up to you to do something with this value, it is ignored by default
    """


class InputWidget_IOPinInfo(InputWidget):
    """Input widget for editing an IOPinInfo value"""
    value: IOPinInfo
    tweaks: InputWidgetTweaks_IOPinInfo
    _all_special_vartypes = collect_special_vartype_classes()
    static_value_skip_types = [VarType.Number, VarType.IOPinInfo, VarType.Select, VarType.VarType, VarType.Any, VarType.Sheet, VarType.Table]
    """Types to skip, if tweaks.edit_static_value=True"""

    def __init__(self, value: IOPinInfo, label: str, description: str, tweaks: InputWidgetTweaks_IOPinInfo = InputWidgetTweaks_IOPinInfo()) -> None:
        super().__init__(value, label, description, tweaks)
        self._all_widgets, self._all_widget_tweaks = collect_input_widgets()

    def craft_flags(self) -> int:
        """Create flags argument, depending on how tweaks are set"""
        flags = 0
        return flags

    def on_frame(self) -> tuple[bool, IOPinInfo]:
        return super().on_frame()

    def _draw(self):
        imgui.separator_text(self.label)

        # IO Type
        skip_types = []
        if self.tweaks.edit_static_value:
            skip_types = self.static_value_skip_types
        _io_type_changed, io_type_value = InputWidget_VarType(self.value.io_type.name, 'I/O Type', 'Type data provided or accepted by the pin', tweaks=InputWidgetTweaks_VarType(skip_types=skip_types)).on_frame()
        if io_type_value.selected != self.value.io_type.name:
            self.value.io_type = get_vartype(io_type_value.selected)
            self.value.static_value = get_vartype_default(self.value.io_type)
            self.changed = True

        # Label
        label_changed, label_value = InputWidget_String(self.value.label, 'Label', 'Label shown next to pin', tweaks=InputWidgetTweaks_String()).on_frame()
        if label_changed:
            self.value.label = label_value
            self.changed = True

        # Description
        description_changed, description_value = InputWidget_String(self.value.description, 'Description', 'Description of this pin, used in tooltip on hover', tweaks=InputWidgetTweaks_String()).on_frame()
        if description_changed:
            self.value.description = description_value
            self.changed = True

        # Static Value
        if self.tweaks.edit_static_value:
            # For StaticValuesNode only
            input_widget_class: type[InputWidget] = self._all_widgets['InputWidget_' + self.value.io_type.name]
            input_widget_tweaks: type[InputWidgetTweaks] = self._all_widget_tweaks['InputWidgetTweaks_' + self.value.io_type.name]
            if self.value.static_value is None:
                self.value.static_value = get_vartype_default(self.value.io_type)

            if input_widget_class.__name__ == 'InputWidget_List':
                existing_type = self.value.static_list_item_type
                more_skip_types = copy(self.static_value_skip_types)
                more_skip_types.extend([VarType.List,])
                _changed, ret_select = InputWidget_VarType(self.value.static_list_item_type.name, 'List item type', 'Type of items in this list',
                                                           tweaks=InputWidgetTweaks_VarType(skip_types=more_skip_types)).on_frame()
                chosen_list_type = get_vartype(ret_select.selected)

                if chosen_list_type != existing_type:
                    self.value.static_list_item_type = chosen_list_type
                    self.value.static_value = get_vartype_default(VarType.List)
                    self.changed = True

                this_tweaks = InputWidgetTweaks_List(item_type=self.value.static_list_item_type, tweaks=self._all_widget_tweaks['InputWidgetTweaks_' + self.value.static_list_item_type.name])
            else:
                this_tweaks = input_widget_tweaks()
            static_value_changed, static_value_value = input_widget_class(self.value.static_value, 'Static Value', 'Value to output on this pin', tweaks=this_tweaks).on_frame()
            if static_value_changed:
                self.value.static_value = static_value_value
                self.changed = True


def collect_input_widgets() -> tuple[dict[str, type[InputWidget]], dict[str, type[InputWidgetTweaks]]]:
    """iterate through the modules in this package"""
    all_widgets: dict[str, type[InputWidget]] = {}
    all_widget_tweaks: dict[str, type[InputWidgetTweaks]] = {}

    module = import_module(f"{__name__}")

    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)

        if isclass(attribute) and (issubclass(attribute, InputWidget) or issubclass(attribute, InputWidget_Select)):
            if attribute.__name__ not in ['InputWidget']:
                all_widgets[attribute_name] = attribute

        if isclass(attribute) and (issubclass(attribute, InputWidgetTweaks) or issubclass(attribute, InputWidgetTweaks_Select)):
            if attribute.__name__ not in ['InputWidgetTweaks']:
                all_widget_tweaks[attribute_name] = attribute
    return all_widgets, all_widget_tweaks


class InputWidgetTweaks_List(InputWidgetTweaks):
    """Tweaks for the List Widget"""
    item_type: VarType = VarType.String
    """The VarType of items in this list"""
    tweaks: InputWidgetTweaks = None
    """Tweaks to apply to item input widgets; must match item_type"""
    min: int = 0
    """Minimum required items in this list"""
    max: int = 0
    """Maximum allowed items in this list; 0 = unlimited"""

    def __init__(self, show_helpmarker: bool = True, read_only: bool = False, item_type: VarType = VarType.String,
                 tweaks: InputWidgetTweaks = None, item_min: int = 0, item_max: int = 0):
        super().__init__(show_helpmarker=show_helpmarker, read_only=read_only)
        if tweaks is None:
            raise UIException('For InputWidgetTweaks_List, the argument "tweaks" is mandatory and has no default value! You must supply tweaks compatible with given item_type')
        self.item_type = item_type
        self.tweaks = tweaks
        self.min = item_min
        self.max = item_max


class InputWidget_List(InputWidget):
    """
    Special input widget for creating homogenous list of another type
        NOTE: since tweaks are type-specific, no default tweak is provided; you MUST provide a tweaks arg
    """
    value: list
    tweaks: InputWidgetTweaks_List
    _all_widgets, _all_widget_tweaks = collect_input_widgets()
    _all_special_vartypes = collect_special_vartype_classes()

    def __init__(self, value: Any, label: str, description: str, tweaks: InputWidgetTweaks_List) -> None:
        if tweaks is None:
            raise UIException('InputWidget_List requires that you pass tweaks')
        if tweaks.item_type in [VarType.Any, VarType.Number, VarType.List]:
            raise UIException(f'InputWidget_List does not support item_type=VarType.{tweaks.item_type.name}')
        super().__init__(value, label, description, tweaks)

        # figure out correct InputWidget class to use
        widgetclassname = 'InputWidget_' + self.tweaks.item_type.name
        if widgetclassname not in self._all_widgets:
            raise UIException(f'Could not find expected widget class: {widgetclassname} for type: {self.tweaks.item_type.name}')
        self.widgetclass: InputWidget = self._all_widgets[widgetclassname]

        # Figure out default value (for when we add a new entry)
        if self.tweaks.item_type.name not in VarTypeDefaults:
            if self.tweaks.item_type.name not in self._all_special_vartypes:
                raise ValueError(f'VarType {self.tweaks.item_type.name} is missing from VarTypeDefaults and self._all_special_vartypes !')
            special_var_type = self._all_special_vartypes[self.tweaks.item_type.name]
            self.default = special_var_type.default()
        else:
            self.default = VarTypeDefaults[self.tweaks.item_type.name]

    def _draw(self):
        label_text = self.label + f' [List of {self.tweaks.item_type.name}s]'
        if self.tweaks.max > 0:
            label_text += f': {self.tweaks.min} - {self.tweaks.max} items'
        imgui.text(label_text)
        self.changed = False

        # if our value is currently less than required minimum, or larger than maximum, correct it
        current_value = deepcopy(self.value)
        while len(current_value) < self.tweaks.min:
            current_value.append(deepcopy(self.default))
            self.changed = True
        if self.tweaks.max > 0:
            while len(current_value) > self.tweaks.max:
                current_value.pop()
                self.changed = True

        with HorizontalGroup(mods=Padding(10)):
            if not self.tweaks.read_only:
                if len(current_value) >= self.tweaks.max and self.tweaks.max > 0:
                    imgui.text('Cannot add anymore items')
                else:
                    if Button('Add'):
                        if self.tweaks.max == 0 or len(current_value) < self.tweaks.max:
                            current_value.append(deepcopy(self.default))
                            self.changed = True
            # now draw an inputwidget for each

            for idx, this_value in enumerate(current_value):
                (changed, value) = self.widgetclass(this_value, self.label + f' ({idx})', self.description + f' (item # {idx + 1})', tweaks=self.tweaks.tweaks).on_frame()
                if isinstance(value, Select):
                    value = value.selected
                if changed:
                    self.changed = True

                should_check_value = True
                if idx >= self.tweaks.min:
                    if not self.tweaks.read_only:
                        imgui.same_line()
                        if Button('Remove'):
                            current_value.pop(idx)
                            self.changed = True
                            should_check_value = False

                if should_check_value:
                    if changed:
                        current_value[idx] = value
                if self.changed:
                    self.value = current_value
