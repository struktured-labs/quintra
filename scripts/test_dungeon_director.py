#!/usr/bin/env python3
"""Live-ROM contract for Quintra's deterministic living-dungeon directives."""

from test_stage_archetypes import EN, PL, TM, addr, generated_room


KIND = addr("_room_encounter_kind")
PHASE = addr("_room_encounter_phase")
TIMER = addr("_room_encounter_timer")
COMPLETE = addr("_room_encounter_complete")
SEALED = addr("_room_combat_sealed")
TARGET = addr("_room_encounter_target")
ROSTER_KIND = addr("_room_roster_kind")
ROSTER_PRIMARY = addr("_room_roster_primary")
ROSTER_SECONDARY = addr("_room_roster_secondary")

ENT_ENEMY, ENT_PICKUP = 2, 3
EF_ACTIVE, EF_ELITE = 0x01, 0x20
PICKUP_BOON_CHOICE = 20
ROOM_W, ROOM_H = 20, 17
WALKABLE = {1, 3, 7, *range(9, 21), 23, 31, 33, 34, 35, 36,
            96, *range(55, 64)}
FULL_BODY_OBSTACLES = {21, 25, 28, 29, 30}


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def enemies(pb):
    return [
        EN + i * 28 for i in range(32)
        if (pb.memory[EN + i * 28] == ENT_ENEMY
            and pb.memory[EN + i * 28 + 1] & EF_ACTIVE)
    ]


def enemy_ids(pb):
    return [pb.memory[ep + 17] for ep in enemies(pb)]


def assert_room_family(pb):
    grammar = pb.memory[ROSTER_KIND]
    if grammar == 0:  # intentional mixed/anything-goes room
        return
    family = {pb.memory[ROSTER_PRIMARY], pb.memory[ROSTER_SECONDARY]}
    observed = set(enemy_ids(pb))
    assert observed <= family, (
        f"director reinforcement broke room family {family}: {observed}"
    )
    if grammar == 1 and observed:
        assert observed == {pb.memory[ROSTER_PRIMARY]}, (
            f"brood reinforcement added a second species: {observed}"
        )


def boon_choices(pb):
    return [
        EN + i * 28 for i in range(32)
        if (pb.memory[EN + i * 28] == ENT_PICKUP
            and pb.memory[EN + i * 28 + 1] & EF_ACTIVE
            and pb.memory[EN + i * 28 + 17] == PICKUP_BOON_CHOICE)
    ]


def assert_boon_reachable(pb, rewards):
    """Model the cartridge's exact feet + full-height-pillar movement."""
    tiles = [pb.memory[TM + i] & 0x7F for i in range(ROOM_W * ROOM_H)]

    def tile_at(x, y):
        if x < 0 or y < 0 or x >= ROOM_W * 8 or y >= ROOM_H * 8:
            return 2
        return tiles[(y >> 3) * ROOM_W + (x >> 3)]

    def body_clear(x, y):
        return (0 <= x <= ROOM_W * 8 - 16
                and 0 <= y <= ROOM_H * 8 - 16
                and all(tile_at(x + dx, y + dy) in WALKABLE
                        for dx in (2, 8, 13) for dy in (8, 15))
                and all(tile_at(x + dx, y + dy) not in FULL_BODY_OBSTACLES
                        for dx in (2, 8, 13) for dy in (0, 7)))

    start = (pb.memory[PL + 9] | pb.memory[PL + 10] << 8,
             pb.memory[PL + 11] | pb.memory[PL + 12] << 8)
    # Wide courts can finish while the hero is in the extension plane. The
    # cartridge projects that position onto the guaranteed-open compact seam
    # before running its compact reward flood; mirror the same anchor here.
    if start[1] + 16 > ROOM_H * 8:
        start = (70, ROOM_H * 8 - 24)
    elif start[0] + 16 > ROOM_W * 8:
        start = (ROOM_W * 8 - 18, ((start[1] + 8) >> 3) * 8 - 8)
    assert body_clear(*start), f"reward-time player position is blocked: {start}"
    seen, pending = {start}, [start]
    while pending:
        x, y = pending.pop()
        for position in ((x - 1, y), (x + 1, y),
                         (x, y - 1), (x, y + 1)):
            if position not in seen and body_clear(*position):
                seen.add(position)
                pending.append(position)

    for reward in rewards:
        x = pb.memory[reward + 3] | pb.memory[reward + 4] << 8
        y = pb.memory[reward + 7] | pb.memory[reward + 8] << 8
        assert any(px + 14 > x and px + 2 < x + 8
                   and py + 16 > y and py + 8 < y + 8
                   for px, py in seen), (
            f"boon at {(x, y)} cannot be reached around full-height scenery"
        )


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
        assert_room_family(pb)
        erase(pb, enemies(pb))
        tick_safe(pb, 4)
        assert pb.memory[SEALED] == 0, "cleared trap did not release doors"
    generated_room(0, seed_for(2), local_room=DIRECTOR_ROOM, probe=probe)


