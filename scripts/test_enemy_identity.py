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


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


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
    for _ in range(240):
        pb.tick()
    tiles = {}
    for enemy_id, (slot, legacy_slot, _, name) in SPECIALISTS.items():
        tile = bytes(pb.memory[0x8000 + slot * 16 + i] for i in range(16))
        legacy = bytes(pb.memory[0x8000 + legacy_slot * 16 + i] for i in range(16))
        assert any(tile), f"{name} OBJ tile is blank in runtime VRAM"
        assert tile != legacy, f"{name} still aliases its legacy silhouette"
        tiles[enemy_id] = tile
    assert len(set(tiles.values())) == 4, "specialist OBJ silhouettes are not unique"

    # Put a live leech across a long pillar wall from the player. Its edge
    # slide must route around cover through the real enemy update loop;
    # otherwise direct homing keeps a sealed room alive indefinitely.
    entities = addr("_entities")
    player = addr("_player")
    tilemap = addr("_room_tilemap")
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    wall_x = 12
    for wall_y in range(3, 15):
        pb.memory[tilemap + wall_y * 20 + wall_x] = 2
    put16(pb, player + 9, 8 * 8)
    put16(pb, player + 11, 12 * 8)
    leech = entities
    pb.memory[leech] = 2
    pb.memory[leech + 1] = 3
    put_fix8(pb, leech + 2, 15 * 8)
    put_fix8(pb, leech + 6, 12 * 8)
    pb.memory[leech + 14] = 4
    pb.memory[leech + 17] = 13
    pb.memory[leech + 25] = 0x66
    frame_counter = addr("_loop_frame_counter")
    before_frames = pb.memory[frame_counter] | (pb.memory[frame_counter + 1] << 8)
    for _ in range(900):
        pb.tick()
    after_frames = pb.memory[frame_counter] | (pb.memory[frame_counter + 1] << 8)
    escaped_x, escaped_y = pb.memory[leech + 3], pb.memory[leech + 7]
    assert escaped_x < wall_x * 8, (
        f"Gloom Leech never routed around cover: {escaped_x},{escaped_y}; "
        f"stuck={pb.memory[leech + 21]} state_timer={pb.memory[leech + 16]} "
        f"flags={pb.memory[leech + 1]} screen={pb.memory[addr('_loop_current_screen')]} "
        f"hp={pb.memory[player + 2]} room={pb.memory[addr('_run_state') + 1]} "
        f"hitstop={pb.memory[addr('_g_hitstop')]} pause={pb.memory[tilemap + 340]}"
        f" loop_frames={before_frames}->{after_frames}"
    )
    pb.stop(save=False)
    print("[enemy-id] PASS unique specialist art + trapped leech edge recovery")


if __name__ == "__main__":
    main()
