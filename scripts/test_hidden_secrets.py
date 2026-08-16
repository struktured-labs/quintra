#!/usr/bin/env python3
"""Live-ROM contract for optional ordinary-looking shot/walk/push secrets."""
from test_boss_identity import addr, put16
from test_stage_archetypes import (
    EN, PL, RS, TM, archetype_sample_cell, generated_room,
)


ENTITY_SIZE = 28
KIND = addr("_room_hidden_secret_kind")
SX = addr("_room_hidden_secret_x")
SY = addr("_room_hidden_secret_y")
SX2 = addr("_room_hidden_secret_x2")
SY2 = addr("_room_hidden_secret_y2")
SECRET_BIT = addr("_room_hidden_secret_bit")
BGT_FLOOR, BGT_WALL, BGT_DOOR = 1, 2, 3
BGT_BLOCK, BGT_BLOCK_TR, BGT_BLOCK_BL, BGT_BLOCK_BR = 25, 28, 29, 30


def put_fix8(pb, address, pixels):
    value = pixels << 8
    for byte in range(4):
        pb.memory[address + byte] = (value >> (byte * 8)) & 0xFF


def clear_board(pb):
    for offset in range(32 * ENTITY_SIZE):
        pb.memory[EN + offset] = 0
    for offset in range(20 * 17):
        pb.memory[TM + offset] = BGT_FLOOR


def main():
    checked = []

    def probe(pb, _tiles):
        clear_board(pb)

        # An utterly ordinary north-wall pair responds to player fire. Drive
        # projectile_update_one through the resident entity table.
        pb.memory[KIND] = 1
        pb.memory[SECRET_BIT] = 0x08
        pb.memory[RS + 28] &= 0x87
        pb.memory[SX], pb.memory[SY] = 10, 0
        pb.memory[SX2], pb.memory[SY2] = 11, 0
        pb.memory[TM + 10] = pb.memory[TM + 11] = BGT_WALL
        shot = EN
        pb.memory[shot], pb.memory[shot + 1] = 1, 0x11
        put_fix8(pb, shot + 2, 80)
        put_fix8(pb, shot + 6, 0)
        pb.memory[shot + 12] = 9
        pb.memory[shot + 14] = 1
        pb.memory[shot + 16] = 12
        pb.memory[shot + 25] = 0x77
        pb.memory[shot + 26] = 1
        for _ in range(5):
            pb.tick()
            if pb.memory[KIND] == 0:
                break
        assert pb.memory[KIND] == 0, "ordinary wall ignored the hidden shot"
        assert pb.memory[TM + 10] == pb.memory[TM + 11] == BGT_DOOR, (
            "hidden shot did not open its paired cache threshold")
        assert pb.memory[RS + 28] & 0x08, "shot secret was not persisted"

        # A normal 2x2 landscape cairn can hide a bonus too. The established
        # ten-frame shove must move the block and reveal the nonessential door.
        clear_board(pb)
        pb.memory[KIND] = 3
        pb.memory[SECRET_BIT] = 0x10
        pb.memory[SX], pb.memory[SY] = 6, 6
        pb.memory[SX2], pb.memory[SY2] = 7, 7
        pb.memory[TM + 6 * 20 + 6] = BGT_BLOCK
        pb.memory[TM + 6 * 20 + 7] = BGT_BLOCK_TR
        pb.memory[TM + 7 * 20 + 6] = BGT_BLOCK_BL
        pb.memory[TM + 7 * 20 + 7] = BGT_BLOCK_BR
        put16(pb, PL + 9, 48)
        put16(pb, PL + 11, 64)
        pb.button_press("up")
        for _ in range(36):
            pb.tick()
            if pb.memory[KIND] == 0:
                break
        pb.button_release("up")
        assert pb.memory[KIND] == 0, "disguised cairn did not reveal on push"
        assert pb.memory[TM + 6] == pb.memory[TM + 7] == BGT_DOOR, (
            "hidden cairn did not open its optional cache door")
        assert pb.memory[RS + 28] & 0x10, "push secret was not persisted"

        # The same normal wall art can instead be a walk-through passage. Use
        # the real north threshold so the cartridge marks it discovered and
        # enters the attached cache overlay rather than merely proving a
        # synthetic interior wall is walkable.
        clear_board(pb)
        pb.memory[KIND] = 2
        pb.memory[SECRET_BIT] = 0x20
        pb.memory[SX], pb.memory[SY] = 10, 0
        pb.memory[SX2], pb.memory[SY2] = 11, 0
        pb.memory[TM + 10] = pb.memory[TM + 11] = BGT_WALL
        put16(pb, PL + 9, 80)
        put16(pb, PL + 11, 0)
        pb.button_press("up")
        for _ in range(120):
            pb.tick()
            if pb.memory[RS + 13] == 2:
                break
        pb.button_release("up")
        assert pb.memory[RS + 28] & 0x20, "walk secret was not persisted"
        assert pb.memory[RS + 13] == 2, "invisible door did not enter its cache"
        checked.extend(("shot", "walk", "push"))

    seed = 0x5EC2E7
    generated_room(0, seed, probe=probe,
                   local_room=archetype_sample_cell(0, seed))
    assert checked == ["shot", "walk", "push"]
    print("[hidden-secrets] PASS ordinary wall shot, invisible walk door, "
          "disguised cairn, persisted anti-farm discoveries")


if __name__ == "__main__":
    main()
