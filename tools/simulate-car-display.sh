#!/bin/zsh
set -e
# Default phone display only; car displays are never modified.
case "${1:-skywindow}" in
 skywindow) adb shell wm size 1696x3024 ;;
 niolink) echo "Disabled: global large-canvas simulation triggered SkyUI launcher taskbar crashes. Use the real NIO Link display."; exit 1 ;;
 restore) adb shell wm size reset ;;
 *) echo 'Usage: simulate-car-display.sh skywindow|niolink|restore'; exit 2 ;;
esac
# Physical density is 600; leave it unchanged.
