#!/usr/bin/env python3
"""Read-only, synchronized AM/NIO test capture. Ctrl-C stops and archives."""
import argparse, datetime, json, pathlib, re, shutil, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds', type=int, default=300)
parser.add_argument('--interval', type=float, default=3)
parser.add_argument('--label', default='car-comparison')
parser.add_argument('--serial')
a = parser.parse_args()
if a.seconds < 1 or a.interval < 2: parser.error('seconds >= 1, interval >= 2 required')
adb = [shutil.which('adb') or 'adb'] + (['-s', a.serial] if a.serial else [])
out = ROOT / 'data/am-landscape' / ('capture-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
out.mkdir(parents=True)
def now(): return datetime.datetime.now().astimezone().isoformat()
def run(name, *args):
    start = now()
    try:
        r = subprocess.run(adb + list(args), capture_output=True, timeout=18)
        (out / name).write_bytes(r.stdout + (b'\nSTDERR:\n' + r.stderr if r.stderr else b''))
        return {'file': name, 'start': start, 'end': now(), 'exit': r.returncode}
    except Exception as exc: return {'file': name, 'start': start, 'end': now(), 'error': str(exc)}
check = subprocess.run(adb + ['get-state'], capture_output=True, timeout=10)
if check.returncode or check.stdout.strip() != b'device': parser.exit(1, 'Phone not connected; no capture started.\n')
meta = {'label': a.label, 'start': now(), 'interval': a.interval, 'records': []}
for name, args in [('device-time.txt', ['shell','date']), ('device.txt',['shell','getprop','ro.build.fingerprint']), ('accessibility.txt',['shell','settings','get','secure','enabled_accessibility_services']), ('vidhub-package.txt',['shell','dumpsys','package','com.oumi.utility.media.hub']), ('quark-package.txt',['shell','dumpsys','package','com.quark.browser'])]:
    meta['records'].append(run(name,*args))
meta['records'].append(run('system-before.log','logcat','-b','all','-d','-t','2000','-v','threadtime'))
log = (out / 'system-live.log').open('wb')
p = subprocess.Popen(adb + ['logcat','-b','all','-v','threadtime','-T','1'], stdout=log, stderr=subprocess.STDOUT)
print('Capture active: ' + str(out), flush=True)
print('Test VidHub and Quark one at a time. Mark start/end in each helper. Ctrl-C finishes.', flush=True)
begin = time.monotonic(); i = 0
try:
    while time.monotonic() - begin < a.seconds:
        tick = time.monotonic(); prefix = f'{i:04d}'
        # Sequential commands: timestamps preserve their actual observation order.
        for suffix, args in [('activities',['shell','dumpsys','activity','activities']), ('windows',['shell','dumpsys','window','windows']), ('display',['shell','dumpsys','display'])]:
            meta['records'].append(run(prefix+'-'+suffix+'.txt',*args))
        (out/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
        i += 1
        time.sleep(max(0, a.interval - (time.monotonic()-tick)))
except KeyboardInterrupt: pass
finally:
    p.terminate()
    try: p.wait(timeout=5)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
    log.close()
    for pkg, folder in [('com.oumi.utility.media.hub','vidhub'), ('com.quark.browser','quark')]:
        meta['records'].append(run('pull-'+folder+'.txt','pull','/sdcard/Android/data/'+pkg+'/files/diagnostics',str(out/folder)))
    meta['records'].append(run('audio-final.txt','shell','dumpsys','audio'))
    meta['end'] = now(); meta['samples'] = i; meta['logcat_exit'] = p.returncode
    (out/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    pat = re.compile(r'code.?102|abortActivityStart|ScreenCastController|mWindowType|mScreenType|adjustOrientation|modify orientation|com\.apple\.android\.music|com\.quark\.browser|com\.oumi\.utility\.media\.hub',re.I)
    with (out/'system-live.log').open(errors='replace') as src, (out/'key-events.log').open('w') as dst:
        for line in src:
            if pat.search(line): dst.write(line)
    failures = [r for r in meta['records'] if r.get('exit',0) or 'error' in r]
    (out/'README.txt').write_text('Observed samples: '+str(i)+'\nFailed commands: '+str(len(failures))+' (inspect manifest.json; absent package logs are expected).\nRaw logs may include private app/system data; archive locally.\nNo success inference is made from launch return values. Match AM ActivityRecord, CurrentConfiguration and system start result.\n')
    archive = shutil.make_archive(str(out),'zip',root_dir=out)
    print('Saved: '+archive, flush=True)
