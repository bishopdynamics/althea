"""
Althea - Special VarTypes: Color

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from abc import abstractmethod
from typing import Union

from imgui_bundle import IM_COL32

from ..common import clamp, ensure_serializable

from .base import SpecialVarType, VarTypeException
from .vector import Vec4

INT_MAX_5BIT = 31.0
INT_MAX_6BIT = 127.0
INT_MAX_8BIT = 255.0
INT_MAX_16BIT = 65_535.0
INT_MAX_32BIT = 4_294_967_295.0


class _Color_RGBA(SpecialVarType):
    """RGBA Color base class"""
    r: Union[int, float]
    """Red component"""
    g: Union[int, float]
    """Green component"""
    b: Union[int, float]
    """Blue component"""
    a: Union[int, float]
    """Alpha component"""

    def __init__(self, r: Union[int, float], g: Union[int, float], b: Union[int, float], a: Union[int, float]):
        super().__init__()
        self.r = r
        self.g = g
        self.b = b
        self.a = a
        self._check_vals()

    @abstractmethod
    def _check_vals(self):
        """check that init values are sane"""
        raise NotImplementedError('subclasses must implement this method!')

    def __str__(self) -> str:
        return ', '.join(f'{str(key).upper()}: {val}' for key, val in self.to_dict().items())

    @ensure_serializable
    def to_dict(self) -> dict:
        return {'r': self.r, 'g': self.g, 'b': self.b, 'a': self.a}

    @staticmethod
    def from_dict(data: dict) -> _Color_RGBA:
        raise NotImplementedError('Sub-classes must implement this method!')

    def to_list(self) -> list[Union[int, float]]:
        """Get this color as a list of four values"""
        return [self.r, self.g, self.b, self.a]

    @staticmethod
    def from_list(data: Union[list[int], list[float]]) -> _Color_RGBA:
        """Create a color from a list of four values"""
        raise NotImplementedError('Sub-classes must implement this method!')


class _Color_RGB(SpecialVarType):
    """RGB Color base class (no alpha)"""
    r: Union[int, float]
    """Red component"""
    g: Union[int, float]
    """Green component"""
    b: Union[int, float]
    """Blue component"""

    def __init__(self, r: Union[int, float], g: Union[int, float], b: Union[int, float]):
        super().__init__()
        self.r = r
        self.g = g
        self.b = b
        self._check_vals()

    @abstractmethod
    def _check_vals(self):
        """check that init values are sane"""
        raise NotImplementedError('subclasses must implement this method!')

    def __str__(self) -> str:
        return ', '.join(f'{str(key).upper()}: {val}' for key, val in self.to_dict().items())

    @ensure_serializable
    def to_dict(self) -> dict:
        return {'r': self.r, 'g': self.g, 'b': self.b}

    @staticmethod
    def from_dict(data: dict) -> _Color_RGB:
        raise NotImplementedError('Sub-classes must implement this method!')

    def to_list(self) -> list[Union[int, float]]:
        """Get this color as a list of three values"""
        return [self.r, self.g, self.b]

    @staticmethod
    def from_list(data: Union[list[int], list[float]]) -> _Color_RGB:
        """Create a color from a list of three values"""
        raise NotImplementedError('Sub-classes must implement this method!')


class Color_RGBA_8888(_Color_RGBA):
    """RGBA Color as 4 8-bit ints (32-bits)"""
    r: int
    """Red component"""
    g: int
    """Green component"""
    b: int
    """Blue component"""
    a: int
    """Alpha component"""

    def _check_vals(self):
        """check that init values are sane"""
        for v in [self.r, self.g, self.b, self.a]:
            if v > INT_MAX_8BIT or v < 0:
                raise VarTypeException(f'Color values must be between 0 and {INT_MAX_8BIT}, got value: {v}')

    @staticmethod
    def from_dict(data: dict) -> Color_RGBA_8888:
        return Color_RGBA_8888(data['r'], data['g'], data['b'], data['a'])

    @staticmethod
    def default() -> Color_RGBA_8888:
        return Color_RGBA_8888(255, 255, 255, 255)

    @staticmethod
    def from_list(data: list[int]) -> Color_RGBA_8888:
        return Color_RGBA_8888(data[0], data[1], data[2], data[3])


class Color_RGB_888(_Color_RGB):
    """RGBA Color as 3 8-bit ints (no alpha) (24-bits)"""
    r: int
    """Red component"""
    g: int
    """Green component"""
    b: int
    """Blue component"""

    def _check_vals(self):
        """check that init values are sane"""
        for v in [self.r, self.g, self.b]:
            if v > INT_MAX_8BIT or v < 0:
                raise VarTypeException(f'Color values must be between 0 and {INT_MAX_8BIT}, got value: {v}')

    @staticmethod
    def from_dict(data: dict) -> Color_RGB_888:
        return Color_RGB_888(data['r'], data['g'], data['b'])

    @staticmethod
    def default() -> Color_RGB_888:
        return Color_RGB_888(255, 255, 255)

    @staticmethod
    def from_list(data: list[int]) -> Color_RGB_888:
        return Color_RGB_888(data[0], data[1], data[2])


class Color_RGBA_5658(_Color_RGBA):
    """RGBA Color as 4 ints, R: 5-bits, G: 6-bits, B: 5-bits, A: 8-bits (24-bits)"""
    r: int
    """Red component"""
    g: int
    """Green component"""
    b: int
    """Blue component"""
    a: int
    """Alpha component"""

    def _check_vals(self):
        """check that init values are sane"""
        if self.r > INT_MAX_5BIT or self.r < 0:
            raise VarTypeException(f'Color red value must be between 0 and {INT_MAX_5BIT}, got value: {self.r}')
        if self.g > INT_MAX_6BIT or self.g < 0:
            raise VarTypeException(f'Color green value must be between 0 and {INT_MAX_6BIT}, got value: {self.g}')
        if self.b > INT_MAX_5BIT or self.b < 0:
            raise VarTypeException(f'Color blue value must be between 0 and {INT_MAX_5BIT}, got value: {self.b}')
        if self.a > INT_MAX_8BIT or self.a < 0:
            raise VarTypeException(f'Color alpha value must be between 0 and {INT_MAX_8BIT}, got value: {self.a}')

    @staticmethod
    def from_dict(data: dict) -> Color_RGBA_5658:
        return Color_RGBA_5658(data['r'], data['g'], data['b'], data['a'])

    @staticmethod
    def default() -> Color_RGBA_5658:
        return Color_RGBA_5658(31, 127, 31, 255)

    @staticmethod
    def from_list(data: list[int]) -> Color_RGBA_5658:
        return Color_RGBA_5658(data[0], data[1], data[2], data[3])


class Color_RGB_565(_Color_RGB):
    """RGBA Color as 3 ints, R: 5-bits, G: 6-bits, B: 5-bits (no alpha) (16-bits)"""
    r: int
    """Red component"""
    g: int
    """Green component"""
    b: int
    """Blue component"""

    def _check_vals(self):
        """check that init values are sane"""
        if self.r > INT_MAX_5BIT or self.r < 0:
            raise VarTypeException(f'Color red value must be between 0 and {INT_MAX_5BIT}, got value: {self.r}')
        if self.g > INT_MAX_6BIT or self.g < 0:
            raise VarTypeException(f'Color green value must be between 0 and {INT_MAX_6BIT}, got value: {self.g}')
        if self.b > INT_MAX_5BIT or self.b < 0:
            raise VarTypeException(f'Color blue value must be between 0 and {INT_MAX_5BIT}, got value: {self.b}')

    @staticmethod
    def from_dict(data: dict) -> Color_RGB_565:
        return Color_RGB_565(data['r'], data['g'], data['b'])

    @staticmethod
    def default() -> Color_RGB_565:
        return Color_RGB_565(31, 127, 31)

    @staticmethod
    def from_list(data: list[int]) -> Color_RGB_565:
        return Color_RGB_565(data[0], data[1], data[2])


class NormalizedColorRGBA(_Color_RGBA):
    """RGBA Color as 4 normalized floats"""
    r: float
    """Red component"""
    g: float
    """Green component"""
    b: float
    """Blue component"""
    a: float
    """Alpha component"""

    def _check_vals(self):
        """check that init values are sane"""
        for v in [self.r, self.g, self.b, self.a]:
            if v > 1.0 or v < 0.0:
                raise VarTypeException(f'Color values must be between 0.0 and 1.0, got value: {v}')

    @staticmethod
    def default() -> NormalizedColorRGBA:
        return NormalizedColorRGBA(1.0, 1.0, 1.0, 1.0)

    @staticmethod
    def from_dict(data: dict) -> NormalizedColorRGBA:
        return NormalizedColorRGBA(data['r'], data['g'], data['b'], data['a'])

    @staticmethod
    def from_list(data: list[float]) -> NormalizedColorRGBA:
        return NormalizedColorRGBA(data[0], data[1], data[2], data[3])

    def to_imcolor(self) -> Vec4:
        """Get this color as a Vec4 object that imgui will accept"""
        return Vec4(self.r, self.g, self.b, self.a)

    def to_imu32(self) -> IM_COL32:
        """Get this color as IMU32 (4 8bit ints)"""
        return IM_COL32(int(self.r * INT_MAX_8BIT), int(self.g * INT_MAX_8BIT), int(self.b * INT_MAX_8BIT), int(self.a * INT_MAX_8BIT))

    def to_rgba_8888(self) -> Color_RGBA_8888:
        """Get this color in 8bit RGBA integer form"""
        return Color_RGBA_8888(int(self.r * INT_MAX_8BIT), int(self.g * INT_MAX_8BIT), int(self.b * INT_MAX_8BIT), int(self.a * INT_MAX_8BIT))

    def to_rgba_5658(self) -> Color_RGBA_5658:
        """Get this color in 5658 RGBA integer form"""
        return Color_RGBA_5658(int(self.r * INT_MAX_5BIT), int(self.g * INT_MAX_6BIT), int(self.b * INT_MAX_5BIT), int(self.a * INT_MAX_8BIT))

    def to_hex_str(self) -> str:
        """Get this color as a hex string like: #04F2A8"""
        color_rgbint = self.to_rgba_8888()
        return "#{0:02x}{1:02x}{2:02x}".format(clamp(color_rgbint.r, 0, INT_MAX_8BIT), clamp(color_rgbint.g, 0, INT_MAX_8BIT), clamp(color_rgbint.b, 0, INT_MAX_8BIT))

    @staticmethod
    def from_hexstr(hex_color: str) -> NormalizedColorRGBA:
        """Create a NormalizedColorRGBA from a hex string color like: #04F2A8 or 04F2A8"""
        if hex_color.startswith('#'):
            hex_color = hex_color.removeprefix('#')
        rgb = []
        for i in (0, 2, 4):
            decimal = int(hex_color[i:i+2], 16)
            rgb.append(decimal)

        return NormalizedColorRGBA(rgb[0] / INT_MAX_8BIT, rgb[1] / INT_MAX_8BIT, rgb[2] / INT_MAX_8BIT, 1.0)

    @staticmethod
    def from_rgba_8888(rgb_color: Color_RGBA_8888) -> NormalizedColorRGBA:
        """Create a NormalizedColorRGBA from Color_RGBA_8888"""
        return NormalizedColorRGBA(rgb_color.r / INT_MAX_8BIT, rgb_color.g / INT_MAX_8BIT, rgb_color.b / INT_MAX_8BIT, rgb_color.a / INT_MAX_8BIT)

    @staticmethod
    def from_rgba_5658(rgb_color: Color_RGBA_5658) -> NormalizedColorRGBA:
        """Create a NormalizedColorRGBA from Color_RGBA_5658"""
        return NormalizedColorRGBA(rgb_color.r / INT_MAX_5BIT, rgb_color.g / INT_MAX_6BIT, rgb_color.b / INT_MAX_5BIT, rgb_color.a / INT_MAX_8BIT)


