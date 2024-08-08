"""
Althea - App Entrypoint

"""
# Created 2022-2024 by James Bishop (james@bishopdynamics.com)
# License: GPLv3, see License.txt

# reference:
#   https://github.com/pthom/imgui_bundle/blob/main/bindings/imgui_bundle/demos_python/demos_immapp/demo_docking.py

from __future__ import annotations

import platform
import sys

from multiprocessing import freeze_support

from althea.common import APP_NAME, log, get_version, get_program_dir
from althea.common import imgui, hello_imgui, immapp, icons_fontawesome
from althea.vartypes import NormalizedColorRGBA
from althea import state
from althea import panes

from althea.ui import global_ui_state


class AltheaApp:
    """Main Althea application"""
    app_name = APP_NAME
    default_window_size: tuple[int, int] = (1000, 900)
    show_fps: bool = True

    def __init__(self) -> None:
        log.debug(f'platform: {platform.system()}')
        self.program_dir = get_program_dir()
        """Program location, where other expected subfolders can be found like assets, fonts, VERSION, COMMIT_ID, etc"""
        log.debug(f'programdir: {self.program_dir}')
        self.app_version = get_version()
        """Version number and commit id it was built from"""
        log.info(f'Initializing {self.app_name} v{self.app_version}')
        self.configure_assets_location()
        self.app_state = state.AppState()
        """Global app state"""
        self.app_state.runner_params = self.create_runner_params()
        """hello imgui runner parameters"""
        self.app_state.addon_params = self.create_addons_params()
        """imapp addons parameters"""

    # init steps

    def configure_assets_location(self):
        """Configure assets folder location"""
        # TODO - actually follow this comment's advice and createa  copy of the assets folder
        # By default, an assets folder is installed via pip inside site-packages/lg_imgui_bundle/assets
        # and provides two fonts (fonts/DroidSans.ttf and fonts/fontawesome-webfont.ttf)
        # If you need to add more assets, make a copy of this assets folder and add your own files,
        # and call set_assets_folder
        # NOTE: on Linux and macOS, imgui finds the correct assets path without any assistance
        #   on Windows, we need to give it a nudge, but only if we are packaged up into an executable using pyinstaller
        if platform.system() == 'Windows':
            if getattr(sys, 'frozen', False):
                hello_imgui.set_assets_folder(str(get_program_dir().joinpath('assets')))

    def create_runner_params(self) -> hello_imgui.RunnerParams:
        """Prepare hello imgui runner params, which holds settings as well as UI callbacks"""
        runner_params = hello_imgui.RunnerParams()
        runner_params.app_window_params.window_title = f'{self.app_name} v{self.app_version}'
        runner_params.imgui_window_params.menu_app_title = self.app_name
        runner_params.app_window_params.window_geometry.size = self.default_window_size
        runner_params.app_window_params.restore_previous_geometry = True
        runner_params.app_window_params.borderless = False
        runner_params.app_window_params.borderless_movable = True
        runner_params.app_window_params.borderless_resizable = True
        runner_params.app_window_params.borderless_closable = True

        # We use the default status bar of Hello ImGui
        runner_params.imgui_window_params.show_status_bar = True
        # Add custom widgets in the status bar
        runner_params.callbacks.show_status = self.status_bar_gui
        # uncomment next line in order to hide the FPS in the status bar
        runner_params.imgui_window_params.show_status_fps = self.show_fps
        runner_params.fps_idling = hello_imgui.FpsIdling(remember_enable_idling=True)

        # Here, we fully customize the menu bar:
        # by setting `show_menu_bar` to True, and `show_menu_app` and `show_menu_view` to False,
        # HelloImGui will display an empty menu bar, which we can fill with our own menu items via the callback `show_menus`
        runner_params.imgui_window_params.show_menu_bar = True
        runner_params.imgui_window_params.show_menu_app = False
        runner_params.imgui_window_params.show_menu_view = False

        # Inside `show_menus`, we can call `hello_imgui.show_view_menu` and `hello_imgui.show_app_menu` if desired
        runner_params.callbacks.show_menus = self.show_menu_gui

        # Optional: add items to Hello ImGui default App menu
        runner_params.callbacks.show_app_menu_items = self.show_app_menu_items

        # toolbar options
        edge_toolbar_options = hello_imgui.EdgeToolbarOptions()
        edge_toolbar_options.size_em = 2.5
        edge_toolbar_options.window_bg = NormalizedColorRGBA(0.8, 0.8, 0.8, 0.35).to_imcolor()
        # top toolbar
        runner_params.callbacks.add_edge_toolbar(
            hello_imgui.EdgeToolbarType.top,
            self.show_top_toolbar,
            edge_toolbar_options,
        )

        # Load user settings at callbacks `post_init` and save them at `before_exit`
        runner_params.callbacks.post_init = self.on_post_init
        runner_params.callbacks.before_exit = self.on_before_exit

        # load assets
        runner_params.callbacks.load_additional_fonts = self.on_load_assets

        # handle pre-frame render tasks
        runner_params.callbacks.before_imgui_render = self.on_before_render

        # Change theme
        tweaked_theme = runner_params.imgui_window_params.tweaked_theme
        tweaked_theme.theme = hello_imgui.ImGuiTheme_.darcula_darker
        tweaked_theme.tweaks.rounding = 10.0

        #
        # Part 2: Define the application layout and windows
        #

        # First, tell HelloImGui that we want full screen dock space (this will create "MainDockSpace")
        runner_params.imgui_window_params.default_imgui_window_type = (
            hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
        )

        # you can drag windows outside the main window in order to put their content into new native windows
        runner_params.imgui_window_params.enable_viewports = True

        # Set the default layout (this contains the default DockingSplits and DockableWindows)
        runner_params.docking_params = self.create_default_layout()

        #
        # Part 3: Where to save the app settings
        #

        # By default, HelloImGui will save the settings in the current folder.
        # This is convenient when developing, but not so much when deploying the app.
        # You can tell HelloImGui to save the settings in a specific folder: choose between
        #         current_folder
        #         app_user_config_folder
        #         app_executable_folder
        #         home_folder
        #         temp_folder
        #         documents_folder
        #
        # Note: app_user_config_folder is:
        #         AppData under Windows (Example: C:\Users\[Username]\AppData\Roaming)
        #         ~/.config under Linux
        #         "~/Library/Application Support" under macOS or iOS
        runner_params.ini_folder_type = hello_imgui.IniFolderType.current_folder

        # runnerParams.ini_filename: this will be the name of the ini file in which the settings
        # will be stored.
        # Note: if ini_filename is left empty, the name of the ini file will be derived
        # from app_window_params.window_title
        runner_params.ini_filename = f"{self.app_name}.ini"
        return runner_params

    def create_addons_params(self) -> immapp.AddOnsParams:
        """Prepare immapp addons parameters, which includes config for node_editor"""
        addon_params = immapp.AddOnsParams()
        addon_params.with_node_editor = True
        addon_params.with_markdown = True
        return addon_params

    def start(self):
        """Start the application using prepared parameters"""
        log.debug('Starting application')
        immapp.run(self.app_state.runner_params, self.app_state.addon_params)

    # on_frame drawing functions

    def on_frame(self):
        """Perform per-frame tasks"""
        self.app_state.on_frame()

    def status_bar_gui(self):
        """Draw the status bar at bottom of window"""
        if self.app_state.unsaved_changes:
            change_msg = 'Unsaved'
        else:
            change_msg = 'Saved'
        imgui.text(f'{change_msg} - {self.app_state.status_text}')

    def show_menu_gui(self):
        """Show the menubar at the top of the window"""
        hello_imgui.show_app_menu(self.app_state.runner_params)
        hello_imgui.show_view_menu(self.app_state.runner_params)
        if imgui.begin_menu("Debug"):
            clicked, _ = imgui.menu_item("Metrics", "", self.app_state.show_metrics)

            if clicked:
                self.app_state.show_metrics = not self.app_state.show_metrics
                if self.app_state.show_metrics:
                    log.warning("Showing metrics window")
                else:
                    log.warning("Hiding metrics window")

            imgui.end_menu()

    def show_app_menu_items(self):
        """Add custom items to main app menu"""
        clicked, _ = imgui.menu_item("Open Workspace", "", False, True)
        if clicked:
            self.app_state.workspace.open()
        clicked, _ = imgui.menu_item("Import Workspace", "", False, True)
        if clicked:
            self.app_state.workspace.import_wk()
        clicked, _ = imgui.menu_item("Clear Workspace", "", False, True)
        if clicked:
            self.app_state.workspace.reset_to_default()
        clicked, _ = imgui.menu_item("Save Workspace", "", False, True)
        if clicked:
            self.app_state.workspace.save()
        clicked, _ = imgui.menu_item("Save Workspace As...", "", False, True)
        if clicked:
            self.app_state.workspace.save_as()

    def show_top_toolbar(self):
        """Show buttons in top toolbar"""
        if imgui.button(icons_fontawesome.ICON_FA_FOLDER_OPEN):
            self.app_state.workspace.open()
        imgui.same_line()
        if imgui.button(icons_fontawesome.ICON_FA_SAVE):
            self.app_state.workspace.save()

        # TODO: find another convenient place to call on_frame
        self.on_frame()

    # Docking Layouts and Docking windows

    def create_default_docking_splits(self) -> list[hello_imgui.DockingSplit]:
        """Define the default docking splits"""
        # i.e. the way the screen space is split in different target zones for the dockable windows
        # We want to split "MainDockSpace" (which is provided automatically) into three zones, like this:
        #
        #    ____________________________________________________
        #    |        |                                |        |
        #    | Command|                                | Props  |
        #    | Space  |    MainDockSpace               | Space  |
        #    |        |                                |        |
        #    |        |                                |        |
        #    |        |                                |        |
        #    ----------------------------------------------------
        #    |     MiscSpace                                    |
        #    ----------------------------------------------------
        #

        # Uncomment the next line if you want to always start with this layout.
        # Otherwise, modifications to the layout applied by the user layout will be remembered.
        # runner_params.docking_params.layout_condition = hello_imgui.DockingLayoutCondition.ApplicationStart

        # Then, add a space named "MiscSpace" whose height is 25% of the app height.
        # This will split the preexisting default dockspace "MainDockSpace" in two parts.
        split_main_misc = hello_imgui.DockingSplit()
        split_main_misc.initial_dock = "MainDockSpace"
        split_main_misc.new_dock = "MiscSpace"
        split_main_misc.direction = imgui.Dir_.down
        split_main_misc.ratio = 0.2

        # Then, add a space to the left which occupies a column whose width is 25% of the app width
        split_main_command = hello_imgui.DockingSplit()
        split_main_command.initial_dock = "MainDockSpace"
        split_main_command.new_dock = "CommandSpace"
        split_main_command.direction = imgui.Dir_.left
        split_main_command.ratio = 0.2

        # Then, add a space to the right which occupies a column whose width is 25% of the app width
        split_main_properties = hello_imgui.DockingSplit()
        split_main_properties.initial_dock = "MainDockSpace"
        split_main_properties.new_dock = "PropertiesSpace"
        split_main_properties.direction = imgui.Dir_.right
        split_main_properties.ratio = 0.3

        splits = [split_main_misc, split_main_command, split_main_properties]
        return splits

    def create_dockable_window(self, name: str, space: str, target_pane: panes.Pane) -> hello_imgui.DockableWindow:
        """Create a dockable window and put a Pane in it"""
        new_window = hello_imgui.DockableWindow()
        new_window.label = name
        new_window.dock_space_name = space
        new_window.gui_function = target_pane.on_frame
        return new_window

    def create_windows(self) -> list[hello_imgui.DockableWindow]:
        """Define all windows"""

        dockable_windows = [
            self.create_dockable_window('  Toolbox', 'CommandSpace', self.app_state.panes.Toolbox),
            self.create_dockable_window('  Sheet Config', 'PropertiesSpace', self.app_state.panes.SheetConfig),
            self.create_dockable_window('  App Config', 'PropertiesSpace', self.app_state.panes.AppConfig),
            self.create_dockable_window('  Test Config', 'PropertiesSpace', self.app_state.panes.TestConfig),
            self.create_dockable_window('  Log', 'MiscSpace', self.app_state.panes.Log),
            self.create_dockable_window('  Function Editor', 'MainDockSpace', self.app_state.panes.FunctionEditor),
        ]
        sheet_win = self.create_dockable_window('  Sheet Editor', 'MainDockSpace', self.app_state.panes.SheetEditor)
        sheet_win.focus_window_at_next_frame = True
        dockable_windows.append(sheet_win)
        return dockable_windows

    def create_default_layout(self) -> hello_imgui.DockingParams:
        """Create the default layout config"""
        # A layout is stored inside DockingParams, and stores the splits + the dockable windows.
        docking_params = hello_imgui.DockingParams()
        # By default, the layout name is already "Default"
        # docking_params.layout_name = "Default"
        docking_params.docking_splits = self.create_default_docking_splits()
        docking_params.dockable_windows = self.create_windows()
        return docking_params

    # callbacks

    def on_post_init(self):
        """Tasks to perform after app is initialized (aka startup tasks)"""
        self.app_state.app_config.load()
        for pane in self.app_state.panes.get_list():
            log.debug(f'Performing pane setup for: {pane.__class__.__name__}')
            pane.setup()
        self.app_state.start_backend()

    def on_before_exit(self):
        """Tasks to perform before exiting"""
        log.debug('Performing app cleanup tasks')
        self.app_state.app_config.save()
        self.app_state.backend.stop()
        for pane in self.app_state.panes.get_list():
            log.debug(f'Performing pane cleanup for: {pane.__class__.__name__}')
            pane.cleanup()

    def on_load_assets(self):
        """Load additiona assets here"""
        # first, load the default font and fontawesome icons
        hello_imgui.imgui_default_settings.load_default_font_with_font_awesome_icons()
        # load our own assets into app_state
        global_ui_state.ensure_assets()

    def on_before_render(self):
        """Tasks to perform immediately before frame rendering"""
        # Need to reset the id registry at the top of every frame
        global_ui_state.id_registry.reset()


##########################################################################


# NOTE: about pyinstaller + multiprocessing
#   according to documentation, freeze_support() is only needed on Windows, and has no effect when used on other platforms
#   however in practice, we found on macOS the app would get stuck in a loop, re-launching itself a million times
#   adding freeze_support() fixed this issue, but it is not clear _why_
#   https://docs.python.org/3/library/multiprocessing.html#multiprocessing.freeze_support
if __name__ == "__main__":
    freeze_support()  # See note above about pyinstaller + multiprocessing
    app = AltheaApp()
    app.start()
