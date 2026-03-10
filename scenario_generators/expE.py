#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime

from core.constants import PATHS

from .expD import ExpDGenerator


class ExpEGenerator(ExpDGenerator):
    """
    Experiment E generator (between-subject, calibrated).
    Practice blocks use fixed L or H difficulty (same as Exp A).
    Experimental block is personalized at runtime after capacity estimation.
    """


def main():
    print("Generating Experiment E scenario files (calibrated between-subject)...")
    gen = ExpEGenerator()

    start_id = 5001
    end_id = 5201

    root = PATHS["SCENARIOS"].joinpath("expE")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Shared instruction files
    gen.write_scenario_file(
        root / "expE_instructions_subtasks.txt",
        gen.build_instruction_subtasks_block(),
        ["# Experiment E instruction subtasks", f"# Date: {now}"],
    )
    gen.write_scenario_file(
        root / "expE_instructions_combined_L.txt",
        gen.build_instruction_combined_block(),
        ["# Experiment E instruction combined low", f"# Date: {now}"],
    )

    for participant_id in range(start_id, end_id):
        print(f"\n--- Generating files for Participant {participant_id} ---")
        p_dir = root / f"participant_{participant_id}"

        # Practice blocks (4 min each) at fixed L and H
        for block_key in ("L", "H"):
            practice_lines = gen.build_practice_block(block_key, 240)
            gen.write_scenario_file(
                p_dir / f"expE_pre_{block_key}_4min.txt",
                practice_lines,
                [f"# Exp E practice ({block_key}) for participant {participant_id}", f"# Date: {now}"],
            )

        # Placeholder experimental blocks (36 min each) — will be regenerated at runtime
        for block_key, m_placeholder in [("L", 0.80), ("H", 1.00)]:
            main_lines = gen._build_full_block(
                duration_sec=2160, m=m_placeholder,
                instruction_file="default/full.txt", include_nasa_tlx=True
            )
            gen.write_scenario_file(
                p_dir / f"expE_main_{block_key}_36min.txt",
                main_lines,
                [
                    f"# Exp E main block ({block_key}) for participant {participant_id}",
                    f"# placeholder m={m_placeholder}",
                    f"# Date: {now}",
                ],
            )

    print(f"\nDone generating Experiment E for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
    main()
