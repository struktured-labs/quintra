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

RS, PL, EN, TM, SCREEN, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y, WORLD_EXT, WORLD_BOTTOM, LARGE, ORIGIN_X, ORIGIN_Y = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap", "_loop_current_screen",
    "_room_world_width", "_room_world_height", "_room_camera_x", "_room_camera_y",
    "_room_world_extension", "_room_world_bottom",
    "_procgen_current_room_is_large",
    "_room_bg_origin_x", "_room_bg_origin_y",
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
    for _ in range(90):
        # This is a topology/render transaction check, not an endurance
        # encounter. Keep incidental destination fire from making the single
        # sampled scroll register land on a one-pixel damage-shake frame.
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()
    # Riftwild seams now use the same streamed slide as dungeon seams. The
    # transition must settle its hardware scroll and restore OBJ afterwards;
    # otherwise a successful graph hop can look like the hero vanished.
    assert pb.memory[0xFF40] & 0x02, "Riftwild seam left sprites disabled"
    expected_x = ((pb.memory[ORIGIN_X] << 3) + pb.memory[CAMERA_X]) & 0xFF
    expected_y = ((pb.memory[ORIGIN_Y] << 3) + pb.memory[CAMERA_Y]) & 0xFF
    for _ in range(20):
        if (pb.memory[0xFF43], pb.memory[0xFF42]) == (expected_x, expected_y):
            break
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()
        expected_x = (
            (pb.memory[ORIGIN_X] << 3) + pb.memory[CAMERA_X]) & 0xFF
        expected_y = (
            (pb.memory[ORIGIN_Y] << 3) + pb.memory[CAMERA_Y]) & 0xFF
    assert pb.memory[0xFF43] == expected_x and pb.memory[0xFF42] == expected_y, (
        f"Riftwild seam camera wrong: "
        f"{pb.memory[0xFF43]},{pb.memory[0xFF42]} != {expected_x},{expected_y}")

