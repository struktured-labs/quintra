#!/usr/bin/env python3
"""Live-ROM contract for Law Lock (Dungeon Law WAX/WANE doorway gates).

For Stages 2, 5 and 8 (one gate, two gates, three gates on most seeds):

* the cart's generated gates/altars equal the Rust reference
  (`lawlock-dump`), which also proves the cart's maze, mission roles and
  cache cell match `quintra-procgen::topology` for that seed;
* a gated doorway is a solid pillar pair while closed, tinted with the
  colour of the state that opens it, and an ordinary door while open;
  presetting the other Law state opens it (both states checked);
* an altar room holds a BGT_SWITCH three tiles inside its first doorway;
  contextual A flips the persistent Law bit and the save byte (no new SRAM);
* the Spirit Compass shows the LAW legend in the active state's colour.

Writes PNGs to $LAW_LOCK_PREVIEW_DIR (default tmp/).
Run: uv run --with pyboy --with pillow python scripts/test_law_lock.py
"""
import os
import subprocess
from pathlib import Path

from quintra_topology import dungeon_predecessor, dungeon_size
from test_stage_archetypes import generated_room, addr

ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / "target/release/lawlock-dump"
OUT = Path(os.environ.get("LAW_LOCK_PREVIEW_DIR", ROOT / "tmp"))
RS, PL, TM = addr("_run_state"), addr("_player"), addr("_room_tilemap")
EXT, BOTTOM = addr("_room_world_extension"), addr("_room_world_bottom")
WORLD_W, WORLD_H = addr("_room_world_width"), addr("_room_world_height")
SCREEN = addr("_loop_current_screen")
RS_LAW = 36
WANE = 0x80
PL_IFRAMES = 15
DOOR, PILLAR, SWITCH = 3, 21, 33
BGPAL_CRYSTAL, BGPAL_DOOR, BGPAL_CRACK = 2, 3, 4
SCREEN_ROOM, SCREEN_MAP = 5, 8
DIRS = "NESW"


def sym(name, n=1):
    a = addr(name)
    return a if n == 1 else [a + i for i in range(n)]


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def reference(seed, bb):
    out = subprocess.run([str(DUMP), hex(seed), str(bb)], check=True,
                         capture_output=True, text=True).stdout.split()
    i = out.index("G")
    n = int(out[i + 1])
    gates = [tuple(map(int, g.split(","))) for g in out[i + 2:i + 2 + n]]
    j = out.index("A")
    altars = [int(a) for a in out[j + 2:j + 2 + int(out[j + 1])]]
    return gates, altars


def tile(pb, x, y):
    if y < 17:
        if x < 20:
            return pb.memory[TM + y * 20 + x]
        return pb.memory[EXT + y * 11 + (x - 20)] & 0x7F
    return pb.memory[BOTTOM + (y - 17) * 31 + x] & 0x7F


def attr(pb, x, y):
    ox = pb.memory[addr("_room_bg_origin_x")]
    oy = pb.memory[addr("_room_bg_origin_y")]
    return pb.memory[1, 0x9800 + ((oy + y) & 31) * 32 + ((ox + x) & 31)] & 7


def door_cells(pb, d):
    east = (pb.memory[WORLD_W] >> 3) - 1
    south = (pb.memory[WORLD_H] >> 3) - 1
    if d == 0:
        return [(9, 0), (10, 0)]
    if d == 2:
        return [(9, south), (10, south)]
    if d == 1:
        return [(east, 8), (east, 9)]
    return [(0, 8), (0, 9)]


def gated_cells(gates):
    """(cell, dir-from-cell, open-state) for both ends of every gate."""
    out = []
    for a, b, d, o in gates:
        out.append((a, d, o))
        out.append((b, (d + 2) & 3, o))
    return out


def entry_is_free(seed, stage, cell, gates):
    src, d = dungeon_predecessor(cell, dungeon_size(stage), seed, stage)
    return not any({a, b} == {src, cell} for a, b, _, _ in gates)


def find_case(stage, want_gates):
    for n in range(3000):
        seed = (0x1A71C0DE + n * 2654435761) & 0xFFFFFFFF
        gates, altars = reference(seed, stage)
        if len(gates) < want_gates:
            continue
        gate = next(((c, d, o) for c, d, o in gated_cells(gates)
                     if entry_is_free(seed, stage, c, gates)), None)
        altar = next((a for a in altars
                      if entry_is_free(seed, stage, a, gates)), None)
        if gate and altar is not None:
            return seed, gates, altars, gate, altar
    raise AssertionError(f"no Law Lock seed for stage {stage + 1}")


def check_cart_matches(pb, gates, altars, label):
    n = pb.memory[sym("_ll_gate_n")]
    cart = [(pb.memory[sym("_ll_gate_a") + i], pb.memory[sym("_ll_gate_b") + i],
             pb.memory[sym("_ll_gate_dir") + i], pb.memory[sym("_ll_gate_open") + i])
            for i in range(n)]
    assert cart == gates, f"{label}: cart gates {cart} != Rust {gates}"
    an = pb.memory[sym("_ll_altar_n")]
    cart_alt = [pb.memory[sym("_ll_altar") + i] for i in range(an)]
    assert cart_alt == altars, f"{label}: cart altars {cart_alt} != Rust {altars}"


