"""Bundle 10 unique pages/model and compare reviewed recognition passages."""
import json,hashlib
from pathlib import Path
B=Path(__file__).resolve().parent.parent;P=B/'experiments/prompt_pilot_v1/pilot-20261114-v1';R=B/'experiments/prompt_pilot_v1/confirmation-20261114-v1';O=R/'quality'
MODELS=['qwen3.5-9b','qwen3.8-27b'];SAMPLES=['typed','handwritten']+[f'pdf_page_{i:02}' for i in range(1,9)]
records=json.loads((P/'quality/paired_results.json').read_text())['records']+json.loads((O/'paired_results.json').read_text())['records']
assert len(records)==40
bundles=[]
for model in MODELS:
 pages=[];md=[f'# Transcripciones literal_regions_v1 — {model}','']
 for sample in SAMPLES:
  source=P if sample in ['typed','handwritten','pdf_page_02'] else R
  path=source/'raw/literal_regions_v1'/model/(sample+'.txt');meta=source/'metadata/literal_regions_v1'/model/(sample+'.json');a=json.loads(meta.read_text());text=path.read_text()
  pages.append(dict(page_id=sample,transcription=text,source=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),metadata=a));md+=['## '+sample,'','```text',text,'```','']
  assert a['status']=='complete' and a['finish_reason']=='stop'
 out=R/'combined'/model;out.mkdir(parents=True,exist_ok=True);(out/'transcriptions.json').write_text(json.dumps(dict(model=model,variant='literal_regions_v1',pages=pages),indent=2,ensure_ascii=False)+'\n');(out/'transcriptions.md').write_text('\n'.join(md)+'\n');bundles.append(dict(model=model,pages=pages))

def agg(rs,layer='active'):
 out={}
 for key in ['word','character']:
  ps=[p for r in rs for p in r['passages'] if p.get('layer','active')==layer]
  c={k:sum(p[key][k] for p in ps) for k in ['H','S','D','I','N','M','errors']};c['rate_percent']=100*c['errors']/c['N'] if c['N'] else None;out[key]=c
 return out
summary=[]
for model in MODELS:
 for v in ['baseline_original','literal_regions_v1']:
  rs=[r for r in records if r['model']==model and r['variant']==v];additional=[r for r in rs if r['sample'] not in ['typed','handwritten','pdf_page_02']]
  summary.append(dict(model=model,variant=v,all_pages=agg(rs),confirmation_pages=agg(additional),deleted_recognition=agg(rs,'deleted')))
assert len({x['all_pages']['word']['N'] for x in summary})==1
# Exact code, reference and output fingerprints, preserving experiment input manifests.
for rec in records:
 assert hashlib.sha256(Path(rec['path']).read_bytes()).hexdigest()==rec['sha256']
 for p in rec['passages']:
  for key in ['word','character']:
   c=p[key];assert c['H']+c['S']+c['D']==c['N'];assert c['H']+c['S']+c['I']==c['M']
result=dict(summary=summary,records=records,scope='Fixed reviewed clear passages from all ten unique pages. Exclusions retained. Active and deleted recognition separate; ignores emitted state tags.',limitations=['Seven extra pages are additional evidence from same small known corpus, not blind representative test.','CER is literal physical text NFKC whitespace collapsed, case/punctuation preserved.','Some clear units excluded due difficult boundaries; all exclusions retained. No whole-page precision or hallucination coverage claim.','Spaced dotted initials normalized identically across all conditions; circled versus parenthesized list labels excluded in explicitly documented passages.','Historical baseline inference times; backend and model files reused, no repeated contemporaneous control.'])
(O/'all_pages_results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
md=['# Confirmación en todos los ejemplos','','Se completaron 20 transcripciones nuevas: 10 páginas únicas por modelo, reutilizando las seis del piloto y ejecutando 14 adicionales. Los archivos duplicados de uploads no se cuentan como muestras nuevas.','','## Reconocimiento en pasajes claros revisados','','La tabla compara las mismas regiones/pasajes contra Astra v2, sin penalizar reordenamientos de márgenes. Se excluyen dudas, los pasajes claros sin límites fiables y los textos auxiliares fuera del alcance. Las lecturas tachadas se puntúan aparte, y la etiqueta DEL emitida por el modelo no determina qué referencia es activa.','','| Modelo | Prompt | N total | Errores | WER total | CER físico | WER siete páginas adicionales |','|---|---|---:|---:|---:|---:|---:|']
for x in summary:
 w=x['all_pages']['word'];c=x['all_pages']['character'];ex=x['confirmation_pages']['word'];md.append(f"| {x['model']} | {x['variant']} | {w['N']} | {w['errors']} | {w['rate_percent']:.2f}% | {c['rate_percent']:.2f}% | {ex['rate_percent']:.2f}% |")
md+=['','## Por página','','| Modelo | Página | N activo | Errores original → nuevo | WER original → nuevo |','|---|---|---:|---:|---:|']
for model in MODELS:
 for sample in SAMPLES:
  rs=[next(r for r in records if r['model']==model and r['sample']==sample and r['variant']==v) for v in ['baseline_original','literal_regions_v1']];old,new=[agg([r])['word'] for r in rs];md.append(f"| {model} | {sample} | {old['N']} | {old['errors']} → {new['errors']} | {old['rate_percent']:.2f}% → {new['rate_percent']:.2f}% |")
md+=['','## Tiempo y recursos','','| Modelo | Total original (s) | Total nuevo (s) | Variación histórica | Mínimo VRAM libre ampliación |','|---|---:|---:|---:|---:|']
resources=[json.loads(x) for x in (R/'resource_monitor.jsonl').read_text().splitlines()]
for bundle in bundles:
 model=bundle['model'];new=sum(p['metadata']['seconds'] for p in bundle['pages']);old=sum(json.loads((B/('extended_results' if s.startswith('pdf') else 'results')/model/(s+'.json')).read_text())['seconds'] for s in SAMPLES);vram=min(x['vram_free_mib'] for x in resources if x['model']==model);md.append(f'| {model} | {old:.2f} | {new:.2f} | {100*(new/old-1):+.1f}% | {vram} MiB |')
md+=['','No se incluye la carga en estos tiempos. El control es histórico y sólo hay una ejecución por condición. Todos los intentos se conservaron; comprobar metadatos y logs para configuración y telemetría.','','## Límites','']+['- '+x for x in result['limitations']]+['','Las tablas son de reconocimiento en un subconjunto documentado, no exactitud absoluta de las páginas completas. El JSON conserva textos, offsets y exclusiones. La muestra adicional incluye una página casi vacía: no interpretar su WER aislado como peso equivalente a una página de contenido.']
(O/'all_pages_report.md').write_text('\n'.join(md)+'\n');print(json.dumps(summary,indent=2))
