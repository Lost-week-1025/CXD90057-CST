import sys, hashlib
src = open(r".\_rt\ext2.py","r",encoding="utf-8").read()
src = src.split("img = sys.argv[1]")[0]
ns={}
exec(compile(src, "ext2mod", "exec"), ns)
e = ns["Ext2"](r"_work\nflasha15.img")
ino = e.walk("/lib/appFw.so")
blks, node = e.file_blocks(ino)
OUT = r"_work\appFw_stock.so"
h=hashlib.sha256(); left=node["size"]
with open(OUT,"wb") as g:
    for b in blks:
        if left<=0: break
        d=e._read_block(b)[:min(left,e.bs)]
        g.write(d); h.update(d); left-=len(d)
print("written %s -> %s" % (format(node["size"],","), OUT))
print("sha256 = %s" % h.hexdigest())
print("STOCK  = %s" % (h.hexdigest()=="e65fd595052be5d0e98ce8000dfcb94f90a2f8309de70ef140375052009b0ef3"))