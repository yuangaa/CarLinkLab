#!/usr/bin/env python3
"""Exercise task/display migration on two owned desktop displays, not NIO protocol."""
import pathlib,subprocess,time,json,re,datetime,sys,argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--renderer",choices=["texture","surface"],default="texture");options=parser.parse_args()
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/'data/am-desktop-migration'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');OUT.mkdir(parents=True)
FILES='/sdcard/Android/data/com.oumi.utility.media.hub/files/'
APP='com.oumi.utility.media.hub/lab.carlink.amlandscape.MainActivity'
def adb(*args):
 p=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=30)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return p.stdout
processes=[];logs=[];marks=[]
try:
 adb('shell','input','keyevent','KEYCODE_WAKEUP')
 if re.search(r'\bshowing=true',adb('shell','dumpsys','window','policy')):raise RuntimeError('安全锁屏')
 adb('install','-r',str(ROOT/'apps/am-landscape/am-landscape.apk'))
 adb('shell','printf '+options.renderer+' > '+FILES+'renderer-mode; chmod 644 '+FILES+'renderer-mode')
 adb('shell','touch',FILES+'phone-guardian-start');time.sleep(3)
 if adb('shell','cat',FILES+'phone-guardian-state').strip()!='running':raise RuntimeError('后台未启动')
 def make(name,size):
  file=OUT/(name+'.log');log=file.open('w');logs.append(log)
  start=time.monotonic();p=subprocess.Popen([str(ROOT/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy'),'--new-display='+size,'--no-vd-system-decorations','--no-audio','--no-playback','--max-size=1280','--max-fps=30','--time-limit=80','--record='+str(OUT/(name+'.mkv'))],stdout=log,stderr=log);processes.append(p)
  for _ in range(80):
   match=re.search(r'New display:.*id=(\d+)',file.read_text())
   if match:return {'name':name,'id':match[1],'start':start}
   time.sleep(.2)
  raise RuntimeError('显示器建立失败')
 a=make('screen-a','3024x1696/600');b=make('screen-b','2800x1600/600')
 adb('shell','am','start','--display',a['id'],'-f','0x10008000','-n',APP);time.sleep(4)
 rows=[json.loads(x) for x in adb('shell','cat',FILES+'diagnostics/events.jsonl').splitlines() if x.strip()]
 sid=next(x['session'] for x in reversed(rows) if x['event']=='process_start')
 buttons=[x for x in rows if x['session']==sid and x['event']=='entry_control_geometry' and str(x['displayId'])==a['id'] and x['label']=='打开 Apple Music']
 if not buttons:raise RuntimeError('入口未布局')
 button=buttons[-1];adb('shell','input','-d',a['id'],'tap',str(button['x']),str(button['y']));time.sleep(7)
 for n,screen in enumerate([a,b,a],1):
  if n>1:adb('shell','am','start','--display',screen['id'],'-f','0x10200000','-n',APP);time.sleep(7)
  (OUT/('round-'+str(n)+'-activities.txt')).write_text(adb('shell','dumpsys','activity','activities'))
  adb('shell','input','-d',screen['id'],'swipe','1450','1250','1450','550','350');time.sleep(2)
  marks.append({'round':n,'screen':screen['name'],'seconds':time.monotonic()-screen['start']});(OUT/'screenshot-marks.json').write_text(json.dumps(marks,indent=2));print('Round '+str(n)+' display '+screen['id'],flush=True);time.sleep(3)
 data=adb('shell','cat',FILES+'diagnostics/events.jsonl');(OUT/'events.jsonl').write_text(data)
 rows=[json.loads(x) for x in data.splitlines() if x.strip()];rows=[x for x in rows if x['session']==sid]
 events=[x for x in rows if x['event'].startswith('embedded_')];(OUT/'migration-events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
 selected=[x for x in rows if x['event']=='embedded_renderer_selected']
 if not selected or any(x.get('renderer')!=options.renderer for x in selected):raise RuntimeError('Renderer mismatch')
 (OUT/'renderer.json').write_text(json.dumps({'requested':options.renderer,'selected':selected},indent=2))
 print('Evidence '+str(OUT),flush=True)
finally:
 for p in processes:
  try:p.wait(timeout=55)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 for log in logs:log.close()
 adb('shell','touch',FILES+'phone-guardian-stop')
 sys.path.insert(0,'/tmp/am-video-tools')
 import imageio_ffmpeg
 for mark in marks:
  target=OUT/('round-'+str(mark['round'])+'.png')
  video=OUT/(mark['screen']+'.mkv')
  sample=max(0,mark['seconds']-1)
  def extract(seconds):
   subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-ss',str(seconds),'-i',str(video),'-frames:v','1',str(target)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
  extract(sample)
  if not target.exists():
   # Recording timestamps begin at first frame, later than display creation.
   # Preserve the original wall-clock mark and explicitly label the fallback.
   sample=5;extract(sample);mark['fallbackSampleSeconds']=sample
  if not target.exists():raise RuntimeError('截图缺失: '+str(target))
 (OUT/'screenshot-marks.json').write_text(json.dumps(marks,indent=2))
 print('Stopped '+str(OUT),flush=True)
