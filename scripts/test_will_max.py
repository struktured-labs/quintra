#!/usr/bin/env python3
"""Live-ROM contract: restraint charges Will and every A weapon owns a MAX."""

import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
WILL_OFFSET = 42
WILL_MAX = 180
ENTITY_SIZE = 28


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER, ENTITIES, SCREEN, TILEMAP = map(
    addr, ("_player", "_entities", "_loop_current_screen", "_room_tilemap")
)


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot(class_id):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    press(pb, "start")
    pb.tick(30)
    for _ in range(class_id):
        press(pb, "down", held=3, released=3)
    press(pb, "a")
    pb.tick(90)
    assert pb.memory[SCREEN] == 5 and pb.memory[PLAYER] == class_id
    return pb


def clear_arena(pb):
    for i in range(32 * ENTITY_SIZE):
        pb.memory[ENTITIES + i] = 0
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
    expected = (3, 1, 5, 5, 3)
    for class_id, minimum in enumerate(expected):
        pb = boot(class_id)
        clear_arena(pb)

        # Real idle room frames—not a memory fill—must charge and clamp Will.
        pb.memory[PLAYER + WILL_OFFSET] = 0
        pb.tick(WILL_MAX + 12)
        assert pb.memory[PLAYER + WILL_OFFSET] == WILL_MAX, (
            f"class {class_id} Will did not charge/clamp")

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
            assert all(pb.memory[s + 12] == 122 for s in shots), (
                "Moonfang MAX stopped being a physical cleave")
        elif class_id == 1:
            assert pb.memory[shots[0] + 12] == 123
            assert pb.memory[shots[0] + 14] == 6
            assert pb.memory[shots[0] + 25] == 0x99
        elif class_id == 2:
            assert all(pb.memory[s + 14] == 4 for s in shots)
        elif class_id == 3:
            # Moon Tide is a forward offensive fan, not Undertow again: all
            # five right-facing lanes remain in the forward half-plane, the
            # center is the broadest/piercing breaker, and MAX grants no ward.
            assert all(pb.memory[s + 10] < 0x80 for s in shots), (
                "Picsean Moon Tide still emitted a rear/radial lane")
            assert any(pb.memory[s + 25] == 0xBB and pb.memory[s + 14] == 6
                       for s in shots), "Moon Tide lost its central breaker"
            assert pb.memory[PLAYER + 15] == 0, (
                "Moon Tide still granted defensive invulnerability")
            assert pb.memory[PLAYER + 20] == 0, (
                "Moon Tide still duplicated Undertow's shield")
        elif class_id == 4:
            assert any(pb.memory[s + 12] == 123 for s in shots)

        # An ordinary primary attack spends partial Will. This is what makes
        # restraint a combat choice instead of another automatic cooldown.
        clear_arena(pb)
        pb.memory[PLAYER + WILL_OFFSET] = 90
        fire_right(pb)
        assert pb.memory[PLAYER + WILL_OFFSET] < 8, (
            f"class {class_id} ordinary A preserved partial Will")
        pb.stop(save=False)

    # B is independent of the restraint economy, but Will pauses for the
    # complete protected interval. Neither shield may purchase a safe MAX by
    # waiting inside immunity, and neither destroys progress already earned.
    for class_id, label, shield_floor in ((1, "Stoneskin", 45),
                                           (3, "Undertow", 80)):
        pb = boot(class_id)
        clear_arena(pb)
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
        pb.memory[PLAYER + 19] = 0
        pb.memory[PLAYER + 20] = 0
        # Partial Will proves both halves of the new contract: B preserves the
        # exact value, then restraint resumes once the guard has ended.
        pb.memory[PLAYER + WILL_OFFSET] = 120
        pb.button_press("b")
        for _ in range(12):
            pb.tick()
            if pb.memory[PLAYER + 19] > 0:
                break
        after_b = pb.memory[PLAYER + WILL_OFFSET]
        # The input frame may earn its ordinary one idle point before the
        # signature raises the guard; it must never erase the partial meter.
        assert 120 <= after_b <= 121, (
            f"{label} spent independent Will meter: {after_b}")
        assert pb.memory[PLAYER + 20] > shield_floor, (
            f"{label} did not raise its authored shield")
        if class_id == 3:
            assert pb.memory[PLAYER + 19] > pb.memory[PLAYER + 20], (
                "Undertow cooldown allows a permanent guard loop")
        pb.button_release("b")
        pb.tick(20)
        assert pb.memory[PLAYER + WILL_OFFSET] == after_b, (
            f"{label} charged Will while its shield was active")
        while pb.memory[PLAYER + 20] > 0:
            pb.tick()
        pb.tick(4)
        assert pb.memory[PLAYER + WILL_OFFSET] > after_b, (
            f"Will did not resume after {label} expired")
        pb.stop(save=False)

    # Will owns a purple spirit palette, distinct from red hearts/boss HP and
    # blue MP. The complete meter brightens toward lavender for MAX readiness.
    pb = boot(0)
    pb.memory[PLAYER + WILL_OFFSET] = 90
    pb.tick(16)
    pb.memory[0xFF4F] = 1
    assert tuple(pb.memory[0x9C00 + x] for x in range(12, 16)) == (5,) * 4, \
        "Will bar did not select its independent purple WINDOW palette"
    pb.memory[0xFF4F] = 0
    colors = set(pb.screen.image.crop((96, 136, 128, 144)).getdata())
    assert (192, 64, 248, 255) in colors, \
        f"partial Will bar is not purple: {colors}"
    pb.memory[PLAYER + WILL_OFFSET] = WILL_MAX
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
        fire_right(pb)
        shots = player_shots(pb)
        assert len(shots) >= minimum, f"weapon {weapon} missing MAX geometry"
        assert any(pb.memory[s + 12] == tile for s in shots)
    pb.stop(save=False)
    print("[will-max] PASS five champions + two run weapons own restraint MAX arts")


if __name__ == "__main__":
    main()
