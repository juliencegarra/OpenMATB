#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path

from .base_generator import BaseGenerator
from core.constants import PATHS


class ExpAGenerator(BaseGenerator):
    """
    Generates scenarios for Experiment A, which includes:
    - A 2-minute instruction block.
    - Three 2-minute "pre" blocks with varying difficulty.
    - Three 8-minute "main" blocks with varying difficulty.
    """

    DIFFICULTY_MAP = {
        "L": {"name": "easy", "difficulty": 0.4, "comms_rate": 2},
        "M": {"name": "moderate", "difficulty": 0.5, "comms_rate": 3},
        "H": {"name": "hard", "difficulty": 0.7, "comms_rate": 4},
    }

    PERMUTATIONS = [
        ("L", "M", "H"),  # 0
        ("L", "H", "M"),  # 1
        ("M", "L", "H"),  # 2
        ("M", "H", "L"),  # 3
        ("H", "L", "M"),  # 4
        ("H", "M", "L"),  # 5
    ]

    def __init__(self):
        super().__init__()

    def build_instruction_subtasks_block(self):
        """Builds instruction practice: 1 min each for Track, SysMon, Comms, ResMan."""
        scenario_lines = []
        total_duration_sec = 240
        single_task_duration = 60
        difficulty = 0.3
        comms_rate = 2

        # Init streaming / pause behavior
        scenario_lines.append("0:00:00;instructions;filename;default/welcome_task.txt")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")

        # 1) Track only (0:00 - 1:00)
        scenario_lines.append("0:00:00;instructions;filename;default/track.txt")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;track;start")
        scenario_lines = self.schedule_track_events(scenario_lines, 5, difficulty)
        scenario_lines.append("0:01:00;track;stop")

        # 2) SysMon only (1:00 - 2:00)
        scenario_lines.append("0:01:00;instructions;filename;default/sysmon.txt")
        scenario_lines.append("0:01:00;instructions;start")
        scenario_lines.append("0:01:00;sysmon;start")
        scenario_lines = self.schedule_sysmon_failures(
            scenario_lines,
            single_task_duration + 5,
            single_task_duration - 10,
            difficulty,
        )
        scenario_lines.append("0:02:00;sysmon;stop")

        # 3) Communications only (2:00 - 3:00)
        scenario_lines.append("0:02:00;instructions;filename;default/communications.txt")
        scenario_lines.append("0:02:00;instructions;start")
        scenario_lines.append("0:02:00;communications;start")
        scenario_lines.append("0:02:00;communications;voicegender;male")
        scenario_lines.append("0:02:00;communications;voiceidiom;english")
        scenario_lines = self.schedule_comms_events(
            scenario_lines,
            2 * single_task_duration,
            single_task_duration,
            comms_rate,
        )
        scenario_lines.append("0:03:00;communications;stop")

        # 4) ResMan only (3:00 - 4:00)
        scenario_lines.append("0:03:00;instructions;filename;default/resman.txt")
        scenario_lines.append("0:03:00;instructions;start")
        scenario_lines.append("0:03:00;resman;start")
        scenario_lines = self.schedule_resman_events(
            scenario_lines,
            3 * single_task_duration + 5,
            difficulty,
        )
        scenario_lines.append("0:04:00;resman;stop")

        # End practice segment
        final_time_str = self.format_time(total_duration_sec)
        for p in self.plugins:
            scenario_lines.append(f"{final_time_str};{p};stop")

        # End instructions
        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)

    def build_instruction_combined_block(self):
        """Builds 2-minute full-task low-load instruction assessment block."""
        scenario_lines = []
        total_duration_sec = 120
        event_start_sec = 10
        block_duration = total_duration_sec - event_start_sec
        difficulty = 0.3
        comms_rate = 2

        scenario_lines.append("0:00:00;instructions;filename;default/full.txt")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")

        for p in self.plugins:
            scenario_lines.append(f"0:00:00;{p};start")
        scenario_lines.append("0:00:00;communications;voicegender;male")
        scenario_lines.append("0:00:00;communications;voiceidiom;english")

        scenario_lines = self.schedule_sysmon_failures(
            scenario_lines, event_start_sec, block_duration, difficulty
        )
        scenario_lines = self.schedule_track_events(
            scenario_lines, event_start_sec, difficulty
        )
        scenario_lines = self.schedule_comms_events(
            scenario_lines, event_start_sec, block_duration, comms_rate
        )
        scenario_lines = self.schedule_resman_events(
            scenario_lines, event_start_sec, difficulty
        )

        final_time_str = self.format_time(total_duration_sec)
        for p in self.plugins:
            scenario_lines.append(f"{final_time_str};{p};stop")

        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)

    def build_experimental_block(self, block_key, duration_sec, include_nasa_tlx=False):
        """Builds an experimental block of a given duration and difficulty."""
        scenario_lines = []

        # Instructions and task start
        scenario_lines.append("0:00:00;instructions;filename;default/welcome_task.txt")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")
        for p in self.plugins:
            scenario_lines.append(f"0:00:00;{p};start")

        # Schedule events based on difficulty
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

        # Stop tasks
        final_time_str = self.format_time(duration_sec)
        for p in self.plugins:
            scenario_lines.append(f"{final_time_str};{p};stop")

        # End of block
        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        if include_nasa_tlx:
            scenario_lines.append(f"{final_time_str};genericscales;filename;nasatlx_en.txt")
            scenario_lines.append(f"{final_time_str};genericscales;start")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)


