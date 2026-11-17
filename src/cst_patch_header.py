"""A6700 固件 header 定点改写器 —— 用法: patch_header.py <out.dat> <off>:<hex> [...]
   只改 FDAT header（明文 512 B 内），自动重算 header CRC32 + L3 帧 + L1 DEND。
   IV 与 RSA 签名保持原样（因此签名必然失效，仅用于离线/识别层测试）。"""
import sys, struct, zlib, mmap, hashlib, time, os
sys.path.insert(0, r"./_runtime/Lib/site-packages")
from Crypto.Cipher import AES

K1 = bytes.fromhex("E3B0C44298FC1C149AFBF4C8996FB924")
K8 = bytes.fromhex("434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69")
SRC= r".\BODYDATA.DAT"
OUT= sys.argv[1]
PATCHES=[]
for a in sys.argv[2:]:
    o,v = a.split(":"); PATCHES.append((int(o,0), int(v,16)))

f=open(SRC,"rb"); N=f.seek(0,2); f.seek(0)
mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
PAY=0x9C; nframes=(N-12-PAY-272)//1024
IV=bytes(mm[N-12-272:N-12-272+16]); SIG=bytes(mm[N-268:N-12]); HEAD=bytes(mm[0:PAY])

def cksum(b): return sum(struct.unpack("<511H", b)) & 0xffff
def pack_block(d, last):
    fl=(len(d)|0x8000) if last else len(d)
    body=struct.pack("<H",fl)+d+b"\xff"*(1020-len(d))
    return struct.pack("<H",cksum(body))+body

blk0=bytes(mm[PAY:PAY+1024])
p0=AES.new(K1,AES.MODE_ECB).decrypt(blk0[:512]) + AES.new(K8,AES.MODE_CBC,IV).decrypt(blk0[512:])
ck,se=struct.unpack("<HH",p0[0:4]); size0=se&0x7fff
data0=bytearray(p0[4:4+size0]); hdr=bytearray(data0[0:512])

print("=== 改动前 header 关键字段 ===")
print("  versionMinor@0x20=%02X  versionMajor@0x21=%02X" % (hdr[32],hdr[33]))
print("  model@0x24=0x%08X  region@0x28=%d" % (struct.unpack("<i",hdr[36:40])[0]&0xFFFFFFFF, struct.unpack("<i",hdr[40:44])[0]))
for off,val in PATCHES:
    old=hdr[off]; hdr[off]=val
    print("  PATCH header[0x%02X]: %02X -> %02X" % (off,old,val))
newcrc = zlib.crc32(bytes(hdr[12:512])) & 0xFFFFFFFF
struct.pack_into("<I", hdr, 8, newcrc)
print("  header CRC32 -> %08X" % newcrc)
print("=== 改动后 ===")
print("  versionMinor@0x20=%02X  versionMajor@0x21=%02X  => v%d.%02X" % (hdr[32],hdr[33],hdr[33],hdr[32]))
data0[0:512]=hdr

d_ecb=AES.new(K1,AES.MODE_ECB); d_cbc=AES.new(K8,AES.MODE_CBC,IV)
e_ecb=AES.new(K1,AES.MODE_ECB); e_cbc=AES.new(K8,AES.MODE_CBC,IV)
out=open(OUT,"wb"); crc=0
def W(b):
    global crc
    out.write(b); crc=zlib.crc32(b,crc)
W(HEAD)
n0=pack_block(bytes(data0), nframes==1)
W(e_ecb.encrypt(n0[:512]) + e_cbc.encrypt(n0[512:]))
t0=time.time()
for k in range(1,nframes):
    o=PAY+k*1024; blk=bytes(mm[o:o+1024])
    p=d_cbc.decrypt(blk)
    ck,se=struct.unpack("<HH",p[0:4]); sz=se&0x7fff
    W(e_cbc.encrypt(pack_block(p[4:4+sz], k==nframes-1)))
W(IV); W(SIG)
crc&=0xFFFFFFFF
out.write(struct.pack(">I",4)+b"DEND"+struct.pack(">I",crc)); out.close()
print("\nout      : %s" % OUT)
print("size     : %s (src %s)" % (format(os.path.getsize(OUT),","), format(N,",")))
print("new DEND : %08X   elapsed %.1fs" % (crc, time.time()-t0))
mm.close(); f.close()
