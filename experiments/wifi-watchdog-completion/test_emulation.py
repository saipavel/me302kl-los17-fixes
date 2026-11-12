"""Execute exact original/patched error paths; stub only kernel callees."""
from pathlib import Path
import sys,json
sys.path.insert(0,'tools/analysis-libs')
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
import argparse,lzma,struct
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('original_boot',type=Path);parser.add_argument('candidate_boot',type=Path)
args=parser.parse_args()
def kernel(path):
    data=path.read_bytes();size=struct.unpack_from('<I',data,8)[0];page=struct.unpack_from('<I',data,36)[0]
    dec=lzma.LZMADecompressor();return dec.decompress(data[page+16408:page+size])
original=kernel(args.original_boot);patched=kernel(args.candidate_boot)
def run(raw,path,ctx,seed):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0000000,0x2000000);u.mem_write(0xc0008000,raw)
 u.mem_map(0x10000,0x40000)
 for i,r in enumerate((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)):
  u.reg_write(r,0x11000+seed*32+i*4)
 u.reg_write(UC_ARM_REG_R4,ctx);u.reg_write(UC_ARM_REG_SP,0x18000)
 # R7 is deliberately unrelated to context: a pre-posted event can skip
 # wait-queue setup, so recovering context from R7 would be unsafe.
 logs=[];out=[]
 def hook(uc,address,size,data):
  if address in (0xc096d9a4,0xc0c676c8,0xc009dc50):
   logs.append((address,*[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]))
   for i,r in enumerate((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12)):uc.reg_write(r,0xabc000+i)
   uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  elif address==0xc00a3850:
   out.append(('completion_exit',uc.reg_read(UC_ARM_REG_R0),uc.reg_read(UC_ARM_REG_R1)));uc.emu_stop()
  elif address==0xc096ada4:
   out.append(('plain_return',uc.reg_read(UC_ARM_REG_R0)));uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,hook)
 starts={'shutdown_failed':0xc096acb0,'reinit_failed':0xc096ad34,'normal_exit':0xc096ab74,'null_argument':0xc096ad80}
 u.emu_start(starts[path],0xc1000000,count=180)
 assert out,(path,seed)
 return logs,out[0]
count=0
for seed in range(16):
 for path in ('shutdown_failed','reinit_failed','normal_exit','null_argument'):
  ctx=0 if path=='null_argument' else 0x20000+seed*0x100
  oldlog,oldout=run(original,path,ctx,seed);newlog,newout=run(patched,path,ctx,seed)
  assert oldlog==newlog,('diagnostic arguments changed',path,seed)
  if path in ('shutdown_failed','reinit_failed'):
   assert oldout==('plain_return',0)
   assert newout==('completion_exit',ctx+0x18,0)
  elif path=='normal_exit':assert oldout==newout==('completion_exit',ctx+0x18,0)
  else:assert oldout==newout==('plain_return',0)
  count+=2
result={'executions':count,'contexts':16,'error_paths_complete_correct_context':True,'normal_exit_and_null_argument_preserved':True,'all_diagnostic_call_arguments_preserved':True,'r7_not_assumed_to_hold_context':True,'kernel_scheduling_not_emulated':True}

print(json.dumps(result))
