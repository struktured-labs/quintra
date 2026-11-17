"""Shared PyBoy helper: keep stage-transition vignettes out of other contracts.

Vignettes play the first time per run a dungeon or the Riftwild is entered
(scripts/test_stage_vignettes.py owns that behavior). Gameplay fixtures that
cross those seams for other reasons pre-mark every vignette as seen right
after class select, so their timing and screen expectations are unchanged.
"""
import re
from pathlib import Path

# offsetof(run_state_t, vignette_seen): appended u16 after shop_civic (59).
VIGNETTE_SEEN_OFFSET = 60


def seen_address(rom):
    noi = Path(rom).with_suffix(".noi").read_text()
    match = re.search(r"DEF _run_state 0x([0-9A-Fa-f]+)", noi)
    return int(match.group(1), 16) + VIGNETTE_SEEN_OFFSET


def mute_vignettes(pb, rom):
    addr = seen_address(rom)
    pb.memory[addr] = pb.memory[addr + 1] = 0xFF
