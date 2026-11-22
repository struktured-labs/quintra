#!/usr/bin/env python3
"""ROM contracts for Wolfkin's Claw Sword: 360-degree spin, stab, beam, and
its reserved bank-1 OBJ tiles (144..159)."""
import os
from pathlib import Path

from pyboy import PyBoy

from test_will_max import (
    PLAYER, ENTITIES, TILEMAP, ENTITY_SIZE, boot, clear_arena, put16, addr,
)

QSTATUS = None  # unused; keep imports tight

AUX_FANG = 0xF1
AUX_BEAM = 0xEE
AUX_PU = 0xED
POWERUP_ID = None


def powerup_addr():
    global POWERUP_ID
    if POWERUP_ID is None:
        POWERUP_ID = addr("_powerup_id")
    return POWERUP_ID


def shots(pb, aux=None):
    out = []
    for i in range(32):
        e = ENTITIES + i * ENTITY_SIZE
        if pb.memory[e] == 1 and (pb.memory[e + 1] & 0x10):
            if aux is None or pb.memory[e + 23] == aux:  # ai_data[6] at +17+6?
                out.append(e)
    return out


def ent_off(field):
    # type0 flags1 x_frac2 x@3 (i16) x_pad5 y_frac6 y@7 (i16) y_pad9
    # vx10 vy11 tile12 pal13 hp14 state15 timer16 ai_data[8] 17..24
    # hitbox25 damage26 oam27
    return {
        "x": 3, "y": 7, "vx": 10, "vy": 11, "tile": 12, "hp": 14,
        "state": 15, "timer": 16, "ai0": 17, "ai5": 22, "ai6": 23,
        "hitbox": 25, "damage": 26,
    }[field]


def get16(pb, a):
    return pb.memory[a] | (pb.memory[a + 1] << 8)


def signed16(v):
    return v if v < 0x8000 else v - 0x10000


def player_xy(pb):
    return signed16(get16(pb, PLAYER + 9)), signed16(get16(pb, PLAYER + 11))


def drop_hp(pb, full=False):
    hp_max = pb.memory[PLAYER + 1]
    pb.memory[PLAYER + 2] = hp_max if full else max(1, hp_max - 1)


def fire_a(pb, direction=None, ticks=4):
    pb.memory[PLAYER + 22] = 0  # cooldown
    if direction:
        pb.button_press(direction)
    pb.button_press("a")
    pb.tick(ticks)
    pb.button_release("a")
    if direction:
        pb.button_release(direction)
    pb.tick(1)


def spawn_foe(pb, x, y, hp=20, eid=2):
    # first free slot that isn't a live projectile we'll overwrite carefully
    for i in range(32):
        e = ENTITIES + i * ENTITY_SIZE
        if pb.memory[e] == 0:
            break
    else:
        raise AssertionError("no free entity")
    for k in range(ENTITY_SIZE):
        pb.memory[e + k] = 0
    pb.memory[e] = 2          # ENT_ENEMY
    pb.memory[e + 1] = 0x07   # active, alive, on-screen
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 14] = hp
    pb.memory[e + 17] = eid   # ai_data[0] enemy id (Hornet: 2, not fire-weak)
    pb.memory[e + 25] = 0x88
    pb.memory[e + 26] = 1
    return e


def pin_spots(pb, foes):
    return [(e, get16(pb, e + 3), get16(pb, e + 7)) for e in foes]


def tick_pinned(pb, frames, foes, spots=None):
    """Advance while holding test bodies still, so AI drift can't decide reach."""
    if spots is None:
        spots = pin_spots(pb, foes)
    for _ in range(frames):
        for e, x, y in spots:
            put16(pb, e + 3, x)
            put16(pb, e + 7, y)
        pb.tick(1)


