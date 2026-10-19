#!/usr/bin/env python3
"""Separate active-input local decode observations from idle intervals."""
import pathlib,json,sys,statistics
p=pathlib.Path(sys.argv[1]);summary=json.loads((p/'summary.json').read_text());rows=[json.loads(l) for l in (p/'events.jsonl').read_text().splitlines() if l.strip()];session=summary['actualVideoGeometry'][-1]['session'];rows=[e for e in rows if e['session']==session]
inputs=[e['elapsedMs'] for e in rows if e['event']=='embedded_touch_down'];active=[];other=[]
for e in rows:
 if e['event']!='embedded_frame_metrics':continue
 end=e['elapsedMs'];start=end-e['intervalMs']
 if 900<=e['intervalMs']<=1400 and any(start-200<=t<=end for t in inputs):active.append(e)
 else:other.append(e)
rates=[e['frames']*1000/e['intervalMs'] for e in active]
result={'scope':'local decode samples overlapping touch-down; not continuous-animation benchmark or car transport fps','activeSampleCount':len(active),'activeMedianDecodeFps':statistics.median(rates) if rates else None,'activeMaxGapMs':max((e['maxGapMs'] for e in active),default=None),'excludedSampleCount':len(other),'excludedLongestGapMs':max((e['maxGapMs'] for e in other),default=None),'captureSize':summary.get('captureSize'),'errors':summary['errors']}
(p/'active-frame-review.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
