#!/usr/bin/env python3
"""Read-only evidence index for retained NIO Link test captures."""
import json,re,collections,pathlib,datetime
ROOT=pathlib.Path(__file__).resolve().parent.parent
OUT=ROOT/'data/nio-development-20261011';OUT.mkdir(parents=True,exist_ok=True)
patterns={
 'auth_request':r'requestConnectAuthDevice', 'ble_connected':r'request ble connection success',
 'auth_init':r'getInitRequest', 'auth_exchange':r'getExchangeRequest',
 'tee_sign':r'purpose: SIGN', 'sign_success':r'keyOperation result 0',
 'auth_success':r'Security auth success',
 'link_state':r'setGlobalSettingInt key=(?:niolink_connect|near_by_connect_status)',
 'window_type':r'getVirtualDisplay mScreenType=',
 'activity_blocked':r'shouldAbortActivityStart.*(?:102|abort)|abortActivityStart.*102',
 'fatal':r'FATAL EXCEPTION|ANR in ',
 'drm_error':r'19623',
 'audio_route':r'nio_virtual_devices',
}
compiled={k:re.compile(v) for k,v in patterns.items()}
index=[]
for base in sorted((ROOT/'data/am-landscape').glob('AM-offline-20261009-*')):
 files=[p for p in base.rglob('*') if p.is_file()];summary={'capture':base.name,'files':len(files),'bytes':sum(p.stat().st_size for p in files),'markers':{},'evidenceCounts':{},'appEventCounts':{},'metrics':{},'displayGeometries':[]}
 for name in ['start.txt','connection-detected.txt','nio-link-disconnected.txt','done','errors.txt','runner.log']:
  p=base/name
  if p.exists():summary['markers'][name]=p.read_text(errors='replace')[:1500]
 counts=collections.Counter();events=collections.Counter();metrics=collections.defaultdict(list);geometry=set();dedup=set()
 date=base.name[11:19];start=base.name[-6:];date_iso=f'{date[:4]}-{date[4:6]}-{date[6:8]}'
 # App logs may contain previous sessions. Only count events from this capture's time window.
 stamp=lambda v:datetime.datetime.strptime(v,'%a %b %d %H:%M:%S CST %Y').isoformat()
 try:lower=stamp(summary['markers']['start.txt'].strip());upper=stamp(summary['markers']['done'].strip())
 except:lower=date_iso+'T'+start[:2]+':'+start[2:4]+':'+start[4:];upper=date_iso+'T23:59:59'
 with (OUT/(base.name+'-evidence.jsonl')).open('w') as output:
  for p in sorted(files):
   if p.suffix=='.jsonl':
    for n,line in enumerate(p.open(errors='replace'),1):
     try:r=json.loads(line)
     except:continue
     t=r.get('time','')[:19]
     if not lower<=t<=upper:continue
     identity=(r.get('session'),r.get('elapsedMs'),r.get('event'),line)
     if identity in dedup:continue
     dedup.add(identity);e=r.get('event','unknown');events[e]+=1
     for field in ['meanMs','maxMs','maxGapMs','intervalMs','queueAndWriteMs','frameAgeMs','ageMs','fps']:
      v=r.get(field)
      if isinstance(v,(int,float)):metrics[e+'.'+field].append(v)
     if e=='configuration':
      for d in r.get('displays',[]):geometry.add((d.get('id'),d.get('widthPx'),d.get('heightPx'),d.get('densityDpi'),d.get('rotation')))
     if e in ['music_entry_selected','uncaught_exception','embedded_touch_down','embedded_touch_sent','bridge_entry_state','embedded_stream_header','embedded_error']:
      safe={k:r[k] for k in ['event','time','displayId','target','width','height','frameWidth','frameHeight','sequence','queueAndWriteMs','frameAgeMs','heartbeatLive','guardianState'] if k in r}
      output.write(json.dumps({'kind':'app','source':str(p.relative_to(ROOT)),'line':n,'fields':safe},ensure_ascii=False)+'\n')
   elif 'system' in p.name or p.name.startswith('pre.log'):
    for n,line in enumerate(p.open(errors='replace'),1):
     for kind,pattern in compiled.items():
      if not pattern.search(line):continue
      counts[kind]+=1;entry={'kind':kind,'source':str(p.relative_to(ROOT)),'line':n,'time':line[:18]}
      if kind=='link_state':
       m=re.search(r'key=(\w+), value=(\d+)',line)
       if m:entry.update(key=m[1],value=int(m[2]))
      if kind=='window_type':
       m=re.search(r'mScreenType=(\d+), mWindowType=(\d+)',line)
       if m:entry.update(screenType=int(m[1]),windowType=int(m[2]))
      output.write(json.dumps(entry,ensure_ascii=False)+'\n')
 summary['evidenceCounts']=dict(counts);summary['appEventCounts']=dict(events)
 for k,v in metrics.items():
  v.sort();summary['metrics'][k]={'samples':len(v),'mean':round(sum(v)/len(v),2),'p50':v[len(v)//2],'p95':v[min(len(v)-1,int(len(v)*.95))],'max':v[-1]}
 summary['displayGeometries']=[dict(zip(['id','widthPx','heightPx','densityDpi','rotation'],g)) for g in sorted(geometry)]
 index.append(summary)
(OUT/'captures.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
print('Captures:',len(index),'Files:',sum(x['files'] for x in index),'Bytes:',sum(x['bytes'] for x in index))
for x in index:print(x['capture'],x['evidenceCounts'].get('auth_success',0),'auth-success log occurrences',len(x['metrics']),'metric groups')
