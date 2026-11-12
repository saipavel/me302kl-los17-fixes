"""Host-only transaction tests. Does not invoke ADB or access a tablet.

Exercises real planning, backup validation, install/rollback orchestration and
settings restoration with a simulated recovery. Physical mount/write/fsck are
not hardware-tested here; file writes are replaced by an in-memory backend.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import zipfile

import repair_bundle as b
import patch_rom

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bundle',type=Path,required=True)
p.add_argument('--work',type=Path,required=True)
a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[1]
real=b.read_bundle(a.bundle)
m=copy.deepcopy(real)
deps={path:('synthetic '+path).encode() for path in m['dependencies']}
m['dependencies']={path:b.sha(data) for path,data in deps.items()}
original={};states={}
specs=b.load(repo/'patches/2026-11-10.json')['repairs']
specs.update(b.load(repo/'patches/2026-11-12-netmgr.json')['repairs'])
v2=b.load(repo/'patches/2026-11-11.json')['repairs']['sensors-v2-from-original']
for path,spec in m['files'].items():
    payload=(a.bundle/'payload'/spec['payload']).read_bytes()
    if None in spec['accepted']:states[path]={'kind':'absent'};continue
    patch=v2 if path==v2['device_path'] else next((x for x in specs.values() if x['device_path']==path),None)
    if patch:payload=patch_rom.transform(payload,patch,reverse=True)
    elif path.endswith('media_codecs.xml'):
        payload,n=re.subn(rb'        <!-- Disabled 2026-11-06: secure firmware .*?\n(.*?OMX\.qcom\.video\.decoder\.avc\.secure.*?</MediaCodec>\n)        -->\n',rb'\1',payload,flags=re.S)
        assert n==1
    else:raise AssertionError(path)
    assert b.sha(payload) in spec['accepted']
    original[path]=payload
    states[path]={k:spec[k] for k in ['uid','gid','mode','label']}
    states[path].update(kind='file',sha256=b.sha(payload))
states[b.ALIAS]={'kind':'absent'}

class Fake(b.Device):
    def __init__(self):
        self.serial='host-fixture';self.data=copy.deepcopy(original);self.states=copy.deepcopy(states)
        self.mounted=False;self.writable=False;self.writes=[];self.sdk='29';self.fail_after=None
        self.values={'globals':{k:'null' for k in b.GLOBALS},'properties':{k:'' for k in b.PROPS},'packages':{k:0 for k in b.PACKAGES}}
        self.values['globals']['bluetooth_disabled_profiles']='2'
    def physical(self,path):
        path=path.removeprefix(b.MOUNT)
        return path.removeprefix('/system') if path.startswith('/system/vendor/') else path
    def snapshot(self,path):
        path=self.physical(path);return copy.deepcopy(self.states.get(path,{'kind':'absent'})),self.data.get(path)
    def binary(self,path):
        if path==b.MOUNT+'/system/build.prop':return ('ro.lineage.version='+b.ROM+'\nro.build.version.sdk='+self.sdk+'\n').encode()
        path=self.physical(path)
        return deps[path] if path in deps else self.data[path]
    def call(self,*args,check=True):
        if args==('get-state',):return subprocess.CompletedProcess(args,0,b'recovery\n',b'')
        if args[0]=='shell' and args[1].startswith('e2fsck '):
            assert not self.mounted
            return subprocess.CompletedProcess(args,0,b'host mock only\n',b'')
        raise AssertionError(args)
    def shell(self,cmd,check=True):
        if cmd=='getprop ro.product.device':return 'duma'
        if cmd=='getprop ro.build.version.sdk':return self.sdk
        if cmd=='getprop ro.lineage.version':return b.ROM
        if cmd=='getprop sys.boot_completed':return '1'
        if cmd=='getprop ro.twrp.version':return 'host-fixture'
        if cmd=='id -u':return '0'
        if cmd.startswith('readlink -f '):return b.BLOCK
        if cmd.startswith('set -e; for src '):assert not self.mounted;return 'mock chcon and e2fsck'
        if cmd.startswith('set -e; mkdir -p '):assert not self.mounted;self.mounted=True;return ''
        if cmd.startswith('mount -o remount,rw '):assert self.mounted;self.writable=True;return ''
        if cmd.startswith('umount '):assert self.mounted;self.mounted=self.writable=False;return ''
        if cmd in ['sync','rm -f /tmp/me302kl-repair-transfer.bin']:return ''
        words=shlex.split(cmd)
        if words[:3]==['settings','get','global']:return self.values['globals'][words[3]]
        if words[:3]==['settings','put','global']:self.values['globals'][words[3]]=words[4];return ''
        if words[:3]==['settings','delete','global']:self.values['globals'][words[3]]='null';return ''
        if words[0]=='getprop':return self.values['properties'][words[1]]
        if words[0]=='setprop':self.values['properties'][words[1]]=words[2];return ''
        if words[:2]==['dumpsys','package']:return 'User 0: installed=true enabled='+str(self.values['packages'][words[2]])
        if words[0]=='pm':
            self.values['packages'][words[-1]]={'default-state':0,'enable':1,'disable':2,'disable-user':3,'disable-until-used':4}[words[1]];return ''
        raise AssertionError(cmd)

def fake_write(device,path,entry,blob,work):
    assert device.mounted and device.writable
    if device.fail_after is not None and len(device.writes)==device.fail_after:raise RuntimeError('Injected disconnect during transaction')
    device.writes.append(path)
    device.states[path]={k:v for k,v in entry.items() if k in ['kind','sha256','uid','gid','mode','label','target']}
    if blob is None:device.data.pop(path,None)
    else:assert b.sha(blob)==entry['sha256'];device.data[path]=blob

b.write_target=fake_write
passed=[]
def setup(name):
    device=Fake();backup=a.work/name
    b.prepare(device,m,backup)
    assert device.values==Fake().values and not device.writes
    return device,backup

d,backup=setup('roundtrip')
before=copy.deepcopy(d.values)
b.install(d,m,a.bundle,backup)
assert len(d.writes)==len(b.TARGETS)+1 and not b.check_files(d,m)[0]
b.configure(d,m,backup)
assert d.values['globals']['bluetooth_disabled_profiles']=='0'
assert all(v=='1' for v in d.values['properties'].values())
assert all(v==3 for v in d.values['packages'].values())
b.install(d,m,a.bundle,backup,rollback=True)
b.configure(d,m,backup,restore=True)
assert d.states==states and d.data==original and d.values==before
passed.append('fresh-file install, configure, exact file/metadata/link/settings rollback')

d,backup=setup('partial')
d.fail_after=3
try:b.install(d,m,a.bundle,backup)
except RuntimeError as e:assert 'Injected' in str(e)
else:raise AssertionError('Failure injection not reached')
assert not d.mounted and len(d.writes)==3
d.fail_after=None;b.install(d,m,a.bundle,backup,rollback=True)
assert d.states==states and d.data==original
passed.append('partial-install interruption and rollback')

d,backup=setup('unknown')
path=next(iter(b.TARGETS));d.states[path]['sha256']='0'*64
try:b.install(d,m,a.bundle,backup)
except RuntimeError as e:assert 'changed since backup' in str(e)
else:raise AssertionError('Unknown version accepted')
assert not d.writes and not d.mounted
passed.append('unknown file refused before writes')

d,backup=setup('corrupt')
with zipfile.ZipFile(backup/'files.zip','w') as z:
    for path,blob in original.items():z.writestr(path.lstrip('/'),blob+b'corrupt')
try:b.install(d,m,a.bundle,backup)
except RuntimeError as e:assert 'Corrupt' in str(e)
else:raise AssertionError('Corrupt backup accepted')
assert not d.writes and not d.mounted
passed.append('corrupt PC backup refused before mounting')

d=Fake();d.sdk='33'
try:d.android()
except RuntimeError as e:assert 'Unsupported' in str(e)
else:raise AssertionError('Android 13 accepted')
assert not d.writes and not d.mounted
passed.append('Android 13 refused')

d,backup=setup('wrong-rom-recovery');d.sdk='33'
try:b.install(d,m,a.bundle,backup)
except RuntimeError as e:assert 'Mounted partition' in str(e)
else:raise AssertionError('Wrong recovery ROM accepted')
assert not d.writes and not d.mounted
passed.append('offline wrong-ROM partition refused and unmounted')

save={'passed':passed,'count':len(passed),'adb_invoked':False,'physical_mount_write_fsck_tested':False}
b.save(a.work/'result.json',save)
print(json.dumps(save,indent=2))
