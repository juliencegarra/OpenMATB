# OpenMATB — Tutorial + Experiment Reference

This guide is split into two parts:

1. **Tutorial:** run your first participant from start to finish.
2. **Experiment specifics:** exact behavior of Streams A, B, and C.

---

## Part 1 — First run tutorial (step by step)

## 1) What you are running

OpenMATB in this repository supports three experiment streams:

- **A**: replication stream
- **B**: within-subject stream (two 25-minute conditions)
- **C**: between-subject stream (one 30-minute condition)

Across all streams, participants begin with an instruction phase:

- subtask instruction trials (**1 minute per subtask**), then
- a combined low-load instruction block (**2 minutes**).

After each combined instruction block, the runner prints subtask accuracies and asks if the instruction session should be repeated.

---

## 2) Prerequisites

Before running participants:

1. Install dependencies from [requirements.txt](requirements.txt).
2. Confirm you are in the repository root (same folder as [run_experiment.py](run_experiment.py)).

---

## 3) Choose your stream and participant ID

Pick:

- one stream: `A`, `B`, or `C`
- one integer participant ID (example: `501`)

Use a **new** participant ID for each participant so outputs never overwrite each other.

---

## 4) Generate scenarios (do this before running)

Run the stream-specific scenario generator:

- Stream A: `python -m scenario_generators.expA`
- Stream B: `python -m scenario_generators.expB`
- Stream C: `python -m scenario_generators.expC`

Tip: if you are unsure which stream you will run next, generate all three once.

---

## 5) Edit config.ini

Open [config.ini](config.ini) and set at minimum:

```ini
experiment=A|B|C
participant_id=<integer>
```

Then set stream-specific fields if needed:

- For B: `stream_b_order=auto|low-high|high-low`
- For C: `stream_c_condition=auto|low|high`

Example for Stream B:

```ini
experiment=B
participant_id=101
stream_b_order=auto
```

---

## 6) Start the run

Launch:

`python run_experiment.py`

During the run:

1. Follow on-screen prompts.
2. Complete instruction phase first.
3. Decide whether to repeat instruction if prompted.
4. Continue through baseline/practice/calibration/experimental blocks (depends on stream).
5. Administer NASA-TLX when prompted.

---

## 7) Verify outputs after the run

Check participant output folder:

- `sessions/participant_<ID>/`

You should see:

- per-block session CSV logs
- per-block communications logs
- for B/C: participant capacity fit JSON (details below)

If output files exist and timestamps match your run, the session was captured correctly.

---

## 8) Fast troubleshooting checklist

- Wrong stream running? Re-check `experiment` in [config.ini](config.ini).
- Missing B/C condition behavior? Re-check `stream_b_order` or `stream_c_condition`.
- No new outputs? Confirm `participant_id` and write access to [sessions/](sessions/).
- Unexpected sequence? Make sure scenarios were generated for the selected stream.

---

## Part 2 — Experiment-specific details

## Experiment A (replication)

### Sequence

- **Instruction phase**
  - `expA_instructions_subtasks.txt`
  - `expA_instructions_combined_L.txt`
- **Baseline phase**: 3 blocks × 2 minutes (counterbalanced L/M/H)
- **Experimental phase**: 3 blocks × 8 minutes (same order as baseline)
- **NASA-TLX**: after each experimental block
- **Break reminder**: 5 minutes between baseline and experimental phases

### Run settings

- Generate scenarios: `python -m scenario_generators.expA`
- In [config.ini](config.ini):
  - `experiment=A`
  - `participant_id=<ID>`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment B (within-subject, 25 + 25)

### Sequence

- Instruction phase (stream-specific files; same structure as A)
- Practice block: 10 minutes (integrated moderate load)
- Integrated calibration: 8 minutes (4 × 2-minute segments)
- Baseline anchor: 2 minutes at low load
- Two experimental blocks: 25 minutes each (low and high, counterbalanced)
- NASA-TLX after each experimental block
- 8–10 minute break reminder between the two experimental blocks

### Calibration model and automatic personalization

The generator/runner uses a scalar load multiplier `m` to scale integrated task demand.

Calibration segments use:

- `m_values = [0.70, 0.85, 1.00, 1.15]`
- 4 segments × 2 minutes
- all subtasks ON
- scripted comm prompts in final 30 seconds of each segment

For Stream B (and C), participant capacity is estimated from **practice**:

1. Compute composite practice score `S_practice` from:
   - Track point accuracy
   - ResMan point accuracy
   - SysMon point accuracy
   - Comms point accuracy
2. Use target score `S_target = 0.75`
3. Estimate

$$
m^* = 0.85 \cdot \frac{S_{practice}}{S_{target}}
$$

and clamp to `[0.60, 1.20]`.

4. Derive
   - `m_high = m*`
   - `m_low = 0.80 * m*` (clamped)

The runner then auto-generates participant-specific B scenarios and routes upcoming B experimental blocks to those files.

### Run settings

- Generate scenarios: `python -m scenario_generators.expB`
- In [config.ini](config.ini):
  - `experiment=B`
  - `participant_id=<ID>`
  - `stream_b_order=auto|low-high|high-low`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`
- Capacity fit JSON:
  - `sessions/participant_<ID>/<ID>_B_capacity_fit.json`

---

## Experiment C (between-subject, 30)

### Sequence

- Instruction phase (stream-specific files; same structure as A)
- Practice block: 10 minutes
- Integrated calibration block: 8 minutes
- Baseline anchor: 2 minutes
- One experimental block: 30 minutes (low **or** high)
- NASA-TLX after the experimental block

### Calibration and condition assignment

Stream C uses the same automatic practice-based capacity estimation pipeline as B (`m*`, `m_low`, `m_high`).

Condition control:

- `stream_c_condition=auto|low|high`

If `auto`, assignment is deterministic from participant ID for reproducibility.

The runner auto-generates personalized 30-minute low/high scenario files after practice.

### Run settings

- Generate scenarios: `python -m scenario_generators.expC`
- In [config.ini](config.ini):
  - `experiment=C`
  - `participant_id=<ID>`
  - `stream_c_condition=auto|low|high`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`
- Capacity fit JSON:
  - `sessions/participant_<ID>/<ID>_C_capacity_fit.json`

---

## Configuration quick reference

In [config.ini](config.ini):

- `experiment=A|B|C`
- `participant_id=<int>`
- `stream_b_order=auto|low-high|high-low`
- `stream_c_condition=auto|low|high`

Capacity-related metadata can remain in config for traceability.
For B/C, active participant-specific fit values are computed from practice and written to participant JSON output files under `sessions/participant_<ID>/`.




