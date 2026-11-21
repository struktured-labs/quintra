#!/usr/bin/env python3
"""Live-ROM contract: restraint charges Will and every A weapon owns a MAX."""

import re
import os
from pathlib import Path

from pyboy import PyBoy
from quintra_vignettes import mute_vignettes


ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get('QUINTRA_TEST_ROM', ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()
WILL_OFFSET = 42
LEVEL_OFFSET = 48
WILL_MAX = 90
ENTITY_SIZE = 28


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER, ENTITIES, SCREEN, TILEMAP, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y = map(
    addr, ("_player", "_entities", "_loop_current_screen", "_room_tilemap",
           "_procgen_current_room_is_large", "_room_world_width",
           "_room_world_height", "_room_camera_x", "_room_camera_y")
)


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def reach_title(pb):
    """Power-on can land in the intro for well over 240 frames. Wait, or
    skip with Start, until the title is actually up."""
    for _ in range(600):
        if pb.memory[SCREEN] == 1:  # SCREEN_TITLE
            return
        pb.tick()
    if pb.memory[SCREEN] != 1:
        press(pb, "start")
        for _ in range(180):
            if pb.memory[SCREEN] == 1:
                return
            pb.tick()


def wait_room(pb, limit=400):
    """Mute may land during RUN_INIT; a foyer vignette can still arm after.
    Skip it with Start once it has started, then wait for the room."""
    skipped = False
    for i in range(limit):
        if pb.memory[SCREEN] == 5:
            return
        if pb.memory[SCREEN] == 6 and not skipped and i >= 8:
            press(pb, "start")
            skipped = True
            continue
        pb.tick()


def boot(class_id):
    from quintra_vignettes import mute_after_class_select
    pb = PyBoy(str(ROM), window="null", cgb=True)
    reach_title(pb)
    pb.tick(30)  # title must settle before Start is accepted
    press(pb, "start")
    for _ in range(200):
        if pb.memory[SCREEN] == 2:  # SCREEN_CLASS_SELECT
            break
        pb.tick()
    pb.tick(30)
    for _ in range(class_id):
        press(pb, "down", held=3, released=3)
    press(pb, "a")
    mute_after_class_select(pb, ROM, settle=8)
    wait_room(pb)
    for btn in ("a", "b", "start", "select", "right", "left", "up", "down"):
        pb.button_release(btn)
    # Foyer entry still eats A for a beat; Will MAX tests need the room live.
    pb.tick(90)
    assert pb.memory[SCREEN] == 5 and pb.memory[PLAYER] == class_id
    return pb


def clear_arena(pb):
    for i in range(32 * ENTITY_SIZE):
        pb.memory[ENTITIES + i] = 0
    # Seeded foyers can be large scrolling rooms. Knockback and MAX geometry
    # tests need a compact, obstacle-free court, not the live start cell.
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W] = 20 * 8
    pb.memory[WORLD_H] = 17 * 8
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    for i in range(20 * 17):
        pb.memory[TILEMAP + i] = 1
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    pb.memory[PLAYER + 22] = 0


def player_shots(pb):
    return [ENTITIES + i * ENTITY_SIZE for i in range(32)
            if pb.memory[ENTITIES + i * ENTITY_SIZE] == 1
            and (pb.memory[ENTITIES + i * ENTITY_SIZE + 1] & 0x10)]


def fire_right(pb):
    # Picsean's play-side recast lock is 360 frames; fixture tests poke
    # a full Will bar and expect the MAX to fire on this press.
    try:
        pb.memory[addr("_picsean_vortex_slow_charge")] = 0
    except RuntimeError:
        pass
    pb.button_press("right")
    pb.button_press("a")
    # Multi-lane MAX arts can cross several VBlanks on real 4 MHz hardware.
    # Wait for the room transaction to commit instead of assuming five host
    # frames always encompass an eight-projectile banked volley.
    for _ in range(40):
        pb.tick()
        if pb.memory[PLAYER + WILL_OFFSET] == 0:
            break
    pb.button_release("a")
    pb.button_release("right")
    # MAX input is processed in the weapon half of room_tick; body dash and
    # projectile motion begin on subsequent room ticks.
    pb.tick(4)


