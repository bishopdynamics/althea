"""
Althea - UI Widgets: fonts

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import enum

from pathlib import Path

import freetype

from imgui_bundle import imgui


class FontVariation(enum.Enum):
    """Font Variations"""
    Regular = enum.auto()
    Bold = enum.auto()
    Italic = enum.auto()
    BoldItalic = enum.auto()
    Thin = enum.auto()
    ThinItalic = enum.auto()
    MonoRegular = enum.auto()
    MonoBold = enum.auto()
    MonoItalic = enum.auto()
    MonoBoldItalic = enum.auto()
    MonoThin = enum.auto()
    MonoThinItalic = enum.auto()


class FontSize(enum.Enum):
    """Font Sizes"""
    Tiny = enum.auto()
    Small = enum.auto()
    Normal = enum.auto()
    Medium = enum.auto()
    Large = enum.auto()
    VeryLarge = enum.auto()
    Huge = enum.auto()
    Massive = enum.auto()


class FontPalette:
    """
    Fonts of all sizes and variations
        specify font_size_tiny (the smallest font), and font_size_increment;  all other sizes will be graduated at font_size_increment
        specify all_glyph_ranges=True to load all available glyphs from file, otherwise will load default glyph set

        Expects folder structure:
            fonts/
                FontName/
                    FontName-Regular.ttf
                    FontName-Bold.ttf
                    FontName-BoldItalic.ttf
                    FontName-Italic.ttf
                    FontName-Thin.ttf
                    FontName-ThinItalic.ttf
                    FontName-MonoRegular.ttf
                    FontName-MonoBold.ttf
                    FontName-MonoBoldItalic.ttf
                    FontName-MonoItalic.ttf
                    FontName-MonoThin.ttf
                    FontName-MonoThinItalic.ttf

        Any missing font variations will fallback to Regular
    """

    def __init__(self, base_path: Path = Path().cwd(), font_name: str = 'Roboto', font_size_increment: int = 4, font_size_tiny: int = 16,
                 all_glyph_ranges: bool = False) -> None:
        self.fonts: dict[FontSize, dict[FontVariation, imgui.ImFont]] = {}
        font_path = base_path.joinpath('fonts').joinpath(font_name)
        io = imgui.get_io()

        font_size_actual = font_size_tiny
        for font_size in FontSize:
            if font_size not in self.fonts:
                self.fonts[font_size] = {}
            for font_variation in FontVariation:
                font_filepath = font_path.joinpath(f'{font_name}-{font_variation.name}.ttf')
                if not font_filepath.is_file() and font_variation == FontVariation.Regular:
                    # At bare minimum, we require "Regular" variation, because will fallback to this variation if any others are not available
                    raise FileNotFoundError(f'Could not find Regular font file: {str(font_filepath)}')
                if font_filepath.is_file():
                    if all_glyph_ranges:
                        glyph_ranges = self.get_font_glyphs(font_filepath)
                        self.fonts[font_size][font_variation] = io.fonts.add_font_from_file_ttf(str(font_filepath), font_size_actual, None, glyph_ranges)
                    else:
                        self.fonts[font_size][font_variation] = io.fonts.add_font_from_file_ttf(str(font_filepath), font_size_actual)
            font_size_actual += font_size_increment

    @staticmethod
    def get_font_glyphs(font_path: Path) -> imgui.ImVector_uint:
        """Get a glyph ranges object of all available glyphs in the given font file"""
        # reference: https://github.com/ocornut/imgui/blob/master/docs/FONTS.md#using-custom-glyph-ranges
        builder = imgui.ImFontGlyphRangesBuilder()
        face = freetype.Face(str(font_path))
        for code, _glyph in face.get_chars():
            builder.add_text(chr(code))
        glyph_ranges = imgui.ImVector_uint()
        builder.build_ranges(glyph_ranges)
        return glyph_ranges

    def get(self, size: FontSize = FontSize.Normal, variation: FontVariation = FontVariation.Regular) -> imgui.ImFont:
        """
        Get a font by size and variation
            if variation is missing, will default to Regular
        """
        if size not in self.fonts:
            raise ValueError(f'Unexpected font size: {size.name}')
        if variation not in self.fonts[size]:
            return self.fonts[size][FontVariation.Regular]
        return self.fonts[size][variation]
