"""Human adjudication of page alerts. Immutable history; never runs models."""
import hashlib,json,os,threading,time,uuid
import review
LOCK=threading.Lock();DECISIONS={'correct','incorrect','different_method'};METHODS={'preprocessing','orientation','regions','layout','handwriting','other'}
def latest(root):
 result={};path=root/'triage_events.jsonl'
 if path.exists():
  for line in path.read_text().splitlines():
   try:
    r=json.loads(line);result[r['document']+':'+str(r['page'])]=r
   except (ValueError,KeyError):continue
 return result

def index(root):
 result=latest(root)
 for value in result.values():
  try:
   current=review.load(root,value['document'],value['page']);value['applicable']=current['original_hash']==value['original_hash'] and (current['review']or{}).get('revision',0)==value['review_revision']
  except (ValueError,FileNotFoundError):value['applicable']=False
 return result

def save(root,data):
 if not isinstance(data,dict):raise ValueError('Invalid request')
 if not isinstance(data.get('document'),str) or type(data.get('page')) is not int:raise ValueError('Invalid page')
 decision=data.get('decision');name=data.get('reviewer');note=data.get('note','');method=data.get('method')
 if decision not in DECISIONS or not isinstance(name,str) or not name.strip() or len(name)>200 or not isinstance(note,str) or len(note)>5000:raise ValueError('Invalid decision or reviewer')
 if decision=='different_method' and method not in METHODS:raise ValueError('Choose a method to explore')
 with LOCK,review.LOCK:
  current=review.load(root,data['document'],data['page']);saved=current['review']or{};revision=saved.get('revision',0)
  if current['stale']:raise FileExistsError('Saved correction belongs to an older original; reconcile it first')
  if data.get('original_hash')!=current['original_hash'] or data.get('review_revision')!=revision:raise FileExistsError('Transcription changed; reopen before deciding')
  old=latest(root).get(data['document']+':'+str(data['page']))
  if data.get('previous_id')!=(old or {}).get('id'):raise FileExistsError('Decision changed; refresh before deciding')
  doc,prefix=review.locate(root,data['document'],data['page']);meta=json.loads(prefix.with_suffix('.json').read_text());audit_runs={}
  for key in ('audit_latest','model_audit_latest'):
   path=root/(key+'.json')
   if path.exists():audit_runs[key]=json.loads(path.read_text())
  r=dict(id=uuid.uuid4().hex,document=data['document'],source=doc['source'],page=data['page'],decision=decision,review_scope='preliminary_alert_review',reviewer_identified=name.strip()!='Human reviewer (unidentified)',reviewer=name.strip(),note=note,method=method if decision=='different_method' else None,original_hash=current['original_hash'],review_revision=revision,reading_basis=saved.get('basis','9b'),reviewed_text_sha256=hashlib.sha256((saved.get('text',current['original'])).encode()).hexdigest(),previous_id=(old or {}).get('id'),audit_runs=audit_runs,baseline_flags=meta.get('flags',[]),updated=time.time())
  with (root/'triage_events.jsonl').open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 return dict(r,applicable=True)
