#!/usr/bin/env python3
"""Live-ROM contract: run gear, alternate weapons, and shields look different."""

import io
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
STATES = ROOT / "tmp/stage-states"
NOI = ROM.with_suffix(".noi").read_text()
VRAM_TILE = 0x8000
SPR_FX_SWING = 122
SPR_SHIELD_AURA = 127
PLAYER_STARTER_WEAPON = 21


def sym(name):
    match = re.search(rf"DEF _{re.escape(name)} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER = sym("player")
APPEARANCE_TIER = sym("room_appearance_tier")


def emulator():
    return PyBoy(
        str(ROM), window="null", cgb=True,
        ram_file=io.BytesIO(bytes(32 * 1024)),
    )


def load(pb, filename):
    with (STATES / filename).open("rb") as handle:
        pb.load_state(handle)
    for _ in range(4):
        pb.tick()


def obj_palette(pb, slot):
    result = []
    for index in range(8):
        pb.memory[0xFF6A] = slot * 8 + index
        result.append(pb.memory[0xFF6B])
    return bytes(result)


def obj_tile(pb, slot):
    pb.memory[0xFF4F] = 0
    return bytes(pb.memory[VRAM_TILE + slot * 16 + i] for i in range(16))


def resume_room(pb):
    pb.button_press("start")
    for _ in range(10):
        pb.tick()
    pb.button_release("start")
    for _ in range(10):
        pb.tick()
    pb.button_press("b")
    for _ in range(12):
        pb.tick()
    pb.button_release("b")
    for _ in range(24):
        pb.tick()


def main():
    pb = emulator()
    try:
        palettes = []
        for stage, expected in ((1, 0), (2, 1), (4, 2), (7, 3)):
            load(pb, f"quintra-stage-{stage:02d}-entry-wolfkin.pyboy")
            actual = pb.memory[APPEARANCE_TIER]
            assert actual == expected, (
                f"stage {stage} appearance tier {actual}, expected {expected}"
            )
            palettes.append(obj_palette(pb, 1))
        assert len(set(palettes)) == 4, (
            "base/blue/red/pearl-gold champion palettes are not all distinct"
        )

        load(pb, "quintra-stage-01-entry-wolfkin.pyboy")
        sword = obj_tile(pb, SPR_FX_SWING)
        pb.memory[PLAYER + PLAYER_STARTER_WEAPON] = 20  # Rift Flail items[] index
        resume_room(pb)
        flail = obj_tile(pb, SPR_FX_SWING)
        assert sword != flail, "Rift Flail still renders the Fang Forms sword tile"

        load(pb, "quintra-stage-01-entry-sauran.pyboy")
        stone = obj_tile(pb, SPR_SHIELD_AURA)
        load(pb, "quintra-stage-01-entry-picsean.pyboy")
        water = obj_tile(pb, SPR_SHIELD_AURA)
        assert stone != water, "Stoneskin and Tidal Guard still share shield art"
    finally:
        pb.stop(save=False)

    print(
        "[visual-progression] PASS base→blue→red→pearl-gold palettes, "
        "sword≠flail, Stoneskin≠Tidal Guard"
    )


if __name__ == "__main__":
    main()
