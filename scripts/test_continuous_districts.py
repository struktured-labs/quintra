#!/usr/bin/env python3
"""Wide dungeon neighbours stream as one visible, reversible district.

Depth names are brief arrival callouts; after their timer expires the rotated
BG ring must contain the exact generated terrain again.
"""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
STATE = ROOT / "tmp/stage-states/quintra-stage-01-court-wolfkin-easy.pyboy"
VERTICAL_STATE = (
    ROOT / "tmp/stage-states/quintra-stage-01-entry-wolfkin-easy.pyboy"
)
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


(RS, PL, TM, EXT, BOTTOM, SEALED, PUZZLE, LARGE, WORLD_W, WORLD_H, SCREEN,
 CAMERA_X, CAMERA_Y, ORIGIN_X, ORIGIN_Y, SHADOW_OAM, MUSIC_ROW,
 LABEL_TICKS) = map(addr, (
    "_run_state", "_player", "_room_tilemap", "_room_world_extension",
    "_room_world_bottom", "_room_combat_sealed", "_room_puzzle_locked",
    "_procgen_current_room_is_large", "_room_world_width",
    "_room_world_height", "_loop_current_screen", "_room_camera_x", "_room_camera_y",
    "_room_bg_origin_x", "_room_bg_origin_y", "_shadow_OAM", "_music_row",
    "_room_district_label_ticks",
))

DISTRICT_LABELS = (
    (85, 84, 79, 86),          # GATE
    (81, 89, 80, 86, 76),      # LOWER
    (82, 86, 86, 90),          # DEEP
    (77, 91, 91, 86, 76),      # INNER
    (92, 86, 84, 76, 79),      # HEART
)
BGT_DOOR = 3
BGT_DOOR_LOCKED = 126


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def hero_visible(pb):
    return all(
        pb.memory[SHADOW_OAM + sprite * 4] != 0
        and pb.memory[SHADOW_OAM + sprite * 4 + 1] != 0
        for sprite in range(4)
    )


def logical_tile(pb, x, y):
    if y < 17:
        if x < 20:
            return pb.memory[TM + y * 20 + x]
        return pb.memory[EXT + y * 11 + x - 20]
    return pb.memory[BOTTOM + (y - 17) * 31 + x]


def assert_rotated_bg_matches(pb, label):
    old_vbk = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    ox, oy = pb.memory[ORIGIN_X], pb.memory[ORIGIN_Y]
    mismatches = []
    for y in range(31):
        for x in range(31):
            physical = 0x9800 + ((oy + y) & 31) * 32 + ((ox + x) & 31)
            actual, expected = pb.memory[physical], logical_tile(pb, x, y)
            # The named depth sign is display-only and brief. Pin its letters
            # only during the two-second arrival beat; afterward every byte
            # must match the generated collision terrain beneath it.
            district = min((pb.memory[RS + 1] % 64) // 6, 4)
            letters = DISTRICT_LABELS[district]
            if (pb.memory[LABEL_TICKS] > 0
                    and y == 1 and 8 <= x < 8 + len(letters)):
                expected = letters[x - 8]
            # Combat/puzzle seals are display overlays: collision memory
            # deliberately remains BGT_DOOR while boundary tiles draw the
            # barred BGT_DOOR_LOCKED cue. The dedicated door suite owns the
            # finer entered/seen-neighbour policy; this streamer contract
            # accepts the overlay only on a real sealed boundary door.
            if (expected == BGT_DOOR and actual == BGT_DOOR_LOCKED
                    and (pb.memory[SEALED] or pb.memory[PUZZLE])
                    and (x in (0, 30) or y in (0, 30))):
                expected = BGT_DOOR_LOCKED
            if actual != expected:
                mismatches.append((x, y, actual, expected))
    pb.memory[0xFF4F] = old_vbk
    assert not mismatches, (
        f"{label}: {len(mismatches)} rotated BG mismatches; "
        f"first={mismatches[:12]}; "
        f"row1-vram={[pb.memory[0x9800 + ((oy + 1) & 31) * 32 + ((ox + x) & 31)] for x in range(20)]}; "
        f"row1-ram={[logical_tile(pb, x, 1) for x in range(20)]}")


def cross(pb, target, x, expected_origin, expected_camera, label):
    pb.memory[SEALED] = 0
    pb.memory[PUZZLE] = 0
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, 60)
    lcd_samples = []
    sprite_samples = []
    scroll_samples = []
    music_rows = set()
    for _ in range(120):
        pb.tick()
        lcd_samples.append(bool(pb.memory[0xFF40] & 0x80))
        sprite_samples.append(hero_visible(pb))
        scroll_samples.append(pb.memory[0xFF43])
        music_rows.add(pb.memory[MUSIC_ROW])
        if (pb.memory[RS + 1] == target
                and pb.memory[ORIGIN_X] == expected_origin
                and pb.memory[CAMERA_X] == expected_camera
                and pb.memory[0xFF43]
                    == ((expected_origin << 3) + expected_camera) & 0xFF):
            break
    else:
        raise AssertionError(
            f"{label}: seam never settled room={pb.memory[RS + 1]} "
            f"origin={pb.memory[ORIGIN_X]} camera={pb.memory[CAMERA_X]} "
            f"SCX={pb.memory[0xFF43]}")
    assert all(lcd_samples), f"{label}: seam blanked the LCD"
    assert all(sprite_samples), f"{label}: champion disappeared during seam"
    assert len(set(scroll_samples)) >= 10, (
        f"{label}: boundary did not visibly stream: {scroll_samples}")
    assert len(music_rows) >= 2, f"{label}: music droned during stream"
    assert pb.memory[LARGE] == 1
    assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    assert_rotated_bg_matches(pb, label)


