from pathlib import Path
import sys,struct,json
sys.path.insert(0,'tools/analysis-libs')
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--base-kernel',required=True,type=Path);ap.add_argument('--elf',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);args=ap.parse_args()
with args.elf.open('rb') as f:
 e=ELFFile(f);s=e.get_section_by_name('.text');code=s.data();assert s['sh_addr']==0xc0cff000
 symbols={x.name:x['st_value'] for x in e.get_section_by_name('.symtab').iter_symbols()}
assert len(code)<4096
raw=args.base_kernel.read_bytes();base=0xc0008000
import hashlib
assert hashlib.sha256(raw).hexdigest()=='f9cc7e5ea9d8135204bfb076c05ba9eeacf0e932854d35bbf9a400bd83a89a49'
assert not any(raw[0xc0c76760-base:0xc0d00000-base])
assert raw[0xc09920fc-base:0xc0992100-base].hex()=='30319fe5'
assert raw[0xc06052d4-base:0xc06052d8-base].hex()=='1830dde5'
def bl(src,dst):
 assert not ((dst-src-8)%4) and -(1<<25)<=dst-src-8<(1<<25)
 return struct.pack('<I',0xeb000000|(((dst-src-8)//4)&0xffffff))
new=bytearray(raw);new[0xc0cff000-base:0xc0cff000-base+len(code)]=code
assert struct.unpack_from('<I',raw,0xc0604fc8-base)[0]==0x00e835e4
for a,n in [(0xc09920fc,'probe'),(0xc06052d4,'response_gate')]:new[a-base:a-base+4]=bl(a,symbols[n])
new[0xc0604f94-base:0xc0604f98-base]=struct.pack('<I',0xea000000|(((symbols['show_probe']-0xc0604f94-8)//4)&0xffffff))
# Full kernel images are never written by this host test.
ENV,STACK,RET=0x100000,0x110000,0x120000
registers=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12]
def machine():
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0000000,0x2000000);u.mem_write(base,bytes(new));u.mem_map(ENV,0x30000)
 for i,r in enumerate(registers):u.reg_write(r,0x12120000+i*16)
 u.reg_write(UC_ARM_REG_SP,STACK+0x8000);u.reg_write(UC_ARM_REG_LR,RET)
 u.mem_write(0xc1488584,struct.pack('<I',ENV));u.mem_write(ENV+0x28,struct.pack('<I',ENV+0x1000));u.mem_write(ENV+0x2c,b'01040102\0'+bytes(21))
 return u
count=0
for expected in [0,51,52,53,96]:
 for marker in [0,1,2,3]:
  for avail,written,reply in [(8192,8,False),(8192,8,True),(7,8,False),(8192,-1,False)]:
   u=machine();u.reg_write(UC_ARM_REG_R6,expected);u.mem_write(ENV+0x49,bytes([marker]));calls=[];saved={r:u.reg_read(r) for r in registers};sp=u.reg_read(UC_ARM_REG_SP)
   def hook(uc,a,size,data):
    if a==RET:uc.emu_stop();return
    if a not in [0xc003edac,0xc003eca8,0xc00af710,0xc0c676c8]:return
    calls.append(a)
    if a==0xc003edac:uc.reg_write(UC_ARM_REG_R0,avail)
    elif a==0xc003eca8:
     ptr=uc.reg_read(UC_ARM_REG_R1);length=uc.reg_read(UC_ARM_REG_R2)
     assert length==8 and bytes(uc.mem_read(ptr,8))==struct.pack('<II',0x01000000,8)
     uc.reg_write(UC_ARM_REG_R0,written&0xffffffff)
    elif a==0xc00af710:
     assert uc.reg_read(UC_ARM_REG_R0)==250
     if reply:uc.mem_write(ENV+0x49,b'\x02')
    else:
     assert uc.reg_read(UC_ARM_REG_R1)==(written if avail>=8 else avail)&0xffffffff
    for reg in [UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]:uc.reg_write(reg,0xabcdef00)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
   u.hook_add(UC_HOOK_CODE,hook);u.emu_start(symbols['probe'],RET,count=1000)
   assert u.reg_read(UC_ARM_REG_PC)==RET and u.reg_read(UC_ARM_REG_SP)==sp
   for r,v in saved.items():assert u.reg_read(r)==(0x2e3cd0 if r==UC_ARM_REG_R3 else v)
   active=expected==52 and marker==0
   assert bool(calls)==active
   assert calls.count(0xc003eca8)==int(active and avail>=8)
   assert calls.count(0xc00af710)==int(active and avail>=8 and written==8)
   count+=1
for marker in [0,1,2,3]:
 for major in [0,1,2]:
  u=machine();sp=u.reg_read(UC_ARM_REG_SP);u.reg_write(UC_ARM_REG_R6,0xc1488584);u.reg_write(UC_ARM_REG_LR,0xc06052d8);u.mem_write(sp+0x18,bytes([major]));u.mem_write(ENV+0x49,bytes([marker]));saved={r:u.reg_read(r) for r in registers}
  target=0xc0605240 if marker==1 else 0xc06052d8
  def h(uc,a,size,data):
   if a in [0xc0605240,0xc06052d8]:uc.emu_stop()
  u.hook_add(UC_HOOK_CODE,h);u.emu_start(symbols['response_gate'],0,count=100)
  assert u.reg_read(UC_ARM_REG_PC)==target and u.reg_read(UC_ARM_REG_SP)==sp
  for r,v in saved.items():
   if r==UC_ARM_REG_R3:assert u.reg_read(r)==(v if marker==1 else major)
   else:assert u.reg_read(r)==v
  assert u.mem_read(ENV+0x49,1)[0]==(2 if marker==1 else marker)
  count+=1
for kind in ['null_env','null_channel','invalid_version','empty_version']:
 u=machine();u.reg_write(UC_ARM_REG_R6,52);sp=u.reg_read(UC_ARM_REG_SP)
 if kind=='null_env':u.mem_write(0xc1488584,bytes(4))
 elif kind=='null_channel':u.mem_write(ENV+0x28,bytes(4))
 elif kind=='invalid_version':u.mem_write(ENV+0x2c,b'INVALID\0')
 else:u.mem_write(ENV+0x2c,b'\0')
 def no_call(uc,a,size,data):
  assert a not in [0xc003edac,0xc003eca8,0xc00af710,0xc0c676c8]
  if a==RET:uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,no_call);u.emu_start(symbols['probe'],RET,count=1000)
 assert u.reg_read(UC_ARM_REG_PC)==RET and u.reg_read(UC_ARM_REG_SP)==sp
 count+=1
u=machine();u.mem_write(ENV+0x49,b'\x02');sp=u.reg_read(UC_ARM_REG_SP);saved={r:u.reg_read(r) for r in registers};lr=u.reg_read(UC_ARM_REG_LR)
def show_stop(uc,a,size,data):
 if a==0xc0604f98:uc.emu_stop()
u.hook_add(UC_HOOK_CODE,show_stop);u.emu_start(0xc0604f94,0,count=1000)
assert u.reg_read(UC_ARM_REG_PC)==0xc0604f98 and u.reg_read(UC_ARM_REG_SP)==sp and u.reg_read(UC_ARM_REG_LR)==lr
for r,v in saved.items():assert u.reg_read(r)==(0xe835e4 if r==UC_ARM_REG_R3 else v)
count+=1
result={'cases':count,'code_bytes':len(code),'nv_only_once_per_boot':True,'packet_type_and_length_verified':True,'delay_only_on_successful_write_ms':250,'diagnostic_reply_skips_nv_reload':True,'normal_reply_preserves_original_major_load':True,'registers_and_stack_verified':True,'symbols':{n:symbols[n] for n in ['probe','response_gate','show_probe']}}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
