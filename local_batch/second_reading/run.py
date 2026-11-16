"""Sequential confidential 27B pilot. Independent immutable outputs; no originals replaced."""
import argparse,base64,collections,difflib,fcntl,hashlib,json,os,runpy,signal,socket,subprocess,threading,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parent;OUT=ROOT/'results'/'second_reading'/'pilot_01'
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
   if time.monotonic()-began>2100:raise TimeoutError('Pilot total time limit')
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
 for source,n,reason in SELECTION:
  d=next(d for d in state['documents'] if d['source']==source);p=next(p for p in d['pages'] if p['number']==n);prefix=Path(d['output'])/f'page_{n:04}'
  if p['status']!='needs_review':raise ValueError('Pilot must use flagged pages')
  sample=dict(document=source,document_id=hashlib.sha256(source.encode()).hexdigest(),page=n,reason=reason,prefix=str(prefix),baseline=p)
  samples.append(sample)
  for suffix in ['.png','.md','.json','.response.json']:inputs[str(prefix.with_suffix(suffix))]=sha(prefix.with_suffix(suffix))
 model=PROJECT/'benchmark/models/Qwen3.8-27B-GGUF'
 cmd=[OLD['SERVER'],'-m',str(model/'Qwen3.8-27B-Q4_K_M.gguf'),'--mmproj',str(model/'mmproj-Qwen3.8-27B-BF16.gguf'),'--host','127.0.0.1','--port','18765','-ngl','all' if gpu_only else '48','-c','8192','-np','1','-t','8','--image-max-tokens','4096','--jinja','--chat-template-kwargs','{"enable_thinking":false}','--no-webui']
 manifest=dict(status='running',started=time.time(),model='Qwen3.8-27B Q4_K_M',prompt=PROMPT,command=cmd,samples=samples,input_hashes=inputs,preflight=pre,policy='whole PDF page; single local model; independent second reading; no automatic acceptance')
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
   payload=dict(model='qwen3.8-27b',messages=[dict(role='user',content=[dict(type='text',text=PROMPT),dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(prefix.with_suffix('.png').read_bytes()).decode()))])],temperature=0,seed=42,max_tokens=4096,stream=False,cache_prompt=False)
   response=request('/v1/chat/completions',payload,timeout=600);write(target/'response.json',response)
   choice=response['choices'][0];text=choice['message'].get('content') or '';(target/'transcription.md').write_text(text);f=flags(text,choice.get('finish_reason'));base=prefix.with_suffix('.md').read_text()
   (target/'comparison.diff').write_text(''.join(difflib.unified_diff(base.splitlines(True),text.splitlines(True),fromfile='9B_original',tofile='27B_second_reading')))
   meta=dict(document=s['document'],document_id=s['document_id'],page=s['page'],case=target.name,status='needs_human_review',flags=f,finish_reason=choice.get('finish_reason'),inference_seconds=time.monotonic()-start,baseline_seconds=s['baseline'].get('inference_seconds'),baseline_flags=s['baseline'].get('flags'),characters=len(text),usage=response.get('usage'),timings=response.get('timings'),baseline_characters=len(base),text_identical=base==text,accuracy_evaluated=False)
   write(target/'metadata.json',meta);results.append(meta);write(OUT/'summary.json',dict(status='running',results=results));print(json.dumps(dict(event='page_saved',document=meta['document'],page=meta['page'],seconds=meta['inference_seconds'],flags=f)),flush=True)
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
 ap=argparse.ArgumentParser();ap.add_argument('--run-id',default='pilot_01');args=ap.parse_args()
 if not __import__('re').fullmatch(r'[A-Za-z0-9_-]+',args.run_id):raise ValueError('Invalid run ID')
 OUT=ROOT/'results'/'second_reading'/args.run_id
 def signal_exit(signum,frame):raise SystemExit('Signal '+str(signum))
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,signal_exit)
 main()
