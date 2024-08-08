"""
Althea - UI Widgets: base classes

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations


from typing import Literal
from abc import abstractmethod

from imgui_bundle import (
    imgui,
    im_file_dialog,  # pyright: ignore[reportMissingModuleSource]
)

from ..common import imgui_color_text_edit, imgui_md, ed
from ..vartypes import VarType, Vec2, NormalizedColorRGBA


from .ids import IDContext, GIDR
from .fonts import FontPalette, FontSize, FontVariation
from ..icons import MaterialIcons

# 20 distinct colors
DISTINCT_COLORS = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4', '#46f0f0', '#f032e6',
                   '#bcf60c', '#fabebe', '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', '#aaffc3',
                   '#808000', '#ffd8b1', '#000075', '#808080']

imfd = im_file_dialog.FileDialog.instance()
"""Global FileDialog Instance"""


class UIException(Exception):
    """Exception from UI subsystem"""


class UIState:
    """UI Runtime State"""

    def __init__(self) -> None:
        self.dialog = im_file_dialog.FileDialog.instance()
        """Global FileDialog Instance"""
        self.fonts: FontPalette = None
        """Available fonts"""
        self.iconfonts: FontPalette = None
        """Special fonts for icons"""
        self.vartype_colors: dict[VarType, NormalizedColorRGBA] = {}
        """Distinct Colors assigned to VarTypes"""
        self.id_registry = GIDR
        self.populate_colors()

    def populate_colors(self):
        """Populate colors for each VarType and Node Category by cycling through a list of distinct colors"""
        counter = 0
        for en in VarType:
            if en.name == 'Any':
                self.vartype_colors[en] = NormalizedColorRGBA(1.0, 1.0, 1.0, 1.0)
            else:
                self.vartype_colors[en] = NormalizedColorRGBA.from_hexstr(DISTINCT_COLORS[counter])
                counter += 1
                if counter >= len(DISTINCT_COLORS):
                    counter = 0

    def ensure_assets(self):
        """
        Ensure assets like fonts are loaded
            call this within runner_params.callbacks.load_additional_fonts to ensure imgui is ready for it
        """
        if self.fonts is None:
            self.fonts = FontPalette(font_name='Roboto')
        if self.iconfonts is None:
            self.iconfonts = FontPalette(font_name='MaterialIcons', all_glyph_ranges=True)


global_ui_state = UIState()
"""
Global instance of UI State
    You MUST call global_ui_state.ensure_assets() once imgui is in a state ready to load fonts
        suggestion: hello_imgui.RunnerParams.callbacks.load_additional_fonts
    You MUST also call global_ui_state.id_registry.reset() at the top of every frame, in order to reset the global ID registry
        suggestion: hello_imgui.RunnerParams.callbacks.before_imgui_render
        if you experience weird broken input widgets (cant interact with them), you probably missed this step
