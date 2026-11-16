"""Durable user-reported page issues, separate from inference and human edits."""
import json,os,threading,time,uuid
import review
LOCK=threading.Lock()
REASONS={'not_transcribed','incomplete','incorrect','image_quality','orientation','other'}
def index(root):
 path=root/'user_issues.jsonl';result={}
 if not path.exists():return result
 for line in path.read_text().splitlines():
  try:
   event=json.loads(line);result[event['document']+':'+str(event['page'])]=event
  except (ValueError,KeyError):continue
 return result

def save(root,data):
 ident=data['document'];page=data['page']
 if not isinstance(ident,str) or type(page) is not int:raise ValueError('Invalid page')
 doc,prefix=review.locate(root,ident,page)
 status=data.get('status','open');reason=data.get('reason','other');reporter=data.get('reporter','');note=data.get('note','')
 if status not in ('open','resolved') or reason not in REASONS:raise ValueError('Invalid issue')
 if not isinstance(reporter,str) or not reporter.strip() or len(reporter)>200 or not isinstance(note,str) or len(note)>5000:raise ValueError('Reporter and valid note required')
 with LOCK:
  old=index(root).get(ident+':'+str(page))
  if status=='resolved' and not old:raise ValueError('No report to resolve')
  event=dict(id=uuid.uuid4().hex,document=ident,source=doc['source'],page=page,status=status,reason=reason,note=note,reporter=reporter.strip(),created=old['created'] if old and old['status']=='open' else time.time(),updated=time.time())
  path=root/'user_issues.jsonl'
  with path.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 return event
