#!/usr/bin/env python3
"""Live-ROM contract for the Prism Toggle crystal-switch chamber.

For a Trial or Waystone that the seeded puzzle pool turns into a Prism
Toggle (Stages 1, 2, 3 and 6 here, covering all three template tiers):

* the cart's chamber matches the Rust reference (`prism-dump`), tile by tile;
* barriers are solid pillars in the raised colour, tinted floor otherwise,
  and the orb glows in the colour that is up (Compass/HUD clarity);
* a melee strike on an orb flips both barrier sets; the orb never shatters;
* standing on the gold seal unlocks the room, persists the slot bit, and
  lowers every barrier so the way back out is open;
* the open ring has a restored, slightly denser guard pack, and exactly one
  grounded inmate stays inside the goal pocket until the seal opens. The
  inmate cannot damage through closed walls, and the seal still solves.

Writes before/after PNGs and a GIF (native and 4x) to $PRISM_PREVIEW_DIR
(default tmp/). Run:

    uv run --with pyboy --with pillow python scripts/test_prism_toggle.py
"""
import os
import subprocess
from pathlib import Path

import sun_lattice_harness as slh
from quintra_topology import (
    PUZZLE_PRISM_TOGGLE, STAGE_START, dungeon_size, mission_graph,
    puzzle_slot_kind, room_seed,
)
from test_stage_archetypes import generated_room, addr, ROM

ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / "target/release/prism-dump"
OUT = Path(os.environ.get("PRISM_PREVIEW_DIR", ROOT / "tmp"))
RS, PL, TM, EN = addr("_run_state"), addr("_player"), addr("_room_tilemap"), addr("_entities")
KIND, LOCKED = addr("_room_puzzle_kind"), addr("_room_puzzle_locked")
RAISED = addr("_prism_raised")
INMATE = addr("_prism_inmate_idx")
WALL, FLOOR, FLOOR2, FLOOR3, PILLAR, CRYSTAL = 2, 1, 19, 20, 21, 22
BGPAL_CRYSTAL, BGPAL_DOOR, BGPAL_CRACK = 2, 3, 4
ENT_ENEMY, EF_ACTIVE = 2, 0x01
# Normal difficulty: 5 ring guards in Stages 1-3, 6 from Stage 4, plus inmate.
def ring_target(stage):
    return 5 + (1 if stage >= 3 else 0)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def find_case(stage):
    for n in range(4000):
        seed = (0x7A11C0DE + n * 2654435761) & 0xFFFFFFFF
        for slot, role in ((0, "trial"), (1, "waystone")):
            if puzzle_slot_kind(seed, stage, slot) == PUZZLE_PRISM_TOGGLE:
                cell = mission_graph(dungeon_size(stage), seed, stage)[role]
                return seed, role, cell
    raise AssertionError(f"no Prism Toggle seed for stage {stage + 1}")


def reference(seed, stage):
    out = subprocess.run([str(DUMP), str(seed), str(stage)], check=True,
                         capture_output=True, text=True).stdout.split("\n")
    tpl, mirror, swap, flips = map(int, out[0].split())
    return dict(tpl=tpl, swap=swap, flips=flips, rows=out[1:18])


def attr(pb, x, y):
    # Live BG attribute plane (VRAM bank 1) at the room's map origin.
    ox = pb.memory[addr("_room_bg_origin_x")]
    oy = pb.memory[addr("_room_bg_origin_y")]
    mx, my = (ox + x) & 31, (oy + y) & 31
    return pb.memory[1, 0x9800 + my * 32 + mx] & 7


def check_barriers(pb, ref, raised, solved=False):
    for y, row in enumerate(ref["rows"]):
        for x, ch in enumerate(row):
            if ch not in "ab":
                continue
            colour = 0 if ch == "a" else 1
            want = FLOOR2 if solved or colour != raised else PILLAR
            got = pb.memory[TM + y * 20 + x]
            assert got == want, (
                f"barrier {ch} at {x},{y}: tile {got}, want {want} "
                f"(raised {raised}, solved {solved})")
            pal = attr(pb, x, y)
            assert pal == (BGPAL_CRACK if colour == 0 else BGPAL_CRYSTAL), (
                f"barrier {ch} at {x},{y} lost its colour: palette {pal}")


def iter_enemies(pb):
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] != ENT_ENEMY or not (pb.memory[ep + 1] & EF_ACTIVE):
            continue
        x = pb.memory[ep + 3] | ((pb.memory[ep + 4] & 0x7F) << 8)
        if pb.memory[ep + 4] & 0x80:
            x -= 0x8000
        y = pb.memory[ep + 7] | ((pb.memory[ep + 8] & 0x7F) << 8)
        if pb.memory[ep + 8] & 0x80:
            y -= 0x8000
        yield i, ep, x, y


