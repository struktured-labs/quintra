#!/usr/bin/env python3
"""ROM contract: Void Halo is a slow, readable Void Sanctum lane shaper."""

from test_enemy_identity import generated_sprite
from spinner_contract import assert_told_spiral
from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_VOID_HALO = 31


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

        # Exercise the live generated entity on a clear board: one told
        # spiral, a shot per compass point (spinner contract since #3).
        assert_told_spiral(pb, halo, EN, PL, TM, "Void Halo")

    for seed in range(0x70A10000, 0x70A10040):
        # Void local 2 is the paired phase gate and intentionally has no
        # enemies. Sample ordinary graph cell 4 for this roster contract.
        generated_room(8, seed, probe=probe, local_room=4)
        if seen:
            break
    assert seen, (
        "Void Halo did not appear in 64 fixed Void Sanctum procgen seeds; "
        f"observed stage IDs={sorted(observed_ids)}")
    print("[void-halo] PASS Void procgen spawn + live told spiral")


if __name__ == "__main__":
    main()