def main():
    print("Generating all counterbalanced scenarios for Experiment A...")
    generator = ExpAGenerator()

    # --- Generate universal instruction files first ---
    print("\n--- Generating universal instruction files ---")

    instr_practice_lines = generator.build_instruction_subtasks_block()
    instr_practice_header = [
        "# Universal instruction subtasks practice for Experiment A",
        f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]

    instr_combined_lines = generator.build_instruction_combined_block()
    instr_combined_header = [
        "# Universal instruction combined 2-min low-load block for Experiment A",
        f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    # Save it in the root of the expA scenarios directory
    instr_dir = PATHS["SCENARIOS"].joinpath("expA")
    generator.write_scenario_file(
        instr_dir / "expA_instructions_subtasks.txt", instr_practice_lines, instr_practice_header
    )
    generator.write_scenario_file(
        instr_dir / "expA_instructions_combined_L.txt", instr_combined_lines, instr_combined_header
    )


    # --- Generate participant-specific blocks ---
    # Define the range of participant IDs to generate files for
    start_id = 500
    end_id = 600  # Generate up to 600, exclusive, so last ID will be 599

    for participant_id in range(start_id, end_id):
        print(f"\n--- Generating files for Participant {participant_id} ---")
        # This logic is from your exp4 scripts
        offset = participant_id - 401
        perm_index = offset % 6
        block_order = generator.PERMUTATIONS[perm_index]

        # Define where to save the scenarios
        scenario_dir = PATHS["SCENARIOS"].joinpath("expA", f"participant_{participant_id}")

        # 2. Generate pre-blocks (2 mins each)
        for i, block_key in enumerate(block_order):
            pre_block_lines = generator.build_experimental_block(block_key, 120)
            pre_header = [
                f"# Pre-block {i+1} ({block_key}) for participant {participant_id}",
                f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ]
            generator.write_scenario_file(
                scenario_dir / f"expA_pre_{i+1}_{block_key}.txt", pre_block_lines, pre_header
            )

        # 3. Generate main blocks (8 mins each)
        for i, block_key in enumerate(block_order):
            main_block_lines = generator.build_experimental_block(block_key, 480, include_nasa_tlx=True)
            main_header = [
                f"# Main-block {i+1} ({block_key}) for participant {participant_id}",
                f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ]
            generator.write_scenario_file(
                scenario_dir / f"expA_main_{i+1}_{block_key}.txt", main_block_lines, main_header
            )

    print(f"\nDone generating all scenarios for Experiment A for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
    main()
