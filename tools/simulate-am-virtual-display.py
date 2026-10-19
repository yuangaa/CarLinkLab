import subprocess,os,re,time,pathlib,shutil,argparse
root=pathlib.Path(__file__).resolve().parent.parent; adb=shutil.which('adb')
parser=argparse.ArgumentParser(description='独立虚拟屏模拟AM，不修改手机主屏；退出销毁虚拟屏。')
parser.add_argument('profile',choices=['phone','tablet','nio','all'])
selected=parser.parse_args().profile
if not adb: parser.error('adb unavailable')
for name,size in [('tablet','3024x1696/450'),('phone','3024x1696/600'),('nio','3232x3248/600')]:
 if selected not in ('all',name): continue
 out=root/'data/am-virtual-display'; out.mkdir(parents=True,exist_ok=True); log=open(out/(name+'.log'),'w'); env=dict(os.environ,ADB=adb)
 p=subprocess.Popen([str(root/'tmp/scrcpy/scrcpy-macos-aarch64-v5.0/scrcpy'),'--new-display='+size,'--start-app=+com.apple.android.music','--no-vd-system-decorations','--no-audio','--no-window','--time-limit=18','--record='+str(out/(name+'.mp4'))],stdout=log,stderr=log,env=env)
 try:
  for i in range(50):
   txt=(out/(name+'.log')).read_text(); m=re.search(r'New display:.*\(id=(\d+)\)',txt)
   if m: break
   time.sleep(.1)
  if not m:
   p.terminate(); p.wait(); raise RuntimeError('No virtual display created; see '+str(out/(name+'.log')))
  if m:
   d=m[1]
   for args in [('set-ignore-orientation-request','-d',d,'1'),('fixed-to-user-rotation','-d',d,'enabled'),('user-rotation','-d',d,'lock','0')]: subprocess.run([adb,'shell','wm',*args],check=True)
   time.sleep(3)
   (out/(name+'-activities.txt')).write_bytes(subprocess.check_output([adb,'shell','dumpsys','activity','activities']))
   print(name,'display',d,flush=True)
 finally:
  if p.poll() is None:
   try: p.wait(timeout=22)
   except subprocess.TimeoutExpired: p.terminate(); p.wait(timeout=5)
  log.close()
