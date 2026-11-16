#!/usr/bin/env python3
"""The Serpent's plated tail stops shots and deflects blades; only the hood
takes damage, the plates go slack (and let shots through) while it unwinds,
and Will signatures cut through.

Headless PyBoy fixture: the Verdant boss room with the head pinned in the
top-right corner and a straight vertical coil at x=100. Player projectiles
are written straight into free entity slots so each case is deterministic.
"""
from pathlib import Path

from test_boss_identity import addr, enter_boss, put16, EN, PL, TM

TAIL_X, TAIL_Y = addr("_serpent_tail_x"), addr("_serpent_tail_y")
VISIBLE, DIRTY = addr("_serpent_tail_visible"), addr("_serpent_body_dirty")
FLASH, CELLS = addr("_serpent_tail_flash"), addr("_serpent_body_cells")
HEAD_X, HEAD_Y, WALL_X = 112, 16, 72
VERDANT = [0x0000, 0x3C6A, 0x611B, 0x3BFF]
SLACK = [0x0000, 0x20A6, 0x396D, 0x4A74]


def bg_palette(pb, slot):
    raw = []
    for index in range(slot * 8, slot * 8 + 8):
        pb.memory[0xFF68] = index
        raw.append(pb.memory[0xFF69])
    return [raw[i] | raw[i + 1] << 8 for i in range(0, 8, 2)]


def pin(pb, boss, state):
    put16(pb, boss + 3, HEAD_X)
    put16(pb, boss + 7, HEAD_Y)
    pb.memory[boss + 15] = state
    if state == 2:
        pb.memory[boss + 11] = 0      # unwind corner index
    pb.memory[TAIL_X] = HEAD_X + 12
    pb.memory[TAIL_Y] = HEAD_Y + 12
    for i in range(1, 49):
        pb.memory[TAIL_X + i] = WALL_X + 4
        pb.memory[TAIL_Y + i] = 36 + 8 * min(i - 1, 10)
    pb.memory[VISIBLE] = 48
    put16(pb, PL + 9, 16)
    put16(pb, PL + 11, 64)
    pb.memory[PL + 15] = 120          # hero invulnerable for the fixture


def settle(pb, boss, state, frames=8):
    for _ in range(frames):
        pin(pb, boss, state)
        pb.memory[DIRTY] = 1
        pb.tick(1, render=True, sound=False)


def wall_drawn(pb):
    tx = (WALL_X + 4) >> 3
    rows = [ty for ty in range(4, 15)
            if pb.memory[CELLS + ty * 4 + (tx >> 3)] & (1 << (tx & 7))]
    return rows


def spawn_shot(pb, x, y, vx, melee=False, flags=0):
    for i in range(32):
        e = EN + i * 28
        if pb.memory[e] == 0:
            break
    else:
        raise AssertionError("no free entity slot")
    for k in range(28):
        pb.memory[e + k] = 0
    pb.memory[e] = 1                  # ENT_PROJECTILE
    pb.memory[e + 1] = 0x11           # EF_ACTIVE | EF_PLAYER_PROJ
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 10] = vx & 0xFF
    pb.memory[e + 12] = 33
    pb.memory[e + 13] = 2
    pb.memory[e + 14] = 1             # pierce
    pb.memory[e + 16] = 18 if melee else 60
    pb.memory[e + 17 + 2] = 1 if melee else 0
    pb.memory[e + 17 + 3] = flags
    pb.memory[e + 25] = 0x88 if melee else 0x77
    pb.memory[e + 26] = 4
    return e


