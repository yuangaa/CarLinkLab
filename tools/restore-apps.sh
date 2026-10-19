#!/usr/bin/env bash
# 解 BL + 刷机 + root 之后，把 tools/backup-apps.sh 存下的应用装回去。
#
# 用法（在仓库根目录执行）：
#   ./tools/restore-apps.sh                    # 自动用 backup/ 里最新的一份
#   ./tools/restore-apps.sh backup/20261007-181500
#   ./tools/restore-apps.sh --list             # 只列会装什么，不装
#   ./tools/restore-apps.sh --dry-run          # 打印 adb 命令，不执行
#   ./tools/restore-apps.sh --only com.apple.android.music
#   ./tools/restore-apps.sh --tag preroot
#
# 装法：目录里只有 1 份 APK → adb install -r；
#       base + split 多份   → adb install-multiple -r（少一份就会 INSTALL_FAILED_MISSING_SPLIT）
# 顺序：Apple Music → 套壳 → NioPlay → 其余（按包名字母序），因为套壳要能查到 AM。
#
# 默认跳过的（加 --all 才装）：
#   com.google.android.apps.auto* / com.google.android.projection.gearhead*
#     —— Android Auto 在这台机器上跑不起来（AA 内部两道墙，见
#        docs/NIO-Link-AppleMusic-最终结论与路径.md），装了只是占地方。
#
# 装完必须手工做的（本脚本只打印命令，不自动执行）：
#   1) 通知监听授权 —— 套壳靠它拿 MediaSessionManager.getActiveSessions() 的权限；
#   2) NIO 账号重新登录 → NIO Link 与车机重新配对；
#   3) Apple Music 重新登录 + 重新下载离线歌曲（数据不在备份里）。
set -u

DEV="${NIO_DEV:-<DEVICE_SERIAL>}"
ADB="adb -s ${DEV}"

BK=""; DO=1; ONLY=""; TAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --list)    DO=0 ;;
    --dry-run) DO=2 ;;
    --all)     ONLY="__ALL__" ;;
    --only)    shift; ONLY="${1:-}" ;;
    --tag)     shift; TAG="${1:-}" ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    -*) echo "未知参数：$1"; exit 1 ;;
    *)  BK="$1" ;;
  esac
  shift
done

# ---------- 找备份目录 ----------
if [ -n "$TAG" ] && [ -z "$BK" ]; then
  BK="$(ls -1dt backup/*"${TAG}"*/ 2>/dev/null | head -1)"
fi
if [ -z "$BK" ]; then
  BK="$(ls -1dt backup/*/ 2>/dev/null | head -1)"
fi
if [ -z "$BK" ] || [ ! -d "$BK/apk" ]; then
  echo "找不到备份目录（要含 apk/ 子目录）。"
  echo "先在仓库根目录跑 ./tools/backup-apps.sh，或用 --help 看用法。"
  exit 1
fi
BK="${BK%/}"
echo "使用备份：${BK}"

# ---------- 设备 ----------
if [ "$DO" = 1 ]; then
  if ! ${ADB} get-state >/dev/null 2>&1; then
    echo "找不到设备 ${DEV}（NIO_DEV=<序列号> 可覆盖）。"
    exit 1
  fi
fi

# ---------- 跳过规则 ----------
skip() {
  case "$1" in
    com.google.android.apps.auto*|com.google.android.projection.gearhead*)
      [ "$ONLY" = "__ALL__" ] && return 1 || return 0 ;;
  esac
  return 1
}

# ---------- 先列清单（含顺序） ----------
ordered=""
for pre in com.apple.android.music com.oumi.utility.media.hub com.shihab.diplay; do
  [ -d "${BK}/apk/${pre}" ] && ordered="${ordered}${pre}
