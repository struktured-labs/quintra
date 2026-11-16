import ctypes, sys, zlib, struct, random, os, glob
L = ctypes.CDLL('/tmp/q-hw-sbh/w/libsbh2.so')
L.s2_open.restype = ctypes.c_void_p; L.s2_open.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
L.s2_load_rom.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
L.s2_quick_reset.argtypes=[ctypes.c_void_p]
L.s2_frame.argtypes=[ctypes.c_void_p,ctypes.c_int]
L.s2_pixels.restype=ctypes.POINTER(ctypes.c_uint32)
L.s2_direct.restype=ctypes.POINTER(ctypes.c_uint8); L.s2_direct.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
L.s2_read.argtypes=[ctypes.c_void_p,ctypes.c_uint16]; L.s2_read.restype=ctypes.c_uint8
L.s2_pc.argtypes=[ctypes.c_void_p]; L.s2_pc.restype=ctypes.c_uint16
L.s2_bank.argtypes=[ctypes.c_void_p]
BOOT=b'/tmp/q-hw-sbh/w/cgb_boot.bin'
def png(path, px):
    raw=b''.join(b'\x00'+b''.join(struct.pack('>I',px[y*160+x])[1:] for x in range(160)) for y in range(144))
    def ch(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    open(path,'wb').write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack('>IIBBBBB',160,144,8,2,0,0,0))+ch(b'IDAT',zlib.compress(raw))+ch(b'IEND',b''))
def fill_sram(gb, data):
    n=ctypes.c_size_t(); p=L.s2_direct(gb,2,ctypes.byref(n))
    for i in range(n.value): p[i]=data[i % len(data)] if data else 0
    return n.value
def run(rom, model, sram, via_gbos, frames=420, tag='x'):
    if via_gbos:
        gb=L.s2_open(b'/tmp/q-hw-sbh/GBOS.GB',BOOT,model)
        for _ in range(240): L.s2_frame(gb,0)
        assert L.s2_load_rom(gb, rom.encode())==0
        if sram is not None: fill_sram(gb, sram)
        L.s2_quick_reset(gb)
    else:
        gb=L.s2_open(rom.encode(),BOOT,model)
        if sram is not None: fill_sram(gb, sram)
    px=L.s2_pixels()
    for f in range(frames): L.s2_frame(gb,0)
    # title check: count pixels of title bg colour
    cols={}
    for i in range(0,160*144,7): cols[px[i]]=cols.get(px[i],0)+1
    top=max(cols.values())/sum(cols.values())
    png(f'/tmp/q-hw-sbh/mx/{tag}.png',px)
    return 'pc=%04x bank=%d lcdc=%02x dom=%06x(%.2f)'%(L.s2_pc(gb),L.s2_bank(gb),L.s2_read(gb,0xff40),max(cols,key=cols.get),top)
os.makedirs('/tmp/q-hw-sbh/mx',exist_ok=True)
roms=sys.argv[1:]
srams={'none':None,'zero':b'\0','ff':b'\xff'}
for i in range(3):
    r=random.Random(i); srams[f'rand{i}']=bytes(r.randrange(256) for _ in range(32768))
for f in glob.glob('/mnt/everdrive/EDGB/SAVE/*.srm')[:4]:
    srams['srm_'+os.path.basename(f)[:10].replace(' ','_')]=open(f,'rb').read()
models={'C':0x203,'D':0x204,'E':0x205}
for rom in roms:
  for mn,m in models.items():
    for via in (0,1):
      for sn,s in srams.items():
        if mn!='E' and sn not in ('none','rand0'): continue
        tag=f'{os.path.basename(rom)[:-4]}-{mn}-{"ed" if via else "pw"}-{sn}'
        print(tag, run(rom,m,s,via,tag=tag), flush=True)
