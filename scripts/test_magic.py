#!/usr/bin/env python3
"""Live-ROM contract: elemental hero magic (2026-11-17 spec).

B tap casts the hero's attack spell, B hold (>= 24 frames) casts the ward,
and A+B in either order stays the special (Oath / Spirit Convergence) and
never casts a spell.
"""

from test_will_max import ENTITIES, ENTITY_SIZE, PLAYER, addr, boot, put16

HEROES = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")
SPELLS = ("MOONFIRE", "FLAME WARD", "THUNDER", "STONESKIN", "HEX",
          "SHADOW VEIL", "BLIZZARD", "CURE", "BRAMBLE", "THORN MIRROR")
WARD_COST = (2, 2, 2, 5, 2)
HOLD_FRAMES = 24

PL_HP_MAX, PL_HP, PL_MP_MAX, PL_MP = 1, 2, 3, 4
PL_X, PL_Y, PL_FACING, PL_IFRAMES = 9, 11, 13, 15
PL_ITEM, PL_ACTIVE_CHARGE, PL_SHIELD, PL_WILL = 18, 19, 20, 42
RS_BOSSES = 11

LAST = addr("_magic_last_spell")
CASTS = addr("_magic_casts")
WARD_TICKS = addr("_magic_ward_ticks")
TAP_CD = addr("_magic_tap_cd")
WARD_CD = addr("_magic_ward_cd")
CURE_USED = addr("_magic_cure_used")
HOLD = addr("_magic_hold")
RUN = addr("_run_state")
ENEMY_COUNT = addr("_entity_enemy_count")
ESTATUS = addr("_enemy_status_kind")
PSTATUS = addr("_player_status_kind")
TILEMAP = addr("_room_tilemap")
LARGE = addr("_procgen_current_room_is_large")
WORLD_W, WORLD_H = addr("_room_world_width"), addr("_room_world_height")
CAM_X, CAM_Y = addr("_room_camera_x"), addr("_room_camera_y")

ST_POISON, ST_BURN, ST_SLOW, ST_STOP, ST_CONFUSION, ST_MUTE = 1, 2, 3, 4, 6, 7
ST_HASTE = 12


def get16(pb, at):
    return pb.memory[at] | (pb.memory[at + 1] << 8)


def signed(b):
    return b - 256 if b & 0x80 else b


def slot(i):
    return ENTITIES + i * ENTITY_SIZE


def entity(pb, i, kind, x, y, hp=40, vx=0, vy=0, enemy_id=10):
    e = slot(i)
    for k in range(ENTITY_SIZE):
        pb.memory[e + k] = 0
    pb.memory[e] = kind
    pb.memory[e + 1] = 0x07
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 10] = vx & 0xFF
    pb.memory[e + 11] = vy & 0xFF
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 90
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    if kind == 2:
        pb.memory[e + 17] = enemy_id
        pb.memory[ENEMY_COUNT] = (pb.memory[ENEMY_COUNT] + 1) & 0xFF
    return e


