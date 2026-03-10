#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime

from core.constants import PATHS
from core.scenario import Event

from .base_generator import BaseGenerator
from .expA import ExpAGenerator


class ExpDGenerator(BaseGenerator):
    """
    Experiment D generator (within-subject, calibrated).
    Practice blocks use fixed L/H difficulty (same as Exp A).
    Experimental blocks are personalized at runtime after capacity estimation.
    """

    DIFFICULTY_MAP = {
        "L": {"name": "easy", "difficulty": 0.4, "comms_rate": 2},
        "H": {"name": "hard", "difficulty": 0.7, "comms_rate": 4},
    }

    def __init__(self):
        super().__init__()

    def _params_from_multiplier(self, m: float) -> tuple[float, int]:
        """Map a capacity multiplier to (difficulty, comms_rate)."""
        difficulty = max(0.25, min(0.9, round(0.6 * m, 3)))
        comms_rate = max(1, int(round(3.0 * (m / 0.85))))
        return difficulty, comms_rate

    def _build_full_block(
        self,
        duration_sec: int,
        m: float,
        instruction_file: str = "default/full.txt",
        include_nasa_tlx: bool = False,
    ):
        """Build a block using multiplier-based difficulty (for personalized scenarios)."""
        scenario_lines = []
        difficulty, comms_rate = self._params_from_multiplier(m)

        scenario_lines.append(f"0:00:00;instructions;filename;{instruction_file}")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")

        for p in self.plugins:
            scenario_lines.append(f"0:00:00;{p};start")
        scenario_lines.append("0:00:00;communications;voicegender;male")
        scenario_lines.append("0:00:00;communications;voiceidiom;english")

        event_start = 10
        block_duration = max(0, duration_sec - event_start)
        scenario_lines = self.schedule_sysmon_failures(scenario_lines, event_start, block_duration, difficulty)
        scenario_lines = self.schedule_track_events(scenario_lines, event_start, difficulty)
        scenario_lines = self.schedule_comms_events(scenario_lines, event_start, block_duration, comms_rate)
        scenario_lines = self.schedule_resman_events(scenario_lines, event_start, difficulty)

        final_time_str = self.format_time(duration_sec)
        for p in self.plugins:
            scenario_lines.append(f"{final_time_str};{p};stop")

        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        if include_nasa_tlx:
            scenario_lines.append(f"{final_time_str};genericscales;filename;nasatlx_en.txt")
            scenario_lines.append(f"{final_time_str};genericscales;start")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)

    def build_instruction_subtasks_block(self):
        return ExpAGenerator().build_instruction_subtasks_block()

    def build_instruction_combined_block(self):
        return ExpAGenerator().build_instruction_combined_block()

    def build_practice_block(self, block_key, duration_sec=240):
        """Build a 4-min practice block at fixed L or H difficulty."""
        scenario_lines = []

        scenario_lines.append("0:00:00;instructions;filename;default/welcome_task.txt")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")
        for p in self.plugins:
            scenario_lines.append(f"0:00:00;{p};start")
        scenario_lines.append("0:00:00;communications;voicegender;male")
        scenario_lines.append("0:00:00;communications;voiceidiom;english")

        block_info = self.DIFFICULTY_MAP[block_key]
        difficulty = block_info["difficulty"]
        comms_rate = block_info["comms_rate"]

        scenario_lines = self.schedule_sysmon_failures(
            scenario_lines, 0, duration_sec, difficulty
        )
        scenario_lines = self.schedule_comms_events(
            scenario_lines, 0, duration_sec, comms_rate
        )
        scenario_lines = self.schedule_resman_events(
            scenario_lines, 0, difficulty
        )
        scenario_lines = self.schedule_track_events(
            scenario_lines, 0, difficulty
        )

        final_time_str = self.format_time(duration_sec)
        for p in self.plugins:
            scenario_lines.append(f"{final_time_str};{p};stop")

        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)


def main():
    print("Generating Experiment D scenario files (calibrated within-subject)...")
    gen = ExpDGenerator()

    start_id = 4001
    end_id = 4201

    root = PATHS["SCENARIOS"].joinpath("expD")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Shared instruction files
    gen.write_scenario_file(
        root / "expD_instructions_subtasks.txt",
        gen.build_instruction_subtasks_block(),
        ["# Experiment D instruction subtasks", f"# Date: {now}"],
    )
    gen.write_scenario_file(
        root / "expD_instructions_combined_L.txt",
        gen.build_instruction_combined_block(),
        ["# Experiment D instruction combined low", f"# Date: {now}"],
    )

    for participant_id in range(start_id, end_id):
        print(f"\n--- Generating files for Participant {participant_id} ---")
        p_dir = root / f"participant_{participant_id}"

        # Practice blocks (4 min each) at fixed L and H
        for block_key in ("L", "H"):
            practice_lines = gen.build_practice_block(block_key, 240)
            gen.write_scenario_file(
                p_dir / f"expD_pre_{block_key}_4min.txt",
                practice_lines,
                [f"# Exp D practice ({block_key}) for participant {participant_id}", f"# Date: {now}"],
            )

        # Placeholder experimental blocks (20 min each) — will be regenerated at runtime
        # Use moderate multiplier as placeholder
        for block_key, m_placeholder in [("L", 0.80), ("H", 1.00)]:
            main_lines = gen._build_full_block(
                duration_sec=1200, m=m_placeholder,
                instruction_file="default/full.txt", include_nasa_tlx=True
            )
            gen.write_scenario_file(
                p_dir / f"expD_main_{block_key}_20min.txt",
                main_lines,
                [
                    f"# Exp D main block ({block_key}) for participant {participant_id}",
                    f"# placeholder m={m_placeholder}",
                    f"# Date: {now}",
                ],
            )

    print(f"\nDone generating Experiment D for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
    main()
