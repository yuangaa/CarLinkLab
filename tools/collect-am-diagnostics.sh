#!/bin/zsh
set -e
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CAPTURE_DIR="$LAB_ROOT/data/am-landscape/session-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$CAPTURE_DIR"
adb pull /sdcard/Android/data/com.oumi.utility.media.hub/files/diagnostics "$CAPTURE_DIR/vidhub"
# Full system buffer supplements app-local events (including code102).
adb logcat -d -v threadtime > "$CAPTURE_DIR/system.log"
adb shell dumpsys display > "$CAPTURE_DIR/display.txt"
adb shell dumpsys activity activities > "$CAPTURE_DIR/activities.txt"
echo "Saved: $CAPTURE_DIR"
