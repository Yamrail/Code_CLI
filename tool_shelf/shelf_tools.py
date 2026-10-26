"""Offline source inventory and packaged-byte verification (Python stdlib only).

This is an inspection alternative, not an implementation of missing YamRail tools.
It never imports or executes recovered source objects and never uses a network.
"""
import argparse
import hashlib
import json
import stat
from pathlib import Path


def contained_regular(root, relative):
    candidate = root / relative
    if candidate.is_symlink() or candidate.resolve().is_relative_to(root.resolve()) is False:
        raise ValueError('HOLD_PATH_ESCAPE_OR_LINK')
    info = candidate.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('HOLD_NONREGULAR_OR_HARDLINK')
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'verify'])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.command == 'list':
        result = json.loads(contained_regular(root, 'TOOLS.json').read_text(encoding='utf-8'))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print('OFFLINE TOOL SHELF — metadata is not installation or execution')
            print(json.dumps(result['summary'], ensure_ascii=False))
            for tool in result['tools']:
                if tool['kind'] != 'SOURCE_FAMILY':
                    print(f"{tool['id']}: {tool['disposition']} | {tool['execution_status']}")
        return 0
    manifest = json.loads(contained_regular(root, 'SHELF_MANIFEST.json').read_text(encoding='utf-8'))
    checks = []
    for entry in manifest['files']:
        try:
            path = contained_regular(root, entry['path'])
            raw = path.read_bytes()
            actual = hashlib.sha256(raw).hexdigest()
            ok = actual == entry['sha256'] and len(raw) == entry['bytes']
            checks.append({'path': entry['path'], 'pass': ok})
        except (OSError, ValueError) as error:
            checks.append({'path': entry['path'], 'pass': False, 'error': type(error).__name__})
    result = {'state': 'PASS_PACKAGED_SHELF_BYTES' if checks and all(c['pass'] for c in checks) else 'HOLD_SHELF_BYTES',
              'evidence_class': 'LOCAL_EXECUTED', 'checks': checks,
              'verification_scope': 'THIS_BYTE_VERIFIER_ONLY; NATIVE_RENDER_EXECUTIONS_HAVE_SEPARATE_RECEIPTS',
              'executed_recovered_tools': 0, 'network_calls': 0,
              'license_or_human_release_approval': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['state'].startswith('PASS_') else 2


if __name__ == '__main__':
    raise SystemExit(main())
