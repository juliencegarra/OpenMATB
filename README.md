# OpenMATB — Experimenter Run Order Guide

This README is written for the experimenter.

This guide is split into two parts:

1. **Tutorial:** run your first participant from start to finish.
2. **Experiment specifics:** exact behavior of Experiments A, B, C, D, and E.

---

## 1. What this repository currently supports

OpenMATB in this repository supports five experiment streams:

- **A**: replication stream (three 8-min experimental conditions — Low, Medium, High)
- **B**: within-subject stream, fixed difficulty (two 25-min experimental conditions — Low & High)
- **C**: between-subject stream, fixed difficulty (one 25-min experimental condition — Low or High)
- **D**: staircase stream (one 36-min continuous block with embedded L/M/H segments)
- **E**: calibration-driven stream (two 12-min personalized conditions — Low & High)

Experiments **B**, **C**, **D**, and **E** share the same instruction pipeline:

1. **Subtask instruction phase**: 4 blocks × 1 minute
   - Track only
   - SysMon only
   - Communications only
   - ResMan only
2. **Combined instruction phase**: 1 block × 2 minutes at low load
3. After the 2-minute combined instruction block, the runner:
   - prints Track / ResMan / SysMon / Comms accuracies,
   - prints average instruction accuracy,
   - asks whether to continue or repeat **only the 2-minute combined instruction block**.

The 4 separate 1-minute subtasks are **not** repeated.

**B and C** use Experiment A's fixed difficulty: L (difficulty=0.4, comms=2), H (difficulty=0.7, comms=4). No calibration.

**D** uses a staircase design with no calibration. **E** uses calibration blocks to estimate the participant-specific operating curve before generating personalized experimental scenarios.

---

## 2. Setup

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

Scenario files for participants are already included under `includes/scenarios/`. You do **not** need to run the generators unless you need IDs beyond the pre-generated range — just set your experiment and participant ID in config.ini and go.

---

## 3. Choose your experiment and participant ID

You need:
- one experiment: `A`, `B`, `C`, `D`, or `E`
- one integer participant ID

### Participant ID ranges

| Experiment | Pre-generated IDs | Full ID Range |
|------------|-------------------|---------------|
| A | 1001–1200 | 1001–1999 |
| B | 1000–1199 | 1000–1999 |
| C | 2000–2199 | 2000–2999 |
| D | 3000–3199 | 3000–3999 |
| E | 4000–4199 | 4000–4999 |

The runner uses the participant ID to determine counterbalancing. Do **not** reuse a participant ID.

---

## 4. (Optional) Generate additional scenarios

Scenarios for IDs shown above are **already included**. Only run generators if you need IDs beyond the pre-generated range:

```bash
python -m scenario_generators.expA   # Experiment A
python -m scenario_generators.expB   # Experiment B
python -m scenario_generators.expC   # Experiment C
python -m scenario_generators.expD   # Experiment D
python -m scenario_generators.expE   # Experiment E
```

Edit the `start_id` / `end_id` in each generator's `main()` to control the range.

For B–E, the generators also create shared instruction files in [includes/scenarios/common/](includes/scenarios/common/).

---

## 5. Edit config.ini

Open [config.ini](config.ini) and set at minimum:

```ini
experiment=A|B|C|D|E
participant_id=<integer>
```

Then set experiment-specific fields if needed:

- For B: `stream_b_order=auto|low-high|high-low`
- For C: `stream_c_condition=auto|low|high`
- For E: `stream_e_order=auto|low-high|high-low`

Experiment D does **not** need an extra stream parameter.

| Field | Values | Applies to |
|-------|--------|------------|
| `experiment` | `A`, `B`, `C`, `D`, `E` | All |
| `participant_id` | integer | All |
| `stream_b_order` | `auto`, `low-high`, `high-low` | B |
| `stream_c_condition` | `auto`, `low`, `high` | C |
| `stream_e_order` | `auto`, `low-high`, `high-low` | E |
| `record_face` | `True`, `False` | All |

### Example configs

#### Experiment A

```ini
experiment=A
participant_id=1001
```

#### Experiment B

```ini
experiment=B
participant_id=1000
stream_b_order=auto
```

#### Experiment C

```ini
experiment=C
participant_id=2000
stream_c_condition=auto
```

#### Experiment D

```ini
experiment=D
participant_id=3000
```

#### Experiment E

```ini
experiment=E
participant_id=4000
stream_e_order=auto
```

---

## 6. Start the run

Launch:

`python run_experiment.py`

During the run:

1. Follow on-screen prompts.
2. Complete instruction phase first.
3. Decide whether to repeat instruction if prompted.
4. Continue through baseline and experimental blocks (depends on experiment).
5. Administer NASA-TLX when prompted.

---

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

### Counterbalancing

- Baseline and experimental blocks use the same participant-specific L/M/H order.

### NASA-TLX

- NASA-TLX appears after each 8-minute experimental block.

### Breaks

- The runner prints a reminder for a **5-minute break** between baseline and experimental phases.

---

