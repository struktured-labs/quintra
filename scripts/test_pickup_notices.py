#!/usr/bin/env python3
"""Live-ROM: every pickup names what it did (or why it stayed) on the HUD.

Loops over floor relics, Pack tools, hearts, wisps, coins, the Antidote, the
weapon orb, every merchant ware and the town elder. Each case spawns the
pickup on the champion and records the sequence of six-cell HUD notices that
follows, then checks it against the expected words. It also checks that a
pickup notice holds for HUD_NOTICE_FRAMES + 60 (105) frames.
"""

from test_performance import EN, PL, addr, boot_room, put32

WIN = 0x9C00
VBK = 0xFF4F
TICKS = addr("_hud_notice_ticks")

G = {
    " ": 8, "+": 95, "-": 67, "h": 4, "$": 7,
    "R": 76, "I": 77, "F": 78, "T": 79, "W": 80, "L": 81, "D": 82, "V": 83,
    "A": 84, "G": 85, "E": 86, "M": 87, "K": 88, "O": 89, "P": 90, "N": 91,
    "H": 92, "S": 93, "C": 94, "B": 64, "U": 65, "X": 66,
}
for d in range(10):
    G[str(d)] = 9 + d
TILE_TO_CH = {v: k for k, v in G.items()}

# player_state_t offsets
HPMAX, HP, MPMAX, MP, ATK, DEF, SPD, LCK = 1, 2, 3, 4, 5, 6, 7, 8
COINS, WEAPON, INV, CURSE = 16, 21, 24, 46

PICKUP_HEART_HALF, PICKUP_COIN_1, PICKUP_ITEM, PICKUP_SHOP = 0, 1, 3, 4
PICKUP_WEAPON, PICKUP_MP, PICKUP_VILLAGER, PICKUP_ANTIDOTE = 5, 6, 7, 26


def text(s):
    """Centered six-cell row exactly as hud_notice draws it."""
    w = len(s)
    pad = (6 - w) >> 1
    s = " " * pad + s
    return s + " " * (6 - len(s))


def hud_text(pb):
    return "".join(TILE_TO_CH.get(pb.memory[WIN + x], "?")
                   for x in range(10, 16))


def clear_entities(pb):
    for i in range(32):
        pb.memory[EN + i * 28] = 0
        pb.memory[EN + i * 28 + 1] = 0


def wait_quiet(pb, limit=1500):
    for _ in range(limit):
        if pb.memory[TICKS] == 0:
            return
        pb.tick()
    raise AssertionError("HUD notice queue never drained")


def prep(pb, **kw):
    wait_quiet(pb)
    clear_entities(pb)
    st = dict(hpmax=10, hp=10, mpmax=5, mp=5, atk=4, def_=2, spd=5, lck=2,
              coins=99, curse=0)
    st.update(kw)
    m = pb.memory
    m[PL + HPMAX], m[PL + HP] = st["hpmax"], st["hp"]
    m[PL + MPMAX], m[PL + MP] = st["mpmax"], st["mp"]
    m[PL + ATK], m[PL + DEF] = st["atk"], st["def_"]
    m[PL + SPD], m[PL + LCK] = st["spd"], st["lck"]
    m[PL + COINS], m[PL + COINS + 1] = st["coins"] & 0xFF, st["coins"] >> 8
    m[PL + CURSE] = st["curse"]
    inv = st.get("inv", [])
    for i in range(16):
        m[PL + INV + i] = inv[i] if i < len(inv) else 0xFF


def spawn_on_player(pb, kind, a1=0, a2=0, a3=0, tile=35, pal=5):
    ep = EN
    m = pb.memory
    px = m[PL + 9] | (m[PL + 10] << 8)
    py = m[PL + 11] | (m[PL + 12] << 8)
    for k in range(28):
        m[ep + k] = 0
    m[ep] = 3
    m[ep + 1] = 0x03
    put32(pb, ep + 2, px << 8)
    put32(pb, ep + 6, py << 8)
    m[ep + 12] = tile
    m[ep + 13] = pal
    m[ep + 14] = 1
    m[ep + 16] = 200
    m[ep + 17] = kind
    m[ep + 18] = a1
    m[ep + 19] = a2
    m[ep + 20] = a3
    m[ep + 24] = 0x40   # visit-persist: no 4 s expiry mid-check
    m[ep + 25] = 0x66
    m[ep + 27] = 1
    return ep


