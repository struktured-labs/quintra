#!/usr/bin/env python3
"""An unkillable Bubble must not block room clear / unseal / rooms_cleared."""

from pyboy import PyBoy
from quintra_vignettes import mute_after_class_select
from test_will_max import PLAYER, ENTITIES, SCREEN, ROM, clear_arena, addr, press

TITLE, CLASS_SELECT, INTRO, ROOM = 1, 2, 4, 5

FRAME = addr("_loop_frame_counter")


def frame_counter(pb):
    return pb.memory[FRAME] | (pb.memory[FRAME + 1] << 8)


def wait_room_live(pb, limit=1800):
    """room_enter sets SCREEN_ROOM before it finishes; wait for loop_run."""
    last = frame_counter(pb)
    for i in range(limit):
        pb.tick()
        now = frame_counter(pb)
        if now != last:
            for _ in range(30):
                pb.tick()
            return i
    raise AssertionError("room_enter never returned to loop_run")


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
EF_ALIVE = 0x02
ENEMY_SKELETON = 3
ENEMY_BUBBLE = 44
ENEMY_AUX_BUBBLE_IMMORTAL = 0xB7

RS = addr("_run_state")
ROOMS_CLEARED = RS + 9
SEALED = addr("_room_combat_sealed")


def until_screen(pb, value, limit):
    for i in range(limit):
        if pb.memory[SCREEN] == value:
            return i
        pb.tick()
    return -1 if pb.memory[SCREEN] != value else limit


def boot_room(class_id):
    """Reach the first room with the foyer vignette muted (not the tight boot())."""
    pb = PyBoy(str(ROM), window="null", cgb=True)
    if until_screen(pb, INTRO, 600) < 0 and pb.memory[SCREEN] != TITLE:
        raise AssertionError(f"did not reach intro/title, screen={pb.memory[SCREEN]}")
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, TITLE, 2400) >= 0, f"did not reach title, screen={pb.memory[SCREEN]}"
    pb.tick(30)
    press(pb, "start")
    assert until_screen(pb, CLASS_SELECT, 400) >= 0, (
        f"did not reach class select, screen={pb.memory[SCREEN]}")
    pb.tick(20)
    for _ in range(class_id):
        press(pb, "down", held=3, released=6)
    press(pb, "a")
    mute_after_class_select(pb, ROM, settle=30)
    assert until_screen(pb, ROOM, 400) >= 0, f"did not reach room, screen={pb.memory[SCREEN]}"
    wait_room_live(pb)
    assert pb.memory[PLAYER] == class_id, f"class {pb.memory[PLAYER]} != {class_id}"
    return pb


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def poke_enemy(pb, slot, enemy_id, x, y, hp=6, aux=0):
    ep = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[ep + i] = 0
    pb.memory[ep + 0] = ENT_ENEMY
    pb.memory[ep + 1] = EF_ACTIVE | EF_ALIVE
    put16(pb, ep + 3, x)
    put16(pb, ep + 7, y)
    pb.memory[ep + 14] = hp
    pb.memory[ep + 17] = enemy_id
    pb.memory[ep + 19] = aux
    pb.memory[ep + 25] = (6 << 4) | 6
    pb.memory[ep + 26] = 1
    return ep


def deactivate(pb, slot):
    ep = ENTITIES + slot * ENTITY_SIZE
    pb.memory[ep + 0] = 0
    pb.memory[ep + 1] = 0


def test_unkillable_does_not_block_clear():
    pb = boot_room(0)
    try:
        clear_arena(pb)
        # A skeleton plus an unkillable Bubble. Only the skeleton is a clear
        # hostile, so killing it must increment rooms_cleared and unseal.
        poke_enemy(pb, 0, ENEMY_SKELETON, 40, 40, hp=8, aux=0)
        poke_enemy(pb, 1, ENEMY_BUBBLE, 120, 40, hp=6, aux=ENEMY_AUX_BUBBLE_IMMORTAL)
        pb.memory[SEALED] = 1
        cleared0 = pb.memory[ROOMS_CLEARED]
        pb.tick(10)
        assert pb.memory[ENTITIES + 1 * ENTITY_SIZE + 1] & EF_ACTIVE, (
            "unkillable Bubble vanished before the clear check")
        assert pb.memory[SEALED] == 1, "room unsealed while a real enemy still lived"
        deactivate(pb, 0)
        pb.tick(10)
        cleared1 = pb.memory[ROOMS_CLEARED]
        assert cleared1 == (cleared0 + 1) & 0xFF, (
            f"unkillable Bubble blocked rooms_cleared: {cleared0} -> {cleared1}")
        assert pb.memory[SEALED] == 0, "unkillable Bubble blocked door unseal"
        # The Bubble itself must still be present after the clear.
        assert pb.memory[ENTITIES + 1 * ENTITY_SIZE] == ENT_ENEMY, (
            "clear removed the unkillable Bubble")
        assert pb.memory[ENTITIES + 1 * ENTITY_SIZE + 1] & EF_ACTIVE
    finally:
        pb.stop(save=False)


def test_killable_bubble_does_count():
    pb = boot_room(0)
    try:
        clear_arena(pb)
        poke_enemy(pb, 0, ENEMY_BUBBLE, 40, 40, hp=6, aux=0)
        pb.memory[SEALED] = 1
        cleared0 = pb.memory[ROOMS_CLEARED]
        pb.tick(10)
        assert pb.memory[SEALED] == 1, "killable Bubble was ignored before death"
        deactivate(pb, 0)
        pb.tick(10)
        cleared1 = pb.memory[ROOMS_CLEARED]
        assert cleared1 == (cleared0 + 1) & 0xFF, (
            f"killable Bubble did not count as a clear hostile: {cleared0} -> {cleared1}")
        assert pb.memory[SEALED] == 0
    finally:
        pb.stop(save=False)


def main():
    test_unkillable_does_not_block_clear()
    test_killable_bubble_does_count()
    print("[bubble-clear] PASS unkillable Bubble does not block clear; killable one does")


if __name__ == "__main__":
    main()
