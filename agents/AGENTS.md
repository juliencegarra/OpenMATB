# OpenMATB Agents

## Architecture

All agents inherit from `AbstractAgent` (`abstract_agent.py`).
When a plugin has `automaticsolver=True`, the scheduler calls `agent.on_plugin_update(plugin, scenario_time)` on every plugin update cycle.

### Common attributes (AbstractAgent)

| Attribute             | Type   | Description                                                                  |
|-----------------------|--------|------------------------------------------------------------------------------|
| `name`                | `str`  | Internal identifier (`"default"`, `"assisted"`, etc.)                        |
| `automode_string`     | `str`  | Text displayed in the UI when `displayautomationstate=True`                  |
| `allows_human_input`  | `bool` | If `True`, the human can interact even when `automaticsolver=True`           |

### Abstract methods

- **`on_plugin_update(plugin, scenario_time)`** -- Called every cycle for each plugin with `automaticsolver=True`.
- **`on_failure_started(plugin, gauge)`** -- Called when a sysmon failure starts. Returns `{"delay": N}` to set the safety-net timer (ms).

### Utility methods

- **`send_key(plugin, keystr, state="press")`** -- Injects an emulated key event into the plugin. Logs the input for replay.
- **`send_joystick(plugin, x, y)`** -- Injects analog joystick input (values in [-1, 1]).

### Registry (`__init__.py`)

```
"default"      -> DefaultAgent
"assisted"     -> AssistedAgent
"cooperative"  -> CooperativeAgent
"supervisory"  -> DefaultAgent  (alias)
"humanlike"    -> HumanLikeAgent
"actr"         -> ACTRAgent
```

Scenario command: `0:00:00;system;agent;assisted`

---

## DefaultAgent / Supervisory

**File**: `default_agent.py`
**Registry**: `"default"`, `"supervisory"`
**Display**: `AUTO`
**`allows_human_input`**: `False` -- the human is fully offloaded

Reproduces the original `automaticsolver` behavior through key and joystick injection. The human has nothing to do; keyboard/mouse inputs are blocked.

### Sysmon

- Waits `automaticsolverdelay` ms after a failure starts.
- Injects the corresponding key (`F1`-`F6`) via `send_key()`.
- Resolves all failures (scales and lights) without exception.

### Track

- Every cycle, reads the cursor's relative position (`reticle.cursor_relative`).
- Computes direction toward center: `jx = 1.0` if cursor is left, `-1.0` otherwise; `jy` inverted.
- Injects via `send_joystick()`. Binary compensation (all-or-nothing).

### Resman

- Waits for the initial `wait_before_leak` to elapse.
- For each pump not in failure, calls `_compute_desired_pump_state()`:
  - **Heuristic 1**: Activate pumps draining non-depletable tanks (E, F).
  - **Heuristic 2**: Activate/deactivate based on target tank vs level deviation (threshold +-50).
  - **Heuristic 3**: Balance between tanks A and B.
- If desired state differs from current state, injects `send_key()` to toggle.

### Communications

- Takes the first radio waiting for a response (`get_waiting_response_radios()`).
- If the active radio is not the right one: injects UP/DOWN to navigate.
- If the frequency is wrong: injects LEFT/RIGHT to tune by 0.1 MHz steps.
- If both match: injects ENTER to validate.

---

## AssistedAgent

**File**: `assisted_agent.py`
**Registry**: `"assisted"`
**Display**: `ASSISTED`
**`allows_human_input`**: `True` -- the human acts, the agent shows

Provides visual cues only. **Never** injects keys or joystick. The human must detect, decide, and act.

### Sysmon

- Iterates over scale gauges (`get_scale_gauges()`).
- If `_onfailure=True`: sets `scale["_hint_arrow_color"] = RED`.
- Otherwise: resets to `None` (black arrow by default).
- **Visual result**: the arrow of the failing scale turns red.

### Track

- One-time setup (runs once):
  - `cursorcolor = BLUE` (cursor inside the target).
  - `cursorcoloroutside = RED` (cursor outside the target).
- **Visual result**: the cursor changes color based on its position.
- The human compensates with the joystick (force and axis unchanged).

### Resman

- Reuses `DefaultAgent._compute_desired_pump_state()` to determine which pumps need toggling.
- If desired state differs from current state: sets `pump["_hint_color"] = CYAN`.
- Otherwise: resets to `None` (normal color).
- **Visual result**: pumps requiring action are colored cyan (distinct from failure RED).
- Pumps in failure state receive no hint.

### Communications