def test_slash_diagonal_and_parented():
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        px, py = player_xy(pb)
        # Diagonal enemy in the front-right arc (facing defaults south? set facing E)
        pb.memory[PLAYER + 13] = 1  # FACE_E
        # Also set aim east so slash covers E + NE + SE
        # player_aim_dir may live elsewhere; pad-less slash uses facing in classic
        # or aim dir in hold-aim (default on). Poke aim if the symbol exists.
        try:
            aim = addr("_player_aim_dir")
            pb.memory[aim] = 2  # east
        except RuntimeError:
            pass
        foe = spawn_foe(pb, px + 24, py - 10, hp=20)
        fire_a(pb, direction=None, ticks=5)
        melees = shots(pb)  # after 5 ticks still alive
        # No traveling melee: every fang segment has vx=vy=0
        fangs = [e for e in melees if pb.memory[e + ent_off("ai6")] == AUX_FANG]
        beams = [e for e in melees if pb.memory[e + ent_off("ai6")] == AUX_BEAM]
        assert not beams, "beam fired below full hearts"
        assert fangs, "slash spawned no sword segments"
        for e in fangs:
            assert pb.memory[e + ent_off("vx")] == 0, "slash segment has velocity"
            assert pb.memory[e + ent_off("vy")] == 0, "slash segment has velocity"
        # Let the spin pass the NE heading
        pb.tick(20)
        hp = pb.memory[foe + 14]
        assert hp == 15, f"spin did not deal 5 to a diagonal body (hp {hp})"
    finally:
        pb.stop(save=False)


def test_stab_reach_and_damage():
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        px, py = player_xy(pb)
        pb.memory[PLAYER + 13] = 1  # FACE_E
        try:
            pb.memory[addr("_player_aim_dir")] = 2
        except RuntimeError:
            pass
        # Close body: both slash and stab should reach (~16-22 px past edge).
        close = spawn_foe(pb, px + 28, py + 4, hp=20)
        fire_a(pb, direction="right", ticks=6)
        pb.tick(4)
        close_hp = pb.memory[close + 14]
        assert close_hp == 11, f"stab close damage not 9 (hp {close_hp})"
        # Far body: ~32 px past the east body edge (player.x+16+32 = +48),
        # place at +44 so the tip box overlaps and a 22 px slash would miss.
        clear_arena(pb)
        drop_hp(pb, full=False)
        px, py = player_xy(pb)
        pb.memory[PLAYER + 13] = 1
        try:
            pb.memory[addr("_player_aim_dir")] = 2
        except RuntimeError:
            pass
        far = spawn_foe(pb, px + 44, py + 4, hp=20)
        # First prove a slash does not reach
        spots = pin_spots(pb, [far])
        pb.memory[PLAYER + 22] = 0
        pb.button_press("a")
        tick_pinned(pb, 2, [far], spots)
        pb.button_release("a")
        tick_pinned(pb, 26, [far], spots)
        # The slot can inherit the close body's 1-HP bleed tick; a spin hit is 5.
        spun = pb.memory[far + 14]
        assert spun >= 19, f"spin reached the stab-only lane (hp {spun})"
        pb.memory[PLAYER + 22] = 0
        fire_a(pb, direction="right", ticks=6)
        pb.tick(6)
        far_hp = pb.memory[far + 14]
        assert spun - far_hp in (9, 10), (
            f"stab did not reach/deal 9 at 32px (hp {spun} -> {far_hp})")
    finally:
        pb.stop(save=False)


def test_beam_only_at_full_hearts_and_no_double_hit():
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        fire_a(pb, direction="right", ticks=3)
        beams = [e for e in shots(pb) if pb.memory[e + ent_off("ai6")] == AUX_BEAM]
        assert not beams, "beam fired at hp_max-1"
        clear_arena(pb)
        drop_hp(pb, full=True)
        px, py = player_xy(pb)
        pb.memory[PLAYER + 13] = 1
        try:
            pb.memory[addr("_player_aim_dir")] = 2
        except RuntimeError:
            pass
        # Place a body on the stab lane, close enough for blade + beam overlap.
        foe = spawn_foe(pb, px + 28, py + 4, hp=20)
        fire_a(pb, direction="right", ticks=4)
        beams = [e for e in shots(pb) if pb.memory[e + ent_off("ai6")] == AUX_BEAM]
        assert beams, "no sword beam at full hearts"
        assert pb.memory[beams[0] + ent_off("damage")] == 3, "beam damage is not 3"
        # Wait for the swing to resolve. Shared latch: 9 from stab, not 9+3.
        pb.tick(10)
        hp = pb.memory[foe + 14]
        assert hp == 11, f"blade+beam double-hit or missed (hp {hp}, want 11)"
    finally:
        pb.stop(save=False)


