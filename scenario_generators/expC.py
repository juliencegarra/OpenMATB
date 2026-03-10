#!/usr/bin/env python3

from datetime import datetime

from core.constants import PATHS

from .expB import ExpBGenerator


class ExpCGenerator(ExpBGenerator):
    """
    Experiment C generator (between-subject, fixed difficulty).
    Produces 4-min baseline blocks (L or H) and 36-min experimental blocks (L or H)
    using Exp A's fixed difficulty levels. No calibration.
    """


def main():
    print("Generating Experiment C scenario files (fixed difficulty)...")
    gen = ExpCGenerator()

    start_id = 3001
    end_id = 3201

    root = PATHS["SCENARIOS"].joinpath("expC")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Shared instruction files
    gen.write_scenario_file(
        root / "expC_instructions_subtasks.txt",
        gen.build_instruction_subtasks_block(),
        ["# Experiment C instruction subtasks", f"# Date: {now}"],
    )
    gen.write_scenario_file(
        root / "expC_instructions_combined_L.txt",
        gen.build_instruction_combined_block(),
        ["# Experiment C instruction combined low", f"# Date: {now}"],
    )

    for participant_id in range(start_id, end_id):
        print(f"\n--- Generating files for Participant {participant_id} ---")
        p_dir = root / f"participant_{participant_id}"

        # Generate baseline blocks (4 min each) for L and H
        for block_key in ("L", "H"):
            pre_lines = gen.build_experimental_block(block_key, 240)
            gen.write_scenario_file(
                p_dir / f"expC_pre_{block_key}_4min.txt",
                pre_lines,
                [f"# Exp C baseline ({block_key}) for participant {participant_id}", f"# Date: {now}"],
            )

        # Generate main experimental blocks (36 min each) for L and H
        for block_key in ("L", "H"):
            main_lines = gen.build_experimental_block(block_key, 2160, include_nasa_tlx=True)
            gen.write_scenario_file(
                p_dir / f"expC_main_{block_key}_36min.txt",
                main_lines,
                [f"# Exp C main block ({block_key}) for participant {participant_id}", f"# Date: {now}"],
            )

    print(f"\nDone generating Experiment C for participants {start_id}-{end_id-1}.")


if __name__ == "__main__":
    main()
