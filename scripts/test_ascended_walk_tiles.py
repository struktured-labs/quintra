#!/usr/bin/env python3
"""Every champion's walk frames draw their own authored art (#253).

Vespine's powered-up (Spirit Convergence) legs showed a "B". The two-tile
stride strip per class lives at OBJ tiles 232..241, and Vespine's pair is
240/241. The HUD's equipped-B box used BG tiles 0xF0/0xF1, which are the
same VRAM (0x8F00, bank 0), so every HUD redraw overwrote Vespine's legs
with the gold "B" letter and the B-item icon.

For all five classes, in the normal and the powered-up state, walking in
each of the four directions:

  * every tile the hero's four OAM slots show holds exactly the art
    authored for that frame (idle, both stride beats, ascended, and the
    ascended stride strip), read back from live VRAM;
  * the HUD B box still shows the gold "B" and its item icon.

Pass --frames DIR to save one PNG per distinct walk frame.
"""
import re
import sys
from pathlib import Path

from test_convergence_transform import PLAYER, ROM, TRANSFORM, addr, boot

ROOT = Path(__file__).resolve().parent.parent
CLASSES = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
DIRECTIONS = ("up", "right", "down", "left")
STRIDE = 4
IDLE, WALK_A, WALK_B, ASCENDED, STEP = 0, 82, 160, 102, 232
S_FLIPX, S_BANK1 = 0x20, 0x08
LETTER_B = bytes((0x00, 0x7C, 0x00, 0x66, 0x00, 0x66, 0x00, 0x7C,
                  0x00, 0x66, 0x00, 0x66, 0x00, 0x7C, 0x00, 0x00))


def c_arrays(*paths):
    arrays = {}
    for path in paths:
        text = (ROOT / path).read_text()
        for name, body in re.findall(
                r"const u8 (sprite_class_\w+)\[\d+\] = \{([^}]*)\}", text):
            arrays[name] = bytes(int(v, 16) for v in re.findall(
                r"0x[0-9A-Fa-f]{2}", body))
    return arrays


ART = c_arrays("src/render/sprites_gen.c", "src/render/sprites_motion_gen.c",
               "src/render/sprites_ascended_gen.c",
               "src/render/sprites_ascended_motion_gen.c")


def authored(class_id):
    """OBJ tile index -> the 16 bytes authored for it, for one class."""
    name = CLASSES[class_id]
    out = {}
    for base, suffix, tiles in ((IDLE, "", 4), (WALK_A, "_walk_a", 4),
                                (WALK_B, "_walk_b", 4),
                                (ASCENDED, "_ascended", 4)):
        data = ART[f"sprite_class_{name}{suffix}"]
        assert len(data) == tiles * 16, (name, suffix, len(data))
        for t in range(tiles):
            out[base + class_id * STRIDE + t] = data[t * 16:t * 16 + 16]
    step = ART[f"sprite_class_{name}_ascended_step"]
    assert len(step) == 32
    for t in range(2):
        out[STEP + class_id * 2 + t] = step[t * 16:t * 16 + 16]
    return out


def vram_tile(pb, tile, bank):
    base = 0x8000 + tile * 16
    return bytes(pb.memory[bank, base + i] for i in range(16))


def bg_tile(pb, tile, bank):
    # LCDC.4 clear: BG/window tiles 0..127 read 0x9000, 128..255 read 0x8800.
    base = (0x9000 if tile < 128 else 0x8000) + tile * 16
    return bytes(pb.memory[bank, base + i] for i in range(16))


def hero_oam(pb):
    return [tuple(pb.memory[0xFE00 + s * 4 + k] for k in range(4))
            for s in range(4)]


def hud_b_box(pb):
    """(tile, attr) of the two HUD cells of the equipped-B box."""
    base = 0x9C00 if pb.memory[0xFF40] & 0x40 else 0x9800
    return [(pb.memory[0, base + col], pb.memory[1, base + col])
            for col in (10, 11)]


