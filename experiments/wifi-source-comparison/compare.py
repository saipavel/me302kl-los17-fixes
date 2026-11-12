"""Compare selected C function tokens; not a C compiler or semantic equivalence proof.

Usage: python compare.py --asus-tree PATH_TO_EXTRACTED_KERNEL --sweet PATH --output report.json
Sweet files must be from the pinned commit documented in README.md.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

LEXER = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\d+|\S', re.S)


def functions(source):
    tokens = [t if t != '__FUNCTION__' else '__func__'
              for t in LEXER.findall(source) if not t.startswith(('/*', '//'))]
    result = {}
    for i, token in enumerate(tokens):
        if (token != '(' or i == 0 or
                not re.fullmatch(r'[A-Za-z_]\w*', tokens[i-1]) or
                tokens[i-1] in ('if', 'while', 'for', 'switch')):
            continue
        depth, j = 1, i + 1
        while j < len(tokens) and depth:
            depth += (tokens[j] == '(') - (tokens[j] == ')')
            j += 1
        if j == len(tokens) or tokens[j] != '{':
            continue
        depth, j = 1, j + 1
        while j < len(tokens) and depth:
            depth += (tokens[j] == '{') - (tokens[j] == '}')
            j += 1
        if depth:
            raise ValueError('Unbalanced body: ' + tokens[i-1])
        name = tokens[i-1]
        if name in result:
            raise ValueError('Multiple definitions: ' + name)
        result[name] = tokens[i-1:j]
    return result


FILES = {
    'wlan_qct_wdi.c': ('CORE/WDI/CP/src/', [
        'WDI_SendNvBlobReq', 'WDI_ProcessNvDownloadReq',
        'WDI_ProcessNvDownloadRsp', 'WDI_GetMessageBuffer', 'WDI_SendMsg',
        'WDI_ResponseTimerCB']),
    'wlan_qct_wdi_cts.c': ('CORE/WDI/TRP/CTS/src/', [
        'WCTS_OpenTransport', 'WCTS_CloseTransport', 'WCTS_SendMessage',
        'WCTS_PALReadCallback', 'WCTS_PALWriteCallback', 'WCTS_PALDataCallback',
        'WCTS_NotifyCallback']),
    'wlan_qct_pal_device.c': ('CORE/WDI/WPAL/src/', [
        'wpalDeviceInit', 'wpalDeviceClose']),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asus-tree', required=True, type=Path)
    parser.add_argument('--sweet', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = {'comparison': 'C tokens: comments and whitespace ignored; __FUNCTION__ normalized to __func__; preprocessing, types and macros not evaluated', 'files': {}}
    for filename, (relative, names) in FILES.items():
        sweet_path = args.sweet / filename
        sweet = functions(sweet_path.read_text(encoding='utf-8'))
        entry = {'sweet_sha256': sha(sweet_path), 'branches': {}}
        for branch in ('net/wireless', 'staging'):
            path = args.asus_tree / 'drivers' / branch / 'prima' / relative / filename
            official = functions(path.read_text(encoding='utf-8'))
            selected = {}
            for name in names:
                if name not in sweet or name not in official:
                    raise ValueError('Missing selected definition: ' + name)
                selected[name] = 'equal_tokens' if sweet[name] == official[name] else 'different_tokens'
            entry['branches'][branch] = {'sha256': sha(path), 'functions': selected}
        report['files'][filename] = entry
    a = args.asus_tree / 'arch/arm/mach-msm/smd.c'
    b = args.sweet / 'smd.c'
    report['smd'] = {'asus_sha256': sha(a), 'sweet_sha256': sha(b),
                     'identical_bytes': a.read_bytes() == b.read_bytes()}
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Compared 15 selected function bodies in both ASUS trees, plus full smd.c.')


if __name__ == '__main__':
    main()
