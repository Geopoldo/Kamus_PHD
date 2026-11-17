"""Resumable attributed research sessions, frozen readings and relational exports."""
import hashlib,json,re,sqlite3,tempfile,threading,time,uuid
from pathlib import Path
import reading_matrix,review,sources
LOCK=threading.RLock()
def path(root,key):
 if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{32}',key):raise ValueError('Invalid research session')
 return Path(root)/'research_sessions'/key/'session.json'
def get(root,key):
 p=path(root,key)
 if not p.is_file():raise ValueError('Research session not found')
 return json.loads(p.read_text())
def summary(value):
 return {k:value[k] for k in ('id','title','objective','researcher','curator','created','updated','revision','pages','readings')}
def listing(root):
 return sorted([summary(json.loads(p.read_text())) for p in (Path(root)/'research_sessions').glob('*/session.json')],key=lambda v:v['updated'],reverse=True)
def text(value,key,maximum,required=False):
 s=value.get(key,'')
 if not isinstance(s,str) or len(s)>maximum or (required and not s.strip()):raise ValueError('Invalid '+key)
 return s.strip()
def bounded(value,maximum=64000):
 if len(json.dumps(value,ensure_ascii=False))>maximum:raise ValueError('Metadata too large')
 return value
def save(root,payload):
 root=Path(root)
 with LOCK,review.LOCK:
  key=payload.get('id') or uuid.uuid4().hex;target=path(root,key)
  old=get(root,key) if payload.get('id') else None
  if payload.get('revision',0)!=(old['revision'] if old else 0):raise FileExistsError('Session changed in another tab. Reopen the saved session before saving again; your local draft is retained.')
  title=text(payload,'title',160,True);objective=text(payload,'objective',5000,True);researcher=text(payload,'researcher',160,True);curator=text(payload,'curator',160)
  records=payload.get('records',[]);searches=payload.get('searches',[])
  if not isinstance(records,list) or len(records)>2000 or not isinstance(searches,list) or len(searches)>5000:raise ValueError('Session limit exceeded')
  old_rows={reading_key(r):r for r in (old or {}).get('records',[])};rows={}
  for item in records:
   if not isinstance(item,dict):raise ValueError('Invalid record')
   rk=reading_key(item);previous=old_rows.get(rk);expected=item.get('text_sha256')
   if previous and (not expected or expected==previous.get('text_sha256')):
    row={k:v for k,v in previous.items() if k not in ('contexts','note','selected_at')}
   else:
    row=reading_matrix.snapshot(root,item)
    if expected and expected!=row['text_sha256']:raise FileExistsError('A selected transcript changed. Check the source and select it again. The saved session is unchanged.')
    _,prefix=review.locate(root,row['document_id'],row['page']);original=prefix.with_suffix('.md').read_text() if prefix.with_suffix('.md').is_file() else ''
    doc,_=review.locate(root,row['document_id'],row['page'])
    row.update(original_text=original,original_sha256=hashlib.sha256(original.encode()).hexdigest(),source_sha256=doc.get('sha256',''),snapshot_at=time.time())
   contexts=item.get('contexts',[])
   if not isinstance(contexts,list) or len(contexts)>100 or any(not isinstance(c,dict) for c in contexts):raise ValueError('Invalid selection contexts')
   contexts=bounded(contexts,256000);note=text(item,'note',5000);selected_at=item.get('selected_at') or time.time()
   if type(selected_at) not in (int,float) or not 0<selected_at<=time.time()+60:raise ValueError('Invalid selection date')
   row.update(note=note,selected_at=selected_at,contexts=contexts)
   if rk in rows:
    for c in contexts:
     if c not in rows[rk]['contexts']:rows[rk]['contexts'].append(c)
   else:rows[rk]=row
  for search in searches:
   if not isinstance(search,dict) or not isinstance(search.get('id'),str):raise ValueError('Invalid search event')
   bounded(search)
  now=time.time();revision=(old or {}).get('revision',0)+1
  value=dict(id=key,title=title,objective=objective,researcher=researcher,curator=curator,created=(old or {}).get('created',now),updated=now,revision=revision,records=list(rows.values()),searches=list({s['id']:s for s in searches}.values()),pages=len({(r['document_id'],r['page']) for r in rows.values()}),readings=len(rows),history=(old or {}).get('history',[])+[dict(revision=revision,time=now,researcher=researcher,curator=curator,readings=len(rows),searches=len(searches))])
  sources.write(target.parent/f'revision-{revision}.json',value);sources.write(target,value)
  sources.audit(root,'research_session_saved',session=key,revision=revision,readings=len(rows),searches=len(searches),researcher=researcher)
  return value
