#!/usr/bin/env python3
"""Max-Will v2 (2026-11-17 spec): authored arts for Sauran, Vespine, Corvin
and Wolfkin's cross-rend; Picsean's crest voice; one shared recast lock."""

import re
from pathlib import Path

from test_will_max import (
    PLAYER, ENTITIES, ENTITY_SIZE, WILL_OFFSET, LEVEL_OFFSET, WILL_MAX,
    addr, boot, clear_arena,
)

ROOT = Path(__file__).resolve().parent.parent
EF_ELITE = 0x20
AUX_CARRIER = 0xF0
LIVE = addr("_will_maxfx_live")
TICK = addr("_will_maxfx_t")
ABORT = addr("_picsean_vortex_abort")
SLOW = addr("_picsean_vortex_slow_charge")
READY = addr("_picsean_vortex_ready_at")
CLOCK = addr("_loop_frame_counter")
BG_SHADOW = addr("_palette_bg_shadow")
MARK_SLOT = addr("_will_corvin_mark_slot")
MARK_TICKS = addr("_will_corvin_mark_ticks")
SWARM = addr("_will_vespine_swarm_ticks")
SFX_PLAY = addr("_sfx_play")

NAMES = {0: "Wolfkin", 1: "Sauran", 2: "Corvin", 3: "Picsean", 4: "Vespine"}
LIFE = {0: 42, 1: 52, 2: 48, 4: 54}
# Damage on a body in the lane at Will 1, LCK 0 (spec: ~18/20/16; Wolfkin
# keeps the shipped point-blank total, ~29, across two beats).
BAND = {0: (18, 34), 1: (14, 24), 2: (12, 22), 4: (16, 26)}


def sfx_ids():
    body = (ROOT / "src/audio/sfx.h").read_text().split("enum {", 1)[1]
    body = body.split("};", 1)[0]
    ids, n = {}, 0
    for raw in body.splitlines():
        line = raw.split("//", 1)[0].strip().rstrip(",")
        if not line:
            continue
        ids[line] = n
        n += 1
    return ids


def put_fix8(pb, a, px):
    raw = (px & 0xFFFF) << 8
    for i in range(4):
        pb.memory[a + i] = (raw >> (i * 8)) & 0xFF


def get16(pb, a):
    return pb.memory[a] | (pb.memory[a + 1] << 8)


def crawler(pb, slot, x, y, hp=200, flags=0x07):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 2
    pb.memory[e + 1] = flags
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 12] = 20
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 120
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    return e


def hostile_shot(pb, slot, x, y):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 1
    pb.memory[e + 1] = 0x03
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 12] = 28
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 250
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    return e


def carriers(pb):
    out = []
    for i in range(32):
        e = ENTITIES + i * ENTITY_SIZE
        if (pb.memory[e] == 1 and pb.memory[e + 1] & 0x10
                and pb.memory[e + 23] == AUX_CARRIER):
            out.append(e)
    return out


def floor_colour(pb):
    return get16(pb, BG_SHADOW + 2)


def arm(pb, unlock=True):
    pb.memory[PLAYER + WILL_OFFSET] = WILL_MAX
    pb.memory[PLAYER + LEVEL_OFFSET] = 1
    pb.memory[PLAYER + 8] = 0         # LCK 0: no crits
    pb.memory[PLAYER + 13] = 1        # face right
    if unlock:
        pb.memory[SLOW] = 0


def press_max(pb):
    """Right+A; returns True when the MAX commits (tier spent)."""
    pb.button_press("right")
    pb.button_press("a")
    fired = False
    for _ in range(30):
        pb.tick()
        if pb.memory[PLAYER + LEVEL_OFFSET] == 0:
            fired = True
            break
    pb.button_release("a")
    pb.button_release("right")
    pb.tick(2)          # let the game see the release before the next press
    return fired


def run_art(pb, cid, limit=140, on_tick=None):
    seen_live = False
    for _ in range(limit):
        if on_tick:
            on_tick()
        pb.tick()
        if pb.memory[LIVE]:
            seen_live = True
        elif seen_live or cid == 3:
            break
    pb.tick(2)


