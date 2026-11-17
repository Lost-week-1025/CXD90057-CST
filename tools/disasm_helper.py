import struct
from capstone import *
P=r"_work\libInfraSSHManager.so"
d=open(P,"rb").read()
e_shoff,=struct.unpack("<Q", d[40:48]); e_shentsize,e_shnum=struct.unpack("<HH", d[58:62])
secs={}
for i in range(e_shnum):
    o=e_shoff+i*64
    nm,_,_=0,0,0
    nm,typ=struct.unpack("<II", d[o:o+8]); addr,off,size=struct.unpack("<QQQ", d[o+16:o+40])
    secs[i]=dict(nameoff=nm,addr=addr,off=off,size=size)
shstr=secs[e_shnum-1]
def sname(i):
    no=secs[i]["nameoff"]; return bytes(d[shstr["off"]+no:shstr["off"]+no+64]).split(b"\0")[0].decode("latin-1")
N={sname(i):secs[i] for i in secs}
text=N[".text"]
md=Cs(CS_ARCH_ARM64, CS_MODE_ARM); md.detail=True
code=d[text["off"]:text["off"]+text["size"]]
def dis(v,sz):
    return list(md.disasm(code[v-text["addr"]:v-text["addr"]+sz], v))
for nm,v,sz in [("SshControllerImpl::initialize",0x09970,128),
                ("SshFunctionWrapperImpl::startSshd",0x0908C,152),
                ("SshFunctionWrapperImpl::executeIMSystem",0x08ED8,300)]:
    print("=== %s @0x%X ===" % (nm,v))
    for ins in dis(v,sz):
        print("   0x%05X  %-8s %s" % (ins.address,ins.mnemonic,ins.op_str))
    print()