#!/usr/bin/env python3
"""Live-ROM contract for the one-wave Rift Cantor reinforcement caller."""

from test_stage_archetypes import EN, PL, RS, TM, generated_room, put16


ENTITY_SIZE = 28
ENT_ENEMY = 2
ENEMY_RIFT_CANTOR = 32


def active_enemies(pb):
    return [
        EN + i * ENTITY_SIZE for i in range(32)
        if pb.memory[EN + i * ENTITY_SIZE] == ENT_ENEMY
        and pb.memory[EN + i * ENTITY_SIZE + 1] & 1
    ]


def clear_entities(pb):
    for i in range(32):
        e = EN + i * ENTITY_SIZE
        pb.memory[e] = 0
        pb.memory[e + 1] = 0


def install_cantor(pb):
    clear_entities(pb)
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 64)
    e = EN
    pb.memory[e] = ENT_ENEMY
    # Generated courts simulate only the active camera sector. This injected
    # body is deliberately on-screen, so publish the same visibility flag the
    # real spawner/sector pass would own.
    pb.memory[e + 1] = 7  # active + alive + on-screen
    put16(pb, e + 3, 72)
    put16(pb, e + 7, 104)
    pb.memory[e + 12] = 70
    pb.memory[e + 13] = 6
    pb.memory[e + 14] = 13
    pb.memory[e + 15] = 0
    pb.memory[e + 16] = 30
    pb.memory[e + 17] = ENEMY_RIFT_CANTOR
    for offset in range(18, 25):
        pb.memory[e + offset] = 0
    pb.memory[e + 25] = 0x66
    pb.memory[e + 26] = 1
    pb.memory[e + 27] = 4


def assert_cantor_art_loaded(pb):
    expected = bytes((
        0x99, 0x99, 0x42, 0x5A, 0x24, 0x3C, 0x5A, 0x66,
        0xBD, 0xDB, 0x5A, 0x3C, 0x3C, 0x24, 0x5A, 0x42,
    ))
    pb.memory[0xFF4F] = 0
    start = 0x8000 + 70 * 16
    actual = bytes(pb.memory[start + i] for i in range(16))
    assert actual == expected, (
        f"combat room retained merchant art in Cantor slot: {actual.hex()}"
    )


def assert_normal_wave(pb, _tiles):
    assert_cantor_art_loaded(pb)
    install_cantor(pb)
    # Detection starts the interruptible 48-frame chant. No escort may
    # materialize during its readable warning window.
    for _ in range(24):
        pb.tick()
    assert pb.memory[EN + 19] == 1, "Cantor did not enter its chant state"
    assert len(active_enemies(pb)) == 1, "escort appeared before chant resolved"

    for _ in range(40):
        pb.tick()
    wave = active_enemies(pb)
    ids = [pb.memory[e + 17] for e in wave]
    assert len(wave) == 3, f"Normal Cantor wave was not bounded at two: {ids}"
    assert ids.count(ENEMY_RIFT_CANTOR) == 1, \
        f"Cantor recursively summoned itself: {ids}"
    assert pb.memory[EN + 19] == 2, "Cantor did not mark its wave spent"

    # It may evade after the call, but it must never return to the summoning
    # state or grow the enemy population again.
    for _ in range(150):
        pb.tick()
    assert len(active_enemies(pb)) == 3, "Cantor produced a second wave"
    assert pb.memory[EN + 19] == 2, "Cantor re-armed after its one wave"


def assert_easy_wave(pb, _tiles):
    assert_cantor_art_loaded(pb)
    install_cantor(pb)
    pb.memory[RS + 26] = 1  # DIFFICULTY_EASY
    for _ in range(64):
        pb.tick()
    wave = active_enemies(pb)
    ids = [pb.memory[e + 17] for e in wave]
    assert len(wave) == 2, f"Easy Cantor did not reduce to one escort: {ids}"
    assert ids.count(ENEMY_RIFT_CANTOR) == 1


def assert_spent_caller_leaves_outer_band(pb, _tiles):
    install_cantor(pb)
    # Reproduce the final-stage softlock in the visible northwest equivalent
    # of its captured southeast pocket. A spent caller at (8,8) sees the
    # champion southeast, so its ordinary away vector points into the two
    # world bounds. Keep the local apron honest floor and prove that the live
    # cartridge chooses the inward vector instead of retrying the corner.
    for ty in range(6):
        for tx in range(6):
            pb.memory[TM + ty * 20 + tx] = 1
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 64)
    put16(pb, EN + 3, 8)
    put16(pb, EN + 7, 8)
    pb.memory[EN + 19] = 2  # wave spent
    pb.memory[EN + 21] = 0  # movement divider
    for _ in range(96):
        pb.tick()
    x = pb.memory[EN + 3] | (pb.memory[EN + 4] << 8)
    y = pb.memory[EN + 7] | (pb.memory[EN + 8] << 8)
    assert x > 8 or y > 8, \
        f"spent Cantor retried its blocked outer corner forever: ({x},{y})"


def main():
    # Stage index three is the first pool that can roll a Cantor. Injecting
    # the typed ID into a real generated court isolates AI behavior from the
    # 6% roster roll while retaining the actual cartridge dispatcher,
    # collision map, entity budget, SFX, and difficulty state.
    generated_room(3, seed=0xCA110012, probe=assert_normal_wave)
    generated_room(3, seed=0xCA110013, probe=assert_easy_wave)
    generated_room(8, seed=0xCA110014,
                   probe=assert_spent_caller_leaves_outer_band)
    print("[reinforcement-caller] PASS 48f interruptible tell, two escorts on "
          "Normal / one on Easy, no recursion, no second wave, outer-band "
          "escape")


if __name__ == "__main__":
    main()
