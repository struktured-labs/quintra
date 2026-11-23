#!/usr/bin/env python3
"""An unkillable Bubble must not block room clear / unseal / rooms_cleared."""

from test_will_max import PLAYER, ENTITIES, boot, clear_arena, addr

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
    pb = boot(0)
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
    pb = boot(0)
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
