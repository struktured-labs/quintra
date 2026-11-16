import sys
src,dst,code=sys.argv[1],sys.argv[2],int(sys.argv[3])
d=bytearray(open(src,'rb').read()); n=32768<<code
d+=b'\xff'*(n-len(d)); d=d[:n]
for b in range(1,n//0x4000):
    o=b*0x4000+0x3FF0
    assert all(x==0xff for x in d[o:o+4]) or b>1, b
    d[o:o+4]=bytes([ord('B'),ord('N'),ord('K'),b&0xff])
d[0x148]=code; d[0x147]=0x1B; d[0x149]=0x03; d[0x143]=0xC0
x=0
for c in d[0x134:0x14d]: x=(x-c-1)&0xff
d[0x14d]=x; g=(sum(d)-d[0x14e]-d[0x14f])&0xffff; d[0x14e]=g>>8; d[0x14f]=g&0xff
open(dst,'wb').write(d); print(dst,len(d))