def test_formation_grants_projectiles():
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        pb.memory[powerup_addr()] = 4  # POWERUP_FORMATION
        fire_a(pb, direction="right", ticks=3)
        pus = [e for e in shots(pb) if pb.memory[e + ent_off("ai6")] == AUX_PU]
        assert len(pus) >= 2, f"Formation did not grant beams ({len(pus)})"
        for e in pus:
            assert pb.memory[e + ent_off("damage")] == 2
            vx = pb.memory[e + ent_off("vx")]
            vy = pb.memory[e + ent_off("vy")]
            if vx >= 128:
                vx -= 256
            if vy >= 128:
                vy -= 256
            assert vx or vy, "power-up beam is stationary"
    finally:
        pb.stop(save=False)


SLASH_REACH = 22
STAB_REACH = 32
# Allow 2 px of placement rounding; the old thrown Fang Claw peaked at ~14.
REACH_SLACK = 2


def fang_segs(pb):
    return [e for e in shots(pb) if pb.memory[e + ent_off("ai6")] == AUX_FANG]


def peak_sprite_reach_east(pb, px):
    """Farthest visible sword pixel past the east body edge (player.x+16)."""
    edge = px + 16
    best = -999
    for e in fang_segs(pb):
        x = signed16(get16(pb, e + ent_off("x")))
        w = pb.memory[e + ent_off("hitbox")] >> 4
        vis = max(8, w)
        dist = (x + vis) - edge
        if dist > best:
            best = dist
    return best


def face_east(pb):
    pb.memory[PLAYER + 13] = 1  # FACE_E
    try:
        pb.memory[addr("_player_aim_dir")] = 2  # dir8 east
    except RuntimeError:
        pass


def test_sword_sprite_reach():
    """The blade sprite itself must reach the spec distances, not just the hitbox."""
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        px, _ = player_xy(pb)
        face_east(pb)
        fire_a(pb, direction=None, ticks=1)
        slash_peak = peak_sprite_reach_east(pb, px)
        for _ in range(22):
            pb.tick(1)
            slash_peak = max(slash_peak, peak_sprite_reach_east(pb, px))
        assert slash_peak >= SLASH_REACH - REACH_SLACK, (
            f"slash sprite only reached {slash_peak}px past the body "
            f"(want {SLASH_REACH})"
        )
        clear_arena(pb)
        drop_hp(pb, full=False)
        px, _ = player_xy(pb)
        face_east(pb)
        fire_a(pb, direction="right", ticks=1)
        # Use the current body edge each frame: the blade is parented, so a
        # one-frame walk during the hold must not shrink measured reach.
        stab_peak = -999
        for _ in range(10):
            cx, _ = player_xy(pb)
            stab_peak = max(stab_peak, peak_sprite_reach_east(pb, cx))
            pb.tick(1)
        assert stab_peak >= STAB_REACH - REACH_SLACK, (
            f"stab sprite only reached {stab_peak}px past the body "
            f"(want {STAB_REACH})"
        )
        # And it must clearly beat the old 14 px thrown sprite.
        assert stab_peak > slash_peak, (
            f"stab reach {stab_peak} should exceed slash {slash_peak}"
        )
    finally:
        pb.stop(save=False)


