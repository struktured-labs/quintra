import sys
src, dst, size_code = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
d = bytearray(open(src,'rb').read())
target = 32768 << size_code
while len(d) < target: d += d[:target-len(d)]
d[0x148] = size_code
x = 0
for b in d[0x134:0x14d]: x = (x - b - 1) & 0xff
d[0x14d] = x
g = (sum(d) - d[0x14e] - d[0x14f]) & 0xffff
d[0x14e] = g >> 8; d[0x14f] = g & 0xff
open(dst,'wb').write(d)
print(dst, len(d), hex(d[0x148]), hex(d[0x14d]), hex(g))
