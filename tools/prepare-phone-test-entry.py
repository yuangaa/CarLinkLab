#!/usr/bin/env python3
"""Pre-arm a 24-hour phone-side launcher; recording begins only on phone click."""
import pathlib,subprocess,secrets,ast,json
ROOT=pathlib.Path(__file__).resolve().parent.parent
PRIMARY='/sdcard/Android/data/com.oumi.utility.media.hub/files'
def adb(*args):
 r=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=30)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).strip())
 return r.stdout.strip()
try:
 # Avoid colliding with any currently running bridge.
 for state,done in [(ROOT/'data/am-embedded/bridge-state.json','/sdcard/Download/am-bridge-supervisor.done'),(ROOT/'data/am-landscape/offline-capture-state.json',None)]:
  if state.exists():
   info=json.loads(state.read_text());target=done or info['remote']+'/done'
   if adb('shell','test -f '+target+' && echo done || echo active')!='done':raise RuntimeError('Previous recording still active; finish it before pre-arming.')
 if adb('shell','test -f '+PRIMARY+'/phone-guardian-heartbeat && test $(( $(date +%s) - $(stat -c %Y '+PRIMARY+'/phone-guardian-heartbeat) )) -lt 20 && echo active || echo absent')=='active':raise RuntimeError('Phone launcher already armed; no second launcher started.')
 subprocess.run(['zsh',str(ROOT/'tools/build-canvas-awake.sh')],check=True)
 adb('push',str(ROOT/'data/canvas-power/dex/classes.dex'),'/data/local/tmp/am-canvas-awake.dex')
 out=ROOT/'data/am-phone-entry';out.mkdir(parents=True,exist_ok=True)
 tree=ast.parse((ROOT/'tools/offline-am-capture.py').read_text())
 body=next(node.value.value for node in ast.walk(tree) if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='body' for t in node.targets) and isinstance(node.value,ast.Constant))
 (out/'capture.sh').write_text(body)
 supervisor=(ROOT/'data/am-embedded/supervisor.sh').read_text()
 (out/'supervisor.sh').write_text(supervisor)
 token=out/'token';token.write_text(secrets.token_hex(32))
 for files in [PRIMARY]:
  adb('shell','mkdir -p '+files)
  adb('push',str(token),files+'/bridge-token')
 token.unlink()
 for local,remote in [(ROOT/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy-server','am-embedded-server.jar'),(ROOT/'apps/am-landscape/bridge/classes.dex','am-local-bridge.dex'),(out/'capture.sh','am-phone-capture.sh'),(out/'supervisor.sh','am-phone-supervisor.sh')]:adb('push',str(local),'/data/local/tmp/'+remote)
 guardian=out/'guardian.sh'
 guardian.write_text("""#!/system/bin/sh
FILES="/sdcard/Android/data/com.oumi.utility.media.hub/files"
START=$(date +%s)
STATE=ready
echo ready > "$FILES/phone-guardian-state"
chmod 644 "$FILES/phone-guardian-state"
# Bounded pre-connection buffer: retains handshake evidence before connected status.
BUFFER="$FILES/link-prebuffer"
mkdir -p "$BUFFER"
logcat -b all -T 1 -v threadtime -f "$BUFFER/pre.log" -r 2048 -n 3 &
BUFFER_PID=$!
finish() {
 kill "$BUFFER_PID" 2>/dev/null
 [ -n "$OUT" ] && touch "$OUT/stop"
 touch /sdcard/Download/am-bridge-supervisor.stop
 echo expired > "$FILES/phone-guardian-state"
 rm -f "$FILES/phone-guardian-heartbeat"
}
trap 'finish; exit' TERM INT HUP
while [ $(($(date +%s)-START)) -lt 86400 ]; do
 date +%s > "$FILES/phone-guardian-heartbeat"
 # Link status is post-handshake; prebuffer supplies the preceding evidence.
 LINK=$(settings get global niolink_connect 2>/dev/null)
 NEAR=$(settings get global near_by_connect_status 2>/dev/null)
 if [ "$STATE" = ready ] && [ "$(cat "$FILES/phone-guardian-monitor" 2>/dev/null)" = 1 ] && [ "$LINK" = 1 ]; then
  echo 1 > "$FILES/phone-guardian-autolink"
  date +%s > "$FILES/phone-guardian-start"
 fi
 if [ "$STATE" = running ] && [ "$(cat "$FILES/phone-guardian-autolink" 2>/dev/null)" = 1 ]; then
  if [ "$LINK" = 0 ] && [ "$NEAR" = 0 ]; then
   LINK_MISSING=$((LINK_MISSING+1))
   if [ "$LINK_MISSING" -ge 3 ]; then
    date > "$OUT/nio-link-disconnected.txt"
    touch "$OUT/stop" /sdcard/Download/am-bridge-supervisor.stop
    STATE=stopping
    echo stopping > "$FILES/phone-guardian-state"
   fi
  elif [ "$LINK" = 1 ] || [ "$NEAR" = 1 ]; then
   LINK_MISSING=0
  fi
 fi
 if [ -f "$FILES/phone-guardian-stop" ]; then
  rm -f "$FILES/phone-guardian-stop"
  if [ "$STATE" = running ]; then
   touch "$OUT/stop" /sdcard/Download/am-bridge-supervisor.stop
   STATE=stopping
   echo stopping > "$FILES/phone-guardian-state"
  fi
 fi
 if [ "$STATE" = running ] || [ "$STATE" = stopping ]; then
  if [ -f "$OUT/done" ] && [ -f /sdcard/Download/am-bridge-supervisor.done ]; then
   wait "$CAPTURE" 2>/dev/null
   wait "$BRIDGE" 2>/dev/null
   STATE=ready
   echo ready > "$FILES/phone-guardian-state"
  elif { ! kill -0 "$CAPTURE" 2>/dev/null && [ ! -f "$OUT/done" ]; } || ! kill -0 "$BRIDGE" 2>/dev/null; then
   # Unexpected exit without completion markers: keep evidence and flag failure.
   if [ ! -f "$OUT/done" ] || [ ! -f /sdcard/Download/am-bridge-supervisor.done ]; then
    echo error > "$FILES/phone-guardian-state"
    touch "$OUT/stop" /sdcard/Download/am-bridge-supervisor.stop
    STATE=stopping
   fi
  fi
 fi
 if [ "$STATE" = running ] && [ -f "$OUT/done" ] && [ "$(cat "$FILES/phone-guardian-recording" 2>/dev/null)" != finished ] && kill -0 "$BRIDGE" 2>/dev/null; then
  echo finished > "$FILES/phone-guardian-recording"
  chmod 644 "$FILES/phone-guardian-recording"
 fi
 if [ -f "$FILES/phone-guardian-start" ]; then
  rm -f "$FILES/phone-guardian-start"
  if [ "$STATE" = ready ]; then
   OUT="/sdcard/Download/AM-offline-$(date +%Y%m%d-%H%M%S)"
   mkdir -p "$OUT/pre-connection"
   cp "$BUFFER"/pre.log* "$OUT/pre-connection/" 2>/dev/null
   date > "$OUT/connection-detected.txt"
   echo "$OUT" > "$FILES/phone-guardian-capture"
   chmod 644 "$FILES/phone-guardian-capture"
   rm -f /sdcard/Download/am-bridge-supervisor.stop /sdcard/Download/am-bridge-supervisor.done
   : > /sdcard/Download/am-embedded-server.log
   : > /sdcard/Download/am-local-bridge.log
   sh /data/local/tmp/am-phone-capture.sh "$OUT" 3600 10 > "$OUT/runner.log" 2>&1 &
   CAPTURE=$!
   sh /data/local/tmp/am-phone-supervisor.sh "$FILES" "$((86400-$(date +%s)+START))" > /sdcard/Download/am-bridge-supervisor.log 2>&1 &
   BRIDGE=$!
   echo running > "$FILES/phone-guardian-recording"
   chmod 644 "$FILES/phone-guardian-recording"
   LINK_MISSING=0
   STATE=running
   echo running > "$FILES/phone-guardian-state"
   date >> /sdcard/Download/am-phone-guardian.log
   echo "$OUT capture=$CAPTURE bridge=$BRIDGE" >> /sdcard/Download/am-phone-guardian.log
  fi
 fi
 sleep 2
done
finish
""")
 adb('push',str(guardian),'/data/local/tmp/am-phone-guardian.sh')
 adb('shell','rm -f '+PRIMARY+'/phone-guardian-start '+PRIMARY+'/phone-guardian-stop')
 pid=adb('shell','nohup sh /data/local/tmp/am-phone-guardian.sh >/sdcard/Download/am-phone-guardian-runner.log 2>&1 </dev/null & echo $!')
 (out/'state.json').write_text(json.dumps({'serial':adb('get-serialno'),'pid':pid,'validHours':24},indent=2))
 print('Phone entry pre-armed for 24 hours. No recording yet. Open AM 横屏助手 → 开始车内测试 tomorrow. Restart requires USB preparation again.')
except Exception as e:raise SystemExit(str(e))
