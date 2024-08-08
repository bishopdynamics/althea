"""
Althea - Nodes Collection

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

# reference: https://julienharbulot.com/python-dynamical-import.html

from inspect import isclass
from pkgutil import iter_modules
from importlib import import_module

from ..common import get_program_dir

from .base import Node


def get_package_dir():
    """figure out absolute path to this package folder"""
    # NOTE: dont forget to include ./althea folder when building app using pyinstaller/nuitka
    program_dir = get_program_dir()
    package_dir = program_dir.joinpath('althea').joinpath('nodes')
    # print(f'nodespkg dir: {str(package_dir)}')
    return package_dir


def collect_node_classes() -> dict[str, type[Node]]:
    """Collect all node classes"""
    all_node_classes: dict[str, type[Node]] = {}
    package_dir = get_package_dir()
    for (_, module_name, _) in iter_modules([package_dir]):

        # import the module and iterate through its attributes
        module = import_module(f"{__name__}.{module_name}")

        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)

            if isclass(attribute) and issubclass(attribute, Node):
                if attribute.__name__ != 'Node':
                    if attribute.node_display != 'Unknown':
                        all_node_classes[attribute_name] = attribute
    return all_node_classes


def create_node_registry() -> dict[str, dict[str, dict[str, type[Node]]]]:
    """create node class registry, organized into category and subcategory"""
    node_classes = collect_node_classes()
    node_class_registry: dict[str, dict[str, dict[str, type[Node]]]] = {}
    for class_name, class_ in node_classes.items():
        if class_.node_category not in node_class_registry:
            node_class_registry[class_.node_category] = {}
        if class_.node_subcategory not in node_class_registry[class_.node_category]:
            node_class_registry[class_.node_category][class_.node_subcategory] = {}
        node_class_registry[class_.node_category][class_.node_subcategory][class_name] = class_
    return node_class_registry


def print_registry(registry: dict[str, dict[str, dict[str, type[Node]]]]):
    """Print the registry of Node sub-classes, organized into Category -> Subcategory -> Classname -> class"""
    print('Registry:')
    for category, subs in registry.items():
        print(f'-- {category} --')
        for subcat, nodesdict in subs.items():
            print(f'  ~~ {subcat} ~~')
            count = 0
            for classname, actual_class in nodesdict.items():
                count += 1
                print(f'    {count}. {classname} - {actual_class.node_desc} - In: {len(actual_class.inputs)} Out: {len(actual_class.outputs)}')