def main():
    # Minimum simultaneous hitbox counts distinguish the five authored MAX
    # geometries without pinning harmless animation/velocity tuning.
    # Picsean's MAX is the Tide Vortex: one inert damage carrier drives the
    # spiral (2026-11-15 spec), so it owns exactly one player projectile.
    # Sauran, Corvin and Vespine use the same carrier model since max-Will v2
    # (2026-11-17 spec); their art is palette washes and direct OAM.
    expected = (3, 1, 1, 1, 1)
    for class_id, minimum in enumerate(expected):
        pb = boot(class_id)
        clear_arena(pb)

        # Real idle room frames—not a memory fill—must charge and clamp Will.
        pb.memory[PLAYER + WILL_OFFSET] = 0
        pb.memory[PLAYER + 7] = 5
        pb.tick(WILL_MAX * 2 + 24)
        assert pb.memory[PLAYER + WILL_OFFSET] == WILL_MAX, (
            f"class {class_id} Will did not charge/clamp")
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 1

        # A room director may have legitimately repopulated the arena during
        # the three-second idle sample. Free those unrelated slots before the
        # simultaneous-hitbox geometry assertion.
        clear_arena(pb)
        before_x = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
        fire_right(pb)
        shots = player_shots(pb)
        assert len(shots) >= minimum, (
            f"class {class_id} MAX has {len(shots)} hitboxes, expected {minimum}")
        assert pb.memory[PLAYER + WILL_OFFSET] < 8, (
            f"class {class_id} MAX did not spend Will")
        if class_id == 0:
            after_x = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
            assert after_x > before_x + 6, "Moonfang MAX did not body-dash"
            # Three physical claw lanes plus the Will wave's crescent
            # (OBJ tiles 200..203; 2026-11-12 Will wave spec).
            claws = [s for s in shots if pb.memory[s + 12] == 122]
            waves = [s for s in shots if 200 <= pb.memory[s + 12] <= 203]
            assert len(claws) >= 3, "Moonfang MAX stopped being a physical cleave"
            assert len(waves) == 3, "Moonfang MAX lost its Will wave"
            assert len(claws) + len(waves) == len(shots), (
                "Moonfang MAX spawned an unexpected shot")
        elif class_id in (1, 2, 4):
            assert len(shots) == 1 and pb.memory[shots[0] + 23] == 0xF0, (
                f"class {class_id} v2 MAX lost its damage carrier")
            assert pb.memory[addr("_will_maxfx_live")] == class_id + 1, (
                f"class {class_id} v2 MAX art did not start")
        elif class_id == 3:
            # Tide Vortex: one carrier (PROJ_AUX_VORTEX) and a live spiral
            # that grants no ward; it is offense, Undertow stays the guard.
            assert len(shots) == 1 and pb.memory[shots[0] + 23] == 0xF0, (
                "Tide Vortex lost its damage carrier")
            assert pb.memory[addr("_picsean_vortex_ticks")] > 0, (
                "Tide Vortex did not start")
            assert pb.memory[PLAYER + 15] == 0, (
                "Tide Vortex granted defensive invulnerability")
            assert pb.memory[PLAYER + 20] == 0, (
                "Tide Vortex duplicated Undertow's shield")

        # An ordinary primary attack spends partial Will. This is what makes
        # restraint a combat choice instead of another automatic cooldown.
        clear_arena(pb)
        pb.memory[PLAYER + WILL_OFFSET] = 45
        fire_right(pb)
        assert pb.memory[PLAYER + WILL_OFFSET] < 8, (
            f"class {class_id} ordinary A preserved partial Will")
        pb.stop(save=False)

    # B magic is independent of the restraint economy, but Will pauses while
    # a held ward is live (2026-11-17 magic spec): no safe MAX bought from
    # inside a shield, and no progress already earned is lost.
    ward_ticks = addr("_magic_ward_ticks")
    for class_id, label in ((1, "Stoneskin"), (3, "Cure"), (0, "Flame Ward")):
        pb = boot(class_id)
        clear_arena(pb)
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
        pb.memory[PLAYER + 2] = max(1, pb.memory[PLAYER + 1] - 2)
        pb.memory[PLAYER + 20] = 0
        pb.memory[PLAYER + WILL_OFFSET] = 60
        pb.button_press("b")
        for _ in range(30):
            pb.tick()
        pb.button_release("b")
        pb.tick(4)
        live = pb.memory[ward_ticks]
        after_b = pb.memory[PLAYER + WILL_OFFSET]
        assert after_b >= 60, f"{label} spent the Will meter: {after_b}"
        if live:
            pb.tick(20)
            assert pb.memory[PLAYER + WILL_OFFSET] == after_b, (
                f"{label} charged Will while its ward was live")
            while pb.memory[ward_ticks] > 0:
                pb.tick()
        pb.tick(8)
        assert pb.memory[PLAYER + WILL_OFFSET] > after_b, (
            f"Will did not resume after {label}")
        pb.stop(save=False)

    # Will owns a purple spirit palette, distinct from red hearts/boss HP and
    # blue MP. The complete meter brightens toward lavender for MAX readiness.
    pb = boot(0)
    pb.memory[PLAYER + WILL_OFFSET] = 45
    pb.memory[PLAYER + LEVEL_OFFSET] = 0
    pb.tick(16)
    pb.memory[0xFF4F] = 1
    assert tuple(pb.memory[0x9C00 + x] for x in range(12, 16)) == (5,) * 4, \
        "Will bar did not select its independent purple WINDOW palette"
    pb.memory[0xFF4F] = 0
    colors = set(pb.screen.image.crop((96, 136, 128, 144)).getdata())
    assert (192, 64, 248, 255) in colors, \
        f"partial Will bar is not purple: {colors}"
    pb.memory[PLAYER + WILL_OFFSET] = WILL_MAX
    pb.memory[PLAYER + LEVEL_OFFSET] = 1
    pb.tick(16)
    colors = set(pb.screen.image.crop((96, 136, 128, 144)).getdata())
    assert (248, 184, 248, 255) in colors, \
        f"full Will bar lacks its lavender MAX cue: {colors}"
    pb.stop(save=False)

    # The two procedural melee pickups also receive distinct full-Will arts.
    pb = boot(0)
    for weapon, minimum, tile in ((20, 8, 122), (21, 1, 123)):
        clear_arena(pb)
        pb.memory[PLAYER + 21] = weapon
        pb.memory[PLAYER + WILL_OFFSET] = WILL_MAX
        pb.memory[PLAYER + LEVEL_OFFSET] = 1
        fire_right(pb)
        shots = player_shots(pb)
        assert len(shots) >= minimum, f"weapon {weapon} missing MAX geometry"
        assert any(pb.memory[s + 12] == tile for s in shots)
    pb.stop(save=False)
    print("[will-max] PASS five champions + two run weapons own restraint MAX arts")


if __name__ == "__main__":
    main()
