# OpenMATB Instructions

This repository supports three experimental streams: **A**, **B**, and **C**.

Common to all streams, participants complete:
- instruction subtasks (1 minute per subtask), then
- a 2-minute combined low-load instruction block.

After each combined instruction block, the runner prints subtask accuracies and asks whether to repeat the instruction session.

---

## Experiment A (replication)

### What it runs
- Instruction phase:
  - `expA_instructions_subtasks.txt`
  - `expA_instructions_combined_L.txt`
- Baseline phase: 3 blocks × 2 minutes (counterbalanced L/M/H)
- Experimental phase: 3 blocks × 8 minutes (same order as baseline)
- NASA-TLX after each experimental block
- 5-minute break reminder printed between baseline and experimental phases

### How to run
1. Generate scenarios:
	- `python -m scenario_generators.expA`
2. Set in [config.ini](config.ini):
	- `experiment=A`
	- `participant_id=<ID>`
3. Run:
	- `python run_experiment.py`

### Logging
- Per-block session CSVs: `sessions/participant_<ID>/`
- Per-block comms logs: `sessions/participant_<ID>/`

---

## Experiment B (within-subject, 25 + 25)

### What it runs
- Instruction phase (same structure as A, stream-specific files)
- Practice block: 10 minutes, integrated moderate load
- Integrated calibration block: 8 minutes (4 × 2-minute segments)
- Baseline anchor: 2 minutes at very low load
- Two experimental blocks: 25 minutes each, low and high (counterbalanced)
- NASA-TLX after each experimental block
- 8–10 minute break reminder printed between the two experimental blocks

### Calibration and parameters (B)

#### Integrated load multiplier
The generator defines a scalar multiplier `m` that scales integrated demand across subtasks.

Calibration uses:
- `m_values = [0.70, 0.85, 1.00, 1.15]`
- 4 segments × 2 minutes each
- all subtasks ON
- scripted comm prompts in the final 30 seconds of each segment

#### Practice-based automatic capacity estimation
For Streams B/C, the runner now automatically estimates participant capacity from the **practice block**:

1. Compute practice composite score `S_practice` from:
	- Track point accuracy
	- ResMan point accuracy
	- SysMon point accuracy
	- Comms point accuracy
2. Use target score `S_target = 0.75`
3. Estimate:
	- `m* = 0.85 * (S_practice / S_target)`
	- clamp to `[0.60, 1.20]`
4. Derive:
	- `m_high = m*`
	- `m_low = 0.80 * m*` (clamped)

The runner then generates participant-specific experimental scenario files automatically and routes upcoming B experimental blocks to those files.

Capacity fit output is saved to:
- `sessions/participant_<ID>/<ID>_B_capacity_fit.json`

### How to run
1. Generate scenarios:
	- `python -m scenario_generators.expB`
2. Set in [config.ini](config.ini):
	- `experiment=B`
	- `participant_id=<ID>`
	- `stream_b_order=auto|low-high|high-low`
3. Run:
	- `python run_experiment.py`

---

## Experiment C (between-subject, 30)

### What it runs
- Instruction phase (same structure as A, stream-specific files)
- Practice block: 10 minutes
- Integrated calibration block: 8 minutes
- Baseline anchor: 2 minutes
- One experimental block: 30 minutes (low or high)
- NASA-TLX after the experimental block

### Calibration and parameters (C)

Uses the same multiplier and practice-based automatic capacity estimation pipeline as Stream B.

After practice, runner estimates `m*`, `m_low`, and `m_high`, writes a participant fit JSON, and auto-generates personalized 30-minute low/high scenarios.

Assignment is controlled by:
- `stream_c_condition=auto|low|high`

If `auto`, the runner uses deterministic participant-based assignment for reproducibility.

Capacity fit output is saved to:
- `sessions/participant_<ID>/<ID>_C_capacity_fit.json`

### How to run
1. Generate scenarios:
	- `python -m scenario_generators.expC`
2. Set in [config.ini](config.ini):
	- `experiment=C`
	- `participant_id=<ID>`
	- `stream_c_condition=auto|low|high`
3. Run:
	- `python run_experiment.py`

---

## Config quick reference

In [config.ini](config.ini):
- `experiment=A|B|C`
- `participant_id=<int>`
- `stream_b_order=auto|low-high|high-low`
- `stream_c_condition=auto|low|high`

Capacity-related metadata fields are available in config for traceability, while the active B/C participant-specific values are now computed automatically from practice and stored in participant JSON outputs under `sessions/participant_<ID>/`.




