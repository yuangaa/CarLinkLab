#!/usr/bin/env python3
"""Check local migration evidence; never asserts real NIO transport quality."""
import sys,json,pathlib,collections
p=pathlib.Path(sys.argv[1]);events=json.loads((p/'migration-events.json').read_text())
errors=[e for e in events if 'error' in e['event']]
fits=[e for e in events if e['event']=='embedded_fit_geometry']
checks=[]
for e in fits:
 error=abs(e['viewWidth']/e['viewHeight']-e['sourceWidth']/e['sourceHeight'])
 checks.append({'displayId':e['displayId'],'aspectError':error,'withinHost':e['viewWidth']<=e['hostWidth']+1 and e['viewHeight']<=e['hostHeight']+1})
touch_results=[]
for e in events:
 if e['event']=='embedded_touch_sent':
  later=[x for x in events if x['event'] in ('embedded_surface_frame_rendered','embedded_texture_presented') and 0<x['elapsedMs']-e['elapsedMs']<2000]
  touch_results.append({'sequence':e['sequence'],'presentationCallbackWithin2s':bool(later),'queueAndWriteMs':e['queueAndWriteMs']})
result={'scope':'owned virtual display migration; callbacks do not prove physical car latency or correct target action','errors':errors,'fitChecks':checks,'touchResults':touch_results,'screenshots':[str(x) for x in sorted(p.glob('round-*.png'))]}
result['geometryAndCallbackChecksPass']=bool(checks) and not errors and all(x['aspectError']<.002 and x['withinHost'] for x in checks) and len(touch_results)==3 and all(x['presentationCallbackWithin2s'] for x in touch_results)
(p/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
