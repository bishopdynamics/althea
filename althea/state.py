"""
Althea - App State and Config

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

from __future__ import annotations

from typing import Literal
from pathlib import Path

from .common import APP_NAME, hello_imgui, immapp
from .common import log, time_millis

from .vartypes import VarType

from .config import FileConfig, ConfigSection, ConfigGroup, ConfigParameter

from .backend import Backend

from .panes import Pane
from .panes import ToolboxPane
from .panes import SheetEditorPane
from .panes import AppConfigPane
from .panes import SheetConfigPane
from .panes import TestConfigEditorPane
from .panes import LogPane

from .nodes.base import Workspace

from .nodes import create_node_registry, collect_node_classes

from .ui import InputWidgetTweaks_Integer, InputWidgetTweaks_Bool, InputWidgetTweaks_Float


class AppConfig(FileConfig):
    """Application configuration"""
    file_name = f'{APP_NAME}-AppConfig'
    sections = [
        ConfigSection('App Config', f'{APP_NAME} Application configuration', [
            ConfigGroup('General', 'General configuration', [
                ConfigParameter('Default Workspaces Folder', 'Default folder to save workspaces',
                                'default_workspaces_folder', VarType.Path, Path().home().joinpath('Documents').joinpath(APP_NAME)),
                ConfigParameter('Auto Re-Calculate', 'Recalculate any changed nodes automatically',
                                'auto_recalc', VarType.Bool, True),
                ConfigParameter('Log Auto Re-Calculate', 'Show a message in the log every time auto-recalc happens',
                                'auto_recalc_log', VarType.Bool, False),
                ConfigParameter('Auto Re-Calc Cycle', 'How often to re-calculate if there are changes',
                                'auto_recalc_time', VarType.Integer, 100, tweaks=InputWidgetTweaks_Integer(min=50, max=5000, increment=10, enforce_range=True, format='%d ms')),
                ConfigParameter('Log CalcJob Traces', 'Show CalcJob error stack traces in the log',
                                'log_calcjob_error_traceback', VarType.Bool, False),
                ConfigParameter('Log CalcJob Dependency Graphs', 'Show dependency graphs for calcjobs in the log',
                                'log_calcjob_dependency_graphs', VarType.Bool, False),
                ConfigParameter('Calc Workers', 'Number of workers to spawn for calc jobs\nThis determines how many jobs can be done in parallel',
                                'num_workers', VarType.Integer, 4, tweaks=InputWidgetTweaks_Integer(enforce_range=True, min=1, max=512, format='%d workers')),
                ConfigParameter('Calc Worker Type', 'Create workers as Threads or Processes\n\tThreads may have slightly lower overhead per-job, but may not be able to operate in true-parallel fashion due to Python GIL\n\tProcess can always operate in true parallel fashion (up to the limits of your CPU), but may incur slightly more overhead.',
                                'worker_type', VarType.Bool, False, tweaks=InputWidgetTweaks_Bool(button=True, button_true='Processes', button_false='Threads')),
            ]),
            ConfigGroup('Node Rendering', 'Configuration for how Nodes are rendered', [
                ConfigParameter('Debug Node Rendering', 'Display debugging information related to node rendering', 'debug_node_rendering', VarType.Bool, False, tweaks=InputWidgetTweaks_Bool()),
                ConfigParameter('View Animation Time', 'How long to take to animate between two views',
                                'view_animation_time', VarType.Float, 1.0, tweaks=InputWidgetTweaks_Float(min=0.0, max=30.0, increment=0.2, enforce_range=True, format='%.3f seconds')),
            ]),
        ]),
    ]

# debug_node_rendering


class AppPanes:
    """Window / Panes"""

    def __init__(self, app_state: AppState) -> None:
        self.AppConfig = AppConfigPane(app_state)
        self.SheetConfig = SheetConfigPane(app_state)
        self.FunctionEditor = SheetEditorPane(app_state, variant='Function')
        self.TestConfig = TestConfigEditorPane(app_state)
        self.Toolbox = ToolboxPane(app_state)
        self.Log = LogPane(app_state)
        self.SheetEditor = SheetEditorPane(app_state, variant='Sheet')
        self.SheetEditor.set_sheet(app_state.workspace.sheets[0].id)

    def get_list(self) -> list[Pane]:
        """Get a list of panes"""
        panes_list: list[Pane] = []
        for _key, obj in self.__dict__.items():
            if isinstance(obj, Pane):
                panes_list.append(obj)
        return panes_list


class AppState:
    """Application Runtime State"""

    def __init__(self):
        self.status_text = 'Initializing...'
        self.all_node_classes = collect_node_classes()
        self.node_registry = create_node_registry()
        self.app_config = AppConfig()
        # we track the current backend config vars, so we can compare to app config values to see if they changed
        self._backend_num_workers: int = None
        self._backend_worker_type: bool = None
        self.backend: Backend = None
        self._backend_needs_restart = False
        self._backend_last_config_change = 0
        # self.first_frame = True
        self.show_metrics = False
        self.unsaved_changes = True
        self.need_change_propagate = False
        self.ensure_save_folder()
        self.workspace = Workspace(self)
        self.panes = AppPanes(self)
        self.status_text = 'Ready'
        self._focused_editor: Literal['Sheet', 'Function'] = 'Sheet'
        self.runner_params: hello_imgui.RunnerParams = None
        self.addon_params: immapp.AddOnsParams = None

    def set_focused_editor(self, sel: Literal['Sheet', 'Function']):
        """Set the internal tracker for which editor (Sheet or Function) is currently in focus"""
        print(f'Focused editor changed to: {sel}')
        self._focused_editor = sel

    def get_focused_editor(self) -> Literal['Sheet', 'Function']:
        """Get internal tracker for which editor (Sheet or Function) is currently in focus"""
        return self._focused_editor

    def start_backend(self):
        """Start backend"""
        self._backend_num_workers: int = self.app_config.get('num_workers')
        self._backend_worker_type: bool = self.app_config.get('worker_type')
        self.backend = Backend(num_workers=self._backend_num_workers, workers_as_processes=self._backend_worker_type)
        self.backend.start()

    def ensure_save_folder(self):
        """Ensure that the configured default workspace folder exists"""
        wk_folder: Path = self.app_config.get('default_workspaces_folder')
        if not wk_folder.is_dir():
            log.debug(f'Creating missing default workspace save folder: {str(wk_folder)}')
            wk_folder.mkdir(parents=True)

    def on_frame(self):
        """perform per-frame tasks for state"""
        # handle workspace
        self.workspace.on_frame()
        # handle backend config changes that may require backend restart
        if self._backend_num_workers is not None and self._backend_worker_type is not None:
            if self._backend_num_workers != self.app_config.get('num_workers'):
                self._backend_num_workers: int = self.app_config.get('num_workers')
                self._backend_last_config_change = time_millis()
                self._backend_needs_restart = True
            if self._backend_worker_type != self.app_config.get('worker_type'):
                self._backend_worker_type: bool = self.app_config.get('worker_type')
                self._backend_last_config_change = time_millis()
                self._backend_needs_restart = True
            if self._backend_needs_restart and time_millis() - self._backend_last_config_change > 1000:
                self._backend_needs_restart = False
                self.backend.restart(num_workers=self._backend_num_workers, workers_as_processes=self._backend_worker_type)