def cross_vertical(pb, target, y, expected_origin, expected_camera, label):
    pb.memory[SEALED] = 0
    pb.memory[PUZZLE] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, y)
    lcd_samples = []
    sprite_samples = []
    scroll_samples = []
    music_rows = set()
    for _ in range(120):
        pb.tick()
        lcd_samples.append(bool(pb.memory[0xFF40] & 0x80))
        sprite_samples.append(hero_visible(pb))
        scroll_samples.append(pb.memory[0xFF42])
        music_rows.add(pb.memory[MUSIC_ROW])
        if (pb.memory[RS + 1] == target
                and pb.memory[ORIGIN_Y] == expected_origin
                and pb.memory[CAMERA_Y] == expected_camera
                and pb.memory[0xFF42]
                    == ((expected_origin << 3) + expected_camera) & 0xFF):
            break
    else:
        raise AssertionError(
            f"{label}: seam never settled room={pb.memory[RS + 1]} "
            f"origin={pb.memory[ORIGIN_Y]} camera={pb.memory[CAMERA_Y]} "
            f"SCY={pb.memory[0xFF42]}")
    assert all(lcd_samples), f"{label}: seam blanked the LCD"
    assert all(sprite_samples), f"{label}: champion disappeared during seam"
    assert len(set(scroll_samples)) >= 10, (
        f"{label}: boundary did not visibly stream: {scroll_samples}")
    assert len(music_rows) >= 2, f"{label}: music droned during stream"
    assert pb.memory[LARGE] == 1
    assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    assert_rotated_bg_matches(pb, label)


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    with STATE.open("rb") as handle:
        pb.load_state(handle)
    for _ in range(12):
        pb.tick()
    assert pb.memory[RS + 1] == 5
    assert pb.memory[ORIGIN_X] == pb.memory[ORIGIN_Y] == 0

    # Court 5 and court 4 are consecutive wide fields on the first snake row.
    cross(pb, target=4, x=0, expected_origin=1, expected_camera=88,
          label="west 5->4")
    # SELECT temporarily owns the same hardware BG map. Returning from the
    # tile-native Compass must rebuild the current 31x31 field at its rotated
    # origin, not snap the district to origin zero or expose stale map glyphs.
    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert pb.memory[SCREEN] == 8, "SELECT did not open Compass after wide seam"
    pb.button("b")
    for _ in range(30):
        pb.tick()
    assert pb.memory[SCREEN] == 5, "Compass did not resume the wide district"
    assert (pb.memory[ORIGIN_X], pb.memory[CAMERA_X], pb.memory[0xFF43]) == (
        1, 88, 96), "Compass resume lost the rotated west-arrival camera"
    assert_rotated_bg_matches(pb, "Compass resume at rotated origin")
    cross(pb, target=5, x=232, expected_origin=0, expected_camera=0,
          label="east 4->5")
    pb.stop(save=False)

    # The objective seam is the stable vertical member of every generated
    # fold: local 1 branches south to local 10. Exercise both directions from
    # the real stage-entry checkpoint instead of assuming the obsolete 5->6
    # snake turn still exists.
    pb = PyBoy(str(ROM), window="null", cgb=True)
    with VERTICAL_STATE.open("rb") as handle:
        pb.load_state(handle)
    for _ in range(12):
        pb.tick()
    assert pb.memory[RS + 1] == 1
    assert pb.memory[ORIGIN_X] == pb.memory[ORIGIN_Y] == 0
    cross_vertical(pb, target=10, y=232, expected_origin=31,
                   expected_camera=0, label="south 1->10")
    cross_vertical(pb, target=1, y=0, expected_origin=0,
                   expected_camera=112, label="north 10->1")
    assert pb.memory[ORIGIN_X] == pb.memory[ORIGIN_Y] == 0
    pb.stop(save=False)
    print("[continuous-districts] PASS reversible wide seam, LCD/hero/music "
          "continuous, Compass resume, rotated 31x31 destination exact")


if __name__ == "__main__":
    main()
