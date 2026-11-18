"""Loopback-only dashboard and explicit local human review."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import html,json,threading,time,re,io,zipfile,os,ipaddress,hashlib
from urllib.parse import urlsplit,parse_qs,unquote
import research_sessions
import research_workspace
import hypotheses
import hypotheses_auto
import place_geography
import graphrag_control
import graphrag_review
import graphrag_queries
import review,issues,triage,content_search,reading_matrix,priority_search,priority_catalog,priority_audit,sources,selections,embeddings,process_telemetry
from metrics import export
from ops import status as operational_status
ROOT=Path(__file__).resolve().parent/'results'
BIND=os.environ.get('MAPH_DASHBOARD_BIND','127.0.0.1')
NETWORK=ipaddress.ip_network(os.environ.get('MAPH_DASHBOARD_NETWORK','127.0.0.0/8'))
HOSTS={'127.0.0.1:8091','localhost:8091'}|set(filter(None,os.environ.get('MAPH_DASHBOARD_HOSTS','').split(',')))
ORIGINS={'http://'+host for host in HOSTS}
def permitted_client(address):
 try:
  ip=ipaddress.ip_address(address);return ip.is_loopback or ip in NETWORK
 except ValueError:return False
def reading_root():
 full=ROOT/'second_reading'/'all_flagged_01'
 return full if (full/'manifest.json').exists() else ROOT/'second_reading'/'pilot_01'
class Handler(BaseHTTPRequestHandler):
 def reply(self,value,status=200,kind='application/json'):
  b=json.dumps(value).encode() if kind=='application/json' else value
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def allowed(self):
  return permitted_client(self.client_address[0]) and self.headers.get('Host') in HOSTS
 def do_POST(self):
  if not self.allowed() or self.headers.get('Origin') not in ORIGINS:self.reply({'error':'Forbidden'},403);return
  if self.path=='/sources/upload':
   try:
    if self.headers.get('Content-Type')!='application/pdf' or self.headers.get('Transfer-Encoding'):raise ValueError('Se requiere un PDF con tamaño conocido')
    self.connection.settimeout(90)
    self.reply(sources.upload(ROOT,unquote(self.headers.get('X-Source-Path','')),self.rfile,int(self.headers.get('Content-Length','0'))))
   except FileExistsError as e:self.reply({'error':str(e)},409)
   except (ValueError,TimeoutError) as e:self.reply({'error':str(e)},400)
   except OSError:self.reply({'error':'No se pudo guardar la fuente. Consulta el registro local.'},500)
   return
  if self.headers.get('Content-Type')!='application/json':self.reply({'error':'Forbidden'},403);return
  if self.path not in ('/review','/issues','/triage','/matrix','/matrix/retry','/priorities-run','/priorities-catalog','/sources/start','/sources/archive','/sources/restore','/selections','/embeddings/start','/place-geography','/knowledge-graph/questions','/knowledge-graph/control','/hypotheses','/hypotheses/auto','/research-sessions'):self.send_error(404);return
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=(5*1024*1024 if self.path in ('/selections','/research-sessions') else 1000000):raise ValueError('Invalid length')
   payload=json.loads(self.rfile.read(length))
   if not isinstance(payload,dict):raise ValueError('Se requiere un objeto JSON')
   if self.path=='/research-sessions':self.reply(research_sessions.save(ROOT,payload));return
   if self.path=='/hypotheses/auto':self.reply(hypotheses_auto.create(ROOT,payload));return
   if self.path=='/hypotheses':
    session_id=research_sessions.validate_link(ROOT,payload.get('session_id'));base=ROOT/'research_sessions'/session_id if session_id else ROOT
    if payload.get('query_id'):self.reply(research_workspace.save_diagram(ROOT,payload));return
    self.reply(hypotheses.save(base,payload));return
   if self.path=='/knowledge-graph/control':self.reply(graphrag_control.request(ROOT,payload));return
   if self.path=='/knowledge-graph/questions':self.reply(graphrag_queries.create(ROOT,payload));return
   if self.path=='/matrix/retry':self.reply(reading_matrix.retry(ROOT,payload));return
   if self.path=='/place-geography':self.reply(place_geography.save(ROOT,payload));return
   if self.path=='/embeddings/start':self.reply(embeddings.start(ROOT));return
   if self.path=='/selections':self.reply(selections.create(ROOT,payload));return
   if self.path.startswith('/sources/'):
    callback='http://127.0.0.1:'+str(self.server.server_port)
    if self.path=='/sources/start':self.reply(sources.start(ROOT,payload.get('ids'),refresh_only=payload.get('refresh_only') is True,dashboard_url=callback));return
    result=sources.archive(ROOT,payload.get('ids')) if self.path=='/sources/archive' else sources.restore(ROOT,payload.get('id'))
    try:result['job']=sources.start(ROOT,refresh_only=True,dashboard_url=callback)
    except (FileExistsError,OSError) as e:result['refresh_error']=str(e)
    self.reply(result);return
   if self.path=='/priorities-run':self.reply(priority_search.start(ROOT,reason='sources_updated' if payload.get('reason')=='sources_updated' else 'manual'));return
   if self.path=='/priorities-catalog':self.reply(priority_catalog.save(ROOT,payload));return
   self.reply((reading_matrix.create if self.path=='/matrix' else triage.save if self.path=='/triage' else issues.save if self.path=='/issues' else review.save)(ROOT,payload))
  except FileExistsError as e:self.reply({'error':str(e)},409)
  except (ValueError,KeyError,FileNotFoundError) as e:self.reply({'error':str(e)},400)
 def do_GET(self):
  if not self.allowed():self.reply({'error':'Forbidden'},403);return
  route=urlsplit(self.path);q=parse_qs(route.query)
  if route.path in ('/research-sessions','/research-sessions/export','/research-sessions/jobs'):
   try:
    key=q.get('id',[''])[0]
    if route.path.endswith('/export'):self.reply(research_sessions.sqlite_bytes(ROOT,key),kind='application/vnd.sqlite3')
    elif route.path.endswith('/jobs'):research_sessions.get(ROOT,key);self.reply(research_sessions.jobs(ROOT,key))
    else:self.reply(research_sessions.get(ROOT,key) if key else research_sessions.listing(ROOT))
   except FileExistsError as e:self.reply({'error':str(e)},409)
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/research-workspace/fishbone':
   try:self.reply(research_workspace.diagram_state(ROOT,q.get('id',[''])[0],q.get('kind',['knowledge_graph'])[0],q.get('session_id',[None])[0]))
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/research-workspace/evidence':
   try:self.reply(research_workspace.manifest(ROOT,q.get('id',[''])[0],q.get('kind',['knowledge_graph'])[0],q.get('session_id',[None])[0]))
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/hypotheses/auto':
   try:self.reply(hypotheses_auto.get(ROOT,q.get('id',[''])[0]))
   except (ValueError,OSError):self.reply({'error':'Job unavailable'},400)
   return
  if route.path=='/hypotheses':
   try:
    session_id=research_sessions.validate_link(ROOT,q.get('session_id',[None])[0]);base=ROOT/'research_sessions'/session_id if session_id else ROOT
    if q.get('query_id'):base=research_workspace.artifact_root(ROOT,q['query_id'][0],q.get('query_kind',['knowledge_graph'])[0],session_id)
    self.reply(hypotheses.load(base))
   except ValueError as e:self.reply({'error':str(e)},400)
   return
  if route.path in ('/knowledge-graph/questions','/knowledge-graph/questions/csv'):
   try:
    if route.path.endswith('/csv'):self.reply(graphrag_queries.csv_bytes(ROOT,q.get('id',[''])[0]),kind='text/csv; charset=utf-8')
    else:self.reply(graphrag_queries.get(ROOT,q['id'][0]) if 'id' in q else graphrag_queries.listing(ROOT))
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path in ('/knowledge-graph','/knowledge-graph/status','/knowledge-graph/page','/knowledge-graph/csv'):
   try:
    if route.path=='/knowledge-graph':self.reply(graphrag_review.get(ROOT))
    elif route.path=='/knowledge-graph/status':self.reply(graphrag_review.status(ROOT))
    elif route.path=='/knowledge-graph/page':self.reply(graphrag_review.page(ROOT,q.get('document',[''])[0],int(q.get('page',['0'])[0]),q.get('version',[''])[0],q.get('run',[None])[0]))
    else:self.reply(graphrag_review.csv_bytes(ROOT),kind='text/csv; charset=utf-8')
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path in ('/process-telemetry','/process-telemetry/record','/process-telemetry/bundle','/process-telemetry/csv','/process-telemetry/pages'):
   try:
    if route.path=='/process-telemetry':self.reply(process_telemetry.listing(ROOT))
    elif route.path=='/process-telemetry/pages':self.reply(process_telemetry.page_coverage(ROOT))
    elif route.path=='/process-telemetry/csv':self.reply(process_telemetry.csv_bytes(ROOT),kind='text/csv; charset=utf-8')
    elif route.path=='/process-telemetry/record':self.reply(process_telemetry.detail(ROOT,q.get('stage',[''])[0],q.get('run',[''])[0]))
    else:self.reply(process_telemetry.bundle(ROOT,q.get('stage',[''])[0],q.get('run',[''])[0]),kind='application/zip')
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path in ('/embeddings/status','/embeddings/history','/embeddings/bundle'):
   try:
    if route.path=='/embeddings/status':self.reply(embeddings.status(ROOT))
    elif route.path=='/embeddings/history':self.reply(embeddings.history(ROOT))
    else:self.reply(embeddings.bundle(ROOT,q.get('run',[''])[0]),kind='application/zip')
   except (ValueError,OSError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/selections':
   try:self.reply(selections.get(ROOT,q['id'][0]) if 'id' in q else selections.listing(ROOT))
   except ValueError as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/selections-image':
   try:self.reply(selections.image_path(ROOT,q.get('id',[''])[0],int(q.get('row',['-1'])[0])).read_bytes(),kind='image/png')
   except (ValueError,FileNotFoundError):self.reply({'error':'Imagen no disponible'},404)
   return
  if route.path=='/selections-export':
   try:
    value=selections.get(ROOT,q.get('id',[''])[0]);format=q.get('format',['csv'])[0]
    if format not in ('csv','json'):raise ValueError('Formato inválido')
    if format=='csv':self.reply(selections.csv_bytes(value,'http://'+self.headers['Host']),kind='text/csv; charset=utf-8')
    else:self.reply(value)
   except ValueError as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/sources':
   try:self.reply(sources.listing(ROOT))
   except (OSError,ValueError,KeyError):self.reply({'error':'No se pudo leer el inventario de fuentes.'},500)
   return
  if route.path=='/sources-history':
   path=ROOT/'sources'/'events.jsonl';self.reply(path.read_bytes() if path.exists() else b'',kind='application/x-ndjson');return
  if route.path=='/sources-log':
   job=sources.job_status(ROOT);key=job.get('id','')
   if not re.fullmatch('[a-f0-9]{32}',key):self.reply(b'Sin procesos de fuentes.',kind='text/plain; charset=utf-8');return
   path=ROOT/'sources'/'jobs'/key/'process.log';self.reply(path.read_bytes() if path.exists() else b'',kind='text/plain; charset=utf-8');return
  if route.path=='/place-geography':
   try:self.reply(place_geography.get(ROOT))
   except (OSError,ValueError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/geography-base.json':
   self.reply((Path(__file__).resolve().parent/'geography-base.json').read_bytes(),kind='application/geo+json');return
  if route.path=='/priorities-history':
   if q.get('download')==['1']:
    path=priority_audit.path(ROOT);self.reply(path.read_bytes() if path.exists() else b'',kind='application/x-ndjson')
   else:self.reply(priority_audit.history(ROOT))
   return
  if route.path=='/priorities-catalog':
   try:self.reply(priority_catalog.get(ROOT))
   except (OSError,ValueError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/priorities':
   try:self.reply(priority_search.get(ROOT))
   except (OSError,ValueError,KeyError) as e:self.reply({'error':str(e)},400)
   return
  if route.path in ('/vendor/sigma-graphology.js','/graph-webgl.js'):
   self.reply((Path(__file__).resolve().parent/route.path.lstrip('/')).read_bytes(),kind='application/javascript');return
  if route.path in ('/priority-search.js','/priority-balance-core.js','/priority-balance.js','/priority-catalog-editor.js','/sources-ui.js','/research-selection.js','/embeddings-ui.js','/process-telemetry-ui.js','/process-methods.js','/graphrag-i18n.js','/interface-catalog.js','/interface-i18n.js','/graphrag-pilot-ui.js','/graphrag-explorer.js','/graphrag-query-progress.js','/graphrag-result-core.js','/graphrag-result-ui.js','/graphrag-entities.js','/source-review.js','/research-sessions.js','/knowledge-workspace.js','/knowledge-graph-filters.js','/knowledge-source-filters.js','/app-header.js','/place-map.js','/place-map-core.js','/place-map-navigation.js'):
   self.reply((Path(__file__).resolve().parent/route.path.lstrip('/')).read_bytes(),kind='application/javascript');return
  if route.path=='/matrix':
   try:self.reply(reading_matrix.get(ROOT,q['id'][0]) if 'id' in q else reading_matrix.listing(ROOT))
   except ValueError as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/reading-matrix.js':
   self.reply((Path(__file__).resolve().parent/'reading-matrix.js').read_bytes(),kind='application/javascript');return
  if route.path in ('/content-search','/content-search-page'):
   try:
    extra={}
    if route.path=='/content-search-page':
     ident=q.get('document',[''])[0];page=int(q.get('page',['0'])[0]);review.locate(ROOT,ident,page)
     extra=dict(document_id=ident,page_number=page,include_text=True)
    self.reply(content_search.search(ROOT,q.get('q',[''])[0],q.get('mode',['flexible'])[0],**extra))
   except ValueError as e:self.reply({'error':str(e)},400)
   return
  if route.path=='/content-search.js':
   self.reply((Path(__file__).resolve().parent/'content-search.js').read_bytes(),kind='application/javascript');return
  if route.path=='/audit-pages':
   kind=q.get('kind',['rules'])[0];category=q.get('category',['all'])[0]
   pointer=ROOT/('model_audit_latest.json' if kind=='model' else 'audit_latest.json')
   if not pointer.exists():self.reply({'pages':[]});return
   base=ROOT/('model_audits' if kind=='model' else 'audits');audit=base/json.loads(pointer.read_text())['run_id']
   if not audit.resolve().is_relative_to(base.resolve()):self.send_error(400);return
   pages=[]
   if kind=='model':
    for path in (audit/'pages').glob('*/*/classification.json'):pages.append(json.loads(path.read_text()))
   elif (audit/'all_pages.json').exists():pages=json.loads((audit/'all_pages.json').read_text())
   pages=[{key:p[key] for key in ('document','document_id','page','classification','findings') if key in p} for p in pages if category=='all' or p.get('classification')==category]
   pages.sort(key=lambda p:(p['document'],p['page']));self.reply({'pages':pages,'kind':kind,'category':category});return
  if route.path in ('/model-audit-status','/model-audit-bundle'):
   pointer=ROOT/'model_audit_latest.json'
   if not pointer.exists():self.reply({'available':False});return
   audit=ROOT/'model_audits'/json.loads(pointer.read_text())['run_id']
   if not audit.resolve().is_relative_to((ROOT/'model_audits').resolve()):self.send_error(400);return
   if route.path=='/model-audit-status':
    manifest=json.loads((audit/'manifest.json').read_text());findings=json.loads((audit/'findings.json').read_text()) if (audit/'findings.json').exists() else []
    samples=[]
    for line in (audit/'telemetry.jsonl').read_text().splitlines()[-120:] if (audit/'telemetry.jsonl').exists() else []:
     try:samples.append(json.loads(line))
     except ValueError:pass
    measured=[]
    for page in (audit/'pages').glob('*/*/classification.json'):
     record=json.loads(page.read_text());measured.append((record.get('audited_at',0),record.get('audit_seconds',0)))
    measured.sort();durations=[seconds for _,seconds in measured if seconds>0]
    estimate=dict(samples=len(durations),remaining=max(0,manifest['total_pages']-manifest['processed']))
    if len(durations)>=20 and manifest['status']=='running' and samples and time.time()-samples[-1]['time']<45:
     mean=sum(durations)/len(durations);recent=sum(durations[-30:])/len(durations[-30:]);remaining=estimate['remaining']
     estimate.update(seconds=remaining*(mean+recent)/2,low=remaining*min(mean,recent)*.8,high=remaining*max(mean,recent)*1.25,estimated_finish=time.time()+remaining*(mean+recent)/2)
    self.reply(dict(available=True,manifest=manifest,findings=findings,telemetry=samples,estimate=estimate));return
   stream=io.BytesIO()
   with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
    for path in audit.rglob('*'):
     if path.is_file() and path.suffix in ('.json','.jsonl','.md','.py','.log'):z.write(path,str(path.relative_to(audit)))
   self.reply(stream.getvalue(),kind='application/zip');return
  if route.path in ('/audit-status','/audit-record','/audit-bundle'):
   pointer=ROOT/'audit_latest.json'
   if not pointer.exists():self.reply({'available':False});return
   run_id=json.loads(pointer.read_text())['run_id'];audit=ROOT/'audits'/run_id
   if not audit.resolve().is_relative_to((ROOT/'audits').resolve()):self.send_error(400);return
   manifest=json.loads((audit/'manifest.json').read_text())
   if route.path=='/audit-status':
    findings=json.loads((audit/'findings.json').read_text()) if (audit/'findings.json').exists() else []
    self.reply(dict(available=True,manifest=manifest,findings=findings));return
   if route.path=='/audit-record':self.reply(manifest);return
   stream=io.BytesIO()
   with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
    for path in audit.rglob('*'):
     if path.is_file() and path.suffix in ('.json','.jsonl','.md','.py'):z.write(path,str(path.relative_to(audit)))
   self.reply(stream.getvalue(),kind='application/zip');return
  if route.path=='/triage':
   self.reply(triage.index(ROOT));return
  if route.path=='/issues':
   self.reply(issues.index(ROOT));return
  if route.path in ('/second-reading-record','/second-reading-bundle'):
   pilot=reading_root()
   if not (pilot/'manifest.json').exists():self.reply({'available':False});return
   if route.path=='/second-reading-record':
    record={}
    for name in ('manifest','provenance','metrics'):
     path=pilot/(name+'.json')
     if path.exists():record[name]=json.loads(path.read_text())
    self.reply(record);return
   stream=io.BytesIO()
   with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
    for path in pilot.rglob('*'):
     if path.is_file() and path.suffix in ('.json','.jsonl','.md','.diff','.log','.py','.png'):z.write(path,str(path.relative_to(pilot)))
    manifest=json.loads((pilot/'manifest.json').read_text())
    for i,sample in enumerate(manifest['samples']):
     prefix=Path(sample['prefix'])
     if not prefix.resolve().is_relative_to((ROOT/'documents').resolve()):continue
     for suffix in ('.png','.md','.json','.response.json'):
      path=prefix.with_suffix(suffix)
      if path.exists():z.write(path,'baseline/case_'+str(i+1)+'/'+path.name)
   self.reply(stream.getvalue(),kind='application/zip');return
  if route.path=='/second-reading-status':
   pilot=reading_root()
   if not (pilot/'manifest.json').exists():self.reply({'available':False});return
   manifest=json.loads((pilot/'manifest.json').read_text());live=json.loads((pilot/'live.json').read_text()) if (pilot/'live.json').exists() else {}
   summary=json.loads((pilot/'summary.json').read_text()) if (pilot/'summary.json').exists() else {'results':[]}
   for result in summary['results']:
    meta=pilot/result['case']/'metadata.json'
    result['completed_at']=meta.stat().st_mtime if meta.exists() else 0
   self.reply(dict(available=True,status=manifest['status'],model=manifest['model'],total=len(manifest['samples']),finished=len(summary['results']),live=live,results=[{k:v for k,v in r.items() if k in ('document','document_id','page','flags','status','assembly_flags','reused_from','completed_at')} for r in summary['results']]));return
  if route.path=='/second-reading':
   try:
    ident=q['document'][0];page=int(q['page'][0]);pilot=reading_root()
    summary=json.loads((pilot/'summary.json').read_text())
    match=next((x for x in summary['results'] if x['document_id']==ident and x['page']==page),None)
    if not match:self.reply({'available':False});return
    case=pilot/match['case']
    if not case.resolve().is_relative_to(pilot.resolve()):raise ValueError()
    self.reply(dict(available=True,run_id=pilot.name,metadata=match,text=(case/'transcription.md').read_text()));return
   except (ValueError,KeyError,FileNotFoundError):self.reply({'available':False});return
  if route.path in ('/reviews.json','/review','/page-image','/download'):
   try:
    if route.path=='/reviews.json':self.reply(review.index(ROOT));return
    ident=q['document'][0];page=int(q.get('page',['1'])[0])
    if route.path=='/review':self.reply(review.load(ROOT,ident,page));return
    if route.path=='/download':self.reply(review.bundle(ROOT,ident),kind='application/zip');return
    doc,prefix=review.locate(ROOT,ident,page);self.reply(prefix.with_suffix('.png').read_bytes(),kind='image/png');return
   except (ValueError,KeyError,FileNotFoundError):self.reply({'error':'Page unavailable'},404);return
  if self.path.split('?',1)[0]=='/operations.json':
   b=json.dumps(operational_status()).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  name={'/':'dashboard.html','/progress.json':'progress.json','/telemetry.json':'telemetry.jsonl','/map-h-symbol.svg':'map-h-symbol.svg','/manrope.woff2':'manrope.woff2','/i18n.js':'i18n.js','/review-ui.js':'review-ui.js','/layout.js':'layout.js','/interactive.js':'interactive.js','/results-ui.js':'results-ui.js','/journey.js':'journey.js','/comfort.js':'comfort.js','/editor-polish.js':'editor-polish.js','/annotations-core.js':'annotations-core.js','/highlights.js':'highlights.js','/unified-editor.js':'unified-editor.js','/unified-editor.css':'unified-editor.css','/image-controls.js':'image-controls.js','/word-correction.js':'word-correction.js','/second-reading.js':'second-reading.js','/processing-issues.js':'processing-issues.js','/audit-ui.js':'audit-ui.js','/model-audit-ui.js':'model-audit-ui.js','/result-links.js':'result-links.js','/review-queue.js':'review-queue.js','/case-review.js':'case-review.js','/experience-order.js':'experience-order.js','/data-flow.js':'data-flow.js'}.get(self.path.split('?',1)[0])
  if not name:self.send_error(404);return
  p=Path(__file__).resolve().parent/name if name in ('dashboard.html','map-h-symbol.svg','manrope.woff2','i18n.js','review-ui.js','layout.js','interactive.js','results-ui.js','journey.js','comfort.js','editor-polish.js','annotations-core.js','highlights.js','unified-editor.js','unified-editor.css','image-controls.js','word-correction.js','second-reading.js','processing-issues.js','audit-ui.js','model-audit-ui.js','result-links.js','review-queue.js','case-review.js','experience-order.js','data-flow.js') else ROOT/name
  if not p.exists():self.send_error(503);return
  b=p.read_bytes()
  if name=='dashboard.html':
   config=json.loads((ROOT/'config.json').read_text());b=b.decode().replace('{{MODEL_PROMPT}}',html.escape(config['prompt'])).encode()
   b=re.sub(rb'src="(/[^"]+\.js)"',lambda m:b'src="'+m[1]+b'?v='+str((Path(__file__).resolve().parent/m[1].decode().lstrip('/')).stat().st_mtime_ns).encode()+b'"',b)
  if name=='progress.json':
   progress=json.loads(b)
   for document in progress.get('documents',[]):document['document_id']=hashlib.sha256(document['source'].encode()).hexdigest()
   b=json.dumps(progress,ensure_ascii=False).encode()
  if name=='telemetry.jsonl':
   records=[]
   for line in b.decode().splitlines():
    try:records.append(json.loads(line))
    except ValueError:pass
   b=json.dumps(records).encode()
  self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if name.endswith('html') else 'text/css; charset=utf-8' if name.endswith('css') else 'image/svg+xml' if name.endswith('svg') else 'font/woff2' if name.endswith('woff2') else 'application/javascript; charset=utf-8' if name.endswith('js') else 'application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def log_message(self,*args):pass
def refresh():
 while True:
  try:export()
  except (OSError,ValueError,KeyError):pass
  time.sleep(5)
if __name__=='__main__':
 threading.Thread(target=refresh,daemon=True).start()
 threading.Thread(target=embeddings.watch,args=(ROOT,),daemon=True).start()
 threading.Thread(target=research_workspace.watch_followups,args=(ROOT,),daemon=True).start()
 ThreadingHTTPServer((BIND,8091),Handler).serve_forever()
