#!/usr/bin/env python3
"""nflasha1 (vfat) 离线解析器 —— 只读，不修改任何输入。

用途：fastboot dump 出 nflasha1 的 24 MiB 镜像后，一次性提取并判定：
  1. dat2 / dat3 / dat4        -> model / region / version（回滚判断的基准）
  2. boot/kemco.txt            -> 内核命令行（找 fallback / init= 线索）
  3. initrd.img 内的 PEM       -> 更新验签公钥（比对 8281413b...）
  4. 其余文件清单              -> updater 脚本 / 二进制

用法:
    python parse_nflasha1.py nflasha1.img [-o 输出目录]
    python parse_nflasha1.py part1.raw part2.raw --concat   # 自动拼接两段
"""
import sys, os, struct, hashlib, argparse, zlib, gzip, io

TARGET_PUB_SHA = "8281413b5607446939613e07d020b2c7d8ee2371349099de56bc8288f7be0a43"
FACTORY = dict(model=0x20030001, region=0, version="2.00")


# ---------------- vfat ----------------
class VFat:
    def __init__(self, img):
        self.img = img
        self.bs = 0
        self.parse_bpb()

    def u16(self, o): return struct.unpack_from("<H", self.img, o)[0]
    def u32(self, o): return struct.unpack_from("<I", self.img, o)[0]

    def parse_bpb(self):
        d = self.img
        if d[510:512] != b"\x55\xaa" and d[0:2] != b"\xeb":
            raise ValueError("不是 vfat：缺 0x55AA 或跳转字节")
        bps = self.u16(11)
        spc = d[13]
        rsvd = self.u16(14)
        nfat = d[16]
        root_ent = self.u16(17)
        tot16 = self.u16(19)
        fatsz16 = self.u16(22)
        tot32 = self.u32(32)
        fatsz32 = self.u32(36)

        self.bps = bps
        self.spc = spc
        self.cluster_size = bps * spc
        self.rsvd = rsvd
        self.nfat = nfat
        self.root_ent = root_ent
        self.fat_start = rsvd * bps
        if fatsz16:
            self.fat_size = fatsz16 * bps
            self.total_sectors = tot16
            self.type = 12 if tot16 * bps < 16 * 1024 * 1024 else 16
        else:
            self.fat_size = fatsz32 * bps
            self.total_sectors = tot32
            self.type = 32

        root_sectors = (root_ent * 32 + bps - 1) // bps
        self.root_start = self.fat_start + nfat * self.fat_size
        self.data_start = self.root_start + root_sectors * bps
        # FAT32 根目录是一个簇链
        if self.type == 32:
            self.root_cluster = self.u32(44)
            self.data_start = self.fat_start + nfat * self.fat_size
        self.max_cluster = (self.total_sectors - self.data_start // bps) // spc + 2

    def fat_entry(self, n):
        if self.type == 32:
            return self.u32(self.fat_start + n * 4) & 0x0FFFFFFF
        if self.type == 16:
            return self.u16(self.fat_start + n * 2)
        # FAT12
        off = self.fat_start + n + n // 2
        v = self.u16(off)
        return (v >> 4) if (n & 1) else (v & 0x0FFF)

    def cluster_off(self, c):
        return self.data_start + (c - 2) * self.cluster_size

    def chain(self, start, limit=None):
        out, c, seen = [], start, set()
        while 2 <= c < 0x0FFFFFF8 and c not in seen:
            seen.add(c); out.append(c)
            if limit and len(out) >= limit: break
            c = self.fat_entry(c)
        return out

    def read_chain(self, start, size=None):
        buf = b"".join(self.img[self.cluster_off(c): self.cluster_off(c) + self.cluster_size]
                       for c in self.chain(start))
        return buf[:size] if size is not None else buf

    def root_entries(self):
        if self.type == 32:
            return self._parse_dir(self.read_chain(self.root_cluster))
        raw = self.img[self.root_start: self.root_start + self.root_ent * 32]
        return self._parse_dir(raw)

    def list_root(self):
        ents = []
        if self.type == 32:
            raw = self.read_chain(self.root_cluster)
            ents = self._parse_dir(raw)
        else:
            raw = self.img[self.root_start: self.root_start + self.root_ent * 32]
            ents = self._parse_dir(raw)
        return ents

    def _parse_dir(self, raw):
        out = []
        lfn_parts = {}
        for i in range(0, len(raw) - 31, 32):
            e = raw[i:i + 32]
            if e[0] == 0x00: break
            if e[0] == 0xE5: continue
            attr = e[11]
            if attr == 0x0F:   # LFN
                seq = e[0] & 0x1F
                name = e[1:11] + e[14:26] + e[28:32]
                try:
                    part = name.decode("utf-16-le", "ignore").split("\x00")[0]
                except Exception:
                    part = ""
                lfn_parts[seq] = part
                continue
            name = e[0:8].decode("latin-1").rstrip()
            ext = e[8:11].decode("latin-1").rstrip()
            short = name + ("." + ext if ext else "")
            if lfn_parts:
                long = "".join(lfn_parts[k] for k in sorted(lfn_parts))
                lfn_parts = {}
                if long: short = long
            if short in (".", ".."): continue
            cl = struct.unpack_from("<H", e, 26)[0]
            if self.type == 32:
                cl |= struct.unpack_from("<H", e, 20)[0] << 16
            size = struct.unpack_from("<I", e, 28)[0]
            out.append(dict(name=short, attr=attr, cluster=cl, size=size,
                            isdir=bool(attr & 0x10)))
        return out

    def find(self, path):
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        cur = None
        for idx, part in enumerate(parts):
            if cur is None:
                ents = self.root_entries()
            else:
                ents = self._parse_dir(self.read_chain(cur))
            hit = None
            for e in ents:
                if e["name"].lower() == part.lower():
                    hit = e; break
            if hit is None: return None
            if idx == len(parts) - 1:
                return hit
            if not hit["isdir"]: return None
            cur = hit["cluster"]
        return None

    def read_file_by_path(self, path):
        e = self.find(path)
        if e is None or e["isdir"]: return None
        return self.read_chain(e["cluster"], e["size"])


# ---------------- 辅助 ----------------
def walk(root, prefix=""):
    out = []
    for e in root:
        p = prefix + "/" + e["name"] if prefix else e["name"]
        out.append((p, e))
        if e["isdir"] and e["name"] not in (".", ".."):
            out.extend(walk([], ""))  # 占位，下面靠实例方法补
    return out


def list_all(fs, cluster, prefix="", depth=0):
    if depth > 8: return []
    try:
        if depth == 0 and fs.type != 32:
            ents = fs.root_entries()
        elif depth == 0 and fs.type == 32:
            ents = fs._parse_dir(fs.read_chain(fs.root_cluster))
        else:
            ents = fs._parse_dir(fs.read_chain(cluster))
    except Exception:
        return []
    rows = []
    for e in ents:
        p = prefix + "/" + e["name"] if prefix else e["name"]
        rows.append((p, e))
        if e["isdir"]:
            rows.extend(list_all(fs, e["cluster"], p, depth + 1))
    return rows


def try_ud_datcnv(dat_bytes):
    """dat 文件是 Sony 私有的 ud_datcnv 编码；此处只做启发式提取可读版本串。"""
    out = {}
    # 常见: 4 字节 ASCII 版本 "0200" / "2.00" / 原始 4 位数字
    import re
    m = re.search(rb"(\d{2})\.?(\d{2})\x00", dat_bytes)
    if m:
        out["guess_version"] = b"%s.%s" % (m.group(1), m.group(2))
    if len(dat_bytes) >= 4:
        out["first4"] = dat_bytes[:4].hex()
        out["ascii4"] = "".join(chr(c) if 32 <= c < 127 else "." for c in dat_bytes[:16])
    out["size"] = len(dat_bytes)
    out["sha256"] = hashlib.sha256(dat_bytes).hexdigest()
    return out


def scan_pem(blob, limit=8):
    """在任意二进制里找 PEM 公钥块，返回 (pem_text, sha256, size)。"""
    res = []
    idx = 0
    while True:
        i = blob.find(b"-----BEGIN", idx)
        if i < 0 or len(res) >= limit: break
        j = blob.find(b"-----END", i)
        if j < 0: break
        k = blob.find(b"-----", j + 9)
        end = k + 5 if k > 0 else j + 25
        pem = blob[i:end]
        try:
            txt = pem.decode("ascii")
        except Exception:
            idx = i + 5; continue
        res.append((txt, hashlib.sha256(pem).hexdigest(), len(pem)))
        idx = end
    return res


def scan_der(blob, limit=6):
    """找 RSA-2048 SPKI DER 并转 PEM。"""
    hdr = bytes.fromhex("30820122300d06092a864886f70d01010105000382010f00")
    res = []
    i = 0
    import base64
    while True:
        i = blob.find(hdr, i)
        if i < 0 or len(res) >= limit: break
        der = blob[i:i + 294]
        b64 = base64.b64encode(der).decode()
        lines = [b64[p:p + 64] for p in range(0, len(b64), 64)]
        pem = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"
        res.append((pem, hashlib.sha256(pem.encode()).hexdigest(), len(pem)))
        i += 4
    return res


def try_gunzip(blob):
    for dec, tag in ((gzip.decompress, "gzip"),):
        try:
            return dec(blob), tag
        except Exception:
            pass
    try:
        return zlib.decompress(blob), "zlib"
    except Exception:
        return None, None


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", help="一个或多个 raw 段（按给定顺序拼接）")
    ap.add_argument("-o", "--out", default="_work/nflasha1", help="输出目录")
    ap.add_argument("--concat", action="store_true", help="按顺序拼接多段后解析")
    args = ap.parse_args()

    if len(args.images) > 1 and not args.concat:
        print("多段输入请加 --concat"); return 2

    blobs = [open(p, "rb").read() for p in args.images]
    img = b"".join(blobs)
    print("=== 输入 ===")
    for p, b in zip(args.images, blobs):
        print("  %-42s %10s B  sha256=%s" % (p, format(len(b), ","), hashlib.sha256(b).hexdigest()[:16]))
    print("  合计 %s B (%.2f MiB)" % (format(len(img), ","), len(img) / 2**20))

    os.makedirs(args.out, exist_ok=True)
    fs = VFat(img)
    print("\n=== vfat 参数 ===")
    print("  FAT%d  bytes/sector=%d  sectors/cluster=%d  cluster=%d B" %
          (fs.type, fs.bps, fs.spc, fs.cluster_size))
    print("  total_sectors=%s  root_entries=%d  nfat=%d" %
          (format(fs.total_sectors, ","), fs.root_ent, fs.nfat))

    print("\n=== 根目录 ===")
    for e in fs.list_root():
        print("  %-24s %s %10s" % (e["name"], "DIR" if e["isdir"] else "   ", format(e["size"], ",")))

    all_files = list_all(fs, fs.root_cluster if fs.type == 32 else 0)
    print("\n=== 全量文件 (%d) ===" % len(all_files))
    for p, e in all_files:
        if not e["isdir"]:
            print("  %-40s %10s" % (p, format(e["size"], ",")))

    # 关键文件
    print("\n=== 关键文件提取 ===")
    for name in ("dat2", "dat3", "dat4"):
        for cand in (name, "boot/" + name, "update/" + name):
            b = fs.read_file_by_path(cand)
            if b is not None:
                open(os.path.join(args.out, os.path.basename(cand)), "wb").write(b)
                print("  %-16s %8d B  %s" % (cand, len(b), try_ud_datcnv(b)))
                break
        else:
            print("  %-16s 未找到" % name)

    for name in ("boot/kemco.txt", "kemco.txt", "boot/kemco", "cmdline.txt"):
        b = fs.read_file_by_path(name)
        if b is not None:
            open(os.path.join(args.out, "kemco.txt"), "wb").write(b)
            print("\n=== %s (%d B) ===" % (name, len(b)))
            print(b.decode("utf-8", "replace"))
            break

    # initrd 与公钥
    print("\n=== 公钥扫描 ===")
    found = []
    for p, e in all_files:
        if e["isdir"]: continue
        if e["size"] > 64 * 1024 * 1024: continue
        blob = fs.read_chain(e["cluster"], e["size"])
        low = os.path.basename(p).lower()
        cands = []
        cands += [("pem-file", t, h, n) for (t, h, n) in scan_pem(blob)]
        cands += [("der-file", t, h, n) for (t, h, n) in scan_der(blob)]
        if "initrd" in low or "initram" in low or low.endswith((".cpio", ".img")):
            dec, kind = try_gunzip(blob)
            if dec:
                cands += [("pem-in-%s" % kind, t, h, n) for (t, h, n) in scan_pem(dec)]
                cands += [("der-in-%s" % kind, t, h, n) for (t, h, n) in scan_der(dec)]
        for src, txt, h, n in cands:
            found.append((p, src, h, n, txt))
    if not found:
        print("  [!] 未在镜像中发现任何 PEM/DER 公钥")
    for p, src, h, n, txt in found:
        mark = "   <<< SONY MATCH >>>" if h == TARGET_PUB_SHA else ""
        print("  %-34s %-14s %4d B  sha256=%s%s" % (p, src, n, h, mark))
        if h == TARGET_PUB_SHA:
            open(os.path.join(args.out, "VerificationKey.pem"), "w").write(txt)

    print("\n=== 结论 ===")
    hits = [x for x in found if x[2] == TARGET_PUB_SHA]
    if hits:
        print("  [OK] 找到索尼更新验签公钥: %s" % hits[0][0])
        print("     已保存 -> %s/VerificationKey.pem" % args.out)
        print("     下一步可做 RSA 验签，闭合信任链。")
    else:
        print("  [NO] 未命中 8281413b... (镜像不完整 / 公钥在别处 / 该分区无公钥)")
    print("  提取产物目录: %s" % os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())