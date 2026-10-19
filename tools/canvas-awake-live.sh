#!/system/bin/sh
# Hot repair for an already-running capture; the regular supervisor owns future captures.
FILES=/sdcard/Android/data/com.oumi.utility.media.hub/files
CAPTURE="$1"
START=$(date +%s)
finish() { [ -n "$AWAKE" ] && kill "$AWAKE" 2>/dev/null; }
trap 'finish; exit' TERM INT HUP
while [ ! -f "$CAPTURE/done" ] && [ $(($(date +%s)-START)) -lt 3600 ]; do
 SESSION=$(cat "$FILES/bridge-ready" 2>/dev/null)
 if [ -z "$SESSION" ]; then finish; AWAKE=""; ACTIVE=""; sleep 1; continue; fi
 if [ "$SESSION" != "$ACTIVE" ]; then
  finish; AWAKE=""; sleep 2
  ID=$(sed -n 's/.*New display:.*(id=\([0-9]*\)).*/\1/p' /sdcard/Download/am-embedded-server.log | tail -1)
  if [ -n "$ID" ] && [ "$(cat "$FILES/bridge-ready" 2>/dev/null)" = "$SESSION" ]; then
   CLASSPATH=/data/local/tmp/am-canvas-awake.dex app_process / HoldCanvasAwake "$ID" 3600 &
   AWAKE=$!; ACTIVE="$SESSION"
  fi
 elif [ -n "$AWAKE" ] && ! kill -0 "$AWAKE" 2>/dev/null; then
  ACTIVE=""
 fi
 sleep 1
done
finish
