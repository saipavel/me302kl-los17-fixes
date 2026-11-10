#!/usr/bin/env python3
"""Generate or reverse an exact-build repair file. Does not access a device."""
import argparse
import hashlib
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / 'patches' / '2026-11-10.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def transform(data, spec, reverse=False):
    before, after = ('after', 'before') if reverse else ('before', 'after')
    if len(data) != spec[before + '_bytes'] or digest(data) != spec[before + '_sha256']:
        raise ValueError('Input does not match this exact ROM file; no output written')
    output, cursor, shift = bytearray(), 0, 0
    for edit in spec['edits']:
        old = bytes.fromhex(edit['before_hex'])
        new = bytes.fromhex(edit['after_hex'])
        offset = edit['offset'] + (shift if reverse else 0)
        expected, replacement = (new, old) if reverse else (old, new)
        if offset < cursor or data[offset:offset + len(expected)] != expected:
            raise ValueError('Patch bytes or ordering do not match')
        output.extend(data[cursor:offset])
        output.extend(replacement)
        cursor = offset + len(expected)
        shift += len(new) - len(old)
    output.extend(data[cursor:])
    result = bytes(output)
    if len(result) != spec[after + '_bytes'] or digest(result) != spec[after + '_sha256']:
        raise ValueError('Output verification failed; no output written')
    return result


def main():
    specs = json.loads(MANIFEST.read_text(encoding='utf-8'))['repairs']
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true', help='List supported exact-build repairs')
    parser.add_argument('--reverse', action='store_true', help='Recover the original from a repaired file')
    parser.add_argument('repair', nargs='?', choices=sorted(specs))
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('output', nargs='?', type=Path)
    args = parser.parse_args()
    if args.list:
        for key, spec in specs.items():
            print(key + ': ' + spec['device_path'])
        return
    if not all((args.repair, args.input, args.output)):
        parser.error('repair, input and output are required (or use --list)')
    try:
        result = transform(args.input.read_bytes(), specs[args.repair], args.reverse)
        # Exclusive creation: never overwrite an original or an existing result.
        with args.output.open('xb') as output:
            output.write(result)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print('Verified SHA-256: ' + digest(result))
    print('Created ' + str(args.output) + '; nothing installed on the tablet.')


if __name__ == '__main__':
    main()
