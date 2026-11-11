"""Build the ARM32 adapter using Zig 0.13.0 and private device link libraries.

Example: python build.py --zig /path/to/zig --libs /path/to/libs --output gps-power.so
Required libraries: libc.so, libdl.so, liblog.so, pulled from this tablet.
No proprietary library is copied into the output or included in this repository.
"""
import argparse
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--zig', required=True)
p.add_argument('--libs', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
libraries = [a.libs / name for name in ('libc.so', 'libdl.so', 'liblog.so')]
for library in libraries:
    if not library.is_file():
        p.error(f'Missing private link library: {library}')
environment = os.environ.copy()
environment.setdefault('ZIG_GLOBAL_CACHE_DIR', str(a.output.resolve().parent / '.zig-cache'))
source = Path(__file__).with_name('gps_power.c').resolve()
try:
    source_argument = os.path.relpath(source).replace(os.sep, '/')
except ValueError:  # A different Windows drive cannot have a relative path.
    source_argument = str(source)
subprocess.run([
    a.zig, 'cc', '-target', 'arm-linux-android', '-mcpu=krait', '-mfloat-abi=softfp',
    '-shared', '-fPIC', '-nostdlib', '-fno-stack-protector', '-fno-builtin',
    '-Wall', '-Wextra', '-Werror', '-Wl,-soname,gps.msm8960.so',
    source_argument, *map(str, libraries),
    '-o', str(a.output),
], check=True, env=environment)
