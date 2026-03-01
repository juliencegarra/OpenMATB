#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime

from core.constants import PATHS

from .expB import ExpBGenerator


class ExpCGenerator(ExpBGenerator):
	"""Stream C generator (between-subject) - scaffold for calibration-driven sessions."""


def main():
	print("Generating Stream C scenario files...")
	gen = ExpCGenerator()

	start_id = 500
	end_id = 600

	root = PATHS["SCENARIOS"].joinpath("expC")
	now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

	# Shared instruction files
	gen.write_scenario_file(
		root / "expC_instructions_subtasks.txt",
		gen.build_instruction_subtasks_block(),
		["# Stream C instruction subtasks", f"# Date: {now}"],
	)
	gen.write_scenario_file(
		root / "expC_instructions_combined_L.txt",
		gen.build_instruction_combined_block(),
		["# Stream C instruction combined low", f"# Date: {now}"],
	)

	for participant_id in range(start_id, end_id):
		p_dir = root / f"participant_{participant_id}"
		order = gen.CALIBRATION_ORDERS[(participant_id - start_id) % len(gen.CALIBRATION_ORDERS)]

		gen.write_scenario_file(
			p_dir / "expC_practice_M_10min.txt",
			gen._build_full_block(duration_sec=600, m=0.85, instruction_file="default/full.txt", include_nasa_tlx=False),
			[f"# Stream C practice for participant {participant_id}", "# m=0.85", f"# Date: {now}"],
		)

		gen.write_scenario_file(
			p_dir / "expC_calibration_integrated_8min.txt",
			gen.build_calibration_block(order),
			[
				f"# Stream C integrated calibration for participant {participant_id}",
				f"# m_order={order}",
				f"# Date: {now}",
			],
		)

		gen.write_scenario_file(
			p_dir / "expC_baseline_anchor_2min.txt",
			gen._build_full_block(duration_sec=120, m=0.60, instruction_file="default/full.txt", include_nasa_tlx=False),
			[f"# Stream C baseline anchor for participant {participant_id}", "# m=0.60", f"# Date: {now}"],
		)

		# Between-subject stream uses one of these, assigned in runner
		gen.write_scenario_file(
			p_dir / "expC_experimental_low_30min.txt",
			gen._build_full_block(duration_sec=1800, m=0.80, instruction_file="default/full.txt", include_nasa_tlx=True),
			[f"# Stream C low block for participant {participant_id}", "# placeholder m=0.80", f"# Date: {now}"],
		)
		gen.write_scenario_file(
			p_dir / "expC_experimental_high_30min.txt",
			gen._build_full_block(duration_sec=1800, m=1.00, instruction_file="default/full.txt", include_nasa_tlx=True),
			[f"# Stream C high block for participant {participant_id}", "# placeholder m=1.00", f"# Date: {now}"],
		)

	print(f"Done Stream C generation for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
	main()

