import os, glob, subprocess, numpy as np, gbc
from PIL import Image, ImageDraw
P = "/workspace/quintra-intro/panels/"; OUT = "/workspace/quintra-intro/"
HER = gbc.heroes(); CLASS_COL = [(247,140,60),(90,210,80),(170,120,247),(90,180,247),(247,220,60)]
BLACK = (8, 0, 24)
def L(n): return Image.open(P + n + ".png").convert("RGB")
def fade(im, k):  # k in 0..4 (0 = full, 4 = black), GBC-style 4-step palette fade
    a = np.asarray(im, float) * (1 - k/4) + np.array(BLACK) * (k/4)
    return Image.fromarray(gbc.to555(a))
def whiten(im, k):
    a = np.asarray(im, float); a = a + (255 - a) * (k/4)
    return Image.fromarray(gbc.to555(a))
def ease(t): t = min(max(t, 0), 1); return t*t*(3-2*t)
def screen(): return Image.new("RGB", (160, 144), BLACK)
def band(im, l1, l2=""):
    d = ImageDraw.Draw(im); d.rectangle([0, 112, 159, 143], fill=BLACK)
    if l1: im = gbc.text_center(im, 15, l1)
    if l2: im = gbc.text_center(im, 16, l2)
    return im
def put(im, sp, x, y, k=0):
    sp = sp if k == 0 else Image.fromarray(np.dstack([gbc.to555(np.asarray(sp)[..., :3]*(1-k/4) + np.array(BLACK)*(k/4)), np.asarray(sp)[..., 3]]))
    im.paste(sp, (int(x), int(y)), sp); return im
def walk(sp, f): return sp.transpose(Image.FLIP_LEFT_RIGHT) if (f // 8) % 2 else sp
def frame_box(im, x0, y0, w, h):
    d = ImageDraw.Draw(im)
    d.rectangle([x0-6, y0-6, x0+w+5, y0+h+5], outline=(200, 200, 216))
    d.rectangle([x0-3, y0-3, x0+w+2, y0+h+2], outline=(96, 88, 128))
    return im
def bosses():
    out = []
    files = sorted(glob.glob("/workspace/quintra-intro/ref/docs/showcase/assets/boss-0*.png"))
    files = [f for f in files if "kilnback" not in f]
    for f in files:
        a = np.asarray(Image.open(f).convert("RGB")).astype(float)
        mx, mn = a.max(2), a.min(2); sat = (mx - mn) > 70
        best, bx = -1, (0, 0)
        for y in range(8, 128-32, 8):
            for x in range(0, 160-48, 8):
                s = sat[y:y+32, x:x+48].sum()
                if s > best: best, bx = s, (x, y)
        out.append(Image.fromarray(a[bx[1]:bx[1]+32, bx[0]:bx[0]+48].astype(np.uint8)))
    return out
def save(frames, name, step=2):
    os.makedirs(os.path.dirname(OUT + name), exist_ok=True)
    fr = frames[::step]; dur = int(1000 * step / 60)
    fr[0].save(OUT + name + ".gif", save_all=True, append_images=fr[1:], duration=dur, loop=0, optimize=False)
    big = [f.resize((640, 576), Image.NEAREST) for f in fr]
    big[0].save(OUT + name + "-4x.gif", save_all=True, append_images=big[1:], duration=dur, loop=0, optimize=False)
    d = "/tmp/q-mp4"; os.makedirs(d, exist_ok=True)
    for f in glob.glob(d + "/*.png"): os.remove(f)
    for i, f in enumerate(big): f.save(f"{d}/{i:05d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(60/step), "-i", f"{d}/%05d.png",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", OUT + name + "-4x.mp4"], check=True)
    print("saved", name, len(fr), "frames", round(len(frames)/60, 1), "s")
