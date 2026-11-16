"""Offline PDF transcription, durable page outputs and live HTML progress."""
import signal,traceback
from ops import event,notify,SESSION
import base64,collections,fcntl,hashlib,html,json,os,re,runpy,socket,subprocess,threading,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent;SOURCE=Path(os.environ.get('MAPH_SOURCE_ROOT',PROJECT/'Map-H-DATA'));OUT=Path(os.environ.get('MAPH_RESULTS_ROOT',ROOT/'results'));OUT.mkdir(parents=True,exist_ok=True)
OLD=runpy.run_path(str(PROJECT/'benchmark/run_qwen.py'))
MODEL=PROJECT/'benchmark/models/Qwen3.5-9B-GGUF';PROMPT=(PROJECT/'benchmark/prompt_trial/prompts/baseline_original.txt').read_text().strip()
state={'stage':'inventory','started':time.time(),'model':'qwen3.5-9b Q4_K_M','source':str(SOURCE),'documents':[],'current':None,'error':None}
try:
 previous=json.loads((OUT/'progress.json').read_text())
 state['started']=previous.get('started',state['started'])
except (OSError,ValueError):previous={}
state['session']=SESSION;state['session_started']=time.time()
mutex=threading.RLock();stop=threading.Event();abort=[];process=None;owns_inventory=False

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');
 with temp.open('w',encoding='utf-8') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2));f.flush();os.fsync(f.fileno())
 temp.replace(path)

def snapshot():
 with mutex:
  docs=state['documents'];pages=[p for d in docs for p in d['pages']];total=sum(d['page_count'] for d in docs)
  done=sum(p.get('status') in ('complete','needs_review','failed') for p in pages)
  groups={}
  for d in docs:
   g=groups.setdefault(d['folder'],dict(documents=0,finished=0,pages=0,processed=0,failed=0,review=0))
   g['documents']+=1;g['pages']+=d['page_count'];g['finished']+=d['status'] in ('complete','needs_review','failed')
   for p in d['pages']:
    g['processed']+=p.get('status') in ('complete','needs_review','failed');g['failed']+=p.get('status')=='failed';g['review']+=p.get('status')=='needs_review'
  state['summary']=dict(documents=len(docs),documents_finished=sum(d['status'] in ('complete','needs_review','failed') for d in docs),pdf_pages=total,processed=done,remaining=total-done,failed=sum(p.get('status')=='failed' for p in pages),review=sum(p.get('status')=='needs_review' for p in pages),folders=groups,elapsed_seconds=time.time()-state['started'])
  state['updated']=time.time();write(OUT/'progress.json',state)
  esc=lambda s:html.escape(str(s))
  rows=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [k,*g.values()])+'</tr>' for k,g in groups.items())
  summary=state['summary'];body=f'''<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>Progreso OCR local</title><style>body{{font:18px system-ui;margin:40px;background:#101827;color:#eee}}td,th{{padding:12px;border:1px solid #556}}table{{border-collapse:collapse}}pre{{white-space:pre-wrap}}a{{color:#8cf}}</style><h1>Transcripción confidencial · sólo modelo local</h1><p>Etapa: <b>{esc(state['stage'])}</b> · Actualización: {esc(time.strftime('%H:%M:%S'))}</p><p>{summary['documents_finished']} / {len(docs)} documentos terminados · {done} / {total} páginas PDF procesadas · {total-done} pendientes</p><p>Fallos: {summary['failed']} · Páginas que requieren revisión: {summary['review']} · Tiempo: {summary['elapsed_seconds']/60:.1f} min</p><p>Actual: {esc(state['current'])}</p><p>Error del proceso: {esc(state['error'])}</p><table><tr><th>Carpeta</th><th>PDF</th><th>PDF terminados</th><th>Páginas PDF</th><th>Procesadas</th><th>Fallos</th><th>Revisar</th></tr>{rows}</table><p>“Procesada” incluye fallos registrados. “Terminada” no significa verificada. Una página PDF puede contener varios escaneos; aún no se contabilizan como páginas lógicas separadas.</p><p>Actualización automática cada cinco segundos. No se muestra el texto confidencial en este panel.</p>'''
  tmp=OUT/'progress.html.tmp';tmp.write_text(body);tmp.replace(OUT/'progress.html')

def telemetry():
 vals=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,memory.used,utilization.gpu,power.draw,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=5).strip().splitlines()[0].split(',')
 return dict(time=time.time(),ram_available_gib=OLD['memory_available_gib'](),vram_free_mib=float(vals[0]),vram_used_mib=float(vals[1]),gpu_util_percent=float(vals[2]),power_watts=vals[3].strip(),temperature_c=vals[4].strip())

