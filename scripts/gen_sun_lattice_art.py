#!/usr/bin/env python3
"""Hand-pixeled Sun Lattice mirror and animated beam tiles (issue #250).

Prints the C arrays pasted into src/game/sun_lattice.c. Each tile is drawn
below as 8 rows of colour indices 0..3, then packed as GB 2bpp.

Palettes at runtime: beams and rotatable mirrors share BGPAL_CRYSTAL, the
stage's glowing accent (0 = dark, 1 = saturated, 2 = bright, 3 = near
white), so the light is the colour of the glass that throws it and stands
out on every stage's floor. Fixed mirrors use BGPAL_WALL, so they look dull.

Run: python3 scripts/gen_sun_lattice_art.py [--preview out.png]
"""
import sys

FRAMES = 4


def pack(rows):
    out = []
    for row in rows:
        lo = hi = 0
        for x, c in enumerate(row):
            lo |= (c & 1) << (7 - x)
            hi |= (c >> 1) << (7 - x)
        out += [lo, hi]
    return out


def beam_h(frame):
    """Horizontal beam: white-hot core, bright halo, saturated edge and a
    dark outline, with a swell that travels 2px a frame so four frames loop
    seamlessly across an 8px cell."""
    profile = (0, 1, 2, 3, 3, 2, 1, 0)
    rows = [[profile[y]] * 8 for y in range(8)]
    for dx in (0, 1):
        x = (frame * 2 + dx) % 8
        # The swell pushes every band outward by a pixel.
        for y, c in enumerate((1, 2, 3, 3, 3, 3, 2, 1)):
            rows[y][x] = c
    # A cooler mote runs the other way inside the core: the shimmer.
    rows[3 + (frame & 1)][(5 - frame * 2) % 8] = 2
    return rows


def transpose(rows):
    return [[rows[x][y] for x in range(8)] for y in range(8)]


def beam_v(frame):
    return transpose(beam_h(frame))


def beam_x(frame):
    """Crossing: the brighter of the two beams wins each pixel, and the
    corners of the centre breathe."""
    h, v = beam_h(frame), beam_v(frame)
    rows = [[max(h[y][x], v[y][x]) for x in range(8)] for y in range(8)]
    if frame & 1:
        for x, y in ((2, 2), (5, 2), (2, 5), (5, 5)):
            rows[y][x] = 3
    return rows


def mirror(frame):
    """Angled mirror, '/' as drawn (hflip gives '\\'). A framed pane seen
    edge-on from above: dark frame lines either side of a bright glass face,
    square mounts at both ends, and a shade that slides along the glass so
    the face visibly shines."""
    rows = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(8):
            d = x + y
            if d in (5, 9):
                rows[y][x] = 1
            elif d in (6, 7, 8):
                rows[y][x] = 3
    # Mounts: the frame wraps both ends of the pane.
    for x, y in ((6, 0), (7, 0), (7, 1), (7, 2), (0, 6), (0, 7), (1, 7), (0, 5)):
        rows[y][x] = 1
    # The sliding shade: two glass cells a tone darker, moving up-right
    # along the middle of the pane.
    for k in range(2):
        x = (1 + frame * 2 + k) % 8
        y = 7 - x
        if 0 < x < 7:
            rows[y][x] = 2
    # The back of the pane stays a tone darker so the lit face (up-left)
    # shows which way the mirror throws light.
    for x in range(2, 7):
        rows[8 - x][x] = 2
    return rows


def c_array(name, tiles, per_frame):
    lines = [f"static const u8 {name}[{FRAMES}][{per_frame * 16}] = {{"]
    for frame in tiles:
        flat = [b for t in frame for b in pack(t)]
        lines.append("    {")
        for i in range(0, len(flat), 16):
            lines.append("        " + " ".join(f"0x{b:02X}," for b in flat[i:i + 16]))
        lines.append("    },")
    lines.append("};")
    return "\n".join(lines)


def preview(path):
    from PIL import Image
    pal = [(56, 16, 16), (128, 56, 40), (184, 96, 56), (240, 160, 96)]
    glass = [(40, 8, 0), (224, 80, 16), (248, 176, 32), (248, 248, 160)]
    img = Image.new("RGB", (FRAMES * 9 * 8, 4 * 9 * 8), (0, 0, 0))
    for f in range(FRAMES):
        for r, (tile, p) in enumerate((
                (mirror(f), glass), (beam_h(f), glass),
                (beam_v(f), glass), (beam_x(f), glass))):
            for y in range(8):
                for x in range(8):
                    c = p[tile[y][x]]
                    for sy in range(8):
                        for sx in range(8):
                            img.putpixel((f * 72 + x * 8 + sx, r * 72 + y * 8 + sy), c)
    img.save(path)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--preview":
        preview(sys.argv[2])
        return
    print("// vane (frame 0)")
    print("    " + " ".join(f"0x{b:02X}," for b in pack(mirror(0))))
    for name, fn in (("beam_h", beam_h), ("beam_v", beam_v), ("beam_x", beam_x)):
        print(f"// {name} (frame 0)")
        print("    " + " ".join(f"0x{b:02X}," for b in pack(fn(0))))
    print(c_array("sl_vane_anim", [[mirror(f)] for f in range(FRAMES)], 1))
    print(c_array("sl_beam_anim",
                  [[beam_h(f), beam_v(f), beam_x(f)] for f in range(FRAMES)], 3))


if __name__ == "__main__":
    main()
