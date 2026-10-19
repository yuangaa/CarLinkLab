#!/usr/bin/env python3
"""Record Apple Music on owned source-sized display without shell video decoder."""
import pathlib,subprocess,time,re,json,datetime,sys
ROOT=pathlib.Path(__file__).resolve().parent.parent;OUT=ROOT/'data/native-scroll-baseline'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');OUT.mkdir(parents=True)
def adb(*a):
 p=subprocess.run(['adb',*a],capture_output=True,text=True,timeout=25)
 if p.returncode:raise RuntimeError(p.stderr+p.stdout)
 return p.stdout
if re.search(r'\bshowing=true',adb('shell','dumpsys','window','policy')):raise RuntimeError('安全锁屏，未进行测试')
log=(OUT/'record.log').open('w');start=time.monotonic();p=subprocess.Popen([str(ROOT/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy'),'--new-display=2560x2558/474','--no-vd-system-decorations','--start-app=com.apple.android.music','--no-audio','--no-playback','--max-size=1920','--max-fps=30','--time-limit=30','--record='+str(OUT/'native.mkv')],stdout=log,stderr=log)
try:
 for _ in range(60):
  m=re.search(r'New display:.*id=(\d+)',(OUT/'record.log').read_text())
  if m:break
  time.sleep(.2)
 if not m:raise RuntimeError('display unavailable')
 display=m[1];time.sleep(7);windows=[]
 for i in range(6):
  y1,y2=(1885,830) if i%2==0 else (830,1885)
  out=adb('shell','cat /proc/uptime; input -d '+display+' swipe 1945 '+str(y1)+' '+str(y2)+' 1000; cat /proc/uptime')
  stamps=[float(l.split()[0])*1000 for l in out.splitlines() if re.match(r'^\d+\.\d+ ',l)]
  windows.append({'gesture':i+1,'uptimeMs':stamps,'recordingSecondsApprox':time.monotonic()-start});print('Native swipe',i+1,flush=True)
 (OUT/'gesture-windows.json').write_text(json.dumps(windows,indent=2));(OUT/'activities.txt').write_text(adb('shell','dumpsys','activity','activities'));print('Evidence',OUT,flush=True)
finally:
 p.wait(timeout=40);log.close()
 sys.path.insert(0,'/tmp/am-video-tools');import imageio_ffmpeg
 subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-ss','9','-t','6','-i',str(OUT/'native.mkv'),'-vf','fps=1,scale=320:-1,tile=3x2','-frames:v','1',str(OUT/'contact-sheet.png')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
