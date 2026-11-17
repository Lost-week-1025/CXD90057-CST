"""A6700 改动版重打包 —— 改 FDAT header 的 1 个 padding 字节，重算 header CRC + L3 + L1。
   保留原 IV 与原 RSA 签名（签名必然失效，用于离线测试，不可刷）。"""
import sys, struct, zlib, mmap, hashlib, time, os
sys.path.insert(0, r"./_runtime/Lib/site-packages")
from Crypto.Cipher import AES

K1 = bytes.fromhex("E3B0C44298FC1C149AFBF4C8996FB924")
K8 = bytes.fromhex("434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69")
SRC = r".\BODYDATA.DAT"
OUT = r"_work\test_modified.DAT"

f=open(SRC,"rb"); N=f.seek(0,2); f.seek(0)
mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
PAY=0x9C
nframes=(N-12-PAY-272)//1024
IV = bytes(mm[N-12-272:N-12-272+16])
SIG= bytes(mm[N-268:N-12])
HEAD=bytes(mm[0:PAY])

def cksum(b): return sum(struct.unpack("<511H", b)) & 0xffff
def pack_block(data, is_last):
    fl=(len(data)|0x8000) if is_last else len(data)
    body=struct.pack("<H",fl)+data+b"\xff"*(1020-len(data))
    return struct.pack("<H",cksum(body))+body

d_ecb=AES.new(K1,AES.MODE_ECB); d_cbc=AES.new(K8,AES.MODE_CBC,IV)
e_ecb=AES.new(K1,AES.MODE_ECB); e_cbc=AES.new(K8,AES.MODE_CBC,IV)

# ---- 第一块：解密 -> 改 header[24] -> 重算 header CRC -> 重打包 ----
blk0 = bytes(mm[PAY:PAY+1024])
p0 = d_ecb.decrypt(blk0[:512]) + d_cbc.decrypt(blk0[512:])
ck,se = struct.unpack("<HH", p0[0:4]); size0 = se & 0x7fff
data0 = bytearray(p0[4:4+size0])          # 1020 bytes
hdr = data0[0:512]
orig_pad = hdr[24]
hdr[24] = 0x41                             # 'A'  仅改 padding，不动语义字段
new_crc = zlib.crc32(bytes(hdr[12:512])) & 0xFFFFFFFF
struct.pack_into("<I", hdr, 8, new_crc)    # header[8:12] = header CRC32
data0[0:512] = hdr
print("changed header[24]: %02X -> 41   header CRC32 -> %08X" % (orig_pad, new_crc))

out=open(OUT,"wb"); crc=0
def W(b):
    global crc
    out.write(b); crc=zlib.crc32(b,crc)
W(HEAD)
first_bad=None; t0=time.time()
new0 = pack_block(bytes(data0), nframes==1)
W(e_ecb.encrypt(new0[:512]) + e_cbc.encrypt(new0[512:]))
for k in range(1, nframes):
    o=PAY+k*1024
    blk=bytes(mm[o:o+1024])
    p=d_cbc.decrypt(blk)
    ck,se=struct.unpack("<HH",p[0:4]); size=se&0x7fff
    new=pack_block(p[4:4+size], k==nframes-1)
    W(e_cbc.encrypt(new))
W(IV); W(SIG)
crc &= 0xFFFFFFFF
out.write(struct.pack(">I",4)+b"DEND"+struct.pack(">I",crc))
out.close()

sz=os.path.getsize(OUT)
print("elapsed      : %.1fs" % (time.time()-t0))
print("out size     : %s (src %s)" % (format(sz,","), format(N,",")))
print("new DEND     : %08X" % crc)

# 签名覆盖区 SHA-256 变化
def sha_region(path, off, size):
    h=hashlib.sha256()
    with open(path,"rb") as g:
        g.seek(off); left=size
        while left:
            b=g.read(min(8<<20,left))
            if not b: break
            h.update(b); left-=len(b)
    return h.hexdigest()
rs = nframes*1024 + 16
a = sha_region(SRC, PAY, rs)
b_= sha_region(OUT, PAY, rs)
print("\nsigned-region SHA256 (orig): %s" % a)
print("signed-region SHA256 (new) : %s" % b_)
print("签名是否仍然匹配           : %s  <-- 必然为 False（无私钥无法重签）" % (a==b_))
mm.close(); f.close()
