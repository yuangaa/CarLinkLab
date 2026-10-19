#!/usr/bin/env python3
"""Repeatable UI traffic and reconnect trial on a disposable display, not a NIO emulator."""
import pathlib,subprocess,time,re,json,datetime,statistics,argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--keyboard-only',action='store_true');parser.add_argument('--keyboard-menu',action='store_true');parser.add_argument('--verify-keyboard',action='store_true');parser.add_argument('--traffic',choices=['mixed','scroll'],default='mixed');parser.add_argument('--profile',choices=['baseline','fast','sharp','wide','balanced'],default='baseline');parser.add_argument("--app",choices=["am","spotify"],default="am");parser.add_argument("--theme",choices=["light","dark"]);parser.add_argument("--transition",choices=["reconnect","theme"],default="reconnect");parser.add_argument('--host',choices=['wide','car'],default='wide');parser.add_argument('--cycles',type=int,default=3);parser.add_argument('--idle-seconds',type=float,default=0);parser.add_argument('--capture-size',type=int,default=1280);parser.add_argument('--verify-controls',action='store_true');parser.add_argument('--dismiss-spotify-promo',action='store_true');parser.add_argument('--auto-record',action='store_true');parser.add_argument('--sleep-phone',action='store_true');parser.add_argument('--renderer',choices=['texture','surface'],default='texture');options=parser.parse_args();hostW,hostH=(3232,3248) if options.host=='car' else (3024,1696)
if options.transition=="theme" and not options.theme:parser.error("theme transition requires --theme")
if options.keyboard_only and not options.verify_keyboard:parser.error("keyboard-only requires verify-keyboard")
if options.keyboard_menu and not options.verify_keyboard:parser.error("keyboard-menu requires verify-keyboard")
if options.verify_keyboard and options.host!='car':parser.error('Keyboard coordinates require near-square host')
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/'data/am-desktop-stress'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S');OUT.mkdir(parents=True)
FILES='/sdcard/Android/data/com.oumi.utility.media.hub/files/'
def adb(*args):
 r=subprocess.run(['adb',*args],capture_output=True,text=True,timeout=25)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r.stdout
def readDiagnostics():
 return adb('shell','for f in '+FILES+'diagnostics/events.previous.jsonl '+FILES+'diagnostics/events.jsonl; do if [ -f "$f" ]; then cat "$f"; fi; done')
p=None;original=None;originalTheme=None;captureMarks=[];memorySamples=[];gestureWindows=[];seenDiagnostics=set()
def preserveDiagnostics(session):
 data=readDiagnostics()
 with (OUT/'events-live.jsonl').open('a') as stream:
  for line in data.splitlines():
   if line.strip() and json.loads(line).get('session')==session and line not in seenDiagnostics:
    stream.write(line+'\n');seenDiagnostics.add(line)
 return data