## Experiment B (within-subject, fixed difficulty)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline 1 (2 min, L/M/H counterbalanced)
Baseline 2 (2 min)
Baseline 3 (2 min)
—— 8–10 min break reminder ——
Experimental Block 1 (25 min, L or H — counterbalanced) + NASA-TLX
—— 8–10 min break reminder ——
Experimental Block 2 (25 min, H or L) + NASA-TLX
```

Uses Experiment A's fixed difficulty levels. No calibration.

### Run settings

- Generate scenarios: `python -m scenario_generators.expB`
- In [config.ini](config.ini):
  - `experiment=B`
  - `participant_id=<ID>` (1000–1999)
  - `stream_b_order=auto|low-high|high-low`
- Run: `python run_experiment.py`

### Counterbalancing

- The three baseline blocks use participant-specific counterbalanced L/M/H order.
- The two experimental blocks are Low then High or High then Low.
- With `stream_b_order=auto`, order is determined from participant ID parity within the B range.

### NASA-TLX

- NASA-TLX appears only at the end of each 25-minute experimental block.
- There is **no NASA-TLX** after the 2-minute baseline blocks.

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment C (between-subject, fixed difficulty)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline 1 (2 min, L/M/H counterbalanced)
Baseline 2 (2 min)
Baseline 3 (2 min)
—— 5-min break reminder ——
Experimental Block (25 min, L or H — assigned) + NASA-TLX
```

Uses Experiment A's fixed difficulty levels. No calibration.

### Run settings

- Generate scenarios: `python -m scenario_generators.expC`
- In [config.ini](config.ini):
  - `experiment=C`
  - `participant_id=<ID>` (2000–2999)
  - `stream_c_condition=auto|low|high`
- Run: `python run_experiment.py`

### Condition assignment

- Each participant receives one 25-minute experimental block only.
- That block is either Low or High.
- With `stream_c_condition=auto`, assignment is determined from participant ID parity within the C range.

### NASA-TLX

- NASA-TLX appears only at the end of the 25-minute experimental block.
- There is **no NASA-TLX** after the 2-minute baseline blocks.

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment D (staircase block)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline 1 (2 min, L/M/H counterbalanced)
Baseline 2 (2 min)
Baseline 3 (2 min)
—— 5-min break reminder ——
Experimental Staircase Block (36 min continuous) — no NASA-TLX
```

The 36-minute block is continuous to the participant. Internally it contains **9 segments × 4 minutes**, arranged as **3 groups of 12 minutes**, each containing one Low, one Moderate, and one High segment (order varies by participant). No calibration.

### Run settings

- Generate scenarios: `python -m scenario_generators.expD`
- In [config.ini](config.ini):
  - `experiment=D`
  - `participant_id=<ID>` (3000–3999)
- Run: `python run_experiment.py`

### NASA-TLX

- There is **no NASA-TLX** in Experiment D.

### Outputs

- Session/log files: `sessions/participant_<ID>/`

---

## Experiment E (calibration-driven low/high)

### Sequence

```
Instructions Subtasks (4 min)
Instructions Combined Low (2 min) — accuracy assessment
Baseline 1 (2 min, L/M/H counterbalanced)
Baseline 2 (2 min)
Baseline 3 (2 min)
Practice Block (6 min, ExpA moderate load)
Calibration Block d1 (2 min)
Calibration Block d2 (2 min)
Calibration Block d3 (2 min)
→ Capacity estimation + personalized scenario generation
—— 8–10 min break reminder ——
Experimental Block 1 (12 min, personalized low or high) + NASA-TLX
—— 8–10 min break reminder ——
Experimental Block 2 (12 min, personalized high or low) + NASA-TLX
```

The three calibration blocks use fixed difficulty scales (d1=0.85, d2=1.00, d3=1.25) to estimate the participant-specific operating curve. The runner then generates participant-specific experimental scenario files.

### Run settings

- Generate scenarios: `python -m scenario_generators.expE`
- In [config.ini](config.ini):
  - `experiment=E`
  - `participant_id=<ID>` (4000–4999)
  - `stream_e_order=auto|low-high|high-low`
- Run: `python run_experiment.py`

### Counterbalancing

- The two 12-minute experimental blocks are Low then High or High then Low.
- With `stream_e_order=auto`, order is determined from participant ID parity within the E range.

### NASA-TLX

- There is **no NASA-TLX** after the calibration blocks.
- NASA-TLX appears only at the end of each 12-minute experimental block.

### Outputs

- Session/log files: `sessions/participant_<ID>/`
- Calibration fit JSON: `sessions/participant_<ID>/<ID>_E_calibration_fit.json`

---

## 7. Verify outputs after the run

Check participant output folder:

- `sessions/participant_<ID>/`

Expected files:

- per-block session CSV logs
- per-block face camera videos (if `record_face=True`)
- for E: calibration fit JSON (`<ID>_E_calibration_fit.json`)

---

## Minimal experimenter workflow summary

1. Generate the experiment scenarios.
2. Pick the correct participant ID range.
3. Edit [config.ini](config.ini).
4. Run `python run_experiment.py`.
5. Press **Enter** at each block to launch it.
6. After the 2-minute combined instruction block, either:
   - press **Enter** to continue, or
   - type **r** to repeat the combined 2-minute block.
7. Complete all remaining blocks in the order shown by the runner.
8. Confirm outputs in `sessions/participant_<ID>/`.
