#!/usr/bin/env python3
"""ROM contract: early procedural combat rooms contain real pressure."""

from test_stage_archetypes import EN, generated_room


def main():
    counts = []

    def count_hostiles(pb, _tiles):
        count = sum(
            pb.memory[EN + i * 28] == 2 and pb.memory[EN + i * 28 + 1] & 1
            for i in range(32)
        )
        counts.append(count)

    # Stage-zero room one is an ordinary combat room (not a shop, rest,
    # miniboss, town, or boss). These seeds exercise different pillar/layout
    # decisions and used to reveal the old one-attempt placement bug.
    for seed in (0xCAFE1234, 0xCAFE1235, 0x1337, 0xDEADBEEF):
        generated_room(0, seed, probe=count_hostiles)

    assert len(counts) == 4
    assert min(counts) >= 2, (
        f"ordinary early room fell below two active enemies: {counts}"
    )
    print(f"[enemy-density] PASS early-room hostiles={counts}")


if __name__ == "__main__":
    main()
