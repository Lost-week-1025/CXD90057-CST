import sys, struct, zlib, mmap, time, os
sys.path.insert(0, r"./_runtime/Lib/site-packages")
from Crypto.Cipher import AES

K1 = bytes.fromhex("E3B0C44298FC1C149AFBF4C8996FB924")
K8 = bytes.fromhex("434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69")
SRC = r".\BODYDATA.DAT"
OUT = r"_work\a6700_fdat_plain.bin"
os.makedirs(os.path.dirname(OUT), exist_ok=True)

f = open(SRC,"rb"); N = f.seek(0,2); f.seek(0)
mm = mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
PAY = 0x9C
nframes = (N - 12 - PAY - 272)//1024
IV = mm[N-12-272 : N-12-272+16]

ecb = AES.new(K1, AES.MODE_ECB)
cbc = AES.new(K2 if False else K8, AES.MODE_CBC, IV)

out = open(OUT,"wb")
bad = 0; ends = 0; total = 0; t0=time.time()
hdr_crc_stored = None
for k in range(nframes):
    off = PAY + k*1024
    blk = mm[off:off+1024]
    if k == 0:
        p = ecb.decrypt(blk[:512]) + cbc.decrypt(blk[512:])
    else:
        p = cbc.decrypt(blk)
    ck, se = struct.unpack("<HH", p[0:4])
    size = se & 0x7fff
    calc = sum(struct.unpack_from("<511H", p, 2)) & 0xffff
    if ck != calc: bad += 1
    if se & 0x8000: ends += 1
    data = p[4:4+size]
    if k == 0:
        hdr_crc_stored = struct.unpack("<I", data[8:12])[0]
        hdr = data[0:512]
    out.write(data); total += size
out.close()
dt = time.time()-t0
mm.close(); f.close()

print("decrypted %s frames in %.1fs" % (format(nframes,","), dt))
print("blocks with BAD checksum : %d" % bad)
print("blocks with endFlag set  : %d  (expect exactly 1)" % ends)
print("plaintext total          : %s bytes" % format(total,","))
print("written -> %s" % OUT)
print()
hdr_crc_calc = zlib.crc32(hdr[12:512]) & 0xFFFFFFFF
print("FdatHeader CRC32 stored=%08X calc=%08X  %s" % (hdr_crc_stored, hdr_crc_calc,
      "OK" if hdr_crc_stored==hdr_crc_calc else "MISMATCH"))
p = open(OUT,"rb"); p.seek(0,2); plen=p.seek(0,2)
print("file size on disk        : %s" % format(plen,","))
fwOff, fwSize, numFs = struct.unpack("<iii", hdr[48:60])
print("header firmwareOffset    : %s" % format(fwOff,","))
print("header firmwareSize      : %s" % format(fwSize,","))
print("header numFileSystems    : %d" % numFs)
print("512 + fs.size + fwSize   : %s  (vs actual %s)" % (format(512+1253376+fwSize,","), format(plen,",")))
print("magic=%r version=%r v%d.%02x" % (hdr[0:8], hdr[12:16], hdr[33], hdr[32]))
