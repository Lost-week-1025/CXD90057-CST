"""ext2 只读解析器 —— 提取指定路径文件（支持直接/单/双/三间接块）"""
import struct, sys, hashlib

class Ext2:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.N = self.f.seek(0, 2)
        self.f.seek(1024); sb = self.f.read(1024)
        assert struct.unpack("<H", sb[56:58])[0] == 0xEF53, "not ext2"
        self.inodes_count = struct.unpack("<I", sb[0:4])[0]
        self.blocks_count = struct.unpack("<I", sb[4:8])[0]
        self.first_data   = struct.unpack("<I", sb[20:24])[0]
        self.log_bs       = struct.unpack("<I", sb[24:28])[0]
        self.bs           = 1024 << self.log_bs
        self.bpg          = struct.unpack("<I", sb[32:36])[0]
        self.ipg          = struct.unpack("<I", sb[40:44])[0]
        rev               = struct.unpack("<I", sb[76:80])[0]
        self.inode_size   = struct.unpack("<H", sb[88:90])[0] if rev >= 1 else 128
        if self.inode_size == 0: self.inode_size = 128
        self.gd_block = 2 if self.bs == 1024 else 1
        self.ptr = self.bs // 4
        print("ext2: bs=%d bpg=%d ipg=%d inode_size=%d blocks=%s inodes=%s"
              % (self.bs, self.bpg, self.ipg, self.inode_size,
                 format(self.blocks_count, ","), format(self.inodes_count, ",")))
    def _read_block(self, blkno):
        # block 0 is boot; file offset = blkno * bs
        off = blkno * self.bs
        self.f.seek(off); return self.f.read(self.bs)
    def _gd(self, group):
        off = self.gd_block * self.bs + group * 32
        self.f.seek(off); gd = self.f.read(32)
        return struct.unpack("<III", gd[8:20])       # inode_table, free, ...
    def inode(self, ino):
        group = (ino - 1) // self.ipg
        index = (ino - 1) % self.ipg
        itable, _, _ = self._gd(group)
        off = itable * self.bs + index * self.inode_size
        self.f.seek(off); raw = self.f.read(self.inode_size)
        mode  = struct.unpack("<H", raw[0:2])[0]
        size  = struct.unpack("<I", raw[4:8])[0]
        blocks= list(struct.unpack("<15I", raw[40:100]))
        return {"ino": ino, "mode": mode, "size": size, "blocks": blocks}
    def _ptrs(self, blkno):
        if blkno == 0: return ()
        b = self._read_block(blkno)
        return struct.unpack("<%dI" % self.ptr, b)
    def file_blocks(self, ino, limit=10**9):
        """按 inode 块指针展开成实际数据块号序列（支持三级间接）"""
        node = self.inode(ino)
        out = []
        for b in node["blocks"][:12]:
            out.append(b)
            if len(out) >= limit: return out, node
        def indirect(blkno, level):
            if blkno == 0 or len(out) >= limit: return
            for p in self._ptrs(blkno):
                if p == 0: continue
                if level == 1:
                    out.append(p)
                    if len(out) >= limit: return
                else:
                    indirect(p, level - 1)
                    if len(out) >= limit: return
        if len(out) < limit: indirect(node["blocks"][12], 1)
        if len(out) < limit: indirect(node["blocks"][13], 2)
        if len(out) < limit: indirect(node["blocks"][14], 3)
        return out, node
    def read_file(self, ino):
        blks, node = self.file_blocks(ino)
        print("  inode %d: size=%s mode=0%o blocks=%d (need %d)"
              % (ino, format(node["size"],","), node["mode"], len(blks),
                 (node["size"] + self.bs - 1)//self.bs))
        h = hashlib.sha256(); got = 0; left = node["size"]
        for b in blks:
            if left <= 0: break
            data = self._read_block(b)[:min(left, self.bs)]
            h.update(data); got += len(data); left -= len(data)
        return got, h.hexdigest()
    def walk(self, path):
        """解析绝对路径 -> inode 号"""
        cur = 2
        for comp in [c for c in path.split("/") if c]:
            data = self._read_dir(cur)
            if comp not in data: raise KeyError("no such entry: %s (in %s)" % (comp, path))
            cur = data[comp]
        return cur
    def _read_dir(self, ino):
        blks, node = self.file_blocks(ino)
        raw = b"".join(self._read_block(b) for b in blks)[:node["size"]]
        res = {}; off = 0
        while off + 8 <= len(raw):
            e_ino, rec_len, name_len, ftype = struct.unpack("<IHBB", raw[off:off+8])
            if rec_len == 0: break
            name = raw[off+8:off+8+name_len].decode("latin-1")
            if e_ino: res[name] = e_ino
            off += rec_len
        return res

img = sys.argv[1]
target = sys.argv[2] if len(sys.argv) > 2 else "/lib/appFw.so"
e = Ext2(img)
print("\n--- 目录探测 ---")
for d in ["/", "/lib", "/usr", "/usr/lib", "/usr/bin"]:
    try:
        ent = e._read_dir(e.walk(d))
        print("  %-10s %d entries: %s" % (d, len(ent), ", ".join(sorted(ent)[:12])))
    except Exception as ex:
        print("  %-10s ERR %s" % (d, ex))
print("\n--- 目标文件 ---")
ino = e.walk(target)
print("  %s -> inode %d" % (target, ino))
n, sha = e.read_file(ino)
print("  read %s bytes  sha256=%s" % (format(n,","), sha))
print("  STOCK match: %s" % (sha == "e65fd595052be5d0e98ce8000dfcb94f90a2f8309de70ef140375052009b0ef3"))
