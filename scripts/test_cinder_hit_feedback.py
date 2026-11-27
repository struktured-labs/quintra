#!/usr/bin/env python3
"""Cinder Rex must make it obvious when a hit hurts it (issue #248).

Carmelo, on hardware, could not tell whether he was hurting the merged
stage 3 boss. Only the head/vent is a weak point, and only while
cinder_damage_open. This locks the feedback for both outcomes:

  * Open-window head hit: HP drops, SFX_HIT plays, no armor clink, and
    the whole 48x32 body flashes bone white (OBJ palette 0).
  * Body hit, or any hit on a closed window: HP holds, the armor clink
    plays instead of SFX_HIT, a spark is counted, and the body never
    flashes white.
  * The open-window tell no longer touches ai_data[7] (the damage flash).
    The open head strobes gold/blue on its own, the closed head glows
    gold more slowly, and the armored body never changes colour.
  * The boss HP bar is on the HUD during the merged form.
"""
from test_boss_identity import addr, enter_boss
from test_cinder_absorb import FLAGS, HP, SPARKS, to_rex, u16
from test_colossal_cinder import (
    CINDER_DAMAGE_OPEN, CINDER_PATTERN, CINDER_PHASE, CINDER_TIMER,
    clear_hostiles, keep_alive, place_player_shot,
)
from test_will_sfx import sfx_ids
from test_cinder_absorb import PL
from test_boss_identity import CAMERA_X

OAM = 0xFE00
REX_OAM = range(16, 40)
AI7 = 24                       # entity.ai_data[7]: the damage flash timer
DMG = 26
PAL_WHITE, PAL_BLUE, PAL_RED, PAL_GOLD, PAL_BOSS = 0, 3, 4, 5, 6
HUD_BAR_FULL, HUD_BAR_EMPTY = 26, 27
CLINKS = addr("_cinder_clink_count")
SFX_PLAY = addr("_sfx_play")
OPEN_T, CLOSED_T = 130, 50
SFX = sfx_ids()


def hook_sfx(pb):
    seen = []
    pb.hook_register(SFX_PLAY >> 16, SFX_PLAY & 0xFFFF,
                     lambda _ctx: seen.append(pb.register_file.A), None)
    return seen


def rex_cells(pb, boss):
    """On-screen Rex sprites as (column, row, palette), plus the head side.

    Rex owns OAM 16..39 as a 6x4 grid, row by row, left to right. The
    logical anchor is the head, on the front two columns of the top two
    rows: columns 0-1 facing west, 4-5 facing east. Columns clipped at
    the screen edge are parked, so they are simply absent here.
    """
    anchor_sx = (u16(pb, boss + 3) - pb.memory[CAMERA_X] + 8) & 0xFF
    cells, lo = [], None
    for i in REX_OAM:
        y, x = pb.memory[OAM + i * 4], pb.memory[OAM + i * 4 + 1]
        if not (y and x):
            continue
        col, row = (i - 16) % 6, (i - 16) // 6
        cells.append((col, row, pb.memory[OAM + i * 4 + 3] & 7))
        if x == anchor_sx and col in (0, 4):
            lo = col
    assert lo is not None, "Rex head is not on screen"
    return cells, lo


def split_head(pb, boss):
    cells, lo = rex_cells(pb, boss)
    head = [p for c, r, p in cells if c in (lo, lo + 1) and r < 2]
    body = [p for c, r, p in cells if not (c in (lo, lo + 1) and r < 2)]
    # A cell or two may be clipped at the screen edge; never the whole head.
    assert len(head) >= 2 and len(body) >= 12, (len(head), len(body))
    return head, body, lo


def hold(pb, timer):
    pb.memory[CINDER_TIMER] = timer
    pb.memory[CINDER_PATTERN] = 1
    pb.memory[PL + 15] = 255


def watch(pb, boss, timer, frames):
    """Tick frame by frame at a pinned cycle time; sample the Rex palettes."""
    samples = []
    for _ in range(frames):
        hold(pb, timer)
        pb.tick()
        if pb.memory[CINDER_PHASE] != 2:
            continue
        samples.append(split_head(pb, boss))
    return samples


def white_frames(samples):
    return sum(all(p == PAL_WHITE for p in head + body)
               for head, body, _ in samples)


def shoot(pb, boss, seen, where, timer):
    """One stationary shot, then watch the result frame by frame."""
    pb.memory[boss + HP] = 80
    clear_hostiles(pb)
    hold(pb, timer)
    keep_alive(pb, 1)
    hold(pb, timer)
    # Let the 8-frame clink cooldown from an earlier shot run out.
    watch(pb, boss, timer, 12)
    pb.memory[boss + AI7] = 0
    ax, ay = u16(pb, boss + 3), u16(pb, boss + 7)
    if where == "head":
        x, y = ax + 2, ay + 2
    else:
        # The tail end of the 48px body, 32px+ behind the head anchor.
        lo = split_head(pb, boss)[2]
        x, y = (ax + 40 if lo == 0 else ax - 28), ay + 5
    hp0, sparks0 = pb.memory[boss + HP], pb.memory[SPARKS]
    clinks0, mark = pb.memory[CLINKS], len(seen)
    shot = place_player_shot(pb, x, y)
    pb.memory[shot + DMG] = 12
    samples = watch(pb, boss, timer, 10)
    return {
        "where": where, "timer": timer,
        "open": pb.memory[CINDER_DAMAGE_OPEN],
        "dhp": hp0 - pb.memory[boss + HP],
        "hit_sfx": seen[mark:].count(SFX["SFX_HIT"]),
        "clinks": (pb.memory[CLINKS] - clinks0) & 255,
        "sparks": (pb.memory[SPARKS] - sparks0) & 255,
        "white": white_frames(samples),
        "shot_live": bool(pb.memory[shot + FLAGS] & 1),
    }


