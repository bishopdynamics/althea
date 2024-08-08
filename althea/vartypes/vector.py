"""
Althea - Special VarTypes: Vector

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from imgui_bundle import ImVec2, ImVec4

from ..common import ensure_serializable

from .base import SpecialVarType


class Vec2(ImVec2, SpecialVarType):
    """Two component floating-point vector with added math dunder methods"""

    def __init__(self, *args, **kwargs) -> None:
        ImVec2.__init__(self, *args, **kwargs)
        SpecialVarType.__init__(self)

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, other: Vec2) -> Vec2:
        return Vec2(self.x * other.x, self.y * other.y)

    @staticmethod
    def convert(other: ImVec2) -> Vec2:
        """Create Vec2 from an ImVec2"""
        return Vec2(other.x, other.y)

    @ensure_serializable
    def to_dict(self) -> dict[str, float]:
        return {'x': self.x, 'y': self.y}

    @staticmethod
    def from_dict(data: dict[str, float]) -> Vec2:
        return Vec2(data['x'], data['y'])

    @staticmethod
    def default() -> Vec2:
        return Vec2(0.0, 0.0)


class Vec4(ImVec4, SpecialVarType):
    """Four component floating-point vector with added math dunder methods"""

    def __init__(self, *args, **kwargs) -> None:
        ImVec4.__init__(self, *args, **kwargs)
        SpecialVarType.__init__(self)

    def __add__(self, other: Vec4) -> Vec4:
        return Vec4(self.x + other.x, self.y + other.y, self.z + other.z, self.w + other.w)

    def __sub__(self, other: Vec4) -> Vec4:
        return Vec4(self.x - other.x, self.y - other.y, self.z + other.z, self.w - other.w)

    def __mul__(self, other: Vec4) -> Vec4:
        return Vec4(self.x * other.x, self.y * other.y, self.z + other.z, self.w * other.w)

    @staticmethod
    def convert(other: ImVec4) -> Vec4:
        """Create Vec4 from an ImVec4"""
        return Vec4(other.x, other.y, other.z, other.w)

    @ensure_serializable
    def to_dict(self) -> dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z, 'w': self.w}

    @staticmethod
    def from_dict(data: dict[str, float]) -> Vec4:
        return Vec4(data['x'], data['y'], data['z'], data['w'])

    @staticmethod
    def default() -> Vec4:
        return Vec4(0.0, 0.0, 0.0, 0.0)


class Region(SpecialVarType):
    """Represents a rectangular region of something as two Vec2: top_left, and bottom_right"""
    top_left: Vec2
    bottom_right: Vec2

    def __init__(self, top_left: Vec2, bottom_right: Vec2) -> None:
        super().__init__()
        self.top_left = top_left
        self.bottom_right = bottom_right

    @ensure_serializable
    def to_dict(self) -> dict[str, float]:
        return {'top_left': self.top_left.to_dict(), 'bottom_right': self.bottom_right.to_dict()}

    @staticmethod
    def from_dict(data: dict[str, float]) -> Region:
        return Region(Vec2.from_dict(data['top_left']), Vec2.from_dict(data['bottom_right']))

    @staticmethod
    def default() -> Region:
        return Region(Vec2.default(), Vec2.default())
