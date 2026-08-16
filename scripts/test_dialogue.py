#!/usr/bin/env python3
"""Live-ROM contract for talkative residents and dungeon wayfarers."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_START
from test_shop_surge import boot_shop


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
DIALOG_SOURCE = (ROOT / "src/game/dialog.c").read_text()
SHOP_COPY_SOURCE = (ROOT / "src/game/shop_copy.c").read_text()
ENTITY_SIZE = 28
PICKUP_MERCHANT = 8
PICKUP_WAYFARER = 21
SCREEN_ROOM = 5
SCREEN_DIALOG = 10


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, SCREEN, LARGE, WORLD_W, WORLD_H = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_loop_current_screen", "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height",
))
DIALOG_KIND, DIALOG_TOPIC, DIALOG_PAGE = map(addr, (
    "_dialog_kind", "_dialog_topic", "_dialog_page",
))


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def put16(pb, where, value):
    pb.memory[where] = value & 0xFF
    pb.memory[where + 1] = (value >> 8) & 0xFF


def tap(pb, button):
    # PyBoy's queued joypad edge crosses the emulated input sampler several
    # frames after the host call; hold/release long enough to observe two
    # distinct hardware edges rather than testing frontend timing.
    pb.button_press(button); tick(pb, 6)
    pb.button_release(button); tick(pb, 8)


def pickups(pb, kind):
    return [EN + slot * ENTITY_SIZE for slot in range(32)
            if pb.memory[EN + slot * ENTITY_SIZE] == 3
            and pb.memory[EN + slot * ENTITY_SIZE + 17] == kind]


def clear_hostiles(pb):
    for slot in range(32):
        entity = EN + slot * ENTITY_SIZE
        if pb.memory[entity] == 2:
            pb.memory[entity] = pb.memory[entity + 1] = 0


def boot_waypoint(stage):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick(pb, 240)
    pb.button("start"); tick(pb, 30)
    pb.button("a"); tick(pb, 60)

    target = STAGE_START[stage] + 5
    pb.memory[RS + 1] = target - 1
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 1
    pb.memory[RS + 18] = 6
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    clear_hostiles(pb)
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[TM + 9 * 20 + 10] = 34
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, f"stage {stage + 1} waypoint did not load"
    tick(pb, 90)
    clear_hostiles(pb)
    speakers = pickups(pb, PICKUP_WAYFARER)
    assert len(speakers) == 1, (
        f"stage {stage + 1} waypoint has {len(speakers)} peaceful creatures")
    speaker = speakers[0]
    assert pb.memory[speaker + 12] == 79, (
        f"stage {stage + 1} wayfarer lost its stage-native sprite slot")
    assert pb.memory[speaker + 18] == stage, (
        f"stage {stage + 1} wayfarer topic is {pb.memory[speaker + 18]}")
    return pb, speaker


def approach_and_talk(pb, speaker, expected_kind, expected_topic):
    x = pb.memory[speaker + 3] | pb.memory[speaker + 4] << 8
    y = pb.memory[speaker + 7] | pb.memory[speaker + 8] << 8
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, max(0, y - 20))
    tick(pb, 4)
    room = pb.memory[RS + 1]
    tap(pb, "a")
    assert pb.memory[SCREEN] == SCREEN_DIALOG, "nearby A did not open dialogue"
    assert pb.memory[DIALOG_KIND] == expected_kind
    assert pb.memory[DIALOG_TOPIC] == expected_topic
    assert pb.memory[DIALOG_PAGE] == 0
    tap(pb, "a")
    assert pb.memory[SCREEN] == SCREEN_DIALOG and pb.memory[DIALOG_PAGE] == 1, (
        f"A did not advance lore to the advice page: "
        f"screen={pb.memory[SCREEN]} page={pb.memory[DIALOG_PAGE]}")
    if expected_kind == PICKUP_MERCHANT:
        # Page two is generated from the live four shelves. Every effect row
        # and its right-aligned price must contain visible font tiles.
        for y in (5, 7, 9, 11):
            effect = bytes(pb.memory[0x9800 + y * 32 + 1:
                                     0x9800 + y * 32 + 14])
            price = bytes(pb.memory[0x9800 + y * 32 + 15:
                                    0x9800 + y * 32 + 18])
            assert any(effect) and any(price), (
                f"merchant stock row {y} did not name effect and cost")
        pb.screen.image.save(ROOT / "tmp" / "merchant-stock.png")
    tap(pb, "b"); tick(pb, 22)
    assert pb.memory[SCREEN] == SCREEN_ROOM, "B did not return to the live room"
    assert pb.memory[RS + 1] == room, "dialogue regenerated or changed the room"


def main():
    # Text begins at column one on the 20-column GBC console. A 20-character
    # line wraps its final glyph to column zero below, which looks like random
    # screen-edge garbage. Keep every authored dialogue literal within the
    # actual 19-character writing width.
    for literal in re.findall(r'"([A-Z0-9 +./:-]+)"',
                              DIALOG_SOURCE + SHOP_COPY_SOURCE):
        assert len(literal) <= 19, (
            f"dialogue line wraps the screen ({len(literal)} chars): {literal!r}")

    # All nine biomes author one creature in their first turn court, sharing
    # one logical kind but inheriting the stage-native slot-79 silhouette.
    for stage in range(9):
        pb, speaker = boot_waypoint(stage)
        if stage == 0:
            approach_and_talk(pb, speaker, PICKUP_WAYFARER, stage)
            assert len(pickups(pb, PICKUP_WAYFARER)) == 1, (
                "wayfarer vanished when returning from dialogue")
        pb.stop(save=False)

    # Dungeon merchants use the same real conversation screen rather than an
    # empty speech bubble, and explain the contact-purchase convention.
    pb = boot_shop(0)
    merchants = pickups(pb, PICKUP_MERCHANT)
    assert len(merchants) == 1, "merchant room lost its speaker"
    approach_and_talk(pb, merchants[0], PICKUP_MERCHANT, 0)
    pb.stop(save=False)
    print("[dialogue] PASS 9 stage creatures + two-page merchant/resident talk")


if __name__ == "__main__":
    main()
