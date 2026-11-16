"""Sequential confidential 27B pilot. Independent immutable outputs; no originals replaced."""
import shutil
from PIL import Image
import argparse,base64,collections,difflib,fcntl,hashlib,json,os,runpy,signal,socket,subprocess,threading,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parent;OUT=ROOT/'results'/'second_reading'/'all_flagged_01'
OLD=runpy.run_path(str(PROJECT/'benchmark/run_qwen.py'))
PROMPT='''Transcribe only the visible text in this scanned historical page, in reading order. Preserve spelling, names, dates, paragraphs and page numbers. Copy each visible line once: do not repeat a passage or continue beyond the image. Do not summarize, translate, infer missing wording, or repair the document. If a word cannot be read, write [illegible]. Return only the transcription.'''
SELECTION=[('Kesa_Control/P0000275.pdf',18,'truncation_and_repetition'),('Kesa_Control/P0003014.pdf',98,'repeated_lines_only'),('Kesa_Control/P0015173.pdf',1,'different_document')]
stop=threading.Event();guard=[];process=None;stage='preflight';current=None;began=time.monotonic()
def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
 tmp.replace(path)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def resources():
 vals=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,memory.used,utilization.gpu,temperature.gpu,power.draw','--format=csv,noheader,nounits'],text=True,timeout=6).strip().splitlines()[0].split(',')
 return dict(time=time.time(),ram_available_gib=OLD['memory_available_gib'](),vram_free_mib=float(vals[0]),vram_used_mib=float(vals[1]),gpu_util_percent=float(vals[2]),temperature_c=float(vals[3]),power_watts=float(vals[4]))
