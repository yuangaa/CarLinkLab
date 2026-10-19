#!/usr/bin/env bash
# 解 BL / root（本机必然抹掉 /data）之前，把手机上的应用与关键设置整包存到电脑。
#
# 为什么必须先做：
#   N2301 解 BL 一定清 /data —— 第三方 App、App 数据、通知监听授权、wm 尺寸/方向覆盖、
#   蓝牙与 WiFi 配对全部消失。/system 里的系统应用与 SkyUI/NIO Link 本体不受影响
#   （刷机后仍在），云端的投屏白名单也会自己重新下发。所以真正会丢的是"我们自己装的"。
#
# 用法（在仓库根目录执行）：
#   ./tools/backup-apps.sh                 # 存到 backup/<时间戳>/
#   ./tools/backup-apps.sh --tag preroot   # 目录名加后缀
#   ./tools/backup-apps.sh --no-apk        # 只存清单与设置，不拉 APK（快，几十秒）
#
# 产出（backup/<时间戳>/）：
#   apps.tsv            每个第三方包的 包名 / versionCode / versionName / APK 份数 / codePath
#   pkgs-third.txt      pm list packages -3                       （现装的第三方）
#   pkgs-third-u.txt    pm list packages -3 -u                    （含"卸载但留数据"的）
#   pkgs-disabled.txt   pm list packages -d                       （被禁用的，含 AA 那条路）
#   pkgs-system.txt     pm list packages -s                       （仅留档，解 BL 不影响）
#   apk/<包名>/*.apk    base + 全部 split（恢复时 adb install-multiple 必须给全集）
#   settings/           getprop / dumpsys package 全文 / settings 三张表 / wm / display /
#                       通知监听 / 蓝牙 / WiFi / APK 的 sha256
#   README.txt          这份备份是什么、下一步怎么做
#
# 明确不做：App 内部数据（无 root 读不到）。Apple Music 的离线歌曲与登录态只能重下重登。
#           详见 docs/root前备份与恢复清单.md。
#
# 恢复：./tools/restore-apps.sh [backup/<时间戳>]
set -u

DEV="${NIO_DEV:-<DEVICE_SERIAL>}"
ADB="adb -s ${DEV}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="backup/${STAMP}"
DO_APK=1

while [ $# -gt 0 ]; do
  case "$1" in
    --no-apk) DO_APK=0 ;;
    --tag)    shift; OUT="backup/${STAMP}-${1:-tag}" ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "未知参数：$1（--help 看用法）"; exit 1 ;;
  esac
  shift
done

sh()  { ${ADB} shell "$@" 2>/dev/null | tr -d '\r'; }
say() { printf '\n=== %s ===\n' "$*"; }

# ---------- 0. 确认设备在线 ----------
if ! ${ADB} get-state >/dev/null 2>&1; then
  echo "找不到设备 ${DEV}。"
  echo "  1) 手机用 USB 连上、开发者选项里开了 USB 调试；"
  echo "  2) 电脑上先跑 adb devices 看到它；"
  echo "  3) 要换序列号：NIO_DEV=<序列号> $0"
  exit 1
fi

mkdir -p "${OUT}/settings" "${OUT}/apk"
echo "备份目录：${OUT}"

# ---------- 1. 环境与指纹 ----------
say "环境与构建指纹"
{
  echo "### 备份时间：$(date '+%F %T %z')"
  echo "### getprop 全量"
  sh getprop
} > "${OUT}/settings/getprop.txt"
sh getprop ro.build.fingerprint   > "${OUT}/settings/build-fingerprint.txt"
sh getprop ro.build.display.id    >> "${OUT}/settings/build-fingerprint.txt"
sh getprop ro.product.model       >> "${OUT}/settings/build-fingerprint.txt"
sh getprop ro.build.version.release >> "${OUT}/settings/build-fingerprint.txt"
sed -n '1,4p' "${OUT}/settings/build-fingerprint.txt" | sed 's/^/  /'

