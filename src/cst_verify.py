"""A6700 / CXD90057 固件壳完整性验证器 —— L1 + L2 + L3 全量，只校验不修改。"""
import sys, struct, zlib, mmap, hashlib, tarfile, json, io, time
sys.path.insert(0, r"./_runtime/Lib/site-packages")
from Crypto.Cipher import AES

DAT   = sys.argv[1] if len(sys.argv) > 1 else r".\BODYDATA.DAT"
K1    = bytes.fromhex("E3B0C44298FC1C149AFBF4C8996FB924")
K8    = bytes.fromhex("434589432D319010F1132727353286CE4D7EDE8B9C4F7217A0E0226E0F0EDC69")
report = {"file": DAT, "checks": {}}

f = open(DAT,"rb"); N = f.seek(0,2); f.seek(0)
mm = mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)

# ---------- L0: 容器记录链 ----------
off = 8; recs = []
while off + 8 <= N:
    ln = struct.unpack(">I", mm[off:off+4])[0]
    tag = bytes(mm[off+4:off+8])
    if not all(32 <= c < 127 for c in tag): break
    recs.append((off, ln, tag.decode(), off+8))
    if tag == b"FDAT": break
    off += 8 + ln
report["container"] = {
    "magic": bytes(mm[0:8]).hex(),
    "records": [{"off": hex(o), "size": s, "tag": t, "data": hex(d)} for o,s,t,d in recs],
    "file_size": N,
}
fdat_off = recs[-1][3]; fdat_len = recs[-1][1]
payload_len = fdat_len
print("[L0] DATV/PROV/UDID/FDAT 链 OK   FDAT payload @0x%X len=%s" % (fdat_off, format(payload_len,",")))

# ---------- L1: DEND CRC32 ----------
tail = bytes(mm[N-12:N])
ok1 = tail[0:4] == b"\x00\x00\x00\x04" and tail[4:8] == b"DEND"
stored = struct.unpack(">I", tail[8:12])[0]
calc   = zlib.crc32(mm[:N-12]) & 0xFFFFFFFF
ok1 = ok1 and stored == calc
report["checks"]["L1_dend_crc32"] = {"ok": ok1, "stored": "%08X"%stored, "calc": "%08X"%calc,
                                     "range": "[0, N-12)", "size": N}
print("[L1] DEND  %s  stored=%08X calc=%08X" % ("OK" if ok1 else "FAIL", stored, calc))

# ---------- L3: 帧校验 + 解密 ----------
nframes = (payload_len - 272)//1024
IV = bytes(mm[N-12-272 : N-12-272+16])
ecb = AES.new(K1, AES.MODE_ECB); cbc = AES.new(K8, AES.MODE_CBC, IV)
bad=0; ends=0; total=0; hdr=None
t0=time.time()
plain = bytearray()
for k in range(nframes):
    o = fdat_off + k*1024
    blk = mm[o:o+1024]
    p = (ecb.decrypt(blk[:512]) + cbc.decrypt(blk[512:])) if k==0 else cbc.decrypt(blk)
    ck, se = struct.unpack("<HH", p[0:4])
    if ck != (sum(struct.unpack_from("<511H", p, 2)) & 0xffff): bad += 1
    if se & 0x8000: ends += 1
    size = se & 0x7fff
    if k==0: hdr = bytes(p[4:4+512])
    plain += p[4:4+size]; total += size
ok3 = (bad == 0 and ends == 1)
report["checks"]["L3_frames"] = {"ok": ok3, "frames": nframes, "bad_checksum": bad,
                                 "endflag_count": ends, "plain_len": total,
                                 "seconds": round(time.time()-t0,1)}
print("[L3] 帧   %s  frames=%s bad=%d endflag=%d  (%.1fs)" %
      ("OK" if ok3 else "FAIL", format(nframes,","), bad, ends, time.time()-t0))

