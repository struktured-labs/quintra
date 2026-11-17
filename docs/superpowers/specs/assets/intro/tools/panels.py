import json, gbc, numpy as np
from PIL import Image
R = "/workspace/quintra-intro/gen/raw/"
O = "/workspace/quintra-intro/panels/"
import os; os.makedirs(O, exist_ok=True)
def sheet_crop(i, inset=14):
    im = Image.open(R + "sheet-0.png").convert("RGB"); a = np.asarray(im).sum(2)
    # find gutters: rows/cols that are mostly black
    def bands(prof):
        dark = prof < 60*3; segs = []; s = None
        for k, d in enumerate(dark):
            if not d and s is None: s = k
            if d and s is not None:
                if k - s > 150: segs.append((s, k))
                s = None
        if s is not None and len(dark) - s > 150: segs.append((s, len(dark)))
        return segs
    c = im.size[0] / 3; x0, x1 = int((i % 3)*c), int((i % 3 + 1)*c); y0, y1 = int((i//3)*c), int((i//3+1)*c)
    return im.crop((x0+inset, y0+inset, x1-inset, y1-inset))
specs = {
  "valley":   (lambda: gbc.fit_img(R+"valley-0.png", 160, 240), 7, 356),
  "torn":     (lambda: gbc.fit_img(R+"torn-0.png", 160, 240), 7, 400),
  "shrine":   (lambda: gbc.fit_img(R+"shrine-0.png", 160, 160).crop((0, 24, 160, 136)), 7, 192),
  "cliff":    (lambda: gbc.fit_img(R+"cliff2-0.png", 192, 128), 7, 320),
  "riftgate": (lambda: gbc.fit_img(R+"riftgate-0.png", 112, 112).crop((0, 8, 112, 104)), 6, 128),
  "riftgate_b": (lambda: gbc.fit_img(R+"riftgate-1.png", 112, 112).crop((0, 8, 112, 104)), 6, 128),
  "ember":    (lambda: gbc.fit_img(R+"ember-0.png", 112, 112).crop((0, 8, 112, 104)), 6, 128),
  "ember_b":  (lambda: gbc.fit_img(R+"ember-1.png", 112, 112).crop((0, 8, 112, 104)), 6, 128),
}
def busts():
    im = Image.open(R + "busts-0.png").convert("RGB"); W, H = im.size
    out = Image.new("RGB", (160, 112), (0, 0, 0))
    for i in range(9):
        c = im.crop((int((i % 3) * W / 3) + 6, int((i // 3) * H / 3) + 6, int((i % 3 + 1) * W / 3) - 6, int((i // 3 + 1) * H / 3) - 6))
        out.paste(c.resize((48, 32), Image.LANCZOS), (4 + (i % 3) * 52, 2 + (i // 3) * 36))
    return out
specs["busts"] = (busts, 7, 216)
names = ["crystal","verdant","ember","frost","mire","shadow","golden","bloodmoon","void"]
for i, n in enumerate(names):
    specs["stage_%d_%s" % (i+1, n)] = ((lambda i=i: sheet_crop(i).resize((112, 96), Image.LANCZOS)), 6, 128)
stats = {}
for k, (fn, npal, tgt) in specs.items():
    src = fn(); src.save(O + k + "_src.png")
    q, pals, labs = gbc.quantize(src, npal=npal)
    q.save(O + k + "_full.png"); q = gbc.reduce_tiles(q, labs, tgt)
    q.save(O + k + ".png"); st = gbc.tile_stats(q, labs); stats[k] = st; print(k, st)
json.dump(stats, open(O + "stats.json", "w"), indent=1)