- Iterates over waiting radios (`get_waiting_response_radios()`).
- Waiting radio: `radio["_hint_color"] = CYAN` (cyan frame around the radio).
- Other radios: `_hint_color = None`.
- **Visual result**: the target radio is highlighted with a cyan frame.
- The human must select the radio, tune the frequency, and validate.

---

## CooperativeAgent

**File**: `cooperative_agent.py`
**Registry**: `"cooperative"`
**Display**: `COOP`
**`allows_human_input`**: `True` -- the human acts with assistance, the agent simplifies

Modifies task parameters to simplify controls AND provides visual cues. **Never** injects keys or joystick.

### Sysmon

- One-time setup (runs once):
  - `allowanykey = True`: the SPACE key can resolve any failure.
  - Adds `"SPACE"` to `plugin.keys`.
- Visual cues: identical to AssistedAgent (red arrows on failures).
- **Result**: the human no longer needs to memorize F1-F6. A single SPACE resolves the first active failure.
- **`allowanykey` mechanism**: in `sysmon.do_on_key()`, if SPACE is pressed and `allowanykey=True`, the first failure from `get_gauges_on_failure()` is resolved with `stop_failure(success=True)`.

### Track

- One-time setup: `joystickforce = 10` (x10 compared to the default value of 1).
- **Result**: any joystick input toward the center is amplified, ensuring rapid cursor return. The human only needs a slight movement.
- Joystick reset is disabled (`allows_human_input=True` prevents the reset to zero in `track.compute_next_plugin_state()`).

### Resman

- Same logic as AssistedAgent but with `pump["_hint_color"] = YELLOW` instead of RED.
- **Visual result**: pumps requiring action are colored yellow.

### Communications

- Visual cues: `radio["_hint_color"] = YELLOW` on waiting radios.
- **Auto-selection**: the agent automatically switches `is_active` to the first waiting radio if it is not already active.
- **Result**: the human no longer needs to navigate with UP/DOWN. They only need to tune the frequency (LEFT/RIGHT) and validate (ENTER).

---

## HumanLikeAgent

**File**: `humanlike_agent.py`
**Registry**: `"humanlike"`
**Display**: `AUTO-HL`
**`allows_human_input`**: `False`

Simulates a realistic human operator using a central attention model. Unlike the DefaultAgent, this agent cannot monitor all 4 tasks simultaneously.

### Attention model

- **Sequential scan**: cycles through tasks in order `[sysmon, track, resman, communications]`.
- **Fixation duration**: Gaussian, mean 3000 ms, std 1000 ms (Sarter & Woods, 1995).
- **Switching cost**: 300 ms delay when changing tasks (Monsell, 2003).
- **Bottom-up interrupt**: sysmon failures capture attention with probability 0.8 (Yantis & Jonides, 1990).
- **Idle-switch**: if the current task is idle and a salient event exists elsewhere, early switch after 500 ms minimum.
- **Persistence**: stays on the current task while active work remains (max 10 s).
- **Visual indicator**: `show_attention=True` displays a cyan border on the attended task.

### Sysmon

- Only acts if `_attended_task == "sysmon"`.
- Log-normal reaction time: mean 2500 ms, std 800 ms (Comstock & Arnegard, 1992).
- **Vigilance decrement**: +50 ms per detected failure (Warm et al., 2008).
- Injects the corresponding key after the delay.
- Unattended failures expire (MISS).

### Track

- Only acts if `_attended_task == "track"`.
- **Reaction delay**: 400 ms before initiating a correction (Welford, 1980).
- **Motor noise**: 15% probability of micro-hesitation per frame (Poulton, 1974).
- **Proportional compensation**: gain=4.0, force proportional to distance from center, clamped to [-1, 1].
- **Settling phase**: maintains a minimum force of 0.3 for 2000 ms after entering the target.
- The cursor drifts when the agent is looking elsewhere.

### Resman

- Only acts if `_attended_task == "resman"`.
- Reuses `DefaultAgent._compute_desired_pump_state()` with Gaussian noise (std=75) on thresholds.
- **Omission error**: 5% probability of missing an identified action (Reason, 1990).

### Communications

- Only acts if `_attended_task == "communications"`.
- **Comprehension delay**: 1500 ms after the audio prompt ends.
- **Tuning interval**: 200 ms between each frequency step (Card, Moran & Newell, 1983).
- **Overshoot**: 10% probability of overshooting the target frequency (Fitts, 1954).
- The reaction persists across visits (if the prompt was heard, the agent remembers on return).

---

