#!/usr/bin/env python3
"""ROM contract: Crystal's Shard Crab has a live shell-counter lesson."""

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_ALIVE, EF_PLAYER_PROJ = 0x01, 0x02, 0x10
ENEMY_SHARD_CRAB = 30
SPR_SHARD_CRAB = 79


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def active_crab(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_SHARD_CRAB):
            return ep
    return None


def player_shot(pb, ep, x, y):
    pb.memory[ep] = ENT_PROJECTILE
    pb.memory[ep + 1] = EF_ACTIVE | EF_ALIVE | EF_PLAYER_PROJ
    put_fix8(pb, ep + 2, x)
    put_fix8(pb, ep + 6, y)
    pb.memory[ep + 14] = 1       # one collision then spent
    pb.memory[ep + 16] = 60
    pb.memory[ep + 25] = 0x88
    pb.memory[ep + 26] = 4


def main():
    seen = []

    def probe(pb, _tiles):
        crab = active_crab(pb)
        if crab is None:
            return
        seen.append(1)

        actual = bytes(pb.memory[0x8000 + SPR_SHARD_CRAB * 16:
                                 0x8000 + (SPR_SHARD_CRAB + 1) * 16])
        assert actual == generated_sprite("sprite_enemy_shard_crab"), \
            "Crystal Caverns did not install Shard Crab shell art"
        assert actual != generated_sprite("sprite_enemy_vine_coil"), \
            "Shard Crab reused Verdant Hollow's Vine Coil silhouette"

        # Isolate the authored AI in an unobstructed live room. The first
        # overlapping player hit must be deflected, triggering the short
        # scuttle; after that the opened shell must accept normal damage.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        # Finish any nested generation VBlank before publishing a disposable
        # live Crab. Reusing the generated entity lets its in-flight ordinary
        # update overwrite this exact shell-state fixture.
        for _ in range(8):
            pb.tick()
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        crab = EN
        pb.memory[crab] = ENT_ENEMY
        pb.memory[crab + 1] = EF_ACTIVE | EF_ALIVE
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 64)
        put_fix8(pb, crab + 2, 64)
        put_fix8(pb, crab + 6, 64)
        pb.memory[crab + 12] = SPR_SHARD_CRAB
        pb.memory[crab + 13] = 6
        pb.memory[crab + 14] = 9
        pb.memory[crab + 15] = 0
        pb.memory[crab + 16] = 0
        pb.memory[crab + 17] = ENEMY_SHARD_CRAB
        pb.memory[crab + 25] = 0x66
        pb.memory[crab + 27] = 2
        player_shot(pb, EN + ENTITY_SIZE, 64, 64)
        for _ in range(4):
            pb.tick()
            if not (pb.memory[EN + ENTITY_SIZE + 1] & EF_ACTIVE):
                break
        assert pb.memory[crab + 14] == 9, "Shard Crab's ready shell took first-hit damage"
        assert pb.memory[crab + 15] == 1, "Shard Crab did not enter its counter-rush"
        assert not (pb.memory[EN + ENTITY_SIZE + 1] & EF_ACTIVE), \
            "Shard Crab did not consume the deflected hit"

        for _ in range(24):
            pb.tick()
        assert pb.memory[crab + 15] == 2 and pb.memory[crab + 13] == 0, \
            "Shard Crab did not open a pale punish window after rushing"
        # It may drift during its opening, but that must not overwrite the
        # shell state (the generic chaser stores its wall-slide direction in
        # state, which used to erase this value).
        for _ in range(16):
            pb.tick()
        assert pb.memory[crab + 15] == 2 and pb.memory[crab + 14] == 9, \
            "Shard Crab movement erased its exposed counter state"
        player_shot(pb, EN + ENTITY_SIZE, pb.memory[crab + 3], pb.memory[crab + 7])
        pb.tick()
        assert pb.memory[crab + 14] < 9, "opened Shard Crab still deflected a follow-up hit"

    # Six percent of Crystal's replacement-weight pool yields a visible Crab
    # across this fixed 16-seed sweep without affecting its body count.
    for seed in range(0x5C4B0000, 0x5C4B0010):
        generated_room(0, seed, probe=probe)
        if seen:
            break
    assert seen, "Shard Crab did not appear in 16 fixed Crystal Caverns procgen seeds"
    print("[shard-crab] PASS Crystal spawn + shell art + counter/punish loop")


if __name__ == "__main__":
    main()
