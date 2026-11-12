"""Build an experimental patch for one exact ME302KL OMX binary; never installs it.

Requires keystone-engine and capstone. See the report before use.
"""
import argparse
import hashlib
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB

SOURCE_SHA256 = '4437d8b36695ffd0e528b22eb4f305fd2836356ed2fbff8b4a783faca0fcf476'


def build(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unsupported source binary; refusing to patch')
    data = bytearray(source)
    asm = ('ldr r0, [r5, #8]; cmp r0, #0; beq input; b.w 0x1c6b0; '
           'input: ldr r0, [r5, #12]; movw r1, #0xa09d; cmp r0, #0; '
           'it ne; movne r0, #1; strb r0, [r4, r1]; b.w 0x1c6b0')
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
    cave = 0x27cd0
    code = bytes(ks.asm(asm, addr=cave)[0])
    instructions = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(code, cave))
    # Do not trust assembler branch encoding without checking its output.
    if ([i.op_str for i in instructions if i.mnemonic == 'b.w'] !=
            ['#0x1c6b0', '#0x1c6b0'] or instructions[2].op_str != '#0x27cda'):
        raise ValueError('Unexpected branch targets')
    if len(code) != 28 or data[cave:cave + len(code)] != bytes(len(code)):
        raise ValueError('Unexpected code cave')
    ph = struct.unpack_from('<I', data, 28)[0] + 2 * 32
    expected = (1, 0x12000, 0x12000, 0x12000, 0x15cd0, 0x15cd0, 5, 4096)
    if struct.unpack_from('<IIIIIIII', data, ph) != expected:
        raise ValueError('Unexpected executable segment')
    struct.pack_into('<II', data, ph + 16, 0x15cd0 + len(code), 0x15cd0 + len(code))
    branch = bytes(ks.asm('b.w 0x27cd0', addr=0x1bea8)[0])
    decoded = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(branch, 0x1bea8))
    if len(branch) != 4 or decoded[0].op_str != '#0x27cd0':
        raise ValueError('Unexpected entry branch')
    data[0x1bea8:0x1beac] = branch
    data[cave:cave + len(code)] = code
    return bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    patched = build(args.source.read_bytes())
    with args.output.open('xb') as output:
        output.write(patched)
    print(hashlib.sha256(patched).hexdigest())
