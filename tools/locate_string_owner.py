import struct, sys, time
src = open(r".\_rt\ext2.py","r",encoding="utf-8").read()
src = src.split("img = sys.argv[1]")[0]
ns={}; exec(compile(src,"m","exec"), ns); Ext2=ns["Ext2"]
e = Ext2(r"_work\nflasha15.img")

TARGETS=[0x75a4872, 0x75a1bc7, 0x75f01a5]
tblk={ (t//e.bs) for t in TARGETS }
print("target blocks:", sorted(hex(b) for b in tblk))

files=[]
def walk_dir(ino, prefix, depth=0):
    if depth>10: return
    try: ent=e._read_dir(ino)
    except Exception: return
    for name,cino in ent.items():
        if name in (".",".."): continue
        path=prefix+"/"+name
        node=e.inode(cino); mode=node["mode"]
        if (mode&0xF000)==0x4000: walk_dir(cino,path,depth+1)
        elif (mode&0xF000)==0x8000: files.append((path,cino,node["size"]))
walk_dir(2,"")
print("files=%d" % len(files))
t0=time.time(); hits=[]
for path,cino,size in files:
    if size > 200<<20: continue
    try: blks,node=e.file_blocks(cino)
    except Exception: continue
    s=set(blks)
    if s & tblk:
        hits.append((path,size,cino,[hex(t) for t in TARGETS if (t//e.bs) in s]))
print("scan %.1fs" % (time.time()-t0))
print("\n=== 命中 ===")
for h in hits: print("  %-50s size=%12s inode=%-7d %s" % (h[0],format(h[1],","),h[2],h[3]))
if not hits: print("  none -> 这些块不属于任何存活文件（可能是已删除残留或元数据）")