def check_gate(pb, d, opens, state, label):
    closed = opens != state
    for x, y in door_cells(pb, d):
        t = tile(pb, x, y)
        want = PILLAR if closed else DOOR
        assert t == want, (f"{label}: {DIRS[d]} doorway {x},{y} tile {t}, "
                           f"want {'pillar' if closed else 'door'}")
        if closed:
            pal = attr(pb, x, y)
            want_pal = BGPAL_CRACK if opens else BGPAL_CRYSTAL
            assert pal == want_pal, (f"{label}: closed gate palette {pal} "
                                     f"!= opening-state colour {want_pal}")
    mask = pb.memory[sym("_law_lock_closed_dirs")]
    assert bool(mask & (1 << d)) == closed, f"{label}: closed mask {mask:#x}"


def open_compass(pb, png):
    pb.button_press("select")
    for _ in range(120):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_MAP:
            break
    pb.button_release("select")
    pb.tick(40)
    assert pb.memory[SCREEN] == SCREEN_MAP, "SELECT did not open the Compass"
    pb.screen.image.save(png)
    legend = [pb.memory[1, 0x9800 + 16 * 32 + x] & 7 for x in (16, 17, 18)]
    pb.button_press("b")
    for _ in range(120):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    pb.button_release("b")
    return legend


def run_stage(stage, want_gates):
    seed, gates, altars, gate, altar = find_case(stage, want_gates)
    cell, d, opens = gate
    tag = f"stage{stage + 1}"
    law_kind = {}

    def gate_probe(state):
        def probe(pb, _tiles):
            pb.tick(30)
            check_cart_matches(pb, gates, altars, tag)
            law = pb.memory[RS + RS_LAW]
            assert (law & WANE) == (WANE if state else 0), f"law {law:#x}"
            law_kind["kind"] = law & 3
            check_gate(pb, d, opens, state, f"{tag} cell {cell}")
            name = "closed" if opens != state else "open"
            pb.screen.image.save(OUT / f"law-lock-{tag}-gate-{name}.png")
        return probe

    # WAX: the dungeon's first state.
    generated_room(stage, seed, local_room=cell, probe=gate_probe(0))

    # WANE preset before crossing: the same doorway flips.
    def pre(pb, _addrs):
        pb.memory[RS + RS_LAW] = 0x40 | law_kind["kind"] | WANE
    generated_room(stage, seed, local_room=cell, probe=gate_probe(1),
                   pre_cross=pre)

    # Altar room: contextual A flips the Law and the suspend copy.
    def altar_probe(pb, _tiles):
        pb.tick(30)
        assert pb.memory[sym("_law_lock_has_altar")], f"{tag}: no altar in {altar}"
        ax = pb.memory[sym("_law_lock_altar_x")]
        ay = pb.memory[sym("_law_lock_altar_y")]
        assert tile(pb, ax, ay) == SWITCH, f"{tag}: altar tile {tile(pb, ax, ay)}"
        assert attr(pb, ax, ay) == BGPAL_CRYSTAL, "WAX altar is not cyan"
        legend = open_compass(pb, OUT / f"law-lock-{tag}-compass-wax.png")
        assert legend == [BGPAL_DOOR] * 3, f"WAX LAW legend palette {legend}"
        pb.screen.image.save(OUT / f"law-lock-{tag}-altar-wax.png")
        before = pb.memory[RS + RS_LAW]
        put16(pb, PL + 9, ax * 8 - 4)
        put16(pb, PL + 11, ay * 8 - 8)
        pb.memory[PL + PL_IFRAMES] = 120
        pb.button_press("a")
        pb.tick(24)
        pb.button_release("a")
        pb.tick(40)
        law = pb.memory[RS + RS_LAW]
        assert law == before ^ WANE, f"{tag}: altar did not flip ({before:#x}->{law:#x})"
        pb.memory[0x0000] = 0x0A
        pb.memory[0x4000] = 0
        saved = pb.memory[0xA005 + RS_LAW]
        pb.memory[0x0000] = 0
        assert saved == law, "Law flip was not suspend-saved"
        assert attr(pb, ax, ay) == BGPAL_CRACK, "WANE altar is not warm"
        pb.screen.image.save(OUT / f"law-lock-{tag}-altar-wane.png")
        legend = open_compass(pb, OUT / f"law-lock-{tag}-compass-wane.png")
        assert legend == [BGPAL_CRACK] * 3, f"WANE LAW legend palette {legend}"

    generated_room(stage, seed, local_room=altar, probe=altar_probe)
    print(f"  {tag} seed {seed:#010x}: {len(gates)} gate(s) {gates}, altars "
          f"{altars}; cart == Rust, gate {cell}{DIRS[d]} pillar/door in both "
          f"states, altar {altar} flips + saves, Compass legend")


def main():
    if not DUMP.exists():
        subprocess.run(["cargo", "build", "--release", "-q", "-p",
                        "quintra-procgen", "--bin", "lawlock-dump"],
                       cwd=ROOT, check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for stage, want in ((1, 1), (4, 2), (7, 3)):
        run_stage(stage, want)
    print("[law-lock] PASS cart == Rust gates/altars, doorway pillars in the "
          "opening colour, altar flip + save, Compass legend, Stages 2/5/8")


if __name__ == "__main__":
    main()