def arena(pb, mp=None):
    """Compact empty floor, hero centred facing right, spells ready."""
    for i in range(32 * ENTITY_SIZE):
        pb.memory[ENTITIES + i] = 0
    for i in range(32):
        pb.memory[ESTATUS + i] = 0
    pb.memory[ENEMY_COUNT] = 0
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W] = 160
    pb.memory[WORLD_H] = 136
    pb.memory[CAM_X] = pb.memory[CAM_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    for i in range(20 * 17):
        pb.memory[TILEMAP + i] = 1
    put16(pb, PLAYER + PL_X, 72)
    put16(pb, PLAYER + PL_Y, 64)
    pb.memory[PLAYER + PL_IFRAMES] = 250
    pb.memory[PLAYER + PL_ACTIVE_CHARGE] = 0
    pb.memory[PLAYER + PL_WILL] = 0
    pb.memory[PLAYER + PL_HP] = pb.memory[PLAYER + PL_HP_MAX]
    pb.memory[PLAYER + PL_MP] = pb.memory[PLAYER + PL_MP_MAX] if mp is None else mp
    pb.memory[TAP_CD] = pb.memory[WARD_CD] = pb.memory[WARD_TICKS] = 0
    pb.memory[CURE_USED] = 0   # a fresh room for Cure's once-per-room rule
    pb.memory[PSTATUS] = 0
    # A distant durable body keeps the room's clear reward (MP refund) away.
    entity(pb, 31, 2, 150, 8, hp=200)
    pb.memory[slot(31) + 1] = 0x03   # off screen: no spell targets it


def tap(pb, aim="right", held=3):
    pb.button_press(aim)
    pb.tick(2)
    pb.button_press("b")
    pb.tick(held)
    pb.button_release("b")
    pb.tick(1)
    pb.button_release(aim)
    pb.tick(3)   # input is sampled a frame late; the cast lands on release


def hold(pb, frames=HOLD_FRAMES + 6):
    pb.button_press("b")
    for _ in range(frames):
        pb.tick()
    charged = pb.memory[HOLD]
    pb.button_release("b")
    pb.tick(4)
    return charged


def chord(pb, b_first):
    first, second = ("b", "a") if b_first else ("a", "b")
    pb.button_press(first)
    pb.tick(2)
    pb.button_press(second)
    pb.tick(5)
    pb.button_release(second)
    pb.tick(2)
    pb.button_release(first)
    pb.tick(8)


def check_inputs(pb, c):
    name = HEROES[c]
    assert pb.memory[PLAYER + PL_ITEM] >= 10, f"{name} hero power not selected"

    # Tap: attack spell, 1 MP.
    arena(pb)
    mp, casts = pb.memory[PLAYER + PL_MP], pb.memory[CASTS]
    tap(pb)
    assert pb.memory[LAST] == c * 2, f"{name} tap cast {pb.memory[LAST]}"
    assert pb.memory[CASTS] == (casts + 1) & 0xFF
    assert pb.memory[PLAYER + PL_MP] == mp - 1, f"{name} tap did not cost 1 MP"
    assert pb.memory[PLAYER + PL_ACTIVE_CHARGE] == 0, "spell locked A+B"

    # Hold: ward, its own cost; the charge tell reached the threshold.
    arena(pb)
    pb.memory[PLAYER + PL_HP] = pb.memory[PLAYER + PL_HP_MAX] - 2   # Cure
    mp, casts = pb.memory[PLAYER + PL_MP], pb.memory[CASTS]
    charged = hold(pb)
    assert charged >= HOLD_FRAMES, f"{name} hold only reached {charged}"
    assert pb.memory[LAST] == c * 2 + 1, f"{name} hold cast {pb.memory[LAST]}"
    assert pb.memory[PLAYER + PL_MP] == mp - WARD_COST[c], f"{name} ward cost"

    # Too little MP: refusal, nothing spent.
    arena(pb, mp=0)
    casts = pb.memory[CASTS]
    tap(pb)
    assert pb.memory[CASTS] == casts and pb.memory[PLAYER + PL_MP] == 0
    arena(pb, mp=1)
    pb.memory[PLAYER + PL_HP] = pb.memory[PLAYER + PL_HP_MAX] - 2
    hold(pb)
    assert pb.memory[CASTS] == casts and pb.memory[PLAYER + PL_MP] == 1, (
        f"{name} ward cast without MP: casts {pb.memory[CASTS]} vs {casts}, "
        f"mp {pb.memory[PLAYER + PL_MP]}")

    # A+B in both orders is the special, never a spell. Below full MP it is
    # the Oath (Shard Wake known from the start), at full MP Convergence.
    for b_first in (True, False):
        arena(pb, mp=pb.memory[PLAYER + PL_MP_MAX] - 1)
        pb.memory[RUN + RS_BOSSES] = 0
        mp, casts = pb.memory[PLAYER + PL_MP], pb.memory[CASTS]
        chord(pb, b_first)
        assert pb.memory[CASTS] == casts, f"{name} A+B cast a spell"
        assert pb.memory[PLAYER + PL_MP] == mp - 1, (
            f"{name} A+B (b_first={b_first}) did not run the Oath")
        assert pb.memory[PLAYER + PL_ACTIVE_CHARGE] > 0
    arena(pb)
    casts = pb.memory[CASTS]
    chord(pb, True)
    assert pb.memory[CASTS] == casts
    assert pb.memory[PLAYER + PL_MP] == 0, f"{name} full-MP A+B not Convergence"


def run_until(pb, frames, cond):
    for _ in range(frames):
        pb.tick()
        if cond():
            return True
    return False


def check_spells(pb, c):
    m = pb.memory
    if c == 0:
        # Moonfire homes onto an off-axis body and burns it.
        arena(pb)
        foe = entity(pb, 0, 2, 124, 30)
        tap(pb)
        turned = run_until(pb, 70, lambda: any(
            m[slot(i)] == 1 and m[slot(i) + 1] & 0x10 and signed(m[slot(i) + 11]) < 0
            for i in range(31)))
        assert turned, "Moonfire did not turn toward the body"
        assert run_until(pb, 70, lambda: m[foe + 14] < 40), "Moonfire missed"
        pb.tick(2)
        assert m[ESTATUS] == ST_BURN, f"Moonfire status {m[ESTATUS]}"
        # Flame Ward erases a hostile shot flying at the hero.
        arena(pb)
        shot = entity(pb, 0, 1, 140, 64, hp=1, vx=-1)
        casts = m[CASTS]
        charged = hold(pb)
        assert m[CASTS] == (casts + 1) & 0xFF, (
            f"Flame Ward not cast: hold {charged} mp {m[PLAYER + PL_MP]} "
            f"last {m[LAST]} cd {m[WARD_CD]}")
        run_until(pb, 90, lambda: not (m[shot + 1] & 1))
        assert not (m[shot + 1] & 1), "Flame Ward did not eat the shot"
    elif c == 1:
        # Thunder: sure strike + stun, then a chain that slows a neighbour.
        arena(pb)
        foe = entity(pb, 0, 2, 120, 64)
        near = entity(pb, 1, 2, 136, 80)
        tap(pb)
        assert run_until(pb, 14, lambda: m[foe + 14] < 40), "Thunder missed"
        assert m[ESTATUS] == ST_STOP, f"Thunder status {m[ESTATUS]}"
        assert run_until(pb, 20, lambda: m[near + 14] < 40), "Thunder no chain"
        assert m[ESTATUS + 1] == ST_SLOW
        # Stoneskin raises the shot/body shield.
        arena(pb)
        hold(pb)
        assert m[PLAYER + PL_SHIELD] > 0, "Stoneskin raised no shield"
    elif c == 2:
        # Hex: the struck body is confused, its neighbour takes the burst.
        arena(pb)
        foe = entity(pb, 0, 2, 112, 64)
        tap(pb)
        assert run_until(pb, 50, lambda: m[foe + 14] < 40), "Hex missed"
        pb.tick(2)
        assert m[ESTATUS] == ST_CONFUSION, f"Hex status {m[ESTATUS]}"
        # Shadow Veil hastes the hero.
        arena(pb)
        hold(pb)
        assert m[PSTATUS] == ST_HASTE, f"Veil status {m[PSTATUS]}"
    elif c == 3:
        # Blizzard follows a held D-pad and freezes what it hits.
        arena(pb)
        tap(pb)
        pb.button_press("up")
        steered = run_until(pb, 24, lambda: any(
            m[slot(i)] == 1 and m[slot(i) + 1] & 0x10 and signed(m[slot(i) + 11]) < 0
            for i in range(31)))
        pb.button_release("up")
        assert steered, "Blizzard ignored the D-pad"
        arena(pb)
        foe = entity(pb, 0, 2, 112, 64)
        tap(pb)
        assert run_until(pb, 30, lambda: m[foe + 14] < 40), "Blizzard missed"
        pb.tick(2)
        assert m[ESTATUS] == ST_STOP, f"Blizzard status {m[ESTATUS]}"
        # Cure heals one heart, once per room.
        arena(pb)
        m[PLAYER + PL_HP] = m[PLAYER + PL_HP_MAX] - 3
        hp = m[PLAYER + PL_HP]
        hold(pb)
        assert m[PLAYER + PL_HP] == hp + 2 and m[CURE_USED] == 1, "Cure"
        m[WARD_CD] = 0
        mp = m[PLAYER + PL_MP]
        hold(pb)
        assert m[PLAYER + PL_MP] == mp and m[PLAYER + PL_HP] == hp + 2, (
            "Cure cast twice in one room")
    else:
        # Bramble poisons each body along the line once.
        arena(pb)
        a = entity(pb, 0, 2, 98, 64)
        b = entity(pb, 1, 2, 126, 64)
        tap(pb)
        pb.tick(30)
        for i, e in ((0, a), (1, b)):
            loss = 40 - m[e + 14]
            assert 1 <= loss <= 9, f"Bramble body {i} lost {loss}"
            assert m[ESTATUS + i] == ST_POISON, f"Bramble status {m[ESTATUS + i]}"
        # Thorn Mirror turns a hostile shot into her own.
        arena(pb)
        shot = entity(pb, 0, 1, 96, 64, hp=1, vx=-1)
        hold(pb)
        assert run_until(pb, 40, lambda: m[shot + 1] & 0x10), "no reflection"
        assert signed(m[shot + 10]) > 0


def player_projectiles(pb):
    return sum(1 for i in range(32)
               if pb.memory[slot(i)] == 1 and pb.memory[slot(i) + 1] & 0x11 == 0x11)


def check_wolfkin_claw(pb):
    """Wolfkin's A is a contact claw: an arm-length arc, never a shot."""
    m = pb.memory
    arena(pb)
    m[PLAYER + 8] = 0                       # no LCK crit noise
    near = entity(pb, 0, 2, 92, 64, enemy_id=3)   # light Skeleton, ~6 px out
    far = entity(pb, 1, 2, 120, 64)         # 40 px: out of claw reach
    x0 = get16(pb, near + 3)
    hero_x = get16(pb, PLAYER + PL_X)
    far_x, reach, life = x0, 0, 0
    pb.button_press("right")
    pb.button_press("a")
    for f in range(20):
        if f == 5:
            pb.button_release("a")
            pb.button_release("right")
        pb.tick()
        far_x = max(far_x, get16(pb, near + 3))
        live = [slot(i) for i in range(31)
                if m[slot(i)] == 1 and m[slot(i) + 1] & 0x11 == 0x11]
        if live:
            life += 1
        for e in live:
            reach = max(reach, get16(pb, e + 3) + (m[e + 25] >> 4) - hero_x)
    loss = 40 - m[near + 14]
    assert loss >= 5, f"claw dealt {loss}"
    assert m[far + 14] == 40, "claw reached a body 40 px away"
    assert reach <= 32, f"claw hitbox reached {reach} px: a ranged shot"
    assert life <= 8, f"claw lived {life} frames"
    assert far_x >= x0 + 3, f"claw knockback only {far_x - x0} px"
    print(f"[magic] Wolfkin claw: {loss} dmg, reach {reach} px, "
          f"{life} f, knockback {far_x - x0} px")


def main():
    for c, name in enumerate(HEROES):
        pb = boot(c)
        check_inputs(pb, c)
        check_spells(pb, c)
        if c == 0:
            check_wolfkin_claw(pb)
        pb.stop(save=False)
        print(f"[magic] {name}: {SPELLS[c * 2]} / {SPELLS[c * 2 + 1]} / A+B ok")
    print("[magic] PASS tap spell, hold ward and A+B for all five heroes")


if __name__ == "__main__":
    main()