"""


# utilities

def estimate_text_size(text: str, size: FontSize = FontSize.Normal, variation: FontVariation = FontVariation.MonoRegular) -> Vec2:
    """Estimate dimensions of given text with given size and variation"""
    imgui.push_font(global_ui_state.fonts.get(size, variation))
    text_width = imgui.calc_text_size(text)
    imgui.pop_font()
    return Vec2.convert(text_width)


def estimate_icon_size(icon: MaterialIcons, size: FontSize = FontSize.Normal) -> Vec2:
    """Estimate the dimensions of an icon"""
    imgui.push_font(global_ui_state.iconfonts.get(size, FontVariation.Regular))
    text_width = imgui.calc_text_size(icon)
    imgui.pop_font()
    return Vec2.convert(text_width)


def get_canvas_origin() -> Vec2:
    """Get origin point (0,0) aka top left corner of canvas
        MUST be run between begin_node() and end_node() !!
    """
    window_min = Vec2.convert(imgui.get_window_content_region_min())
    origin_canvas = Vec2.convert(ed.screen_to_canvas(window_min))
    return origin_canvas


def get_view_center() -> Vec2:
    """Get the center of the current canvas view
        MUST be run between begin_node() and end_node() !!
    """
    screen_size = Vec2.convert(ed.get_screen_size())
    screen_center = Vec2(screen_size.x / 2, screen_size.y / 2)
    zoom = ed.get_current_zoom()
    center = Vec2(screen_center.x * zoom, screen_center.y * zoom)
    return center


# Drawing Basics

def draw_text(text_: str,
              size: FontSize = FontSize.Normal, variation: FontVariation = FontVariation.Regular,
              align: Literal['left', 'center', 'right'] = 'left', container_width: int = 100) -> int:
    """Draw text with a font and alignment"""
    imgui.push_font(global_ui_state.fonts.get(size, variation))
    text_width = imgui.calc_text_size(text_).x
    previous_x = imgui.get_cursor_pos_x()
    font_size = global_ui_state.fonts.get(size, variation).font_size
    match align:
        case 'center':
            imgui.set_cursor_pos_x(previous_x + ((container_width - text_width) * 0.5) - (font_size * 0.5))
        case 'right':
            # TODO: This doesnt work because container width will change as a result
            # imgui.set_cursor_pos_x(previous_x + (container_width - text_width) - (font_size * 1.2) + offset)
            pass
        case _:
            pass
    imgui.text(text_)
    # if align == 'right':
    #     imgui.set_cursor_pos_x(previous_x)
    imgui.pop_font()

    return text_width


def draw_icon(icon: MaterialIcons, color: NormalizedColorRGBA = None, size: FontSize = FontSize.Huge):
    """Draw given icon in given color"""
    if color is None:
        color = NormalizedColorRGBA(1, 1, 1, 1)
    imgui.push_font(global_ui_state.iconfonts.get(size, FontVariation.Regular))
    imgui.text_colored(color.to_imcolor(), icon)
    imgui.pop_font()


def draw_rectangle(dimensions: Vec2, color: NormalizedColorRGBA, filled: bool = True, rounding: float = 0.0, thickness: float = 1, flags: imgui.ImDrawFlags = 0):
    """Draw a rectangle"""
    origin = Vec2.convert(imgui.get_cursor_screen_pos())
    bottom_right = origin + dimensions
    # flags |= imgui.ImDrawFlags_.round_corners_all.value
    drawlist = imgui.get_window_draw_list()
    if filled:
        drawlist.add_rect_filled(origin, bottom_right, color.to_imu32(), rounding, flags)
    else:
        drawlist.add_rect(origin, bottom_right, color.to_imu32(), rounding, flags, thickness)


# interactivity

def Button(text_: str) -> bool:
    """Create a button, handling ids, and return a bool indicating if it has been clicked"""
    with IDContext('Button' + text_):
        clicked = imgui.button(text_)
    return clicked


# Layout

class Widget:
    """
    Base class for UI Widgets
        Automatically handles pushing a stable, unique id to the stack, so you dont have to care about ids
    """
    widget_name: str = 'Unknown'

    def __init__(self) -> None:
        self.widget_id: str = 'Unknown-0'
        """Widget unique id, uniquely assigned at frame time"""

    def on_frame(self):
        """Tasks to perform every frame"""
        with IDContext(self.widget_name) as wid:
            self.widget_id = wid
            self._draw()

    @abstractmethod
    def _draw(self):
        """
        Draw this widget
            Do NOT call this directly! call on_frame() instead!
        """
        raise NotImplementedError('Subclasses must implement this method!')


class HelpMarker(Widget):
    """A help marker (?) that displays tooltip with text on hover"""

    def __init__(self, tooltip: str) -> None:
        super().__init__()
        self.tooltip_text = tooltip

    def _draw(self):
        # TODO this should be a dope material icon instead
        imgui.text_disabled("(?)")
        if imgui.begin_item_tooltip():
            imgui.push_text_wrap_pos(imgui.get_font_size() * 35.0)
            imgui.text_unformatted(self.tooltip_text)
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()


class TextEditor:
    """Wrapper for imgui_color_text_edit.TextEditor"""

    def __init__(self):
        self.lang = 'none'
        self.editor = imgui_color_text_edit.TextEditor()
        self.editor.set_text('')
        self.editor.set_palette(imgui_color_text_edit.TextEditor.get_mariana_palette())

    def set_language(self, lang: Literal['none', 'python', 'angel_script', 'c', 'c_plus_plus', 'c_sharp', 'glsl', 'hlsl', 'json', 'lua'] = 'none'):
        """
        Set the programming language for this editor
            supported languages: ['none', 'python', 'angel_script', 'c', 'c_plus_plus', 'c_sharp', 'glsl', 'hlsl', 'json', 'lua']
        """
        match lang:
            case 'python':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.python())
            case 'angel_script':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.angel_script())
            case 'c':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.c())
            case 'c_plus_plus':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.c_plus_plus())
            case 'c_sharp':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.c_sharp())
            case 'glsl':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.glsl())
            case 'hlsl':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.hlsl())
            case 'json':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.json())
            case 'lua':
                self.editor.set_language_definition(imgui_color_text_edit.TextEditor.LanguageDefinition.lua())
            case 'none':
                pass
            case _:
                raise UIException(f'Unsupported code editor language: {lang}')
        self.lang = lang

    def set_text(self, text: str):
        """Set the text of this code editor"""
        self.editor.set_text(text)

    def get_text(self) -> str:
        """Get the text from this code editor"""
        return self.editor.get_text()

    def on_frame(self):
        """Render text editor, returning tuple of: changed:bool, value:str"""
        imgui.push_font(imgui_md.get_code_font())
        changed = self.editor.render("Code")
        value = self.get_text()
        imgui.pop_font()
        return (changed, value)


global_text_editor = TextEditor()
"""
Global text editor instance, because you only want to create it once!
    usage:
        global_text_editor.set_text('print("hello world")')

        global_text_editor.set_language('python')
        
        changed, newvalue = global_text_editor.on_frame()
"""


class CursorPosition:
    """Context handler which overrides (or offsets) the current cursor position on enter, and puts it back on exit"""

    def __init__(self, pos: Vec2 = None, x: int = None, y: int = None, offset: bool = False) -> None:
        self.previous_cursor = Vec2.convert(imgui.get_cursor_screen_pos())
        if pos is not None:
            # override / offset entire position
            if offset:
                self.new_cursor = self.previous_cursor + pos
            else:
                self.new_cursor = pos
        else:
            # override  / offset only x or y
            self.new_cursor = self.previous_cursor
            if offset:
                if x is not None:
                    self.new_cursor.x += x
                if y is not None:
                    self.new_cursor.y += y
            else:
                if x is not None:
                    self.new_cursor.x = x
                if y is not None:
                    self.new_cursor.y = y

    def __enter__(self) -> Vec2:
        imgui.set_cursor_screen_pos(self.new_cursor)
        return self.new_cursor

    def __exit__(self, _type, _value, _traceback):
        imgui.set_cursor_screen_pos(self.previous_cursor)