def reading_key(record):
 if not isinstance(record.get('document_id'),str) or type(record.get('page')) is not int or record['page']<1 or not isinstance(record.get('version'),str):raise ValueError('Invalid page reference')
 return (record['document_id'],record['page'],record['version'])
def validate_link(root,key):
 if key:get(root,key)
 return key or None
def jobs(root,key):
 result=[]
 for kind,pattern in [('matrix','matrices/*/matrix.json'),('knowledge_graph','knowledge_graph/questions/*/question.json'),('fishbone','hypotheses/auto/*/job.json')]:
  for p in Path(root).glob(pattern):
   v=json.loads(p.read_text())
   if v.get('session_id')==key:result.append({'kind':kind,'id':v.get('id'),**v})
 return sorted(result,key=lambda v:v.get('created',v.get('started',0)),reverse=True)
def sqlite_bytes(root,key):
 value=get(root,key);runs=jobs(root,key)
 with tempfile.TemporaryDirectory(prefix='maph-session-export-') as tmp:
  p=Path(tmp)/'session.sqlite';db=sqlite3.connect(p);db.executescript('''
 PRAGMA foreign_keys=ON;
 CREATE TABLE session(id TEXT PRIMARY KEY,title TEXT,objective TEXT,researcher TEXT,curator TEXT,created REAL,updated REAL,revision INTEGER,exported_at REAL);
 CREATE TABLE documents(id TEXT PRIMARY KEY,path TEXT,folder TEXT,source_sha256 TEXT);
 CREATE TABLE readings(id INTEGER PRIMARY KEY,document_id TEXT REFERENCES documents(id),page INTEGER,version TEXT,text TEXT,text_sha256 TEXT,original_text TEXT,original_sha256 TEXT,review_status TEXT,snapshot_at REAL,selected INTEGER,note TEXT,selected_at REAL);
 CREATE TABLE search_events(id TEXT PRIMARY KEY,kind TEXT,query TEXT,created REAL,parameters_json TEXT);
 CREATE TABLE selection_contexts(id INTEGER PRIMARY KEY,reading_id INTEGER REFERENCES readings(id),kind TEXT,query TEXT,parameters_json TEXT);
 CREATE TABLE runs(id TEXT PRIMARY KEY,kind TEXT,status TEXT,model TEXT,created REAL,details_json TEXT);
 CREATE TABLE run_readings(run_id TEXT REFERENCES runs(id),reading_id INTEGER REFERENCES readings(id),PRIMARY KEY(run_id,reading_id));
 CREATE TABLE questions(id INTEGER PRIMARY KEY,run_id TEXT REFERENCES runs(id),question_index INTEGER,text TEXT);
 CREATE TABLE answers(id INTEGER PRIMARY KEY,run_id TEXT REFERENCES runs(id),question_id INTEGER REFERENCES questions(id),reading_id INTEGER REFERENCES readings(id),status TEXT,answer TEXT,evidence_quote TEXT,errors_json TEXT);
 CREATE TABLE history(revision INTEGER,time REAL,researcher TEXT,curator TEXT,details_json TEXT);
 CREATE TABLE research_artifacts(kind TEXT,data_json TEXT);
 ''')
  db.execute('INSERT INTO session VALUES(?,?,?,?,?,?,?,?,?)',tuple(value[k] for k in ('id','title','objective','researcher','curator','created','updated','revision'))+(time.time(),))
  reading_ids={}
  def add_reading(r,selected=0):
   # Keep matrix text snapshots even when a later correction changes that reading.
   rk=(*reading_key(r),r.get('text_sha256',''))
   if rk in reading_ids:return reading_ids[rk]
   db.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?)',(r['document_id'],r['document'],r.get('folder',''),r.get('source_sha256','')))
   cursor=db.execute('INSERT INTO readings(document_id,page,version,text,text_sha256,original_text,original_sha256,review_status,snapshot_at,selected,note,selected_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(r['document_id'],r['page'],r['version'],r.get('text',''),r.get('text_sha256',''),r.get('original_text',''),r.get('original_sha256',''),r.get('review_status',''),r.get('snapshot_at'),selected,r.get('note',''),r.get('selected_at')));rid=cursor.lastrowid;reading_ids[rk]=rid
   for c in r.get('contexts',[]):db.execute('INSERT INTO selection_contexts(reading_id,kind,query,parameters_json) VALUES(?,?,?,?)',(rid,c.get('kind'),c.get('query'),json.dumps(c,ensure_ascii=False)))
   return rid
  for r in value['records']:add_reading(r,1)
  for s in value['searches']:db.execute('INSERT INTO search_events VALUES(?,?,?,?,?)',(s['id'],s.get('kind'),s.get('query'),s.get('created'),json.dumps(s,ensure_ascii=False)))
  for run in runs:
   db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(run['id'],run['kind'],run['status'],run.get('model'),run.get('created',run.get('started')),json.dumps(run,ensure_ascii=False)))
   source_rows=run.get('rows',[])
   if run['kind']=='knowledge_graph' and run['status'] in ('complete','complete_with_errors'):
    import research_workspace
    try:_,source_rows,_=research_workspace.evidence(root,run['id'],'knowledge_graph',key)
    except (ValueError,OSError,KeyError) as error:
     db.execute('INSERT INTO research_artifacts VALUES(?,?)',('unresolved_question_sources',json.dumps({'query_id':run['id'],'error':str(error)})))
   for row in source_rows:db.execute('INSERT OR IGNORE INTO run_readings VALUES(?,?)',(run['id'],add_reading(row)))
   if run['kind']=='matrix':
    qids=[]
    for i,q in enumerate(run['questions']):qids.append(db.execute('INSERT INTO questions(run_id,question_index,text) VALUES(?,?,?)',(run['id'],i,q)).lastrowid)
    for cell in run.get('cells',[]):
     rid=add_reading(run['rows'][cell['row']]);parts=cell.get('parts') or [{}]
     for part in parts:
      for quote in part.get('evidence_quotes') or [part.get('evidence_quote','')]:
       db.execute('INSERT INTO answers(run_id,question_id,reading_id,status,answer,evidence_quote,errors_json) VALUES(?,?,?,?,?,?,?)',(run['id'],qids[cell['question']],rid,part.get('status',cell['status']),part.get('answer',''),quote,json.dumps(cell.get('errors',[]))))
   elif run['kind']=='fishbone':
    for row in run.get('rows',[]):add_reading(row)
   elif run['kind']=='knowledge_graph':
    qid=db.execute('INSERT INTO questions(run_id,question_index,text) VALUES(?,?,?)',(run['id'],0,run['question'])).lastrowid
    db.execute('INSERT INTO answers(run_id,question_id,status,answer,errors_json) VALUES(?,?,?,?,?)',(run['id'],qid,run['status'],str(run.get('answer','')),json.dumps(run.get('error'))))
  for run in runs:
   if run['kind'] not in ('knowledge_graph','matrix'):continue
   import research_workspace
   artifact=research_workspace.artifact_root(root,run['id'],run['kind'],key)/'hypotheses/current.json'
   if artifact.exists():db.execute('INSERT INTO research_artifacts VALUES(?,?)',('question_fishbone',artifact.read_text()))
  for event in value['history']:db.execute('INSERT INTO history VALUES(?,?,?,?,?)',(event['revision'],event['time'],event['researcher'],event['curator'],json.dumps(event)))
  fish=path(root,key).parent/'hypotheses/current.json'
  if fish.exists():db.execute('INSERT INTO research_artifacts VALUES(?,?)',('fishbone',fish.read_text()))
  db.commit();db.close();return p.read_bytes()