def request(path,payload=None,timeout=5):
 req=urllib.request.Request('http://127.0.0.1:18765'+path,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def flags(text,finish):
 lines=[x.strip() for x in text.splitlines() if x.strip()];words=text.split();f=[]
 if finish!='stop':f.append('truncated_or_nonstop')
 if not text.strip():f.append('empty_output')
 if len(lines)>8 and len(set(lines))/len(lines)<.6:f.append('repeated_lines')
 if len(words)>100 and len(set(words))/len(words)<.15:f.append('repetitive_output')
 return f

def monitor():
 while not stop.is_set():
  try:
   r=resources();r.update(stage=stage,current=current)
   with (OUT/'telemetry.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
   write(OUT/'live.json',dict(stage=stage,current=current,resources=r,updated=time.time()))
   if r['ram_available_gib']<4 or r['vram_free_mib']<1024 or r['temperature_c']>=88:raise RuntimeError('Memory/temperature reserve crossed')
   if time.monotonic()-began>14000:raise TimeoutError('Pilot total time limit')
  except Exception as e:
   guard.append(str(e))
   if process and process.poll() is None:process.terminate()
   return
  stop.wait(3)
def main():
 global process,stage,current
 lock=(PROJECT/'benchmark/prompt_trial/execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if OUT.exists():raise RuntimeError('Pilot output already exists; refusing overwrite')
 pre=resources()
 policy_path=ROOT/'inference_policy.json'
 policy=json.loads(policy_path.read_text()) if policy_path.exists() else {}
 gpu_only=policy.get('allow_cpu_model_layers') is False
 if gpu_only:
  folder=PROJECT/'benchmark/models/Qwen3.8-27B-GGUF'
  required=sum(f.stat().st_size for f in folder.glob('*.gguf'))/(1024*1024)+policy.get('minimum_vram_reserve_mib',1536)
  if required>pre['vram_free_mib']:raise RuntimeError('GPU-only policy: 27B weights/projector plus reserve exceed free VRAM; CPU offload forbidden')
 if pre['ram_available_gib']<12 or pre['vram_free_mib']<14000:raise RuntimeError('Preflight memory reserve unavailable')
 if subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip():raise RuntimeError('Foreign GPU workload present')
 with socket.socket() as sock:
  if sock.connect_ex(('127.0.0.1',18765))==0:raise RuntimeError('Inference port occupied')
 state=json.loads((ROOT/'results/progress.json').read_text());samples=[];inputs={}
 selection=[(d['source'],p['number'],'flagged_mass_processing') for d in state['documents'] for p in d['pages'] if p['status']=='needs_review']
 import sys
 sys.path.insert(0,str(ROOT))
 import issues
 existing={(source,n) for source,n,reason in selection}
 for report in issues.index(ROOT/'results').values():
  pair=(report['source'],report['page'])
  if report['status']=='open' and pair not in existing:selection.append((*pair,'user_report'));existing.add(pair)
 pointer=ROOT/'results/audit_latest.json'
 if pointer.exists():
  audit_id=json.loads(pointer.read_text())['run_id']
  findings_path=ROOT/'results/audits'/audit_id/'findings.json'
  if findings_path.exists():
   for finding in json.loads(findings_path.read_text()):
    pair=(finding['document'],finding['page'])
    if any(f['severity'] in ('high','medium') for f in finding['findings']) and pair not in existing:selection.append((*pair,'output_audit:'+audit_id));existing.add(pair)
 pilot=ROOT/'results/second_reading/pilot_01'
 prior=json.loads((pilot/'summary.json').read_text())['results']
 for source,n,reason in selection:
  d=next(d for d in state['documents'] if d['source']==source);p=next(p for p in d['pages'] if p['number']==n);prefix=Path(d['output'])/f'page_{n:04}'
  if p['status']=='pending':raise ValueError('Page not processed yet')
  sample=dict(document=source,document_id=hashlib.sha256(source.encode()).hexdigest(),page=n,reason=reason,prefix=str(prefix),baseline=p)
  samples.append(sample)
  for suffix in ['.png','.md','.json','.response.json']:inputs[str(prefix.with_suffix(suffix))]=sha(prefix.with_suffix(suffix))
 model=PROJECT/'benchmark/models/Qwen3.8-27B-GGUF'
 cmd=[OLD['SERVER'],'-m',str(model/'Qwen3.8-27B-Q4_K_M.gguf'),'--mmproj',str(model/'mmproj-Qwen3.8-27B-BF16.gguf'),'--host','127.0.0.1','--port','18765','-ngl','all' if gpu_only else '48','-c','8192','-np','1','-t','8','--image-max-tokens','2048','--jinja','--chat-template-kwargs','{"enable_thinking":false}','--no-webui']
 manifest=dict(status='running',started=time.time(),model='Qwen3.8-27B Q4_K_M',prompt=PROMPT,command=cmd,samples=samples,input_hashes=inputs,preflight=pre,policy='Reuse 2 unflagged pilot readings; reprocess other 13 pages in overlapping horizontal regions (55 percent each). No automatic acceptance.')
 write(OUT/'manifest.json',manifest);results=[];watcher=None
 try:
  stage='loading_model'
  with (OUT/'server.log').open('w') as log:process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
  watcher=threading.Thread(target=monitor,daemon=True);watcher.start();loaded=time.monotonic()
  while True:
   if guard or process.poll() is not None:raise RuntimeError('Server stopped '+str(guard))
   if time.monotonic()-loaded>300:raise TimeoutError('Model loading timeout')
   try:
    if request('/health').get('status')=='ok':break
   except OSError:pass
   time.sleep(1)
  manifest['load_seconds']=time.monotonic()-loaded;write(OUT/'manifest.json',manifest)
  for i,s in enumerate(samples):
   current=dict(document=s['document'],page=s['page']);stage='transcribing';r=resources()
   if r['ram_available_gib']<6 or r['vram_free_mib']<1500:raise RuntimeError('Pre-inference reserve unavailable')
   print(json.dumps(dict(event='page_started',**current)),flush=True)
   target=OUT/f'case_{i+1:02}';target.mkdir();prefix=Path(s['prefix']);start=time.monotonic()
   previous=next((x for x in prior if x['document']==s['document'] and x['page']==s['page'] and not x['flags']),None)
   if previous:
    shutil.copytree(pilot/previous['case'],target,dirs_exist_ok=True)
    meta=dict(previous,case=target.name,reused_from='pilot_01/'+previous['case'],run_inference_seconds=0)
    write(target/'metadata.json',meta);results.append(meta);write(OUT/'summary.json',dict(status='running',results=results));continue
   parts=[];region_meta=[];failures=[]
   image=Image.open(prefix.with_suffix('.png'));w,h=image.size
   def region(y0,y1,name,depth=0):
    global current
    current=dict(document=s['document'],page=s['page'],region=name)
    r=resources()
    if guard or process.poll() is not None:raise RuntimeError('Inference engine stopped '+str(guard))
    if r['ram_available_gib']<6 or r['vram_free_mib']<1500:raise RuntimeError('Region memory reserve unavailable')
    path=target/(name+'.png');image.crop((0,y0,w,y1)).save(path)
    prompt=PROMPT+' This image is one region of a larger page. Transcribe only this region; do not infer text beyond its edges.'
    payload=dict(model='qwen3.8-27b',messages=[dict(role='user',content=[dict(type='text',text=prompt),dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()))])],temperature=0,seed=42,max_tokens=4096,stream=False,cache_prompt=False)
    t=time.monotonic()
    try:
     response=request('/v1/chat/completions',payload,timeout=600);write(target/(name+'.response.json'),response)
     choice=response['choices'][0];text=choice['message'].get('content') or '';(target/(name+'.md')).write_text(text)
     f=flags(text,choice.get('finish_reason'));region_meta.append(dict(region=name,bounds=[0,y0,w,y1],png_sha256=sha(path),prompt=prompt,seconds=time.monotonic()-t,flags=f,usage=response.get('usage'),finish_reason=choice.get('finish_reason')))
     write(target/'regions.json',region_meta)
     if 'truncated_or_nonstop' in f and depth<1:
      mid=(y0+y1)//2;overlap=max(1,int((y1-y0)*.05));return region(y0,mid+overlap,name+'a',depth+1)+region(mid-overlap,y1,name+'b',depth+1)
     return [dict(text=text,flags=f,region=name)]
    except (OSError,TimeoutError,KeyError,ValueError) as e:
     failures.append(dict(region=name,error=str(e),seconds=time.monotonic()-t));write(target/'failures.json',failures)
     if guard or process.poll() is not None:raise
     return [dict(text='',flags=['technical_failure'],region=name)]
   parts=region(0,int(h*.55),'upper')+region(int(h*.45),h,'lower')
   # Preserve uncertain overlaps; only identical, complete lines are deduplicated.
   lines=[]
   for part in parts:
    new=part['text'].splitlines();overlap=0
    for count in range(1,min(len(lines),len(new),60)+1):
     if lines[-count:]==new[:count]:overlap=count
    lines+=new[overlap:]
   text='\n'.join(lines);(target/'transcription.md').write_text(text)
   base=prefix.with_suffix('.md').read_text();(target/'comparison.diff').write_text(''.join(difflib.unified_diff(base.splitlines(True),text.splitlines(True),fromfile='9B_original',tofile='27B_regions')))
   f=sorted(set(x for part in parts for x in part['flags']))
   meta=dict(document=s['document'],document_id=s['document_id'],page=s['page'],case=target.name,status='needs_human_review',flags=f,assembly_flags=['overlapping_regions_require_human_check'],finish_reason='regions',inference_seconds=sum(x['seconds'] for x in region_meta),run_inference_seconds=time.monotonic()-start,baseline_seconds=s['baseline'].get('inference_seconds'),baseline_flags=s['baseline'].get('flags'),characters=len(text),baseline_characters=len(base),regions=region_meta,failures=failures,accuracy_evaluated=False)
   write(target/'metadata.json',meta);results.append(meta);write(OUT/'summary.json',dict(status='running',results=results));print(json.dumps(dict(event='page_saved',document=meta['document'],page=meta['page'],flags=f)),flush=True)
  for path,digest in inputs.items():
   if sha(path)!=digest:raise RuntimeError('Baseline input modified')
  manifest['status']='complete';manifest['finished']=time.time();manifest['baseline_integrity_verified']=True
 except BaseException as e:
  manifest.update(status='failed',error=str(e),finished=time.time());raise
 finally:
  stage=manifest['status'];
  if process and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=15)
   except subprocess.TimeoutExpired:process.kill();process.wait()
  stop.set()
  if watcher:watcher.join(timeout=8)
  manifest['elapsed_seconds']=time.monotonic()-began;manifest['guard']=guard;write(OUT/'manifest.json',manifest);write(OUT/'summary.json',dict(status=manifest['status'],results=results,accuracy_evaluated=False))
  write(OUT/'live.json',dict(stage=stage,current=None,updated=time.time()))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run-id',default='all_flagged_01');args=ap.parse_args()
 if not __import__('re').fullmatch(r'[A-Za-z0-9_-]+',args.run_id):raise ValueError('Invalid run ID')
 OUT=ROOT/'results'/'second_reading'/args.run_id
 def signal_exit(signum,frame):raise SystemExit('Signal '+str(signum))
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,signal_exit)
 main()
