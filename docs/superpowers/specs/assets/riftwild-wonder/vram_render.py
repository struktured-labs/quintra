"""Render the full 32x32 CGB BG map straight from PyBoy VRAM + palette RAM."""
from PIL import Image


def read_bg_palettes(pb):
    pals = []
    for i in range(64):
        pb.memory[0xFF68] = i
        pals.append(pb.memory[0xFF69])
    out = []
    for p in range(8):
        cols = []
        for c in range(4):
            lo, hi = pals[p * 8 + c * 2], pals[p * 8 + c * 2 + 1]
            v = lo | hi << 8
            r, g, b = v & 31, (v >> 5) & 31, (v >> 10) & 31
            cols.append((r * 255 // 31, g * 255 // 31, b * 255 // 31))
        out.append(cols)
    return out


def vram(pb, bank, a0, a1):
    old = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = bank
    data = bytes(pb.memory[a0:a1])
    pb.memory[0xFF4F] = old
    return data


def render_bg(pb, map_base=None):
    lcdc = pb.memory[0xFF40]
    if map_base is None:
        map_base = 0x9C00 if lcdc & 0x08 else 0x9800
    signed = not (lcdc & 0x10)
    tiles = [vram(pb, b, 0x8000, 0x9800) for b in (0, 1)]
    idx = vram(pb, 0, map_base, map_base + 1024)
    attr = vram(pb, 1, map_base, map_base + 1024)
    pals = read_bg_palettes(pb)
    img = Image.new("RGB", (256, 256))
    px = img.load()
    for ty in range(32):
        for tx in range(32):
            t = idx[ty * 32 + tx]
            a = attr[ty * 32 + tx]
            if signed:
                off = 0x1000 + (t - 256 if t >= 128 else t) * 16
            else:
                off = t * 16
            data = tiles[(a >> 3) & 1]
            pal = pals[a & 7]
            for y in range(8):
                sy = 7 - y if a & 0x40 else y
                lo, hi = data[off + sy * 2], data[off + sy * 2 + 1]
                for x in range(8):
                    sx = x if a & 0x20 else 7 - x
                    c = ((lo >> sx) & 1) | (((hi >> sx) & 1) << 1)
                    px[tx * 8 + x, ty * 8 + y] = pal[c]
    return img


def field_from_bg(pb, origin_x, origin_y, w=248, h=248):
    bg = render_bg(pb)
    # Wrap-around crop starting at the field origin.
    big = Image.new("RGB", (512, 512))
    for dy in (0, 256):
        for dx in (0, 256):
            big.paste(bg, (dx, dy))
    return big.crop((origin_x * 8, origin_y * 8,
                     origin_x * 8 + w, origin_y * 8 + h))


# room_render.c render_attr(): BGT id -> CGB BG palette slot (outdoor subset).
WALL, CRYSTAL, DOOR, CRACK, FLOOR = 1, 2, 3, 4, 0
ATTR = {2: WALL, 21: WALL, 37: WALL, 38: WALL, 39: WALL, 98: WALL, 109: WALL,
        110: WALL, 100: WALL, 103: WALL, 104: WALL, 25: WALL, 28: WALL,
        29: WALL, 30: WALL, 24: CRACK, 31: CRACK, 32: DOOR, 33: DOOR,
        99: DOOR, 106: DOOR, 22: CRYSTAL, 34: CRYSTAL, 96: CRYSTAL,
        97: CRYSTAL, 107: CRYSTAL, 101: CRYSTAL, 102: CRYSTAL, 108: CRACK,
        105: FLOOR, 3: DOOR}


def field_from_wram(pb, wide):
    """Render the logical 31x31 field from WRAM tile ids.

    room_draw_tilemap() writes the BGT id itself as the VRAM tile index and
    render_attr() as the palette, so this is the exact picture the hardware
    shows, minus the transient area label and sprites, and immune to the
    off-screen stale BG rows left behind by the streamed seam slide.
    """
    lcdc = pb.memory[0xFF40]
    signed = not (lcdc & 0x10)
    data = vram(pb, 0, 0x8000, 0x9800)
    pals = read_bg_palettes(pb)
    h, w = len(wide), len(wide[0])
    img = Image.new("RGB", (w * 8, h * 8))
    px = img.load()
    for ty in range(h):
        for tx in range(w):
            t = wide[ty][tx]
            off = (0x1000 + (t - 256 if t >= 128 else t) * 16) if signed \
                else t * 16
            pal = pals[ATTR.get(t, FLOOR)]
            for y in range(8):
                lo, hi = data[off + y * 2], data[off + y * 2 + 1]
                for x in range(8):
                    sx = 7 - x
                    c = ((lo >> sx) & 1) | (((hi >> sx) & 1) << 1)
                    px[tx * 8 + x, ty * 8 + y] = pal[c]
    return img