def test_attract_sword_sprite_reach():
    """The Wolfkin attract demo must show the same long blade, not Fang Claw."""
    os.environ["QUINTRA_KEEP_INTRO"] = "1"
    # Local imports: test_will_max boots with the intro muted.
    from test_will_max import ROM, NOI
    import re

    def sym(name):
        return int(re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI).group(1), 16)

    scr, cnt, demo, mute = map(sym, (
        "_loop_current_screen", "_loop_frame_counter",
        "_attract_demo", "_attract_mute",
    ))
    pb = PyBoy(str(ROM), window="null", cgb=True, sound_emulated=False)
    m = pb.memory

    def loop_cnt():
        return m[cnt] | (m[cnt + 1] << 8)

    try:
        for _ in range(400):
            pb.tick()
            if m[scr] == 4 and loop_cnt() > 4:
                break
        assert m[scr] == 4, f"intro did not start (screen {m[scr]})"
        pb.button_press("start")
        pb.tick(4)
        pb.button_release("start")
        pb.tick(2)
        for _ in range(40):
            pb.tick()
            if m[scr] == 1:
                break
        assert m[scr] == 1 and m[mute] == 0, (
            f"skip did not reach a live title (screen {m[scr]} mute {m[mute]})"
        )
        started = False
        for _ in range(720 + 200):
            pb.tick()
            if m[demo] == 1:
                started = True
                break
        assert started, "Wolfkin attract demo did not start"
        for _ in range(400):
            pb.tick()
            if m[scr] == 5:
                break
        peak = -999
        for _ in range(700):
            if not m[demo] or m[scr] != 5:
                if not m[demo]:
                    break
                pb.tick()
                continue
            if fang_segs(pb):
                cx, _ = player_xy(pb)
                # Attract facing varies; measure the max axis from the body box.
                px, py = cx, signed16(get16(pb, PLAYER + 11))
                for e in fang_segs(pb):
                    x = signed16(get16(pb, e + ent_off("x")))
                    y = signed16(get16(pb, e + ent_off("y")))
                    w = max(8, pb.memory[e + ent_off("hitbox")] >> 4)
                    h = max(8, pb.memory[e + ent_off("hitbox")] & 0x0F)
                    # Distance of the far sprite edge from the nearest body edge
                    # in the direction the segment sits.
                    if x + w / 2 >= px + 8:
                        dist = (x + w) - (px + 16)
                    else:
                        dist = px - x
                    if y + h / 2 >= py + 8:
                        dist_y = (y + h) - (py + 16)
                    else:
                        dist_y = py - y
                    peak = max(peak, dist, dist_y)
            pb.tick()
        # Slash is 22 px; a demo that only slashes still has to beat Fang Claw.
        assert peak >= SLASH_REACH - REACH_SLACK, (
            f"attract Wolfkin sword sprite only reached {peak}px past the body "
            f"(want at least slash {SLASH_REACH})"
        )
    finally:
        pb.stop(save=False)
        os.environ.pop("QUINTRA_KEEP_INTRO", None)


SWORD_BASE = 144
SPIN_LIFE = 21
SPIN_DMG = 5


def sword_art():
    """The 256 tile bytes the ROM must hold at bank-1 OBJ 144..159."""
    src = (Path(__file__).resolve().parent.parent
           / "src/game/wolfkin_sword_art.c").read_text()
    body = src.split("wolfkin_sword_tiles[256] = {", 1)[1].split("};", 1)[0]
    vals = [int(v, 16) for v in body.replace("\n", " ").split(",") if v.strip()]
    assert len(vals) == 256, len(vals)
    return bytes(vals)


def sword_vram(pb):
    return bytes(pb.memory[1, 0x8000 + SWORD_BASE * 16 + i] for i in range(256))