def goal_pocket(rows):
    """Room-tile set of the sealed goal cell (floor + gold, not barriers)."""
    h, w = len(rows), len(rows[0])
    seeds = [(x, y) for y, row in enumerate(rows)
             for x, ch in enumerate(row) if ch == "G"]
    pocket = set(seeds)
    stack = list(seeds)
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            if (nx, ny) in pocket:
                continue
            if rows[ny][nx] not in ".G":
                continue
            pocket.add((nx, ny))
            stack.append((nx, ny))
    return pocket


def save_scaled(img, name):
    img.save(OUT / name)
    big = img.convert("RGB").resize((640, 576), 0)
    stem, ext = name.rsplit(".", 1)
    big.save(OUT / f"{stem}-4x.{ext}")
    return big


def check_encounters(pb, ref, stage, frames):
    pocket = goal_pocket(ref["rows"])
    assert pocket, "Rust reference has no goal pocket"
    inmate_i = pb.memory[INMATE]
    assert inmate_i != 0xFF, "no Prism Toggle center inmate was placed"
    enemies = list(iter_enemies(pb))
    by_idx = {i: (x, y) for i, _ep, x, y in enemies}
    assert inmate_i in by_idx, f"inmate slot {inmate_i} is not a live enemy"
    ix, iy = by_idx[inmate_i]
    stx, sty = ix >> 3, iy >> 3
    ctx, cty = (ix + 8) >> 3, (iy + 8) >> 3
    assert (ctx, cty) in pocket and (stx, sty) in pocket, (
        f"inmate at tile {(ctx, cty)} is not inside the goal pocket {sorted(pocket)[:8]}...")
    # The stand / center must stay off the gold plate so the hero can still
    # step on a seal cell. Tight tier-2 pockets only have an 8px apron, so
    # a 16px sprite may visually graze a neighboring gold tile.
    goals = {(x, y) for y, row in enumerate(ref["rows"])
             for x, ch in enumerate(row) if ch == "G"}
    assert (stx, sty) not in goals, (
        f"inmate stand {(stx, sty)} is on the seal {goals}")

    ring = []
    for i, _ep, x, y in enemies:
        if i == inmate_i:
            continue
        cx, cy = (x + 8) >> 3, (y + 8) >> 3
        assert (cx, cy) not in pocket, f"ring guard {i} spawned in the goal pocket at {(cx, cy)}"
        ring.append(i)
    want = ring_target(stage)
    assert len(ring) >= want, (
        f"stage {stage + 1} ring pack too thin: {len(ring)} < {want} "
        f"(plus inmate, total {len(enemies)})")

    # Containment: the inmate stays in the pocket while the seal is locked.
    for _ in range(180):
        pb.tick()
    enemies = list(iter_enemies(pb))
    by_idx = {i: (x, y) for i, _ep, x, y in enemies}
    assert inmate_i in by_idx, "inmate died or despawned while still locked in"
    ix, iy = by_idx[inmate_i]
    ctx, cty = (ix + 8) >> 3, (iy + 8) >> 3
    assert (ctx, cty) in pocket, (
        f"inmate walked out of the goal pocket to {(ctx, cty)} before the seal opened")
    assert pb.memory[LOCKED] == 1, "chamber unlocked itself during the pen test"

    # Damage-through-walls: park on the outside of a pocket wall, after
    # silencing the ring pack so only the inmate could be the source.
    for i, ep, _x, _y in iter_enemies(pb):
        if i == inmate_i:
            continue
        pb.memory[ep] = 0
        pb.memory[ep + 1] = 0
    wall_side = None
    for (tx, ty) in pocket:
        for nx, ny, px, py in (
            (tx - 1, ty, (tx - 2) * 8, ty * 8 - 8),
            (tx + 1, ty, (tx + 1) * 8, ty * 8 - 8),
            (tx, ty - 1, tx * 8 - 8, (ty - 2) * 8),
            (tx, ty + 1, tx * 8 - 8, (ty + 1) * 8),
        ):
            if not (0 <= nx < 20 and 0 <= ny < 17):
                continue
            if (nx, ny) in pocket:
                continue
            tile = pb.memory[TM + ny * 20 + nx]
            if tile not in (WALL, PILLAR):
                continue
            if not (0 <= px <= 144 and 0 <= py <= 120):
                continue
            wall_side = (px, py, nx, ny)
            break
        if wall_side:
            break
    assert wall_side, "no outside floor next to a pocket wall"
    px, py, wx, wy = wall_side
    put16(pb, PL + 9, px)
    put16(pb, PL + 11, py)
    pb.memory[PL + 15] = 0  # iframes
    if pb.memory[PL + 2] < 8:
        pb.memory[PL + 2] = 12
    hp = pb.memory[PL + 2]
    for _ in range(90):
        pb.tick()
        # Keep the hero parked; movement would wander into a door or gate.
        put16(pb, PL + 9, px)
        put16(pb, PL + 11, py)
        pb.memory[PL + 15] = 0
    assert pb.memory[PL + 2] == hp, (
        f"inmate damaged the hero through wall/pillar at {(wx, wy)} "
        f"({hp} -> {pb.memory[PL + 2]})")
    frames.append(pb.screen.image.copy())
    save_scaled(pb.screen.image, f"prism-stage{stage + 1}-inmate.png")
    return dict(ring=len(ring), inmate=(ctx, cty), pocket=len(pocket))


