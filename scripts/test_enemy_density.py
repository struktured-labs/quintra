#!/usr/bin/env python3
"""ROM contract: early procedural combat rooms contain real pressure."""

from test_stage_archetypes import EN, generated_room


def main():
    counts = []
    first_positions = []

    def count_hostiles(pb, _tiles):
        enemies = [
            EN + i * 28 for i in range(32)
            if pb.memory[EN + i * 28] == 2
            and pb.memory[EN + i * 28 + 1] & 1
        ]
        count = len(enemies)
        counts.append(count)
        first = enemies[0]
        first_positions.append((
            pb.memory[first + 3] | (pb.memory[first + 4] << 8),
            pb.memory[first + 7] | (pb.memory[first + 8] << 8),
        ))

    # Stage-zero local room four is an ordinary first-visit court. Select only
    # director signatures 0/1 here so this remains the baseline-skirmish
    # density contract; trap/wave openings intentionally alter the initial
    # body count and have their own live state-machine regression.
    for seed in (0xCAFE1234, 0xCAFE1235, 0xCAFE123C, 0xCAFE123D):
        generated_room(0, seed, probe=count_hostiles)

    assert len(counts) == 4
    assert min(counts) >= 3, (
        f"ordinary early room fell below three active enemies: {counts}"
    )
    assert len(set(first_positions)) >= 2, (
        "baseline skirmish formations collapsed onto one opening: "
        f"{first_positions}"
    )
    print(f"[enemy-density] PASS early-room hostiles={counts}; "
          f"baseline opening formations={first_positions}")


if __name__ == "__main__":
    main()
