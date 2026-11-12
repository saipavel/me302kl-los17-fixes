#!/usr/bin/env python3
"""Private, exact-ROM repair bundle builder and ADB recovery installer.

Build from the already repaired tablet; never publish the resulting vendor
payloads or PC backups. Public source/manifests contain no firmware libraries.
Python 3 standard library only. Recovery installation writes only system files;
the separate Android configure step changes the explicitly listed settings.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import zipfile

ROM='17.1-20230306-UNOFFICIAL-duma'
MOUNT='/tmp/me302kl-repair-system'
BLOCK='/dev/block/mmcblk0p22'
ALIAS='/system/etc/gps.conf'
LINK='/vendor/etc/gps.conf'
TARGETS={
    '/vendor/bin/sensors.qcom':(0,2000,'755','sensors_exec'),
    '/system/lib/libbluetooth.so':(0,0,'644','system_lib_file'),
    '/vendor/lib/hw/android.hardware.gnss@1.0-impl.so':(0,0,'644','vendor_file'),
    '/vendor/lib/hw/gps.msm8960.so':(0,0,'644','vendor_file'),
    '/vendor/lib/hw/gps.msm8960.base.so':(0,0,'644','system_file'),
    '/vendor/lib/libgps.utils.so':(0,0,'644','vendor_file'),
    '/system/etc/gps_debug.conf':(0,0,'644','system_file'),
    '/vendor/build.prop':(0,0,'600','vendor_file'),
    '/vendor/etc/init/me302kl-cellular-disabled.rc':(0,0,'644','vendor_configs_file'),
    '/system/product/overlay/Me302klConfigurator/Me302klConfiguratorOverlay.apk':(0,0,'644','vendor_overlay_file'),
    '/vendor/etc/media_codecs.xml':(0,0,'644','vendor_configs_file'),
    '/vendor/lib/libnetmgr.so':(0,0,'644','vendor_file'),
}
GLOBALS=['bluetooth_disabled_profiles','mobile_data','data_roaming','airplane_mode_radios']
PROPS=['persist.me302kl.cellular_disabled','persist.me302kl.gps_power_control']
PACKAGES=['com.android.phone','com.android.mms.service','com.google.android.carriersetup']
DEPENDENCIES={
    '/vendor/lib/libloc_eng.so':'738150c1cfc134a473b7591f962a083edb5e809f1691dc9e10c5d0197329df6a',
    '/vendor/lib/libloc_core.so':'bda70bd2e651f768648e76fc57c771d6ba6c2084a439c971e9c0cb6f4298a0d1',
    '/vendor/lib/libloc_api_v02.so':'057dc76d46efb8b577f91e13d76d16d87b464897fa22e1d8ac65d13ba371705d',
    '/vendor/lib/libloc_ds_api.so':'81fc15c00f256c0a0bd6e5a08d24238c4291046000f015296501bfe45ca5d24f',
}

def sha(data):return hashlib.sha256(data).hexdigest()
def q(s):return shlex.quote(str(s))
def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
def load(path):return json.loads(path.read_text(encoding='utf-8'))

class Device:
    def __init__(self,adb,serial):self.command=[adb,'-s',serial];self.serial=serial
    def call(self,*args,check=True):
        r=subprocess.run(self.command+list(args),capture_output=True,timeout=120)
        if check and r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')+' '+r.stdout.decode(errors='replace'))
        return r
    def shell(self,cmd,check=True):return self.call('shell',cmd,check=check).stdout.decode(errors='replace').strip()
    def binary(self,path):return self.call('exec-out','cat '+q(path)).stdout
    def root(self):
        if self.shell('id -u')!='0':
            self.call('root');self.call('wait-for-device')
        if self.shell('id -u')!='0':raise RuntimeError('Rooted debugging must be enabled.')
    def android(self):
        if self.shell('getprop ro.product.device')!='duma' or self.shell('getprop ro.build.version.sdk')!='29' or self.shell('getprop ro.lineage.version')!=ROM:
            raise RuntimeError('Unsupported ROM/device. Only '+ROM+' is accepted. Android 13 is refused.')
        if self.shell('getprop sys.boot_completed')!='1':raise RuntimeError('Wait for Android to finish starting.')
    def snapshot(self,path):
        if self.shell('test -L '+q(path)+' && echo yes',check=False)=='yes':
            return {'kind':'link','target':self.shell('readlink '+q(path))},None
        if self.shell('test -e '+q(path)+' && echo yes',check=False)!='yes':return {'kind':'absent'},None
        if self.shell('test -f '+q(path)+' && echo yes')!='yes':raise RuntimeError('Not a regular file: '+path)
        data=self.binary(path)
        values=self.shell("stat -c '%u %g %a' "+q(path)).split()
        labels=self.shell('ls -Zd '+q(path))
        label=re.search(r'u:object_r:[A-Za-z0-9_]+:s0',labels)
        if not label:raise RuntimeError('Cannot capture SELinux label: '+path)
        return {'kind':'file','sha256':sha(data),'uid':int(values[0]),'gid':int(values[1]),'mode':values[2],'label':label[0]},data
    def settings(self):
        result={'serial':self.serial,'rom':ROM,'globals':{},'properties':{},'packages':{}}
        for name in GLOBALS:result['globals'][name]=self.shell('settings get global '+name)
        for name in PROPS:result['properties'][name]=self.shell('getprop '+name)
        for name in PACKAGES:
            s=self.shell('dumpsys package '+name)
            m=re.search(r'User 0:.*?\benabled=(\d+)',s)
            if m:result['packages'][name]=int(m[1])
        return result

def read_bundle(folder):
    m=load(folder/'manifest.json')
    if m['rom']!=ROM or set(m['files'])!=set(TARGETS):raise ValueError('Unsupported manifest targets')
    for path,spec in m['files'].items():
        if spec['payload']!=str(list(TARGETS).index(path))+'.bin':raise ValueError('Invalid payload name')
        if sha((folder/'payload'/spec['payload']).read_bytes())!=spec['sha256']:raise ValueError('Corrupt payload: '+path)
    return m

def accepted(snapshot,spec):
    if snapshot['kind']=='absent':return None in spec['accepted']
    return snapshot['kind']=='file' and snapshot['sha256'] in spec['accepted']

def check_files(device,manifest,prefix=''):
    changes=[];states={};data={}
    for path,spec in manifest['files'].items():
        physical=prefix+('/system'+path if path.startswith('/vendor/') else path)
        state,blob=device.snapshot(physical)
        if not accepted(state,spec):raise RuntimeError('Unknown file/version; nothing written: '+path+' '+str(state))
        states[path]=state
        if blob is not None:data[path]=blob
        if state.get('sha256')!=spec['sha256']:changes.append(path)
    state,_=device.snapshot(prefix+ALIAS)
    if state['kind']!='absent' and state!={'kind':'link','target':LINK}:raise RuntimeError('Unexpected GPS config alias')
    states[ALIAS]=state
    if state['kind']=='absent':changes.append(ALIAS)
    for path,expected in manifest['dependencies'].items():
        physical=prefix+'/system'+path
        if sha(device.binary(physical))!=expected:raise RuntimeError('GPS dependency mismatch: '+path)
    return changes,states,data

def build(device,repo,output):
    device.android();device.root()
    m10=load(repo/'patches/2026-11-10.json')['repairs'];m11=load(repo/'patches/2026-11-11.json')['repairs']
    expected=load(repo/'evidence/full-health-2026-11-11.json')['repairs']['hashes']
    expected.update({
        '/vendor/etc/init/me302kl-cellular-disabled.rc':'184e63aefe14815179372157ceb0865005f3768c1435acc16025a804637ffeee',
        '/system/product/overlay/Me302klConfigurator/Me302klConfiguratorOverlay.apk':'105fa4a3ac1a1d407c23f3f248aca4a1b318039bc20d3ca3a50e3c9422cd88f9',
        '/vendor/etc/media_codecs.xml':'61b54df613f6a0b8a4084562a0583067e12ba6a714868e44e72fc0f79c7f22e9'})
    netmgr=load(repo/'patches/2026-11-12-netmgr.json')['repairs']['netmgr-eintr']
    expected[netmgr['device_path']]=netmgr['after_sha256']
    allowed={p:[h] for p,h in expected.items()}
    allowed[netmgr['device_path']].append(netmgr['before_sha256'])
    for spec in m10.values():allowed[spec['device_path']].append(spec['before_sha256'])
    allowed['/vendor/bin/sensors.qcom'].append(m11['sensors-logmask-v2']['before_sha256'])
    for path in ['/vendor/lib/hw/gps.msm8960.so','/vendor/lib/hw/gps.msm8960.base.so','/vendor/lib/libgps.utils.so','/vendor/etc/init/me302kl-cellular-disabled.rc','/system/product/overlay/Me302klConfigurator/Me302klConfiguratorOverlay.apk']:
        allowed[path].append(None)
    allowed['/vendor/lib/hw/gps.msm8960.so'].append(expected['/vendor/lib/hw/gps.msm8960.base.so'])
    files={};payload={}
    for n,path in enumerate(TARGETS):
        blob=device.binary(path)
        if sha(blob)!=expected[path]:raise RuntimeError('Export source is not the tested repaired file: '+path)
        if path.endswith('/media_codecs.xml'):
            text=blob.decode();pattern=r'        <!-- Disabled 2026-11-06: secure firmware .*?\n(.*?OMX\.qcom\.video\.decoder\.avc\.secure.*?</MediaCodec>\n)        -->\n'
            original,count=re.subn(pattern,r'\1',text,flags=re.S)
            if count!=1:raise RuntimeError('Cannot identify exact existing codec workaround')
            allowed[path].append(sha(original.encode()))
        uid,gid,mode,label=TARGETS[path]
        files[path]={'payload':str(n)+'.bin','sha256':sha(blob),'accepted':list(dict.fromkeys(allowed[path])),
                                                            'uid':uid,'gid':gid,'mode':mode,'label':'u:object_r:'+label+':s0'}
        payload['payload/'+str(n)+'.bin']=blob
    deps={}
    for name in ['libloc_eng.so','libloc_core.so','libloc_api_v02.so','libloc_ds_api.so']:
        path='/vendor/lib/'+name;deps[path]=sha(device.binary(path))
    if deps!=DEPENDENCIES:raise RuntimeError('Export source GPS dependencies differ from tested tablet')
    manifest={'format':1,'rom':ROM,'wifi_only':True,'files':files,'dependencies':deps,'experimental_thermal_included':False,'boot_image_included':False}
    payload.update({'manifest.json':(json.dumps(manifest,indent=2)+'\n').encode(),
                                                                    'repair_bundle.py':Path(__file__).read_bytes(),
                                                                    'INSTALL.txt':(repo/'docs/repair-bundle-install.txt').read_bytes()})
    payload['SHA256SUMS.txt']=''.join(sha(b)+'  '+name+'\n' for name,b in sorted(payload.items())).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,blob in payload.items():z.writestr(name,blob)
    print('Built private bundle:',output,'SHA256',sha(output.read_bytes()))

def prepare(device,manifest,backup):
    device.android();device.root()
    changes,states,data=check_files(device,manifest)
    if not changes:print('All bundled files already installed. No reinstall needed.');return
    backup.mkdir(parents=True,exist_ok=False)
    state=device.settings();state['files']=states;state['manifest_sha256']=sha(json.dumps(manifest,sort_keys=True).encode())
    with zipfile.ZipFile(backup/'files.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for path,blob in data.items():z.writestr(path.lstrip('/'),blob)
    save(backup/'before.json',state)
    with zipfile.ZipFile(backup/'files.zip') as z:
        for path,entry in states.items():
            if entry['kind']=='file':assert sha(z.read(path.lstrip('/')))==entry['sha256']
    print('Verified PC backup:',backup.resolve());print('Planned changes:',len(changes))
    print('Now reboot to TWRP; uncheck System under Mount. Do not wipe.')

def backup_state(device,manifest,backup):
    state=load(backup/'before.json')
    if state['serial']!=device.serial or state['rom']!=ROM or set(state['files'])!=set(TARGETS)|{ALIAS}:raise RuntimeError('Backup is for a different tablet/ROM')
    if state['manifest_sha256']!=sha(json.dumps(manifest,sort_keys=True).encode()):raise RuntimeError('Backup belongs to a different bundle')
    if set(state['globals'])!=set(GLOBALS) or set(state['properties'])!=set(PROPS) or not set(state['packages']).issubset(PACKAGES):raise RuntimeError('Invalid backup settings keys')
    if any(value not in range(5) for value in state['packages'].values()):raise RuntimeError('Invalid backup package state')
    with zipfile.ZipFile(backup/'files.zip') as z:
        for path,entry in state['files'].items():
            if entry['kind']=='file' and sha(z.read(path.lstrip('/')))!=entry['sha256']:raise RuntimeError('Corrupt PC backup')
    return state

def recover_mount(device):
    if device.call('get-state').stdout.decode().strip()!='recovery' or not device.shell('getprop ro.twrp.version'):
        raise RuntimeError('This action requires TWRP recovery; Android will not be modified live.')
    if device.shell('readlink -f /dev/block/platform/msm_sdcc.1/by-name/system')!=BLOCK:raise RuntimeError('Unexpected system partition')
    device.shell('set -e; for src in $(awk \'{print $1}\' /proc/mounts); do [ "$(readlink -f "$src")" != '+q(BLOCK)+' ] || { echo "System is already mounted. Uncheck System in TWRP Mount."; exit 1; }; done; command -v chcon; command -v e2fsck')
    device.shell('set -e; mkdir -p '+q(MOUNT)+'; mount -t ext4 -o ro '+q(BLOCK)+' '+q(MOUNT))
    try:
        text=device.binary(MOUNT+'/system/build.prop').decode()
        if 'ro.lineage.version='+ROM not in text.splitlines() or 'ro.build.version.sdk=29' not in text.splitlines():raise RuntimeError('Mounted partition is not the supported ROM')
    except Exception:
        device.shell('umount '+q(MOUNT),check=False);raise

def same(a,b):return a==b if a['kind']!='file' else b['kind']=='file' and a['sha256']==b.get('sha256')

def write_target(device,path,entry,blob,work):
    physical=MOUNT+('/system'+path if path.startswith('/vendor/') else path)
    if entry['kind']=='absent':device.shell('rm -f '+q(physical));return
    if entry['kind']=='link':
        if path!=ALIAS or entry['target']!=LINK:raise RuntimeError('Unexpected link')
        device.shell('set -e; ln -s '+q(LINK)+' '+q(physical+'.me302kl-new')+'; mv -f '+q(physical+'.me302kl-new')+' '+q(physical));return
    temp=work/'transfer.bin';temp.write_bytes(blob)
    device.call('push',str(temp),'/tmp/me302kl-repair-transfer.bin')
    parent=str(Path(path).parent).replace('\\','/')
    if path.startswith('/system/product/overlay/Me302klConfigurator/'):
        directory=MOUNT+parent
        device.shell('set -e; mkdir -p '+q(directory)+'; chown 0:0 '+q(directory)+'; chmod 755 '+q(directory)+'; chcon u:object_r:vendor_overlay_file:s0 '+q(directory))
    new=physical+'.me302kl-new'
    device.shell('set -e; [ ! -e '+q(new)+' ]; [ ! -L '+q(new)+' ]; cat /tmp/me302kl-repair-transfer.bin > '+q(new)+'; chown '+str(int(entry['uid']))+':'+str(int(entry['gid']))+' '+q(new)+'; chmod '+q(entry['mode'])+' '+q(new)+'; chcon '+q(entry['label'])+' '+q(new))
    if sha(device.binary(new))!=entry['sha256']:raise RuntimeError('Staged file verification failed')
    device.shell('mv -f '+q(new)+' '+q(physical))

def install(device,manifest,folder,backup,rollback=False):
    state=backup_state(device,manifest,backup)
    recover_mount(device)
    try:
        current={}
        for path,spec in state['files'].items():
            physical=MOUNT+('/system'+path if path.startswith('/vendor/') else path)
            cur,_=device.snapshot(physical);current[path]=cur
            desired={'kind':'link','target':LINK} if path==ALIAS else {'kind':'file','sha256':manifest['files'][path]['sha256']}
            if not same(spec,cur) and not same(desired,cur):raise RuntimeError('File changed since backup; stopped before writing: '+path)
        # Recheck all dependency hashes before any write, including rollback.
        for path,expected in manifest['dependencies'].items():
            if sha(device.binary(MOUNT+'/system'+path))!=expected:raise RuntimeError('Dependency mismatch: '+path)
        desired={ALIAS:{'kind':'link','target':LINK}}
        desired.update({p:dict(s,kind='file') for p,s in manifest['files'].items()})
        if rollback:desired=state['files']
        plan=[p for p in desired if not same(desired[p],current[p])]
        save(backup/('rollback-plan.json' if rollback else 'install-plan.json'),{'paths':plan,'started':datetime.datetime.now().isoformat()})
        if plan:
            device.shell('mount -o remount,rw '+q(MOUNT))
            with zipfile.ZipFile(backup/'files.zip') as z:
                for path in plan:
                    entry=desired[path];blob=None
                    if entry['kind']=='file':blob=z.read(path.lstrip('/')) if rollback else (folder/'payload'/entry['payload']).read_bytes()
                    write_target(device,path,entry,blob,backup)
                    physical=MOUNT+('/system'+path if path.startswith('/vendor/') else path)
                    got,_=device.snapshot(physical)
                    if not same(entry,got):raise RuntimeError('Written file verification failed: '+path)
                    if entry['kind']=='file' and any(got[k]!=entry[k] for k in ['uid','gid','mode','label']):raise RuntimeError('Written metadata verification failed: '+path)
            device.shell('sync')
        print(('Restored' if rollback else 'Installed'),len(plan),'file/link changes; no boot/EFS/userdata writes.')
    finally:
        device.shell('rm -f /tmp/me302kl-repair-transfer.bin',check=False)
        device.shell('umount '+q(MOUNT))
    # Only after our mount is removed; never run fsck against a live mounted fs.
    for flags,allowed in [('-fp',{0,1}),('-fn',{0})]:
        device.shell('set -e; for src in $(awk \'{print $1}\' /proc/mounts); do [ "$(readlink -f "$src")" != '+q(BLOCK)+' ] || { echo "System was mounted again; filesystem check stopped."; exit 99; }; done')
        result=device.call('shell','e2fsck '+flags+' '+q(BLOCK),check=False)
        log=backup/(('rollback' if rollback else 'install')+'-e2fsck'+flags+'.txt');log.write_bytes(result.stdout+result.stderr)
        if result.returncode not in allowed:raise RuntimeError('Filesystem check needs attention. Stay in TWRP; see '+str(log))
    save(backup/('rollback-complete.json' if rollback else 'install-complete.json'),{'paths':plan,'verified':True})
    print('Filesystem verification passed. Reboot Android, enable rooted debugging if needed, then run '+('restore-settings' if rollback else 'configure')+'.')

def configure(device,manifest,backup,restore=False):
    state=backup_state(device,manifest,backup);device.android();device.root()
    if not restore:
        changes,_,_=check_files(device,manifest)
        if changes:raise RuntimeError('Repaired files not all installed; settings unchanged')
        globals_={'bluetooth_disabled_profiles':'0','mobile_data':'0','data_roaming':'0','airplane_mode_radios':'cell,nfc,wimax'}
        props={p:'1' for p in PROPS};packages={p:3 for p in state['packages']}
    else:globals_=state['globals'];props=state['properties'];packages=state['packages']
    for name,value in globals_.items():
        device.shell('settings '+('delete global '+name if value=='null' else 'put global '+name+' '+q(value)))
    for name,value in props.items():device.shell('setprop '+name+' '+q(value))
    verbs={0:'default-state',1:'enable',2:'disable',3:'disable-user',4:'disable-until-used'}
    for name,value in packages.items():device.shell('pm '+verbs[value]+' --user 0 '+name)
    for name,value in props.items():
        if device.shell('getprop '+name)!=value:raise RuntimeError('Property verification failed: '+name)
    for name,value in globals_.items():
        if device.shell('settings get global '+name)!=value:raise RuntimeError('Setting verification failed: '+name)
    print('Settings restored.' if restore else 'Bluetooth HFP enabled; Wi-Fi-only/GPS power settings configured.')
    print('Reboot once more to apply startup/profile settings. Location, Wi-Fi, Bluetooth toggles and rotation were preserved.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',default='adb');p.add_argument('--serial',required=True)
    p.add_argument('--folder',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--backup',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('action',choices=['build','check','prepare','install','configure','rollback','restore-settings'])
    a=p.parse_args();d=Device(a.adb,a.serial)
    if a.action=='build':
        if not a.output:p.error('--output is required')
        build(d,Path(__file__).resolve().parents[1],a.output);return
    m=read_bundle(a.folder)
    if a.action=='check':
        d.android();d.root();changes,_,_=check_files(d,m)
        print('Compatible:',ROM);print('File/link changes needed:',len(changes))
        print('Wi-Fi-only package: cellular services disabled; shared modem retained for GPS.')
        print('No files or settings changed.');return
    if not a.backup:p.error('--backup is required')
    if a.action=='prepare':prepare(d,m,a.backup)
    elif a.action in ('install','rollback'):install(d,m,a.folder,a.backup,a.action=='rollback')
    else:configure(d,m,a.backup,a.action=='restore-settings')

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError,subprocess.SubprocessError) as e:
        print('STOP:',e,file=sys.stderr);sys.exit(1)
