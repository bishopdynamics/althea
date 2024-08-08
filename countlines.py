#!/usr/bin/env python3
"""
Print a summary of lines of code per file
"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

import os
import pathlib


SKIP_DIRNAMES = ['venv', '__pycache__', 'fonts', 'examples', 'assets', '.idea', '.git', 'dist', 'docs', 'sampledata']  # folder names to skip when looking for .py files

SEARCH_PATH = pathlib.Path.cwd()


def print_statline(lines, newlines, reldir, header=False):
    """
    Print a line of stats formatted for a table
    """
    print(f'{lines:>8} |{newlines:>8} | {reldir:<20}')
    if header:
        g = ''
        print(f'{g:->9}|{g:->9}|{g:->20}')


def path_to_name(path: str) -> str:
    """Turn path to a module into a module name we can print"""
    modulename = path.removeprefix(str(SEARCH_PATH) + '/')
    modulename = modulename.replace('/', '.')
    modulename = modulename.replace('\\', '.')
    return modulename


def countlines(start: str, lines: int = 0, header: bool = True, begin_start: str = None):
    """
    count lines (recursively) of files ending in .py in given folder
    """
    if header:
        print_statline('Total', 'Lines', 'File', header=True)
        modulename = ''
    else:
        modulename = path_to_name(start)
        print(f' Module: {modulename}')
    thing_list = os.listdir(start)
    thing_list.sort()
    for thing in thing_list:
        thing = os.path.join(start, thing)
        if os.path.isfile(thing):
            if thing.endswith('.py'):
                if 'tmp/' in thing:
                    continue  # skip tmp folder
                with open(thing, 'r', encoding='utf-8') as f:
                    newlines = f.readlines()
                    newlines = len(newlines)
                    lines += newlines
                    if begin_start is not None:
                        reldir_of_thing = '.' + thing.replace(begin_start, '')
                    else:
                        reldir_of_thing = '.' + thing.replace(start, '')
                print_statline(lines, newlines, reldir_of_thing)

    for thing in thing_list:
        if thing in SKIP_DIRNAMES:
            continue
        thing = os.path.join(start, thing)
        if os.path.isdir(thing):
            this_name = path_to_name(thing)
            mlines = countlines(thing, 0, header=False, begin_start=start)
            if '.' not in this_name:
                print(f' {this_name} total: {mlines}')
            else:
                print(f'    {this_name} total: {mlines}')
            lines += mlines
    return lines


if __name__ == '__main__':
    countlines(str(SEARCH_PATH))