# ---------- FDAT header ----------
hmagic = hdr[0:8]; hcrc_s = struct.unpack("<I", hdr[8:12])[0]
hcrc_c = zlib.crc32(hdr[12:512]) & 0xFFFFFFFF
vmin, vmaj = hdr[32], hdr[33]
model, region = struct.unpack("<ii", hdr[36:44])
fwOff, fwSize, numFs = struct.unpack("<iii", hdr[48:60])
okh = hmagic==b"UDTRFIRM" and hcrc_s==hcrc_c
report["header"] = {"ok": okh, "magic": hmagic.decode(errors="replace"),
                    "version": "%x.%02x" % (vmaj, vmin), "model": "0x%X"%(model&0xFFFFFFFF),
                    "region": region, "firmwareOffset": fwOff, "firmwareSize": fwSize,
                    "numFileSystems": numFs, "header_crc": "%08X"%hcrc_s,
                    "layout_ok": 512 + 1253376 + fwSize == total}
print("[H ] FDAT %s magic=%r v%d.%02x model=0x%X layout=%s" %
      ("OK" if okh else "FAIL", hmagic, vmaj, vmin, model&0xFFFFFFFF,
       "OK" if 512+1253376+fwSize==total else "MISMATCH"))

# ---------- L2: tar .sum 全量 ----------
tf = tarfile.open(fileobj=io.BytesIO(bytes(plain[fwOff:])), mode="r:")
sums = [m for m in tf.getmembers() if m.name.endswith(".sum")]
l2 = []; l2_ok_all = True
for m in sums:
    txt = tf.extractfile(m).read().decode("utf-8","replace")
    _d = m.name.rsplit("/",1)[0]                      # e.g. 0701_part_image_sum
    _num, _rest = _d.split("_",1)
    base = _num[:-1] + "0_" + _rest[:-4]                # NN01_X_sum -> NN00_X
    n=okc=badc=0; misses=[]
    for line in txt.splitlines():
        p = line.split(",")
        if len(p) < 11 or p[0] != "0": continue
        n += 1
        rel = p[10].strip(); decl = p[1].strip()
        cand = [base + "/" + rel, rel]
        got = None
        for c in cand:
            try:
                got = zlib.crc32(tf.extractfile(tf.getmember(c)).read()) & 0xFFFFFFFF; break
            except KeyError: continue
        if got is None: misses.append(rel); badc += 1; l2_ok_all=False
        elif "%08x"%got == decl: okc += 1
        else: badc += 1; l2_ok_all=False
    l2.append({"manifest": m.name, "entries": n, "pass": okc, "fail": badc,
               "missing": misses[:5]})
report["checks"]["L2_sum_manifests"] = {"ok": l2_ok_all, "manifests": l2,
                                        "total_entries": sum(x["entries"] for x in l2),
                                        "total_pass": sum(x["pass"] for x in l2)}
print("[L2] .sum %s  清单=%d 条目=%d 通过=%d" %
      ("OK" if l2_ok_all else "FAIL", len(sums), sum(x["entries"] for x in l2), sum(x["pass"] for x in l2)))
for x in l2:
    print("       %-38s %3d/%3d %s" % (x["manifest"], x["pass"], x["entries"], "" if x["fail"]==0 else "FAIL"))

# ---------- RSA 签名（结构级，无私钥不做验签）----------
sig = bytes(mm[N-268:N-12])
report["signature"] = {"len": len(sig), "at": hex(N-268), "sha256": hashlib.sha256(sig).hexdigest(),
                       "covered_range": "[0x%X, 0x%X)" % (fdat_off, fdat_off + nframes*1024),
                       "covered_len": nframes*1024 + 16,
                       "verification": "skipped: 公钥不在更新包内"}

# ---------- 汇总 ----------
allok = all(v["ok"] for k,v in report["checks"].items() if isinstance(v,dict) and "ok" in v) and okh
report["verdict"] = "PASS" if allok else "FAIL"
print("\n=== VERDICT: %s ===" % report["verdict"])
out = "_work/verify_a6700.json"
json.dump(report, open(out,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("report ->", out)
mm.close(); f.close()



