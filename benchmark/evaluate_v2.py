"""Score saved outputs against frozen v2. CPU only; reference never rewritten."""
import json,runpy,hashlib,re,collections
from pathlib import Path
R=Path(__file__).resolve().parent
B=runpy.run_path(str(R/'assistant_reference_v2/build.py'));B['verify']()
normalize=B['normalize']; ref=json.loads((R/'assistant_reference_v2/transcriptions.json').read_text());units=json.loads((R/'assistant_reference_v2/evaluation_units.json').read_text())
O=R/'evaluation_v2';O.mkdir(exist_ok=True)
def align(a,b):
 n,m=len(a),len(b);prev=list(range(m+1));trace=[bytearray([2]*(m+1))]
 for i,x in enumerate(a,1):
  cur=[i]+[0]*m;t=bytearray(m+1);t[0]=1
  for j,y in enumerate(b,1):
   v=(prev[j-1]+(x!=y),prev[j]+1,cur[j-1]+1);k=min(range(3),key=v.__getitem__);cur[j]=v[k];t[j]=k
  prev=cur;trace.append(t)
 out=[];i=n;j=m
 while i or j:
  k=trace[i][j] if i and j else (1 if i else 2)
  if k==0:out.append((i-1,j-1));i-=1;j-=1
  elif k==1:out.append((i-1,None));i-=1
  else:out.append((None,j-1));j-=1
 return out[::-1]
def distance(a,b):
 p=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  c=[i]
  for j,y in enumerate(b,1):c.append(min(p[j]+1,c[-1]+1,p[j-1]+(x!=y)))
  p=c
 return p[-1]
def model_tokens(t):
 # Join physical wrapped words before normalization, identically for all models.
 return normalize(re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','',t)).split()
page_lookup={}
for d in ref['documents']:
 for p in d['pages']:page_lookup[p['page_id']]=(d,p)
rows=[]
for path in sorted((R/'extended_results').glob('*/transcriptions.json')):
 data=json.loads(path.read_text());pages=[]
 for p in data['pages']:
  k=p['page_id'];pid=('typed_letter_1914.p01' if k=='typed' else 'handwritten_letter_1865.p01' if k=='handwritten' else 'british_system_notes.p'+k[-2:])
  if pid not in page_lookup:continue
  doc,page=page_lookup[pid];a=[];meta=[]
  for region in sorted(page['regions'],key=lambda x:x['reading_order']):
   for group in B['unit_groups'](region):
    segs=[s for l in group for s in B['active_segments'](l)]
    strict=bool(segs) and all(s['certainty']=='clear' for s in segs)
    text=B['joined_literal'](group)
    for tok in normalize(text).split():a.append(tok);meta.append(dict(strict=strict,kind=region['kind'],line_ids=[l['line_id'] for l in group]))
  b=model_tokens(p['transcription']);ops=align(a,b);counts=collections.Counter();bykind=collections.defaultdict(collections.Counter);edits=[]
  for z,(i,j) in enumerate(ops):
   if i is not None:
    if not meta[i]['strict']:continue
    kind=meta[i]['kind'];tag='D' if j is None else 'H' if a[i]==b[j] else 'S';charerr=len(a[i]) if j is None else distance(a[i],b[j]);chars=len(a[i])
   else:
    left=next((ii for ii,jj in reversed(ops[:z]) if ii is not None),None);right=next((ii for ii,jj in ops[z+1:] if ii is not None),None)
    # Boundary insertions only counted when all extant neighboring reference tokens are strict.
    near=[x for x in [left,right] if x is not None]
    if not near or not all(meta[x]['strict'] for x in near):counts['unscored_insertions']+=1;continue
    kind=meta[near[0]]['kind'];tag='I';charerr=len(b[j]);chars=0
   for c in [counts,bykind[kind]]:c[tag]+=1;c['character_errors']+=charerr;c['reference_characters']+=chars
   if tag!='H':edits.append(dict(operation=tag,reference=a[i] if i is not None else None,hypothesis=b[j] if j is not None else None,kind=kind,line_ids=meta[i]['line_ids'] if i is not None else []))
  def metrics(c):
   c=dict(c);n=sum(c.get(x,0) for x in ['H','S','D']);c['N']=n;c['wer_percent']=100*sum(c.get(x,0) for x in ['S','D','I'])/n if n else None;c['match_percent']=100*c.get('H',0)/n if n else None;c['token_character_error_percent']=100*c.get('character_errors',0)/c['reference_characters'] if c.get('reference_characters') else None;return c
  ents=[e for e in units['entities'] if e['page_id']==pid and e['strict_eligible']];hay=' '+' '.join(b)+' '
  entity_results=[dict(entity_id=e['entity_id'],type=e['type'],text=e['text'],present=(' '+normalize(e['text'])+' ') in hay) for e in ents]
  pages.append(dict(page_id=pid,document_id=doc['document_id'],reference_all_tokens=len(a),reference_strict_tokens=counts['H']+counts['S']+counts['D'],metrics=metrics(counts),by_region_kind={k:metrics(v) for k,v in bykind.items()},entity_presence=entity_results,edits=edits))
 total=collections.Counter()
 for p in pages:
  for k in ['H','S','D','I','character_errors','reference_characters','unscored_insertions']:total[k]+=p['metrics'].get(k,0)
 entities=[e for p in pages for e in p['entity_presence']]
 rows.append(dict(model=data['model'],input_path=str(path),input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),total=metrics(total),entity_mentions_present=sum(e['present'] for e in entities),entity_mentions_total=len(entities),pages=pages))