def run_stage(stage, frames):
    seed, role, cell = find_case(stage)
    report = {}

    def probe(pb, _tiles):
        for _ in range(60):
            pb.tick()
        assert pb.memory[KIND] == PUZZLE_PRISM_TOGGLE, (
            f"stage {stage + 1} {role} is kind {pb.memory[KIND]}")
        assert pb.memory[LOCKED] == 1
        rseed = room_seed(seed, pb.memory[RS], pb.memory[RS + 1])
        r = reference(rseed, stage)
        tiles = [pb.memory[TM + i] for i in range(20 * 17)]
        for y in range(1, 16):
            for x in range(1, 19):
                ch = r["rows"][y][x]
                t = tiles[y * 20 + x]
                want = {"#": {WALL}, ".": {FLOOR}, "o": {CRYSTAL},
                        "G": {FLOOR}, "a": {PILLAR, FLOOR2},
                        "b": {PILLAR, FLOOR2}}[ch]
                assert t in want, f"ROM {t} at {x},{y} != Rust {ch!r}"
        raised = pb.memory[RAISED]
        assert raised == r["swap"], "start colour differs from Rust"
        check_barriers(pb, r, raised)
        orbs = [(x, y) for y, row in enumerate(r["rows"])
                for x, ch in enumerate(row) if ch == "o"]
        goal = next((x, y) for y, row in enumerate(r["rows"])
                    for x, ch in enumerate(row) if ch == "G")
        for ox, oy in orbs:
            assert attr(pb, ox, oy) == (BGPAL_CRYSTAL if raised else BGPAL_CRACK)
        frames.append(pb.screen.image.copy())
        save_scaled(pb.screen.image, f"prism-stage{stage + 1}-arrival.png")
        enc = check_encounters(pb, r, stage, frames)
        # Melee strike flips the chamber and the orb survives.
        ox, oy = orbs[0]
        side = slh.strike(pb, PL, TM, ox, oy,
                          lambda: pb.memory[RAISED] != raised, frames=60)
        assert side, f"melee strike at orb {ox},{oy} did not flip"
        for _ in range(40):
            pb.tick()
        assert pb.memory[TM + oy * 20 + ox] == CRYSTAL, "orb shattered"
        check_barriers(pb, r, raised ^ 1)
        frames.append(pb.screen.image.copy())
        save_scaled(pb.screen.image, f"prism-stage{stage + 1}-flipped.png")
        # The seal: feet on the gold plate. The inmate must not block this.
        gx, gy = goal
        put16(pb, PL + 9, gx * 8 - 8 + 8)
        put16(pb, PL + 11, gy * 8 - 12 + 8)
        for _ in range(30):
            pb.tick()
            if pb.memory[LOCKED] == 0:
                break
        assert pb.memory[LOCKED] == 0, "seal did not open the room"
        bit = 1 if role == "trial" else 0x80
        assert pb.memory[RS + 27] & bit, "solve did not persist its slot bit"
        for _ in range(60):
            pb.tick()
        check_barriers(pb, r, pb.memory[RAISED], solved=True)
        frames.append(pb.screen.image.copy())
        save_scaled(pb.screen.image, f"prism-stage{stage + 1}-solved.png")
        report.update(seed=seed, role=role, tpl=r["tpl"], flips=r["flips"],
                      ring=enc["ring"], inmate=enc["inmate"])

    generated_room(stage, seed, local_room=cell, probe=probe)
    print(f"  stage {stage + 1} {role} cell {cell}: template {report['tpl']}, "
          f"{report['flips']} strike(s) minimum, ring {report['ring']}, "
          f"inmate {report['inmate']}, ROM == Rust, flip + seal OK")


def main():
    if not DUMP.exists():
        subprocess.run(["cargo", "build", "--release", "-q", "-p",
                        "quintra-procgen", "--bin", "prism-dump"],
                       cwd=ROOT, check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    scaled = []
    for stage in (0, 1, 2, 5):
        before = len(frames)
        run_stage(stage, frames)
        scaled.extend(f.convert("RGB").resize((640, 576), 0)
                      for f in frames[before:])
    frames[0].save(OUT / "prism-toggle.gif", save_all=True,
                   append_images=frames[1:], duration=900, loop=0)
    scaled[0].save(OUT / "prism-toggle-4x.gif", save_all=True,
                   append_images=scaled[1:], duration=900, loop=0)
    print("[prism] PASS chamber parity, colour clarity, melee flip, "
          "unbreakable orb, seal unlock + persistence, ring pack + "
          "contained center inmate, Stages 1/2/3/6")


if __name__ == "__main__":
    main()
