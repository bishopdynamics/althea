"""
Althea - Node Configuration Schemas

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations


from ..vartypes import VarType
from ..config import Config, ConfigSection, ConfigGroup, ConfigParameter
from ..ui import InputWidgetTweaks_List, InputWidgetTweaks_IOPinInfo


class NodeConfig(Config):
    """Base class for node-specific configuration"""


class WorkspaceConfig(Config):
    """Workspace Configuration"""
    sections = [
        ConfigSection('Workspace Config', 'Common workspace configuration', [
            ConfigGroup('General', 'General configuration', [
                ConfigParameter('Name', 'Give this workspace a meaningful name', 'name', VarType.String, ''),
            ]),
        ]),
    ]


class WorkspaceSheetConfig(Config):
    """Sheet Configuration"""
    sections = [
        ConfigSection('Sheet Config', 'Common sheet configuration', [
            ConfigGroup('General', 'General configuration', [
                ConfigParameter('Name', 'Give this sheet a meaningful name', 'name', VarType.String, ''),
            ]),
        ]),
    ]


class CommonNodeConfig(Config):
    """Common Node Configuration; applies to all nodes, separate namespace from other config"""
    sections = [
        ConfigSection('Common Config', 'Common node configuration', [
            ConfigGroup('General', 'General configuration', [
                ConfigParameter('Name', 'Give this node a meanful name', 'name', VarType.String, ''),
                ConfigParameter('Inputs', 'Specify the input types', 'input_iopininfos',
                        VarType.List,
                        tweaks=InputWidgetTweaks_List(item_min=0, item_max=128,
                                                      item_type=VarType.IOPinInfo,
                                                      tweaks=InputWidgetTweaks_IOPinInfo()
                                                      )
                                ),
                ConfigParameter('Outputs', 'Specify the output types', 'output_iopininfos',
                        VarType.List,
                        tweaks=InputWidgetTweaks_List(item_min=0, item_max=128,
                                                      item_type=VarType.IOPinInfo,
                                                      tweaks=InputWidgetTweaks_IOPinInfo()
                                                      )
                                )

            ])
        ]),
    ]


class SpecialCommonNodeConfig(CommonNodeConfig):
    """Common Node Configuration, but special for StaticValuesNode to allow assigning static output values"""
    sections = [
        ConfigSection('Common Config', 'Common node configuration', [
            ConfigGroup('General', 'General configuration', [
                ConfigParameter('Name', 'Give this node a meanful name', 'name', VarType.String, ''),
                ConfigParameter('Inputs', 'Specify the input types', 'input_iopininfos',
                        VarType.List,
                        tweaks=InputWidgetTweaks_List(item_min=0, item_max=128,
                                                      item_type=VarType.IOPinInfo,
                                                      tweaks=InputWidgetTweaks_IOPinInfo()
                                                      )
                                ),
                ConfigParameter('Outputs', 'Specify the output types and static values', 'output_iopininfos',
                        VarType.List,
                        tweaks=InputWidgetTweaks_List(item_min=0, item_max=128,
                                                      item_type=VarType.IOPinInfo,
                                                      tweaks=InputWidgetTweaks_IOPinInfo(edit_static_value=True),
                                                      )
                                )

            ])
        ]),
    ]
