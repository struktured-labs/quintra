#!/usr/bin/env python3
"""Late-fight Cinder Rex armor must be readable, and never silently ignore hits.

Carmelo's Vespine death in Ember Depths felt like the boss "absorbed hits
near the end." Live probes on main (4614675c) showed this is authored
invulnerability with misleading feedback, not a dropped-damage bug:

  * Only the 15x13 head/vent is a weak point, even while the 48x32 body
    flashes. Body shots die with SPR_FX_IMPACT + the ordinary SFX_HIT
    crunch, so they sound like damage.
  * At 40 HP, Rex splits into five fire husks for a full invuln reprise
    (now 64 frames). Every colliding shot is consumed; HP does not move.
  * Large-boss per-hit damage is clamped to 3 on Normal (5 on Easy), so
    a 12- or 20-damage volley still only chips 3.

This contract locks the readable reject (spark + clink counter), the
shortened late split, the vent-only damage window, the damage cap, and
Vespine Swarm / a MAX volley on both the closed husks and the open head.
"""
from test_boss_identity import EN, PL, addr, enter_boss, put16
from test_colossal_cinder import (
    CINDER_ACTIVE, CINDER_DAMAGE_OPEN, CINDER_PHASE, CINDER_PATTERN,
    CINDER_TIMER, CINDER_X, CINDER_Y, keep_alive, clear_hostiles,
    place_player_shot,
)
from test_will_max import boot
from test_boss_identity import RS, TM, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y
from quintra_vignettes import mute_vignettes
from quintra_topology import STAGE_BOSS_ROOM, STAGE_START, dungeon_direction
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
ENTITY_SIZE = 28
HP, FLAGS, DMG = 14, 1, 26
STAGE, ROOM_W = 2, 20
SPARKS = addr("_cinder_armor_sparks")
SWARM = addr("_will_vespine_swarm_ticks")
SCREEN = addr("_loop_current_screen")
NORMAL_CAP = 3
PHASE3_MAX = 72   # authored 64, plus a few frames of settle


def u16(pb, a):
    return pb.memory[a] | (pb.memory[a + 1] << 8)


def rex_body_box(pb):
    cam_x, cam_y = pb.memory[CAMERA_X], pb.memory[CAMERA_Y]
    xs, ys = [], []
    for i in range(16, 40):
        y = pb.memory[0xFE00 + i * 4]
        x = pb.memory[0xFE00 + i * 4 + 1]
        if y and x:
            xs.append(x - 8 + cam_x)
            ys.append(y - 16 + cam_y)
    assert xs, "Rex body is not on screen"
    return min(xs), min(ys), max(xs) + 8, max(ys) + 8


def to_rex(pb, boss, hp=80):
    pb.memory[PL + 1] = pb.memory[PL + 2] = 255
    pb.memory[PL + 15] = 255
    pb.memory[boss + HP] = 120
    for _ in range(400):
        keep_alive(pb, 1)
        if pb.memory[CINDER_PHASE] == 2:
            break
    assert pb.memory[CINDER_PHASE] == 2, "Cinder Rex did not unfold"
    pb.memory[boss + HP] = hp
    keep_alive(pb, 2)


def fire_shot(pb, boss, x, y, damage=12, timer=None, pattern=1, hp=None,
              retarget_head=False):
    if hp is not None:
        pb.memory[boss + HP] = hp
    if timer is not None:
        pb.memory[CINDER_TIMER] = timer
        pb.memory[CINDER_PATTERN] = pattern
    clear_hostiles(pb)
    if timer is not None:
        pb.memory[CINDER_TIMER] = timer
        pb.memory[CINDER_PATTERN] = pattern
    if hp is not None:
        pb.memory[boss + HP] = hp
    if retarget_head:
        # One tick lets Rex finish a facing/anchor swap after we poke the timer.
        pb.memory[PL + 15] = 255
        keep_alive(pb, 1)
        if timer is not None:
            pb.memory[CINDER_TIMER] = timer
            pb.memory[CINDER_PATTERN] = pattern
        x = u16(pb, boss + 3) + 2
        y = u16(pb, boss + 7) + 2
    before_hp = pb.memory[boss + HP]
    before_sparks = pb.memory[SPARKS]
    shot = place_player_shot(pb, x, y)
    pb.memory[shot + DMG] = damage
    pb.memory[PL + 15] = 255
    keep_alive(pb, 2)
    return {
        "dhp": before_hp - pb.memory[boss + HP],
        "shot_live": bool(pb.memory[shot + FLAGS] & 1),
        "sparks": (pb.memory[SPARKS] - before_sparks) & 255,
        "open": pb.memory[CINDER_DAMAGE_OPEN],
        "phase": pb.memory[CINDER_PHASE],
        "on": bool(pb.memory[boss + FLAGS] & 4),
        "hp": pb.memory[boss + HP],
    }


