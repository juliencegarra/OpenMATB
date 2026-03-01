#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime

from core.constants import PATHS
from core.scenario import Event

from .base_generator import BaseGenerator


class ExpBGenerator(BaseGenerator):
	"""Stream B generator (within-subject) - scaffold for calibration-driven sessions."""

	CALIBRATION_M_VALUES = [0.70, 0.85, 1.00, 1.15]
	CALIBRATION_ORDERS = [
		[0.70, 0.85, 1.00, 1.15],
		[0.85, 1.00, 1.15, 0.70],
		[1.00, 1.15, 0.70, 0.85],
		[1.15, 0.70, 0.85, 1.00],
	]

	def _params_from_multiplier(self, m: float) -> tuple[float, int]:
		# Tunable mapping stub. Chosen so m=0.85 approximates Stream A moderate level.
		difficulty = max(0.25, min(0.9, round(0.6 * m, 3)))
		comms_rate = max(1, int(round(3.0 * (m / 0.85))))
		return difficulty, comms_rate

	def _build_full_block(
		self,
		duration_sec: int,
		m: float,
		instruction_file: str = "default/full.txt",
		include_nasa_tlx: bool = False,
		force_comms_last_30s: bool = False,
	):
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

		if force_comms_last_30s and duration_sec >= 40:
			prompts = ["own", "other", "own", "other"]
			t0 = duration_sec - 30
			line_id = self.get_last_line_num(scenario_lines)
			for i, kind in enumerate(prompts):
				line_id += 1
				scenario_lines.append(Event(line_id, t0 + (i * 8), "communications", ["radioprompt", kind]))

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
		from .expA import ExpAGenerator

		return ExpAGenerator().build_instruction_subtasks_block()

	def build_instruction_combined_block(self):
		from .expA import ExpAGenerator

		return ExpAGenerator().build_instruction_combined_block()

	def build_calibration_block(self, m_order: list[float]):
		# 4 x 2-min integrated segments
		scenario_lines = []
		segment_sec = 120
		total_duration = segment_sec * len(m_order)

		scenario_lines.append("0:00:00;instructions;filename;default/full.txt")
		scenario_lines.append("0:00:00;instructions;start")
		scenario_lines.append("0:00:00;labstreaminglayer;pauseatstart;true")
		scenario_lines.append("0:00:00;labstreaminglayer;streamsession;true")
		scenario_lines.append("0:00:00;labstreaminglayer;start")
		for p in self.plugins:
			scenario_lines.append(f"0:00:00;{p};start")
		scenario_lines.append("0:00:00;communications;voicegender;male")
		scenario_lines.append("0:00:00;communications;voiceidiom;english")

		for idx, m in enumerate(m_order):
			seg_start = idx * segment_sec
			difficulty, comms_rate = self._params_from_multiplier(m)

			# marker for parsing/calibration fitting pipeline
			scenario_lines.append(f"{self.format_time(seg_start)};labstreaminglayer;marker;calibration_segment_{idx+1}_m_{m:.2f}")

			event_start = seg_start + 5
			block_dur = segment_sec - 10
			scenario_lines = self.schedule_sysmon_failures(scenario_lines, event_start, block_dur, difficulty)
			scenario_lines = self.schedule_track_events(scenario_lines, event_start, difficulty)
			scenario_lines = self.schedule_resman_events(scenario_lines, event_start, difficulty)
			scenario_lines = self.schedule_comms_events(scenario_lines, event_start, block_dur, comms_rate)

			# Ensure comm sampling in final 30 seconds of each segment
			prompts = ["own", "other", "own", "other"]
			line_id = self.get_last_line_num(scenario_lines)
			t0 = seg_start + segment_sec - 30
			for i, kind in enumerate(prompts):
				line_id += 1
				scenario_lines.append(Event(line_id, t0 + (i * 8), "communications", ["radioprompt", kind]))

		final_time_str = self.format_time(total_duration)
		for p in self.plugins:
			scenario_lines.append(f"{final_time_str};{p};stop")
		scenario_lines.append(f"{final_time_str};labstreaminglayer;stop")
		scenario_lines.append(f"{final_time_str};instructions;filename;default/end_task.txt")
		scenario_lines.append(f"{final_time_str};instructions;start")

		return self.reorder_scenario_by_time(scenario_lines)


def main():
	print("Generating Stream B scenario files...")
	gen = ExpBGenerator()

	start_id = 500
	end_id = 600

	root = PATHS["SCENARIOS"].joinpath("expB")
	now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	# Shared instruction files
	gen.write_scenario_file(
		root / "expB_instructions_subtasks.txt",
		gen.build_instruction_subtasks_block(),
		["# Stream B instruction subtasks", f"# Date: {now}"],
	)
	gen.write_scenario_file(
		root / "expB_instructions_combined_L.txt",
		gen.build_instruction_combined_block(),
		["# Stream B instruction combined low", f"# Date: {now}"],
	)

	for participant_id in range(start_id, end_id):
		p_dir = root / f"participant_{participant_id}"
		order = gen.CALIBRATION_ORDERS[(participant_id - start_id) % len(gen.CALIBRATION_ORDERS)]

		# 10-min practice at m=0.85 (moderate proxy)
		gen.write_scenario_file(
			p_dir / "expB_practice_M_10min.txt",
			gen._build_full_block(duration_sec=600, m=0.85, instruction_file="default/full.txt", include_nasa_tlx=False),
			[f"# Stream B practice for participant {participant_id}", "# m=0.85", f"# Date: {now}"],
		)

		# 8-min integrated calibration, 4 x 2-min segments
		gen.write_scenario_file(
			p_dir / "expB_calibration_integrated_8min.txt",
			gen.build_calibration_block(order),
			[
				f"# Stream B integrated calibration for participant {participant_id}",
				f"# m_order={order}",
				f"# Date: {now}",
			],
		)

		# 2-min baseline anchor (very low demand)
		gen.write_scenario_file(
			p_dir / "expB_baseline_anchor_2min.txt",
			gen._build_full_block(duration_sec=120, m=0.60, instruction_file="default/full.txt", include_nasa_tlx=False),
			[f"# Stream B baseline anchor for participant {participant_id}", "# m=0.60", f"# Date: {now}"],
		)

		# 25-min sustained blocks (low/high placeholders until participant-specific m* fit is applied)
		gen.write_scenario_file(
			p_dir / "expB_experimental_low_25min.txt",
			gen._build_full_block(duration_sec=1500, m=0.80, instruction_file="default/full.txt", include_nasa_tlx=True),
			[f"# Stream B low block for participant {participant_id}", "# placeholder m=0.80", f"# Date: {now}"],
		)
		gen.write_scenario_file(
			p_dir / "expB_experimental_high_25min.txt",
			gen._build_full_block(duration_sec=1500, m=1.00, instruction_file="default/full.txt", include_nasa_tlx=True),
			[f"# Stream B high block for participant {participant_id}", "# placeholder m=1.00", f"# Date: {now}"],
		)

	print(f"Done Stream B generation for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
	main()

