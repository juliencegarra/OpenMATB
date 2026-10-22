# Changelog

The main changes of each version of OpenMATB. The releases and their files are on [GitHub](https://github.com/juliencegarra/OpenMATB/releases).

## Unreleased
  **New Features**
  - New example scenarios: three workload levels (`workload_levels/`, 5-minute blocks with the NASA-TLX), the multitasking cost (each task alone, then together), a workload peak, a training session, a session synchronized with physiological recordings (resting baseline and LSL markers), and in-task workload ratings (a one-item scale every 2 minutes, closed after 10 s), with participant instructions (`includes/instructions/tasks_en`)
  - Scenarios with names that tell what they are: `guided_tour_en` and `guided_tour_fr` (formerly `default_en` and `default_fr`), `one_minute_mouse_demo` (formerly `demo`); the manual test scenarios moved to `tests/scenarios` (out of the scenario selection)
  - Scenario selector: each scenario is shown by its title, a `# title: Workload peak` comment before its first command (else its file name in words), sorted by title, with its file name in grey
  - Questionnaires: a clearer layout. The scales are regularly spaced, the scale titles larger than the questions, the questions at most about 100 characters per line, the slider bounds next to the track, and the response text smaller, in grey. A full page brings its scales closer, then uses smaller titles and longer lines
  - The English NASA-TLX is scored from 0 to 100 (was 0 to 10), as the original and the French version; the French version has the order of the original (Performance before Effort)
  - Texts scaled to the window, as the task areas: from a 1920 x 1080 window, smaller in a smaller one (at least 0.75, e.g. 9 pt for 12 pt texts) and larger in a larger one. In a 1366 x 768 window, texts overlapped (system monitoring, communications, scheduling); in a 2560 x 1440 one, they looked small. In the replay, the texts follow the reduced task areas, as in the session. The scale is logged in the session file (`font_scale`)
  - Replay: the performance strip greys each task while it was not visible (instructions, questionnaires, dialogs, before its start and after its stop). The strip is now in replay time, as the timeline: the instructions and questionnaires, which pause the scenario time, had no width on it

  **Bug Fixes**
  - Fix a hidden communications task heard: a prompt cut by a pause was played again when the task was resumed while still hidden (guided tours). A hidden task is now silent, in the replay too
  - Fix the guided tours: the communications prompt was cut before its frequency, and the French tour had the English voice; fix the demo prompt cut by the end
  - Fix the communications radios on desktop: the name and the frequency were glued ("NAV 1135.7"), their digits even overlapped with pyglet 3 (a tab has no width in a single-line label)
  - Fix the communications callsign label: "Callsign" disappeared after the first frame, only the callsign remained
  - Fix in the browser the top right of italic letters cut (e.g. the dot of an italic i)
  - Fix a scenario path given on the command line from the current folder (e.g. `includes/scenarios/basic.txt`), looked for in the scenarios folder
  - Fix a questionnaire page title covering the first scale of a full page
  - Fix the scheduling chronometer in a window narrower than 1920 px: separated from its time by a tab, its name wrapped onto two lines, the second one below the task area. They are now side by side, centered together
  - Fix the replay keyboard history: the first key was on the title line, which wrapped in the narrow inputs strip. The replay timeline also takes the whole space between the play button and the time
  - Fix the system monitoring scale response times, one task step (200 ms) too long: the arrow entered its failure zone at the step after the start of the failure, when its response time had already started (the lights changed at once). A failure also ends the freeze of the arrow by the feedback of a previous one
  - Fix the communications tuning: a key press held for more than a task step tuned two steps. A press tunes one step, a key held tunes continuously after 0.3 s

## Version 1.5.2
  **New Features**
  - `maxdurationsec` in instructions and questionnaires: each page is shown at most this duration (seconds, real time, pauses excluded; 0: no limit). A page ended this way is logged as a `timeout` input and a `page_timeout` performance, and is ended at the same time in the replay
  - The session ID is logged at the start of the session file (`session_id` row): a renamed session file is replayed with the pseudorandom values of its session
  - Replay: the communications prompts end when they ended in the session, and their sound follows the replay speed (up to x4, muted above), its pauses and its seeks
  - CI: the scenarios of `includes/scenarios` are loaded with the plugins, and any error or warning (e.g. a deprecated command) fails the tests

  **Bug Fixes**
  - Fix response times counting the time a task was paused by the scenario (e.g. `sysmon;pause`), and the automatic solver delay after such a pause
  - Fix a second failure on a gauge already on failure, which restarted the response time and the alert timeout of the running one
  - Fix questionnaire answers logged again by a `genericscales;stop` after the end of the questionnaire (generated scenarios)
  - Fix a crash with fewer scheduling `labels` than timelines, and with a questionnaire scale with equal bounds
  - Fix the replay of a session file cut by a crash, or saved again with a BOM (e.g. by Excel), and its memory growing during the replay
  - Fix a seek in the replay leaving the previous run on screen (background bands, prompt sound, pointer)
  - Fix the scenario generator: custom_generator.txt numeric values, the advanced parameters of a block replaced by the computed ones, the track panel defaults, the inter-block file paths (old presets included), and the file selector selecting the row above
  - Fix a missing `scenario_path` in config.ini (the scenario selector opens), and config.ini read in UTF-8
  - Fix the parallel port triggers lasting a few microseconds on desktop (raised and lowered in the same update): a trigger now lasts `delayms` of scenario time
  - Fix closing the window (X button, Alt+F4) while a dialog is open, which lost the end of the session, and a scenario event run after quitting or behind an error dialog
  - Fix a `labstreaminglayer` started without a stop, which kept the session open (now a scenario error)
  - Fix the files of instructions and questionnaires checked in the other plugin folder, or a folder accepted as a file
  - Fix the performance level with `toleranceradius` 0, a blocking plugin placed in a corner, and `inf` in an integer parameter
  - Fix in the browser a prompt sound played again after a pause, and the LSL bridge reconnecting after the end of the session

## Version 1.5
  **Web version (new)**, see [WEB.md](WEB.md)
  - OpenMATB runs in a web browser (Pyodide, pyglet 3): same scenarios, plugins, session files and replay
  - Session files downloaded, or sent to JATOS, DataPipe or a WebDAV folder; static site, JATOS, SCORM and cmi5 packages
  - Joysticks through the browser Gamepad API, USB trigger box instead of the parallel port, Lab Streaming Layer bridge
  - The desktop version keeps pyglet 2 (`core/pyglet_compat.py` holds the differences)

  **New Features**
  - Response times measured from the frame showing the stimulus to the input (the key event timestamp in the browser), instead of between two clock ticks
  - Agents: the automatic solver (`automaticsolver`) plays the tasks through an agent, with keys and joystick inputs logged as `agent` inputs and replayed; `system;agent;<name>` changes the agent
  - `allowanykey` in system monitoring: any system monitoring key, or SPACE, signals a failure
  - Windows installer and portable version, and the web packages, in each release

  **Bug Fixes**
  - Fix lost questionnaire answers: only the answers of the last page were logged
  - Fix replay: inputs replayed about 0.2 s late, keys replayed after the plugin steps, agent actions done twice
  - Fix plugins resumed after a dialog although they were paused by a blocking plugin
  - Fix early exit during a gap of the scenario
  - Fix the manual/automatic periods of the scheduling timelines
  - Fix a strong joystick bouncing on the tracking reticle edge
  - Fix communications callsigns reusing characters, and a possible endless loop
  - Fix scenario and instruction files saved in UTF-8 with BOM, and crashes on a malformed scenario line
## Version 1.3+
  **Replay Mode (new)**
  - Full session replay system — replay recorded sessions from log files
  - File selector screen with mute button for replay mode
  - Replay slider with play, pause, and seeking support
  - Fast-forward capability
  - Instruction & scale plugins supported during replay

  **New Features**
  - system;pause scenario command — trigger pause directly from scenario files
  - Generic trigger plugin added
  - Joystick button mapping — any joystick button can be defined as a plugin response key (e.g., scales-1-key in System Monitoring)
  - Customizable vertical bounds of plugin areas
  - showvalue parameter for `generic scales` — hide the numeric value on scale sliders (hidden by default)
  - Question titles in `generic scales` displayed when title differs from question
  - Dynamic scale layout with proper slider sub-container distribution
  - Keyboard control for `genericscales` slides
  - Scenario selector shown at startup when no scenario is set in config.ini
  - Better English voice in `communications` task

  **Bug Fixes**
  - Fix `performance` scale ignoring params set after start (#34)
  - Fix numpad keys removed when scenario sets pump key to its default value (#52)
  - Fix `communications` voice language switching (#32)
  - Fix automode in `track` (#57)
  - Fix exit freezing under Windows
  - Fix slider widgets persisting across questionnaire pages
  - Fix pylsl import blocking the compiled version
  - Fix scenario generator (four small bugs)
  - Protect audio loading from crashes

## Version 1.2

**New plugins/features:**

- Each task (system monitoring, tracking, communications, resources management) can now be taken over by an automation, with the `automaticsolver` parameter;
- Accordingly, in the `scheduling` module, it is now possible to display up to four timelines (one per task);
- In the `scheduling` module, it is now possible to hide (no time) or reverse (remaining time) the chronometer;
- All the task plugins can now display their own feedback:
    * The `resman` plugin can now feedback the participant if the tanks are out of their tolerance area, by turning tolerance indicators to red (default) ;
    * The `communications` plugin can feedback the participant on response by displaying a green/red rectangle around the responded radio.
- Each task can now also display an overdue alarm, when a response is needed since too long (new parameters);
- A new plugin (labstreaminglayer) now allows the MATB to stream its log through the LSL communication protocol so as to synchronize it with various neurophysiological recordings.
- A `performance` plugin has been added, which displays a general performance level to the participant. The rules underlying the performance computation are described in [the wiki](https://github.com/juliencegarra/OpenMATB/wiki/How-to-modify-automatic-performance-computation%3F);
- A new `instructions` module is available, which allows the user to present static instructions in an HTML format, to the participant, at desired time. This includes the possibility to present images thanks to the `<img>` html tag;
- The `track` plugin now allows to reverse joystick axis;
- The tracking reticule path now sticks to the algorithm described in the initial MATB version by Comstock & Arnegard (1992);
- To avoid aberrant calculations of performance in the tracking task, due to the (potential) unequal proportions of height and width, the `equalproportions` parameters has been removed. Proportions in the tracking are now necessarily equals;
- The `pumpstatus` module (showing pump flows of the resources management task) has been removed. It has been integrated to the resources management module (`resman`), as an option (`displaystatus` parameter);
- Resources management pump states can now be either `on`, `off` or `failure` (instead of `1`, `0` or `-1`): more transparent;
- According to the original MATB version, scale arrows of the `sysmon` plugin now freeze during 1.5 second if a correct detection is made.

**Other changes:**

- Each scenario value is now finely controlled against a set of type verification methods. For instance, a `taskplacement` value must be a correct value (being in location_list = ['fullscreen', 'topmid', 'topright', 'topleft', 'bottomleft', 'bottommid', 'bottomright']), and so on, which greatly facilitates scenario debugging.
- Each scenario error is now logged into a `last_scenario_errors.log` file.
- The scenario does not need a final ending line anymore (e.g., `0:05:00;end`). Program now exits if there is no event to execute anymore and all the modules have been stopped.
- Added a `config.ini` file where to modify the main OpenMATB parameters, such as the scenario to use, the locale, the fullscreen mode...
- Switch from PySide/PyQt to the pyglet graphical library, which has the major advantage to be a pure python library.
- Can now exit OpenMATB with the Escape key + confirmation.
- OpenMATB can now be paused with the P key.
- The user can now define a global font into `config.ini`, given it is available on their computer
- Areas of interest (AOI) of each task are now automatically logged at start, for further (oculometric) computations. AOIs can be displayed for debugging purpose, with the `highlight_aoi` parameter of the `config.ini` file.
- To comply with anonymity constraints, the `participantinfo` was removed and replaced with a session ID, displayed at startup. This session ID (e.g., 52) is used as a suffix for session logging files.
- A particular scenario generator was added, so as to help designing scenarios of progressive difficulty.
- Each task module now logs a series of performance metrics as soon as they are available, to facilitate further calculations.
