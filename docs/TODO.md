# TODO

This is a poorly structured outline of potential next things to work on, in no particular order.

## Up first

imgui_bundle v1.5.2 broke things! segfault at launch, no idea what's wrong, locked to v1.3.0 for now

## Presentations

* presentations
  * a slide is:
    * select a bookmarked view
    * select some nodes
      * save the current state/config of each
  * playback of a slide:
    * go to view
    * for each advance (or automatically after N seconds) apply the next set of state/config to nodes
      * option to lerp between values for Integer/Float/Vec2/Vec4/Color
        * non-lerped values would change at 50% thru lerp time
      * 

## more new ideas after watching bunch of videos

* all our methods that return an actual object, should really return the index to that object
* the duplicative import of log object is not necessarily a problem, but should still be fixed
* for loops are slow, but can be implemented better
* for things where we need to check state compared to previous frame, we should capture "previous" and "current" for the entire thing instead of piecemeal
  * at top of frame, move current -> previous, then capture new current



## Little Items

* check and update has_changed for sheet and workspace
* keyboard shortcuts for save/load/recalc
* input widget for path type needs config for filetypes filter
  * apply this to Table from file value node
* table widget needs buttons to remove row/col
* newly created nodes should be brought to front
* sheet editor and function editor cannot be visible at the same time, breaks drag, zoom, actualy it breaks the whole editor
* we can add a simple button to config, by doing a boolean with same text for true/false, and onchange doesnt check value, just does a thing (like reset values to dfaults)
* add a minimap to sheet editors

## New Thoughts, after we got functions working well

* list fanout
  * configure # of outputs
  * if input list is longer, extra data dropped
  * if input list is shorter, remaining values become None
  * number of outputs doesnt change as a consequence of input data change, but values may be invalid
* color value/view

* we need two new special nodes
  * configurable inputs -> output dict
  * input dict -> individual outputs (whatever dict has)
  * "dict" would actually be a SpecialVarType which only "matches" if all the key names are identical
    * so effectively, any "dict" type is actually "dict of these specific key:vartype"
* we need a treeview node, for viewing dicts, lists, etc
* view node should have a "loop out" checkbox, which creates an output matching type and value of input
* we need a convenient, simple, minimal way to define/generate "built-in functions"
  * would be appended to actual function_sheets list, when creating a Select for dropdowns
  * would rather not copy/paste boilerplate and define all of them by hand

## Function Nodes

* we still need a way to provide test values when editing a function sheet
  * We can now do this by allowing user to edit static values on the Function Inputs' outputs!
    * the Function Node will ignore the static values, so they wont matter!
  * when calc is called on that sheet, it should always use the test values instead
  * maybe Function Inputs actually has input pins, mirroring the output pins (which are set by config)
  * input pins are specifically labeld as "Test Input"
  * input pins are ignored for use_function() situation
  * when function sheet is active, and calc called, test input values are used

## Error handling

* top-level try/except context
* any unhandled exceptions cause an error dialog
  * this is where end-user ability to report an issue goes
  * capture the exception, the trace of that exception, AND a full trace
  * capture app_state, configs, idproviders, etc
  * capture platform details, python version, etc
  * capture version, commit
  * capture the currently loaded file (the json string on-disk)
  * capture the current workspace state (dump it to json string as if writing to file)
* we also need an in-app tool (window) that can inspect the entire app state
  * create a base class with generic __reduce__, to_dict() and from_dict() methods
  * apply that to, like, everything
    * already done for SpecialVarType
  * AltheaObject ?
  * are we building an entity system?
  * anything that fails json.dumps(), use objdump instead (which will make a kinda ugly broken version thats still better than nothing for debugging)
* we need a generic treeview ui widget for this



## User nicities

* unsaved/applied changes markers everywhere
  * confirm app exit if unsaved changes
* recovery log
  * every change, save to a hidden rotating file set
  * also take a screenshot of the view before and after, turn it into a little gif of the change
    * that means we need a way to capture current active window specifically
    * so we can capture change on node editor, or in a config editor
  * keep N previous versions
  * log (in the file), the last M changes (long-term undo history?)
  * at app startup, create a canary file
  * when saving, write details to canary file
  * on proper app shutdown, remove canary file only if there are no unsaved changes
  * on startup, if canary file exists, read it
    * prompt user to recover from last X previous versions
    * pre-validate all restore files and changes, looking for corrupt version after J change
  * can we store last-save + just changes in undo history?
