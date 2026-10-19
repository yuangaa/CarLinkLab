#!/usr/bin/env python3
"""One-click USB preparation; then test offline without the computer."""
import argparse,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--minutes',type=int,default=60)
a=p.parse_args()
if not 1<=a.minutes<=120:p.error('minutes must be 1..120')
def call(script,*args):
 r=subprocess.run([sys.executable,str(ROOT/'tools'/script),*args],cwd=ROOT,capture_output=True,text=True,timeout=60)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).strip())
 return r.stdout.strip()
started_capture=False
try:
 check=subprocess.run(['adb','get-state'],capture_output=True,text=True,timeout=10)
 if check.returncode or check.stdout.strip()!='device':raise RuntimeError('请用 USB 连接手机，解锁屏幕，并允许 USB 调试；只连接一部手机。')
 # Refuse overlapping sessions rather than replace or terminate an earlier test.
 for state,done in [('offline-capture-state.json',None),('../am-embedded/bridge-state.json','/sdcard/Download/am-bridge-supervisor.done')]:
  path=ROOT/'data/am-landscape'/state
  if not path.exists():continue
  info=json.loads(path.read_text())
  remote_done=done or info['remote']+'/done'
  result=subprocess.run(['adb','shell','test -f '+remote_done+' && echo finished || echo active'],capture_output=True,text=True,timeout=10)
  if result.returncode or result.stdout.strip()!='finished':raise RuntimeError('已有测试正在记录，请结束该轮后再启动；本次没有覆盖原记录。')
 print('正在启动手机离线采集…',flush=True)
 call('offline-am-capture.py','start','--minutes',str(a.minutes));started_capture=True
 print('正在启动原生 AM 画布桥接…',flush=True)
 call('arm-am-embedded.py','start','--minutes',str(a.minutes))
 r=subprocess.run(['adb','shell','am','start','-n','com.oumi.utility.media.hub/lab.carlink.amlandscape.MainActivity'],capture_output=True,text=True,timeout=15)
 if r.returncode:print('准备已完成；请手动打开手机上的 AM 横屏助手。',flush=True)
 print('\n准备完成。两项后台任务均已启动，持续 '+str(a.minutes)+' 分钟（路程也算在内）。\n手机助手 → 原生 AM 大画布（实验），确认画面后即可拔线。\n在车内点击“标记”记录开始和结束，并拍下车机效果。\n回来连接 USB 后读取日志；重启手机会中断本轮。',flush=True)
except Exception as exc:
 if started_capture:
  try:call('offline-am-capture.py','stop')
  except Exception:pass
 print('\n准备未完成：'+str(exc),file=sys.stderr)
 sys.exit(1)