def warp_to_cinder(pb):
    target = STAGE_BOSS_ROOM[STAGE]
    pb.memory[RS + 1] = target - 1
    pb.memory[RS + 11] = STAGE
    pb.memory[RS + 6] = 0xFF
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    put16(pb, RS + 23, 1 << STAGE)
    pb.memory[RS + 27] = (1 << 0) | (1 << 3) | (1 << 6) | (1 << 7)
    pb.memory[RS + 28] |= (1 << 2) | (1 << 7)
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    source_local = target - 1 - STAGE_START[STAGE]
    target_local = target - STAGE_START[STAGE]
    direction = dungeon_direction(source_local, target_local)
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * ROOM_W + tx] = 3
    x, y = {0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60)}[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(80):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, "could not enter Ember boss"
    for _ in range(60):
        pb.tick()
    boss = None
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == 2 and pb.memory[ep + 17] == 1 and pb.memory[ep + 20] & 1:
            boss = ep
            break
    assert boss is not None and pb.memory[CINDER_ACTIVE] == 1
    pb.memory[PL + 1] = pb.memory[PL + 2] = 255
    pb.memory[PL + 15] = 255
    return boss


def test_windows_and_cap():
    pb, boss = enter_boss(2, keep_open=True)
    to_rex(pb, boss, 80)
    x0, y0, x1, y1 = rex_body_box(pb)
    ax, ay = u16(pb, boss + 3), u16(pb, boss + 7)
    tail_x, tail_y = x0 + 4, y0 + 14
    head_x, head_y = ax + 2, ay + 2

    closed_tail = fire_shot(pb, boss, tail_x, tail_y, timer=50, hp=80)
    closed_head = fire_shot(pb, boss, head_x, head_y, timer=50, hp=80)
    assert closed_tail["dhp"] == 0 and not closed_tail["shot_live"], closed_tail
    assert closed_head["dhp"] == 0 and not closed_head["shot_live"], closed_head
    assert closed_tail["sparks"] >= 1 and closed_head["sparks"] >= 1, (
        f"closed armor rejected a shot without a spark counter tick: "
        f"tail={closed_tail} head={closed_head}")

    open_tail = fire_shot(pb, boss, tail_x, tail_y, timer=130, hp=80)
    assert open_tail["dhp"] == 0 and not open_tail["shot_live"], open_tail
    assert open_tail["open"] == 1 and open_tail["sparks"] >= 1, open_tail

    open_head = fire_shot(pb, boss, head_x, head_y, damage=12, timer=130, hp=80, retarget_head=True)
    assert open_head["open"] == 1 and open_head["dhp"] == NORMAL_CAP, open_head
    assert not open_head["shot_live"]

    chip = fire_shot(pb, boss, head_x, head_y, damage=1, timer=130, hp=80, retarget_head=True)
    assert chip["dhp"] == 1, chip
    capped = fire_shot(pb, boss, head_x, head_y, damage=20, timer=130, hp=80, retarget_head=True)
    assert capped["dhp"] == NORMAL_CAP, capped

    # Late split: every husk shot is a readable reject, and the reprise is brief.
    pb.memory[boss + HP] = 40
    for _ in range(80):
        keep_alive(pb, 1)
        if pb.memory[CINDER_PHASE] == 3:
            break
    assert pb.memory[CINDER_PHASE] == 3, "critical Rex did not split"
    assert pb.memory[CINDER_DAMAGE_OPEN] == 0
    assert not (pb.memory[boss + FLAGS] & 4)
    start = pb.memory[CINDER_TIMER]
    sparks = 0
    for i in range(5):
        if pb.memory[CINDER_PHASE] != 3:
            break
        r = fire_shot(pb, boss, pb.memory[CINDER_X + i] + 5,
                      pb.memory[CINDER_Y + i] + 5, hp=40)
        assert r["dhp"] == 0 and not r["shot_live"], r
        sparks += r["sparks"]
    assert sparks >= 1, "phase-3 husks consumed shots without an armor spark"
    # Finish the reprise and confirm it does not linger toward the old 96f.
    frames = 0
    while pb.memory[CINDER_PHASE] == 3:
        keep_alive(pb, 1)
        frames += 1
        assert frames < PHASE3_MAX, (
            f"phase 3 lasted {start}+{frames} frames, expected under {PHASE3_MAX}")
    assert pb.memory[CINDER_PHASE] == 2

    # After recombine, the open head window still works at low HP.
    ax, ay = u16(pb, boss + 3), u16(pb, boss + 7)
    low = fire_shot(pb, boss, ax + 2, ay + 2, damage=12, timer=130, hp=40, retarget_head=True)
    assert low["dhp"] == NORMAL_CAP, low

    pb.stop(save=False)
    print("[cinder-absorb] PASS windows, cap, sparks, short late split")


def test_vespine_swarm_and_max():
    # Vespine is class 4. boot() requires the intro mute sitecustomize.
    pb = boot(4)
    mute_vignettes(pb, ROM)
    assert pb.memory[SCREEN] == 5 and pb.memory[PL] == 4
    boss = warp_to_cinder(pb)
    to_rex(pb, boss, 80)
    ax, ay = u16(pb, boss + 3), u16(pb, boss + 7)
    put16(pb, PL + 9, max(8, ax - 24))
    put16(pb, PL + 11, max(8, ay - 8))
    pb.memory[PL + 13] = 1

    # Swarm against a closed body: no HP change, but the swarm still runs.
    pb.memory[CINDER_PATTERN] = 1
    pb.memory[CINDER_TIMER] = 40
    hp0 = pb.memory[boss + HP]
    pb.button_press("b")
    keep_alive(pb, 4)
    pb.button_release("b")
    for _ in range(24):
        pb.memory[CINDER_TIMER] = 40
        pb.memory[CINDER_PATTERN] = 1
        pb.memory[PL + 15] = 255
        keep_alive(pb, 1)
    assert pb.memory[SWARM] > 0, "Vespine Swarm did not start"
    assert pb.memory[boss + HP] == hp0, (
        f"Swarm damaged a closed Rex: {hp0}->{pb.memory[boss + HP]}")

    # Late split rejects Swarm too.
    pb.memory[boss + HP] = 40
    for _ in range(80):
        keep_alive(pb, 1)
        if pb.memory[CINDER_PHASE] == 3:
            break
    assert pb.memory[CINDER_PHASE] == 3
    hp0 = pb.memory[boss + HP]
    pb.button_press("b")
    keep_alive(pb, 4)
    pb.button_release("b")
    for _ in range(20):
        if pb.memory[CINDER_PHASE] != 3:
            break
        pb.memory[PL + 15] = 255
        keep_alive(pb, 1)
    assert pb.memory[boss + HP] == hp0, (
        f"Swarm damaged phase-3 husks: {hp0}->{pb.memory[boss + HP]}")

    # After recombine, an open-head shot still deals the cap (sanity for Vespine).
    while pb.memory[CINDER_PHASE] == 3:
        keep_alive(pb, 1)
    ax, ay = u16(pb, boss + 3), u16(pb, boss + 7)
    r = fire_shot(pb, boss, ax + 2, ay + 2, damage=12, timer=130, hp=40, retarget_head=True)
    assert r["dhp"] == NORMAL_CAP, r

    pb.stop(save=False)
    print("[cinder-absorb] PASS Vespine Swarm on closed Rex and phase-3 husks")


def main():
    test_windows_and_cap()
    test_vespine_swarm_and_max()
    print("[cinder-absorb] PASS")


if __name__ == "__main__":
    main()
