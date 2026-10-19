#!/bin/zsh
set -e
# Restore the phone default display only. Original physical size 1440x3200, density 600.
adb shell wm size reset
