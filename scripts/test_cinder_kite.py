#!/usr/bin/env python3
"""ROM contract: Ember's Cinder Kite is a live procedural harrier."""

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_CINDER_KITE = 25
SPR_CINDER_KITE = 79


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def active_kite(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_CINDER_KITE):
            return ep
    return None


def main():
    seen = []

    def probe(pb, _tiles):
        kite = active_kite(pb)
        if kite is None:
            return
        seen.append(1)

        # Ember must replace the phase-safe apothecary slot with the Kite,
        # not accidentally retain the later Midge or Temple Sunwheel art.
        actual = bytes(pb.memory[0x8000 + SPR_CINDER_KITE * 16:
                                 0x8000 + (SPR_CINDER_KITE + 1) * 16])
        expected = generated_sprite("sprite_enemy_cinder_kite")
        assert actual == expected, "Ember Depths did not install Cinder Kite OBJ art"
        assert actual != generated_sprite("sprite_enemy_cinder_maw"), \
            "Cinder Kite reused the rooted Cinder Maw silhouette"
        assert actual != generated_sprite("sprite_enemy_dusk_midge"), \
            "Cinder Kite reused the later Dusk Midge silhouette"

        # Exercise the real generated entity on an open board. Its fast body
        # drifts east every four ticks and its three normal-speed fan leaves
        # a readable center lane rather than Cinder Maw's fast bullet flood.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if ep != kite:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, kite + 2, 64)
        put_fix8(pb, kite + 6, 64)
        pb.memory[kite + 15] = 2  # state: east
        pb.memory[kite + 16] = 0  # body divider: move this update
        pb.memory[kite + 18] = 0  # Shooter ai_data[1]: fire this update
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
        assert len(hostile) == 3 and len(set(hostile)) == 3, (
            f"Cinder Kite fan lost its three readable lanes: {hostile}")
        assert max(max(abs(vx), abs(vy)) for vx, vy in hostile) == 2, (
            f"Cinder Kite bullets are not normal-speed lane prompts: {hostile}")

        for _ in range(7):
            pb.tick()
        assert pb.memory[kite + 3] == 66, (
            f"Cinder Kite lost its authored fast drift: x={pb.memory[kite + 3]}")

    # Fixed seeds retain reproducibility while allowing its 12% pool weight
    # to demonstrate that this is reachable procedural content, not dead data.
    for seed in range(0xC1DE0000, 0xC1DE0010):
        # Local 2 is Ember's deliberately hostile-free phase gate. Sample
        # ordinary graph cell 4 for the procedural harrier contract.
        generated_room(2, seed, probe=probe, local_room=4)
        if seen:
            break
    assert seen, "Cinder Kite did not appear in 16 fixed Ember procgen seeds"
    print("[cinder-kite] PASS Ember procgen spawn + distinct art + readable three-lane fan")


if __name__ == "__main__":
    main()