def window_map(pb):
    return 0x9C00 if pb.memory[0xFF40] & 0x40 else 0x9800


def boss_bar(pb):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    row = [pb.memory[window_map(pb) + 12 + i] for i in range(4)]
    pb.memory[0xFF4F] = bank
    return row


def main():
    pb, boss = enter_boss(2, keep_open=True)
    seen = hook_sfx(pb)
    to_rex(pb, boss, 80)

    # --- the open-window tell is not the damage flash --------------------
    # Settle first: the unfold's red head telegraph and the first pinned
    # frame (drawn before the window flag catches up) are not the tell.
    watch(pb, boss, OPEN_T, 24)
    pb.memory[boss + AI7] = 0
    idle_open = watch(pb, boss, OPEN_T, 48)
    assert pb.memory[CINDER_DAMAGE_OPEN] == 1
    assert pb.memory[boss + AI7] == 0, (
        "the open-window tell still writes ai_data[7], the damage flash")
    assert white_frames(idle_open) == 0, (
        "Rex flashed white on an open window with no hit")
    open_head = {p for head, _, _ in idle_open for p in head}
    assert all(len(set(head)) == 1 for head, _, _ in idle_open)
    assert open_head == {PAL_GOLD, PAL_BLUE}, (
        f"open head should strobe gold/blue, saw palettes {open_head}")
    assert all(set(body) == {PAL_BOSS} for _, body, _ in idle_open), (
        "the open-window strobe leaked onto the armored body")

    watch(pb, boss, CLOSED_T, 4)
    idle_closed = watch(pb, boss, CLOSED_T, 48)
    assert pb.memory[CINDER_DAMAGE_OPEN] == 0
    assert white_frames(idle_closed) == 0
    closed_head = {p for head, _, _ in idle_closed for p in head}
    assert PAL_GOLD in closed_head and PAL_BLUE not in closed_head, (
        f"closed head should glow gold without the open strobe: {closed_head}")
    assert all(set(body) == {PAL_BOSS} for _, body, _ in idle_closed)
    # Stronger when open: the open head changes palette far more often.
    def flips(samples):
        heads = [head[0] for head, _, _ in samples]
        return sum(a != b for a, b in zip(heads, heads[1:]))
    assert flips(idle_open) >= 2 * max(1, flips(idle_closed)), (
        f"open strobe ({flips(idle_open)} flips) is not clearly faster than "
        f"the closed glow ({flips(idle_closed)} flips)")

    # --- a damaging head hit ---------------------------------------------
    hurt = shoot(pb, boss, seen, "head", OPEN_T)
    assert hurt["open"] == 1 and hurt["dhp"] > 0, hurt
    assert hurt["hit_sfx"] >= 1, f"a damaging head hit played no SFX_HIT: {hurt}"
    assert hurt["clinks"] == 0, f"a damaging head hit also clinked: {hurt}"
    assert hurt["white"] >= 3, (
        f"a damaging hit did not flash the whole body white: {hurt}")

    # --- rejected hits: armor clink, never SFX_HIT -----------------------
    rejects = [
        shoot(pb, boss, seen, "body", OPEN_T),
        shoot(pb, boss, seen, "body", CLOSED_T),
        shoot(pb, boss, seen, "head", CLOSED_T),
    ]
    for r in rejects:
        assert r["dhp"] == 0 and not r["shot_live"], r
        assert r["hit_sfx"] == 0, f"an armored hit played SFX_HIT: {r}"
        assert r["clinks"] == 1, f"an armored hit did not clink once: {r}"
        assert r["sparks"] >= 1, f"an armored hit made no spark: {r}"
        assert r["white"] == 0, f"an armored hit flashed like damage: {r}"

    # --- the boss HP bar stays on the HUD for the merged form ------------
    pb.memory[boss + HP] = 80
    keep_alive(pb, 4)
    bar = boss_bar(pb)
    assert all(t in (HUD_BAR_FULL, HUD_BAR_EMPTY) for t in bar), (
        f"boss HP bar is not on the HUD during Rex: tiles {bar}")
    assert HUD_BAR_FULL in bar and HUD_BAR_EMPTY in bar, (
        f"boss HP bar does not show 80 of 240 HP: tiles {bar}")

    pb.stop(save=False)
    print(f"[cinder-hit-feedback] PASS head hit: SFX_HIT, -{hurt['dhp']} HP, "
          f"{hurt['white']} white body frames; body/closed hits: clink, "
          f"spark, 0 HP, no flash; head tell on its own palettes; HP bar shown")


if __name__ == "__main__":
    main()
