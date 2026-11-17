"""GBC helpers: tile/palette quantizer, real font, hero sprites, tile stats."""
import numpy as np
from PIL import Image
REF = "/workspace/quintra-intro/ref/docs"

def to555(c):  # snap RGB to RGB555 grid
    return (np.round(np.asarray(c, float) / 255 * 31) * 255 / 31).astype(np.uint8)

def _kmeans(X, k, iters=12, seed=0):
    rng = np.random.default_rng(seed)
    if len(X) <= k:
        C = np.vstack([X, np.repeat(X[:1], k - len(X), 0)]) if len(X) else np.zeros((k, 3))
        return C.astype(float)
    # kmeans++ init
    C = [X[rng.integers(len(X))]]
    for _ in range(k - 1):
        d = np.min(((X[:, None] - np.array(C)[None]) ** 2).sum(2), 1)
        C.append(X[rng.choice(len(X), p=d / d.sum())] if d.sum() > 0 else X[0])
    C = np.array(C, float)
    for _ in range(iters):
        lab = np.argmin(((X[:, None] - C[None]) ** 2).sum(2), 1)
        for j in range(k):
            if (lab == j).any(): C[j] = X[lab == j].mean(0)
    return C

def quantize(img, npal=7, ncol=4, force_black=False, iters=10, seed=0):
    """Per-8x8-tile palette assignment, npal palettes of ncol colours (RGB555).
    Returns (quantized PIL image, palettes array, per-tile palette index)."""
    a = np.asarray(img.convert("RGB"), float)
    H, W = a.shape[:2]; th, tw = H // 8, W // 8
    tiles = a[:th*8, :tw*8].reshape(th, 8, tw, 8, 3).transpose(0, 2, 1, 3, 4).reshape(th*tw, 64, 3)
    # seed palettes: cluster tile mean colours
    feats = np.concatenate([tiles.mean(1), tiles.std(1)], 1)
    C = _kmeans(feats, npal, seed=seed)
    lab = np.argmin(((feats[:, None] - C[None]) ** 2).sum(2), 1)
    pals = np.zeros((npal, ncol, 3))
    def fit(j):
        px = tiles[lab == j].reshape(-1, 3)
        if len(px) == 0: return pals[j]
        sub = px[np.random.default_rng(j).choice(len(px), min(len(px), 4000), replace=False)]
        k = ncol - 1 if force_black else ncol
        P = _kmeans(sub, k, seed=j)
        if force_black: P = np.vstack([[0, 0, 0], P])
        return P
    for it in range(iters):
        for j in range(npal): pals[j] = fit(j)
        # reassign tiles to palette minimising error
        err = np.zeros((len(tiles), npal))
        for j in range(npal):
            d = ((tiles[:, :, None] - pals[j][None, None]) ** 2).sum(3)
            err[:, j] = d.min(2).sum(1)
        lab = err.argmin(1)
    pals = np.array([[to555(c) for c in p] for p in pals]).astype(float)
    out = np.zeros_like(tiles)
    for j in range(npal):
        m = lab == j
        if not m.any(): continue
        d = ((tiles[m][:, :, None] - pals[j][None, None]) ** 2).sum(3)
        out[m] = pals[j][d.argmin(2)]
    q = out.reshape(th, tw, 8, 8, 3).transpose(0, 2, 1, 3, 4).reshape(th*8, tw*8, 3)
    return Image.fromarray(q.astype(np.uint8)), pals.astype(np.uint8), lab.reshape(th, tw)