def assert_hud_b(pb, where):
    (letter, lattr), (_icon, _iattr) = hud_b_box(pb)
    got = bg_tile(pb, letter, 1 if lattr & S_BANK1 else 0)
    assert got == LETTER_B, (
        f"{where}: the HUD B box does not show the gold B letter "
        f"(tile {letter}, attr 0x{lattr:02X}): {got.hex()}")


def walk(pb, class_id, state, frames_dir, seen):
    art = authored(class_id)
    name = CLASSES[class_id]
    for direction in DIRECTIONS:
        pb.button_press(direction)
        for _ in range(40):
            pb.tick()
            if state == "powered":
                pb.memory[TRANSFORM] = 100       # hold the 18s form open
            pb.memory[PLAYER + 15] = 0           # no i-frame blink frames
            oam = hero_oam(pb)
            if not all(y and x for y, x, _t, _p in oam):
                continue
            key = tuple((t, p & (S_FLIPX | S_BANK1)) for _y, _x, t, p in oam)
            where = f"{name} {state} walking {direction}, OAM tiles {key}"
            # Save the frame first so a broken one is still captured.
            if (state, key) not in seen:
                seen[(state, key)] = direction
                if frames_dir is not None:
                    y, x = oam[0][0] - 16, oam[0][1] - 8
                    tag = "-".join(str(t) + ("f" if p else "") for t, p in key)
                    pb.screen.image.convert("RGB").crop(
                        (x - 4, y - 4, x + 20, y + 20)).resize(
                        (192, 192), 0).save(
                        frames_dir / f"{name}-{state}-{direction}-{tag}.png")
            for tile, prop in key:
                assert not prop & S_BANK1, f"{where}: hero tile in bank 1"
                assert tile in art, f"{where}: tile {tile} is not {name} art"
                got = vram_tile(pb, tile, 0)
                assert got == art[tile], (
                    f"{where}: tile {tile} does not hold its authored art; "
                    f"VRAM {got.hex()} != {art[tile].hex()}"
                    + (" (it is the HUD B letter)" if got == LETTER_B else ""))
        pb.button_release(direction)
        pb.tick(4)
    assert_hud_b(pb, f"{name} {state}")


def check_class(class_id, frames_dir):
    name = CLASSES[class_id]
    pb = boot(class_id)
    assert pb.memory[PLAYER] == class_id, f"did not enter as {name}"
    pb.tick(30)
    seen = {}
    walk(pb, class_id, "normal", frames_dir, seen)
    normal = {k for s, k in seen if s == "normal"}
    assert len(normal) >= 3, f"{name}: normal walk showed only {normal}"

    # The real A+B chord at full MP, as test_convergence_transform does.
    pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
    pb.memory[PLAYER + 19] = 0
    pb.button_press("a")
    pb.button_press("b")
    pb.tick()
    pb.button_release("a")
    pb.button_release("b")
    for _ in range(8):
        if pb.memory[TRANSFORM] > 0:
            break
        pb.tick()
    assert pb.memory[TRANSFORM] > 0, f"{name} did not start Convergence"
    pb.tick(20)
    walk(pb, class_id, "powered", frames_dir, seen)
    powered = {k for s, k in seen if s == "powered"}
    step = {STEP + class_id * 2, STEP + class_id * 2 + 1}
    strides = [k for k in powered if {k[2][0], k[3][0]} == step]
    assert len(strides) == 2, (
        f"{name}: powered walk should alternate two stride strips, "
        f"saw {sorted(powered)}")
    assert {k[2][1] for k in strides} == {0, S_FLIPX}, strides
    pb.stop(save=False)
    return len(normal), len(powered)


def main():
    frames_dir = None
    if "--frames" in sys.argv:
        frames_dir = Path(sys.argv[sys.argv.index("--frames") + 1])
        frames_dir.mkdir(parents=True, exist_ok=True)
    counts = [check_class(c, frames_dir) for c in range(5)]
    print(f"[ascended-walk-tiles] PASS five classes x 4 directions: "
          f"{sum(n for n, _ in counts)} normal and "
          f"{sum(p for _, p in counts)} powered-up walk frames all hold "
          f"their authored art; HUD B box intact")


if __name__ == "__main__":
    main()