def fly(pb, boss, state, shot, frames=40):
    """Track the shot. Returns (max x reached, flash seen, palettes seen)."""
    max_x, flash, palettes = 0, 0, []
    for _ in range(frames):
        pin(pb, boss, state)
        pb.tick(1, render=True, sound=False)
        flash = max(flash, pb.memory[FLASH])
        palettes.append(bg_palette(pb, 6))
        if not (pb.memory[shot] == 1 and pb.memory[shot + 1] & 0x10
                and pb.memory[shot + 1] & 1):
            # Let the plate flash reach the palette before reporting.
            for _ in range(4):
                pin(pb, boss, state)
                pb.tick(1, render=True, sound=False)
                palettes.append(bg_palette(pb, 6))
            break
        max_x = max(max_x, pb.memory[shot + 3] | pb.memory[shot + 4] << 8)
    return max_x, flash, palettes


def main():
    pb, boss = enter_boss(1, keep_open=True)
    for i in range(32):
        e = EN + i * 28
        if e != boss and pb.memory[e] in (1, 2):
            pb.memory[e] = pb.memory[e + 1] = 0
    for i in range(20 * 17):
        if pb.memory[TM + i] not in (0, 3):
            pb.memory[TM + i] = 1
    for x in range(1, 19):
        for y in range(1, 16):
            pb.memory[TM + y * 20 + x] = 1

    pb.memory[boss + 14] = 200
    # 1. Plated: a shot into the coil stops at it, with a flash, no damage.
    settle(pb, boss, 0, 40)
    assert len(wall_drawn(pb)) >= 10, f"coil not drawn: {wall_drawn(pb)}"
    assert bg_palette(pb, 6) == VERDANT, f"plated coil palette {bg_palette(pb, 6)}"
    hp = pb.memory[boss + 14]
    shot = spawn_shot(pb, 32, 64, 3)
    max_x, flash, pals = fly(pb, boss, 0, shot)
    assert max_x < WALL_X + 4, f"shot crossed the plated coil (x={max_x})"
    assert flash, "blocked shot did not flash the plates"
    assert any(p[2] == 0x7FFF for p in pals), "no white block flash on the coil"
    assert pb.memory[boss + 14] == hp, "a tail block damaged the boss"
    Path("tmp").mkdir(exist_ok=True)
    pb.screen.image.save("tmp/serpent-tail-block.png")

    # 2. Melee is deflected the same way.
    settle(pb, boss, 0, 10)
    blade = spawn_shot(pb, 56, 64, 3, melee=True)
    max_x, flash, _ = fly(pb, boss, 0, blade, 18)
    assert max_x < WALL_X + 4 and flash, f"blade passed the plated coil (x={max_x})"
    assert pb.memory[boss + 14] == hp, "a deflected blade damaged the boss"

    # 3. The hood still takes damage while the plates are up.
    settle(pb, boss, 0, 10)
    shot = spawn_shot(pb, 88, HEAD_Y + 2, 3)
    fly(pb, boss, 0, shot, 30)
    assert pb.memory[boss + 14] < hp, "the hood did not take damage"
    hp = pb.memory[boss + 14]

    # 4. A Will signature / Convergence chord cuts straight through.
    settle(pb, boss, 0, 10)
    chord = spawn_shot(pb, 32, 64, 3, flags=0x01)
    max_x, _, _ = fly(pb, boss, 0, chord, 30)
    assert max_x > WALL_X + 12, f"Convergence chord was blocked (x={max_x})"

    # 5. Unwinding after a storm charge: plates slack (grey), shots pass.
    settle(pb, boss, 2, 12)
    assert bg_palette(pb, 6) == SLACK, f"slack coil palette {bg_palette(pb, 6)}"
    shot = spawn_shot(pb, 32, 64, 3)
    max_x, flash, _ = fly(pb, boss, 2, shot, 58)
    assert max_x > WALL_X + 12, f"slack coil still blocked the shot (x={max_x} flash={flash} cells={wall_drawn(pb)} hp={pb.memory[boss+14]} st={pb.memory[boss+15]} {list(pb.memory[shot:shot+28])})"
    pb.screen.image.save("tmp/serpent-tail-slack.png")
    pb.stop(save=False)
    print("serpent tail shield: block, deflect, hood damage, signature, slack window OK")


if __name__ == "__main__":
    main()
