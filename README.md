# OpenMATB — Tutorial + Experiment Reference

This guide is split into two parts:

1. **Tutorial:** run your first participant from start to finish.
2. **Experiment specifics:** exact behavior of Experiments A, B, C, D, and E.

---

## Part 1 — First run tutorial (step by step)

## 1) What you are running

OpenMATB in this repository supports five experiment streams:

- **A**: replication stream (three 8-min experimental conditions — Low, Medium, High)
- **B**: within-subject stream, fixed difficulty (two 20-min experimental conditions — Low & High)
- **C**: between-subject stream, fixed difficulty (one 36-min experimental condition — Low or High)
- **D**: within-subject stream, calibrated difficulty (two 20-min personalized conditions)
- **E**: between-subject stream, calibrated difficulty (one 36-min personalized condition)

Across all streams, participants begin with an instruction phase:

- subtask instruction trials (**1 minute per subtask**, 4 min total), then
- a combined low-load instruction block (**2 minutes**).

After each combined instruction block, the runner prints subtask accuracies and asks if the instruction session should be repeated.

**B and C** use Experiment A's fixed difficulty: L (difficulty=0.4, comms=2), H (difficulty=0.7, comms=4). No calibration.

**D and E** use the same practice structure as B and C respectively, then estimate capacity from practice performance to generate personalized experimental scenarios.

---

## 2) Setup

### Python environment

Requires **Python 3.10+**. Create a virtual environment and install dependencies:

```bash
cd OpenMATB
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

Activate this environment each time before running experiments:

```bash
source venv/bin/activate        # macOS / Linux
```

### Verify setup

Confirm you are in the repository root (same folder as [run_experiment.py](run_experiment.py)):

```bash
python run_experiment.py --help   # should print without import errors
```

### Pre-generated scenarios

Scenario files for 200 participants per experiment are already included under `includes/scenarios/`. You do **not** need to run the generators — just set your experiment and participant ID in config.ini and go.

---

## 3) Choose your experiment and participant ID

Pick:

- one experiment: `A`, `B`, `C`, `D`, or `E`
- one integer participant ID

Use a **new** participant ID for each participant so outputs never overwrite each other.

Participant ID ranges:

| Experiment | Pre-generated IDs | Full ID Range |
|------------|-------------------|---------------|
| A | 1001–1200 | 1001–1999 |
| B | 2001–2200 | 2001–2999 |
| C | 3001–3200 | 3001–3999 |
| D | 4001–4200 | 4001–4999 |
| E | 5001–5200 | 5001–5999 |

---

## 4) (Optional) Generate additional scenarios

Scenarios for IDs shown above are **already included**. Only run generators if you need IDs beyond the pre-generated range:

```bash
python -m scenario_generators.expA   # Experiment A
python -m scenario_generators.expB   # Experiment B
python -m scenario_generators.expC   # Experiment C
python -m scenario_generators.expD   # Experiment D
python -m scenario_generators.expE   # Experiment E
```

Edit the `start_id` / `end_id` in each generator's `main()` to control the range.

---

## 5) Edit config.ini

Open [config.ini](config.ini) and set at minimum:

```ini
experiment=A|B|C|D|E
participant_id=<integer>
```

Then set experiment-specific fields if needed:

- For B: `stream_b_order=auto|low-high|high-low`
- For C: `stream_c_condition=auto|low|high`
- For D: `stream_d_order=auto|low-high|high-low`
- For E: `stream_e_condition=auto|low|high`

Example for Experiment D:

```ini
experiment=D
participant_id=4001
stream_d_order=auto
```

---

## 6) Start the run

Launch:

`python run_experiment.py`

During the run:

1. Follow on-screen prompts.
2. Complete instruction phase first.
3. Decide whether to repeat instruction if prompted.
4. Continue through baseline/practice and experimental blocks (depends on experiment).
5. Administer NASA-TLX when prompted.

---

## 7) Verify outputs after the run

Check participant output folder:

- `sessions/participant_<ID>/`

You should see:

- per-block session CSV logs
- per-block face camera videos (if `record_face=True`)
- for D/E: participant capacity fit JSON

If output files exist and timestamps match your run, the session was captured correctly.

---

## 8) Fast troubleshooting checklist

- Wrong experiment running? Re-check `experiment` in [config.ini](config.ini).
- Missing B/D order or C/E condition behavior? Re-check the stream-specific config fields.
- No new outputs? Confirm `participant_id` and write access to [sessions/](sessions/).
- Unexpected sequence? Make sure scenarios were generated for the selected experiment.

---

## Part 2 — Experiment-specific details

## Experiment A (replication — L/M/H)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline 1 (2 min, L/M/H counterbalanced)
Baseline 2 (2 min)
Baseline 3 (2 min)
—— 5-min break reminder ——
Experimental 1 (8 min, same order) + NASA-TLX
Experimental 2 (8 min) + NASA-TLX
Experimental 3 (8 min) + NASA-TLX
```

