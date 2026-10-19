#!/usr/bin/env python3
"""Retrieve the latest phone-button-started test after reconnecting USB."""
import pathlib,subprocess,shutil,re
root=pathlib.Path(__file__).resolve().parent.parent
def adb(*args):
 r=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=120)
 if r.returncode:raise RuntimeError((r.stdout+r.stderr).strip())
 return r.stdout.strip()
try:
 remote=adb('shell','cat','/sdcard/Android/data/com.oumi.utility.media.hub/files/phone-guardian-capture')
 if not re.fullmatch(r'/sdcard/Download/AM-offline-\d{8}-\d{6}',remote):raise RuntimeError('No valid phone test path')
 done=adb('shell','test -f '+remote+'/done && echo done || echo running')
 if done!='done':raise RuntimeError('请先在手机点击结束测试，并等到重新显示已预备，再读取。')
 dest=root/'data/am-landscape'/pathlib.Path(remote).name
 adb('pull',remote,str(dest))
 archive=shutil.make_archive(str(dest),'zip',root_dir=dest)
 print('Saved: '+archive)
except Exception as e:raise SystemExit(str(e))
