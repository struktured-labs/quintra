#!/usr/bin/env python3
"""Live-ROM contract for Quintra's deterministic living-dungeon directives."""

from test_stage_archetypes import EN, PL, addr, generated_room


KIND = addr("_room_encounter_kind")
PHASE = addr("_room_encounter_phase")
TIMER = addr("_room_encounter_timer")
COMPLETE = addr("_room_encounter_complete")
SEALED = addr("_room_combat_sealed")
TARGET = addr("_room_encounter_target")

ENT_ENEMY, ENT_PICKUP = 2, 3
EF_ACTIVE, EF_ELITE = 0x01, 0x20
PICKUP_BOON_CHOICE = 20


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def enemies(pb):
    return [
        EN + i * 28 for i in range(32)
        if (pb.memory[EN + i * 28] == ENT_ENEMY
            and pb.memory[EN + i * 28 + 1] & EF_ACTIVE)
    ]


def boon_choices(pb):
    return [
        EN + i * 28 for i in range(32)
        if (pb.memory[EN + i * 28] == ENT_PICKUP
            and pb.memory[EN + i * 28 + 1] & EF_ACTIVE
            and pb.memory[EN + i * 28 + 17] == PICKUP_BOON_CHOICE)
    ]


def erase(pb, entities):
    for ep in entities:
        pb.memory[ep] = 0
        pb.memory[ep + 1] = 0


def tick_safe(pb, frames):
    for _ in range(frames):
        pb.memory[PL + 2] = 14
        pb.memory[PL + 15] = 60
        pb.tick()


DIRECTOR_ROOM = 8


def seed_for(signature):
    # Stage zero, ordinary local room eight:
    # (seed_low + room + stage*3) & 7. Mission roles are seed-dependent now,
    # so avoid local four, which can correctly become the Deep Warden room.
    return 0xD1CE0000 | ((signature - DIRECTOR_ROOM) & 7)


def trap_contract():
    def probe(pb, _tiles):
        assert pb.memory[KIND] == 1 and pb.memory[SEALED] == 1
        # The empty hush is deliberate; the warning clock then materializes
        # a real pack without another doorway transaction.
        for _ in range(80):
            tick_safe(pb, 1)
            if pb.memory[PHASE] == 1:
                break
        assert pb.memory[PHASE] == 1 and len(enemies(pb)) >= 4, \
            "trap did not spring a Normal-mode ambush"
        erase(pb, enemies(pb))
        tick_safe(pb, 4)
        assert pb.memory[SEALED] == 0, "cleared trap did not release doors"
    generated_room(0, seed_for(2), local_room=DIRECTOR_ROOM, probe=probe)


def wave_contract():
    def probe(pb, _tiles):
        assert pb.memory[KIND] == 2 and pb.memory[SEALED] == 1
        first = len(enemies(pb))
        assert first >= 2
        erase(pb, enemies(pb))
        tick_safe(pb, 4)
        second = len(enemies(pb))
        assert pb.memory[PHASE] == 1 and second >= 3, \
            "first clear did not create a second formation"
        erase(pb, enemies(pb))
        tick_safe(pb, 4)
        assert pb.memory[SEALED] == 0, "second wave did not release doors"
    generated_room(0, seed_for(3), local_room=DIRECTOR_ROOM, probe=probe)


def elite_contract():
    def probe(pb, _tiles):
        assert pb.memory[KIND] == 3 and pb.memory[SEALED] == 1
        index = pb.memory[TARGET]
        target = EN + index * 28
        assert index < 32 and target in enemies(pb), \
            "elite directive lacks one persistent target handle"
        assert pb.memory[target + 1] & EF_ELITE and pb.memory[target + 13] == 6
        erase(pb, [target])
        tick_safe(pb, 4)
        rewards = boon_choices(pb)
        assert pb.memory[SEALED] == 0 and len(rewards) == 2, \
            "elite kill did not offer a two-way build choice"
        chosen = rewards[0]
        put16(pb, PL + 9, (pb.memory[chosen + 3] - 2) & 0xFF)
        put16(pb, PL + 11, (pb.memory[chosen + 7] - 9) & 0xFF)
        tick_safe(pb, 8)
        assert not boon_choices(pb), "taking one boon did not retire its sibling"
    generated_room(0, seed_for(5), local_room=DIRECTOR_ROOM, probe=probe)


def hold_contract():
    def probe(pb, _tiles):
        assert pb.memory[KIND] == 4 and pb.memory[SEALED] == 1
        initial = len(enemies(pb))
        assert 1 <= initial <= 4
        start_timer = pb.memory[TIMER] | (pb.memory[TIMER + 1] << 8)
        tick_safe(pb, 130)
        assert len(enemies(pb)) > initial, "hold room did not reinforce pressure"
        now = pb.memory[TIMER] | (pb.memory[TIMER + 1] << 8)
        assert now < start_timer
        # Fast-forward only the clock; release/reward still travels through
        # the cartridge's real per-frame director and room-door path.
        pb.memory[TIMER] = 2
        pb.memory[TIMER + 1] = 0
        tick_safe(pb, 5)
        assert pb.memory[SEALED] == 0 and len(boon_choices(pb)) == 2, \
            "survival completion did not release a boon choice"
    generated_room(0, seed_for(6), local_room=DIRECTOR_ROOM, probe=probe)


def main():
    trap_contract()
    wave_contract()
    elite_contract()
    hold_contract()
    print("[dungeon-director] PASS trap + wave + elite target/choice + hold reinforcements")


if __name__ == "__main__":
    main()
