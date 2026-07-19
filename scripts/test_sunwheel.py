#!/usr/bin/env python3
"""ROM contract: Sunwheel is a readable Golden Temple lane-shaper."""

from test_enemy_identity import generated_sprite
from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_SUNWHEEL = 24


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def active_sunwheel(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_SUNWHEEL):
            return ep
    return None


def main():
    seen = []

    def probe(pb, _tiles):
        wheel = active_sunwheel(pb)
        if wheel is None:
            return
        seen.append(1)

        # Golden Temple must install Sunwheel art into the phase-safe slot 79
        # before anything is drawn. This catches a loader regression where
        # the correct typed enemy could spawn with the late-game Midge art.
        actual = bytes(pb.memory[0x8000 + 79 * 16:0x8000 + 80 * 16])
        assert actual == generated_sprite("sprite_enemy_sunwheel"), (
            "Golden Temple did not install Sunwheel art in OBJ slot 79")

        # Exercise the live, generated entity on a clear board. Spinner fires
        # exactly an opposite pair, making a readable lane rather than a ring.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if ep != wheel:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, wheel + 2, 64)
        put_fix8(pb, wheel + 6, 64)
        pb.memory[wheel + 16] = 2  # body divider: take one measured orbit step
        pb.memory[wheel + 18] = 0  # Spinner ai_data[1]: fire now
        pb.memory[wheel + 19] = 0  # Spinner ai_data[2]: north/south pair
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
        assert len(hostile) == 2, f"Sunwheel emitted {len(hostile)} shots: {hostile}"
        assert set(hostile) == {(0, -2), (0, 2)}, (
            f"Sunwheel lost its opposite lane contract: {hostile}")

    for seed in range(0x5A710000, 0x5A710010):
        generated_room(6, seed, probe=probe)
        if seen:
            break
    assert seen, "Sunwheel did not appear in 16 fixed Golden Temple procgen seeds"
    print("[sunwheel] PASS Golden Temple procgen spawn + live opposite lane")


if __name__ == "__main__":
    main()
