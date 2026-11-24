#!/usr/bin/env python3
"""ROM contract: every active Riftwild guard field has a reachable Warden.

Issues #242 and #245: compact-plane reachability can leave the regional
guard field without a Sentinel/Bellwarden. The kill hook then never sets
the guard bit, and the next arch stays asleep. Guarantee the body after
population, and still set the bit if the field empties without that kill.
"""

from pyboy import PyBoy

from quintra_topology import STAGE_BOSS_ROOM
from quintra_vignettes import mute_after_class_select, mute_vignettes
from test_miniboss_spawn_reach import (
    ENEMY_AUX_BELLWARDEN, ENEMY_DREAD_BELL, ENEMY_STONE_SENTINEL,
    active_enemies, world_tiles,
)
from test_riftwild_landmarks import WALKABLE, cross_to
from test_overworld import (
    CAMERA_X, CAMERA_Y, EN, LARGE, PL, ROM, RS, TM, WORLD_H, WORLD_W, exit_at,
)
from test_regional_riftwild import FLAGS, GUARD_1, GUARD_2, GUARD_3


CHAMPIONS = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
ROOM_W = 20
BGT_DOOR = 3
ENTITY_SIZE = 28
EF_ACTIVE = 0x01
ENT_PICKUP = 3
# #242: Easy Corvin, title wait 2, seed recorded by the machine player.
REPRO_242_SEED = 0x7B081A4A
# Sweep is wide enough to catch seed- and class-dependent flood failures
# without turning CI into a long geography walk.
SWEEP_SEEDS = tuple(0x51A70000 + i for i in range(8)) + (REPRO_242_SEED,)

def body_ok(tiles, width, height, x, y):
    return (1 <= x < width - 1 and 1 <= y < height - 1
            and all(tiles[ty * width + tx] in WALKABLE
                    for tx, ty in ((x, y), (x + 1, y),
                                   (x, y + 1), (x + 1, y + 1))))


def reachable(tiles, width, height, start):
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if ((nx, ny) not in seen
                    and body_ok(tiles, width, height, nx, ny)):
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen




def title_boot(class_id, difficulty):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    for _ in range(class_id):
        pb.button("down")
        for _ in range(8):
            pb.tick()
    if difficulty == "easy":
        pb.button("select")
        for _ in range(8):
            pb.tick()
    pb.button_press("a")
    for _ in range(6):
        pb.tick()
    pb.button_release("a")
    mute_after_class_select(pb, ROM, settle=90)
    mute_vignettes(pb, ROM)
    return pb


def set_seed(pb, seed):
    for i, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + i] = byte


def return_after_boss(pb, number):
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[number - 1]
    pb.memory[RS + 11] = number
    pb.memory[RS + 17] = 0
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    pb.memory[TM + 16 * ROOM_W + 9] = BGT_DOOR
    pb.memory[TM + 16 * ROOM_W + 10] = BGT_DOOR
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 17] == 1, "did not enter Riftwild after the boss exit"


def walk_east_to(pb, target):
    """Walk the first-row trail (0 -> 1 -> 2 -> 3 and similar east hops)."""
    while pb.memory[RS + 18] != target:
        before = pb.memory[RS + 18]
        cross_to(pb, before + 1, 232, 60)
        after = pb.memory[RS + 18]
        assert after == before + 1, (
            f"east hop from {before} landed on {after}; wanted {target}")
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == target


def walk_path(pb, hops, target):
    # hops: (next_screen, mouth_x, mouth_y)
    for nxt, x, y in hops:
        before = pb.memory[RS + 18]
        cross_to(pb, nxt, x, y)
        after = pb.memory[RS + 18]
        assert after == nxt, f"hop from {before} via ({x},{y}) landed on {after}, wanted {nxt}"
    assert pb.memory[RS + 18] == target, (
        f"path landed on {pb.memory[RS + 18]}, expected {target}")


def expected_for_stage(bosses_beaten):
    if bosses_beaten >= 6:
        return {"id": ENEMY_DREAD_BELL, "name": "Bellwarden",
                "ai2": ENEMY_AUX_BELLWARDEN, "hp": 20}
    return {"id": ENEMY_STONE_SENTINEL, "name": "Sentinel",
            "ai2": None, "hp": 50}


def specialists(pb, expected):
    found = []
    for enemy in active_enemies(pb):
        if enemy["id"] != expected["id"]:
            continue
        if expected.get("ai2") is not None and enemy["ai2"] != expected["ai2"]:
            continue
        if enemy["hp"] < expected["hp"]:
            continue
        found.append(enemy)
    return found