def test_spin_hits_all_eight_sides_once():
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        face_east(pb)
        px, py = player_xy(pb)
        cx, cy = px + 8, py + 8
        foes = []
        # Body centres ~20 px past the body edge on cardinals, ~26 px out on
        # diagonals; 8x8 boxes, so top-left = centre - 4.
        for dx, dy in ((0, -1), (1, -1), (1, 0), (1, 1),
                       (0, 1), (-1, 1), (-1, 0), (-1, -1)):
            r = 28 if (dx == 0 or dy == 0) else 19
            foes.append(spawn_foe(pb, cx + dx * r - 4, cy + dy * r - 4, hp=20))
        far = spawn_foe(pb, cx + 48 - 4, cy - 4, hp=20)
        spots = pin_spots(pb, foes + [far])
        pb.memory[PLAYER + 22] = 0
        pb.button_press("a")
        tick_pinned(pb, 1, foes, spots)
        pb.button_release("a")
        tick_pinned(pb, 1, foes, spots)
        cd = pb.memory[PLAYER + 22]
        assert cd >= SPIN_LIFE + 1, f"spin cooldown {cd} shorter than the swing"
        # Crowded rooms run game logic below 60 Hz; wait for the swing to end.
        for _ in range(300):
            tick_pinned(pb, 1, foes, spots)
            if not fang_segs(pb):
                break
        tick_pinned(pb, 2, foes, spots)
        hps = [pb.memory[e + 14] for e in foes]
        assert all(h == 20 - SPIN_DMG for h in hps), (
            f"spin must hit all 8 sides exactly once for {SPIN_DMG}: {hps}")
        assert pb.memory[far + 14] == 20, "spin reached 48 px (stab-only range)"
    finally:
        pb.stop(save=False)


def test_claw_sword_tiles_survive_events():
    """Regression: the sword used to share bank-1 OBJ 160..175 with the spell
    art, and every room entry / Pack resume turned it into spell glyphs."""
    art = sword_art()
    pb = boot(0)
    try:
        clear_arena(pb)
        drop_hp(pb, full=False)
        face_east(pb)
        fire_a(pb, direction=None, ticks=1)
        pb.tick(30)
        assert sword_vram(pb) == art, "Claw Sword tiles not loaded at 144..159"
        scr = addr("_loop_current_screen")
        # Pack resume runs the same room-entry tile refresh as a door.
        for _ in range(2):
            pb.button("start"); pb.tick(40)
            pb.button("start"); pb.tick(60)
        assert pb.memory[scr] == 5, "did not return from the Pack"
        assert sword_vram(pb) == art, "Pack/room refresh clobbered the Claw Sword"
        # Spell (B) and Will MAX.
        pb.button_press("b"); pb.tick(30); pb.button_release("b"); pb.tick(40)
        assert sword_vram(pb) == art, "spell cast clobbered the Claw Sword"
        pb.memory[PLAYER + 48] = 1  # will_level
        pb.memory[PLAYER + 22] = 0
        pb.button_press("a"); pb.tick(2); pb.button_release("a"); pb.tick(60)
        assert sword_vram(pb) == art, "Will MAX clobbered the Claw Sword"
        clear_arena(pb)
        fire_a(pb, direction="right", ticks=4); pb.tick(20)
        assert sword_vram(pb) == art, "stab after events drew stale tiles"
    finally:
        pb.stop(save=False)
    # Reserved: another hero never writes the window.
    pb = boot(2)
    try:
        before = sword_vram(pb)
        scr = addr("_loop_current_screen")
        for _ in range(2):
            pb.button("start"); pb.tick(40)
            pb.button("start"); pb.tick(60)
        pb.button_press("b"); pb.tick(30); pb.button_release("b"); pb.tick(40)
        pb.button_press("a"); pb.tick(20); pb.button_release("a"); pb.tick(20)
        assert sword_vram(pb) == before, (
            "bank-1 OBJ 144..159 is reserved for the Claw Sword, "
            "but a non-Wolfkin run wrote it")
    finally:
        pb.stop(save=False)


def main():
    test_slash_diagonal_and_parented()
    test_stab_reach_and_damage()
    test_beam_only_at_full_hearts_and_no_double_hit()
    test_formation_grants_projectiles()
    test_sword_sprite_reach()
    test_attract_sword_sprite_reach()
    test_spin_hits_all_eight_sides_once()
    test_claw_sword_tiles_survive_events()
    print("[wolfkin-longsword] PASS spin diag, stab 9/reach, beam latch, formation beams, sprite reach, attract reach, spin 8 sides once, reserved tiles")


if __name__ == "__main__":
    main()