* add to menu:  Y previous workspace files
* command pallete
  * format query (applies to a currently active sql query input text input)
  * format script (applies to a currently active code editor, using currently configured language)
  * new sheet
  * bookmark view
  * run command/script
    * re-use script manager, but give it access to app state
    * let us script anything about the app
    * to do this, we really need to refactor all app/ui/state/context/etc into a single app_global_state object
      * maybe even a sub-module: state
    * workspace needs a dictionary of scripts
    * we can recall scripts by name (key in dict)
    * pre-compile, checksum content, avoid re-compile if no changes
    * tutorials can just be another set of scripts
      * can tutorials play back in a separate instance of the main window?
      * put tutorial window on another screen
      * play/pause/ffw/rewind/skip
      * need a way to record tutorials, but dont record mouse movements, record things to click and animate between needed mouse positions
      * it would be even cooler to constantly be recording, and keep the last 10 minutes? in a temporary file
      * for bug submission, can submit recording of actions and app state
      * to reproduce bug, we can load app state and then start playback
      * for tests, we can package up various ways to test bugs
      * also we can automate creation of recordings to test all features, etc
      * 

## Medium Items

* import from workspace (import selected sheets into current workspace)
* when shutting down, 
  * save app config
  * if unsaved workspace changes, save to temporary file and reload it (marked as still unsaved) next app launch
* we need a concept of context-sensitive action buttons
  * this is not config, more like "do X to this node", or "do Y to these nodes"
  * reload this table from file (otherwise dont, only do it when file/subitem changes)
  * for a node that writes a table to file: write to file now
  * for a node that executes an API call using data this graph prepared: make the call

* What other things go in toolbox?
  * wizards to create N instances of a node type, in a neat grid
  * layout node? 
    * horizontal or vertical list of slots for nodes
    * being in a slot only affects layout, does not touch inputs/outputs
    * moving layout node moves everything with it


## Big Picture Items

* File Output Node?
* we need ways to navigate the node editor canvas
  * bookmark zoom + pan positions
    * call them views
    * views are updatable
    * go to view node graph gets dark blue border
    * now pan/zoom away from that view, the blue outline of saved view remains in place, and actual view is orange
    * click update, current view becomes saved view and blue

* looking at other node like projects
  * 3d modeling https://github.com/kovacsv/VisualScriptCAD
  * creating GLSL shaders https://blog.undefinist.com/writing-a-shader-graph/
  * pyscript: we could put the whole frontend into a web page via pyscript, maybe use web workers for calc workers?

* presentation mode
  * we have sheets, functions, and nodes. now we need Cards
  * cards present a collection of UI elements
  * kinda like a slide deck, but navigating between cards is purely non-linear (there is no next slide, only links to other cards)
  * yeah, kinda like hypercard

### VarTypes

* we really should switch to using actual python types/classes instead of the enum
  * default becomes initialized without parameters
  * aliases and subclasses can be automatically identified
  * maybe pre-populate a list of all available types, excluding ones used internally for this app
  * can we dynamically generate all the values classes?


## Idea: data source proxies

instead of adding a pip package for every little api we want to support, create a template for a data proxy

* a data proxy is a service running on this, or another host
* it has an extremely simple api:
  * get - returns a table of data
* a data proxy boils down to a single function which accepts a config object/dict and returns a table
* it is up to the proxy to convert the data into a table
* it is up to the proxy to cache this table, and only perform the actual API call as often as allowed by that API convention
* it is up to the proxy to handle paging entirely
* maybe it doesnt need to be a table
  * could just be dict as json


## Idea: how would continuous / time-based nodes work?

* we have a clock, it regularly causes a "tick" event
* at "tick", nodes are processed
* a tick also includes a "right now" value, probably nanoseconds since app start, or some reset condition
* time-based nodes have execute_tick() method
  * nodes must do their thing based on the current time value
* dependency tree is built, and nodes tick() in parallel where able, in sets
* the current time value is static for a single tick(); all nodes do their thing as if it were the exact same time

