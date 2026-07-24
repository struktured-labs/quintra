#!/usr/bin/env python3
"""ROM contract for boss -> authored overworld graph -> next dungeon."""
import re
from pathlib import Path
from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m: raise RuntimeError(name)
    return int(m.group(1), 16)

RS, PL, EN, TM, SCREEN, WORLD_W, CAMERA_X, WORLD_EXT = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap", "_loop_current_screen",
    "_room_world_width", "_room_camera_x", "_room_world_extension",
))

def put16(pb, p, v):
    pb.memory[p] = v & 255; pb.memory[p + 1] = (v >> 8) & 255

def clear_hostiles(pb):
    for i in range(32):
        p = EN + i * 28
        if pb.memory[p] == 2: pb.memory[p] = pb.memory[p + 1] = 0

def hostile_count(pb):
    return sum(pb.memory[EN + i * 28] == 2 for i in range(32))

def exit_at(pb, x, y, clear=True):
    if clear: clear_hostiles(pb)
    put16(pb, PL + 9, x); put16(pb, PL + 11, y)
    assert pb.memory[PL + 9] == (x & 255) and pb.memory[PL + 11] == (y & 255)
    # A full generated-room swap can straddle several video frames; the
    # outdoor rebuild also streams a complete tilemap before it is safe to
    # inspect authored paths.
    for _ in range(90): pb.tick()
    # Riftwild seams now use the same streamed slide as dungeon seams. The
    # transition must settle its hardware scroll and restore OBJ afterwards;
    # otherwise a successful graph hop can look like the hero vanished.
    assert pb.memory[0xFF40] & 0x02, "Riftwild seam left sprites disabled"
    expected_camera = 64 if x == 0 else 0
    assert pb.memory[0xFF43] == expected_camera and pb.memory[0xFF42] == 0, (
        f"Riftwild seam camera wrong: {pb.memory[0xFF43]} != {expected_camera}")