def wave_contract():
    def probe(pb, _tiles):
        assert pb.memory[KIND] == 2 and pb.memory[SEALED] == 1
        first = len(enemies(pb))
        assert first >= 2
        assert_room_family(pb)
        erase(pb, enemies(pb))
        tick_safe(pb, 4)
        second = len(enemies(pb))
        assert pb.memory[PHASE] == 1 and second >= 3, \
            "first clear did not create a second formation"
        assert_room_family(pb)
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
        # A dense room can span several host emulator frames before its
        # cartridge frame reaches the post-director door transaction.
        for _ in range(60):
            tick_safe(pb, 1)
            if pb.memory[SEALED] == 0:
                break
        rewards = boon_choices(pb)
        assert pb.memory[SEALED] == 0 and len(rewards) == 2, \
            "elite kill did not release the room with a two-way build choice"
        assert_boon_reachable(pb, rewards)
        # The pair owns a 30-game-update anti-auto-pickup grace period. Dense
        # rooms can advance fewer cartridge updates than host VBlanks, so
        # observe the actual entity state instead of assuming 32 host ticks.
        for _ in range(120):
            tick_safe(pb, 1)
            if all(pb.memory[ep + 15] == 0 for ep in rewards):
                break
        assert all(pb.memory[ep + 15] == 0 for ep in rewards), \
            "boon choice grace did not expire"
        chosen = rewards[0]
        put16(pb, PL + 9, (pb.memory[chosen + 3] - 2) & 0xFF)
        put16(pb, PL + 11, (pb.memory[chosen + 7] - 9) & 0xFF)
        for _ in range(60):
            tick_safe(pb, 1)
            if not boon_choices(pb):
                break
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
        assert_room_family(pb)
        now = pb.memory[TIMER] | (pb.memory[TIMER + 1] << 8)
        assert now < start_timer
        # Fast-forward only the clock; release/reward still travels through
        # the cartridge's real per-frame director and room-door path.
        for _ in range(120):
            # A cartridge frame can span several host VBlanks under maximum
            # density. Hold the requested clock value until the director
            # reaches and consumes that frame boundary.
            if pb.memory[PHASE] != 2:
                pb.memory[TIMER] = 1
                pb.memory[TIMER + 1] = 0
            tick_safe(pb, 1)
            if pb.memory[SEALED] == 0:
                break
        assert pb.memory[SEALED] == 0 and len(boon_choices(pb)) == 2, \
            f"survival completion did not release a boon choice: " \
            f"sealed={pb.memory[SEALED]} phase={pb.memory[PHASE]} " \
            f"complete={pb.memory[COMPLETE]} timer=" \
            f"{pb.memory[TIMER] | pb.memory[TIMER + 1] << 8} " \
            f"rewards={len(boon_choices(pb))}"
        assert_boon_reachable(pb, boon_choices(pb))
    generated_room(0, seed_for(6), local_room=DIRECTOR_ROOM, probe=probe)


def main():
    trap_contract()
    wave_contract()
    elite_contract()
    hold_contract()
    print("[dungeon-director] PASS themed trap/wave/hold reinforcements + elite target/choice")


if __name__ == "__main__":
    main()
