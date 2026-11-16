#!/usr/bin/env python3
"""Default dry run. Explicit --execute activates sequential GPU inference."""
import argparse,base64,fcntl,hashlib,json,os,runpy,subprocess,threading,time,urllib.request
from pathlib import Path
from parse import parse
ROOT=Path(__file__).resolve().parent;B=ROOT.parent
OLD=runpy.run_path(str(B/'run_qwen.py'))
SPECS={'qwen3.5-9b':('Qwen3.5-9B-GGUF','Qwen3.5-9B','all'),'qwen3.8-27b':('Qwen3.8-27B-GGUF','Qwen3.8-27B','48')}
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(p)
def telemetry():return {'time':time.time(),'ram_available_gib':OLD['memory_available_gib'](),'vram_free_mib':OLD['gpu_free_mib']()}
def enough(r,ram,vram):return r['ram_available_gib']>=ram and r['vram_free_mib']>=vram

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--run-id',default=time.strftime('%Y%m%d-%H%M%S'));ap.add_argument('--repeat-baseline',action='store_true');ap.add_argument('--config',type=Path,default=ROOT/'pilot.json');args=ap.parse_args()
 cfg=json.loads(args.config.read_text());runpy.run_path(str(B/'assistant_reference_v2/build.py'))['verify']()
 paths=[args.config,B/'assistant_reference_v2/manifest.json',Path(OLD['SERVER'])]+list(ROOT.glob('*.py'))+list((ROOT/'prompts').glob('*.txt'))+[Path(x) for x in cfg['samples'].values()]
 for model in cfg['models']:
  folder,name,layers=SPECS[model];paths += [B/'models'/folder/(name+'-Q4_K_M.gguf'),B/'models'/folder/('mmproj-'+name+'-BF16.gguf')]
 for p in paths:
  if not p.is_file():raise FileNotFoundError(p)
 print(json.dumps({'dry_run':not args.execute,'models':cfg['models'],'samples':list(cfg['samples']),'attempts':len(cfg['models'])*len(cfg['samples'])*(2 if args.repeat_baseline else 1),'paths_valid':True}),flush=True)
 if not args.execute:return
 dest=B/'experiments/prompt_pilot_v1'/args.run_id
 if dest.exists():raise ValueError('Use a new run ID; existing runs are immutable')
 lock=(ROOT/'execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 initial=telemetry()
 if not enough(initial,12,14000):raise RuntimeError('Preflight resource reserve unavailable')
 # Detect foreign GPU workloads as well as a busy port. Never kill/reuse unknown processes.
 import socket
 with socket.socket() as sock:
  if sock.connect_ex(('127.0.0.1',18765))==0:raise RuntimeError('Port already occupied')
 workloads=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
 if workloads:raise RuntimeError('Other GPU compute processes present')
 hashes={str(p):digest(p) for p in paths};write(dest/'manifest.json',dict(config=cfg,hashes=hashes,run_id=args.run_id,status='running',baseline_comparison='historical unless repeated'))
 variants=['baseline_original','literal_regions_v1'] if args.repeat_baseline else [cfg.get('variant','literal_regions_v1')]
 failures=[]
 for model in cfg['models']:
  folder,name,layers=SPECS[model];r=telemetry()
  if not enough(r,12,14000):raise RuntimeError('Resources not recovered before load')
  cmd=[OLD['SERVER'],'-m',str(B/'models'/folder/(name+'-Q4_K_M.gguf')),'--mmproj',str(B/'models'/folder/('mmproj-'+name+'-BF16.gguf')),'--host','127.0.0.1','--port','18765','-ngl',layers,'-c','8192','-np','1','--image-max-tokens','4096','--jinja','--chat-template-kwargs','{"enable_thinking":false}','--no-webui']
  write(dest/model/'command.json',cmd);logpath=dest/model/'server.log';logpath.parent.mkdir(parents=True,exist_ok=True)
  stop=threading.Event();guard=[];process=None
  with logpath.open('w') as log:
   try:
    start=time.monotonic();process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    def monitor():
     while not stop.is_set():
      try:
       r=telemetry()
       if time.monotonic()-start>cfg.get('max_runtime_seconds',86400):raise TimeoutError('Document runtime limit')
       with (dest/'resource_monitor.jsonl').open('a') as f:f.write(json.dumps(dict(model=model,**r))+'\n')
       if not enough(r,4,1024):raise RuntimeError('Memory guard reserve crossed')
      except Exception as e:
       guard.append(str(e));process.terminate()
       try:process.wait(timeout=10)
       except subprocess.TimeoutExpired:process.kill()
       return
      stop.wait(3)
    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
    while True:
     if process.poll() is not None:raise RuntimeError('Server stopped: '+str(guard))
     if time.monotonic()-start>300:raise TimeoutError('Load timeout')
     try:
      if OLD['request']('/health',timeout=2).get('status')=='ok':break
     except OSError:pass
     time.sleep(1)
    load=time.monotonic()-start
    if not enough(telemetry(),8,2000):raise RuntimeError('Post-load reserve unavailable')
    for variant in variants:
     prompt=(ROOT/'prompts'/f'{variant}.txt').read_text().rstrip('\n')
     for sample,path in cfg['samples'].items():
      meta=dict(model=model,variant=variant,sample=sample,status='failed',load_seconds=load)
      try:
       if not enough(telemetry(),6,1500):raise RuntimeError('Pre-inference reserve unavailable')
       payload={'model':model,'messages':[{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(Path(path).read_bytes()).decode()}}]}],'temperature':0,'seed':42,'max_tokens':cfg.get('max_tokens',4096),'stream':False,'cache_prompt':False}
       t=time.monotonic();response=OLD['request']('/v1/chat/completions',payload,timeout=1800)
       write(dest/'raw'/variant/model/(sample+'-response.json'),response)
       choice=response['choices'][0];text=choice['message']['content'] or '';raw=dest/'raw'/variant/model/(sample+'.txt');raw.write_text(text)
       parsed=parse(text,variant!='baseline_original');write(dest/'parsed'/variant/model/(sample+'.json'),parsed)
       meta.update(seconds=time.monotonic()-t,finish_reason=choice.get('finish_reason'),usage=response.get('usage'),prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),status='complete' if text and choice.get('finish_reason')=='stop' else 'incomplete',parser_errors=parsed['errors'])
      except Exception as e:meta['error']=str(e);failures.append(meta)
      finally:write(dest/'metadata'/variant/model/(sample+'.json'),meta)
      if guard or process.poll() is not None:raise RuntimeError('Resource/server guard stopped experiment')
   finally:
    if process is not None:
     process.terminate()
     try:process.wait(timeout=20)
     except subprocess.TimeoutExpired:process.kill();process.wait()
    stop.set()
    if 'watcher' in locals():watcher.join(timeout=5)
  time.sleep(3)
 for p,h in hashes.items():
  if digest(p)!=h:raise RuntimeError('Input changed: '+p)
 write(dest/'validation.json',dict(inference_finished=True,failures=failures,evaluation_status='requires_region_assignment_review'))
 manifest=json.loads((dest/'manifest.json').read_text());manifest['status']='inference_complete';write(dest/'manifest.json',manifest)
 print(str(dest),flush=True)
if __name__=='__main__':main()
