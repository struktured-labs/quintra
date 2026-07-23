#!/usr/bin/env python3
"""ROM contract: Void Halo is a slow, readable Void Sanctum lane shaper."""

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_VOID_HALO = 31


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def active_halo(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_VOID_HALO):
            return ep
    return None


def main():
    seen = []
    observed_ids = set()

    def probe(pb, _tiles):
        observed_ids.update(
            pb.memory[EN + i * ENTITY_SIZE + 17]
            for i in range(32)
            if (pb.memory[EN + i * ENTITY_SIZE] == ENT_ENEMY
                and pb.memory[EN + i * ENTITY_SIZE + 1] & EF_ACTIVE)
        )
        halo = active_halo(pb)
        if halo is None:
            return
        seen.append(1)

        # Stage eight owns slot 79 in dungeon combat. The real room loader
        # must replace its town/default art before the generated Halo draws.
        actual = bytes(pb.memory[0x8000 + 79 * 16:0x8000 + 80 * 16])
        assert actual == generated_sprite("sprite_enemy_void_halo"), (
            "Void Sanctum did not install Void Halo art in OBJ slot 79")

        # Exercise the generated spinner on an open board. It keeps the
        # authored slow opposite pair—not a copied Midge fan or a ring flood.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if ep != halo:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, halo + 2, 64)
        put_fix8(pb, halo + 6, 64)
        pb.memory[halo + 16] = 2   # one measured spinner movement beat
        pb.memory[halo + 18] = 0   # ai_data[1]: fire this update
        pb.memory[halo + 19] = 0   # ai_data[2]: north/south pair
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 64)
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
        assert len(hostile) == 2, f"Void Halo emitted {len(hostile)} shots: {hostile}"
        assert set(hostile) == {(0, -2), (0, 2)}, (
            f"Void Halo lost its readable opposite lane: {hostile}")

    for seed in range(0x70A10000, 0x70A10040):
        # Void local 2 is the paired phase gate and intentionally has no
        # enemies. Sample ordinary graph cell 4 for this roster contract.
        generated_room(8, seed, probe=probe, local_room=4)
        if seen:
            break
    assert seen, (
        "Void Halo did not appear in 64 fixed Void Sanctum procgen seeds; "
        f"observed stage IDs={sorted(observed_ids)}")
    print("[void-halo] PASS Void procgen spawn + live wide opposite lane")


if __name__ == "__main__":
    main()
