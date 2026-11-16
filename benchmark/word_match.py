import json,re,unicodedata
from pathlib import Path
R=Path(__file__).resolve().parent
ref=json.loads((R/'assistant_reference/transcriptions.json').read_text())
def normalize(s):
 s=unicodedata.normalize('NFKC',s)
 s=re.sub(r'(?<=\w)-\s*\n\s*(?=\w)','',s)
 s=s.replace("'",'').replace('’','')
 s=re.sub(r'\.{2,}', '.',s)
 s=re.sub(r'\b(?:[A-Za-z]\.[ \t]*)+[A-Za-z]\.?(?=\s|$|[,;:])',lambda m:re.sub('[^a-z]','',m.group().lower()),s)
 return re.findall(r'[a-z0-9]+',s.lower())
def align(a,b):
 # Tuples: edit cost, negative matches, substitutions, deletions, insertions.
 prev=[(j,0,0,0,j) for j in range(len(b)+1)]
 for i,x in enumerate(a,1):
  cur=[(i,0,0,i,0)]
  for j,y in enumerate(b,1):
   c,h,s,d,k=prev[j-1];diag=(c+(x!=y),h-(x==y),s+(x!=y),d,k)
   c,h,s,d,k=prev[j];delete=(c+1,h,s,d+1,k)
   c,h,s,d,k=cur[-1];insert=(c+1,h,s,d,k+1)
   cur.append(min(diag,delete,insert))
  prev=cur
 _,h,s,d,i=prev[-1];return dict(H=-h,S=s,D=d,I=i,N=len(a),M=len(b))
def metrics(c):
 h,s,d,i,n,m=[c[k] for k in ['H','S','D','I','N','M']]
 return c|dict(match_percent=100*h/n,wer_percent=100*(s+d+i)/n,f1_percent=200*h/(n+m))
targets={'typed':ref['documents'][0]['comparison_body_text']}
# Main text on PDF 5 and 7 has no tentative readings; preserve numbers here.
for i in [5,7]:targets[f'pdf_page_{i:02}']=ref['documents'][2]['pages'][i-1]['transcription']
rows=[]
for p in (R/'extended_results').glob('*/transcriptions.json'):
 model=json.loads(p.read_text());pages=[]
 for page in model['pages']:
  key=page['page_id']
  if key not in targets:continue
  text=page['transcription']
  if key=='typed':
   text=text[text.lower().index('my dear'):];end=text.lower().rfind('candidacy');text=text[:end+len('candidacy')]
  pages.append({'page_id':key}|metrics(align(normalize(targets[key]),normalize(text))))
 total={k:sum(x[k] for x in pages) for k in ['H','S','D','I','N','M']}
 rows.append({'model':model['model'],'pages':pages,'total':metrics(total)})
rows.sort(key=lambda x:x['total']['wer_percent'])
report={'reference':'Astra Ultra, fixed user-selected reference','scope':'Typewritten body (341 old-normalization words), PDF pages 5 and 7. Other pages excluded from aggregate because of uncertain readings/editorial annotations and complex layout. No whole-ten-page accuracy claimed.','normalization':'Unicode NFKC, lowercase, punctuation/apostrophe removal, abbreviation equivalence, dehyphenation. Numbers included. No fuzzy spelling. Page numbers absent from Astra transcription count as insertions; numerical list labels retained.','alignment':'Minimum Levenshtein word edits; ties maximize exact matches. Micro-aggregated counts across pages.','results':rows}
(R/'extended_results/word_match.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
md=['# Coincidencia matemática contra Astra Ultra','','Referencia fija: Astra Ultra. Se evalúan el cuerpo mecanografiado y las páginas PDF 5 y 7. Las otras páginas quedan fuera del agregado por contener lecturas dudosas o anotaciones editoriales. No representa exactitud de las diez páginas.','','Se incluyen cifras; se normalizan mayúsculas, puntuación, abreviaturas y palabras divididas con guion. Se conserva el orden y las repeticiones. H = coincidencias; S = sustituciones; D = omisiones; I = añadidos.','','| Modelo | H | S | D | I | N | Coincidencia | WER | F1 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for x in rows:
 c=x['total'];md.append(f"| {x['model']} | {c['H']} | {c['S']} | {c['D']} | {c['I']} | {c['N']} | {c['match_percent']:.2f}% | {c['wer_percent']:.2f}% | {c['f1_percent']:.2f}% |")
md+=['','Estas métricas difieren de las anteriores porque ahora incluyen cifras, conservan marcadores numéricos y suman el cuerpo mecanografiado. Los números de página que el modelo añade y Astra no transcribió cuentan como inserciones; se pueden inspeccionar por página en el JSON.','', 'Coincidencia = H/N. WER = (S+D+I)/N. F1 = 2H/(N+M). Los totales suman conteos; no promedian porcentajes.']
(R/'extended_results/word_match.md').write_text('\n'.join(md)+'\n')
print(json.dumps([{'model':x['model'],**x['total']} for x in rows],indent=2))
