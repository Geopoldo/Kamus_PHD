"""Local rules-based audit of saved model output. No inference; no originals changed."""
import argparse,collections,hashlib,json,os,platform,re,shutil,sys,time
from pathlib import Path
VERSION='output-audit-v1'
RULES={
 'missing_artifact':dict(severity='high',description='A saved model output file is missing or unreadable'),
 'invalid_response':dict(severity='high',description='Response JSON lacks a valid completion'),
 'empty_output':dict(severity='high',description='No transcription text'),
 'explicit_refusal':dict(severity='high',description='Opening text explicitly declines or says it cannot transcribe'),
 'explanatory_response':dict(severity='medium',description='Opening text discusses image quality/transcribing instead of a transcription'),
 'truncated_output':dict(severity='high',description='Completion did not finish normally'),
 'repeated_lines':dict(severity='medium',description='More than 8 lines and fewer than 60 percent distinct nonempty lines'),
 'repetitive_words':dict(severity='medium',description='Over 100 words and fewer than 15 percent distinct words'),
 'repeated_phrase':dict(severity='medium',description='A repeated sequence of 8 words occupies at least 30 percent of the output'),
 'short_output':dict(severity='low',description='Under 12 words; advisory only, may be a legitimate title or blank page'),
 'output_mismatch':dict(severity='high',description='Saved Markdown differs from the original model response')}
