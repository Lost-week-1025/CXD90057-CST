import tarfile, os, io, zlib, struct, hashlib
P = r"_work\a6700_fdat_plain.bin"
OUTD = r"_work"
fwOff, fwSize = 1253888, 1018763264

# updater.img
src = open(P,"rb")
src.seek(512); upd = src.read(1253376)
open(os.path.join(OUTD,"updater.img"),"wb").write(upd)
print("updater.img   : %s bytes  magic=%s" % (format(len(upd),","), upd[:4].hex()))
print("  sqsh magic  : %s" % (upd[:4]==b"hsqs"))

# tar
f = open(P,"rb")
f.seek(fwOff)
tf = tarfile.open(fileobj=f, mode="r:")
members = tf.getmembers()
print("\nfirmware.tar  : %s bytes, %d members" % (format(fwSize,","), len(members)))
dirs = [m for m in members if m.isdir()]
files = [m for m in members if m.isfile()]
print("  dirs=%d  files=%d" % (len(dirs), len(files)))
print("\n=== members (name, size) ===")
for m in members[:60]:
    print("  %-46s %12s %s" % (m.name, format(m.size,","), "DIR" if m.isdir() else ""))
if len(members) > 60:
    print("  ... (%d more)" % (len(members)-60))

# 找 .sum
sums = [m for m in members if m.name.endswith(".sum")]
print("\n=== .sum manifests: %d ===" % len(sums))
for m in sums:
    print("  %-46s %10d bytes" % (m.name, m.size))
f.close()
