"""
Althea - Node primitive classes

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

import enum

from dataclasses import dataclass
from typing import Any


from ..common import ed
from ..vartypes import VarType, get_vartype, NormalizedColorRGBA


# Sub-classed stuff from imgui_node_editor, so that we can expand upon them later

class PinKind(ed.PinKind):
    """Pin Kind"""


class PinId(ed.PinId):
    """Pin ID"""


class NodeId(ed.NodeId):
    """Node ID"""


class LinkId(ed.LinkId):
    """Link ID"""


@dataclass
class IOPin:
    """Represents an Input or Output pin, with metadata, and stores current value, link state"""
    # static, set at init
    label: str
    """Label for this I/O pin"""
    description: str
    """Description shown in tooltip when hovering over this pin"""
    io_type: VarType
    """Type of data accepted by this pin; links can only be made between compatible data types"""
    io_kind: IOKind
    """Kind of I/O: Input or Output"""

    # dynamic, set automatically
    node_id: NodeId = None
    """Unique, stable Node ID shared with IMGUI node editor backend"""
    pin_id: PinId = None
    """Unique, stable I/O Pin ID shared with IMGUI node editor backend"""

    # dynamic, set on-demand
    value: Any = None
    """Current actual value at this pin; if not linked, value will be None"""
    linked: bool = False
    """Current linked status of this pin; Output pins can be linked multiple times, but Input pins can only be linked once"""


class IOKind(enum.Enum):
    """IO Kind (Input or Output)"""
    Output = enum.auto()
    """Output Pin"""
    Input = enum.auto()
    """Input Pin"""


class NodeKind(enum.Enum):
    """Node Kind; controls how node calculation/execution is handled"""
    Simple = enum.auto()
    """execute() is static method, nothing fancy"""
    Static = enum.auto()
    """static value, no execute()"""
    Display = enum.auto()
    """only displays a value in UI, no execute()"""
    Script = enum.auto()
    """passes input to a python script, which is executed to output result, configurable number and type of ins and outs"""
    Special = enum.auto()
    """special node, requiring special attention"""


class NodeCalcStatus(enum.Enum):
    """Status of node calulations; used for nodes and sheets"""
    Idle = enum.auto()
    """No calculation is happening right now"""
    Processing = enum.auto()
    """Currently processing calculations (or queued)"""
    Success = enum.auto()
    """Calculation complete, and successful"""
    Warning = enum.auto()
    """Calculation complete, with warning, possibly still successful"""
    Error = enum.auto()
    """Calculation complete, but failed"""
    TimedOut = enum.auto()
    """Calculation took too long to complete, may be hung or lost"""


class LinkInfo:
    """Node Link"""
    id: LinkId
    """Unique, stable Link ID shared with IMGUI node editor backend"""
    input_id: PinId
    """ID of the input pin in this link"""
    input_node_id: NodeId
    """ID of the node providing the input pin in this link"""
    output_id: PinId
    """ID of the output pin in this link"""
    output_node_id: NodeId
    """ID of the node providing the output pin in this link"""
    io_type: VarType
    """Data type of this link; determines link color"""
    color: NormalizedColorRGBA = NormalizedColorRGBA(1.0, 1.0, 1.0, 1.0)
    """Current color of this link; defaults to white, but will be changed to follow VarType; color is not stored when persisting on disk, but selected at runtime"""

    def __init__(self, id_: LinkId, input_id: PinId, input_node_id: NodeId, output_id: PinId, output_node_id: NodeId, io_type: VarType, color: NormalizedColorRGBA = NormalizedColorRGBA(1.0, 1.0, 1.0, 1.0)) -> None:
        self.id = id_
        self.input_id = input_id
        self.input_node_id = input_node_id
        self.output_id = output_id
        self.output_node_id = output_node_id
        self.io_type = io_type
        self.color = color

    def get_dict(self) -> dict:
        """Get this link as a json serializable dict, to write to file"""
        data = {
            'id': self.id.id(),
            'var_type': self.io_type.name,
            'input_id': self.input_id.id(),
            'input_node_id': self.input_node_id.id(),
            'output_id': self.output_id.id(),
            'output_node_id': self.output_node_id.id(),
        }
        return data

    @staticmethod
    def from_dict(data: dict, color: NormalizedColorRGBA) -> LinkInfo:
        """Create a new instance of LinkInfo from the given data and color"""
        _required_keys = ['id', 'var_type', 'input_id', 'input_node_id', 'output_id', 'output_node_id']
        for keyname in _required_keys:
            if keyname not in data:
                raise KeyError(f'Missing required key: {keyname}')
        var_type = get_vartype(data['var_type'])
        return LinkInfo(LinkId(data['id']),
                        PinId(data['input_id']),
                        NodeId(data['input_node_id']),
                        PinId(data['output_id']),
                        NodeId(data['output_node_id']),
                        var_type, color
                        )


@dataclass
class WorkspaceSheetId:
    """ID for workspace sheet; styled to mimic the way IMGUI does NodeId, LinkId, PinId for consistency; These IDs are not shared with IMGUI"""
    _id: int

    def id(self) -> int:
        """Get id as integer"""
        return self._id