def mem_is(off, val):
    def check(pb):
        got = pb.memory[PL + off]
        assert got == val, f"player+{off} = {got}, want {val}"
    return check


def alive(pb):
    return bool(pb.memory[EN + 1] & 1) and pb.memory[EN] == 3


def record(pb, frames=700):
    """Distinct notices shown, in order, until the queue drains."""
    seen = []
    last_ticks = 0
    for _ in range(frames):
        pb.tick()
        t = pb.memory[TICKS]
        if t > last_ticks:          # a notice (re)started this frame
            seen.append(hud_text(pb))
        last_ticks = t
        if not t and seen:
            # Contact pickups that stay may re-show after the cadence; one
            # pass is enough for the check.
            break
    return seen


def case(pb, name, expect, kind, a1=0, a2=0, a3=0, stays=False,
         check=None, **state):
    prep(pb, **state)
    spawn_on_player(pb, kind, a1, a2, a3)
    seen = record(pb)
    want = [text(w) for w in expect]
    assert seen[:len(want)] == want, f"{name}: saw {seen}, want {want}"
    if stays is not None:
        assert alive(pb) == stays, f"{name}: alive={alive(pb)} want {stays}"
    if check:
        check(pb)
    # Leave the champion's tile clear of a refused pickup for the next case.
    clear_entities(pb)
    return name, " / ".join(expect)


