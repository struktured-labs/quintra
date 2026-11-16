#!/usr/bin/env python3
"""Live-ROM contract for the Prism Toggle crystal-switch chamber.

For a Trial or Waystone that the seeded puzzle pool turns into a Prism
Toggle (Stages 1, 2, 3 and 6 here, covering all three template tiers):

* the cart's chamber matches the Rust reference (`prism-dump`), tile by tile;
* barriers are solid pillars in the raised colour, tinted floor otherwise,
  and the orb glows in the colour that is up (Compass/HUD clarity);
* a melee strike on an orb flips both barrier sets; the orb never shatters;
* standing on the gold seal unlocks the room, persists the slot bit, and
  lowers every barrier so the way back out is open.

Writes before/after PNGs and a GIF to $PRISM_PREVIEW_DIR (default tmp/).
Run: uv run --with pyboy --with pillow python scripts/test_prism_toggle.py
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
RS, PL, TM = addr("_run_state"), addr("_player"), addr("_room_tilemap")
KIND, LOCKED = addr("_room_puzzle_kind"), addr("_room_puzzle_locked")
RAISED = addr("_prism_raised")
WALL, FLOOR, FLOOR2, FLOOR3, PILLAR, CRYSTAL = 2, 1, 19, 20, 21, 22
BGPAL_CRYSTAL, BGPAL_DOOR, BGPAL_CRACK = 2, 3, 4


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
                        "G": {FLOOR3}, "a": {PILLAR, FLOOR2},
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
        pb.screen.image.save(OUT / f"prism-stage{stage + 1}-arrival.png")
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
        pb.screen.image.save(OUT / f"prism-stage{stage + 1}-flipped.png")
        # The seal: feet on the gold plate.
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
        pb.screen.image.save(OUT / f"prism-stage{stage + 1}-solved.png")
        report.update(seed=seed, role=role, tpl=r["tpl"], flips=r["flips"])

    generated_room(stage, seed, local_room=cell, probe=probe)
    print(f"  stage {stage + 1} {role} cell {cell}: template {report['tpl']}, "
          f"{report['flips']} strike(s) minimum, ROM == Rust, flip + seal OK")


def main():
    if not DUMP.exists():
        subprocess.run(["cargo", "build", "--release", "-q", "-p",
                        "quintra-procgen", "--bin", "prism-dump"],
                       cwd=ROOT, check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for stage in (0, 1, 2, 5):
        run_stage(stage, frames)
    frames[0].save(OUT / "prism-toggle.gif", save_all=True,
                   append_images=frames[1:], duration=900, loop=0)
    print("[prism] PASS chamber parity, colour clarity, melee flip, "
          "unbreakable orb, seal unlock + persistence, Stages 1/2/3/6")


if __name__ == "__main__":
    main()
