"""Build a PRIVATE exact-boot PNO experiment. Does not connect to any device."""
import argparse,hashlib,lzma,struct
from pathlib import Path

ORIGINAL='5d7dd05fd96a1e8041c456ba1ff5018ac98bb0418cf38b521f8e602651316e62'
BASE=0xc0008000
ADDRESS=0xc0847cbc

def boot_id(image,sizes,page):
    cursor=page;sha=hashlib.sha1()
    for size in sizes:
        sha.update(image[cursor:cursor+size]);sha.update(struct.pack('<I',size))
        cursor+=(size+page-1)//page*page
    return sha.digest()+bytes(12)

def build(original):
    if hashlib.sha256(original).hexdigest()!=ORIGINAL:
        raise ValueError('Unsupported boot image; nothing created')
    ks,_,rs,_,ss,_,_,page,dt,_=struct.unpack_from('<10I',original,8)
    assert (ks,rs,ss,page,dt)==(5919072,771398,0,2048,0)
    assert original[576:608]==boot_id(original,(ks,rs,ss,dt),page)
    zimage=original[page:page+ks];start=16408
    decoder=lzma.LZMADecompressor();raw=decoder.decompress(zimage[start:])
    used=len(zimage)-start-len(decoder.unused_data)
    assert used==5902604 and len(raw)==20556680
    off=ADDRESS-BASE
    assert raw[off:off+4]==bytes.fromhex('04c087e5')
    # ip is 1 and lr is 0 at this store. Change only the mode field,
    # preserving the scan-timer count that also uses ip.
    patched=raw[:off]+bytes.fromhex('04e087e5')+raw[off+4:]
    compressed=lzma.compress(patched,format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC32,
                           filters=[{'id':lzma.FILTER_ARM},{'id':lzma.FILTER_LZMA2,'dict_size':32<<20}])
    if len(compressed)>used:raise ValueError('Compressed candidate exceeds original space')
    newkernel=zimage[:start]+compressed+bytes(used-len(compressed))+zimage[start+used:]
    check=lzma.LZMADecompressor();assert check.decompress(newkernel[start:])==patched
    assert newkernel[start+used:]==zimage[start+used:]
    image=bytearray(original);image[page:page+ks]=newkernel
    image[576:608]=boot_id(image,(ks,rs,ss,dt),page)
    assert len(image)==len(original) and image[page+ks:]==original[page+ks:]
    return bytes(image)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();result=build(a.original.read_bytes())
    with a.output.open('xb') as f:f.write(result)
    print('PRIVATE, UNTESTED candidate SHA-256:',hashlib.sha256(result).hexdigest())
    print('No tablet accessed. No partition flashed. Do not publish the full image.')
