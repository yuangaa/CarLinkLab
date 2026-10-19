#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NIO Link 进车一键采样器
============================================================
在车里（车机已打开「天空视窗」/ 已出现车机屏）跑一次，
把判定「某个应用有没有拿到车机原生级待遇」所需的全部证据一次性落盘 + 打印结论。

用法：
    ./tools/car-session.py --preflight                 # 出门前在家跑，检查弹药是否齐
    ./tools/car-session.py                             # 采样一次（自动识别车机屏）
    ./tools/car-session.py --tag youtube               # 给本次采样起名，便于对照
    ./tools/car-session.py --pkg com.tencent.qqlive     # 指定关注的应用
    ./tools/car-session.py --why                       # 只打印判定用的关键日志，不落盘

产物：data/car-sessions/<时间戳>[-tag]/
      summary.txt  display.txt  windows.txt  activity.txt
      logcat.txt   settings.txt skylink.txt
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.environ.get("NIO_DEV") or "<DEVICE_SERIAL>"

CAR_MARK = os.environ.get("NIO_CAR_MARK") or "com.nio.link.connly.five"  # 车机虚拟显示器 uniqueId 特征串
DEFAULT_PKG = "com.apple.android.music"

# ── 判定用的日志关键字（全部从 SkyLink 反编译产物里考据出来，不是猜的）────────────
# 这些行分别回答：拿到的是几号窗口 / 白名单放不放行 / 方向被谁改 / 驻车是否禁横屏
KEY = [
    # ① 窗口类型与屏幕类型（同一行，最核心）
    "indowType", "mScreenType", "screenType=", "screen_type",
    "judgeCreateVirtualDisplay", "getVirtualDisplay",
    "createVirtualWindowManager", "updateSmallWindowSize",
    # ② 白名单准入（拒绝时会明确打出来）
    "startCast", "supportCast", "not in the support list",
    "app disabled in settings", "only cast on pano",
    "whitelist", "cast func enable state check failed",
    "screenCastSwitchApp", "freeWindowAuthRefuse", "auto matic not start app",
    # ③ 方向 / 旋转（谁改了方向、驻车是否禁横屏）
    "can Landscape", "adjustOrientation", "onDisplaysRotationChanged",
    "isLandscapeDisabledWhenParkingOff", "parkingOffForbidLandscape",
    "mLastRotation", "redirectOrientation", "sendSkyWindowRotationChangeMsg",
    "AutoMaticWindowMode onDisplaysRotationChanged",
    # ④ 渲染尺寸与投放
    "onVideoInit width", "createFullWindow width", "createMirrorWindow width",
    "createVirtualDisplay width", "VirtualDisplayChangeListener",
    "onWindowStateChange", "queryAllVirtualDisplayGetDisplayID",
    "startSmallDisplay", "startMirror", "movePackageToDisplay",
    "notifyCastScreenStatus", "startActivityToLauncher",
    "requestedHeight", "mPhoneWidthPixels", "mPhoneHeightPixels", "windowTag",
    # ⑤ 模块标签（兜底，确保不漏）
    "BaseVirtualWindowManager", "ScreenCastController", "WifiDisplay",
]
KEY_RE = "|".join(KEY)

# 车机屏上「谁占了多大地方」要看的窗口标志位（判断是铺满还是带黑边/小窗）
FULLSCREEN_HINT = ("mWindowType=6", "mWindowType = 6", "windowType=6")