REFUSAL=re.compile(r"(?:\b(?:i|we)\s+(?:(?:am|are)\s+)?(?:cannot|can't|can not|am unable to|are unable to)|\b(?:impossible|unable) to (?:accurately |reliably )?(?:transcribe|read)|\b(?:cannot|can't) (?:be |reliably |accurately )*(?:read|transcribed)|\bno puedo (?:leer|transcribir)|\bje ne peux pas (?:lire|transcrire))",re.I)
EXPLAIN=re.compile(r"(?:\b(?:image|characters|text)\b.{0,100}\b(?:low resolution|distorted|too blurred|fragmented|illegible|unreadable)\b|\b(?:please provide|upload a clearer|higher.resolution image)\b)",re.I|re.S)
def digest(b):return hashlib.sha256(b).hexdigest()
def inspect(text,response):
 findings=[]
 def add(rule,**evidence):findings.append(dict(rule=rule,severity=RULES[rule]['severity'],evidence=evidence))
 if not isinstance(response,dict):add('invalid_response');response={}
 choices=response.get('choices') or []
 if not choices or not isinstance(choices[0],dict):add('invalid_response');choice={}
 else:choice=choices[0]
 raw=(choice.get('message') or {}).get('content')
 if isinstance(raw,str) and raw!=text:add('output_mismatch',markdown_sha256=digest(text.encode()),response_text_sha256=digest(raw.encode()))
 if not text.strip():add('empty_output')
 opening=text[:500]
 refusal=REFUSAL.search(opening);explain=EXPLAIN.search(opening)
 if refusal:add('explicit_refusal',start=refusal.start(),end=refusal.end(),scope='first_500_characters')
 elif explain:add('explanatory_response',start=explain.start(),end=explain.end(),scope='first_500_characters')
 if choice.get('finish_reason')!='stop':add('truncated_output',finish_reason=choice.get('finish_reason'))
 lines=[x.strip() for x in text.splitlines() if x.strip()];words=text.split()
 if len(lines)>8 and len(set(lines))/len(lines)<.6:add('repeated_lines',lines=len(lines),distinct_lines=len(set(lines)))
 if len(words)>100 and len(set(words))/len(words)<.15:add('repetitive_words',words=len(words),distinct_words=len(set(words)))
 if len(words)>100:
  grams=collections.Counter(tuple(words[i:i+8]) for i in range(len(words)-7));count=max(grams.values(),default=0)
  if count>=5 and count*8/len(words)>=.3:add('repeated_phrase',ngram_words=8,repetitions=count,output_words=len(words))
 if text.strip() and len(words)<12 and not refusal:add('short_output',words=len(words),advisory=True)
 classification='not_transcribed' if any(x['rule'] in ('empty_output','explicit_refusal') for x in findings) else 'possibly_incomplete' if findings else 'candidate'
 return dict(classification=classification,findings=findings,characters=len(text),words=len(words),finish_reason=choice.get('finish_reason'),human_validated=False)
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
 tmp.replace(path)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'results');ap.add_argument('--run-id',default=time.strftime('%Y%m%d-%H%M%S'));args=ap.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run_id):raise ValueError('Invalid run ID')
 root=args.root.resolve();out=root/'audits'/args.run_id
 out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,out/'auditor.py');snapshot=(root/'progress.json').read_bytes();state=json.loads(snapshot);(out/'inventory_snapshot.json').write_bytes(snapshot)
 manifest=dict(run_id=args.run_id,status='running',version=VERSION,started=time.time(),rules=RULES,code_sha256=digest(Path(__file__).read_bytes()),inventory_sha256=digest(snapshot),python=sys.version,platform=platform.platform(),scope='Saved first-pass model outputs; no image-content analysis or reference comparison; no accuracy score',documents=len(state['documents']),total_pages=sum(len(d['pages']) for d in state['documents']),processed=0,flagged=0,counts={},folders={},current=None,errors=0)
 write(out/'manifest.json',manifest);write(root/'audit_latest.json',dict(run_id=args.run_id));records=[];start=time.monotonic()
 def save_manifest():manifest['updated']=time.time();write(out/'manifest.json',manifest)
 try:
  for d in state['documents']:
   target=Path(d['output']).resolve()
   if not target.is_relative_to((root/'documents').resolve()):raise ValueError('Unsafe inventory path')
   folder=manifest['folders'].setdefault(d['folder'],dict(total=sum(len(x['pages']) for x in state['documents'] if x['folder']==d['folder']),processed=0,flagged=0))
   for page in d['pages']:
    number=page['number'];prefix=target/f'page_{number:04}';manifest['current']=dict(document=d['source'],page=number)
    record=dict(document=d['source'],document_id=digest(d['source'].encode()),folder=d['folder'],page=number,version=VERSION,run_id=args.run_id,audited_at=time.time(),baseline_flags=page.get('flags',[]),hashes={});t=time.monotonic()
    try:
     for suffix in ('.md','.response.json','.json'):
      data=prefix.with_suffix(suffix).read_bytes();record['hashes'][suffix]=digest(data)
     text=prefix.with_suffix('.md').read_text();response=json.loads(prefix.with_suffix('.response.json').read_text());record.update(inspect(text,response))
     # Check hashes after inspection to identify concurrent source changes.
     if any(digest(prefix.with_suffix(s).read_bytes())!=h for s,h in record['hashes'].items()):raise RuntimeError('Input changed during audit')
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:
     record.update(classification='technical_failure',findings=[dict(rule='missing_artifact',severity='high',evidence=dict(error_type=type(e).__name__))],human_validated=False);manifest['errors']+=1
    record['seconds']=time.monotonic()-t;records.append(record);write(out/'pages'/record['document_id']/f'{number}.json',record)
    with (out/'events.jsonl').open('a') as f:f.write(json.dumps(dict(event='page_audited',document=record['document'],page=number,classification=record['classification'],rules=[x['rule'] for x in record['findings']],time=time.time()))+'\n');f.flush();os.fsync(f.fileno())
    manifest['processed']+=1;folder['processed']+=1;manifest['flagged']+=bool(record['findings']);folder['flagged']+=bool(record['findings']);manifest['counts'][record['classification']]=manifest['counts'].get(record['classification'],0)+1;save_manifest()
  manifest['status']='complete'
 except BaseException as e:manifest.update(status='failed',error_type=type(e).__name__);raise
 finally:
  manifest.update(finished=time.time(),elapsed_seconds=time.monotonic()-start,current=None);save_manifest();write(out/'findings.json',[r for r in records if r['findings']]);write(out/'all_pages.json',records)
  text=['# Auditoría local de salidas guardadas','','No mide exactitud ni compara con imágenes. Las reglas y evidencias son indicios para revisar. Los originales no se modifican.','','```json',json.dumps(manifest,ensure_ascii=False,indent=2),'```'];(out/'INFORME.md').write_text('\n'.join(text)+'\n');print(json.dumps({k:manifest[k] for k in ('run_id','status','processed','flagged','counts','elapsed_seconds')}))
if __name__=='__main__':main()
