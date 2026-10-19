#!/usr/bin/env python3
"""Narrow, reversible fallback for the real sky-window display; never changes size/density."""
import argparse, json, re, subprocess
from pathlib import Path

DISPLAY = '90000005'
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'data/am-landscape/car-rotation-backup.json'

def adb(*args):
    r = subprocess.run(['adb', *args], capture_output=True, text=True, timeout=20)
    if r.returncode:
        raise RuntimeError((r.stderr + r.stdout).strip())
    return r.stdout.strip()

def read_state():
    try:
        ignore = adb('shell', 'wm', 'get-ignore-orientation-request', '-d', DISPLAY)
    except RuntimeError as exc:
        raise RuntimeError('Sky-window unavailable; no settings changed. ' + str(exc))
    match = re.search(r'ignoreOrientationRequest\s+(true|false)\s+for displayId=90000005', ignore)
    if not match:
        raise RuntimeError('Sky-window display unavailable or response unsupported: ' + ignore)
    rotation = adb('shell', 'wm', 'user-rotation', '-d', DISPLAY)
    if not re.fullmatch(r'free|lock [0-3]', rotation):
        raise RuntimeError('Rotation response unsupported: ' + rotation)
    fixed = adb('shell', 'wm', 'fixed-to-user-rotation', '-d', DISPLAY)
    if fixed not in ('default', 'enabled', 'disabled'):
        raise RuntimeError('Fixed rotation response unsupported: ' + fixed)
    return {'serial': adb('get-serialno'), 'ignore': match[1] == 'true', 'rotation': rotation, 'fixed': fixed}

def restore(saved):
    adb('shell', 'wm', 'fixed-to-user-rotation', '-d', DISPLAY, saved['fixed'])
    adb('shell', 'wm', 'set-ignore-orientation-request', '-d', DISPLAY, '1' if saved['ignore'] else '0')
    adb('shell', 'wm', 'user-rotation', '-d', DISPLAY, *saved['rotation'].split())

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=['status', 'apply', 'restore'])
args = parser.parse_args()
try:
    current = read_state()  # Fails before mutation when the car is disconnected.
    if args.action == 'status':
        print(json.dumps(current, ensure_ascii=False))
    elif args.action == 'apply':
        if STATE.exists():
            raise RuntimeError('A backup already exists. Restore the previous run first: ' + str(STATE))
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(current, indent=2))
        try:
            adb('shell', 'wm', 'set-ignore-orientation-request', '-d', DISPLAY, '1')
            adb('shell', 'wm', 'fixed-to-user-rotation', '-d', DISPLAY, 'enabled')
            adb('shell', 'wm', 'user-rotation', '-d', DISPLAY, 'lock', '1')
            result = read_state()
            if not result['ignore'] or result['rotation'] != 'lock 1' or result['fixed'] != 'enabled':
                raise RuntimeError('Settings did not stay applied: ' + str(result))
            print('Applied; actual AM window orientation still needs verification. Backup: ' + str(STATE))
        except Exception:
            restore(current)
            STATE.unlink()
            raise
    else:
        saved = json.loads(STATE.read_text())
        if saved['serial'] != current['serial']:
            raise RuntimeError('Backup belongs to a different phone')
        if saved.get('fixed') not in ('default', 'enabled', 'disabled') or not isinstance(saved['ignore'], bool) or not re.fullmatch(r'free|lock [0-3]', saved['rotation']):
            raise RuntimeError('Invalid backup')
        restore(saved)
        result = read_state()
        if result != saved:
            raise RuntimeError('Restore readback mismatch; keeping backup: ' + str(result))
        STATE.unlink()
        print('Restored original rotation settings.')
except Exception as exc:
    parser.exit(1, str(exc) + '\n')
