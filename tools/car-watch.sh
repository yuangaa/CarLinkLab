#!/usr/bin/env bash
# NIO Link 进车「实时跟随」——一边在车机上点应用，一边看关键行滚出来
#
# 为什么需要它：车机屏带 FLAG_SECURE，截图是断的；而且决定成败的那行日志
# （getVirtualDisplay mScreenType=..,mWindowType=..）只在应用被投上去那一刻打一次，
# 事后 logcat -d 很容易已经被别的日志冲掉。开着它就不会漏。
#
# 用法：
#   ./tools/car-watch.sh              # 前台实时看
#   ./tools/car-watch.sh --save      # 同时落盘到 data/car-sessions/watch-<时间戳>.log
#   ./tools/car-watch.sh --all       # 不过滤，全量（排查疑难时用）
set -u

DEV="${NIO_DEV:-<DEVICE_SERIAL>}"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$PROJ/data/car-sessions/watch-$STAMP.log"
SAVE=0
ALL=0
for a in "$@"; do
  case "$a" in
    --save) SAVE=1 ;;
    --all)  ALL=1 ;;
  esac
done

# ── 关键字：全部从 SkyLink 反编译产物里考据出来 ────────────────────────────
# ① 窗口/屏幕类型  ② 白名单准入  ③ 方向与驻车闸门  ④ 渲染尺寸
PAT='mWindowType|mScreenType|screenType=|screen_type|judgeCreateVirtualDisplay|getVirtualDisplay
startCast|supportCast|not in the support list|app disabled in settings|only cast on pano|whitelist|cast func enable state check failed
can Landscape|adjustOrientation|onDisplaysRotationChanged|isLandscapeDisabledWhenParkingOff|parkingOffForbidLandscape|mLastRotation|redirectOrientation|sendSkyWindowRotationChangeMsg
onVideoInit width|createFullWindow width|createMirrorWindow width|createVirtualDisplay width|VirtualDisplayChangeListener|onWindowStateChange|queryAllVirtualDisplayGetDisplayID|startSmallDisplay|startMirror|movePackageToDisplay|notifyCastScreenStatus|startActivityToLauncher|requestedHeight
BaseVirtualWindowManager|ScreenCastController|WifiDisplay
DisplayManager: Display|ActivityTaskManager: START|topResumedActivity'
PAT="$(printf '%s' "$PAT" | tr '\n' '|')"

if [ "$ALL" = "1" ]; then PAT="."; fi

echo "────────────────────────────────────────────────────────────"
echo " 实时跟随中…（车机上点开一个应用，这里就会滚出关键行）"
echo " 设备: $DEV"
[ "$SAVE" = "1" ] && echo " 落盘: $OUT"
echo " 退出: Ctrl-C"
echo "────────────────────────────────────────────────────────────"
echo " 看这 4 行就够："
echo "   getVirtualDisplay mScreenType=..,mWindowType=..   ← 6=原生级 / 2=镜像"
echo "   judgeCreateVirtualDisplay mPackageName=..         ← 这个包被判成什么"
echo "   ...not in the support list                        ← 白名单拒绝（若有）"
echo "   onDisplaysRotationChanged -- rotation=..          ← 方向被改成了几"
echo "────────────────────────────────────────────────────────────"

# macOS 的 grep 是 BSD 版，没有 --line-buffered；用 awk + fflush 保证实时输出
if [ "$SAVE" = "1" ]; then
  adb -s "$DEV" logcat -v time 2>/dev/null \
    | awk -v pat="$PAT" '$0 ~ pat { print; fflush() }' \
    | tee -a "$OUT"
else
  adb -s "$DEV" logcat -v time 2>/dev/null \
    | awk -v pat="$PAT" '$0 ~ pat { print; fflush() }'
fi
