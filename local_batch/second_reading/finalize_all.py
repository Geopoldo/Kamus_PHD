"""Finish the reproducibility report after the supervised run; no inference."""
import hashlib,json,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'results/second_reading/all_flagged_01'
while True:
 m=json.loads((ROOT/'manifest.json').read_text())
 if m['status']!='running':break
 time.sleep(10)
s=json.loads((ROOT/'summary.json').read_text());rows=s['results'];tele=[]
for line in (ROOT/'telemetry.jsonl').read_text().splitlines():
 try:tele.append(json.loads(line))
 except ValueError:pass
metrics=dict(status=s['status'],pages_available=len(rows),total_flagged_pages=len(m['samples']),reused_pages=sum('reused_from' in r for r in rows),newly_processed_pages=sum('reused_from' not in r for r in rows),run_inference_seconds=sum(r.get('run_inference_seconds',r['inference_seconds']) for r in rows),pages_with_output_alerts=sum(bool(r['flags']) for r in rows),accuracy_evaluated=False,baseline_integrity_verified=m.get('baseline_integrity_verified',False),elapsed_seconds=m.get('elapsed_seconds'))
if tele:metrics['resources']=dict(min_vram_free_mib=min(t['vram_free_mib'] for t in tele),max_temperature_c=max(t['temperature_c'] for t in tele),min_ram_available_gib=min(t['ram_available_gib'] for t in tele))
def write(name,value):
 path=ROOT/name;tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)
write('metrics.json',metrics)
lines=['# Segunda lectura de todas las páginas señaladas','', 'Estado: '+s['status'], '', 'Se conservan originales y todas las respuestas; ninguna lectura se valida automáticamente. Las regiones solapadas requieren comprobar fronteras y orden. No se ha medido exactitud contra una referencia humana.', '', '| Documento | Página | Procedimiento | Alertas | Segundos nuevos |','|---|---:|---|---|---:|']
for r in rows:lines.append('| '+r['document']+' | '+str(r['page'])+' | '+('Reutilizado del piloto' if 'reused_from' in r else 'Regiones solapadas')+' | '+(', '.join(r['flags']) or 'Sin alertas de salida; revisar unión si hay regiones')+' | '+str(round(r.get('run_inference_seconds',r['inference_seconds']),1))+' |')
lines+=['','```json',json.dumps(metrics,ensure_ascii=False,indent=2),'```'];(ROOT/'INFORME.md').write_text('\n'.join(lines)+'\n')
files={}
for p in ROOT.rglob('*'):
 if p.is_file() and p.name!='output_hashes.json' and not p.name.endswith('.tmp'):files[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
write('output_hashes.json',files);print(json.dumps(metrics),flush=True)
