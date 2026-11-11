"""Reproduce the saved NULL-zone fault in an emulator, never on the tablet.

Requires capstone-independent Unicorn Python bindings and a private backup of
the exact installed boot partition. No image is modified or distributed.
"""
from pathlib import Path
import argparse, hashlib, json, lzma, struct
from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_MEM_INVALID
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('boot',type=Path)
a=p.parse_args()
b=a.boot.read_bytes()
assert hashlib.sha256(b).hexdigest()=='5d7dd05fd96a1e8041c456ba1ff5018ac98bb0418cf38b521f8e602651316e62', 'Different boot image: addresses are build-specific'
assert b[:8]==b'ANDROID!'
size=struct.unpack_from('<I',b,8)[0];page=struct.unpack_from('<I',b,36)[0]
z=b[page:page+size];offset=z.find(b'\xfd7zXZ');assert offset>=0
decoder=lzma.LZMADecompressor();raw=decoder.decompress(z[offset:]);assert decoder.eof
base=0xc0008000
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
u.mem_map(base,(len(raw)+0x800000+4095)&~4095);u.mem_write(base,raw)
u.mem_map(0x2000000,0x20000)
def read(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
def write(addr,value):u.mem_write(addr,struct.pack('<I',value))
# Resolve this build's actual tmdev global through the warm-wrapper GOT load.
slot=read(0xc076288c+8+read(0xc076291c))
chip=0x2001000;write(slot,chip);write(chip+8,11)
# tmdev exists and sensor count is valid; sensor 7's tz_dev remains NULL.
for register,value in [(UC_ARM_REG_R0,7),(UC_ARM_REG_R1,80),
                       (UC_ARM_REG_R2,0x2010000),(UC_ARM_REG_SP,0x201f000),
                       (UC_ARM_REG_LR,0x2000000)]:u.reg_write(register,value)
fault=[]
def invalid(uc,access,address,size,value,data):
    fault.append({'pc':hex(uc.reg_read(UC_ARM_REG_PC)),
                  'address':hex(address),'size':size})
    return False
u.hook_add(UC_HOOK_MEM_INVALID,invalid)
try:u.emu_start(0xc0762878,0x2000000,count=100)
except UcError:
    if not fault:raise
assert fault==[{'pc':'0xc0761a68','address':'0x188','size':4}], fault
print(json.dumps({'matches_saved_crash':True,'fault':fault},indent=2))
