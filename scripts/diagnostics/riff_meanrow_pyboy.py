"""riff_meanrow_pyboy.py — Reach Riff arena (D880=0x0D, FFBA=1) via the PROVEN
PyBoy teleport mechanism (map bank3, IE=0, simulate CALL 0x1A2B), then sample the
active tilemap for ~300 frames. For each NON-ZERO tile id: count, sum-of-screen-
row (0-17), min/max row, distinct rows, distinct cols, and current attr-palette
histogram (low 3 bits of VRAM bank1). Output: /tmp/riff/riff_meanrow_pyboy.log

Adapted from scripts/diagnostics/crystal_meanrow_pyboy.py (which produced a clean
349-tile arena dump). The mgba combo-teleport stack-redirect does NOT land in
headless mgba (D880 frozen at 0x02); the PyBoy CALL 0x1A2B path is the working one.

Run: uv run python scripts/diagnostics/riff_meanrow_pyboy.py
"""
import sys, os
from pyboy import PyBoy

ROM = "rom/working/penta_dragon_dx_teleport.gb"
BOSS = 1  # Riff -> D880 0x0D
OUTDIR = "/tmp/riff"
os.makedirs(OUTDIR, exist_ok=True)
LOG = os.path.join(OUTDIR, "riff_meanrow_pyboy.log")
logf = open(LOG, "w")
def log(m):
    logf.write(m + "\n"); logf.flush()

log(f"riff meanrow pyboy ROM={ROM} BOSS={BOSS} (D880 target=0x{0x0C+BOSS:02X})")

pb = PyBoy(ROM, window="null", cgb=True)
pb.set_emulation_speed(0)
m = pb.memory
rf = pb.register_file

# --- boot to title + auto-start ---
sched = [(180,186,'down'),(201,207,'a'),(261,267,'a'),(321,327,'a'),(381,387,'start'),(431,437,'a')]
held = None
for f in range(1,640):
    want = None
    for s,e,b in sched:
        if s<=f<e: want=b; break
    if want != held:
        if held: pb.button_release(held)
        if want: pb.button_press(want)
        held = want
    pb.tick(1,True)
if held: pb.button_release(held)

# walk right until in dungeon (D880=0x02)
for f in range(1400):
    if m[0xD880]==0x02 and m[0xFFC1]==1: break
    if f%40<8: pb.button_press('right')
    else: pb.button_release('right')
    pb.tick(1,True)
pb.button_release('right')
log(f"dungeon: D880=0x{m[0xD880]:02X} FFC1={m[0xFFC1]}")
if m[0xD880]!=0x02:
    log("FAIL: never reached dungeon"); pb.stop(save=False); logf.close(); sys.exit(1)
pb.tick(10,True)

# --- teleport via CALL 0x1A2B with IE=0 ---
m[0xFFBA]=BOSS; m[0xFFBF]=0
m[0x2000]=3          # map ROM bank 3 (MBC1)
m[0xFF99]=3
ie_save=m[0xFFFF]
m[0xFFFF]=0          # IE=0 — mask all IRQs during arena init
ret=rf.PC
sp=rf.SP-2
m[sp]=ret & 0xFF; m[sp+1]=(ret>>8)&0xFF
rf.SP=sp
rf.PC=0x1A2B
log(f"bank3 mapped, IE=0, FFBA={BOSS}, CALL 0x1A2B (ret=0x{ret:04X})")
for i in range(300):
    pb.tick(1,True)
    if m[0xD880]==(0x0C+BOSS): break
m[0xFFFF]=ie_save    # restore IE so VBlank/colorizer runs and paints attrs
expect=0x0C+BOSS
log(f"after CALL: D880=0x{m[0xD880]:02X} (want 0x{expect:02X}) FFBA={m[0xFFBA]} FFB7=0x{m[0xFFB7]:02X}")
if m[0xD880]!=expect:
    log("FAIL: arena did not load"); pb.screen.image.save(OUTDIR+"/riff_fail.png"); pb.stop(save=False); logf.close(); sys.exit(1)

# settle: let the arena's per-frame loop + colorizer paint the tilemap.
def base():
    return 0x9C00 if (m[0xFF40] & 0x08) else 0x9800
def nonzero_count():
    bb=base(); n=0
    for r in range(18):
        for c in range(20):
            if m[0, bb+r*32+c]!=0: n+=1
    return n
settle_n=0
for i in range(240):
    m[0xDCDC]=0xFF; m[0xDCDD]=0xFF; m[0xDCBB]=0x80
    pb.tick(1,True)
    if i>=120 and i%20==0:
        settle_n=nonzero_count()
        if settle_n>50: break
log(f"settle done nonzero_tiles={nonzero_count()}")
pb.screen.image.save(OUTDIR+"/riff_arena.png")

# --- sample tilemap ---
cnt={}; rowsum={}; rmin={}; rmax={}; rowset={}; colset={}; palhist={}
SAMPLES=300
for s in range(SAMPLES):
    m[0xDCDC]=0xFF; m[0xDCDD]=0xFF; m[0xDCBB]=0x80
    bb=base()
    for r in range(18):
        for c in range(20):
            addr=bb+r*32+c
            t=m[0, addr]            # bank0 = tile id
            if t!=0:
                a=m[1, addr] & 7    # bank1 low3 = BG palette
                cnt[t]=cnt.get(t,0)+1
                rowsum[t]=rowsum.get(t,0)+r
                if t not in rmin or r<rmin[t]: rmin[t]=r
                if t not in rmax or r>rmax[t]: rmax[t]=r
                rowset.setdefault(t,set()).add(r)
                colset.setdefault(t,set()).add(c)
                ph=palhist.setdefault(t,{})
                ph[a]=ph.get(a,0)+1
    pb.tick(1,True)

log(f"SAMPLES={SAMPLES} D880=0x{m[0xD880]:02X} base=0x{base():04X}")
log("tile  cnt  meanrow rmin rmax nrows ncols palhist")
ids=sorted(cnt.keys(), key=lambda t: rowsum[t]/cnt[t])
for t in ids:
    mr=rowsum[t]/cnt[t]
    nrows=len(rowset[t]); ncols=len(colset[t])
    ph=" ".join(f"p{p}={palhist[t][p]}" for p in sorted(palhist[t]))
    log(f"0x{t:02X}  {cnt[t]:4d}  {mr:5.2f}  {rmin[t]:3d}  {rmax[t]:3d}  {nrows:4d}  {ncols:4d}  {ph}")
log("DONE")
pb.stop(save=False)
logf.close()
print("DONE")
