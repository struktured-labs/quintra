import numpy as np
from anim import *
VAL, TORN, SHR, CLF, BUST = L("valley"), L("torn"), L("shrine"), L("cliff"), L("busts")
NAMES = [("WOLFKIN", "FANG OF FLAME"), ("SAURAN", "SCALE OF STONE"), ("CORVIN", "WING OF SHADOW"),
         ("PICSEAN", "FIN OF TIDE"), ("VESPINE", "STING OF BLOOM")]
SHOTS = [(0, 180, "1 roads"), (180, 420, "2 tear"), (420, 600, "3 colossi"), (600, 780, "4 spirits"),
         (780, 1020, "5 chosen"), (1020, 1200, "6 bind"), (1200, 1380, "7 title")]
LAND_Y = 88  # source rows >= this are 'land' (dimmed by palette in shot 2)
def tear(r):  # valley + Rift overlay tiles (rows 0..7 only) revealed within radius r tiles
    a, b = np.asarray(VAL).copy(), np.asarray(TORN)
    for ty in range(8):
        for tx in range(20):
            if (tx - 10) ** 2 + ((ty - 4) * 1.6) ** 2 <= r * r:
                a[ty*8:ty*8+8, tx*8:tx*8+8] = b[ty*8:ty*8+8, tx*8:tx*8+8]
    return a
def render(f):
    s, e, sid = next(x for x in SHOTS if x[0] <= f < x[1]); t = f - s
    im = screen(); fin, fout = True, True
    if sid == "1 roads":
        scy = int(128 * ease((t - 20) / 140)); fout = False
        im.paste(VAL.crop((0, scy, 160, scy + 112)), (0, 0))
        im = band(im, "ONCE EVERY ROAD", "KNEW ITS OWN NAME")
    elif sid == "2 tear":
        fin = False
        a = tear([0, 3, 6, 10, 30][min(4, t // 20)]).astype(float)
        k = 0 if t < 150 else (1 if t < 190 else 2)  # 2 palette steps toward violet on land palettes
        a[LAND_Y:] = a[LAND_Y:] * (1 - 0.28*k) + np.array([40, 0, 72]) * 0.28*k
        src = Image.fromarray(gbc.to555(a))
        scy = int(128 * ease((t - 120) / 110)); sx = sy = 0
        if 20 <= t < 90: sx, sy = [(2, 0), (-2, 1), (1, -1), (-1, 0)][(t // 3) % 4]
        im.paste(src.crop((0, scy, 160, scy + 112)), (sx, sy))
        if 20 <= t < 24: im = whiten(im, 1)
        im = band(im, *(("THEN THE SKY TORE", "") if t < 120 else ("THE RIFT DEVOURED", "ROADS AND NAMES")))
    elif sid == "3 colossi":
        a = np.asarray(BUST).copy()
        for i in range(9):
            at = 12 + i * 12; x, y = 4 + (i % 3) * 52, 2 + (i // 3) * 36
            if t < at: a[y:y+32, x:x+48] = 0
        im.paste(Image.fromarray(a), (0, 0))
        for i in range(9):
            at = 12 + i * 12
            if 0 <= t - at < 2:
                x, y = 4 + (i % 3) * 52, 2 + (i // 3) * 36
                im.paste(whiten(im.crop((x, y, x + 48, y + 32)), 3), (x, y))
        im = band(im, "NINE COLOSSI ROSE", "IN THE WORLD BELOW")
    elif sid == "4 spirits":
        im.paste(SHR, (0, 0)); d = ImageDraw.Draw(im)
        for i, x in enumerate([22, 50, 80, 110, 138]):
            y = 62 - ((t * 0.5 + i * 23) % 62); c = CLASS_COL[i]
            d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=c); d.point((x, y), fill=(255, 255, 255))
        im = band(im, "FIVE SPIRITS WOKE", "TO BEAR THE SPARKS")
    elif sid == "5 chosen":
        im = gbc.text_center(im, 1, "FIVE ARE CHOSEN")
        for i in range(5):
            at = 16 + i * 32
            if t < at: continue
            row = 3 + i * 3; left = i % 2 == 0
            sx = 8 if left else 136; tx = 4 if left else 2
            slide = min(1, (t - at) / 16)
            x = (sx - 24 + 24 * slide) if left else (sx + 24 - 24 * slide)
            put(im, walk(HER[i], t) if slide < 1 else HER[i], x, row * 8 - ((t // 16 + i) % 2))
            n, ep = NAMES[i]
            im = gbc.text(im, tx, row, n); im = gbc.text(im, tx, row + 1, ep, (190, 190, 210))
    elif sid == "6 bind":
        sx = int(32 * (1 - ease(t / 170))); sy = int(16 * ease(t / 170))
        im.paste(CLF.crop((sx, sy, sx + 160, sy + 112)), (0, 0))
        im = band(im, *(("INTO THE WILD BELOW", "") if t < 80 else ("BIND THE RIFT", "ERE ALL NAMES FADE")))
    elif sid == "7 title":
        fout = False
        d = ImageDraw.Draw(im); d.line([(12, 63), (148, 63)], fill=(96, 88, 128))
        for i in range(5):
            p = min(1, max(0, (t - i * 8) / 90)); x = -20 + p * (36 + 28 * i)
            put(im, walk(HER[i], t + i * 5) if p < 1 else HER[i], x, 47 - ((t // 20 + i) % 2 if p >= 1 else 0))
        im = gbc.text_center(im, 3, "QUINTRA")
        if t < 100:
            im = gbc.text_center(im, 10, "CHOOSE YOUR VESSEL"); im = gbc.text_center(im, 12, "REKINDLE THE DAWN")
        elif (t // 30) % 2 == 0: im = gbc.text_center(im, 12, "PRESS  START")
    if fin and t < 16: im = fade(im, 4 - t * 4 // 16)
    if fout and e - f <= 16: im = fade(im, 4 - (e - f - 1) * 4 // 16)
    return im
if __name__ == "__main__":
    frames = [render(f) for f in range(SHOTS[-1][1])]
    import glob, os
    for g in glob.glob(OUT + "intro/*"): os.remove(g)
    save(frames, "intro/quintra-intro")
    picks = [(0, 120, "1-roads"), (180, 90, "2a-tear"), (180, 215, "2b-devour"), (420, 140, "3-colossi"),
             (600, 120, "4-spirits"), (780, 200, "5-chosen"), (1020, 140, "6-bind"), (1200, 60, "7a-vessel"), (1200, 160, "7b-title")]
    kf = []
    for s, o, n in picks:
        k = frames[s + o]; k.save(OUT + "intro/shot-%s.png" % n); kf.append(k)
    sheet = Image.new("RGB", (5 * 168, 2 * 152), (40, 40, 48))
    for i, k in enumerate(kf): sheet.paste(k, ((i % 5) * 168 + 4, (i // 5) * 152 + 4))
    sheet.resize((sheet.size[0] * 2, sheet.size[1] * 2), Image.NEAREST).save(OUT + "intro/storyboard-sheet.png")
