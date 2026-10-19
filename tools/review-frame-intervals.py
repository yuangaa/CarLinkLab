#!/usr/bin/env python3
"""Compare decoded source timestamps with local output spacing."""
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);summary=json.loads((p/'summary.json').read_text());sid=summary['actualVideoGeometry'][-1]['session'];events=[json.loads(l) for l in (p/'events.jsonl').read_text().splitlines() if l.strip()];gaps=[e for e in events if e['session']==sid and e['event']=='embedded_long_frame_interval']
result=[]
for e in gaps:
 source=e['sourcePtsGapUs']/1000;excess=e['outputGapMs']-source
 result.append({'time':e['time'],'outputGapMs':e['outputGapMs'],'sourcePtsGapMs':source,'outputExcessMs':round(excess,3),'decodeMs':e['decodeMs'],'frameAgeMs':e['frameAgeUs']/1000,'pendingFrames':e['pendingFrames'],'observation':'output spacing mostly follows source timestamps' if source>0 and abs(excess)<=50 else 'requires pipeline investigation'})
report={'scope':'source timestamps are captured/encoded frame timestamps; sparse timestamps do not distinguish app redraw from capture/encoder delay','intervals':result,'count':len(result),'requiresInvestigation':sum(e['observation']=='requires pipeline investigation' for e in result)}
(p/'frame-interval-review.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