"
done
for d in "${BK}"/apk/*/; do
  p="$(basename "$d")"
  case "
${ordered}" in *"
${p}
"*) continue ;; esac
  ordered="${ordered}${p}
"
done

printf '\n%-46s %-8s %s\n' "包名" "版本" "APK"
printf '%s\n' "--------------------------------------------------------------------------"
todo=""
while read -r p; do
  [ -n "$p" ] || continue
  n=$(find "${BK}/apk/${p}" -name '*.apk' 2>/dev/null | grep -c .)
  v="$(awk -F'\t' -v p="$p" '$1==p{print $3}' "${BK}/apps.tsv" 2>/dev/null | head -1)"
  if skip "$p"; then
    printf '%-46s %-8s %s\n' "$p" "${v:--}" "跳过（AA 家族，--all 可强制）"
    continue
  fi
  if [ -n "$ONLY" ] && [ "$ONLY" != "__ALL__" ] && [ "$ONLY" != "$p" ]; then continue; fi
  printf '%-46s %-8s %s 份\n' "$p" "${v:--}" "$n"
  todo="${todo}${p}
"
done <<EOF
${ordered}
EOF

[ "$DO" = 0 ] && { echo; echo "（--list：未安装）"; exit 0; }

# ---------- 安装 ----------
ok=0; fail=0
while read -r p; do
  [ -n "$p" ] || continue
  skip "$p" && continue
  dir="${BK}/apk/${p}"
  [ -d "$dir" ] || continue
  files="$(find "$dir" -name '*.apk' | sort | tr '\n' ' ')"
  [ -n "${files// /}" ] || continue
  n=$(printf '%s' "$files" | wc -w)
  if [ "$n" -eq 1 ]; then
    cmd="adb -s ${DEV} install -r ${files}"
  else
    cmd="adb -s ${DEV} install-multiple -r ${files}"
  fi
  echo
  echo "=== ${p}  (${n} 份) ==="
  if [ "$DO" = 2 ]; then
    echo "  ${cmd}"
    continue
  fi
  if ${cmd} 2>&1 | sed 's/^/  /'; then
    ok=$((ok+1))
  else
    fail=$((fail+1))
    echo "  !! 失败。若提示 INSTALL_FAILED_MISSING_SPLIT → 备份少了 split，回手机重拉。"
  fi
done <<EOF
${todo}
EOF

if [ "$DO" = 1 ]; then
  echo
  echo "成功 ${ok} 个，失败 ${fail} 个。"
fi

# ---------- 装完的手工项 ----------
cat <<EOF

────────────────────────────────────────────────────────────────────
还要手工做的（按顺序）：

1) 给套壳授权通知监听（它的 MediaSession 权限来源）
     adb -s ${DEV} shell cmd notification allow_listener \
        com.oumi.utility.media.hub/com.oumi.utility.media.hub.MediaListenerService
   命令不存在时的兜底：
     adb -s ${DEV} shell settings put secure enabled_notification_listeners \
        com.oumi.utility.media.hub/com.oumi.utility.media.hub.MediaListenerService
   （注意：清单里那句 <uses-permission BIND_NOTIFICATION_LISTENER_SERVICE> 没用——
     它是 signature 级权限，声明不给。真正生效的就是上面这条。）

2) 确认套壳可以装/覆盖到白名单包位
     套壳包名必须保持 com.oumi.utility.media.hub，versionCode ≥ 云白名单里的 minVer。
     仓库里现成的一版：apps/nio-link-shell/niolink-shell.apk（另外一版 sensorLandscape：
     niolink-shell-3.3-landscape.apk）。两版证书一致，可直接覆盖安装。

3) NIO 账号 + 车机
     登录 NIO 账号 → NIO Link 重新配对车机 → 车机点开对应图块验证。

4) Apple Music
     重新登录 Apple ID；离线歌曲重新下载（不在这份备份里）。

5) 现场设置（多数系统会自己重建，别当必做项）
     · 投屏白名单：云端会重新下发，不用手工恢复；
     · wm 尺寸/方向覆盖：SkyLink 每秒重设，恢复也没用；
     · 蓝牙/WiFi 配对：列表在 backup/<时间戳>/settings/pairings.txt，照着重连。

明确不要在套壳之外装的东西：
  · apk/NioLink-CrossApp-vidhub.apk —— 全量 NioPlay 伪装包，曾把 NIO Link 搞崩，
    只在 CSV 里 installed=no 的空位包名下才安全，别直接 adb install。
    （这是仓库里的文件，不在本次 backup/ 里。）
EOF
