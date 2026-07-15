#!/usr/bin/env python3
"""Regression: specialist IDs map to four unique OBJ tiles loaded by the ROM."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
AI_SOURCE = (ROOT / "src/game/enemy_ai.c").read_text()

SPECIALISTS = {
    11: (72, 37, "SPR_ENEMY_FOLD_STAR", "fold-star"),
    12: (73, 21, "SPR_ENEMY_FLUTTERBAT", "flutterbat"),
    13: (74, 34, "SPR_ENEMY_GLOAM_LEECH", "gloam-leech"),
    14: (75, 20, "SPR_ENEMY_CINDER_MAW", "cinder-maw"),
}


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def main():
    # Guard the content-ID dispatch itself. This catches accidental fallback to
    # a legacy monster even before the cartridge is built.
    for enemy_id, (_, _, symbol, name) in SPECIALISTS.items():
        pattern = rf"case\s+{enemy_id}\s*:\s*return\s+{symbol}\s*;"
        assert re.search(pattern, AI_SOURCE), f"{name} ID mapping drifted"

    # Boot the real cartridge so room_enter loads OBJ VRAM through the same
    # loader used by gameplay, then compare the compiled 2bpp tiles.
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    assert pb.memory[addr("_music_track_id")] == 18, "ROM did not boot to title"
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    pb.memory[0xFF40] &= 0x7F
    pb.tick(2)

    tiles = {}
    for enemy_id, (slot, legacy_slot, _, name) in SPECIALISTS.items():
        tile = bytes(pb.memory[0x8000 + slot * 16 + i] for i in range(16))
        legacy = bytes(pb.memory[0x8000 + legacy_slot * 16 + i] for i in range(16))
        assert any(tile), f"{name} OBJ tile is blank in runtime VRAM"
        assert tile != legacy, f"{name} still aliases its legacy silhouette"
        tiles[enemy_id] = tile
    assert len(set(tiles.values())) == 4, "specialist OBJ silhouettes are not unique"
    pb.stop(save=False)
    print("[enemy-id] PASS IDs 11-14 -> unique runtime OBJ slots 72-75")


if __name__ == "__main__":
    main()
