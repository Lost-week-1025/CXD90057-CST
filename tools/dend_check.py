import zlib, struct, sys, hashlib
p = r".\BODYDATA.DAT"
data = open(p,"rb").read()
N = len(data)
print("size = %s" % format(N,","))
tail = data[N-16:]
print("last16 = %s" % tail.hex(" "))
print()
print("=== DEND record (last 12 bytes) ===")
rec = data[N-12:]
print("rec      = %s" % rec.hex(" "))
print("  [0:4]  = %s  (u32be %d)" % (rec[0:4].hex(), struct.unpack(">I",rec[0:4])[0]))
print("  [4:8]  = %r" % rec[4:8])
print("  [8:12] = %s  (u32be 0x%08X)" % (rec[8:12].hex(), struct.unpack(">I",rec[8:12])[0]))
stored = struct.unpack(">I", rec[8:12])[0]
calc = zlib.crc32(data[:N-12]) & 0xFFFFFFFF
print()
print("stored CRC32 = 0x%08X" % stored)
print("calc   CRC32 = 0x%08X  over [0, N-12)" % calc)
print("MATCH        = %s" % (stored == calc))
# also test覆盖范围变体
calc_full = zlib.crc32(data) & 0xFFFFFFFF
print("calc full-file CRC32 = 0x%08X  match=%s" % (calc_full, calc_full==stored))
calc_minus16 = zlib.crc32(data[:N-16]) & 0xFFFFFFFF
print("calc [0,N-16)  CRC32 = 0x%08X  match=%s" % (calc_minus16, calc_minus16==stored))
