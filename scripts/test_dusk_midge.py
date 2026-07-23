#!/usr/bin/env python3
"""ROM contract: the Dusk Midge is a real late-stage procgen harrier."""

from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_DUSK_MIDGE = 23


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def active_midge(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_DUSK_MIDGE):
            return ep
    return None


def main():
    # Bloodmoon is the first legal Midge stage. Search a compact fixed seed
    # set through the real Riftwild gate; this proves a 7% weighted entry is
    # not merely present in generated content while unreachable at runtime.
    seen = []

    def probe(pb, _tiles):
        midge = active_midge(pb)
        if midge is None:
            return
        seen.append(1)

        # The spawn was procedural. Now clear unrelated room noise and place
        # the discovered live entity on an open lane so one normal AI update
        # can prove its authored fan rather than a static table value.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if ep != midge:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, midge + 2, 64)
        put_fix8(pb, midge + 6, 64)
        pb.memory[midge + 15] = 2  # state: east; dir8[2] is +X.
        # Start just before a harrier beat. This avoids conflating the first
        # post-room-update frame with the cadence itself: an 80-speed Midge
        # must step twice in eight updates, while an eight-tick caster gets
        # only one step in that same measured lane.
        pb.memory[midge + 16] = 3
        pb.memory[midge + 18] = 0  # Shooter ai_data[1]: fire this update.
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
        assert len(hostile) == 3, f"Dusk Midge fan emitted {len(hostile)} shots: {hostile}"
        assert len(set(hostile)) == 3, f"Dusk Midge fan lost its three lanes: {hostile}"

        # The Midge's authored 80 speed must affect the shared Shooter AI,
        # rather than merely looking "fast" in generated content. Eight
        # ticks span two four-tick harrier beats; legacy casters retain only
        # one eight-tick body beat in that same lane.
        positions = [pb.memory[midge + 3]]
        for _ in range(7):
            pb.tick()
            positions.append(pb.memory[midge + 3])
        assert pb.memory[midge + 3] == 66, (
            f"Dusk Midge ignored its fast drift cadence: x={pb.memory[midge + 3]}, "
            f"positions={positions}, timer={pb.memory[midge + 16]}, state={pb.memory[midge + 15]}"
        )

    for seed in (
        0xD05C0000, 0xD05C0001, 0xD05C0002, 0xD05C0003,
        0xD05C0004, 0xD05C0005, 0xD05C0006, 0xD05C0007,
        0xD05C0008, 0xD05C0009, 0xD05C000A, 0xD05C000B,
    ):
        generated_room(7, seed, probe=probe)
        if seen:
            break
    assert seen, "Dusk Midge did not appear in 12 fixed Bloodmoon procgen seeds"
    print("[dusk-midge] PASS Bloodmoon procgen spawn + live three-lane fan")


if __name__ == "__main__":
    main()
