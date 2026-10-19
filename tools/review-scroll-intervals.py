#!/usr/bin/env python3
import pathlib,json,sys
p=pathlib.Path(sys.argv[1]);windows=json.loads((p/'gesture-windows.json').read_text());s=json.loads((p/'summary.json').read_text());sid=s['actualVideoGeometry'][-1]['session'];events=[json.loads(l) for l in (p/'events.jsonl').read_text().splitlines() if l.strip()];gaps=[e for e in events if e['session']==sid and e['event']=='embedded_long_frame_interval'];results=[]
for w in windows:
 inside=[e for e in gaps if w['startMs']+150<=e['elapsedMs']-e['outputGapMs'] and e['elapsedMs']<=w['endMs']]
 results.append({'round':w['round'],'gesture':w['gesture'],'durationMs':w['endMs']-w['startMs'],'longIntervalsDuringGesture':inside})
report={'scope':'injected swipe windows, requiring entire output interval inside gesture after first150ms; does not prove native content actually scrolls or car response time','gestures':results,'longIntervalCount':sum(len(x['longIntervalsDuringGesture']) for x in results)};(p/'scroll-interval-review.json').write_text(json.dumps(report,indent=2));print('Gestures',len(results),'long intervals',report['longIntervalCount'])
