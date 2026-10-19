#!/usr/bin/env python3
"""Arm phone-side bounded collection before unplugging USB; no network required."""
import argparse,datetime,json,pathlib,shlex,subprocess
ROOT=pathlib.Path(__file__).resolve().parent.parent
STATE=ROOT/'data/am-landscape/offline-capture-state.json'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('action',choices=['start','status','stop','pull'])
p.add_argument('--minutes',type=int,default=30)
p.add_argument('--interval',type=int,default=10)
a=p.parse_args()
def adb(*args):
 r=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=30)
 if r.returncode: raise RuntimeError((r.stdout+r.stderr).strip())
 return r.stdout.strip()
try:
 serial=adb('get-serialno')
 if a.action=='start':
  if not 1<=a.minutes<=120 or not 5<=a.interval<=60: raise RuntimeError('minutes 1..120, interval 5..60')
  if STATE.exists():
   previous=json.loads(STATE.read_text())
   if previous['serial']!=serial: raise RuntimeError('Existing capture belongs to another phone')
   done=adb('shell','test -f '+shlex.quote(previous['remote']+'/done')+' && echo done || echo active')
   if done!='done': raise RuntimeError('Previous capture may still be active; stop/pull it first')
  stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
  remote='/sdcard/Download/AM-offline-'+stamp
  script='/data/local/tmp/am-capture-'+stamp+'.sh'
  body="""#!/system/bin/sh
OUT="$1"
SECONDS_LIMIT="$2"
INTERVAL="$3"
mkdir -p "$OUT"
date > "$OUT/start.txt"
getprop ro.build.fingerprint > "$OUT/build.txt"
settings get secure enabled_accessibility_services > "$OUT/accessibility.txt"
dumpsys package com.oumi.utility.media.hub > "$OUT/vidhub-package.txt"
dumpsys package com.quark.browser > "$OUT/quark-package.txt"
logcat -b all -d -t 2000 -v threadtime > "$OUT/system-before.log"
logcat -b all -T 1 -v threadtime -f "$OUT/system-live.log" -r 8192 -n 7 &
LOG_PID=$!
echo "$LOG_PID" > "$OUT/logcat.pid"
finish() {
 kill "$LOG_PID" 2>/dev/null
 wait "$LOG_PID" 2>/dev/null
 timeout 12 dumpsys audio > "$OUT/audio-final.txt"
 for PKG in com.oumi.utility.media.hub com.quark.browser; do
  mkdir -p "$OUT/$PKG"
  cp /sdcard/Android/data/$PKG/files/diagnostics/*.jsonl "$OUT/$PKG/" 2>> "$OUT/errors.txt"
 done
 cp /sdcard/Download/am-embedded-server.log /sdcard/Download/am-local-bridge.log /sdcard/Download/am-bridge-supervisor.log "$OUT/" 2>> "$OUT/errors.txt"
 date > "$OUT/done"
}
trap 'finish; exit' INT TERM HUP
START=$(date +%s)
INDEX=0
while [ $(($(date +%s)-START)) -lt "$SECONDS_LIMIT" ] && [ ! -f "$OUT/stop" ]; do
 date >> "$OUT/timeline.txt"
 echo "sample=$INDEX" >> "$OUT/timeline.txt"
 timeout 12 dumpsys activity activities > "$OUT/$INDEX-activities.txt"
 timeout 12 dumpsys window windows > "$OUT/$INDEX-windows.txt"
 timeout 12 dumpsys display > "$OUT/$INDEX-display.txt"
 INDEX=$((INDEX+1))
 sleep "$INTERVAL"
done
finish
"""
  local=ROOT/'data/am-landscape'/('offline-script-'+stamp+'.sh')
  local.parent.mkdir(parents=True,exist_ok=True);local.write_text(body)
  adb('push',str(local),script)
  command='mkdir -p '+shlex.quote(remote)+'; nohup sh '+shlex.quote(script)+' '+shlex.quote(remote)+' '+str(a.minutes*60)+' '+str(a.interval)+' >'+shlex.quote(remote+'/runner.log')+' 2>&1 </dev/null & echo $!'
  pid=adb('shell',command)
  STATE.write_text(json.dumps({'serial':serial,'remote':remote,'script':script,'pid':pid,'minutes':a.minutes,'interval':a.interval},indent=2))
  print('Armed on phone: '+remote+'; duration '+str(a.minutes)+' minutes. USB and network are not needed while recording.')
 else:
  s=json.loads(STATE.read_text())
  if s['serial']!=serial: raise RuntimeError('Capture belongs to a different phone')
  remote=shlex.quote(s['remote'])
  if a.action=='stop':
   print(adb('shell','touch '+remote+'/stop; echo "Stop requested; finish after current sample."'))
  elif a.action=='status':
   print(adb('shell','if [ -f '+remote+'/done ]; then echo finished; cat '+remote+'/done; else echo pending; tail -4 '+remote+'/timeline.txt; fi; du -sh '+remote))
  else:
   dest=ROOT/'data/am-landscape'/pathlib.Path(s['remote']).name
   print(adb('pull',s['remote'],str(dest)))
   print('Saved: '+str(dest))
except Exception as exc: p.exit(1,str(exc)+'\n')