### Run settings

- Generate scenarios: `python -m scenario_generators.expA`
- In [config.ini](config.ini):
  - `experiment=A`
  - `participant_id=<ID>` (1001–1999)
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment B (within-subject, fixed difficulty)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline Pre 1 (2 min, L or H — same order as experimental)
Baseline Pre 2 (2 min, H or L)
—— 5-min break reminder ——
Experimental Block 1 (20 min, L or H — counterbalanced) + NASA-TLX
—— 5-min break reminder ——
Experimental Block 2 (20 min, H or L) + NASA-TLX
```

Uses Experiment A's fixed difficulty levels. No calibration, no capacity estimation.

### Run settings

- Generate scenarios: `python -m scenario_generators.expB`
- In [config.ini](config.ini):
  - `experiment=B`
  - `participant_id=<ID>` (2001–2999)
  - `stream_b_order=auto|low-high|high-low`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment C (between-subject, fixed difficulty)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline (4 min, same condition as experimental — L or H)
—— 5-min break reminder ——
Experimental Block (36 min, L or H — assigned) + NASA-TLX
```

Uses Experiment A's fixed difficulty levels. No calibration, no capacity estimation.

Condition control:

- `stream_c_condition=auto|low|high`
- If `auto`, assignment is deterministic from participant ID.

### Run settings

- Generate scenarios: `python -m scenario_generators.expC`
- In [config.ini](config.ini):
  - `experiment=C`
  - `participant_id=<ID>` (3001–3999)
  - `stream_c_condition=auto|low|high`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment D (within-subject, calibrated)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Practice 1 (4 min, L or H — same order as experimental)
Practice 2 (4 min, H or L)
→ Capacity estimation from practice performance
→ Generate personalized experimental scenarios
—— 5-min break reminder ——
Experimental Block 1 (20 min, personalized low) + NASA-TLX
—— 5-min break reminder ——
Experimental Block 2 (20 min, personalized high) + NASA-TLX
```

Practice blocks use fixed L/H difficulty. After both practice blocks, the runner estimates participant capacity (m*) and generates personalized experimental scenarios at calibrated low and high difficulty levels.

### Run settings

- Generate scenarios: `python -m scenario_generators.expD`
- In [config.ini](config.ini):
  - `experiment=D`
  - `participant_id=<ID>` (4001–4999)
  - `stream_d_order=auto|low-high|high-low`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`
- Capacity fit JSON: `sessions/participant_<ID>/<ID>_D_capacity_fit.json`

---

## Experiment E (between-subject, calibrated)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Practice (4 min, assigned condition — L or H)
→ Capacity estimation from practice performance
→ Generate personalized experimental scenario
—— 5-min break reminder ——
Experimental Block (36 min, personalized low or high) + NASA-TLX
```

Practice block uses fixed L or H difficulty. After practice, the runner estimates participant capacity and generates a personalized experimental scenario.

Condition control:

- `stream_e_condition=auto|low|high`
- If `auto`, assignment is deterministic from participant ID.

### Run settings

- Generate scenarios: `python -m scenario_generators.expE`
- In [config.ini](config.ini):
  - `experiment=E`
  - `participant_id=<ID>` (5001–5999)
  - `stream_e_condition=auto|low|high`
- Run: `python run_experiment.py`

### Outputs

- Session/log files: `sessions/participant_<ID>/`
- Capacity fit JSON: `sessions/participant_<ID>/<ID>_E_capacity_fit.json`

---

## Configuration quick reference

In [config.ini](config.ini):

| Field | Values | Applies to |
|-------|--------|------------|
| `experiment` | `A`, `B`, `C`, `D`, `E` | All |
| `participant_id` | integer | All |
| `stream_b_order` | `auto`, `low-high`, `high-low` | B |
| `stream_c_condition` | `auto`, `low`, `high` | C |
| `stream_d_order` | `auto`, `low-high`, `high-low` | D |
| `stream_e_condition` | `auto`, `low`, `high` | E |
| `record_face` | `True`, `False` | All |

Capacity calibration settings (D/E only) are in the calibration section of config.ini.