def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()

    # Simulate a cleared first boss and leave through its south door.
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0]; pb.memory[RS + 11] = 1
    # The fixture rewrites the logical room to the defeated compact arena.
    # Do not retain the actual opening field's world dimensions.
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
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
    # the field; the reciprocal east exit lives at the true x=240 boundary.
    assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (0, 0), (
        f"boss arrival camera is "
        f"{pb.memory[CAMERA_X]},{pb.memory[CAMERA_Y]} "
        f"from direction {pb.memory[RS + 6]}")
    assert pb.memory[TM + 10] == 39 and pb.memory[TM + 9 * 20] == 39
    assert pb.memory[TM + 9 * 20 + 19] == 36
    assert pb.memory[TM + 16 * 20 + 10] == 36, \
        "obsolete south viewport edge is not an open internal trail"
    assert pb.memory[WORLD_EXT + 8 * 11 + 10] == 36
    assert pb.memory[WORLD_EXT + 9 * 11 + 10] == 36
    assert pb.memory[WORLD_BOTTOM + 13 * 31 + 9] == 36
    assert pb.memory[WORLD_BOTTOM + 13 * 31 + 10] == 36
    assert pb.memory[WORLD_BOTTOM + 2 * 31 + 14] == pb.memory[TM + 4 * 20 + 5], \
        "southern field lost its seed-stable landmark family"
    assert pb.memory[TM + 8 * 20 + 10] == 36, "Riftwild center lacks path terrain"
    # The boss exit arrives at the actual southern edge. Follow the camera
    # north before judging the label placed in the top portion of the field.
    put16(pb, PL + 11, 60)
    pb.memory[PL + 15] = 120
    for _ in range(64): pb.tick()
    assert pb.memory[CAMERA_Y] == 0
    assert pb.memory[0xFF42] == ((pb.memory[ORIGIN_Y] << 3) & 0xFF)
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
         pb.memory[EN + i * 28 + 7] | pb.memory[EN + i * 28 + 8] << 8)
        for i in range(32) if pb.memory[EN + i * 28] == 2
    ]
    hostile_records = [
        bytes(pb.memory[EN + i * 28:EN + (i + 1) * 28])
        for i in range(32) if pb.memory[EN + i * 28] == 2
    ]
    assert hostile_count(pb) > 0, "test seed produced no overworld encounter"
    assert any(x >= 160 for x, _ in hostile_positions), \
        f"Riftwild spawned no far-field hostile: {hostile_positions}"
    assert any(y >= 136 for _, y in hostile_positions), \
        f"Riftwild spawned no southern-field hostile: {hostile_positions}"
    # Incidental knockback made this camera contract depend on the random
    # encounter.  Keep the already-inspected spawn distribution, then sample
    # the actual 248-136 southern camera bound deterministically.
    clear_hostiles(pb)
    put16(pb, PL + 9, 224); put16(pb, PL + 11, 224)
    pb.memory[PL + 15] = 120
    for _ in range(64): pb.tick()
    assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (88, 112), (
        f"camera={pb.memory[CAMERA_X]},{pb.memory[CAMERA_Y]} "
        f"player={pb.memory[PL + 9] | pb.memory[PL + 10] << 8},"
        f"{pb.memory[PL + 11] | pb.memory[PL + 12] << 8} "
        f"world={pb.memory[RS + 17]}/{pb.memory[RS + 18]} "
        f"size={pb.memory[WORLD_W]},{pb.memory[WORLD_H]}")
    assert (pb.memory[0xFF43], pb.memory[0xFF42]) == (
        ((pb.memory[ORIGIN_X] << 3) + 88) & 0xFF,
        ((pb.memory[ORIGIN_Y] << 3) + 112) & 0xFF), \
        "Riftwild camera did not reach its southeast bound"
    pb.screen.image.save(ROOT / "tmp" / "riftwild-southeast-field.png")
    put16(pb, PL + 9, 72); put16(pb, PL + 11, 40)
    for _ in range(64): pb.tick()
    assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (0, 0)
    assert (pb.memory[0xFF43], pb.memory[0xFF42]) == (
        (pb.memory[ORIGIN_X] << 3) & 0xFF,
        (pb.memory[ORIGIN_Y] << 3) & 0xFF)

    # Riftwild encounters never seal exits: leave screen 0 with its generated
    # hostiles alive, then explore the northern cave before taking the short
    # 0 --E--> 1 --E--> 2 --S--> gate-8 speed route.
    for off, value in enumerate(hostile_records[0]):
        pb.memory[EN + off] = value
    exit_at(pb, 232, 60, clear=False); assert pb.memory[RS + 18] == 1, pb.memory[RS + 18]
    exit_at(pb, 232, 60); assert pb.memory[RS + 18] == 2, pb.memory[RS + 18]
    exit_at(pb, 232, 60); assert pb.memory[RS + 18] == 3, pb.memory[RS + 18]
    exit_at(pb, 232, 60); assert pb.memory[RS + 18] == 4, pb.memory[RS + 18]
    exit_at(pb, 232, 60); assert pb.memory[RS + 18] == 5, pb.memory[RS + 18]
    # Screen 5's cave staircase is a nonlinear hop to vault 30 and back.
    clear_hostiles(pb); put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(45): pb.tick()
    assert pb.memory[RS + 18] == 30 and pb.memory[RS + 19] == 5
    assert (pb.memory[PL + 9], pb.memory[PL + 11]) == (72, 60), \
        "cave arrival did not use the body-safe world-center intersection"
    put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    for _ in range(45): pb.tick()
    assert pb.memory[RS + 18] == 5, "vault staircase did not return"
    assert (pb.memory[PL + 9], pb.memory[PL + 11]) == (72, 60), \
        "vault return did not use the body-safe world-center intersection"
    exit_at(pb, 0, 60); assert pb.memory[RS + 18] == 4, pb.memory[RS + 18]
    exit_at(pb, 0, 60); assert pb.memory[RS + 18] == 3, pb.memory[RS + 18]
    exit_at(pb, 0, 60); assert pb.memory[RS + 18] == 2, pb.memory[RS + 18]
    exit_at(pb, 72, 232); assert pb.memory[RS + 18] == 8, pb.memory[RS + 18]
    assert pb.memory[TM + 8 * 20 + 10] != 34, \
        "dungeon arch woke before its Riftwild Warden was defeated"
    # This topology/media test already proved that screen 3 is reachable; its
    # encounter was cleared synthetically above. Publish the persistent kill
    # bit, then regenerate the arch and prove that the expedition gate wakes.
    pb.memory[RS + 47] |= 0x04
    exit_at(pb, 72, 0); assert pb.memory[RS + 18] == 2, pb.memory[RS + 18]
    exit_at(pb, 72, 232); assert pb.memory[RS + 18] == 8, pb.memory[RS + 18]
    assert pb.memory[TM + 8 * 20 + 10] == 34, \
        "Warden victory did not wake the dungeon arch"
    for _ in range(60): pb.tick()
    pb.screen.image.save(ROOT / "tmp" / "riftwild-gate.png")
    seen = (
        pb.memory[RS + 21] | (pb.memory[RS + 22] << 8),
        pb.memory[RS + 48], pb.memory[RS + 49], pb.memory[RS + 50],
    )
    expected_seen = (0x013F, 0, 0x40, 0)
    assert seen == expected_seen, (
        f"Riftwild map did not reveal exact visited cells: {seen}"
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
    assert pb.memory[bg + 4 * 32 + 5] == 50, "current cell lacks player map pin"
    assert pb.memory[bg + 12 * 32 + 1] == 52, "visited vault lacks violet glyph"
    assert pb.memory[bg + 12 * 32 + 11] == 95, \
        "unseen cell lost its dim 6x6-grid placeholder"
    assert sum(pb.memory[bg + y * 32 + x] == 95
               for y in (2, 4, 6, 8, 10, 12)
               for x in (1, 3, 5, 7, 9, 11)) == 28, \
        "Riftwild map did not expose all twenty-eight unseen field slots"
    assert all(pb.memory[bg + 2 * 32 + x] == 53
               for x in (2, 4, 6, 8, 10)), \
        "Riftwild graph lost its visited east-west links"
    assert pb.memory[bg + 3 * 32 + 5] == 54, \
        "Riftwild graph lost its visited south link"
    # The route symbols explain themselves in the live 20x18 tilemap.
    assert tuple(pb.memory[bg + 2 * 32 + x] for x in range(13, 17)) == \
        (50, 64, 65, 66), "Riftwild map lost YOU legend"
    assert tuple(pb.memory[bg + 5 * 32 + x] for x in range(13, 18)) == \
        (34, 85, 84, 93, 86), "Riftwild map lost GATE legend"
    assert tuple(pb.memory[bg + 8 * 32 + x] for x in range(13, 18)) == \
        (90, 91, 68, 92, 93), "Riftwild map lost RIFT legend"
    assert tuple(pb.memory[bg + 11 * 32 + x] for x in range(13, 18)) == \
        (51, 71, 65, 67, 67), "Riftwild map lost BOSS legend"
    # Semantic colors must survive actual CGB rendering, not just nominal
    # palette attributes.
    image = pb.screen.image
    here_rgb = image.getpixel((5 * 8 + 4, 4 * 8 + 4))[:3]
    rift_rgb = image.getpixel((13 * 8 + 2, 8 * 8 + 3))[:3]
    boss_rgb = image.getpixel((13 * 8 + 4, 11 * 8 + 4))[:3]
    assert len({here_rgb, rift_rgb, boss_rgb}) == 3, \
        f"Riftwild semantic colors collapsed: {here_rgb}, {rift_rgb}, {boss_rgb}"
    map_shot = ROOT / "tmp" / "riftwild-map.png"
    map_shot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(map_shot)
    pb.button("b"); pb.tick(24)
    assert pb.memory[SCREEN] == 5, "map did not resume Riftwild"

    put16(pb, PL + 9, 72); put16(pb, PL + 11, 52)
    # Entering a dungeon streams a complete 31x31 room and can legitimately
    # span several VBlanks.  Observe the committed room, not the middle of
    # that display transaction.
    for _ in range(90): pb.tick()
    assert pb.memory[RS + 17] == 0, "gate did not return to dungeon mode"
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] + 1, \
        "next dungeon did not advance depth"
    assert pb.memory[RS + 20] == 1, (
        "new dungeon map did not reset to entry cell: "
        f"room={pb.memory[RS + 1]} bosses={pb.memory[RS + 11]} "
        f"world={pb.memory[RS + 17]}/{pb.memory[RS + 18]} "
        f"seen={tuple(pb.memory[RS + off] for off in (20, 28, 30, 32))}"
    )
    pb.stop(save=False)
    print("[overworld] PASS 248x248 field + 2D camera + visited 6x6 map -> dungeon gate")

if __name__ == "__main__": main()
