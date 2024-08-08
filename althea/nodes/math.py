"""
Althea - Node implementations, Math

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from ..config import ConfigParameter, ConfigGroup, ConfigSection

from ..vartypes import VarType

from .primitives import IOPin, IOKind, NodeKind
from .base import Node, NodeException
from .config import NodeConfig, CommonNodeConfig

if TYPE_CHECKING:
    from . import state


class Node_Math(Node):
    """Base class for nodes which do math"""
    node_category = 'Math'
    node_subcategory = 'General'

    @staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        raise NotImplementedError('Node subclass did not implement method execute() !')


class Node_SimpleMath(Node_Math):
    """Base class for nodes which do simple math"""
    node_subcategory = 'Simple'

    @staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        raise NotImplementedError('Node subclass did not implement method execute() !')


class Node_Math_Add(Node_SimpleMath):
    """A node which adds two numbers (int/float), outputting the result"""
    node_kind = NodeKind.Simple
    node_display = 'Add'
    node_desc = 'Add two numbers'
    inputs = [
        IOPin('A', 'Value A', VarType.Number, IOKind.Input),
        IOPin('B', 'Value B', VarType.Number, IOKind.Input),
    ]
    outputs = [
        IOPin('Sum', 'Sum of input values', VarType.Number, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('MathNode Config', 'Configuration for MathNode', [
                ConfigGroup('General', 'General configuration', []),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list[Union[float, int]], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        return [inputs[0] + inputs[1]]


class Node_Math_Subtract(Node_SimpleMath):
    """A node which subtracts two numbers (int/float), outputting the result"""
    node_kind = NodeKind.Simple
    node_display = 'Subtract'
    node_desc = 'Subtract second number from the first'
    inputs = [
        IOPin('A', 'Value A', VarType.Number, IOKind.Input),
        IOPin('B', 'Value B', VarType.Number, IOKind.Input),
    ]
    outputs = [
        IOPin('Difference', 'Difference between input values', VarType.Number, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('MathNode Config', 'Configuration for MathNode', [
                ConfigGroup('General', 'General configuration', []),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list[Union[float, int]], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        return [inputs[0] - inputs[1]]


class Node_Math_Multiply(Node_SimpleMath):
    """A node which multiplies two numbers (int/float), outputting the result"""
    node_kind = NodeKind.Simple
    node_display = 'Multiply'
    node_desc = 'Multiply two numbers'
    inputs = [
        IOPin('A', 'Value A', VarType.Number, IOKind.Input),
        IOPin('B', 'Value B', VarType.Number, IOKind.Input),
    ]
    outputs = [
        IOPin('Product', 'Product of input values', VarType.Number, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('MathNode Config', 'Configuration for MathNode', [
                ConfigGroup('General', 'General configuration', []),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list[Union[float, int]], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        return [inputs[0] * inputs[1]]


class Node_Math_Invert(Node_SimpleMath):
    """A node which inverts a number (multiply by -1) outputting the result"""
    node_kind = NodeKind.Simple
    node_display = 'Invert'
    node_desc = 'Invert a number'
    inputs = [
        IOPin('Value', 'Value', VarType.Number, IOKind.Input),
    ]
    outputs = [
        IOPin('Inverted', 'Inverted value', VarType.Number, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('MathNode Config', 'Configuration for MathNode', [
                ConfigGroup('General', 'General configuration', []),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list[Union[float, int]], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        return [inputs[0] * -1]


class Node_Math_Divide(Node_SimpleMath):
    """A node which divides two numbers (int/float), outputting the result"""
    node_kind = NodeKind.Simple
    node_display = 'Divide'
    node_desc = 'Divides first number by the second'
    inputs = [
        IOPin('Dividend', 'Value to be divided', VarType.Number, IOKind.Input),
        IOPin('Divisor', 'Value to divide by', VarType.Number, IOKind.Input),
    ]
    outputs = [
        IOPin('Quotient', 'Result of division', VarType.Float, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('MathNode Config', 'Configuration for MathNode', [
                ConfigGroup('General', 'General configuration', []),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list[Union[float, int]], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        if inputs[1] == 0:
            raise NodeException('Cannot divide by 0!')
        return [inputs[0] / inputs[1]]


class Node_Math_Round(Node_Math):
    """A node which rounds a number (int/float), outputting the result"""
    # NOTE: imgui input widget for floats has configuration for floating point accuracy and rounding
    #   that needs to be properly configured (it should already be by default)
    #   or unexpected rounding may happen before we ever enter reach this node
    node_kind = NodeKind.Simple
    node_display = 'Round'
    node_desc = 'Round a number'
    inputs = [
        IOPin('Value', 'Input Value', VarType.Number, IOKind.Input),
    ]
    outputs = [
        IOPin('Sum', 'Rounded value', VarType.Number, IOKind.Output),
    ]

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('MathNode Config', 'Configuration for MathNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Places', 'Round to N places after the decimal place', 'places', VarType.Integer, 2),
                ]),
            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list[Union[float, int]], config: NodeConfig, common_config: CommonNodeConfig) -> list[Union[int, float]]:
        places: int = config.get('places')
        return [round(inputs[0], places)]
