#!/usr/bin/env python3
"""Live-ROM contract for one-shot objective-leg return surprises."""

from test_stage_archetypes import (
    RS, addr, archetype_sample_cell, generated_room,
)


RETURN_KIND = addr("_room_return_echo_kind")
ENCOUNTER_KIND = addr("_room_encounter_kind")
LABEL_TICKS = addr("_room_district_label_ticks")
BG_X = addr("_room_bg_origin_x")
BG_Y = addr("_room_bg_origin_y")
RS_PUZZLES = 27
RS_RETURN_FLAGS = 52
RS_VISITED = 53
RUN_TRIAL_BIT = 0x01


def mark(bitmap_offset, cell):
    return bitmap_offset + cell // 8, 1 << (cell % 8)


def seed_for_variant(wanted):
    for byte1 in range(256):
        seed = 0x51A70031 | (byte1 << 8)
        local = archetype_sample_cell(0, seed, preferred=6)
        variant = (byte1 + local + RUN_TRIAL_BIT) & 3
        if variant == wanted:
            return seed, local
    raise AssertionError(f"no seed for return variant {wanted}")


def variant_contract(wanted):
    seed, local = seed_for_variant(wanted)

    def prepare(pb, _addrs):
        address, bit = mark(RS_VISITED, local)
        pb.memory[RS + address] |= bit
        pb.memory[RS + RS_PUZZLES] |= RUN_TRIAL_BIT

    def inspect(pb, _tiles):
        assert pb.memory[RS + RS_RETURN_FLAGS] & RUN_TRIAL_BIT, \
            "completed leg did not spend its one return surprise"
        assert pb.memory[RETURN_KIND] == wanted + 1, (
            f"variant {wanted} published return kind {pb.memory[RETURN_KIND]}"
        )
        expected_encounter = (0, 2, 1, 3)[wanted]
        assert pb.memory[ENCOUNTER_KIND] == expected_encounter, (
            f"variant {wanted} published encounter {pb.memory[ENCOUNTER_KIND]}, "
            f"expected {expected_encounter}"
        )
        assert pb.memory[LABEL_TICKS] > 0, \
            "return surprise did not publish a visible arrival card"
        px = (pb.memory[BG_X] + 8) & 31
        py = (pb.memory[BG_Y] + 1) & 31
        label = [pb.memory[0x9800 + py * 32 + ((px + i) & 31)]
                 for i in range(4)]
        assert label == [76, 77, 78, 79], \
            f"return surprise card is not RIFT: {label}"

    generated_room(0, seed, local_room=local,
                   pre_cross=prepare, probe=inspect)


def revealed_is_not_visited():
    seed, local = seed_for_variant(3)

    def prepare(pb, _addrs):
        # Cartographer/ASK writes the visible compass map only.
        seen_offset = (18, 29, 31, 33)[local // 8]
        pb.memory[RS + seen_offset] |= 1 << (local % 8)
        pb.memory[RS + RS_PUZZLES] |= RUN_TRIAL_BIT

    def inspect(pb, _tiles):
        assert pb.memory[RETURN_KIND] == 0, \
            "map-revealed first visit falsely became a backtrack ambush"
        assert pb.memory[RS + RS_RETURN_FLAGS] == 0, \
            "map reveal silently consumed a future return surprise"

    generated_room(0, seed, local_room=local,
                   pre_cross=prepare, probe=inspect)


def main():
    for wanted in range(4):
        variant_contract(wanted)
    revealed_is_not_visited()
    print("[return-echo] PASS changed pack, wave, trap, miniboss echo, "
          "one-shot flag, chart-safe first visit")


if __name__ == "__main__":
    main()
