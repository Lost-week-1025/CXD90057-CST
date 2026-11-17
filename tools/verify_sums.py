import tarfile, io, zlib, sys
P = r"_work\a6700_fdat_plain.bin"
f = open(P,"rb"); f.seek(1253888)
tf = tarfile.open(fileobj=f, mode="r:")
members = tf.getmembers()

print("=== 剩余成员 (60 之后) ===")
for m in members[60:]:
    print("  %-52s %12s %s" % (m.name, format(m.size,","), "DIR" if m.isdir() else ""))

print("\n=== part_image.sum (454 bytes) ===")
d = tf.extractfile("0701_part_image_sum/part_image.sum").read()
print(d.decode("utf-8", "replace"))
print("raw len = %d, CRLF? %s, LF-only? %s" % (len(d), b"\r\n" in d, d.count(b"\n")==d.count(b"\r\n")==0 or b"\r" not in d))

print("=== appli.sum (2740 bytes) 前 15 行 ===")
d2 = tf.extractfile("0801_appli_sum/appli.sum").read().decode("utf-8","replace")
for line in d2.splitlines()[:15]: print("  "+line)

print("\n=== 关键分区文件实际 CRC32 vs .sum 声明 ===")
sums = {}
for line in d.decode("utf-8","replace").splitlines():
    p = line.split(",")
    if len(p) >= 11 and p[0] == "0":
        sums[p[10].strip()] = (p[1].strip(), int(p[2].strip(),16))
for name,(declared,dsz) in sums.items():
    try:
        m = tf.getmember("0700_part_image/"+name)
        h = zlib.crc32(tf.extractfile(m).read()) & 0xFFFFFFFF
        ok = ("%08x" % h) == declared
        print("  %-22s size=%12s(decl %12s)  crc=%08x decl=%s  %s" %
              (name, format(m.size,","), format(dsz,","), h, declared, "OK" if ok else "MISMATCH"))
    except KeyError:
        print("  %-22s NOT FOUND in tar" % name)
f.close()