def hero_contract(cid, ids):
    name = NAMES[cid]
    pb = boot(cid)
    seen = []
    pb.hook_register(SFX_PLAY >> 16, SFX_PLAY & 0xFFFF,
                     lambda _c: seen.append(pb.register_file.A), None)
    try:
        clear_arena(pb)
        px = get16(pb, PLAYER + 9)
        py = get16(pb, PLAYER + 11)
        dummy = crawler(pb, 10, px + 32, py + 4)
        # Wolfkin's shipped claw lanes cleave two bodies in turn; keep his
        # heavy off the lane so the band measures one body.
        heavy = crawler(pb, 11, px + 44, py + (40 if cid == 0 else 4),
                        flags=0x07 | EF_ELITE)
        pb.tick(12)
        base_floor = floor_colour(pb)
        hp0, hh0 = pb.memory[dummy + 14], pb.memory[heavy + 14]
        arm(pb)
        seen.clear()
        assert press_max(pb), f"{name} MAX did not fire"
        assert pb.memory[LIVE] == cid + 1, f"{name} art did not start"
        if cid != 0:
            assert len(carriers(pb)) == 1, f"{name} must own exactly one carrier"
            assert floor_colour(pb) != base_floor, f"{name} has no palette wash"
        assert pb.memory[SLOW] == 1, f"{name} did not arm the recast lock"
        drops = []
        last = [pb.memory[dummy + 14]]

        def watch():
            hp = pb.memory[dummy + 14]
            if hp < last[0]:
                drops.append(last[0] - hp)
            last[0] = hp
        run_art(pb, cid, on_tick=watch)
        assert pb.memory[LIVE] == 0, f"{name} art never ended"
        dmg = hp0 - pb.memory[dummy + 14]
        hdmg = hh0 - pb.memory[heavy + 14]
        lo, hi = BAND[cid]
        assert lo <= dmg <= hi, f"{name} lane damage {dmg} outside {BAND[cid]} ({drops})"
        if cid in (1, 2):
            assert len(drops) <= 2, f"{name} hit one body more than once per beat: {drops}"
            assert hdmg <= 12, f"{name} heavy cap broken: {hdmg}"
        assert not carriers(pb), f"{name} leaked its carrier"
        assert floor_colour(pb) == base_floor, f"{name} left the palette washed"
        assert all(pb.memory[0xFE00 + k * 4] == 0 for k in range(32, 36)), \
            f"{name} left direct OAM behind"
        assert ids["SFX_ROAR"] not in seen, f"{name} MAX still plays SFX_ROAR"

        # Lock: a second full bar inside 360 frames is an ordinary shot.
        arm(pb, unlock=False)
        press_max(pb)
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 1, f"{name} recast inside the lock"
        assert pb.memory[LIVE] == 0
        pb.memory[READY] = pb.memory[CLOCK]
        pb.memory[READY + 1] = pb.memory[CLOCK + 1]
        clear_arena(pb)
        arm(pb, unlock=False)
        ok = press_max(pb)
        assert ok, (f"{name} MAX stayed locked after the lock expired: lvl "
                    f"{pb.memory[PLAYER + LEVEL_OFFSET]} slow {pb.memory[SLOW]} "
                    f"clock {get16(pb, CLOCK)} ready {get16(pb, READY)} "
                    f"live {pb.memory[LIVE]} screen {pb.memory[addr('_loop_current_screen')]}")

        # Room exit mid-cast: abort restores palette and frees everything.
        pb.tick(6)
        pb.memory[ABORT] = 1
        pb.tick(3)
        assert pb.memory[LIVE] == 0, f"{name} ignored the room-exit abort"
        assert not carriers(pb), f"{name} abort leaked the carrier"
        assert floor_colour(pb) == base_floor, f"{name} abort left the wash"
        print(f"  ok  {name}: lane {dmg} {drops}, heavy {hdmg}")
        return dmg
    finally:
        pb.stop(save=False)