if not 3<=options.cycles<=60 or not 0<=options.idle_seconds<=60:parser.error("cycles 3..60, idle seconds 0..60")
try:
 adb('shell','input','keyevent','KEYCODE_WAKEUP')
 if re.search(r'\bshowing=true',adb('shell','dumpsys','window','policy')):raise RuntimeError('安全锁屏：需用户解锁；此次不计入通过率。')
 if options.theme:
  mode=adb('shell','cmd','uimode','night');found=re.search(r'Night mode: (yes|no|auto|custom)',mode)
  if not found:raise RuntimeError('无法读取原主题，停止以免无法恢复：'+mode)
  originalTheme=found[1];adb('shell','cmd','uimode','night','yes' if options.theme=='dark' else 'no')
 adb('install','-r',str(ROOT/'apps/am-landscape/am-landscape.apk'))
 adb('shell','printf '+options.renderer+' > '+FILES+'renderer-mode; chmod 644 '+FILES+'renderer-mode')
 if options.profile in ['fast','sharp','wide','balanced']:
  original=OUT/'supervisor-original.sh';original.write_text(adb('shell','cat','/data/local/tmp/am-phone-supervisor.sh'))
  variant=OUT/('supervisor-'+options.profile+'.sh');variantText=original.read_text()
  if options.profile=='fast':variantText=variantText.replace('max_fps=30','max_fps=60')
  elif options.profile=='balanced':
   if 'max_size=2560' not in variantText:raise RuntimeError('balanced试验要求2560当前基线')
   variantText=variantText.replace('max_size=2560','max_size=2240')
  elif options.profile=='sharp':variantText=variantText.replace('max_size=1920','max_size=2560')
  else:variantText=variantText.replace('new_display=3232x3248/600','new_display=3024x1696/300')
  variant.write_text(variantText)
  adb('push',str(variant),'/data/local/tmp/am-phone-supervisor.sh')
 if not options.auto_record:
  adb('shell','touch',FILES+'phone-guardian-start');time.sleep(3)
  if adb('shell','cat',FILES+'phone-guardian-state').strip()!='running':raise RuntimeError('测试后台未启动')
 log=open(OUT/'preview.log','w')
 p=subprocess.Popen([str(ROOT/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy'),'--new-display='+str(hostW)+'x'+str(hostH)+'/600','--no-vd-system-decorations','--start-app=com.oumi.utility.media.hub','--no-audio','--no-playback','--max-size='+str(options.capture_size),'--max-fps=30','--time-limit='+str(70 if options.keyboard_only else int(max(65,options.cycles*(20+options.idle_seconds)+25))),'--record='+str(OUT/'preview.mkv')],stdout=log,stderr=log)
 recordStarted=time.monotonic();m=None
 for _ in range(60):
  m=re.search(r'New display:.*id=(\d+)',(OUT/'preview.log').read_text())
  if m:break
  time.sleep(.2)
 if not m:raise RuntimeError('模拟屏未建立')
 display=m[1];print('Display '+display+'; results '+str(OUT),flush=True);adb('shell','am','start','--display',display,'-f','0x10008000','-n','com.oumi.utility.media.hub/lab.carlink.amlandscape.MainActivity');time.sleep(4)
 if options.auto_record:
  for attempt in range(10):
   if adb('shell','cat',FILES+'phone-guardian-state').strip()=='running':break
   time.sleep(1)
  else:raise RuntimeError('自动记录未启动')
  print('Automatic recording verified without phone start request',flush=True)
 def tap(x,y):adb('shell','input','-d',display,'tap',str(x),str(y))
 initialRows=[json.loads(line) for line in readDiagnostics().splitlines() if line.strip()]
 testSession=next(x['session'] for x in reversed(initialRows) if x['event']=='process_start')
 preserveDiagnostics(testSession)
 initialOpens=sum(x["event"]=="embedded_open" for x in initialRows)
 captureMarks.append({'round':'entry','seconds':time.monotonic()-recordStarted})
 (OUT/'screenshot-marks.json').write_text(json.dumps(captureMarks,indent=2));time.sleep(3)
 for attempt in range(3):
  bounds=[json.loads(line) for line in readDiagnostics().splitlines() if line.strip()]
  matching=[x for x in bounds if x['event']=='entry_control_geometry' and x.get('displayId')==int(display) and x.get('label')==('打开 Spotify' if options.app=='spotify' else '打开 Apple Music')]
  if not matching:raise RuntimeError('没有入口几何信息，停止盲点')
  button=matching[-1];print('Entry center '+str((button['x'],button['y'])),flush=True)
  tap(button['x'],button['y']);time.sleep(3)
  probe=readDiagnostics()
  recent=[json.loads(line) for line in probe.splitlines() if line.strip()]
  if sum(x['event']=='embedded_open' for x in recent)>initialOpens:break
 else:raise RuntimeError('未进入原生画布，保留失败录像；不计算通过率')
 time.sleep(2)
 if options.dismiss_spotify_promo:
  if options.app!='spotify' or options.host!='car':raise RuntimeError('Promo dismissal coordinates only for observed Spotify near-square dialog')
  tap(round(hostW*.5),round(hostH*.813));time.sleep(1)
 if options.sleep_phone:
  adb('shell','input','-d','0','keyevent','223');time.sleep(15)
  (OUT/'phone-sleep-display.txt').write_text(adb('shell','dumpsys','display'))
  (OUT/'phone-sleep-power.txt').write_text(adb('shell','dumpsys','power'))
 if options.verify_controls:
  if options.host!='car':raise RuntimeError('Native control coordinates currently defined only for near-square host')
  package='com.spotify.music' if options.app=='spotify' else 'com.apple.android.music'
  x,y=(round(hostW*.126),round(hostH*.892)) if options.app=='spotify' else (round(hostW*.918),round(hostH*.966))
  for n in range(2):
   r=subprocess.run(['python3',str(ROOT/'tools/verify-native-music-control.py'),'--package',package,'--display',display,'--x',str(x),'--y',str(y),'--expected','TOGGLE'],capture_output=True,text=True)
   (OUT/('native-control-'+str(n+1)+'.log')).write_text(r.stdout+r.stderr)
   if r.returncode:raise RuntimeError('Native control verification failed; see saved log')
   print('Native player toggle '+str(n+1)+' verified',flush=True)
 if options.verify_keyboard:
  searchX,searchY=(.08,.11) if options.app=='spotify' else (.43,.966)
  tap(round(hostW*searchX),round(hostH*searchY));time.sleep(1)
  tap(round(hostW*.5 if options.app=='spotify' else hostW*.3),round(hostH*(.14 if options.app=='spotify' else .052)));time.sleep(3)
  imeEvidence=adb('shell','dumpsys','input_method')
  (OUT/'keyboard-input-method.txt').write_text(imeEvidence)
  (OUT/'keyboard-windows.txt').write_text(adb('shell','dumpsys','window','windows'))
  captureMarks.append({'round':'keyboard','seconds':time.monotonic()-recordStarted});(OUT/'screenshot-marks.json').write_text(json.dumps(captureMarks,indent=2))
  print('Keyboard focus evidence saved',flush=True);time.sleep(3)
  if not re.search(r'mInputShown=true',imeEvidence):raise RuntimeError('Keyboard is not shown; stop rather than tapping content as keyboard keys')
  if options.keyboard_menu:
   tap(round(hostW*.08),round(hostH*.65));time.sleep(2)
   captureMarks.append({'round':'keyboard-menu','seconds':time.monotonic()-recordStarted});(OUT/'screenshot-marks.json').write_text(json.dumps(captureMarks,indent=2));time.sleep(3)
   tap(round(hostW*.08),round(hostH*.65));time.sleep(1)
  # Observed split Pinyin keyboard: tap its n/i keys through the shell surface.
  for x,y in [(.785,.84),(.791,.713)]:tap(round(hostW*x),round(hostH*y));time.sleep(.4)
  captureMarks.append({'round':'keyboard-typed','seconds':time.monotonic()-recordStarted});(OUT/'screenshot-marks.json').write_text(json.dumps(captureMarks,indent=2));time.sleep(3)
  tap(round(hostW*.53),round(hostH*.906));time.sleep(.5)
  tap(round(hostW*.913),round(hostH*.906));time.sleep(3)
  captureMarks.append({'round':'keyboard-submitted','seconds':time.monotonic()-recordStarted});(OUT/'screenshot-marks.json').write_text(json.dumps(captureMarks,indent=2));time.sleep(3)
  if options.sleep_phone:(OUT/'keyboard-submitted-display.txt').write_text(adb('shell','dumpsys','display'))
 for cycle in range(0 if options.keyboard_only else options.cycles):
  print('Traffic cycle '+str(cycle+1),flush=True)
  for i in range(6):
   # Scroll AM content in both directions, then touch its bottom navigation.
   a,b=(1250,550) if i%2==0 else (550,1250)
   if options.traffic=='scroll':
    x=round(hostW*.76);y1=round(a*hostH/1696);y2=round(b*hostH/1696)
    timing=adb('shell','cat /proc/uptime; input -d '+display+' swipe '+str(x)+' '+str(y1)+' '+str(x)+' '+str(y2)+' 1000; cat /proc/uptime')
    stamps=[float(line.split()[0])*1000 for line in timing.splitlines() if re.match(r'^\d+\.\d+ ',line)]
    if len(stamps)!=2:raise RuntimeError('Gesture uptime markers missing')
    gestureWindows.append({'round':cycle+1,'gesture':i+1,'startMs':stamps[0],'endMs':stamps[1]});(OUT/'gesture-windows.json').write_text(json.dumps(gestureWindows,indent=2))
   else:
    adb('shell','input','-d',display,'swipe',str(round(hostW*.48)),str(round(a*hostH/1696)),str(round(hostW*.48)),str(round(b*hostH/1696)),'350')
    tap(round((1150+(i%3)*210)*hostW/3024),round(1640*hostH/1696));time.sleep(.6)
  captureMarks.append({'round':cycle+1,'seconds':time.monotonic()-recordStarted})
  (OUT/'screenshot-marks.json').write_text(json.dumps(captureMarks,indent=2))
  preserveDiagnostics(testSession)
  if options.sleep_phone:(OUT/('round-'+str(cycle+1)+'-display.txt')).write_text(adb('shell','dumpsys','display'))
  memorySamples.append({'cycle':cycle+1,'meminfo':adb('shell','dumpsys','meminfo','com.oumi.utility.media.hub')})
  (OUT/'memory-samples.json').write_text(json.dumps(memorySamples,indent=2))
  if options.idle_seconds:time.sleep(options.idle_seconds)
  if cycle<options.cycles-1:
   # Keep this state stable while recorder startup delay catches up to the screenshot mark.
   time.sleep(3)
   if options.transition=='theme':
    nextTheme=('no' if options.theme=='dark' else 'yes') if cycle==0 else ('yes' if options.theme=='dark' else 'no')
    adb('shell','cmd','uimode','night',nextTheme);time.sleep(5);print('Theme transition '+nextTheme,flush=True)
   else:
    tap(round(hostW-42*3.75),round(98*3.75));tap(round(hostW-126*3.75),round(42*3.75));time.sleep(5);print('Reconnect '+str(cycle+1)+' requested',flush=True)
 time.sleep(3)
 preserveDiagnostics(testSession);data=(OUT/'events-live.jsonl').read_text();(OUT/'events.jsonl').write_text(data)
 rows=[json.loads(l) for l in data.splitlines() if l.strip()]
 sid=testSession;rows=[x for x in rows if x['session']==sid]
 metrics=[x for x in rows if x['event']=='embedded_frame_metrics'];inputs=[x for x in rows if x['event']=='embedded_touch_sent']
 rates=[x['frames']*1000/x['intervalMs'] for x in metrics]
 presented=[x for x in rows if x['event'] in ['embedded_texture_presented','embedded_surface_frame_rendered']];lifecycle=[x for x in rows if x['event'] in ['embedded_surface_destroyed','embedded_pause','embedded_stop','embedded_configuration_changed']];summary={'app':options.app,'theme':options.theme,'transition':options.transition,'textureSamples':len(presented),'lastTextureReport':presented[-1] if presented else None,'lifecycle':lifecycle,'renderer':options.renderer,'profile':options.profile,'requestedCanvases':[x for x in rows if x['event']=='embedded_canvas_requested'],'actualVideoGeometry':[x for x in rows if x['event']=='embedded_video_geometry'],'display':int(display),'sourceProfile':('3024x1696/300, video1920/30fps/8Mbps' if options.profile=='wide' else ('3232x3248/600, video1920/60fps/8Mbps' if options.profile=='fast' else '3232x3248/600, video'+('2560' if options.profile=='sharp' else '1920')+'/30fps/8Mbps')),'previewProfile':str(hostW)+'x'+str(hostH)+'/600, desktop capture'+str(options.capture_size)+'/30fps','videoStarts':sum(x['event']=='embedded_video_geometry' for x in rows),'errors':[x for x in rows if x['event'] in ['embedded_error','embedded_decoder_error','embedded_touch_error','embedded_control_read_error']],'metricSamples':len(metrics),'medianDecodeFps':statistics.median(rates) if rates else None,'maximumFrameGapMs':max([x['maxGapMs'] for x in metrics],default=None),'touchSends':len(inputs),'maxQueueAndWriteMs':max([x.get('queueAndWriteMs',0) for x in inputs],default=None),'limits':'Decode output and control writes only; not end-to-end touch response or car fps.'}
 if summary['requestedCanvases']:
  canvas=summary['requestedCanvases'][-1];geometry=summary['actualVideoGeometry'][-1] if summary['actualVideoGeometry'] else None
  summary['sourceProfile']='actual canvas '+str(canvas['width'])+'x'+str(canvas['height'])+'/'+str(canvas['density'])+'; actual encoded '+(str(geometry['width'])+'x'+str(geometry['height']) if geometry else 'unknown')
 rendererModes=[x.get('renderer') for x in rows if x['event']=='embedded_renderer_selected']
 if not rendererModes or any(x!=options.renderer for x in rendererModes):raise RuntimeError('Renderer did not match requested path: '+str(rendererModes))
 expectedStarts=1 if options.keyboard_only or options.transition=='theme' else options.cycles
 geometries=summary['actualVideoGeometry'];presentedPerConnection=[]
 for i,geometry in enumerate(geometries):
  upper=geometries[i+1]['elapsedMs'] if i+1<len(geometries) else float('inf')
  presentedPerConnection.append(any(geometry['elapsedMs']<=x['elapsedMs']<upper for x in presented))
 summary['keyboardOnly']=options.keyboard_only;summary['traffic']=options.traffic;summary['requestedTrafficCycles']=options.cycles;summary['cycles']=0 if options.keyboard_only else options.cycles;summary['idleSeconds']=options.idle_seconds;summary['captureSize']=options.capture_size
 summary['presentationPerConnection']=presentedPerConnection
 summary['pipelineCheckPassed']=summary['videoStarts']==expectedStarts and not summary['errors'] and summary['touchSends']>=(4 if options.keyboard_only else (6 if options.traffic=='scroll' else 12)*options.cycles) and all(presentedPerConnection)
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True)
 (ROOT/'data/am-desktop-stress/latest.txt').write_text(str(OUT))
 if not summary['pipelineCheckPassed']:raise RuntimeError('画布/呈现/输入检查未全部通过，见summary.json')
finally:
 if p is not None:
  try:p.wait(timeout=40)
  except subprocess.TimeoutExpired:p.kill();p.wait()
  log.close()
  try:
   import sys
   sys.path.insert(0,'/tmp/am-video-tools')
   import imageio_ffmpeg
   for mark in captureMarks:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-ss',str(max(0,mark['seconds']-1)),'-i',str(OUT/'preview.mkv'),'-frames:v','1',str(OUT/('round-'+str(mark['round'])+'.png'))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  except Exception as error:print('Screenshot extraction failed: '+str(error),flush=True)
 adb('shell','touch',FILES+'phone-guardian-stop')
 if originalTheme is not None:adb('shell','cmd','uimode','night',originalTheme)
 if original is not None:adb('push',str(original),'/data/local/tmp/am-phone-supervisor.sh')
 print('Test stopped; evidence '+str(OUT),flush=True)
