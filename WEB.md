# OpenMATB in a web browser

OpenMATB also runs in a web browser, with no installation for participants: the same scenario files, plugins and
session files as the desktop version (see the [README](README.md)). A demo runs on the
[website](https://juliencegarra.github.io/OpenMATB/). The code of the web version is in `web/`; `core/pyglet_compat.py`
holds the differences between pyglet 3, used in the browser, and pyglet 2, used on desktop.

## Building and hosting

OpenMATB can also run in a web browser, with no installation for participants: Python runs in the page thanks to [Pyodide](https://pyodide.org) and pyglet 3 draws with WebGL. To build and test it locally:

```bash
python web/build.py --serve
```

Then open http://localhost:8000. `web/build.py` writes a static site into `web/dist` (the application files, the pyglet and rstr wheels, and a font), which can be hosted on any web server (the page must be served over HTTP, `file://` does not work). The start page lets you choose the language, run a scenario or replay a session. These choices can also be given in the URL: `?lang=fr_FR`, `?scenario=basic.txt`, `?mode=replay`, `?session=12`. `?demo=1` runs the demo scenario (`includes/scenarios/demo.txt`: English voice, no questionnaire, mouse control) without recording anything: it is the Demo tab of the website.

Differences with the desktop version:

- **Session files** are downloaded at the end of the session by default, or sent to a server (see [Collecting the session files](#collecting-the-session-files)). They are also kept in the browser storage (IndexedDB), so they can be replayed later from the same browser. A session file can also be imported from the start page to be replayed. In replay mode, the start page lists the sessions kept in the browser: each one can be downloaded again or deleted, and all of them can be deleted at once.
- **The scenario is paused** when the page is hidden (tab change, minimized window), because browsers slow down hidden pages. The `visibility` entries of the session file record when it happened.
- **Joysticks** (e.g. flight joysticks) are read with the browser Gamepad API: the main stick axes control the tracking task and buttons are available as `JOY_BTN_n`. Browsers reveal a joystick only once one of its buttons has been pressed: the start page shows the detected joystick.
- The **parallel port** is replaced by a USB trigger box, and **Lab Streaming Layer** goes through a bridge (see [Psychophysiology in the browser](#psychophysiology-in-the-browser-triggers-lsl-clocks)).
- **Sound** starts after the first click (the "Start" button), as required by browsers.
- **Timing**: response times to human inputs are measured as in PsychoJS and lab.js. They start at the drawing of the first frame showing the stimulus (the display is refreshed by the browser, `requestAnimationFrame`) for sysmon failures, and at the clock tick when the message ends for communications. They end at the timestamp given by the browser to the key or click (`event.timeStamp`), even when the page handles it later. Both use the browser clock (`performance.now`), whose resolution browsers reduce (to about 0.1 ms in Chrome, 1 ms in Firefox). The latencies of the screen and of the keyboard or mouse (typically 10 to 40 ms, depending on the computer) are not measured. Take it into account for time-critical experiments.
- **Browsers**: use **Chrome or Edge** for experiments. They are tested with Firefox and Safari's engine (WebKit) too, but **Firefox pauses the page for 0.1 to 1 s every few seconds** (garbage collection, notably when the user has not interacted for a few seconds), which delays updates and responses. Timing studies of online experiment platforms also found Firefox the most variable browser ([Anwyl-Irvine et al., 2021](https://doi.org/10.3758/s13428-020-01501-5)). The start page displays a notice in Firefox; `web_browser_check` in `config.ini` sets this check: `warn` (default), `block` (Firefox cannot start) or `off`. It can also be set in the URL: `?browsercheck=block`.
- **Session file**: it records the browser, its version and the system (`browser`, `os` and `useragent` entries), and every pause of the page longer than 100 ms (`freeze` entries: the duration in ms, at the scenario time when the page stopped), so that the affected periods can be excluded from the analysis. The replay shows the browser and the system of the session, marks on the timeline the periods when the page was hidden (orange) and the pauses of the page (red), and displays a banner while the page was hidden or the session paused.

## Collecting the session files

The web version is a static site: by default, the session file is downloaded on the participant's computer. It can
instead (or also) be sent to a server, set by `web_session_output` in `config.ini` (a comma separated list):

| `web_session_output` | Where the file goes | When |
|---|---|---|
| `download` (default) | Downloaded on the participant's computer | At the end |
| `webdav` | A folder of a web server, with the desktop structure: `<web_webdav_url>/YYYY-MM-DD/<N>_<yymmdd>_<hhmmss>.csv` | Every 10 s and at the end |
| `jatos` | [JATOS](https://www.jatos.org), as a compressed result file (`.csv.gz`) of the study run | Every 10 s and at the end |
| `datapipe` | Google Drive, Dataverse or Zenodo, through [DataPipe](https://pipe.jspsych.org), as a compressed file (`.csv.gz`) | At the end |
| `none` | Nowhere: only kept in the browser storage | |

For example `web_session_output=webdav, download` sends the file to the server and also downloads it. The end page
tells the participant where the file went. If it could not be sent anywhere, it is downloaded instead. Sending the
file every 10 s keeps the data of a session interrupted by a closed tab or a crash.

- **WebDAV** (`web_webdav_url=https://lab.example.org/openmatb/sessions/`): a folder of an Apache (`mod_dav`), nginx
  (`dav_methods`) or Nextcloud server that accepts `PUT` (and `MKCOL` for the day folders). Allow only these methods on
  this folder (no reading, listing or deleting by the participants), and limit the file size (a session writes about
  70 MB of CSV per hour). Serve it from the same server as the page, or allow CORS for `PUT`, `MKCOL` and the `If-None-Match` header.
  A file is never overwritten by another session: if the name is already used, the session is sent as `<name>_2.csv`.
  The session numbers are those of the browser, which can be the same for two participants.
- **JATOS**: upload the files of `web/dist` as the files of a JATOS study (one HTML component, `index.html`). The
  session file is saved as a gzip result file, `<N>_<yymmdd>_<hhmmss>.csv.gz`, replaced every 10 s, and the study run
  is ended at the end of the session (JATOS end page, or the end redirect set in JATOS, e.g. to Prolific). The result
  data only holds a summary (`{"file", "state": "running" | "finished", "scenario_time", "csv_bytes"}`), to follow the
  sessions in the JATOS result pages. The file is compressed because of the JATOS limits (by default 5 MB of result
  data, 30 MB per result file and 50 MB per study run): a session writes about 70 MB of CSV per hour, about 14 MB once
  compressed. The `.csv.gz` files can be imported as they are in the replay (start page), or decompressed with any
  archive tool (7-Zip, `gunzip`, `pandas.read_csv` reads them directly). The page must be run from JATOS: it loads
  `jatos.js` from there.
- **DataPipe** (`web_datapipe_experiment=<experiment ID>`): connect a storage provider to your account on
  https://pipe.jspsych.org (Google Drive, Dataverse or Zenodo; DataPipe stops writing to OSF after November 16, 2026),
  create the experiment and enable its **base64 data collection** (the compressed file is sent as base64; the text
  data collection is not used). When a session starts, OpenMATB checks, without sending a file, that DataPipe
  accepts the files of the experiment: otherwise the session does not start and the reason is shown. This check sends
  invalid data on purpose, so each session leaves an `INVALID_BASE64_DATA` error in the DataPipe logs of the
  experiment when it starts: it is expected. The "completed sessions" count of DataPipe stays at 0: it counts the
  sessions of its incremental API, which OpenMATB does not use. The site can then be hosted anywhere, e.g. on GitHub
  Pages. The
  file is sent at the end of the session only, compressed, as `<N>_<yymmdd>_<hhmmss>_<random>.csv.gz`: DataPipe accepts
  32 MB per request (about 1 h 40 of session once compressed), and the random suffix keeps two sessions with the same
  name from replacing each other (Zenodo replaces an existing file silently). With Zenodo, the files go to an
  unpublished (private) deposition, which holds at most 100 files: DataPipe merges the sessions into archives as the
  collection goes on. Publishing it makes it public, with a DOI, and it can no longer be changed.

## Running OpenMATB from an LMS (SCORM)

OpenMATB can be imported as an activity into a learning management system (Moodle, Canvas, Blackboard, SCORM
Cloud...):

```bash
python web/build.py --scorm        # SCORM 1.2 (supported by every LMS): web/openmatb_scorm_1.2.zip
python web/build.py --scorm 2004   # SCORM 2004 4th edition: web/openmatb_scorm_2004.zip
```

The package contains `web/dist` and Pyodide (about 12 MB), because LMSs often block scripts from other sites
(`--pyodide cdn` loads it from its CDN instead; `--pyodide local` also works without SCORM, to host Pyodide with the
page). Set `config.ini` (scenario, `web_session_output`...) before building: it is part of the package.

In the LMS, the start page only offers to run the scenario. The LMS records that the activity was started
(`incomplete`), then `completed` at the end of the session, the time spent, and the name of the session file as the
lesson location (`cmi.core.lesson_location`, `cmi.location` in SCORM 2004), to match each learner with their file.
**The session file itself is not stored in the LMS**: SCORM only keeps a few kB per learner, while a session file is a
tens of MB (about 70 MB per hour). It goes where `web_session_output` says, e.g. `webdav` or `datapipe`, which must accept requests from the
LMS site (CORS). Open the activity in a new window if the LMS frame prevents the fullscreen or the joystick.

## Running OpenMATB from a cmi5 LMS (xAPI)

[cmi5](https://aicc.github.io/CMI-5_Spec_Current/) is the successor of SCORM: the LMS launches the page with the
address of its Learning Record Store (LRS), and the page sends it xAPI statements. It is supported by Moodle (cmi5
plugin), SCORM Cloud, Rustici Engine, Cornerstone, Docebo...

```bash
python web/build.py --cmi5         # web/openmatb_cmi5.zip (cmi5.xml + web/dist + Pyodide)
```

Import the zip file as a cmi5 course (one assignable unit, `moveOn="Completed"`). As with SCORM, set `config.ini`
before building, and the start page only offers to run the scenario. The LRS receives:

- `initialized` when the page opens;
- `completed` at the end of the session, with its duration and the name of the session file as a context extension
  (`https://github.com/juliencegarra/OpenMATB/xapi/extensions/session-file`), to match each learner with their file.
  It is not sent when the LMS opens the activity in `Browse` or `Review` mode (cmi5 forbids it);
- `terminated` at the end of the session, or when the page is closed; then the page goes back to the course
  (`returnURL` of the LMS).

If the learner did not choose a language (`?lang=`), the language preference of their LMS profile
(`cmi5LearnerPreferences`) is used. The LMS gives its access token only once: a reloaded page cannot record anything
and says so instead of starting (launch the activity again from the LMS). The session file itself goes where
`web_session_output` says, as with SCORM.

## Psychophysiology in the browser (triggers, LSL, clocks)

Browsers cannot reach a parallel port or Lab Streaming Layer directly. The web version offers instead:

- **USB trigger box** (`parallelport` plugin, **Chrome or Edge**): with `web_serial_trigger=True`, the values of the
  plugin are written as one byte to a serial port (Web Serial API), which the box outputs on its 8 lines until the next
  value, as a parallel port does: Brain Products TriggerBox, BioSemi USB trigger interface, Neurospec MMBT-S, an
  Arduino... The scenarios do not change (`parallelport;trigger;5`, `delayms`). The port is chosen once on the start
  page ("Choose the port"), and the browser remembers the permission; `web_serial_baudrate` sets its speed (ignored
  by most USB boxes). Each value stays at least `delayms` before the next one, even though the browser runs the
  scenario every 8 to 16 ms (the value and its reset would otherwise be written together). The session does not
  start if the port is not chosen or cannot be opened; the end page shows how many values were written.
- **Lab Streaming Layer**, through a bridge (`labstreaminglayer` plugin): run on the participant's computer

  ```bash
  pip install pylsl
  python web/lsl_bridge.py           # ws://127.0.0.1:8766 (--origin https://your.site to accept only your pages)
  ```

  and set `web_lsl_bridge=ws://127.0.0.1:8766`. The bridge creates the same `OpenMATB` marker stream as the desktop
  version (`marker` and `streamsession` work the same), recorded with LabRecorder. It only needs the Python standard
  library and `pylsl`. The session does not start if the bridge does not answer. Markers sent while the bridge is
  briefly disconnected are kept and sent, with their original time, when it is back. Chrome may ask the permission
  to access the devices of the local network (a page from a web server connecting to `127.0.0.1`): allow it.
- **Clocks**: the `logtime` column of a web session file is `performance.now()` in seconds (the page clock, 0.1 ms
  resolution in Chrome). The `timeorigin` entry is the Unix time of `logtime` 0, so the Unix time of a row is
  `timeorigin + logtime` (with the accuracy of the computer clock). With the LSL bridge, each marker carries its page
  time and the bridge stamps it in LSL time: it measures the offset between both clocks like NTP (it sends its time,
  the page answers at once, the exchange with the shortest round trip wins; typically well below 1 ms on the same
  computer), so neither the WebSocket nor the browser loop delays the recorded times. The offset is logged in the
  session file (`lsl_offset` entries, when it changes by 0.1 ms or more), so that any row can be put in LSL time:
  `logtime - lsl_offset`, e.g. to align the whole session file with an XDF recording.