def tile_stats(qimg, labs):
    """Unique tiles as 2bpp patterns (palette-index form), deduped incl. H/V flips."""
    a = np.asarray(qimg.convert("RGB")).astype(int)
    H, W = a.shape[:2]; seen = set(); uniq = 0
    for ty in range(H // 8):
        for tx in range(W // 8):
            t = a[ty*8:ty*8+8, tx*8:tx*8+8]
            cols = {}
            idx = np.zeros((8, 8), int)
            # palette-index form: rank colours by luminance within tile's palette
            flat = [tuple(c) for c in t.reshape(-1, 3)]
            order = sorted(set(flat), key=lambda c: c[0]*3 + c[1]*6 + c[2])
            for i, c in enumerate(flat): idx.flat[i] = order.index(c)
            keys = [idx, idx[:, ::-1], idx[::-1], idx[::-1, ::-1]]
            if any(k.tobytes() in seen for k in keys): continue
            seen.add(idx.tobytes()); uniq += 1
    return {"cells": (H//8)*(W//8), "unique_tiles": uniq, "tile_bytes": uniq*16,
            "map_bytes": (H//8)*(W//8)*2, "palettes": int(len(set(labs.flat)))}

def fit_img(path, w, h, box=None):
    im = Image.open(path).convert("RGB")
    if box: im = im.crop(box)
    return im.resize((w, h), Image.LANCZOS)

# ---------- font from real ROM screenshots ----------
_FONT = None
def font():
    global _FONT
    if _FONT: return _FONT
    g = {}
    def harvest(path, items):
        a = np.asarray(Image.open(path).convert("RGB")).astype(int)
        lum = a.sum(2)
        for col, row, s in items:
            for i, ch in enumerate(s):
                if ch == " ": continue
                t = lum[row*8:row*8+8, (col+i)*8:(col+i)*8+8]
                g.setdefault(ch, (t > 400))
    harvest(f"{REF}/media/title.png", [(6,4,"QUINTRA"),(5,6,"THE  ROGUELIKE"),(2,8,"WHEN THE SKY TORE"),
        (2,9,"FIVE SPIRITS WOKE"),(4,12,"PRESS  START"),(1,16,"SELECT RECORDS HELP")])
    harvest(f"{REF}/media/class_preview.png", [(3,1,"CHOOSE YOUR HERO"),(4,3,"WOLFKIN"),(4,4,"SAURAN"),
        (4,5,"CORVIN"),(4,6,"PICSEAN"),(4,7,"VESPINE"),(0,9,"ROLE RANGED HUNTER"),(0,10,"A RETURNING FEATHER"),
        (0,11,"B MARK   RAVEN DIVES"),(0,14,"HEALTH 14 MAGIC 8"),(0,15,"ATTACK 2 ARMOR 1"),(0,16,"SPEED 5 SEL EASY")])
    extra = {  # hand-drawn to match font_min (not in ROM yet; spec proposes adding them)
      "X": [".#....#.","..#..#..","...##...","...##...","..#..#..",".#....#."],
      "J": [".....#..",".....#..",".....#..",".....#..",".#...#..","..###..."],
      "Z": [".######.",".....#..","....#...","...#....","..#.....",".######."],
      ".": ["........","........","........","........","........","...##..."]}
    for ch, rows in extra.items():
        if ch not in g:
            m = np.zeros((8, 8), bool)
            for y, r in enumerate(rows): m[y+1] = [c == "#" for c in r]
            g[ch] = m
    _FONT = g; return g

def text(img, col, row, s, color=(255, 255, 255)):
    f = font(); a = np.array(img)
    for i, ch in enumerate(s):
        if ch == " ": continue
        m = f.get(ch)
        if m is None: raise KeyError("glyph missing: " + ch)
        x, y = (col+i)*8, row*8
        if 0 <= x < a.shape[1]-7 and 0 <= y < a.shape[0]-7:
            a[y:y+8, x:x+8][m] = color
    return Image.fromarray(a)

def text_center(img, row, s, color=(255, 255, 255)):
    return text(img, (20 - len(s)) // 2, row, s, color)

# ---------- hero sprites (16x16, transparent) ----------
def heroes():
    a = np.asarray(Image.open(f"{REF}/media/title.png").convert("RGB")).astype(int)
    bg = a[0, 0]; out = []
    for gmin, gmax in [(18,29),(46,57),(73,85),(102,113),(129,142)]:
        c = (gmin + gmax + 1) // 2; x0 = c - 8
        t = a[15:31, x0:x0+16]
        rgba = np.zeros((16, 16, 4), np.uint8); rgba[..., :3] = t
        rgba[..., 3] = (np.abs(t - bg).sum(2) > 30) * 255
        out.append(Image.fromarray(rgba))
    return out  # wolfkin, sauran, corvin, picsean, vespine

def sprite_tint(sp, k):
    a = np.array(sp).astype(float); a[..., :3] *= k
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))

def reduce_tiles(qimg, labs, target):
    """Greedy merge of most-similar tiles (same palette) until unique count <= target."""
    a = np.asarray(qimg.convert("RGB")).astype(int)
    H, W = a.shape[:2]; th, tw = H//8, W//8
    T = a.reshape(th, 8, tw, 8, 3).transpose(0, 2, 1, 3, 4).reshape(th*tw, 64, 3)
    L = labs.reshape(-1)
    keys = {}; uid = np.zeros(len(T), int); reps = []
    for i, t in enumerate(T):
        k = (L[i], t.tobytes())
        if k not in keys: keys[k] = len(reps); reps.append(i)
        uid[i] = keys[k]
    n = len(reps)
    if n <= target: return qimg
    R = T[reps].reshape(n, -1).astype(float); RL = L[reps]
    cnt = np.bincount(uid, minlength=n)
    parent = list(range(n))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    D = ((R[:, None] - R[None]) ** 2).sum(2)
    D[RL[:, None] != RL[None]] = np.inf
    np.fill_diagonal(D, np.inf)
    iu = np.triu_indices(n, 1); order = np.argsort(D[iu])
    alive = n
    for o in order:
        if alive <= target: break
        i, j = iu[0][o], iu[1][o]
        if not np.isfinite(D[i, j]): break
        ri, rj = find(i), find(j)
        if ri == rj: continue
        if cnt[ri] < cnt[rj]: ri, rj = rj, ri
        parent[rj] = ri; cnt[ri] += cnt[rj]; alive -= 1
    out = T.copy()
    for i in range(len(T)): out[i] = T[reps[find(uid[i])]]
    q = out.reshape(th, tw, 8, 8, 3).transpose(0, 2, 1, 3, 4).reshape(H, W, 3)
    return Image.fromarray(q.astype(np.uint8))
