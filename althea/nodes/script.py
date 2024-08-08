"""
Althea - Node implementations: Python Script

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

# Reference: https://restrictedpython.readthedocs.io/en/latest/usage/policy.html#implementing-a-policy

# NOTE: RestrictedPython helps enforce a lot of restrictions upon scripts to be executed,
#   however those restrictions are... restrictive. As such, many of these restrictions have been undone in the name of more interesting functionality
#   if you wish to make script execution slightly safer (it will always be a little risky), you can re-apply restrictions as needed
#       the majority of this is undone via: LessRestrictingNodeTransformer, details are clearly commented there
#       there are also 4 methods in ScriptManager that should be scrutinized when tightening up restrictions:
#           _safe_import    - restrict allowed imports
#           _unsafe_write   - restrict writing to some objects/files/etc
#           _apply          - restrict access to args and kwargs
#           _inplacevar     - restrict usage in-place operators, such as +=

from __future__ import annotations

from ..vartypes import VarType
from ..config import ConfigGroup, ConfigSection, ConfigParameter
from ..ui import InputWidgetTweaks_String

from ..scriptrunner import SAFE_SCRIPT_MODULES

from .primitives import NodeKind
from .base import Node
from .config import NodeConfig, CommonNodeConfig


# pretty version of allowed modules
PRETTY_SAFE_MODULES = ''
for smod in SAFE_SCRIPT_MODULES:
    PRETTY_SAFE_MODULES += f'\n\t* `{smod}`'

# Instructions shown above text editor for script, in markdown format
NODE_PY_SCRIPT_COMMENT = f"""
## Python Script
### Instructions:
* Inputs available via global var:
    * `inputs[]`
* Append outputs to global var:
    * `outputs[]`
    * You must append output values in the expected order
* Write log messages using:
    * `log.debug()`
    * `log.info()`
    * `log.warning()`
    * `log.error()`
* Raised exceptions will be caught, traced, and logged
    * enable CalcJob Traces in App Config to see full stack traces in the log
* The following modules are allowed to be imported in your script:
    {PRETTY_SAFE_MODULES}
---
"""


class Node_PythonScript(Node):
    """A node used to run a small Python script to process data"""
    node_kind = NodeKind.Script
    node_display = 'Python Script'
    node_desc = 'Process data using a small Python script'
    node_category = 'Advanced'
    node_subcategory = 'Script'
    configurable_inputs = True
    configurable_outputs = True
    inputs = []
    outputs = []

    class nodeConfig(NodeConfig):
        """Config for this node"""
        sections = [
            ConfigSection('ScriptNode Config', 'Configuration for ScriptNode', [
                ConfigGroup('General', 'General configuration', [
                    ConfigParameter('Script', 'Script to execute', 'script', VarType.String, comment=NODE_PY_SCRIPT_COMMENT,
                                    tweaks=InputWidgetTweaks_String(code_editor=True, code_language='python')),
                ]),

            ]),
        ]
    config = nodeConfig()

    @staticmethod
    def execute(inputs: list, config: NodeConfig, common_config: CommonNodeConfig) -> list:
        # NOTE: not aplicable to NodeKind.Script
        return []