def assert_reachable_warden(pb, expected, where):
    tiles, width, height = world_tiles(pb, list(pb.memory[TM:TM + ROOM_W * 17]))
    found = specialists(pb, expected)
    assert len(found) == 1, (
        f"{where}: expected one required {expected['name']}, "
        f"got {len(found)} enemies="
        f"{[(e['id'], e['hp'], e['ai2'], e['x'], e['y']) for e in active_enemies(pb)]}"
        f" flags=0x{pb.memory[RS + FLAGS]:02X} screen={pb.memory[RS + 18]}"
        f" bosses={pb.memory[RS + 11]}")
    body = found[0]
    sx = (body["x"] + 4) // 8
    sy = (body["y"] + 4) // 8
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    start = ((px + 2) // 8, (py + 8) // 8)
    assert body_ok(tiles, width, height, sx, sy), (
        f"{where}: {expected['name']} overlaps solid tile at {(sx, sy)}")
    assert (sx, sy) in reachable(tiles, width, height, start), (
        f"{where}: {expected['name']} at {(sx, sy)} is outside the player "
        f"component from {start}")
    return body


def enter_guard_field(pb, seed, bosses_beaten, guard_screen, hops=None):
    set_seed(pb, seed)
    # Force a fresh region so each seed actually rebuilds geography.
    pb.memory[RS + FLAGS] = 0
    return_after_boss(pb, bosses_beaten)
    if hops:
        walk_path(pb, hops, guard_screen)
    else:
        walk_east_to(pb, guard_screen)
    # Drop entry iframes so later ticks of the clear-net path are ordinary play.
    pb.memory[PL + 15] = 0


def pedestal_pickup_present(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == ENT_PICKUP and pb.memory[ep + 1] & EF_ACTIVE:
            if pb.memory[ep + 3] == 120 and pb.memory[ep + 7] == 72:
                return True
    return False


def assert_clear_net(pb, guard_bit, where):
    assert not (pb.memory[RS + FLAGS] & guard_bit), (
        f"{where}: guard bit already set before the clear-room net "
        f"(flags=0x{pb.memory[RS + FLAGS]:02X})")
    for enemy in active_enemies(pb):
        pb.memory[enemy["ep"] + 1] &= ~EF_ACTIVE
    for _ in range(180):
        pb.tick()
        if pb.memory[RS + FLAGS] & guard_bit:
            # Pedestal restore is part of the same last-net: the implement
            # must appear at the cleared trail marker, not require a re-entry.
            assert pedestal_pickup_present(pb), (
                f"{where}: guard bit set but the waygear pedestal stayed empty")
            return
    raise AssertionError(
        f"{where}: guard field cleared without a Warden kill, but "
        f"riftwild_flags stayed 0x{pb.memory[RS + FLAGS]:02X}")


def main():
    checked = 0

    # Exact #242 repro, then its clear-room net, on a fresh-boot path.
    # Mid-frame player states can hang on a rebuilt ROM.
    pb = title_boot(CHAMPIONS.index("corvin"), "easy")
    try:
        enter_guard_field(pb, REPRO_242_SEED, 4, 3)
        assert_reachable_warden(
            pb, expected_for_stage(4), "#242 Easy Corvin seed 0x7B081A4A field 3")
        assert_clear_net(pb, GUARD_1, "#242 clear-room net")
        checked += 1
        print("[riftwild-guard-spawn] #242 Easy Corvin repro + clear-room net PASS")
    finally:
        pb.stop(save=False)

    # All five heroes, both difficulties, eight seeds plus the #242 seed,
    # on the region-1 first guard field (the #245 situation: bosses_beaten=4).
    for class_id, name in enumerate(CHAMPIONS):
        for difficulty in ("normal", "easy"):
            pb = title_boot(class_id, difficulty)
            try:
                for seed in SWEEP_SEEDS:
                    enter_guard_field(pb, seed, 4, 3)
                    assert_reachable_warden(
                        pb, expected_for_stage(4),
                        f"{difficulty} {name} seed={seed:#x} field 3")
                    checked += 1
            finally:
                pb.stop(save=False)
    print("[riftwild-guard-spawn] PASS "
          f"{len(CHAMPIONS)} heroes x 2 difficulties x {len(SWEEP_SEEDS)} "
          "seeds on field 3 (bosses_beaten=4)")

    pb = title_boot(CHAMPIONS.index("sauran"), "normal")
    try:
        # Screen 17: after boss 5, return screen is 8. Path: 8 south->14,
        # 14 east->15, 15 east->16, 16 east->17.
        enter_guard_field(pb, 0x51A70001, 5, 17,
                          hops=[(14, 72, 232), (15, 232, 60), (16, 232, 60), (17, 232, 60)])
        assert_reachable_warden(
            pb, expected_for_stage(5), "Normal Sauran field 17")
        assert_clear_net(pb, GUARD_2, "field 17 clear-room net")
        checked += 1

        # Screen 3 Bellwarden after boss 7 (region 2, step 0).
        enter_guard_field(pb, 0x51A70002, 7, 3)
        assert_reachable_warden(
            pb, expected_for_stage(7), "Normal Sauran Bellwarden field 3")
        assert_clear_net(pb, GUARD_1, "Bellwarden field 3 clear-room net")
        checked += 1

        # Screen 29 after boss 6 (region 1, step 2). Return screen is 21.
        # 21 south->27, 27 east->28, 28 east->29.
        enter_guard_field(pb, 0x51A70003, 6, 29,
                          hops=[(27, 72, 232), (28, 232, 60), (29, 232, 60)])
        assert_reachable_warden(
            pb, expected_for_stage(6), "Normal Sauran Bellwarden field 29")
        assert_clear_net(pb, GUARD_3, "field 29 clear-room net")
        checked += 1
    finally:
        pb.stop(save=False)

    print(f"[riftwild-guard-spawn] PASS later guards + Bellwarden + clear nets; "
          f"total fields checked={checked}")


if __name__ == "__main__":
    main()
