#!/usr/bin/env python3
"""Desktop display-and-touch test bench; does not emulate NIO authorization or car audio."""
import argparse,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--seconds',type=int,default=300,help='Preview time limit (default 300 seconds)')
p.add_argument('--headless',action='store_true',help='Record the preview without opening a desktop window')
p.add_argument('--record',type=pathlib.Path,help='Optional MKV recording path')
a=p.parse_args()
binary=root/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy'
if not binary.exists():p.error('scrcpy 5.0 portable runtime missing')
heartbeat=subprocess.run(['adb','shell','cat','/sdcard/Android/data/com.oumi.utility.media.hub/files/phone-guardian-state'],capture_output=True,text=True,check=True).stdout.strip()
if heartbeat!='running':p.error('先在主助手点击开始车内测试，等后台记录中，再打开桌面测试台。')
cmd=[str(binary),'--new-display=3024x1696/600','--no-vd-system-decorations','--start-app=com.oumi.utility.media.hub','--no-audio','--time-limit='+str(a.seconds),'--window-title=AM 桌面测试台 · 非 NIO Link 仿真']
if a.headless:cmd+=['--no-playback']
if a.record:
 a.record.parent.mkdir(parents=True,exist_ok=True);cmd+=['--record='+str(a.record.resolve())]
if a.headless and not a.record:p.error('--headless requires --record')
raise SystemExit(subprocess.call(cmd))
