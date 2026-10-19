#!/usr/bin/env bash
# 已作废：2026-10-07 实测显示器目标错误、shell 启动被拦，私有命令不可达。
echo "此实验已作废，已阻止执行。请阅读 docs/PUBLICATION-NOTES.md。" >&2
exit 1

# 方案 D · 第 1 步：在「天空视窗」车机显示器（90000005）上把任意应用弄成横屏 16:9
# 依次对照 4 种手段，看哪一种能让应用在车机屏上横屏：
#   A 基线
#   B wm set-ignore-orientation-request -d 90000005 1     （AOSP 标准，让显示器忽略应用请求的方向）
#   C am compat enable 265464455 <包名>                    （OVERRIDE_ANY_ORIENTATION，按包）
#   D dumpsys window allPackagesFullscreen 1              （NIO 扩展命令，可能仅 root 可用）
#
# 前提：人在车里、车机上已打开「天空视窗」（虚拟显示器 90000005 存在）
# 用法：  ./tools/car-orientation-test.sh [包名]      默认 com.apple.android.music
#        ./tools/car-orientation-test.sh --restore   只恢复现场
set -u

PKG="${1:-com.apple.android.music}"
D=90000005
CAR_MARK="com.nio.link.connly.five"
CHANGE_ID=265464455

say() { printf '\n=== %s ===\n' "$*"; }

car_present() { adb shell dumpsys display 2>/dev/null | grep -q "$CAR_MARK"; }

car_info() {
  adb shell dumpsys display 2>/dev/null | tr '\n' ' ' \
    | grep -o "uniqueId=\"virtual:[^\"]*${CAR_MARK}[^\"]*\"[^}]*" | head -1 \
    | grep -oE "[0-9]+ x [0-9]+"
}

ignore_rot() { adb shell wm get-ignore-orientation-request -d "$D" 2>/dev/null | grep -oE "true|false" | head -1; }

app_frame() {
  adb shell dumpsys window windows 2>/dev/null \
    | grep -A16 "Window{.* $PKG/" | grep -m2 -E "mFrame=|frame=" | sed 's/^ *//'
}

wtype() { adb shell logcat -d 2>/dev/null | grep -E "mWindowType" | tail -2 | sed 's/^.*BaseVirtualWindowManager/  BVM/'; }

snapshot() {
  printf '  车机显示器: %s   ignoreOrientationRequest=%s\n' "$(car_info)" "$(ignore_rot)"
  printf '  应用窗口: %s\n' "$(app_frame | tr '\n' ' ')"
  wtype
}

run_case() {
  local name="$1"; shift
  say "$name"
  adb shell am force-stop "$PKG" >/dev/null 2>&1
  "$@" >/dev/null 2>&1
  adb shell wm user-rotation -d "$D" lock 1 >/dev/null 2>&1
  adb logcat -c 2>/dev/null
  adb shell am start --display "$D" -n "$ACT" >/dev/null 2>&1
  sleep 6
  snapshot
  # 收掉这一组的作用
  adb shell wm set-ignore-orientation-request -d "$D" 0 >/dev/null 2>&1
  adb shell am compat disable "$CHANGE_ID" "$PKG" >/dev/null 2>&1
  adb shell dumpsys window allPackagesFullscreen 0 >/dev/null 2>&1
  adb shell settings put global skyui_custom_rotation "$CUSTOM_ROT_ORIG" >/dev/null 2>&1
}

restore() {
  say "恢复现场"
  adb shell wm user-rotation -d "$D" lock 0 >/dev/null 2>&1
  adb shell wm set-ignore-orientation-request -d "$D" 0 >/dev/null 2>&1
  adb shell am compat enable "$CHANGE_ID" "$PKG" >/dev/null 2>&1   # 保持原有的按包覆盖
  adb shell settings put global skyui_custom_rotation "$CUSTOM_ROT_ORIG" >/dev/null 2>&1
  echo "  user-rotation=竖屏, ignoreOrientationRequest=0, skyui_custom_rotation=$CUSTOM_ROT_ORIG, compat $CHANGE_ID 对 $PKG 保持 enable"
}

if [ "${PKG}" = "--restore" ]; then restore; exit 0; fi

if ! car_present; then
  echo "❌ 没看到车机显示器（${CAR_MARK}）。请先在车机上打开「天空视窗」再运行本脚本。" >&2
  exit 1
fi

ACT=$(adb shell cmd package resolve-activity --brief "$PKG" 2>/dev/null | tail -1 | tr -d '\r')
CUSTOM_ROT_ORIG=$(adb shell settings get global skyui_custom_rotation 2>/dev/null | tr -d '\r')
echo "目标应用: $PKG   入口: $ACT   车机显示器: $D"
echo "基线 ignoreOrientationRequest=$(ignore_rot)   skyui_custom_rotation=$CUSTOM_ROT_ORIG"

run_case "A 基线（只锁横屏，不忽略应用请求）" true
run_case "B wm set-ignore-orientation-request -d $D 1" adb shell wm set-ignore-orientation-request -d "$D" 1
run_case "C am compat enable $CHANGE_ID $PKG" adb shell am compat enable "$CHANGE_ID" "$PKG"
run_case "D dumpsys window allPackagesFullscreen 1（NIO 扩展，可能仅 root）" adb shell dumpsys window allPackagesFullscreen 1
run_case "E skyui_custom_rotation=0" adb shell settings put global skyui_custom_rotation 0
run_case "F skyui_custom_rotation=1" adb shell settings put global skyui_custom_rotation 1

say "判定（看'车机显示器'那一行）"
cat <<'EOF'
  3200x1440 级别（16:9 宽）→ 该手段有效，任意应用可在车机屏横屏
  1440x3200 级别（9:16 竖）→ 无效
  注意 D 若只在 logcat 出现 "ScreenCastController dumpCommand" 而无实际效果，
  很可能被 enforceCallerIsRoot() 拦了（shell 不是 root）
EOF

restore
