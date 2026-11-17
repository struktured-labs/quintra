from anim import *
from transitions import VX, VY, vignette_base
STAGES = [("crystal","CRYSTAL CAVERNS","CRYSTALS LISTEN"),("verdant","VERDANT HOLLOW","THE ROOTS HUNGER"),
 ("ember","EMBER DEPTHS","THE KILN WAKES"),("frost","FROST VAULT","NOTHING THAWS HERE"),
 ("mire","TOXIC MIRE","A DARK HEART BEATS"),("shadow","SHADOW KEEP","THE GATE WATCHES"),
 ("golden","GOLDEN TEMPLE","THE SUN NEVER SETS"),("bloodmoon","BLOODMOON","THE MOON BLEEDS"),
 ("void","VOID SANCTUM","WHERE NAMES END")]
ks = []
for i, (k, name, line) in enumerate(STAGES):
    im = vignette_base(screen(), L("stage_%d_%s" % (i + 1, k)))
    im = band(im, name, line); ks.append(im)
sheet = Image.new("RGB", (3 * 168, 3 * 152), (40, 40, 48))
for i, k in enumerate(ks): sheet.paste(k, ((i % 3) * 168 + 4, (i // 3) * 152 + 4))
sheet.resize((sheet.size[0] * 2, sheet.size[1] * 2), Image.NEAREST).save(OUT + "transitions/all-stages-sheet.png")
