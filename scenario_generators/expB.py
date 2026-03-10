#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path

from .base_generator import BaseGenerator
from .expA import ExpAGenerator
from core.constants import PATHS


class ExpBGenerator(BaseGenerator):
    """
    Experiment B generator (within-subject, fixed difficulty).
    Produces 2-min baseline pre-blocks (L/H) and 20-min experimental blocks (L/H)
    using Exp A's fixed difficulty levels. No calibration.
    """

    DIFFICULTY_MAP = {
        "L": {"name": "easy", "difficulty": 0.4, "comms_rate": 2},
        "H": {"name": "hard", "difficulty": 0.7, "comms_rate": 4},
    }

    def __init__(self):
        super().__init__()

    def build_instruction_subtasks_block(self):
        return ExpAGenerator().build_instruction_subtasks_block()

    def build_instruction_combined_block(self):
        return ExpAGenerator().build_instruction_combined_block()

    def build_experimental_block(self, block_key, duration_sec, include_nasa_tlx=False):
        """Builds a block at fixed difficulty, same pattern as ExpA."""
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
        if include_nasa_tlx:
            scenario_lines.append(f"{final_time_str};genericscales;filename;nasatlx_en.txt")
            scenario_lines.append(f"{final_time_str};genericscales;start")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)


def main():
    print("Generating Experiment B scenario files (fixed difficulty)...")
    gen = ExpBGenerator()

    start_id = 2001
    end_id = 2201

    root = PATHS["SCENARIOS"].joinpath("expB")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Shared instruction files
    gen.write_scenario_file(
        root / "expB_instructions_subtasks.txt",
        gen.build_instruction_subtasks_block(),
        ["# Experiment B instruction subtasks", f"# Date: {now}"],
    )
    gen.write_scenario_file(
        root / "expB_instructions_combined_L.txt",
        gen.build_instruction_combined_block(),
        ["# Experiment B instruction combined low", f"# Date: {now}"],
    )

    for participant_id in range(start_id, end_id):
        print(f"\n--- Generating files for Participant {participant_id} ---")
        p_dir = root / f"participant_{participant_id}"

        # Generate pre-blocks (2 min each) for L and H
        for block_key in ("L", "H"):
            pre_lines = gen.build_experimental_block(block_key, 120)
            gen.write_scenario_file(
                p_dir / f"expB_pre_{block_key}_2min.txt",
                pre_lines,
                [f"# Exp B pre-block ({block_key}) for participant {participant_id}", f"# Date: {now}"],
            )

        # Generate main experimental blocks (20 min each) for L and H
        for block_key in ("L", "H"):
            main_lines = gen.build_experimental_block(block_key, 1200, include_nasa_tlx=True)
            gen.write_scenario_file(
                p_dir / f"expB_main_{block_key}_20min.txt",
                main_lines,
                [f"# Exp B main block ({block_key}) for participant {participant_id}", f"# Date: {now}"],
            )

    print(f"\nDone generating Experiment B for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
    main()
