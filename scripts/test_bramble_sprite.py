#!/usr/bin/env python3
"""ROM contract: Shadow Keep's Bramble Sprite is a live, distinct lane prompt."""

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, PL, TM, addr, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_BRAMBLE_SPRITE = 27
SPR_BRAMBLE_SPRITE = 79
ROSTER_KIND = addr("_room_roster_kind")
ROOM_ROSTER_MIXED = 0


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


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

        # The live Spinner driver emits two opposite normal-speed shots. Its
        # 132-frame cadence is long enough to teach the lane without turning
        # the early grove into a bullet flood.
        fixture = bytes(pb.memory[bramble:bramble + ENTITY_SIZE])
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            pb.memory[ep] = pb.memory[ep + 1] = 0
        # A direct fixture can land while the generated room still has an old
        # entity pointer cached in its current update. Retire that frame, clear
        # any replacements, and republish the observed procgen Bramble before
        # testing its authored volley.
        pb.tick(4)
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            pb.memory[ep] = pb.memory[ep + 1] = 0
        for offset, value in enumerate(fixture):
            pb.memory[bramble + offset] = value
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, bramble + 2, 64)
        put_fix8(pb, bramble + 6, 64)
        pb.memory[bramble + 1] |= 4
        pb.memory[bramble + 16] = 2
        pb.memory[bramble + 18] = 0
        pb.memory[bramble + 19] = 0
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 64)
        hostile = []
        for _ in range(4):
            pb.tick()
            hostile = []
            for i in range(32):
                ep = EN + i * ENTITY_SIZE
                flags = pb.memory[ep + 1]
                if (pb.memory[ep] == ENT_PROJECTILE and flags & EF_ACTIVE
                        and not flags & EF_PLAYER_PROJ):
                    vx, vy = pb.memory[ep + 10], pb.memory[ep + 11]
                    hostile.append((vx - 256 if vx >= 128 else vx,
                                    vy - 256 if vy >= 128 else vy))
            if len(hostile) >= 2:
                break
        assert set(hostile) == {(0, -2), (0, 2)}, (
            f"Bramble Sprite lost its readable opposite lane: {hostile}")

    # Brambles deliberately cannot fill Brood/Pair slots: a full orbiting pack
    # can wall a generated lane. This fixed Mixed room proves they remain in
    # Shadow Keep's weighted hodgepodge vocabulary and exercises their live AI.
    generated_room(5, 0xB4A60022, probe=probe, local_room=4)
    assert seen, "Bramble Sprite disappeared from Shadow Keep Mixed rooms"
    print("[bramble-sprite] PASS Shadow Keep procgen spawn + distinct art + live lane")


if __name__ == "__main__":
    main()
