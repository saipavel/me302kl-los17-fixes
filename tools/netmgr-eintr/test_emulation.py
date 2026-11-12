"""Execute real patched Thumb bytes; hook only libc's __errno PLT."""
import sys
from pathlib import Path
sys.path.insert(0,'tools/analysis-libs')
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import *
b=Path(sys.argv[1]).read_bytes()
registers=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_SP)
def run(result,errno):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0,0x20000);u.mem_write(0,b)
 u.mem_write(0x18000,errno.to_bytes(4,'little'))
 u.reg_write(UC_ARM_REG_R0,result&0xffffffff)
 for i,r in enumerate(registers):u.reg_write(r,0x19000+i*8)
 endpoints=[]
 def hook(uc,address,size,data):
  if address in (0x2c14,0x2bf6,0x2bd4):
   endpoints.append(address);uc.emu_stop()
  elif address==0x18b0:
   uc.reg_write(UC_ARM_REG_R0,0x18000)
   uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(0x2bf3,0x10000,count=80)
 wanted=0x2c14 if result>=0 else (0x2bd4 if errno==4 else 0x2bf6)
 assert endpoints==[wanted],(result,errno,endpoints)
 assert all(u.reg_read(r)==0x19000+i*8 for i,r in enumerate(registers))
 if result>=0:
  assert bool(u.reg_read(UC_ARM_REG_CPSR)&(1<<30))==(result==0)
for e in range(134):run(-1,e)
for r in (0,1,2,32,1024,0x7fffffff):run(r,4)
print('140 execution cases passed: EINTR retry, other errors retained, success flags and callee-saved registers preserved')