class NormalizedColorRGB(_Color_RGB):
    """RGBA Color as 3 normalized floats"""
    r: float
    """Red component"""
    g: float
    """Green component"""
    b: float
    """Blue component"""

    def _check_vals(self):
        """check that init values are sane"""
        for v in [self.r, self.g, self.b]:
            if v > 1.0 or v < 0.0:
                raise VarTypeException(f'Color values must be between 0.0 and 1.0, got value: {v}')

    @staticmethod
    def default() -> NormalizedColorRGB:
        return NormalizedColorRGB(1.0, 1.0, 1.0)

    @staticmethod
    def from_dict(data: dict) -> NormalizedColorRGB:
        return NormalizedColorRGB(data['r'], data['g'], data['b'])

    @staticmethod
    def from_list(data: list[float]) -> NormalizedColorRGB:
        return NormalizedColorRGB(data[0], data[1], data[2])

    def to_imcolor(self) -> Vec4:
        """Get this color as a Vec4 object that imgui will accept (alpha 1.0)"""
        return Vec4(self.r, self.g, self.b, 1.0)

    def to_imu32(self) -> IM_COL32:
        """Get this color as IMU32 (4 8bit ints)"""
        return IM_COL32(int(self.r * INT_MAX_8BIT), int(self.g * INT_MAX_8BIT), int(self.b * INT_MAX_8BIT), int(INT_MAX_8BIT))

    def to_rgb_888(self) -> Color_RGB_888:
        """Get this color in 8bit RGB integer form"""
        return Color_RGB_888(int(self.r * INT_MAX_8BIT), int(self.g * INT_MAX_8BIT), int(self.b * INT_MAX_8BIT))

    def to_rgb_565(self) -> Color_RGB_565:
        """Get this color in 565 RGB integer form"""
        return Color_RGB_565(int(self.r * INT_MAX_5BIT), int(self.g * INT_MAX_6BIT), int(self.b * INT_MAX_5BIT))

    def to_hex_str(self) -> str:
        """Get this color as a hex string like: #04F2A8"""
        color_rgbint = self.to_rgb_888()
        return "#{0:02x}{1:02x}{2:02x}".format(clamp(color_rgbint.r, 0, INT_MAX_8BIT), clamp(color_rgbint.g, 0, INT_MAX_8BIT), clamp(color_rgbint.b, 0, INT_MAX_8BIT))

    @staticmethod
    def from_hexstr(hex_color: str) -> NormalizedColorRGB:
        """Create a NormalizedColorRGB from a hex string color like: #04F2A8 or 04F2A8"""
        if hex_color.startswith('#'):
            hex_color = hex_color.removeprefix('#')
        rgb = []
        for i in (0, 2, 4):
            decimal = int(hex_color[i:i+2], 16)
            rgb.append(decimal)

        return NormalizedColorRGB(rgb[0] / INT_MAX_8BIT, rgb[1] / INT_MAX_8BIT, rgb[2] / INT_MAX_8BIT)

    @staticmethod
    def from_rgb_888(rgb_color: Color_RGB_888) -> NormalizedColorRGB:
        """Create a NormalizedColorRGB from Color_RGB_888"""
        return NormalizedColorRGB(rgb_color.r / INT_MAX_8BIT, rgb_color.g / INT_MAX_8BIT, rgb_color.b / INT_MAX_8BIT)

    @staticmethod
    def from_rgb_565(rgb_color: Color_RGB_565) -> NormalizedColorRGB:
        """Create a NormalizedColorRGB from Color_RGB_565"""
        return NormalizedColorRGB(rgb_color.r / INT_MAX_5BIT, rgb_color.g / INT_MAX_6BIT, rgb_color.b / INT_MAX_5BIT)