report=dict(reference_sha256=hashlib.sha256((R/'assistant_reference_v2/transcriptions.json').read_bytes()).hexdigest(),method='Global minimum word edit alignment per page in v2 region reading order; uncertain active units anchor alignment but are excluded from counts. Deleted segments excluded. Insertions beside uncertainty excluded. Fixed diagonal/delete/insert tie order.',limitations_es=['El orden de regiones de las salidas libres puede diferir: el WER incluye desplazamientos y no es una medida aislada de reconocimiento.','La alineación automática puede asignar mal pasajes muy divergentes; consultar edits por página. No es una adjudicación manual de regiones.','Los tramos dudosos se usan sólo como anclas tentativas; su longitud desconocida y su lectura pueden influir en la alineación.','La tasa de caracteres usa distancias dentro de operaciones de palabras y excluye espacios: NO es CER convencional global.','Presencia de entidades significa coincidencia normalizada en la página; no prueba ubicación, desambiguación ni precisión de entidades inventadas.','El texto añadido cerca de dudas queda sin puntuar; no se afirma cobertura total de alucinaciones.'],results=rows)
(O/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
md=['# Comparación exploratoria contra Astra v2','','Se reutilizan las 50 transcripciones guardadas; no se ejecutan modelos. Referencia fija verificada por SHA-256.','','El WER de esta tabla incluye diferencias de orden entre regiones. No debe usarse solo para elegir el mejor reconocedor. Las dudas activas se excluyen por unidad completa y los tachados se mantienen fuera del texto activo.','','| Modelo | Palabras ref. | Coincidencia | WER con orden | S | D | I | Entidades presentes |','|---|---:|---:|---:|---:|---:|---:|---:|']
for r in sorted(rows,key=lambda r:r['total']['wer_percent']):
 c=r['total'];md.append(f"| {r['model']} | {c['N']} | {c['match_percent']:.2f}% | {c['wer_percent']:.2f}% | {c.get('S',0)} | {c.get('D',0)} | {c.get('I',0)} | {r['entity_mentions_present']}/{r['entity_mentions_total']} |")
md+=['','## Por página','','| Modelo | Página | N | WER | Coincidencia |','|---|---|---:|---:|---:|']
for r in rows:
 for p in r['pages']:
  c=p['metrics'];md.append(f"| {r['model']} | {p['page_id']} | {c['N']} | {c['wer_percent']:.2f}% | {c['match_percent']:.2f}% |")
md+=['','## Límites de interpretación','']+['- '+s for s in report['limitations_es']]+['','## Próximo paso','','Para obtener WER/CER de reconocimiento independientes del orden, revisar y fijar la asignación de regiones en las salidas existentes, especialmente márgenes y membretes; después calcular CER convencional en esos mismos tramos. Los conteos por región del JSON son diagnósticos de la alineación global, no asignaciones verificadas.','', 'No se recalculan tiempos ni memoria: se conservan las mediciones de las ejecuciones originales.']
(O/'report.md').write_text('\n'.join(md)+'\n')
print('\n'.join(md[:15]))
assert len(rows)==5 and all(len(r['pages'])==10 for r in rows)
assert len({r['total']['N'] for r in rows})==1
B['verify']()
