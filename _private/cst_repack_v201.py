"""A6700 v2.00 -> v2.01 版本号重打包

改动：FDAT header[32] = versionMinor  0x00 -> 0x01
影响：header CRC32 (hdr[8:12]) 重算、第一帧 L3 校验重算、DEND CRC32 重算
不变：firmwareOffset/firmwareSize/model/region、tar 内容、L2 .sum 清单
代价：RSA 签名失效（无私钥），但识别层（appFw.so / nflasha15）不验签，
      所以相机仍会按「发现新版本」处理——这与真机 test_v201.DAT 的行为一致。

用法：
    python3 src/cst_repack_v201.py <src.DAT> <out.DAT>
"""
import sys, struct, zlib, mmap, hashlib, time, os
sys.path.insert(0, r"./_runtime/Lib/site-packages")
from Crypto.Cipher import AES

K1 = bytes.fromhex("E3B0C44298FC1C149AFBF4C8996FB924")
K8 = bytes.fromhex("434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69")

SRC = sys.argv[1] if len(sys.argv) > 1 else r".\BODYDATA.DAT"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"_work\a6700_v201.DAT"

f = open(SRC, "rb"); N = f.seek(0, 2); f.seek(0)
mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
PAY = 0x9C
nframes = (N - 12 - PAY - 272) // 1024
IV  = bytes(mm[N-12-272:N-12-272+16])
SIG = bytes(mm[N-268:N-12])
HEAD = bytes(mm[0:PAY])

def cksum(b):
    return sum(struct.unpack("<511H", b)) & 0xffff

def pack_block(data, is_last):
    fl = (len(data) | 0x8000) if is_last else len(data)
    body = struct.pack("<H", fl) + data + b"\xff" * (1020 - len(data))
    return struct.pack("<H", cksum(body)) + body

d_ecb = AES.new(K1, AES.MODE_ECB); d_cbc = AES.new(K8, AES.MODE_CBC, IV)
e_ecb = AES.new(K1, AES.MODE_ECB); e_cbc = AES.new(K8, AES.MODE_CBC, IV)

# ---- 第一块：解密 -> 改 versionMinor -> 重算 header CRC -> 重打包 ----
blk0 = bytes(mm[PAY:PAY+1024])
p0 = d_ecb.decrypt(blk0[:512]) + d_cbc.decrypt(blk0[512:])
ck, se = struct.unpack("<HH", p0[0:4]); size0 = se & 0x7fff
data0 = bytearray(p0[4:4+size0])
hdr = data0[0:512]

old_minor, old_major = hdr[32], hdr[33]
model, region = struct.unpack("<ii", hdr[36:44])
fw_off, fw_size, num_fs = struct.unpack("<iii", hdr[48:60])
print("原始: version=%d.%02d model=0x%X region=%d fwOff=%d fwSize=%d numFs=%d"
      % (old_major, old_minor, model & 0xFFFFFFFF, region, fw_off, fw_size, num_fs))

hdr[32] = 0x01                                  # versionMinor: 0x00 -> 0x01
new_crc = zlib.crc32(bytes(hdr[12:512])) & 0xFFFFFFFF
struct.pack_into("<I", hdr, 8, new_crc)         # header[8:12] = header CRC32
data0[0:512] = hdr
print("改动: versionMinor %02X -> %02X   版本号 %d.%02d -> %d.%02d   header CRC32 -> %08X"
      % (old_minor, hdr[32], old_major, old_minor, hdr[33], hdr[32], new_crc))

out = open(OUT, "wb"); crc = 0
def W(b):
    global crc
    out.write(b); crc = zlib.crc32(b, crc)

W(HEAD)
t0 = time.time()
new0 = pack_block(bytes(data0), nframes == 1)
W(e_ecb.encrypt(new0[:512]) + e_cbc.encrypt(new0[512:]))
for k in range(1, nframes):
    o = PAY + k * 1024
    p = d_cbc.decrypt(bytes(mm[o:o+1024]))
    ck, se = struct.unpack("<HH", p[0:4]); size = se & 0x7fff
    W(e_cbc.encrypt(pack_block(p[4:4+size], k == nframes - 1)))
W(IV); W(SIG)
crc &= 0xFFFFFFFF
out.write(struct.pack(">I", 4) + b"DEND" + struct.pack(">I", crc))
out.close()

sz = os.path.getsize(OUT)
print("耗时         : %.1fs" % (time.time() - t0))
print("输出         : %s (%s B, 源 %s B)" % (OUT, format(sz, ","), format(N, ",")))
print("新 DEND      : %08X" % crc)

def sha_region(path, off, size):
    h = hashlib.sha256()
    with open(path, "rb") as g:
        g.seek(off); left = size
        while left:
            b = g.read(min(8 << 20, left))
            if not b: break
            h.update(b); left -= len(b)
    return h.hexdigest()

rs = nframes * 1024 + 16
a = sha_region(SRC, PAY, rs)
b_ = sha_region(OUT, PAY, rs)
print("\n签名覆盖区 SHA256 (原): %s" % a)
print("签名覆盖区 SHA256 (新): %s" % b_)
print("RSA 签名是否仍匹配     : %s  (预期 False——无私钥无法重签)" % (a == b_))
mm.close(); f.close()
