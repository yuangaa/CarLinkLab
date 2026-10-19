#!/usr/bin/env python3
"""Start a phone-only, localhost AM bridge before going to the car."""
import argparse,pathlib,subprocess,json,secrets,shlex
ROOT=pathlib.Path(__file__).resolve().parent.parent
STATE=ROOT/'data/am-embedded/bridge-state.json'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('action',choices=['start','status','stop'])
p.add_argument('--minutes',type=int,default=60)
p.add_argument('--package',choices=['com.oumi.utility.media.hub','com.quark.browser'],default='com.oumi.utility.media.hub')
a=p.parse_args()
def adb(*args):
 r=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=30)
 if r.returncode: raise RuntimeError((r.stdout+r.stderr).strip())
 return r.stdout.strip()
try:
 serial=adb('get-serialno')
 if a.action=='start':
  if not 1<=a.minutes<=120:raise RuntimeError('minutes must be 1..120')
  if STATE.exists():
   old=json.loads(STATE.read_text())
   if old['serial']!=serial:raise RuntimeError('Bridge state belongs to another phone')
   result=adb('shell','test -f /sdcard/Download/am-bridge-supervisor.done && echo done || echo pending')
   if result!='done':raise RuntimeError('Stop previous bridge before starting another one')
  if not adb('shell','pm','path',a.package): raise RuntimeError('Shell app is not installed')
  subprocess.run(['zsh',str(ROOT/'tools/build-canvas-awake.sh')],check=True)
  adb('push',str(ROOT/'data/canvas-power/dex/classes.dex'),'/data/local/tmp/am-canvas-awake.dex')
  files='/sdcard/Android/data/'+a.package+'/files'
  adb('shell','mkdir -p '+shlex.quote(files))
  local=ROOT/'data/am-embedded';local.mkdir(parents=True,exist_ok=True)
  token=local/'bridge-token';token.write_text(secrets.token_hex(32))
  adb('push',str(token),files+'/bridge-token')
  token.unlink()
  adb('push',str(ROOT/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy-server'),'/data/local/tmp/am-embedded-server.jar')
  adb('push',str(ROOT/'apps/am-landscape/bridge/classes.dex'),'/data/local/tmp/am-local-bridge.dex')
  script=local/'supervisor.sh'
  script.write_text(r"""#!/system/bin/sh
FILES="$1"
LIMIT="$2"
START=$(date +%s)
echo $$ > /sdcard/Download/am-bridge-supervisor.pid
finish() {
 [ -n "$AWAKE" ] && kill "$AWAKE" 2>/dev/null
 [ -n "$SERVER" ] && kill "$SERVER" 2>/dev/null
 [ -n "$BRIDGE" ] && kill "$BRIDGE" 2>/dev/null
 rm -f "$FILES/bridge-ready"
 date > /sdcard/Download/am-bridge-supervisor.done
}
trap 'finish; exit' TERM INT HUP
while [ $(($(date +%s)-START)) -lt "$LIMIT" ] && [ ! -f /sdcard/Download/am-bridge-supervisor.stop ]; do
 if [ ! -f "$FILES/bridge-ready" ]; then sleep 1; continue; fi
 SESSION=$(cat "$FILES/bridge-ready")
 CANVAS=3232x3248/600
 if [ -f "$FILES/bridge-canvas" ]; then
  read CANVAS_W CANVAS_H CANVAS_D CANVAS_EXTRA < "$FILES/bridge-canvas"
  case "$CANVAS_W:$CANVAS_H:$CANVAS_D" in
   *[!0-9:]*|::*|:*|*:) ;; 
   *) if [ -z "$CANVAS_EXTRA" ] && [ "$CANVAS_W" -ge 512 ] && [ "$CANVAS_W" -le 4096 ] && [ "$CANVAS_H" -ge 512 ] && [ "$CANVAS_H" -le 4096 ] && [ "$CANVAS_D" -ge 160 ] && [ "$CANVAS_D" -le 600 ]; then CANVAS=${CANVAS_W}x${CANVAS_H}/${CANVAS_D}; fi ;;
  esac
 fi
 echo "session=$SESSION canvas=$CANVAS"
 CLASSPATH=/data/local/tmp/am-local-bridge.dex app_process / lab.carlink.bridge.LocalBridge "$FILES/bridge-token" >> /sdcard/Download/am-local-bridge.log 2>&1 &
 BRIDGE=$!
 sleep 1
 LOG_START=$(wc -l < /sdcard/Download/am-embedded-server.log)
 CLASSPATH=/data/local/tmp/am-embedded-server.jar app_process / com.genymobile.scrcpy.Server 5.0 scid=414d0001 tunnel_forward=false audio=false control=true cleanup=false send_device_meta=false send_dummy_byte=false new_display="$CANVAS" vd_system_decorations=false display_ime_policy=local max_size=2560 max_fps=30 video_bit_rate=8000000 clipboard_autosync=false >> /sdcard/Download/am-embedded-server.log 2>&1 &
 SERVER=$!
 CANVAS_ID=""
 ATTEMPT=0
 while [ "$ATTEMPT" -lt 10 ] && kill -0 "$SERVER" 2>/dev/null; do
  CANVAS_ID=$(tail -n +$((LOG_START+1)) /sdcard/Download/am-embedded-server.log | sed -n 's/.*New display:.*(id=\([0-9]*\)).*/\1/p' | tail -1)
  [ -n "$CANVAS_ID" ] && break
  ATTEMPT=$((ATTEMPT+1)); sleep 1
 done
 if [ -n "$CANVAS_ID" ]; then
  CLASSPATH=/data/local/tmp/am-canvas-awake.dex app_process / HoldCanvasAwake "$CANVAS_ID" "$LIMIT" >> /sdcard/Download/am-canvas-awake.log 2>&1 &
  AWAKE=$!
 else
  echo "Canvas wake lock unavailable: source display ID missing"
 fi
 while kill -0 "$SERVER" 2>/dev/null && kill -0 "$BRIDGE" 2>/dev/null && [ "$(cat "$FILES/bridge-ready" 2>/dev/null)" = "$SESSION" ] && [ $(($(date +%s)-START)) -lt "$LIMIT" ] && [ ! -f /sdcard/Download/am-bridge-supervisor.stop ]; do sleep 1; done
 [ -n "$AWAKE" ] && kill "$AWAKE" 2>/dev/null
 AWAKE=""
 kill "$SERVER" "$BRIDGE" 2>/dev/null
 wait "$SERVER" 2>/dev/null
 wait "$BRIDGE" 2>/dev/null
 SERVER=""
 BRIDGE=""
 sleep 1
done
finish
""")
  adb('push',str(script),'/data/local/tmp/am-bridge-supervisor.sh')
  adb('shell','rm -f /sdcard/Download/am-bridge-supervisor.stop /sdcard/Download/am-bridge-supervisor.done; : > /sdcard/Download/am-local-bridge.log; : > /sdcard/Download/am-embedded-server.log')
  pid=adb('shell','nohup sh /data/local/tmp/am-bridge-supervisor.sh '+shlex.quote(files)+' '+str(a.minutes*60)+' >/sdcard/Download/am-bridge-supervisor.log 2>&1 </dev/null & echo $!')
  STATE.write_text(json.dumps({'serial':serial,'package':a.package,'pid':pid,'minutes':a.minutes},indent=2))
  print('Phone bridge armed for '+str(a.minutes)+' minutes. Open helper → 原生 AM 大画布（实验）. No external network required.')
 else:
  s=json.loads(STATE.read_text())
  if s['serial']!=serial:raise RuntimeError('Different phone')
  if a.action=='stop':print(adb('shell','touch /sdcard/Download/am-bridge-supervisor.stop; echo "Stop requested"'))
  else:print(adb('shell','if [ -f /sdcard/Download/am-bridge-supervisor.done ]; then echo finished; else echo pending; fi; tail -8 /sdcard/Download/am-embedded-server.log'))
except Exception as exc:p.exit(1,str(exc)+'\n')