def corvin_mark():
    pb = boot(2)
    try:
        clear_arena(pb)
        px = get16(pb, PLAYER + 9)
        py = get16(pb, PLAYER + 11)
        dummy = crawler(pb, 10, px + 48, py + 4)
        pb.tick(8)
        hp0 = pb.memory[dummy + 14]
        pb.memory[MARK_SLOT] = 10
        pb.memory[MARK_TICKS] = 120
        arm(pb)
        assert press_max(pb)
        marked_before = pb.memory[MARK_TICKS]
        run_art(pb, 2)
        dmg = hp0 - pb.memory[dummy + 14]
        assert dmg >= 15, f"marked Murderstorm too weak: {dmg}"
        assert pb.memory[MARK_TICKS] + 10 >= marked_before, "Mark was not refreshed"
        print(f"  ok  Corvin marked target {dmg}")
    finally:
        pb.stop(save=False)


def vespine_swarm_and_shots():
    pb = boot(4)
    try:
        clear_arena(pb)
        px = get16(pb, PLAYER + 9)
        py = get16(pb, PLAYER + 11)
        shot = hostile_shot(pb, 12, px + 18, py + 6)
        crawler(pb, 10, px + 40, py + 4)
        arm(pb)
        assert press_max(pb)
        pb.tick(4)
        assert not (pb.memory[shot] == 1 and pb.memory[shot + 1] & 1
                    and not pb.memory[shot + 1] & 0x10), "frontal deflect missed a shot"
        while pb.memory[TICK] < 43 and pb.memory[LIVE]:
            pb.tick()
        pb.memory[SWARM] = 100
        while pb.memory[TICK] < 47 and pb.memory[LIVE]:
            pb.tick()
        assert pb.memory[SWARM] >= 125, f"rupture did not feed the Swarm ({pb.memory[SWARM]})"
        print("  ok  Vespine deflect + Swarm feed")
    finally:
        pb.stop(save=False)


def sauran_pylons_eat_shots():
    pb = boot(1)
    try:
        clear_arena(pb)
        px = get16(pb, PLAYER + 9)
        py = get16(pb, PLAYER + 11)
        arm(pb)
        assert press_max(pb)
        while pb.memory[TICK] < 22:
            pb.tick()
        # A shot dropped on pylon A (24 ahead, 10 across) is eaten.
        shot = hostile_shot(pb, 20, px + 8 + 24 - 3, py + 8 + 10 - 3)
        pb.tick(6)
        assert not (pb.memory[shot] == 1 and pb.memory[shot + 1] & 1
                    and not pb.memory[shot + 1] & 0x10), "pylon did not eat a shot"
        print("  ok  Sauran pylons eat shots")
    finally:
        pb.stop(save=False)


def picsean_crest(ids):
    pb = boot(3)
    seen = []
    pb.hook_register(SFX_PLAY >> 16, SFX_PLAY & 0xFFFF,
                     lambda _c: seen.append(pb.register_file.A), None)
    try:
        clear_arena(pb)
        arm(pb)
        seen.clear()
        assert press_max(pb)
        ticks = addr("_picsean_vortex_ticks")
        nr42 = []
        for _ in range(140):
            pb.tick()
            nr42.append(pb.memory[0xFF21])
            if not pb.memory[ticks]:
                break
        assert seen.count(ids["SFX_ROAR"]) <= 1, f"crest still roars: {seen}"
        assert 0xF2 in nr42, "surf crash missing at the crest"
        print("  ok  Picsean crest is a surf crash (one cast roar)")
    finally:
        pb.stop(save=False)


def structural():
    # The v2 arts ride the Tide Vortex dispatch: no new hooks in the hot
    # combat loop or room_draw_overlays.
    vortex = (ROOT / "src/game/picsean_vortex.c").read_text()
    assert "will_maxfx_tick();" in vortex and "will_maxfx_draw();" in vortex
    assert "will_maxfx" not in (ROOT / "src/game/combat.c").read_text()
    fx = (ROOT / "src/game/will_maxfx.c").read_text()
    assert fx.startswith("#pragma bank 27")
    assert "sfx_play(SFX_ROAR)" not in fx


def main():
    structural()
    ids = sfx_ids()
    for cid in (1, 4, 2, 0):
        hero_contract(cid, ids)
    corvin_mark()
    vespine_swarm_and_shots()
    sauran_pylons_eat_shots()
    picsean_crest(ids)
    print("[will-max-v2] PASS four authored arts, shared lock, crest voice")


if __name__ == "__main__":
    main()
