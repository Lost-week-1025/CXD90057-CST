"""A6700 重打包器 —— 无损 roundtrip（解密→重分块→重加密，逐块比对 + 单遍算 DEND）"""
import sys, struct, zlib, mmap, hashlib, time, os
sys.path.insert(0, r"./_runtime/Lib/site-packages")
from Crypto.Cipher import AES

K1 = bytes.fromhex("E3B0C44298FC1C149AFBF4C8996FB924")
K8 = bytes.fromhex("434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69")
SRC = r".\BODYDATA.DAT"
OUT = r"_work\repack_roundtrip.DAT"

f = open(SRC,"rb"); N = f.seek(0,2); f.seek(0)
mm = mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
PAY = 0x9C
nframes = (N - 12 - PAY - 272)//1024
IV  = bytes(mm[N-12-272 : N-12-272+16])
SIG = bytes(mm[N-268 : N-12])
HEAD= bytes(mm[0:PAY])

def cksum(b1022): return sum(struct.unpack("<511H", b1022)) & 0xffff
def pack_block(data, is_last):
    fl = (len(data) | 0x8000) if is_last else len(data)
    body = struct.pack("<H", fl) + data + b"\xff"*(1020-len(data))
    return struct.pack("<H", cksum(body)) + body

ecb_d=AES.new(K1,AES.MODE_ECB); cbc_d=AES.new(K8,AES.MODE_CBC,IV)
ecb_e=AES.new(K1,AES.MODE_ECB); cbc_e=AES.new(K8,AES.MODE_CBC,IV)

out = open(OUT,"wb"); crc = 0
def W(b):
    global crc
    out.write(b); crc = zlib.crc32(b, crc)

W(HEAD)
first_bad = None; t0 = time.time()
for k in range(nframes):
    o = PAY + k*1024
    blk = bytes(mm[o:o+1024])
    p = (ecb_d.decrypt(blk[:512]) + cbc_d.decrypt(blk[512:])) if k==0 else cbc_d.decrypt(blk)
    ck, se = struct.unpack("<HH", p[0:4])
    size = se & 0x7fff
    new = pack_block(p[4:4+size], k == nframes-1)
    e = (ecb_e.encrypt(new[:512]) + cbc_e.encrypt(new[512:])) if k==0 else cbc_e.encrypt(new)
    if e != blk and first_bad is None: first_bad = k
    W(e)
W(IV); W(SIG)
crc &= 0xFFFFFFFF
out.write(struct.pack(">I",4) + b"DEND" + struct.pack(">I",crc))
out.close()

sz = os.path.getsize(OUT)
print("frames           : %s" % format(nframes,","))
print("first mismatch   : %s" % (first_bad if first_bad is not None else "NONE  <== 无损 roundtrip 成功"))
print("elapsed          : %.1fs" % (time.time()-t0))
print("out size         : %s  (src %s)" % (format(sz,","), format(N,",")))
def md5(p):
    m=hashlib.md5()
    with open(p,"rb") as fp:
        for b in iter(lambda: fp.read(8<<20), b""): m.update(b)
    return m.hexdigest()
a, b_ = md5(SRC), md5(OUT)
print("src MD5          : %s" % a)
print("new MD5          : %s" % b_)
print("BYTE-IDENTICAL   : %s" % (a == b_))
print("DEND stored      : %08X" % crc)
mm.close(); f.close()