# ---------- 2. 包清单 ----------
say "包清单"
sh pm list packages -3     > "${OUT}/pkgs-third.txt"
sh pm list packages -3 -u  > "${OUT}/pkgs-third-u.txt"
sh pm list packages -d     > "${OUT}/pkgs-disabled.txt"
sh pm list packages -s     > "${OUT}/pkgs-system.txt"
sh pm list users           > "${OUT}/settings/users.txt"
printf '  第三方 %s 个，系统 %s 个\n' \
  "$(grep -c . "${OUT}/pkgs-third.txt")" "$(grep -c . "${OUT}/pkgs-system.txt")"

# ---------- 3. dumpsys package 全文（一次抓，后面本地解析） ----------
say "dumpsys package 全文（约十几 MB，稍等）"
sh dumpsys package > "${OUT}/settings/dumpsys-package.txt"
printf '  %s 行\n' "$(wc -l < "${OUT}/settings/dumpsys-package.txt")"
DUMPSYS="${OUT}/settings/dumpsys-package.txt"

# ---------- 4. 关键设置现场 ----------
say "设置现场"
sh settings list secure > "${OUT}/settings/settings-secure.txt"
sh settings list global > "${OUT}/settings/settings-global.txt"
sh settings list system  > "${OUT}/settings/settings-system.txt"

{
  echo "### wm size / density（display 0 与两个 NIO 虚拟屏）"
  for d in "" "-d 90000001" "-d 90000005"; do
    echo "--- wm size ${d}";     sh wm size ${d}
    echo "--- wm density ${d}";  sh wm density ${d}
  done
  echo "### wm user-rotation（含 NIO 冻结值）"
  for d in "" "-d 90000001" "-d 90000005"; do
    echo "--- ${d:-display 0}"; sh wm user-rotation ${d}
  done
  echo "### ignore-orientation-request"
  for d in "" "-d 90000001" "-d 90000005"; do
    echo "--- ${d:-display 0}"; sh wm get-ignore-orientation-request ${d}
  done
} > "${OUT}/settings/wm.txt"
cat "${OUT}/settings/wm.txt" | sed 's/^/  /' | head -30

sh dumpsys display > "${OUT}/settings/dumpsys-display.txt"
sh dumpsys window  > "${OUT}/settings/dumpsys-window.txt"

# 通知监听（套壳的 MediaSession 权限来源）+ 无障碍
{
  echo "### cmd notification list_listeners"
  sh cmd notification list_listeners
  echo
  echo "### settings secure enabled_notification_listeners"
  sh settings get secure enabled_notification_listeners
  echo
  echo "### settings secure enabled_accessibility_services"
  sh settings get secure enabled_accessibility_services
  echo
  echo "### dumpsys notification | grep -i listener"
  sh dumpsys notification | grep -i listener
} > "${OUT}/settings/notif-listeners.txt"
grep -i 'enabled_notification_listeners' "${OUT}/settings/settings-secure.txt" | sed 's/^/  /'

# 配对信息（刷完要重连）
{
  echo "### 蓝牙已配对"
  sh dumpsys bluetooth_manager | grep -iE 'bonded|Bond state' | head -40
  echo
  echo "### WiFi"
  sh dumpsys wifi | grep -iE 'mWifiInfo|SSID|ConfigKey' | head -40
} > "${OUT}/settings/pairings.txt"

# ---------- 5. 逐个第三方包：pm path + 拉 APK ----------
# versionCode/versionName 从已存下的 dumpsys 全文里本地解析
# 注意：dumpsys 的包块行是带缩进的（"  Package [com.x] (abc):"），不能用 index(...)==1 判断
meta() {
  awk -v want="$1" '
    match($0, /Package \[[^]]+\]/) {
      inb = (substr($0, RSTART, RLENGTH) == "Package [" want "]")
      next
    }
    inb && match($0, /versionCode=[0-9]+/) { vc = substr($0, RSTART+12, RLENGTH-12) }
    inb && match($0, /versionName=[^ ]+/)  { vn = substr($0, RSTART+12, RLENGTH-12) }
    END { print (vc==""?"-":vc) "\t" (vn==""?"-":vn) }
  ' "$DUMPSYS"
}

