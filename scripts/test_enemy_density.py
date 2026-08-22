#!/usr/bin/env python3
"""ROM contract: early procedural combat rooms contain real pressure."""

from test_stage_archetypes import EN, generated_room


def main():
    counts = []
    first_positions = []
    late_positions = []

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
    assert min(counts) >= 14 and max(counts) <= 18, (
        f"Normal opening district left the 14-18 pressure band: {counts}"
    )
    assert len(set(first_positions)) >= 2, (
        "baseline skirmish formations collapsed onto one opening: "
        f"{first_positions}"
    )
    def collect_late_positions(pb, _tiles):
        positions = [
            (pb.memory[EN + i * 28 + 3]
             | (pb.memory[EN + i * 28 + 4] << 8),
             pb.memory[EN + i * 28 + 7]
             | (pb.memory[EN + i * 28 + 8] << 8))
            for i in range(32)
            if pb.memory[EN + i * 28] == 2
            and pb.memory[EN + i * 28 + 1] & 1
        ]
        late_positions.append(positions)

    # Void's late-stage bonus can produce 18 bodies. Every one must retain a
    # distinct physical anchor rather than the last two wrapping over a
    # 16-slot formation table.
    generated_room(8, 0xCAFE1234, probe=collect_late_positions)
    assert len(late_positions[0]) >= 16, late_positions[0]
    assert len(set(late_positions[0])) == len(late_positions[0]), (
        f"late wide encounter stacked bodies: {late_positions[0]}")

    print(f"[enemy-density] PASS Normal early-room hostiles={counts}; "
          f"baseline openings={first_positions}; late unique="
          f"{len(late_positions[0])}")


if __name__ == "__main__":
    main()
