#!/usr/bin/env bash
# NIO Link 无线调试开启/接管 —— 让你人在车里，电脑（我）远程读设备
#
# 两种组网方式，任选其一：
#   A. 手机开热点，电脑连它        → ./tools/car-wireless.sh hotspot
#   B. 车机/家里有 WiFi，两边都连   → ./tools/car-wireless.sh join <SSID> [密码]
#
# 通用：
#   ./tools/car-wireless.sh info          看当前所有网卡 IP 与热点状态
#   ./tools/car-wireless.sh tcpip         把 adbd 切到 5555 端口（USB 仍可用）
#   ./tools/car-wireless.sh usb           切回纯 USB（无线连不上时救急）
#   ./tools/car-wireless.sh connect <IP>  从电脑侧连接
set -u

DEV="${NIO_DEV:-<DEVICE_SERIAL>}"
AP_SSID="${AP_SSID:-NioLink-ADB}"
AP_PASS="${AP_PASS:-}"
PORT=5555
# 安卓热点默认网关
AP_GW="192.168.43.1"

cmd="${1:-info}"

hotspot_ip() {
  # 热点起来后，本机在 ap0/softap0 上的地址通常就是网关
  adb -s "$DEV" shell "ip -4 addr show 2>/dev/null | grep -E 'inet .*(ap0|softap0|wlan1)' | head -2" 2>/dev/null
}

case "$cmd" in
  info)
    echo "=== 各网卡 IPv4 ==="
    adb -s "$DEV" shell "ip -4 addr show 2>/dev/null | grep -E '^[0-9]+: |inet '" 2>/dev/null
    echo
    echo "=== WiFi 状态 ==="
    adb -s "$DEV" shell "dumpsys wifi 2>/dev/null | grep -m1 'mWifiInfo'" 2>/dev/null | cut -c1-200
    echo
    echo "=== adbd 是否已监听 $PORT ==="
    adb -s "$DEV" shell "ss -tln 2>/dev/null | grep $PORT" 2>/dev/null || echo "  （未监听）"
    echo
    echo "=== 热点（softap）==="
    adb -s "$DEV" shell "dumpsys wifi 2>/dev/null | grep -i -m3 -E 'soft ?ap|SoftAp'" 2>/dev/null | cut -c1-160
    ;;

  hotspot)
    [ -n "$AP_PASS" ] || { echo "请通过 AP_PASS 设置自己的热点密码。" >&2; exit 1; }
    echo "→ 让手机开热点：SSID=$AP_SSID"
    adb -s "$DEV" shell "cmd wifi start-softap $AP_SSID wpa2 $AP_PASS" 2>&1 | head -3
    sleep 4
    echo
    echo "→ 手机侧地址："
    hotspot_ip
    echo
    echo "★ 现在请在电脑上：连接 WiFi「$AP_SSID」，密码 $AP_PASS"
    echo "  连上后再跑： ./tools/car-wireless.sh tcpip"
    echo "            ./tools/car-wireless.sh connect $AP_GW"
    ;;

  stop-hotspot)
    adb -s "$DEV" shell "cmd wifi stop-softap" 2>&1 | head -2
    ;;

  join)
    SSID="${2:?用法: car-wireless.sh join <SSID> [密码]}"
    PASS="${3:-}"
    if [ -n "$PASS" ]; then
      adb -s "$DEV" shell "cmd wifi connect-network '$SSID' wpa2 '$PASS'" 2>&1 | head -3
    else
      adb -s "$DEV" shell "cmd wifi connect-network '$SSID' open" 2>&1 | head -3
    fi
    sleep 6
    echo "→ 手机侧地址（拿这个 IP 去 connect）："
    adb -s "$DEV" shell "ip -4 addr show wlan0 2>/dev/null | grep inet" 2>/dev/null
    ;;

  tcpip)
    adb -s "$DEV" tcpip $PORT 2>&1 | head -3
    sleep 2
    echo
    echo "→ 手机上各地址（挑电脑能 ping 通的那个）："
    adb -s "$DEV" shell "ip -4 addr show 2>/dev/null | grep inet | grep -v 127.0.0.1" 2>/dev/null
    echo
    echo "接着跑： ./tools/car-wireless.sh connect <IP>"
    ;;

  connect)
    IP="${2:-$AP_GW}"
    adb connect "$IP:$PORT" 2>&1 | head -3
    sleep 1
    adb devices -l | tail -4
    echo
    echo "若成功，把 NIO_DEV 换成这个 IP 即可："
    echo "  export NIO_DEV=$IP:$PORT"
    echo "  然后 car-session.py / car-watch.sh 都会自动用它"
    ;;

  usb)
    adb -s "$DEV" usb 2>&1 | head -2
    echo "已切回 USB 模式（无线断开）"
    ;;

  *)
    sed -n '2,20p' "$0"
    ;;
esac
