#!/usr/bin/env python3
"""Regression: specialist IDs map to four unique OBJ tiles loaded by the ROM."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
AI_SOURCE = (ROOT / "src/game/enemy_ai.c").read_text()
ENEMY_HEADER = (ROOT / "src/generated/enemies.h").read_text()

SPECIALISTS = {
    11: (72, 37, "FOLD_STAR", "SPR_ENEMY_FOLD_STAR", "fold-star"),
    12: (73, 21, "FLUTTERBAT", "SPR_ENEMY_FLUTTERBAT", "flutterbat"),
    13: (74, 34, "GLOAM_LEECH", "SPR_ENEMY_GLOAM_LEECH", "gloam-leech"),
    14: (75, 20, "CINDER_MAW", "SPR_ENEMY_CINDER_MAW", "cinder-maw"),
    15: (76, 20, "RIFT_OOZE", "SPR_ENEMY_RIFT_OOZE", "rift-ooze"),
    16: (77, 21, "MIRROR_MOTH", "SPR_ENEMY_MIRROR_MOTH", "mirror-moth"),
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
    for enemy_id, (_, _, enemy_symbol, sprite_symbol, name) in SPECIALISTS.items():
        id_pattern = rf"#define\s+ENEMY_{enemy_symbol}\s+{enemy_id}\b"
        assert re.search(id_pattern, ENEMY_HEADER), f"{name} generated ID drifted"
        pattern = rf"case\s+ENEMY_{enemy_symbol}\s*:\s*return\s+{sprite_symbol}\s*;"
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
    for enemy_id, (slot, legacy_slot, _, _, name) in SPECIALISTS.items():
        tile = bytes(pb.memory[0x8000 + slot * 16 + i] for i in range(16))
        legacy = bytes(pb.memory[0x8000 + legacy_slot * 16 + i] for i in range(16))
        assert any(tile), f"{name} OBJ tile is blank in runtime VRAM"
        assert tile != legacy, f"{name} still aliases its legacy silhouette"
        tiles[enemy_id] = tile
    assert len(set(tiles.values())) == len(SPECIALISTS), "specialist OBJ silhouettes are not unique"

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

    # A Flutterbat can fit into a diagonal notch that the champion's wider
    # feet-box cannot enter. Recreate that exact corner: NE is blocked by the
    # tile above, while east is open. Its cardinal fallback must escape rather
    # than repeatedly settling there and softlocking a sealed melee room.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    pb.memory[tilemap + 9 * 20 + 10] = 2
    bat = entities
    pb.memory[bat] = 2
    pb.memory[bat + 1] = 3
    put_fix8(pb, bat + 2, 80)
    put_fix8(pb, bat + 6, 79)
    pb.memory[bat + 14] = 2
    pb.memory[bat + 15] = 1       # flutter phase
    pb.memory[bat + 16] = 1       # move on the next update
    pb.memory[bat + 17] = 12
    pb.memory[bat + 19] = 1       # NE diagonal seed
    pb.memory[bat + 25] = 0x66
    pb.memory[player + 2] = 20
    pb.memory[addr("_g_hitstop")] = 0
    for _ in range(20):
        pb.tick()
        if pb.memory[bat + 3] != 80 or pb.memory[bat + 7] != 79:
            break
    assert pb.memory[bat + 3] > 80 and pb.memory[bat + 7] == 79, (
        f"Flutterbat did not cardinal-fallback out of notch: "
        f"{pb.memory[bat + 3]},{pb.memory[bat + 7]}"
    )

    # Mirror Moth runs through its typed AI_MIRROR dispatch in bank 3. Real
    # controller movement to the right must make it step left, and its authored
    # fire clock must produce a hostile reflected bolt without direct writes.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    put16(pb, player + 9, 64)
    put16(pb, player + 11, 72)
    pb.memory[player + 2] = 20
    moth = entities
    pb.memory[moth] = 2
    pb.memory[moth + 1] = 3
    put_fix8(pb, moth + 2, 112)
    put_fix8(pb, moth + 6, 72)
    pb.memory[moth + 14] = 4
    pb.memory[moth + 17] = 16
    pb.memory[moth + 18] = 116      # four ticks from reflected fire
    pb.memory[moth + 25] = 0x66
    pb.memory[addr("_g_hitstop")] = 0
    pb.tick()                        # initialize last-player sample
    player_x0, moth_x0 = pb.memory[player + 9], pb.memory[moth + 3]
    pb.button_press("right")
    for _ in range(18):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[player + 9] > player_x0, "controller did not move hero right"
    assert pb.memory[moth + 3] < moth_x0, (
        f"Mirror Moth did not reverse hero movement: {moth_x0}->{pb.memory[moth + 3]}"
    )
    reflected = []
    for i in range(1, 32):
        ep = entities + i * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1:
            reflected.append((pb.memory[ep + 5], pb.memory[ep + 9]))
    assert reflected, "Mirror Moth did not fire its reflected hostile bolt"

    # Kill a Rift Ooze through the real projectile/combat loop. The corpse
    # must become two fragile crawler fragments, not merely claim to split in
    # authored data or a unit-test-only helper.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    ooze = entities
    shot = entities + 28
    # Saturate all other slots with harmless long-lived FX. Both fragments
    # must still appear, proving the lethal shot is released early enough.
    for i in range(2, 32):
        filler = entities + i * 28
        pb.memory[filler] = 4
        pb.memory[filler + 1] = 3
        pb.memory[filler + 16] = 100
    pb.memory[ooze] = 2
    pb.memory[ooze + 1] = 3
    put_fix8(pb, ooze + 2, 80)
    put_fix8(pb, ooze + 6, 72)
    pb.memory[ooze + 14] = 1
    pb.memory[ooze + 16] = 30
    pb.memory[ooze + 17] = 15
    pb.memory[ooze + 25] = 0x66
    pb.memory[ooze + 27] = 1
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    put_fix8(pb, shot + 2, 80)
    put_fix8(pb, shot + 6, 72)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 10
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 27] = 1
    pb.memory[addr("_g_hitstop")] = 0
    for _ in range(4):
        pb.tick()
    fragments = []
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == 2 and pb.memory[e + 1] & 1:
            fragments.append((pb.memory[e + 17], pb.memory[e + 14]))
    assert fragments.count((0, 2)) == 2, f"Rift Ooze split drifted: {fragments}"
    assert all(enemy_id != 15 for enemy_id, _ in fragments), (
        f"dead Rift Ooze remained active: {fragments}"
    )
    pb.stop(save=False)
    print("[enemy-id] PASS specialist art + leech routing + flutterbat escape + mirror motion/fire + ooze split")


if __name__ == "__main__":
    main()
