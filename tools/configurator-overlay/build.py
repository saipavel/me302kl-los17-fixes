"""Build/sign the one-resource Android 10 overlay. Signing keys stay private.

ME302KL_OVERLAY_STOREPASS must contain the private keystore password.
"""
from pathlib import Path
import argparse,os,subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--aapt2',required=True,type=Path)
p.add_argument('--framework',required=True,type=Path)
p.add_argument('--java-home',required=True,type=Path)
p.add_argument('--keystore',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
if not os.environ.get('ME302KL_OVERLAY_STOREPASS'):
    p.error('Set ME302KL_OVERLAY_STOREPASS without putting the password in command arguments')
here=Path(__file__).resolve().parent
a.output.parent.mkdir(parents=True,exist_ok=True)
compiled=a.output.with_suffix('.resources.zip')
unsigned=a.output.with_suffix('.unsigned.apk')
commands=[
    [str(a.aapt2),'compile','--dir',str(here/'res'),'-o',str(compiled)],
    [str(a.aapt2),'link','-I',str(a.framework),'--manifest',str(here/'AndroidManifest.xml'),
     '--auto-add-overlay','-R',str(compiled),'-o',str(unsigned)],
    [str(a.java_home/'bin/jarsigner.exe'),'-keystore',str(a.keystore),
     '-storepass:env','ME302KL_OVERLAY_STOREPASS','-sigalg','SHA256withRSA',
     '-digestalg','SHA-256','-signedjar',str(a.output),str(unsigned),'me302kl-overlay'],
    [str(a.java_home/'bin/jarsigner.exe'),'-verify',str(a.output)],
]
for command in commands:
    r=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if r.returncode:
        raise SystemExit(Path(command[0]).name+' failed:\n'+r.stdout)
    if r.stdout.strip():print(r.stdout.strip())
print('Built and verified',a.output)
