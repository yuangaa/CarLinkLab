#!/usr/bin/env bash
# N2301 到底能不能 root —— 只读探针。
#
# 这个脚本**不刷机、不解锁、不清数据**。它只把决策需要的两个闸门问清楚：
#   闸门 A：开发者选项里的「OEM 解锁」能不能打开（只能靠眼睛看，脚本给出当前值供对照）
#   闸门 B：bootloader 允不允许解锁（fastboot 只读查询 get_unlock_ability）
#   闸门 C：有没有与当前构建指纹匹配的 boot.img（Magisk 修补需要它）
#
# 用法（在仓库根目录执行）：
#   ./tools/root-feasibility.sh              # 只跑 adb 能查的，几秒，零风险
#   ./tools/root-feasibility.sh --fastboot   # 再进 fastboot 查闸门 B（会重启手机，仍不清数据）
#
# 严禁：不要随手跑 `fastboot flashing unlock`。那条命令一执行就清空 /data，是不可逆的。
#       本脚本不会替你跑它。
#
# 为什么先探再刷：这台机器的 ROM 把 oem_unlock 相关属性用 SELinux 挡在 shell 外面
#（日志实证：avc denied { read } name="u:object_r:oem_unlock_prop:s0"，见
#  data/car-sessions/live/full.log:708059）。厂商主动收紧到这一步，说明「解锁」不是
#  AOSP 默认敞开的状态 —— 所以两个闸门必须先探，不能直接假定能刷。
set -u

DEV="${NIO_DEV:-<DEVICE_SERIAL>}"
ADB="adb -s ${DEV}"
FB="fastboot -s ${DEV}"
GO_FB=0
[ "${1:-}" = "--fastboot" ] && GO_FB=1
[ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] && { sed -n '2,26p' "$0"; exit 0; }

sh()  { ${ADB} shell "$@" 2>/dev/null | tr -d '\r'; }
say() { printf '\n=== %s ===\n' "$*"; }
val() { printf '  %-34s %s\n' "$1" "$2"; }
vv()  { local v="$1"; if [ -n "$v" ] && [ "$v" != "null" ]; then echo "$v"; else echo '（空 / 被挡）'; fi; }

if ! ${ADB} get-state >/dev/null 2>&1; then
  echo "找不到设备 ${DEV}（NIO_DEV=<序列号> 覆盖）。先在 Mac 上 adb devices 确认能看到它。"
  exit 1
fi

# ---------- 0. 指纹（找 boot.img 时要拿它去比对） ----------
say "构建指纹（匹配 boot.img 用，一字不能差）"
FP="$(sh getprop ro.build.fingerprint)"
ID="$(sh getprop ro.build.display.id)"
val "ro.build.fingerprint" "${FP:-读不到}"
val "ro.build.display.id" "${ID:-读不到}"
val "ro.product.device" "$(sh getprop ro.product.device)"
val "ro.product.vendor.device" "$(sh getprop ro.product.vendor.device)"
val "ro.build.version.release" "$(sh getprop ro.build.version.release)"
val "内核" "$(sh uname -a | cut -c1-60)"

# ---------- 1. 现在这台机器是什么货色 ----------
say "构建类型与既有权限（判断有没有现成的门）"
for p in ro.build.type ro.secure ro.debuggable ro.adb.secure ro.product.build.type; do
  val "$p" "$(sh getprop $p)"
done
val "adb root 是否可用" "$(sh id | grep -q 'uid=0' && echo '可用（已是 root）' || echo '否（普通 shell）')"
val "su 是否存在" "$(sh 'ls /system/bin/su /system/xbin/su 2>/dev/null' | head -1 || true)"
echo
echo "  已装的 root 管理器（有就说明已经 root 过）："
sh "pm list packages | grep -iE 'magisk|topjohnwu|kernelsu|apatch|superuser'" | sed 's/^/    /' || true
echo "    （以上为空 = 未 root）"

