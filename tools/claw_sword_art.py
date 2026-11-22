#!/usr/bin/env python3
"""Claw Sword OBJ tiles for Wolfkin (src/game/wolfkin_sword_art.c).

Hand-placed 4-colour pixel art, redrawn from GPT Image 2 reference renders
(gpt-image-2.6-sunburst; raw renders are not committed). Colour indices:
0 transparent, 1 pale edge highlight, 2 steel, 3 outline.
Run: python3 tools/claw_sword_art.py  -> prints the 256-byte C initializer.
"""
import numpy as np
from PIL import Image
def blade_h():
    a=np.zeros((8,32),int)
    def p(x,y,v): a[y,x]=v
    # pommel (round fang pommel) x0..2, rows 3..5
    for y in (3,4,5): p(0,y,3)
    p(1,2,3);p(2,2,3);p(1,6,3);p(2,6,3)
    p(1,3,1);p(2,3,1);p(1,4,1);p(2,4,2);p(1,5,2);p(2,5,3)
    # grip x3..7: outline r3,r5, wrap r4
    for x in range(3,8):
        p(x,3,3);p(x,5,3);p(x,4,2 if x%2 else 1)
    # blade body x11..27: outline r2/r6, steel r3,r4, edge highlight r5
    for x in range(11,28):
        p(x,2,3);p(x,3,2);p(x,4,2);p(x,5,1);p(x,6,3)
    # notches on back edge (top): outline dips one row
    for x in (17,22):
        p(x,2,0);p(x,3,3)
    p(18,3,1);p(23,3,1)  # glint after each notch
    # fang tip: back edge sweeps up, edge cuts diagonally
    p(28,1,3);p(29,1,3);p(30,2,3)
    p(28,2,1);p(29,2,1)
    p(28,3,2);p(29,3,1);p(30,3,3)
    p(28,4,1);p(29,4,3)
    p(27,5,1);p(28,5,3)
    p(27,6,3)
    # three-claw guard x8..10: centre claw = guard bar, top & bottom claws curve forward
    for y in range(2,7): p(8,y,3);p(10,y,3)
    for y in range(3,6): p(9,y,1)
    p(9,2,2);p(9,6,2)
    # top claw sweeping up-forward
    p(9,1,3);p(10,1,1);p(11,1,3);p(10,0,3);p(11,0,3);p(12,1,3)
    # bottom claw sweeping down-forward
    p(9,7,3);p(10,7,1);p(11,7,3);p(12,7,3)
    # middle claw: highlight spike on blade at guard
    p(11,4,1);p(12,4,1);p(11,3,1)
    return a
PAL=[(0,0,0,0),(232,240,248,255),(112,136,160,255),(16,24,40,255)]
def render(a,scale=16,bg=(60,120,60,255)):
    img=Image.new('RGBA',(a.shape[1],a.shape[0]),bg)
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y,x]: img.putpixel((x,y),PAL[a[y,x]])
    return img.resize((a.shape[1]*scale,a.shape[0]*scale),0)


DSTEP=6
def blade_d():
    """NE diagonal Claw Sword, hand-placed on a 20x20 canvas. Single-edged
    like the cardinal blade: dark steel spine with claw notches on the
    upper-left, pale cutting edge lower-right, fang tip hooked back."""
    a=np.zeros((20,20),int)
    def p(x,y,v):
        if 0<=x<20 and 0<=y<20: a[y,x]=v
    for y in range(3,15):                     # blade, 5 px per row
        c=18-y
        p(c-1,y,3); p(c,y,2); p(c+1,y,2); p(c+2,y,1); p(c+3,y,3)
    for y in (5,9):                           # claw notches bite the spine
        c=18-y; p(c-1,y,0); p(c,y,3)
    # fang tip: edge sweeps up into a point that hooks back over the spine
    p(15,2,3); p(16,2,2); p(17,2,1); p(18,2,3)
    p(16,1,3); p(17,1,1); p(18,1,3)
    p(17,0,3); p(18,0,3); p(15,1,0)
    # guard: perpendicular bar through (4,15), kept inside the hilt tile
    for j in range(-3,4):
        p(3+j,15+j,3); p(5+j,15+j,3)
    for j in range(-3,4):
        p(4+j,15+j,1)
    p(0,12,3); p(1,11,0); p(7,19,3); p(8,18,0)
    for y in (16,17):                         # wrapped grip
        c=18-y
        p(c-1,y,3); p(c,y,2); p(c+1,y,3)
    p(0,18,1); p(1,18,3); p(0,19,3)           # pommel
    return a
WIN=((0,12),(6,6),(12,0))
def diag_tiles():
    D=blade_d(); owned=np.zeros_like(D); out=[]
    for (x0,y0) in WIN:
        t=np.zeros((8,8),int)
        for y in range(8):
            for x in range(8):
                X,Y=x0+x,y0+y
                if D[Y,X] and not owned[Y,X]:
                    t[y,x]=D[Y,X]; owned[Y,X]=1
        out.append(t)
    return out

SMEAR_A=["........",
         ".shh....",
         "shhhhh..",
         "h..shhhs",
         "......hh",
         ".......h",
         "........",
         "........"]
def smear(kind):
    A=np.array([[{'.':0,'h':1,'s':2,'#':3}[c] for c in r] for r in SMEAR_A])
    if kind=='A': return A
    return A[::-1, ::-1].T.copy()   # anti-transpose: NNE -> ENE

def beam():
    """Full-heart sword beam: a symmetric pale claw spark (reads in any heading)."""
    rows=["........",
          "...##...",
          "..#hh#..",
          ".#hshh#.",
          ".#hhsh#.",
          "..#hh#..",
          "...##...",
          "........"]
    return np.array([[{'.':0,'h':1,'s':2,'#':3}[c] for c in r] for r in rows])

def all_tiles():
    H=blade_h()
    V=np.rot90(H,1)  # 32 tall x 8 wide, tip at top
    t=[]
    for k in range(4): t.append(H[:,8*k:8*k+8])          # 0..3  H pommel,guard,blade,tip
    for k in range(4): t.append(V[24-8*k:32-8*k,:])       # 4..7  V near body..tip
    t+=diag_tiles()                                       # 8..10 D
    t.append(smear('A')); t.append(smear('B'))           # 11,12 smears
    t.append(np.zeros((8,8),int)); t.append(np.zeros((8,8),int))  # 13,14 spare
    t.append(beam())                                      # 15 beam
    return t

def to_2bpp(tile):
    out=[]
    for r in tile:
        lo=hi=0
        for x,v in enumerate(r):
            if v&1: lo|=0x80>>x
            if v&2: hi|=0x80>>x
        out+= [lo,hi]
    return out


if __name__ == "__main__":
    data = []
    for t in all_tiles():
        data += to_2bpp(t)
    for i in range(16):
        print("    " + ", ".join(f"0x{b:02X}" for b in data[i*16:(i+1)*16]) + ",")