: > "${OUT}/apps.tsv"
printf 'package\tversionCode\tversionName\tnapk\tcodePath\n' >> "${OUT}/apps.tsv"

say "逐个第三方包：pm path"
PKGS="$(sed 's/^package://' "${OUT}/pkgs-third.txt" | sort -u)"
TOTAL=$(printf '%s\n' "$PKGS" | grep -c .)

i=0
for p in $PKGS; do
  i=$((i+1))
  paths="$(sh pm path "$p" | sed 's/^package://')"
  n=$(printf '%s\n' "$paths" | grep -c .)
  cp1="$(printf '%s\n' "$paths" | head -1 | sed 's#/[^/]*$##')"
  m="$(meta "$p")"
  printf '%s\t%s\t%s\t%s\t%s\n' "$p" "${m%%$'\t'*}" "${m##*$'\t'}" "$n" "$cp1" >> "${OUT}/apps.tsv"

  if [ "$DO_APK" = 1 ]; then
    mkdir -p "${OUT}/apk/${p}"
    printf '%s\n' "$paths" | while read -r f; do
      [ -n "$f" ] || continue
      ${ADB} pull "$f" "${OUT}/apk/${p}/" >/dev/null 2>&1 \
        || echo "  !! 拉取失败：$f"
    done
    printf '  [%2d/%2d] %-45s v%-8s %s 份\n' "$i" "$TOTAL" "$p" "${m%%$'\t'*}" "$n"
  else
    printf '  [%2d/%2d] %-45s v%-8s %s 份（未拉）\n' "$i" "$TOTAL" "$p" "${m%%$'\t'*}" "$n"
  fi
done

# ---------- 6. APK 校验和 ----------
if [ "$DO_APK" = 1 ]; then
  say "APK sha256"
  ( cd "${OUT}/apk" && find . -name '*.apk' -print0 | xargs -0 sha256sum ) \
    > "${OUT}/settings/sha256-apk.txt"
  printf '  %s 份，总 %s\n' \
    "$(wc -l < "${OUT}/settings/sha256-apk.txt")" \
    "$(du -sh "${OUT}/apk" | cut -f1)"
fi

# ---------- 7. 备份说明 ----------
cat > "${OUT}/README.txt" <<EOF
CarLinkLab · 解 BL / root 前的应用备份
备份时间：$(date '+%F %T %z')
设备序列号：${DEV}
构建指纹：$(head -1 "${OUT}/settings/build-fingerprint.txt")

这是什么
  这台 NIO Phone N2301 解 BL 必然抹掉 /data。本目录把"会被抹掉、又能在电脑上重建的东西"
  整包留档：第三方 App 的 APK 全集（base + split）、版本号、以及一批关键设置现场。

怎么装回去
  在仓库根目录执行：./tools/restore-apps.sh ${OUT}
  装完还必须手工做的两件事（脚本会打印命令）：
    1) 给套壳 App 授权通知监听（它的 MediaSession 权限来源）；
    2) 重新配对车机 / 登录 NIO 账号。

装不回去的（只能重来）
  · Apple Music 的登录态与离线歌曲 → 重新登录、重新下载；
  · 各 App 的本地数据（无 root 读不到 /data/data）；
  · 蓝牙、WiFi 配对 → 重新配。
  详见 docs/root前备份与恢复清单.md。

别误会
  · /system 里的系统应用（SkyUI、NIO Link、NetConfig…）刷机后还在，本备份里的 pkgs-system.txt
    只是留档，用来事后对比；
  · 云端投屏白名单会自己重新下发，不需要从这份备份里恢复。
EOF

say "完成"
echo "  ${OUT}/apps.tsv        ← 先看这个"
echo "  ${OUT}/README.txt"
echo
echo "下一步：把人拉齐后跑 ./tools/restore-apps.sh ${OUT}"