# ---------- 2. 闸门 A：OEM 解锁 ----------
say "闸门 A：OEM 解锁开关"
val "settings global oem_unlock_allowed" "$(vv "$(sh settings get global oem_unlock_allowed)")"
val "ro.oem_unlock_supported" "$(vv "$(sh getprop ro.oem_unlock_supported)")"
val "ro.boot.flash.locked" "$(vv "$(sh getprop ro.boot.flash.locked)")"
val "ro.boot.verifiedbootstate" "$(vv "$(sh getprop ro.boot.verifiedbootstate)")"
val "ro.boot.vbmeta.device_state" "$(vv "$(sh getprop ro.boot.vbmeta.device_state)")"
cat <<'EOT'

  ⚠️ 上面几行如果全是「（空）」，不是机器没这属性，而是被 SELinux 挡住了 ——
     日志里能看到 avc denied { read } name="u:object_r:oem_unlock_prop:s0"。
     adb 读不到，所以闸门 A 只能你在手机上用眼睛判：

     设置 → 关于手机 → 连点「版本号」7 次开开发者选项
       → 系统与更新 → 开发者选项 → 找「OEM 解锁 / OEM unlocking」
         · 开关可拨动、能打开          → 闸门 A 过，继续看闸门 B
         · 开关是灰的、按不动          → 闸门 A 不过 → root 路到此为止
           （灰掉 = ROM 层不支持解锁，不是权限问题，adb 也绕不过去）

     注意：`settings put global oem_unlock_allowed 1` 之类是没用的 ——
     这个开关写在 persistent data block 里，必须人在 UI 上确认，adb 代劳不了。
EOT

# ---------- 3. 闸门 B：bootloader 是否允许解锁 ----------
if [ "$GO_FB" = 1 ]; then
  say "闸门 B：bootloader 解锁能力（只读查询）"
  echo "  即将重启到 bootloader。这一步只读，不清数据；清数据的是 flashing unlock，本脚本不会跑。"
  ${ADB} reboot bootloader >/dev/null 2>&1
  echo -n "  等待 fastboot 设备"
  for i in $(seq 1 30); do
    if ${FB} devices 2>/dev/null | grep -q .; then echo " —— 就绪"; break; fi
    echo -n "."; sleep 1
  done
  echo
  echo "  --- fastboot getvar 关键项 ---"
  for v in unlocked secure flash.locked serialno product version-bootloader; do
    printf '  %-24s %s\n' "$v" "$(${FB} getvar $v 2>&1 | grep -m1 -v '^$' | sed 's/^[^:]*: *//')"
  done
  echo
  echo "  --- flashing get_unlock_ability（0/1，这是决定性的一条）---"
  ${FB} flashing get_unlock_ability 2>&1 | sed 's/^/    /'
  echo
  cat <<'EOT'
    怎么读这条：
      get_unlock_ability: 1  → bootloader 允许解锁 → 闸门 B 过
      get_unlock_ability: 0  → 不允许（多半是闸门 A 的开关没开，回去开；开了还是 0 就是厂商禁了）
      "unknown command"      → 这个 bootloader 不支持该查询，改用 fastboot oem device-info 看
EOT
  echo
  read -r -p "  按回车重启回系统（不回 fastboot 的话手机自己也会超时重启）..." _ || true
  ${FB} reboot >/dev/null 2>&1 || true
  echo "  已发出重启指令。"
else
  say "闸门 B：未探测"
  echo "  加 --fastboot 参数可进 bootloader 做只读查询（会重启手机，不清数据）。"
fi

# ---------- 4. 闸门 C：boot.img ----------
say "闸门 C：匹配构建的 boot.img（闸门 A、B 都过了才需要）"
echo "  当前构建：${ID:-未知}"
found=0
for f in $(find . -maxdepth 4 -iname 'boot*.img' 2>/dev/null); do
  printf '  找到 %s\n' "$f"; found=1
done
[ "$found" = 0 ] && cat <<'EOT'
  仓库里没有 boot.img（预期）。它不会自己出现，来源只有两个：
    1) 官方固件包 —— NIO 是否对外发布 N2301 的完整固件包，目前查不到（NeedROM 上只有
       「NIO Phone 2」，第二代 SD 8 Gen 3，与这台 N2301 不是一回事，不能混用）；
    2) 系统 OTA 更新包 —— 抓完整 OTA 的下载地址，从 payload.bin 里抽 boot.img
       （payload-dumper-go 这类工具可做，需要匹配当前构建号）。
  两条路都断了的话：即使 BL 解锁成功，也补不出 boot.img，Magisk 无从下手。
EOT

# ---------- 结论汇总 ----------
cat <<EOF

────────────────────────────────────────────────────────────────────
结论怎么下

  闸门 A（OEM 解锁开关可开）      ： 你眼睛判断 —— 见上面
  闸门 B（bootloader 允许解锁）   ： $( [ "$GO_FB" = 1 ] && echo '见上面 get_unlock_ability' || echo '未测，加 --fastboot' )
  闸门 C（拿得到匹配的 boot.img） ： 目前未找到来源

  三个都过 → 按标准 Magisk 流程走，再到「白名单注入」那一步。
  任一不过 → root 路作废，退回零 root 的两条：
             · 改密度让 AM 本体进平板布局（见 tools 里的密度实验）
             · 套壳继续用（车测已通过）

记住顺序：**先备份**（./tools/backup-apps.sh），再动 BL。BL 一解锁就清数据，没有第二次机会。
EOF
