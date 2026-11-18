#!/usr/bin/env python3
"""Sun Lattice tool contracts (PR C): Hookshot snag-and-spin, Morningstar.

Spec question 3: a Hookshot that reaches a rotatable Helio Vane in an
unsolved Sun Lattice room turns it 90 degrees and retracts without pulling
the champion. Braziers, Obelisks, Wedges, Fixed Vanes and a solved room's
frozen vanes keep the ordinary latch-and-pull. The Morningstar's ball turns
a vane it sweeps into.

Run: python3 scripts/test_sun_lattice_tools.py [--gif DIR]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sun_lattice_harness as slh  # noqa: E402
import test_puzzles as tp  # noqa: E402

PL, EN, SL = tp.PL, tp.EN, tp.SL
HOOKSHOT, MORNINGSTAR, BOMBS = 46, 47, 48
AUX = {HOOKSHOT: 0xF5, MORNINGSTAR: 0xF6, BOMBS: 0xF7}
AIM = int(re.search(r"DEF _player_aim_dir 0x([0-9A-Fa-f]+)", tp.NOI).group(1), 16)


def pos(pb):
    return (pb.memory[PL + 9] | (pb.memory[PL + 10] << 8),
            pb.memory[PL + 11] | (pb.memory[PL + 12] << 8))


def tool_live(pb, item):
    return any(pb.memory[EN + i * 28] != 0 and pb.memory[EN + i * 28 + 1] & 1
               and pb.memory[EN + i * 28 + 23] == AUX[item] for i in range(32))


def equip(pb, item):
    pb.memory[PL + 24] = item
    pb.memory[PL + 18] = item
    pb.memory[PL + 19] = 0
    pb.memory[PL + 4] = max(pb.memory[PL + 4], 5)


def body_free(tiles, px, py):
    for ty in range(py // 8, (py + 15) // 8 + 1):
        for tx in range(px // 8, (px + 15) // 8 + 1):
            if not (0 <= tx < 20 and 0 <= ty < 17) or tiles[ty * 20 + tx] not in slh.WALKABLE:
                return False
    return True


def hook_lanes(f, tiles):
    """Placements that send the hook straight down a clear lane into f."""
    x, y = f["x"], f["y"]
    for k in range(1, 6):
        for button, d8, px, py, lane in (
            ("right", 2, 8 * x - 16 - 8 * k, 8 * y - 4, [(x - j, y) for j in range(1, k + 2)]),
            ("left", 6, 8 * x + 8 + 8 * k, 8 * y - 4, [(x + j, y) for j in range(1, k + 2)]),
            ("down", 4, 8 * x - 4, 8 * y - 16 - 8 * k, [(x, y - j) for j in range(1, k + 2)]),
            ("up", 0, 8 * x - 4, 8 * y + 8 + 8 * k, [(x, y + j) for j in range(1, k + 2)]),
        ):
            if px < 8 or py < 8 or not body_free(tiles, px, py):
                continue
            if all(0 <= cx < 20 and 0 <= cy < 17 and tiles[cy * 20 + cx] in slh.WALKABLE
                   for cx, cy in lane):
                yield button, d8, px, py


def fire(pb, item, button, d8, px, py, frames, frames_out=None):
    """Aim, fire the secondary once and watch; returns max displacement."""
    equip(pb, item)
    slh.put16(pb, PL + 9, px)
    slh.put16(pb, PL + 11, py)
    pb.button_press(button)
    pb.tick()
    pb.button_release(button)
    slh.put16(pb, PL + 9, px)
    slh.put16(pb, PL + 11, py)
    pb.memory[AIM] = d8
    pb.memory[PL + 22] = 0
    pb.tick(2)
    start = pos(pb)
    if frames_out is not None:
        frames_out.extend(pb.screen.image.copy() for _ in range(4))
    pb.button_press("b")
    pb.tick(2)
    pb.button_release("b")
    moved = 0
    for i in range(frames):
        pb.tick()
        p = pos(pb)
        moved = max(moved, abs(p[0] - start[0]) + abs(p[1] - start[1]))
        if frames_out is not None:
            frames_out.append(pb.screen.image.copy())
        if i > 4 and not tool_live(pb, item):
            break
    for _ in range(10):
        pb.tick()
    # A drop knocked loose by the tool runs snap_reward_to_reachable(), whose
    # flood marks room_tilemap bit 7 for a few frames. Compare beams only
    # once that main-loop pass has finished.
    for _ in range(30):
        if not any(pb.memory[tp.TM + i] & 0x80 for i in range(340)):
            break
        pb.tick()
    return moved


def hook_spins_vane(pb, fixtures, tiles, frames_out=None):
    for i, f in enumerate(fixtures):
        if f["kind"] != slh.SLK_VANE:
            continue
        for li, lane in enumerate(hook_lanes(f, tiles)):
            before = pb.memory[SL["_sl_ang"] + i]
            moved = fire(pb, HOOKSHOT, *lane, 60, frames_out)
            after = pb.memory[SL["_sl_ang"] + i]
            assert not tool_live(pb, HOOKSHOT), "hook never retracted"
            if after != before:
                assert after == before ^ 1, "vane turned more than once"
                assert moved == 0, f"snag-and-spin pulled the champion {moved}px"
                tp.lattice_beams_match(pb, slh.read_state(pb, SL))
                return i, lane + (li,)
            if frames_out is not None:
                frames_out.clear()
    raise AssertionError("no Hookshot lane turned any rotatable vane")


def hook_pulls(pb, fixtures, tiles, kinds, label, frames_out=None):
    for i, f in enumerate(fixtures):
        if f["kind"] not in kinds:
            continue
        for lane in hook_lanes(f, tiles):
            angs = [pb.memory[SL["_sl_ang"] + j] for j in range(len(fixtures))]
            mark = len(frames_out) if frames_out is not None else 0
            moved = fire(pb, HOOKSHOT, *lane, 60, frames_out)
            assert angs == [pb.memory[SL["_sl_ang"] + j] for j in range(len(fixtures))], (
                f"{label}: hook changed an angle")
            if moved >= 8:
                return i
            if frames_out is not None:
                del frames_out[mark:]
    raise AssertionError(f"{label}: no lane latched and pulled the champion")


def morningstar_spins(pb, fixtures, tiles):
    # Will now scales the orbit (24/27/33/39 px). Clear it so the classic
    # 24 px stance still hits, and also try farther stances so a juiced
    # swing is not a false miss.
    pb.memory[PL + 42] = 0
    pb.memory[PL + 48] = 0
    for i, f in enumerate(fixtures):
        if f["kind"] != slh.SLK_VANE:
            continue
        x, y = f["x"], f["y"]
        for dist in (28, 36, 44):
            for d8, px, py in ((2, 8 * x - dist, 8 * y - 4),
                               (6, 8 * x - 4, 8 * y - dist),
                               (4, 8 * x - dist, 8 * y - 4),
                               (0, 8 * x - 4, 8 * y - dist)):
                if px < 8 or py < 8 or not body_free(tiles, px, py):
                    continue
                before = pb.memory[SL["_sl_ang"] + i]
                fire(pb, MORNINGSTAR, "right" if px < 8 * x else "down",
                     d8, px, py, 50)
                if pb.memory[SL["_sl_ang"] + i] != before:
                    tp.lattice_beams_match(pb, slh.read_state(pb, SL))
                    return i
    raise AssertionError("the Morningstar never turned a vane")


def fuse_bomb_spins(pb, fixtures, tiles):
    for i, f in enumerate(fixtures):
        if f["kind"] != slh.SLK_VANE:
            continue
        x, y = f["x"], f["y"]
        # Bomb centre (player + 8) lands one cell beside the vane.
        for px, py in ((8 * x - 16, 8 * y - 4), (8 * x, 8 * y - 4),
                       (8 * x - 4, 8 * y - 16), (8 * x - 4, 8 * y)):
            if px < 8 or py < 8 or not body_free(tiles, px, py):
                continue
            if (px // 8 <= x <= (px + 15) // 8) and (py // 8 <= y <= (py + 15) // 8):
                continue
            before = pb.memory[SL["_sl_ang"] + i]
            fire(pb, BOMBS, "right", 2, px, py, 80)
            if pb.memory[SL["_sl_ang"] + i] != before:
                tp.lattice_beams_match(pb, slh.read_state(pb, SL))
                return i
    raise AssertionError("no fuse bomb turned a vane")


def contract(stage, gif_dir=None):
    pb = tp.enter_mission_cell(stage, "trial")
    tp.clear_hostiles(pb)
    assert pb.memory[tp.KIND] == slh.PUZZLE_SUN_LATTICE and pb.memory[tp.LOCKED]
    for _ in range(60):
        pb.tick()
    fixtures = slh.read_state(pb, SL)
    tiles = tp.tilemap(pb)
    frames = [] if gif_dir else None
    vane, lane = hook_spins_vane(pb, fixtures, tiles, frames)
    print(f"  stage {stage}: Hookshot spun vane {vane} from the {lane[0]} lane "
          f"(lane #{lane[-1]}), no pull")
    # Non-rotatable fixtures keep latch-and-pull.
    target = hook_pulls(pb, fixtures, tiles,
                        {slh.SLK_EMITTER, slh.SLK_OBELISK, slh.SLK_BIFROST, slh.SLK_FIXED},
                        "fixed fixture", frames)
    print(f"  stage {stage}: fixture {target} (kind {fixtures[target]['kind']}) still pulls")
    tp.clear_hostiles(pb)
    star = morningstar_spins(pb, slh.read_state(pb, SL), tiles)
    print(f"  stage {stage}: Morningstar turned vane {star}")
    tp.clear_hostiles(pb)
    if pb.memory[tp.LOCKED]:
        bomb = fuse_bomb_spins(pb, slh.read_state(pb, SL), tiles)
        print(f"  stage {stage}: fuse bomb turned vane {bomb}")
    pb.memory[PL + 2] = pb.memory[PL + 1]   # refill hearts after the blast
    tp.clear_hostiles(pb)
    fx_now = slh.read_state(pb, SL)
    lit = slh.trace(fx_now, [f["ang"] for f in fx_now], tp.tilemap(pb))[2]
    if slh.obelisks(fx_now) <= lit:
        # The tool turns above happened to finish the room: let it dwell.
        for _ in range(30):
            pb.tick()
    else:
        tp.solve_sun_lattice(pb)
    assert pb.memory[tp.LOCKED] == 0, "room did not unlock"
    # A solved room's frozen vanes are ordinary posts again: latch and pull.
    hook_pulls(pb, fixtures, tp.tilemap(pb), {slh.SLK_VANE}, "solved vane")
    print(f"  stage {stage}: solved room's vanes latch and pull")
    if gif_dir:
        out = Path(gif_dir) / f"hook_stage{stage}.gif"
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=100, loop=0)
    pb.stop(save=False)


def demo(stage, vane, lane_index, out):
    """Record one Hookshot throw at a vane (before/after evidence only)."""
    pb = tp.enter_mission_cell(stage, "trial")
    tp.clear_hostiles(pb)
    for _ in range(60):
        pb.tick()
    fixtures = slh.read_state(pb, SL)
    lane = list(hook_lanes(fixtures[vane], tp.tilemap(pb)))[lane_index]
    frames = []
    before = pb.memory[SL["_sl_ang"] + vane]
    moved = fire(pb, HOOKSHOT, *lane, 60, frames)
    frames.extend(pb.screen.image.copy() for _ in range(6))
    print(f"  demo stage {stage} vane {vane}: angle {before}->"
          f"{pb.memory[SL['_sl_ang'] + vane]}, champion moved {moved}px")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=60, loop=0)
    pb.stop(save=False)


def main():
    if "--demo" in sys.argv:
        a = sys.argv[sys.argv.index("--demo") + 1:]
        demo(int(a[0]), int(a[1]), int(a[2]), a[3])
        return
    gif_dir = sys.argv[sys.argv.index("--gif") + 1] if "--gif" in sys.argv else None
    stages = [int(a) for a in sys.argv[1:] if a.isdigit()] or [3, 4, 6, 9]
    for stage in stages:
        contract(stage, gif_dir)
    print("[sun-lattice-tools] PASS Hookshot snag-and-spin, latch-and-pull, "
          f"Morningstar and fuse bomb turns, solved vanes frozen (Stages {stages})")


if __name__ == "__main__":
    main()