## ACTRAgent

**File**: `actr_agent.py`
**Registry**: `"actr"`
**Display**: `AUTO-ACTR`
**`allows_human_input`**: `False`

Model based on the ACT-R cognitive architecture. Reference: Swan, Stevens, Fisher & Klosterman (2022) -- "Exploring Multitasking Strategies in an ACT-R model of a Complex Piloting Task".

### Constructor parameters

| Parameter    | Default | Description                                                            |
|--------------|---------|------------------------------------------------------------------------|
| `seed`       | `None`  | Random seed for reproducibility                                        |
| `bottom_up`  | `"LR"`  | Subtasks with bottom-up selection. L=Lights, G=Gauges, R=Resource, T=Tracking |
| `top_down`   | `True`  | Enable serial clockwise scanning. `False` = purely reactive            |

### ACT-R constants

- **Production cycle**: 50 ms
- **Peripheral detection**: 3.0 s (delay before a bottom-up stimulus triggers an interrupt)
- **Motor execution**: 250 ms per action
- **Motor error**: 5% probability of pressing the wrong key

### Attention model

- **Top-down scan**: cycles through 5 subtasks in order `[sysmon_lights, sysmon_gauges, tracking, resman, communications]`.
- Sysmon is split into 2 subtasks (lights vs gauges) as per the ACT-R model.
- **Scan advance**: moves to the next subtask when there is no pending work, with a minimum of 100 ms.
- **Bottom-up interrupts**: configurable per subtask via the `bottom_up` parameter. Detection after `VISUAL_ONSET_SPAN_S` (3 s). Priority: lights > gauges > resman > tracking.
- **Visual indicator**: `show_attention=True`.

### Declarative memory (Communications)

- ACT-R base-level learning model: decay=0.5, noise=0.2 (logistic), constant=2.0, threshold=2.9.
- When an audio prompt ends, the agent attempts a memory retrieval. If activation + noise > threshold, the target frequency is memorized and the agent switches to communications.
- If retrieval fails, the agent does not process that prompt (it forgets it).

### Sysmon (Lights + Gauges)

- Handles lights and gauges separately based on the attended subtask.
- Immediate detection when attention is on the matching subtask.
- Injects the key with motor execution (250 ms blocking).

### Track

- Proportional compensation: gain=0.125, max 10 px per update.
- Gaussian noise on joystick output (std=0.03).
- Only acts if `_attended == "tracking"`.

### Resman

- **Initialization**: activates the first 6 pumps sequentially at startup (250 ms between each).
- **Monitoring**: evaluates deviations of tanks A and B from targets.
  - Action threshold (attended): 100 units of deviation.
  - Bottom-up threshold: 700 units of deviation.
- Builds a pump action queue, executed sequentially with motor delay.

### Communications

- Parallel audio monitoring: detects completed prompts regardless of the scan.
- Attempts declarative memory retrieval for each new prompt.
- If retrieval succeeds: immediate switch to communications.
- Tuning: 4 production cycles (200 ms) between each action (navigation, tuning, validation).

---

## Comparison table

| Property                   | Default/Supervisory | Assisted          | Cooperative       | HumanLike         | ACT-R             |
|----------------------------|---------------------|-------------------|-------------------|-------------------|-------------------|
| **Human input**            | Blocked             | Allowed           | Allowed           | Blocked           | Blocked           |
| **Key injection**          | Yes                 | No                | No                | Yes               | Yes               |
| **Joystick injection**     | Yes                 | No                | No                | Yes               | Yes               |
| **Visual cues**            | No                  | Yes               | Yes               | No                | No                |
| **Simplification**         | N/A (fully auto)    | No                | Yes               | N/A (fully auto)  | N/A (fully auto)  |
| **Limited attention**      | No (omniscient)     | N/A               | N/A               | Yes (scan)        | Yes (ACT-R scan)  |
| **Human errors**           | No                  | N/A               | N/A               | Yes               | Yes               |
| **`automode_string`**      | `AUTO`              | `ASSISTED`        | `COOP`            | `AUTO-HL`         | `AUTO-ACTR`       |

### HMCM modes (Navarro et al., 2021)

| HMCM mode        | Agent           | Description                                        |
|------------------|-----------------|----------------------------------------------------|
| Manual           | none            | `automaticsolver=False` (default)                  |
| Assisted         | `assisted`      | Visual cues only                                   |
| Cooperative      | `cooperative`   | Simplified controls + visual cues                  |
| Supervisory      | `supervisory`   | Full automation (= `default`)                      |
