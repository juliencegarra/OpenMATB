#!/usr/bin/env python3

from __future__ import annotations

from core.constants import PATHS

from .base_generator import BaseGenerator
from .expA import ExpAGenerator

COMMON_SCENARIO_DIRNAME = "common"
COMMON_INSTRUCTION_SUBTASKS_FILENAME = "instruction_subtasks_4x1min.txt"
COMMON_INSTRUCTION_COMBINED_FILENAME = "instruction_combined_low_2min.txt"
COMMON_INSTRUCTION_SUBTASKS_RELATIVE_PATH = (
    f"{COMMON_SCENARIO_DIRNAME}/{COMMON_INSTRUCTION_SUBTASKS_FILENAME}"
)
COMMON_INSTRUCTION_COMBINED_RELATIVE_PATH = (
    f"{COMMON_SCENARIO_DIRNAME}/{COMMON_INSTRUCTION_COMBINED_FILENAME}"
)


class ExpABasedScenarioGenerator(BaseGenerator):
    """Shared helpers for experiments derived from the Experiment A task model."""

    PARTICIPANT_START_ID = 0
    DIFFICULTY_MAP = ExpAGenerator.DIFFICULTY_MAP
    PERMUTATIONS = ExpAGenerator.PERMUTATIONS

    def build_instruction_subtasks_block(self):
        return ExpAGenerator().build_instruction_subtasks_block()

    def build_instruction_combined_block(self):
        return ExpAGenerator().build_instruction_combined_block()

    def write_common_instruction_files(self, timestamp: str) -> None:
        root_dir = PATHS["SCENARIOS"].joinpath(COMMON_SCENARIO_DIRNAME)
        self.write_scenario_file(
            root_dir / COMMON_INSTRUCTION_SUBTASKS_FILENAME,
            self.build_instruction_subtasks_block(),
            [
                "# Shared instruction subtasks block for Experiments B-E",
                f"# Date: {timestamp}",
            ],
        )
        self.write_scenario_file(
            root_dir / COMMON_INSTRUCTION_COMBINED_FILENAME,
            self.build_instruction_combined_block(),
            [
                "# Shared instruction combined low-load block for Experiments B-E",
                f"# Date: {timestamp}",
            ],
        )

    @classmethod
    def baseline_order_for_participant(cls, participant_id: int) -> tuple[str, str, str]:
        offset = participant_id - cls.PARTICIPANT_START_ID
        return cls.PERMUTATIONS[offset % len(cls.PERMUTATIONS)]

    @classmethod
    def low_high_order_for_participant(cls, participant_id: int) -> tuple[str, str]:
        offset = participant_id - cls.PARTICIPANT_START_ID
        return ("L", "H") if offset % 2 == 0 else ("H", "L")

    def difficulty_settings_for_level(self, level_key: str) -> tuple[float, float]:
        block_info = self.DIFFICULTY_MAP[level_key]
        return float(block_info["difficulty"]), float(block_info["comms_rate"])

    def build_integrated_block(
        self,
        duration_sec: int,
        difficulty: float,
        comms_rate: float,
        instruction_file: str = "default/full.txt",
        include_nasa_tlx: bool = False,
        marker: str | None = None,
    ):
        scenario_lines = []

        scenario_lines.append(f"0:00:00;instructions;filename;{instruction_file}")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")
        if marker is not None:
            scenario_lines.append(f"0:00:00;labstreaminglayer;marker;{marker}")

        for plugin_name in self.plugins:
            scenario_lines.append(f"0:00:00;{plugin_name};start")
        scenario_lines.append("0:00:00;communications;voicegender;male")
        scenario_lines.append("0:00:00;communications;voiceidiom;english")

        scenario_lines = self.schedule_sysmon_failures(
            scenario_lines,
            0,
            duration_sec,
            difficulty,
        )
        scenario_lines = self.schedule_comms_events(
            scenario_lines,
            0,
            duration_sec,
            comms_rate,
        )
        scenario_lines = self.schedule_resman_events(
            scenario_lines,
            0,
            difficulty,
        )
        scenario_lines = self.schedule_track_events(
            scenario_lines,
            0,
            difficulty,
        )

        final_time_str = self.format_time(duration_sec)
        for plugin_name in self.plugins:
            scenario_lines.append(f"{final_time_str};{plugin_name};stop")

        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        if include_nasa_tlx:
            scenario_lines.append(
                f"{final_time_str};genericscales;filename;nasatlx_en.txt"
            )
            scenario_lines.append(f"{final_time_str};genericscales;start")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)

    def build_level_block(
        self,
        level_key: str,
        duration_sec: int,
        include_nasa_tlx: bool = False,
        marker: str | None = None,
        instruction_file: str = "default/full.txt",
    ):
        difficulty, comms_rate = self.difficulty_settings_for_level(level_key)
        return self.build_integrated_block(
            duration_sec=duration_sec,
            difficulty=difficulty,
            comms_rate=comms_rate,
            instruction_file=instruction_file,
            include_nasa_tlx=include_nasa_tlx,
            marker=marker,
        )

    def build_staircase_block(
        self,
        macro_orders: tuple[tuple[str, str, str], ...],
        segment_duration_sec: int,
        include_nasa_tlx: bool = False,
        instruction_file: str = "default/full.txt",
        segment_markers: list[str] | None = None,
    ):
        flattened_levels = [
            level_key
            for macro_order in macro_orders
            for level_key in macro_order
        ]
        total_duration_sec = segment_duration_sec * len(flattened_levels)
        scenario_lines = []

        scenario_lines.append(f"0:00:00;instructions;filename;{instruction_file}")
        scenario_lines.append("0:00:00;instructions;start")
        scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
        scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
        scenario_lines.append("0:00:00;labstreaminglayer;start")

        for plugin_name in self.plugins:
            scenario_lines.append(f"0:00:00;{plugin_name};start")
        scenario_lines.append("0:00:00;communications;voicegender;male")
        scenario_lines.append("0:00:00;communications;voiceidiom;english")

        for segment_index, level_key in enumerate(flattened_levels):
            segment_start_sec = segment_index * segment_duration_sec
            difficulty, comms_rate = self.difficulty_settings_for_level(level_key)

            if segment_markers is not None:
                marker = segment_markers[segment_index]
                scenario_lines.append(
                    f"{self.format_time(segment_start_sec)};labstreaminglayer;marker;{marker}"
                )

            scenario_lines = self.schedule_sysmon_failures(
                scenario_lines,
                segment_start_sec,
                segment_duration_sec,
                difficulty,
            )
            scenario_lines = self.schedule_comms_events(
                scenario_lines,
                segment_start_sec,
                segment_duration_sec,
                comms_rate,
            )
            scenario_lines = self.schedule_resman_events(
                scenario_lines,
                segment_start_sec,
                difficulty,
            )
            scenario_lines = self.schedule_track_events(
                scenario_lines,
                segment_start_sec,
                difficulty,
            )

        final_time_str = self.format_time(total_duration_sec)
        for plugin_name in self.plugins:
            scenario_lines.append(f"{final_time_str};{plugin_name};stop")

        scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
        if include_nasa_tlx:
            scenario_lines.append(
                f"{final_time_str};genericscales;filename;nasatlx_en.txt"
            )
            scenario_lines.append(f"{final_time_str};genericscales;start")
        scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
        scenario_lines.append(f"{final_time_str};instructions;start")

        return self.reorder_scenario_by_time(scenario_lines)
