#!/usr/bin/env python3
"""Sequence-puzzle floor notes are loud, sustained, and precede the fanfare."""
from test_puzzles import RUNE_ENV, rune_sequence_contract


if __name__ == "__main__":
    rune_sequence_contract()
    print(
        "[puzzle-note] PASS "
        f"CH1 NR12=0x{RUNE_ENV:02X} (vol 15, down, period 3), "
        "40-frame music claim, mid-phrase sustain >= 24 frames, "
        "final rune holds >= 10 frames before the fanfare"
    )