def main():
    pb = boot_room()
    rows = []
    try:
        m = pb.memory
        # Duration: a pickup card holds 45 + 60 frames.
        prep(pb)
        spawn_on_player(pb, PICKUP_ITEM, 12)
        pb.tick()
        start = m[TICKS]
        assert start in (104, 105), f"pickup notice ticks {start}, want 105"
        assert hud_text(pb) == text("ATK+1")
        for _ in range(100):
            pb.tick()
        assert hud_text(pb) == text("ATK+1"), "ATK+1 left before 100 frames"
        for _ in range(8):
            pb.tick()
        assert m[TICKS] == 0 and hud_text(pb) != text("ATK+1")
        wait_quiet(pb)

        # Regression (Stage 1 white heart): a refused floor relic must keep
        # explaining itself on every touch, not once per lifetime.
        prep(pb, hpmax=16, hp=16)
        ep = spawn_on_player(pb, PICKUP_ITEM, 10)
        first = record(pb)
        assert first[:1] == [text("hMAX")], first
        px = m[PL + 9] | (m[PL + 10] << 8)
        put32(pb, ep + 2, (px + 40) << 8)        # step away
        for _ in range(10):
            pb.tick()
        put32(pb, ep + 2, px << 8)               # and touch it again
        again = record(pb)
        assert again[:1] == [text("hMAX")], f"second touch was silent: {again}"
        assert alive(pb)
        clear_entities(pb)

        I = PICKUP_ITEM
        rows += [
            case(pb, "Iron Heart", ["MAXh+2"], I, 10,
                 check=mem_is(HPMAX, 12)),
            case(pb, "Iron Heart at cap, hurt", ["hMAX", "HEAL+2"], I, 10,
                 hpmax=16, hp=10, check=mem_is(HP, 12)),
            case(pb, "Iron Heart at cap, full", ["hMAX"], I, 10, stays=True,
                 hpmax=16, hp=16),
            case(pb, "Speed Ring", ["SPD+1"], I, 11),
            # PLAYER_SPD_MAX is 12 (#98): 9 is no longer a cap.
            case(pb, "Speed Ring at 9", ["SPD+1"], I, 11, spd=9,
                 check=mem_is(SPD, 10)),
            case(pb, "Speed Ring at cap", ["SPDMAX"], I, 11, stays=True,
                 spd=12),
            case(pb, "Power Stone", ["ATK+1"], I, 12),
            case(pb, "Power Stone at cap", ["ATKMAX"], I, 12, stays=True,
                 atk=15),
            case(pb, "Tough Skin", ["DEF+1"], I, 13),
            case(pb, "Lucky Coin", ["LCK+2"], I, 14),
            case(pb, "Mana Gem", ["MP+2"], I, 15),
            case(pb, "Ward Charm", ["DEF+1", "LCK+1", "WARD"], I, 16),
            case(pb, "Swift Fang, ATK capped", ["SPD+1", "ATKMAX"], I, 17,
                 atk=15),
            case(pb, "Hunter's Eye", ["LCK+3"], I, 18),
            case(pb, "Vampiric Sigil", ["ATK+1", "MAXh+1", "VAMP"], I, 19),
            case(pb, "Rift Bomb", ["BURST"], I, 22),
            case(pb, "Echo Chime", ["CHIME"], I, 23),
            case(pb, "Mirror Shard", ["MIRROR"], I, 24),
            case(pb, "Blast Seed", ["BLAST"], I, 25),
            case(pb, "Rift Lens", ["BEAM"], I, 26),
            case(pb, "Pack tool, Pack full", ["NOROOM"], I, 22, stays=True,
                 inv=[40] * 16),
            case(pb, "Half heart", ["HEAL+1"], PICKUP_HEART_HALF, hp=4),
            case(pb, "Half heart, full HP", ["HPFULL"], PICKUP_HEART_HALF,
                 stays=True),
            case(pb, "Half heart, Hunger", ["HUNGER", "NOHEAL"],
                 PICKUP_HEART_HALF, stays=True, hp=4, curse=0x08),
            case(pb, "Half heart, Moon Flask", ["MANA+1"], PICKUP_HEART_HALF,
                 mp=2, inv=[38]),
            case(pb, "MP wisp", ["MANA+1"], PICKUP_MP, mp=2),
            case(pb, "MP wisp, full", ["MPFULL"], PICKUP_MP, stays=True),
            case(pb, "Coin, purse full", ["$MAX"], PICKUP_COIN_1, stays=True,
                 coins=999),
            case(pb, "Antidote", ["CURE+1"], PICKUP_ANTIDOTE),
            case(pb, "Antidote, pouch full", ["NOROOM"], PICKUP_ANTIDOTE,
                 stays=True, inv=[49, 49, 49]),
            case(pb, "Weapon orb, no A", ["A SWAP"], PICKUP_WEAPON, 21,
                 stays=True),
            case(pb, "Town elder", ["HEALED", "REGEN"], PICKUP_VILLAGER,
                 stays=True, hp=4),
        ]
        S = PICKUP_SHOP
        rows += [
            case(pb, "Ware: heart", ["HEAL+2"], S, 0, 10, hp=4),
            case(pb, "Ware: Iron Heart", ["MAXh+2"], S, 2, 40),
            case(pb, "Ware: Power Stone", ["ATK+1"], S, 3, 30),
            case(pb, "Ware: Mana Gem", ["MP+2"], S, 4, 30),
            case(pb, "Ware: Vampiric Sigil", ["ATK+1", "MAXh+1", "VAMP"],
                 S, 6, 35),
            case(pb, "Ware: Chart", ["CHART"], S, 7, 15),
            case(pb, "Ware: Glass Fang", ["ATK+2", "SPD+1", "MAXh-2"],
                 S, 9, 20),
            case(pb, "Ware: Phoenix Thread", ["REVIVE"], S, 10, 35),
            case(pb, "Ware: Echo Prism", ["FORK"], S, 12, 30),
            case(pb, "Ware: Ricochet Rune", ["BOUNCE"], S, 13, 28),
            case(pb, "Ware: Thorn Crown", ["THORNS"], S, 14, 35),
            case(pb, "Ware: War Drum", ["DRUM"], S, 15, 28),
            case(pb, "Ware: Moon Flask", ["FLASK"], S, 16, 20),
            case(pb, "Ware: Blast Seed", ["BLAST"], S, 17, 32),
            # The Antidote shelf restocks: the vial stays on the counter.
            case(pb, "Ware: Antidote", ["CURE+1"], S, 22, 12, stays=True),
            case(pb, "Ware: too dear", ["NEED35"], S, 10, 35, stays=True,
                 coins=5),
            case(pb, "Ware: already owned", ["OWNED"], S, 10, 35,
                 stays=True, inv=[33]),
            case(pb, "Ware: heart at full HP", ["HPFULL"], S, 0, 10,
                 stays=True),
        ]
    finally:
        pb.stop(save=False)

    for name, words in rows:
        print(f"  {name:28s} {words}")
    print(f"[pickup-notices] PASS {len(rows)} pickup cases name their effect; "
          "pickup notices hold 105 frames")


if __name__ == "__main__":
    main()
