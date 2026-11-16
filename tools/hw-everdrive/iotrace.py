import ctypes, sys
L = ctypes.CDLL('/tmp/q-hw-sbh/w/libsbh2.so')
L.s2_open.restype = ctypes.c_void_p; L.s2_open.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
L.s2_frame.argtypes=[ctypes.c_void_p,ctypes.c_int]
L.s2_iolog.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
gb=L.s2_open(sys.argv[1].encode(), b'/tmp/q-hw-sbh/w/cgb_boot.bin', 0x205)
# skip boot rom (~ 0x100 reached): just log everything; boot ROM writes appear with bank 1 pc<0x900
L.s2_iolog(gb, sys.argv[2].encode())
for f in range(int(sys.argv[3])): L.s2_frame(gb,0)
L.s2_iolog_close()