def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()

    # Simulate a cleared first boss and leave through its south door.
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0]; pb.memory[RS + 11] = 1
    # The currently rendered room is still opening cell 0, whose new 6x5
    # maze has no south edge. Publish the defeated arena's unsealed threshold
    # explicitly before exercising the real cleared-boss exit transaction.
    pb.memory[TM + 16 * 20 + 9] = 3
    pb.memory[TM + 16 * 20 + 10] = 3
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == 0
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0], \
        "overworld traversal consumed dungeon depth"
    # Screen 0 is authored E+S only, now bounded by a real tree line rather
    # than dungeon brick. The old x=152 threshold is a traversable seam into
    # the field; the reciprocal east exit lives at the true x=216 boundary.
    assert pb.memory[WORLD_W] == 224 and pb.memory[CAMERA_X] == 0
    assert pb.memory[TM + 10] == 39 and pb.memory[TM + 9 * 20] == 39
    assert pb.memory[TM + 9 * 20 + 19] == 36
    assert pb.memory[TM + 16 * 20 + 10] == 3
    assert pb.memory[WORLD_EXT + 8 * 8 + 7] == 3
    assert pb.memory[WORLD_EXT + 9 * 8 + 7] == 3
    assert pb.memory[TM + 8 * 20 + 10] == 36, "Riftwild center lacks path terrain"
    # The live playfield identifies the region without replacing the walkable
    # grass/path data that collision and procgen parity consume.
    pb.memory[0xFF4F] = 0
    assert bytes(pb.memory[0x9800 + 1 * 32 + 6:0x9800 + 1 * 32 + 14]) == \
        bytes((76, 77, 78, 79, 80, 77, 81, 82)), \
        "Riftwild lacks its tile-native in-play landmark"
    pb.memory[0xFF4F] = 1
    assert all((pb.memory[0x9800 + 1 * 32 + x] & 7) == 3 for x in range(6, 14)), \
        "Riftwild landmark is not using the amber door palette"
    pb.memory[0xFF4F] = 0
    pb.screen.image.save(ROOT / "tmp" / "riftwild-arrival.png")

    # The generated encounter inhabits both halves of the field. Follow the
    # camera across the obsolete viewport edge and capture the paired landmark.
    hostile_positions = [
        (pb.memory[EN + i * 28 + 3] | pb.memory[EN + i * 28 + 4] << 8,
         pb.memory[EN + i * 28 + 5] | pb.memory[EN + i * 28 + 6] << 8)
        for i in range(32) if pb.memory[EN + i * 28] == 2
    ]
    assert any(x >= 160 for x, _ in hostile_positions), \
        f"Riftwild spawned no far-field hostile: {hostile_positions}"
    put16(pb, PL + 9, 192); put16(pb, PL + 11, 60)
    pb.memory[PL + 15] = 120
    for _ in range(40): pb.tick()
    assert pb.memory[CAMERA_X] == 64 and pb.memory[0xFF43] == 64, \
        "Riftwild camera did not reach its far bound"
    pb.screen.image.save(ROOT / "tmp" / "riftwild-far-field.png")
    put16(pb, PL + 9, 72)
    for _ in range(40): pb.tick()
    assert pb.memory[CAMERA_X] == 0 and pb.memory[0xFF43] == 0

    # Riftwild encounters never seal exits: leave screen 0 with its generated
    # hostiles alive, then follow graph 0 --E--> 1 --E--> 2 --S--> gate 6.
    assert hostile_count(pb) > 0, "test seed produced no overworld encounter"
    exit_at(pb, 208, 60, clear=False); assert pb.memory[RS + 18] == 1, pb.memory[RS + 18]
    exit_at(pb, 208, 60); assert pb.memory[RS + 18] == 2, pb.memory[RS + 18]
    # Screen 2's cave staircase is a nonlinear hop to vault 15 and back.
    clear_hostiles(pb); put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(45): pb.tick()
    assert pb.memory[RS + 18] == 15 and pb.memory[RS + 19] == 2
    assert (pb.memory[PL + 9], pb.memory[PL + 11]) == (72, 60), \
        "cave arrival did not use the safe visible center spawn"
    put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(45): pb.tick()
    assert pb.memory[RS + 18] == 2, "vault staircase did not return"
    assert (pb.memory[PL + 9], pb.memory[PL + 11]) == (72, 60), \
        "vault return did not use the safe visible center spawn"
    exit_at(pb, 72, 120); assert pb.memory[RS + 18] == 6, pb.memory[RS + 18]
    assert pb.memory[TM + 8 * 20 + 10] == 34, "dungeon gate has no portal"
    for _ in range(60): pb.tick()
    pb.screen.image.save(ROOT / "tmp" / "riftwild-gate.png")
    seen = pb.memory[RS + 21] | (pb.memory[RS + 22] << 8)
    expected_seen = sum(1 << cell for cell in (0, 1, 2, 6, 15))
    assert seen == expected_seen, (
        f"Riftwild map did not reveal exact visited cells: {seen:#06x}"
    )
    pb.button("select"); pb.tick(24)
    assert pb.memory[SCREEN] == 8, "SELECT did not open visited Riftwild map"
    # Tile rendering is a deliberate multi-VBlank transaction on real CGB
    # hardware; wait for DISPLAY_ON before judging the composed screen.
    for _ in range(90): pb.tick()
    pb.memory[0xFF4F] = 0
    bg = 0x9800
    # The field begins below the heading and uses the same compact one-glyph
    # graph language as the dungeon Compass. The old 3x3 terrain thumbnails
    # consumed the LCD without explaining the two colored squares.
    assert bytes(pb.memory[bg + 0 * 32 + 8:bg + 0 * 32 + 11]) == bytes((87, 84, 94)), \
        "Riftwild map heading was overwritten by its top row"
    assert pb.memory[bg + 7 * 32 + 7] == 50, "current cell lacks cyan HERE glyph"
    assert pb.memory[bg + 13 * 32 + 10] == 52, "visited vault lacks violet glyph"
    assert pb.memory[bg + 4 * 32 + 10] == 95, \
        "unseen cell lost its dim 4x4-grid placeholder"
    assert sum(pb.memory[bg + y * 32 + x] == 95
               for y in (4, 7, 10, 13) for x in (1, 4, 7, 10)) == 11, \
        "Riftwild map did not expose all eleven unseen grid slots"
    assert all(pb.memory[bg + 4 * 32 + x] == 53 for x in (2, 3, 5, 6)), \
        "Riftwild graph lost its visited east-west links"
    assert all(pb.memory[bg + y * 32 + 7] == 54 for y in (5, 6)), \
        "Riftwild graph lost its visited south link"
    # The route symbols explain themselves in the live 20x18 tilemap.
    assert tuple(pb.memory[bg + 4 * 32 + x] for x in range(13, 17)) == \
        (50, 64, 65, 66), "Riftwild map lost YOU legend"
    assert tuple(pb.memory[bg + 7 * 32 + x] for x in range(13, 18)) == \
        (34, 85, 84, 93, 86), "Riftwild map lost GATE legend"
    assert tuple(pb.memory[bg + 10 * 32 + x] for x in range(13, 18)) == \
        (90, 91, 68, 92, 93), "Riftwild map lost RIFT legend"
    assert tuple(pb.memory[bg + 13 * 32 + x] for x in range(13, 18)) == \
        (51, 71, 65, 67, 67), "Riftwild map lost BOSS legend"
    # Semantic colors must survive actual CGB rendering, not just nominal
    # palette attributes.
    image = pb.screen.image
    here_rgb = image.getpixel((7 * 8 + 4, 7 * 8 + 4))[:3]
    rift_rgb = image.getpixel((13 * 8 + 2, 10 * 8 + 3))[:3]
    boss_rgb = image.getpixel((13 * 8 + 4, 13 * 8 + 4))[:3]
    assert len({here_rgb, rift_rgb, boss_rgb}) == 3, \
        f"Riftwild semantic colors collapsed: {here_rgb}, {rift_rgb}, {boss_rgb}"
    map_shot = ROOT / "tmp" / "riftwild-map.png"
    map_shot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(map_shot)
    pb.button("b"); pb.tick(24)
    assert pb.memory[SCREEN] == 5, "map did not resume Riftwild"

    put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(8): pb.tick()
    assert pb.memory[RS + 17] == 0, "gate did not return to dungeon mode"
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] + 1, \
        "next dungeon did not advance depth"
    assert pb.memory[RS + 20] == 1, "new dungeon map did not reset to entry cell"
    pb.stop(save=False)
    print("[overworld] PASS 224px field + camera + visited 4x4 map -> dungeon gate")

if __name__ == "__main__": main()
