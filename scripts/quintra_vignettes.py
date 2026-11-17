"""Shared PyBoy helper: keep stage-transition vignettes out of other contracts.

Vignettes play the first time per run a dungeon or the Riftwild is entered
(scripts/test_stage_vignettes.py owns that behavior). Gameplay fixtures that
cross those seams for other reasons pre-mark every vignette as seen right
after class select, so their timing and screen expectations are unchanged.
"""
import re
from pathlib import Path


def mute_vignettes(pb, rom):
    noi = Path(rom).with_suffix(".noi").read_text()
    match = re.search(r"DEF _vignette_seen 0x([0-9A-Fa-f]+)", noi)
    if not match:  # ROMs older than the vignette player
        return
    addr = int(match.group(1), 16)
    pb.memory[addr] = pb.memory[addr + 1] = 0xFF