def sh(cmd: str, timeout: int = 30) -> str:
    """在设备上执行 shell 命令，返回 stdout+stderr（永不抛异常）。"""
    try:
        r = subprocess.run(["adb", "-s", DEV, "shell", cmd],
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return "__ERR__ 找不到 adb，请确认已安装并加入 PATH"
    except subprocess.TimeoutExpired:
        return "__ERR__ 命令超时：" + cmd
    except Exception as e:  # pragma: no cover
        return f"__ERR__ {e}"


def adb_devices() -> str:
    try:
        r = subprocess.run(["adb", "devices", "-l"], capture_output=True,
                           text=True, timeout=15)
        return r.stdout or ""
    except Exception as e:
        return f"__ERR__ {e}"


def is_err(s: str) -> bool:
    return s.startswith("__ERR__")


# ────────────────────────── 解析 ──────────────────────────

def parse_viewports(dump: str):
    """从 dumpsys display 的 mViewports 里抽出 displayId ↔ uniqueId。"""
    out = []
    for m in re.finditer(r"DisplayViewport\{[^}]*\}", dump):
        seg = m.group(0)
        did = re.search(r"displayId=(\d+)", seg)
        uid = re.search(r"uniqueId='([^']*)'", seg)
        lf = re.search(r"logicalFrame=Rect\((-?\d+), (-?\d+) - (-?\d+), (-?\d+)\)", seg)
        ori = re.search(r"\borientation=(\d+)", seg)
        if did:
            rec = {
                "id": int(did.group(1)),
                "uniqueId": uid.group(1) if uid else "",
            }
            if lf:
                rec["lw"] = int(lf.group(3)) - int(lf.group(1))
                rec["lh"] = int(lf.group(4)) - int(lf.group(2))
            if ori:
                rec["ori"] = int(ori.group(1))   # 0=0° 1=90° 2=180° 3=270°
            out.append(rec)
    return out


def parse_effective_info(dump: str):
    """有效显示信息：优先 mOverrideDisplayInfo（含旋转后的真实几何），兜底 mBaseDisplayInfo。"""
    out = []
    for key in ("mOverrideDisplayInfo", "mBaseDisplayInfo"):
        for m in re.finditer(re.escape(key) + r"=DisplayInfo\{", dump):
            seg = dump[m.start():m.start() + 1200]
            uid = re.search(r'uniqueId "([^"]+)"', seg)
            real = re.search(r"\breal (\d+) x (\d+)", seg)
            rot = re.search(r"\brotation (\d+),", seg)
            dens = re.search(r"density (\d+) \(", seg)
            owner = re.search(r"\bowner ([^,(]+) \(uid \d+\)", seg)
            if not uid or not real:
                continue
            out.append({
                "uniqueId": uid.group(1),
                "w": int(real.group(1)),
                "h": int(real.group(2)),
                "rotation": int(rot.group(1)) if rot else 0,
                "density": int(dens.group(1)) if dens else None,
                "owner": owner.group(1) if owner else "",
                "src": "override" if key == "mOverrideDisplayInfo" else "base",
            })
    return out


def parse_device_infos(dump: str):
    """从 dumpsys display 里抽出每块屏的分辨率/密度/旋转/owner。"""
    out = []
    for m in re.finditer(r"DisplayDeviceInfo\{", dump):
        seg = dump[m.start():m.start() + 1600]
        uid = re.search(r'uniqueId="([^"]+)"', seg)
        wh = re.search(r",\s*(\d{3,5}) x (\d{3,5}),", seg)
        dens = re.search(r"density (\d+)", seg)
        rot = re.search(r"\brotation (\d)", seg)
        owner = re.search(r"\bowner ([^,(]+) \((uid \d+)\)", seg)
        if uid and wh:
            out.append({
                "uniqueId": uid.group(1),
                "w": int(wh.group(1)),
                "h": int(wh.group(2)),
                "density": int(dens.group(1)) if dens else None,
                "rotation": int(rot.group(1)) if rot else None,
                "owner": owner.group(1) if owner else "",
            })
    return out


def parse_windows(text: str):
    """dumpsys window windows → [{name, display, frame, pkg, ty, orient, wmode}]

    实测格式（Android 14 / SkyUI）：
        Window #1 Window{1a2d180 u0 ScreenDecorOverlay}:
          mDisplayId=0 rootTaskId=1 ...
          package=com.android.systemui appop=NONE
          mAttrs={(0,0)(fillxwrap) ... ty=NAVIGATION_BAR_PANEL ...}
          mFullConfiguration={... 600dpi nrml long hdr widecg port ... mWindowingMode=fullscreen ... mRotation=ROTATION_0}
          Frames: parent=... display=[0,0][1440,3200] frame=[0,0][1440,220] ...
    """
    out = []
    for chunk in re.split(r"\n\s*Window #", text)[1:]:
        head = re.search(r"Window\{[^}]*\}", chunk)
        did = re.search(r"mDisplayId=(-?\d+)", chunk)
        if not did:
            continue
        frame = re.search(r"\bframe=(\[[^\]]*\]\[[^\]]*\])", chunk)
        if not frame:
            frame = re.search(r"mFrame=(\[[^\]]*\]\[[^\]]*\])", chunk)
        pkg = re.search(r"\bpackage=([A-Za-z0-9_.]+)", chunk)
        ty = re.search(r"\bty=([A-Z_]+)", chunk)
        wmode = re.search(r"mWindowingMode=(\w+)", chunk)
        cfg = re.search(r"mFullConfiguration=\{(.*?)\}\s*extraConfig", chunk, re.S)
        orient = None
        if cfg:
            c = cfg.group(1)
            if re.search(r"\bland\b", c):
                orient = "land"
            elif re.search(r"\bport\b", c):
                orient = "port"
        out.append({
            "name": head.group(0) if head else "",
            "display": int(did.group(1)),
            "frame": frame.group(1) if frame else "",
            "pkg": pkg.group(1) if pkg else "",
            "ty": ty.group(1) if ty else "",
            "orient": orient,
            "wmode": wmode.group(1) if wmode else "",
        })
    return out


def frame_size(frame: str):
    nums = re.findall(r"-?\d+", frame or "")
    if len(nums) >= 4:
        return int(nums[2]) - int(nums[0]), int(nums[3]) - int(nums[1])
    return None, None


def extract_bool(text: str):
    """从 'ignoreOrientationRequest true for displayId=..' 这类输出里抽 true/false。"""
    m = re.search(r"\b(true|false)\b", text or "")
    return m.group(1) if m else (text or "").strip()[:40]


def ratio_label(w: int, h: int) -> str:
    if w <= 0 or h <= 0:
        return "?"
    if w > h * 1.2:
        return f"横屏 {w / h:.2f}:1（16:9 级）"
    if h > w * 1.2:
        return f"竖屏 1:{h / w:.2f}（9:16 级）"
    return f"近方形 {w / h:.2f}:1"


def pick_lines(logcat: str, patterns, limit=14):
    """按出现顺序取最后 limit 条命中行。"""
    rx = re.compile("|".join(re.escape(p) for p in patterns))
    hits = [ln for ln in logcat.splitlines() if rx.search(ln)]
    return hits[-limit:]


# ────────────────────────── 外出前预检 ──────────────────────────

def preflight() -> int:
    print("=" * 64)
    print("NIO Link 进车预检（这一步在家/插着 USB 时跑完，进车就不慌）")
    print("=" * 64)
    ok = True

    dev = adb_devices()
    if DEV not in dev:
        print(f"[✗] 设备 {DEV} 不在线。adb devices 输出：\n{dev}")
        print("    → 插上 USB / 或在手机开发者选项里确认 USB 调试已开。")
        return 1
    print(f"[✓] 设备 {DEV} 在线")

    # logcat 缓冲：太小的话关键行几秒内就被冲掉，这是最容易踩的坑
    g = sh("logcat -g")
    m = re.search(r"main: ring buffer is (\d+) (KiB|MiB)", g)
    if m:
        size, unit = int(m.group(1)), m.group(2)
        mib = size / 1024 if unit == "KiB" else size
        if mib < 4:
            print(f"[!] logcat main 缓冲只有 {size}{unit} → 正在扩到 16 MiB")
            sh("logcat -G 16M")
            g2 = sh("logcat -g")
            print("    " + (g2.splitlines()[0] if g2 else ""))
        else:
            print(f"[✓] logcat main 缓冲 {size}{unit}（够用）")
    else:
        print("[?] 读不到 logcat 缓冲大小：" + g.strip()[:120])

    # 系统冻结器（之前排查过：NIO 的 QuickFreeze 会冻住后台应用）
    fz = sh("settings get global cached_apps_freezer").strip()
    if fz == "disabled":
        print("[✓] cached_apps_freezer = disabled")
    else:
        print(f"[!] cached_apps_freezer = {fz} → 建议改 disabled")
        sh("settings put global cached_apps_freezer disabled")
        print("    已改为 disabled")

    # 关键命令是否都在（不在就早点知道，免得在车里才发现）
    cmds = {
        "wm user-rotation": "wm user-rotation",
        "wm set-ignore-orientation-request": "wm set-ignore-orientation-request",
        "cmd wifi start-softap": "cmd wifi start-softap",
        "dumpsys display": "dumpsys display",
    }
    for label, c in cmds.items():
        out = sh(c)
        bad = "Unknown command" in out or "not found" in out or is_err(out)
        print(f"[{'✗' if bad else '✓'}] {label}")

    # 基线设置快照（进车后好对照）
    print("\n--- 基线设置 ---")
    for k in ("skylink_feature_switch", "skylink_inject_rotation",
              "skylink_inject_rotation_value", "skylink_cast_start",
              "skyui_custom_rotation", "cached_apps_freezer"):
        print(f"  {k} = {sh(f'settings get global {k}').strip()}")

    # 白名单里已装的应用（进车就从这几个开点）
    print("\n--- 白名单中本机已安装的应用（进车优先点这些）---")
    csv_path = os.path.join(PROJ, "data", "nio_link_whitelist.csv")
    if os.path.exists(csv_path):
        import csv as _csv
        rows = list(_csv.DictReader(open(csv_path, encoding="utf-8-sig")))
        inst = [r for r in rows if (r.get("installed") or "").strip() == "yes"]
        for r in inst:
            pkg = r.get("pkgName", "")
            alive = "已装" if pkg in sh(f"pm list packages {pkg}") else "?? 未装"
            print(f"  [{r.get('bizType', '')}] {r.get('appName_zh', ''):8} "
                  f"{pkg:46} {alive}")
    else:
        print("  (找不到 data/nio_link_whitelist.csv)")

    print("\n[结论] 预检完毕。进车后：先在车机上打开「天空视窗」，"
          "再跑 ./tools/car-session.py")
    return 0 if ok else 1


# ────────────────────────── 单次采样 ──────────────────────────

def snapshot(tag: str, pkg: str, quiet: bool) -> int:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = ts + (f"-{tag}" if tag else "")
    outdir = os.path.join(PROJ, "data", "car-sessions", name)

    display = sh("dumpsys display", timeout=40)
    windows = sh("dumpsys window windows", timeout=40)
    if is_err(windows) or "Window #" not in windows:
        windows = sh("dumpsys window", timeout=40)
    acts = sh("dumpsys activity activities", timeout=40)
    logcat = sh("logcat -d -v time -t 20000", timeout=60)

    # 车机屏识别：先看 viewport，再兜底看 device info
    vps = parse_viewports(display)
    infos = parse_device_infos(display)
    effs = parse_effective_info(display)
    car_id = None
    car_vp = None
    for v in vps:
        if CAR_MARK in v["uniqueId"]:
            car_id = v["id"]
            car_vp = v
            break
    # 几何以「有效 DisplayInfo」为准（它含旋转后的真实宽高），否则退回设备信息
    car_info = None
    for i in effs:
        if CAR_MARK in i["uniqueId"]:
            car_info = i
            break
    if car_info is None:
        for i in infos:
            if CAR_MARK in i["uniqueId"]:
                car_info = dict(i)
                break
    if car_info is None and car_vp:
        car_info = {
            "uniqueId": car_vp["uniqueId"],
            "w": car_vp.get("lw"), "h": car_vp.get("lh"),
            "rotation": car_vp.get("ori", 0), "density": None, "owner": "",
        }

    if car_id is None and car_info is None:
        print("❌ 没检测到车机屏（uniqueId 里没有 " + CAR_MARK + "）")
        print("   当前设备上存在的屏：")
        for ln in [l for l in display.splitlines() if "DisplayViewport{" in l]:
            print("   " + ln.strip()[:220])
        print("\n   常见原因：① 车机上还没打开「天空视窗」/ NIO Link ② USB 掉了 "
              "③ 手机没和车机连上")
        print("   修好后重跑本命令即可（本次未落盘）。")
        return 2

    os.makedirs(outdir, exist_ok=True)

    # 关注应用的窗口
    wins = parse_windows(windows)
    app_wins = [w for w in wins if pkg and (pkg in w["name"] or w["pkg"] == pkg)]
    car_wins = [w for w in wins if car_id is not None and w["display"] == car_id]

    # 关键日志
    keylines = [ln for ln in logcat.splitlines() if re.search(KEY_RE, ln)]

    # mWindowType 的现值（取最后一条 getVirtualDisplay / startActivityToLauncher）
    wt_now, wt_src = None, ""
    for ln in reversed(keylines):
        if "mWindowType" in ln:
            mm = re.search(r"mWindowType\s*=\s*(\d+)", ln)
            if mm:
                wt_now, wt_src = int(mm.group(1)), ln.strip()
                break

    st_now = None
    for ln in reversed(keylines):
        mm = re.search(r"mScreenType=(\d+)", ln)
        if mm:
            st_now = int(mm.group(1))
            break

    # 白名单准入结论：拒绝日志会直接说明原因
    verdict_deny = [ln for ln in keylines
                    if ("not in the support list" in ln
                        or "app disabled in settings" in ln
                        or "only cast on pano" in ln
                        or "cast func enable state check failed" in ln)]
    verdict_allow = [ln for ln in keylines if "supportCast packageName=" in ln]

    # 方向闸门
    park = [ln for ln in keylines if "ark" in ln and "Landscape" in ln]
    orient = [ln for ln in keylines if "onDisplaysRotationChanged" in ln
              or "adjustOrientation" in ln or "can Landscape" in ln]

    settings = {k: sh(f"settings get global {k}").strip()
                for k in ("skyui_custom_rotation", "skylink_feature_switch",
                          "skylink_inject_rotation", "skylink_inject_rotation_value",
                          "skylink_cast_start", "cached_apps_freezer")}
    urot = sh(f"wm user-rotation -d {car_id}").strip() if car_id is not None else "?"
    igor = extract_bool(sh(f"wm get-ignore-orientation-request -d {car_id}")) \
        if car_id is not None else "?"
    top = ""
    for ln in acts.splitlines():
        if "topResumedActivity" in ln:
            top = ln.strip()
            break

    skylink = sh("dumpsys activity services com.skyui.skylink.coreservice", timeout=30)

    # ── 落盘 ──
    def dump(fn, content):
        with open(os.path.join(outdir, fn), "w", encoding="utf-8") as f:
            f.write(content)

    dump("display.txt", display)
    dump("windows.txt", windows)
    dump("activity.txt", acts)
    dump("logcat.txt", "\n".join(keylines) if keylines else "(无关键行)")
    dump("settings.txt", "\n".join(f"{k}={v}" for k, v in settings.items()))
    dump("skylink.txt", skylink)

    # ── 结论 ──
    L = []
    L.append("=" * 64)
    L.append(f"NIO Link 采样小结   {datetime.datetime.now():%Y-%m-%d %H:%M:%S}   tag={tag or '-'}")
    L.append("=" * 64)
    if car_info:
        L.append(f"车机屏        : displayId={car_id}  "
                 f"{car_info['w']}x{car_info['h']}  → {ratio_label(car_info['w'], car_info['h'])}"
                 f"   density={car_info['density']}  rotation={car_info['rotation']}")
    else:
        L.append(f"车机屏        : displayId={car_id}  (从 device info 未解析到分辨率)")
    L.append(f"关注应用      : {pkg}")

    if app_wins:
        for w in app_wins:
            L.append(f"  应用窗口    : display={w['display']}  frame={w['frame']}"
                     f"  ty={w['ty']}  方向={w['orient']}  {w['wmode']}")
            aw, ah = frame_size(w["frame"])
            if aw and car_info and w["display"] == car_id:
                pct = 100.0 * aw / car_info["w"]
                L.append(f"    实测占屏    : {aw}x{ah}"
                         f"（车机屏 {car_info['w']}x{car_info['h']}，横向占 {pct:.0f}%）")
            elif aw and w["display"] == 0:
                L.append(f"    在手机屏上   : {aw}x{ah}  ← 没有投到车机屏")
    else:
        L.append("  应用窗口    : 未在窗口列表里找到该应用"
                 "（可能没启动，或被投到别的屏）")

    if car_wins:
        L.append(f"  车机屏上窗口: {len(car_wins)} 个")
        for w in car_wins[:8]:
            aw, ah = frame_size(w["frame"])
            size = f"{aw}x{ah}" if aw else "?"
            L.append(f"    - {size:12} {w['orient'] or '?':4} {w['ty']:24} "
                     f"{w['pkg'] or w['name'][:48]}")
    else:
        L.append("  车机屏上窗口: 0 个 ← 车机屏是空的，没有应用被投上去")

    L.append("")
    if wt_now is not None:
        meaning = {1: "小窗", 2: "镜像(9:16 降级)", 6: "★原生级(16:9)"}.get(wt_now, "未知")
        L.append(f"mWindowType   : {wt_now}  → {meaning}")
    else:
        L.append("mWindowType   : 本次没抓到（可能应用还没投上去；"
                 "先开 car-watch.sh 再操作）")
    L.append(f"mScreenType   : {st_now}")
    L.append(f"日志原文      : {wt_src[:180] or '(空)'}")

    if verdict_deny:
        L.append("白名单判定    : ✗ 被拒 →")
        for ln in verdict_deny[-3:]:
            L.append("    " + ln.strip()[:180])
    elif verdict_allow:
        L.append("白名单判定    : ✓ 放行 → " + verdict_allow[-1].strip()[:160])
    else:
        L.append("白名单判定    : 本次无明确放行/拒绝日志")

    L.append(f"方向状态      : user-rotation={urot}  "
             f"ignoreOrientationRequest={igor}  "
             f"skyui_custom_rotation={settings['skyui_custom_rotation']}  "
             f"skylink_inject_rotation={settings['skylink_inject_rotation']}")
    if orient:
        L.append("旋转相关日志  :")
        for ln in orient[-4:]:
            L.append("    " + ln.strip()[:180])
    if park:
        L.append("驻车/横屏闸门 :")
        for ln in park[-4:]:
            L.append("    " + ln.strip()[:180])
    L.append(f"前台 Activity : {top[:150]}")
    L.append("")

    # ── 一句话结论（这是进车最该抄下来回传的一行）────────────────────
    verdict = []
    if wt_now == 6:
        verdict.append("★ 拿到原生级(6)")
    elif wt_now == 2:
        verdict.append("✗ 被降级为镜像(2)")
    elif wt_now == 1:
        verdict.append("· 小窗(1)")
    else:
        verdict.append("? 本次没抓到 mWindowType")
    if car_info:
        verdict.append(f"车机屏 {ratio_label(car_info['w'], car_info['h']).split('（')[0]}")
    if verdict_deny:
        verdict.append("白名单拒绝")
    app_on_car = [w for w in app_wins if w["display"] == car_id]
    if app_on_car:
        verdict.append(f"应用在车机屏上（{app_on_car[0]['orient'] or '方向未知'}）")
    elif app_wins:
        verdict.append("应用只在手机屏上")
    L.append("【一句话结论】 " + " ｜ ".join(verdict))
    L.append("判定速查：6=原生级可套壳 ／ 2=镜像，套壳白做 ／ 1=小窗")
    L.append(f"落盘目录：{outdir}")
    L.append("=" * 64)
    summary = "\n".join(L)
    dump("summary.txt", summary)

    if quiet:
        for ln in keylines[-40:]:
            print(ln)
    else:
        print(summary)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--preflight", action="store_true", help="外出前预检")
    ap.add_argument("--tag", default="", help="本次采样命名，便于对照")
    ap.add_argument("--pkg", default=DEFAULT_PKG, help="关注的应用包名")
    ap.add_argument("--why", action="store_true", help="只打印关键日志，不落盘")
    a = ap.parse_args()

    if a.preflight:
        return preflight()
    return snapshot(a.tag, a.pkg, a.why)


if __name__ == "__main__":
    sys.exit(main())
