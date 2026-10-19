#!/usr/bin/env python3
"""Verify a host UI tap against the selected native MediaSession, not car audio/visual latency."""
import argparse, datetime, json, pathlib, re, subprocess, time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--package', choices=['com.apple.android.music', 'com.spotify.music'], required=True)
p.add_argument('--display', type=int, required=True)
p.add_argument('--x', type=int, required=True)
p.add_argument('--y', type=int, required=True)
p.add_argument('--expected', choices=['PLAYING', 'PAUSED', 'TOGGLE'], required=True)
p.add_argument('--seconds', type=float, default=8)
o = p.parse_args()
root = pathlib.Path(__file__).resolve().parent.parent
out = root / 'data/native-control' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
out.mkdir(parents=True)

def adb(*args):
    r = subprocess.run(['adb', *args], capture_output=True, text=True, timeout=15)
    if r.returncode:
        raise RuntimeError(r.stdout + r.stderr)
    return r.stdout

def snapshot(index):
    raw = adb('shell', 'dumpsys', 'media_session')
    (out / ('session-%03d.txt' % index)).write_text(raw)
    match = re.search(r'^\s+package=' + re.escape(o.package) + r'\s*$', raw, re.M)
    if not match:
        raise RuntimeError('Selected native session missing')
    rest = raw[match.end():]
    state = re.search(r'state=PlaybackState \{state=(\w+)\(\d+\), position=(-?\d+)', rest)
    # Require the state to precede the next session owner; never read another app's state.
    boundary = re.search(r'\n\s+ownerPid=', rest)
    if not state or (boundary and state.start() > boundary.start()):
        raise RuntimeError('Selected session has no playback state')
    return {'state': state[1], 'position': int(state[2]), 'observedAt': time.monotonic()}

before = snapshot(0)
if o.expected == 'TOGGLE':
    if before['state'] not in ['PLAYING', 'PAUSED']:
        raise RuntimeError('Cannot toggle an unprepared native player')
    o.expected = 'PAUSED' if before['state'] == 'PLAYING' else 'PLAYING'
if before['state'] == o.expected:
    raise RuntimeError('Already in expected state; this would not prove the tap worked')
started = time.monotonic()
adb('shell', 'input', '-d', str(o.display), 'tap', str(o.x), str(o.y))
samples = []
passed = False
while time.monotonic() - started < o.seconds:
    current = snapshot(len(samples) + 1)
    samples.append(current)
    if current['state'] == o.expected:
        passed = True
        break
    time.sleep(.2)
result = {'package': o.package, 'hostDisplay': o.display, 'tap': [o.x, o.y],
          'before': before, 'samples': samples, 'expected': o.expected, 'passed': passed,
          'stateObservedAfterMs': round((samples[-1]['observedAt'] - started) * 1000) if passed else None,
          'limits': 'State observation includes adb/polling delay. Does not prove visible response latency or car audio.'}
(out / 'result.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result), flush=True)
print('Evidence ' + str(out), flush=True)
if not passed:
    raise SystemExit(1)
