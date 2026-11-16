"""Metadata only: incremental CSV and scale estimates; no transcription read."""
import csv,json,math,statistics,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'results'
def export():
 state=json.loads((ROOT/'progress.json').read_text());rows=[]
 for doc in state['documents']:
  for page in doc['pages']:
   if page['status']=='pending':continue
   usage=page.get('usage') or {};seconds=page.get('inference_seconds');tokens=usage.get('completion_tokens')
   rows.append(dict(folder=doc['folder'],document=doc['source'],pdf_page=page['number'],status=page['status'],render_seconds=page.get('render_seconds'),inference_seconds=seconds,wall_seconds=page.get('wall_seconds'),completion_tokens=tokens,tokens_per_second=tokens/seconds if tokens and seconds else None,characters=page.get('characters'),finish_reason=page.get('finish_reason'),flags=';'.join(page.get('flags',[])),attempts=len(page.get('attempts',[]))))
 if rows:
  temp=ROOT/'page_metrics.csv.tmp'
  with temp.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  temp.replace(ROOT/'page_metrics.csv')
 values=[r['wall_seconds'] for r in rows if r['status'] in ('complete','needs_review') and r['wall_seconds']]
 data=dict(updated=time.time(),summary=state['summary'],measured_pages=len(values),note='PDF pages, not logical scans; timings exclude human validation; estimates are extrapolations, not SLA')
 if values:
  avg=statistics.mean(values);data.update(page_wall_mean_seconds=avg,page_wall_median_seconds=statistics.median(values),page_wall_p95_seconds=sorted(values)[math.ceil(.95*len(values))-1],active_pages_per_hour=3600/avg)
  if len(values)>=20:data['remaining_estimate_seconds']=state['summary']['remaining']*avg
 raw=ROOT/'telemetry.jsonl'
 if raw.exists():
  samples=[]
  for line in raw.read_text().splitlines():
   try:samples.append(json.loads(line))
   except json.JSONDecodeError:pass
  if samples:data['resources']=dict(sample_count=len(samples),vram_used_peak_mib=max(s['vram_used_mib'] for s in samples),ram_available_min_gib=min(s['ram_available_gib'] for s in samples),gpu_util_mean_percent=statistics.mean(s['gpu_util_percent'] for s in samples))
 tmp=ROOT/'scale_metrics.json.tmp';tmp.write_text(json.dumps(data,indent=2));tmp.replace(ROOT/'scale_metrics.json');return data
if __name__=='__main__':print(json.dumps(export(),indent=2))
