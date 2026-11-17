import numpy as np
from anim import *
VX, VY = 24, 8  # vignette at tile col 3, row 1 (112x96), ROV-style double frame
def vignette_base(im, v, t=0):
    im = frame_box(im, VX, VY, 112, 96); im.paste(v, (VX, VY)); return im
def hollow_pal(v):
    a = np.asarray(v, float); g = a.mean(2, keepdims=True)
    return Image.fromarray(gbc.to555(np.clip(g * np.array([0.75, 0.95, 1.15]) + a * 0.15, 0, 255)))
RG = L("riftgate")
JAG = [0, 2, 1, 3, 0, -1, 2, 1, 0, 3, 1, -1, 0, 2]  # per-8px-row edge offsets (4 edge-tile shapes, X-flipped)
_rg = np.asarray(RG).astype(int)
_mag = (_rg[..., 0] > 170) & (_rg[..., 2] > 140) & (_rg[..., 1] < 130)
BOUNDS = {}
for y in range(0, 80):
    xs = np.where(_mag[y, 20:92])[0] + 20
    if len(xs) >= 2 and xs.max() - xs.min() > 8: BOUNDS[y] = (xs.min() + 2, xs.max() - 1)
def rift_open(step, src):
    a = np.asarray(src).copy(); cx = 56
    if step >= 5: return Image.fromarray(a)
    for y, (l, r) in BOUNDS.items():
        half = [0, 4, 9, 15, 21][step] + (JAG[(y // 4) % len(JAG)] if step else 0)
        x0, x1 = max(l, cx - half), min(r, cx + half)
        a[y, l:x0] = (16, 0, 32); a[y, x1:r] = (16, 0, 32)
        a[y, max(l, x0 - 2):x0] = (240, 80, 220); a[y, x1:min(r, x1 + 2)] = (240, 80, 220)
    return Image.fromarray(a)
def hero_in(im, f, hx, hy, k):
    if k >= 4: return im
    sp = walk(HER[0], f)
    if hy + 16 > VY + 96: sp = sp.crop((0, 0, 16, max(1, int(VY + 96 - hy))))
    return put(im, sp, hx, hy, k)
def riftwild_enter(hollow=False):
    fr = []; src = hollow_pal(RG) if hollow else RG
    for t in range(180):
        im = screen()
        v = rift_open(min(5, max(0, (t - 10) // 12)), src)
        im = vignette_base(im, v)
        hy = VY + 100 - 46 * ease((t - 30) / 100); k = 0 if t < 126 else min(4, (t - 126) // 3)
        im = hero_in(im, t, VX + 48, hy, k)
        if 134 <= t < 142: im = whiten(im, 3 if t < 138 else 2)
        im = band(im, *(("HOLLOW RIFTWILD", "THE WILD FORGETS") if hollow else ("WAKING RIFTWILD", "THE WILD REMEMBERS")))
        if t < 16: im = fade(im, 4 - t * 4 // 16)
        if t >= 160: im = whiten(im, min(4, (t - 160) // 4))
        fr.append(im)
    return fr
EM0 = L("ember")
def darken_path(v):
    a = np.asarray(v).astype(float); sat = a.max(2) - a.min(2)
    m = np.zeros(a.shape[:2], bool); m[60:] = sat[60:] < 60  # grey cobbles on the walkway -> charcoal
    a[m] *= 0.55; return Image.fromarray(gbc.to555(a))
EM = darken_path(EM0)
def lava_cycle(v, phase):
    a = np.asarray(v).astype(int); out = a.copy()
    lava = sorted([c for c in {tuple(c) for c in a.reshape(-1, 3)} if c[0] > 180 and c[2] < 120 and c[1] > 40], key=lambda c: c[1])
    for i, c in enumerate(lava):
        out[(a == c).all(2)] = lava[(i + phase) % len(lava)]
    return Image.fromarray(out.astype(np.uint8))
def ember_depths():
    fr = []
    for t in range(180):
        im = vignette_base(screen(), lava_cycle(EM, t // 10))
        hy = VY + 100 - 46 * ease((t - 16) / 100); k = 0 if t < 92 else min(4, (t - 92) // 9)
        im = hero_in(im, t, VX + 48, hy, k)
        d = ImageDraw.Draw(im)
        if 56 < t < 64: d.rectangle([VX + 40, VY + 46, VX + 72, VY + 50], fill=(24, 8, 8))  # blink
        if 132 <= t < 162 and (t // 4) % 2 == 0:
            for ex in (VX + 47, VX + 63): d.rectangle([ex, VY + 47, ex + 2, VY + 49], fill=(255, 240, 120))
        im = band(im, "EMBER DEPTHS", "THE KILN WAKES")
        if t < 16: im = fade(im, 4 - t * 4 // 16)
        if t >= 164: im = fade(im, min(4, (t - 164) // 4))
        fr.append(im)
    return fr
if __name__ == "__main__":
    import glob, os
    for g in glob.glob(OUT + "transitions/*"): os.remove(g)
    a = riftwild_enter(); save(a, "transitions/riftwild-enter")
    h = riftwild_enter(hollow=True); save(h, "transitions/riftwild-enter-hollow")
    b = ember_depths(); save(b, "transitions/stage3-ember-depths")
    ks = [a[22], a[46], a[100], a[136], h[100], b[40], b[100], b[140]]
    sheet = Image.new("RGB", (4 * 168, 2 * 152), (40, 40, 48))
    for i, k in enumerate(ks): sheet.paste(k, ((i % 4) * 168 + 4, (i // 4) * 152 + 4))
    sheet.resize((sheet.size[0] * 2, sheet.size[1] * 2), Image.NEAREST).save(OUT + "transitions/transitions-sheet.png")
