#!/usr/bin/env python3
"""ROM contract: Shadow Keep's Bramble Sprite is a live, distinct lane prompt."""

from test_enemy_identity import generated_sprite
from spinner_contract import assert_told_spiral
from test_stage_archetypes import EN, PL, TM, addr, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_BRAMBLE_SPRITE = 27
SPR_BRAMBLE_SPRITE = 79
ROSTER_KIND = addr("_room_roster_kind")
ROOM_ROSTER_MIXED = 0


def active_bramble(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_BRAMBLE_SPRITE):
            return ep
    return None


def main():
    seen = []

    def probe(pb, _tiles):
        assert pb.memory[ROSTER_KIND] == ROOM_ROSTER_MIXED, (
            "Bramble spawn fixture stopped exercising a Mixed room")
        bramble = active_bramble(pb)
        if bramble is None:
            return
        seen.append(1)

        actual = bytes(pb.memory[0x8000 + SPR_BRAMBLE_SPRITE * 16:
                                 0x8000 + (SPR_BRAMBLE_SPRITE + 1) * 16])
        expected = generated_sprite("sprite_enemy_bramble_sprite")
        assert actual == expected, "Shadow Keep did not install Bramble Sprite art"
        assert actual != generated_sprite("sprite_enemy_sunwheel"), \
            "Bramble Sprite reused Golden Temple's Sunwheel silhouette"

        # The live Spinner driver arms a told spiral: one shot per compass
        # point every eight frames (#3), never an instant burst. Retire the
        # room's other bodies and republish the observed procgen Bramble.
        fixture = bytes(pb.memory[bramble:bramble + ENTITY_SIZE])
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            pb.memory[ep] = pb.memory[ep + 1] = 0
        pb.tick(4)
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            pb.memory[ep] = pb.memory[ep + 1] = 0
        for offset, value in enumerate(fixture):
            pb.memory[bramble + offset] = value
        assert_told_spiral(pb, bramble, EN, PL, TM, "Bramble Sprite")

    # Brambles deliberately cannot fill Brood/Pair slots: a full orbiting pack
    # can wall a generated lane. This fixed Mixed room proves they remain in
    # Shadow Keep's weighted hodgepodge vocabulary and exercises their live AI.
    generated_room(5, 0xB4A60022, probe=probe, local_room=4)
    assert seen, "Bramble Sprite disappeared from Shadow Keep Mixed rooms"
    print("[bramble-sprite] PASS Shadow Keep procgen spawn + distinct art + live told spiral")


if __name__ == "__main__":
    main()