def monitor():
 while not stop.is_set():
  try:
   t=telemetry();t['stage']=state['stage'];t['current']=state['current'];t['session']=SESSION;state['last_resources']=t;notify('WATCHDOG=1')
   with (OUT/'telemetry.jsonl').open('a') as f:f.write(json.dumps(t)+'\n')
   if state.get('stage_started') and time.time()-state['stage_started']>240:raise TimeoutError('Stage exceeded 240 seconds')
   if t['ram_available_gib']<4 or t['vram_free_mib']<1024:raise RuntimeError('Memory reserve crossed')
   snapshot()
  except Exception as e:
   event('guard_stop',reason=str(e),stage=state['stage'],current=state['current'],resources=state.get('last_resources'));abort.append(str(e));state['error']=str(e)
   if process and process.poll() is None:
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill()
   return
  stop.wait(3)

def request(payload,timeout=180):
 req=urllib.request.Request('http://127.0.0.1:18765/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

def main():
 global process,owns_inventory
 management=OUT/'sources'/'management.lock';management.parent.mkdir(parents=True,exist_ok=True)
 inherited=os.environ.get('MAPH_SOURCE_LOCK_FD')
 if inherited:
  source_lock=os.fdopen(os.dup(int(inherited)),'a')
  if os.fstat(source_lock.fileno()).st_ino!=management.stat().st_ino:raise RuntimeError('Invalid source lock')
 else:
  source_lock=management.open('a');fcntl.flock(source_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 scope=set(json.loads(Path(os.environ['MAPH_SOURCE_SCOPE']).read_text())) if os.environ.get('MAPH_SOURCE_SCOPE') else None
 lock=(PROJECT/'benchmark/prompt_trial/execution.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 event('session_start',previous_stage=previous.get('stage'),previous_updated=previous.get('updated'),previous_processed=previous.get('summary',{}).get('processed'))
 candidates=[SOURCE/d['source'] for d in previous.get('documents',[])] if scope is not None else sorted(SOURCE.rglob('*'))
 for source in candidates:
  if source.suffix.lower()!='.pdf':continue
  rel=source.relative_to(SOURCE);digest=hashlib.sha256(source.read_bytes()).hexdigest();target=OUT/'documents'/rel.parent/(source.stem+'-'+digest[:10]);target.mkdir(parents=True,exist_ok=True)
  doc=dict(source=str(rel),folder=str(rel.parent),sha256=digest,page_count=0,pages=[],status='pending',output=str(target))
  try:
   info=subprocess.check_output(['pdfinfo',str(source)],text=True,stderr=subprocess.STDOUT,timeout=60);doc['page_count']=int(re.search(r'^Pages:\s+(\d+)',info,re.M)[1])
   for n in range(1,doc['page_count']+1):
    meta=target/f'page_{n:04}.json';prior=json.loads(meta.read_text()) if meta.exists() else {};doc['pages'].append(prior if prior.get('status')=='failed' or (prior.get('status') in ('complete','needs_review') and (target/f'page_{n:04}.md').exists()) else dict(number=n,status='pending'))
  except Exception as e:doc.update(status='failed',error=str(e))
  if doc['status']!='failed':
   statuses=[p['status'] for p in doc['pages']];doc['status']='pending' if 'pending' in statuses else 'failed' if 'failed' in statuses else 'needs_review' if 'needs_review' in statuses else 'complete'
  state['documents'].append(doc)
 owns_inventory=True;snapshot();write(OUT/'inventory.json',state['documents'])
 if not any(p['status'] not in ('complete','needs_review') for d in state['documents'] if (scope is None or d['source'] in scope) for p in d['pages']):
  state['stage']='finished';snapshot();event('batch_no_pending_pages');return
 initial=telemetry()
 if initial['ram_available_gib']<12 or initial['vram_free_mib']<14000:raise RuntimeError('Insufficient free memory before load')
 if subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip():raise RuntimeError('Another GPU workload present')
 with socket.socket() as sock:
  if sock.connect_ex(('127.0.0.1',18765))==0:raise RuntimeError('Inference port busy')
 cmd=[OLD['SERVER'],'-m',str(MODEL/'Qwen3.5-9B-Q4_K_M.gguf'),'--mmproj',str(MODEL/'mmproj-Qwen3.5-9B-BF16.gguf'),'--host','127.0.0.1','--port','18765','-ngl','all','-c','8192','-np','1','--image-max-tokens','4096','--jinja','--chat-template-kwargs','{"enable_thinking":false}','--no-webui']
 write(OUT/'config.json',dict(command=cmd,prompt=PROMPT,temperature=0,seed=42,max_tokens=4096,render_long_side=3000,logical_page_policy='whole PDF page; multiple scans remain together'))
 state['stage']='loading_model';snapshot();loaded=time.monotonic()
 with (OUT/'server.log').open('a') as log:
  process=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
 watcher=threading.Thread(target=monitor,daemon=True);watcher.start();notify('READY=1\nSTATUS=Local OCR active')
 event('engine_started',engine_pid=process.pid)
 try:
  while True:
   if abort or process.poll() is not None:raise RuntimeError('Model stopped: '+str(abort))
   if time.monotonic()-loaded>300:raise TimeoutError('Model load timeout')
   try:
    if OLD['request']('/health',timeout=2).get('status')=='ok':break
   except OSError:pass
   time.sleep(1)
  state['load_seconds']=time.monotonic()-loaded;event('model_loaded',seconds=state['load_seconds'])
  for doc in state['documents']:
   if not doc['pages'] or (scope is not None and doc['source'] not in scope):continue
   started=time.monotonic();target=Path(doc['output']);doc['status']='processing'
   for page in doc['pages']:
    if page['status'] in ('complete','needs_review'):continue
    n=page['number'];prefix=target/f'page_{n:04}';state['current']=dict(document=doc['source'],pdf_page=n,folder=doc['folder']);begin=time.monotonic();page['attempts']=page.get('attempts',[]);event('page_started',current=state['current'])
    for attempt in range(2):
     try:
      if abort:raise RuntimeError(str(abort))
      t=telemetry()
      if t['ram_available_gib']<6 or t['vram_free_mib']<1500:raise RuntimeError('Pre-inference reserve unavailable')
      state['stage']='rendering';state['stage_started']=time.time();snapshot();render=time.monotonic()
      subprocess.run(['pdftoppm','-f',str(n),'-l',str(n),'-singlefile','-scale-to','3000','-png',str(SOURCE/doc['source']),str(prefix)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120)
      page['render_seconds']=time.monotonic()-render;state['stage']='transcribing';state['stage_started']=time.time();snapshot();infer=time.monotonic()
      payload=dict(model='qwen3.5-9b',messages=[dict(role='user',content=[dict(type='text',text=PROMPT),dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(prefix.with_suffix('.png').read_bytes()).decode()))])],temperature=0,seed=42,max_tokens=4096,stream=False,cache_prompt=False)
      response=request(payload);page['inference_seconds']=time.monotonic()-infer;write(target/f'page_{n:04}.response.json',response)
      choice=response['choices'][0];text=choice['message'].get('content') or '';prefix.with_suffix('.md').write_text(text,encoding='utf-8')
      lines=[s.strip() for s in text.splitlines() if s.strip()];words=text.split();flags=[]
      if choice.get('finish_reason')!='stop':flags.append('truncated_or_nonstop')
      if not text.strip():flags.append('empty_output')
      if len(lines)>8 and len(set(lines))/len(lines)<0.6:flags.append('repeated_lines')
      if len(words)>100 and len(set(words))/len(words)<0.15:flags.append('repetitive_output')
      page.update(status='needs_review' if flags else 'complete',flags=flags,finish_reason=choice.get('finish_reason'),characters=len(text),usage=response.get('usage'),timings=response.get('timings'),review_status='unreviewed',attempts=page['attempts']+[dict(attempt=attempt+1,status='response_saved')]);break
     except Exception as e:
      event('page_attempt_failed',current=state['current'],attempt=attempt+1,error=str(e),error_type=type(e).__name__);page['attempts'].append(dict(attempt=attempt+1,error=str(e),time=time.time()));page.update(status='failed',error=str(e))
      if abort or process.poll() is not None:raise
      time.sleep(2)
    page['wall_seconds']=time.monotonic()-begin;write(prefix.with_suffix('.json'),page);state['stage_started']=None;event('page_saved',current=state['current'],status=page['status'],seconds=page['wall_seconds'],flags=page.get('flags',[]));snapshot()
   statuses=[p['status'] for p in doc['pages']];doc['status']='failed' if 'failed' in statuses else 'needs_review' if 'needs_review' in statuses else 'complete';doc['wall_seconds']=time.monotonic()-started
   write(target/'document.json',doc)
   texts=[]
   for p in doc['pages']:
    f=target/f"page_{p['number']:04}.md";texts.append(f"## Página PDF {p['number']} · {p['status']}\n\n"+(f.read_text() if f.exists() else '[Fallo técnico: sin transcripción]'))
   (target/'transcription.md').write_text('\n\n'.join(texts),encoding='utf-8');snapshot()
  state['stage']='finished';state['current']=None;event('batch_finished')
 finally:
  if process and process.poll() is None:
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait()
  stop.set();watcher.join(timeout=10);event('engine_exit',returncode=process.poll() if process else None);snapshot()

def received_signal(signum,frame):
 event('signal_received',signal=signal.Signals(signum).name,stage=state['stage'],current=state['current'],resources=state.get('last_resources'),sender='not_available_in_python_signal_handler')
 raise SystemExit(128+signum)

if __name__=='__main__':
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,received_signal)
 try:main()
 except BaseException as e:
  state['stage']='stopped';state['error']=str(e);event('coordinator_exit',error=str(e),error_type=type(e).__name__,traceback=traceback.format_exc(),current=state['current'])
  if owns_inventory:snapshot()
  raise
