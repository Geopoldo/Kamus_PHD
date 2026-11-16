"""Local human review overlay. Never modifies model outputs or triggers inference."""
import hashlib, io, json, os, threading, time, uuid, zipfile
from pathlib import Path
LOCK=threading.Lock()
def catalog(root):
 return json.loads((root/'progress.json').read_text())['documents']
def locate(root, ident, page):
 for doc in catalog(root):
  if hashlib.sha256(doc['source'].encode()).hexdigest()==ident:
   if not 1<=page<=doc['page_count']: raise ValueError('Invalid page')
   target=Path(doc['output']).resolve()
   if not target.is_relative_to((root/'documents').resolve()): raise ValueError('Invalid output')
   return doc,target/f'page_{page:04}'
 raise ValueError('Unknown document')
def key(doc): return hashlib.sha256(doc['source'].encode()).hexdigest()
def load(root, ident, page):
 doc,prefix=locate(root,ident,page)
 meta=json.loads(prefix.with_suffix('.json').read_text())
 original=prefix.with_suffix('.md').read_text() if prefix.with_suffix('.md').exists() else ''
 path=root/'reviews'/ident/f'{page}.json'
 review=json.loads(path.read_text()) if path.exists() else None
 digest=hashlib.sha256(original.encode()).hexdigest()
 return dict(original=original,original_hash=digest,review=review,metadata=meta,image=prefix.with_suffix('.png').exists(),stale=bool(review and review['original_hash']!=digest))
def index(root):
 result={}
 for p in (root/'reviews').glob('*/*.json'):
  r=json.loads(p.read_text())
  try:
   current=load(root,p.parent.name,int(p.stem))
   entry={k:r[k] for k in ('status','revision','updated')}
   if current['stale']:entry['status']='stale'
   result[p.parent.name+':'+p.stem]=entry
  except (ValueError,FileNotFoundError):continue
 return result

def save(root, data):
 ident,page=data['document'],int(data['page'])
 with LOCK:
  current=load(root,ident,page);old=current['review']
  if data.get('revision',0)!=(old or {}).get('revision',0) or data.get('original_hash')!=current['original_hash']: raise FileExistsError('Review changed; reopen before saving')
  if current['metadata']['status'] not in ('complete','needs_review'):raise ValueError('No successful transcription to review')
  if data.get('status') not in ('draft','deferred','validated'):raise ValueError('Invalid review status')
  if not isinstance(data.get('text'),str) or not str(data.get('reviewer','')).strip():raise ValueError('Text and reviewer required')
  if data['status']=='validated' and not data['text'].strip():raise ValueError('Empty validation')
  record={k:data[k] for k in ('text','reviewer','status','original_hash')}
  marks=data.get('annotations',[])
  if not isinstance(marks,list) or len(marks)>500:raise ValueError('Invalid annotations')
  encoded=data['text'].encode('utf-16-le')
  for mark in marks:
   if not isinstance(mark,dict) or type(mark.get('start')) is not int or type(mark.get('end')) is not int or not 0<=mark['start']<mark['end']<=len(encoded)//2:raise ValueError('Invalid annotation range')
   try:quote=encoded[mark['start']*2:mark['end']*2].decode('utf-16-le')
   except UnicodeError:raise ValueError('Invalid Unicode boundary')
   if mark.get('quote')!=quote or not isinstance(mark.get('note',''),str):raise ValueError('Annotation text mismatch')
  if data['status']=='validated' and marks:raise ValueError('Resolve open uncertainties before validation')
  record['annotations']=[dict(start=m['start'],end=m['end'],quote=m['quote'],note=m.get('note','')[:2000]) for m in marks]
  basis=data.get('basis','9b')
  if basis not in ('9b','27b_pilot_01','27b_all_flagged_01'):raise ValueError('Invalid reading basis')
  record['basis']=basis
  record['note']=str(data.get('note',''))[:10000]
  record.update(revision=(old or {}).get('revision',0)+1,updated=time.time(),document=ident,page=page)
  dest=root/'reviews'/ident;dest.mkdir(parents=True,exist_ok=True)
  payload=json.dumps(record,ensure_ascii=False,indent=2)
  # Immutable revision first, then atomic current pointer.
  history=dest/f'{page}.history';history.mkdir(exist_ok=True)
  with (history/f"{record['revision']}-{uuid.uuid4().hex}.json").open('x') as f:f.write(payload);f.flush();os.fsync(f.fileno())
  tmp=dest/f'{page}.tmp'
  with tmp.open('w') as f:f.write(payload);f.flush();os.fsync(f.fileno())
  tmp.replace(dest/f'{page}.json')
  return record

def bundle(root, ident):
 doc,prefix=locate(root,ident,1);stream=io.BytesIO()
 with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('manifest.json',json.dumps(doc,ensure_ascii=False,indent=2))
  z.write(root/'config.json','config.json')
  for p in prefix.parent.iterdir():
   if p.is_file() and p.suffix in ('.md','.json'):z.write(p,'model/'+p.name)
  directory=root/'reviews'/ident
  for p in directory.rglob('*.json') if directory.exists() else []:z.write(p,'human/'+str(p.relative_to(directory)))
 return stream.getvalue()
