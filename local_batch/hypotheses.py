"""Local, versioned research hypotheses. User assertions are not model findings."""
import json, os, threading, time
from pathlib import Path
LOCK=threading.Lock()
def load(root):
 p=Path(root)/'hypotheses'/'current.json'
 return json.loads(p.read_text()) if p.exists() else {'revision':0,'question':'','author':'','branches':[],'history':[]}
def save(root,payload):
 with LOCK:
  previous=load(root)
  if payload.get('revision')!=previous['revision']:raise ValueError('Revision conflict: reload before saving')
  question=payload.get('question');author=payload.get('author');branches=payload.get('branches')
  if not isinstance(question,str) or not question.strip() or len(question)>2000:raise ValueError('Question required (max 2000)')
  if not isinstance(author,str) or not author.strip() or len(author)>160:raise ValueError('Author required (max 160)')
  if not isinstance(branches,list) or len(branches)>30:raise ValueError('Maximum 30 branches')
  for branch in branches:
   if not isinstance(branch,dict) or not isinstance(branch.get('label'),str) or not branch['label'].strip() or len(branch['label'])>250:raise ValueError('Invalid branch')
   items=branch.get('items')
   if not isinstance(items,list) or len(items)>100:raise ValueError('Maximum 100 hypotheses per branch')
   for item in items:
    if not isinstance(item,dict) or not isinstance(item.get('text'),str) or not item['text'].strip() or len(item['text'])>5000:raise ValueError('Invalid hypothesis')
    if item.get('status') not in ('explore','evidence','contradicted','reviewed'):raise ValueError('Invalid status')
    if not isinstance(item.get('evidence'),list) or len(item['evidence'])>200:raise ValueError('Invalid evidence')
    for record in item['evidence']:
     if not isinstance(record,dict) or not isinstance(record.get('document_id'),str) or not isinstance(record.get('document'),str) or not isinstance(record.get('page'),int) or record['page']<1 or not isinstance(record.get('version'),str):raise ValueError('Invalid source reference')
  now=time.time();revision=previous['revision']+1
  value={'revision':revision,'question':question.strip(),'author':author.strip(),'branches':branches,'updated':now,'generation':payload.get('generation'),'query_id':payload.get('query_id'),'query_kind':payload.get('query_kind'),'session_id':payload.get('session_id'),'history':previous['history']+[{'revision':revision,'author':author.strip(),'time':now}]}
  folder=Path(root)/'hypotheses';folder.mkdir(exist_ok=True,parents=True)
  raw=json.dumps(value,ensure_ascii=False,indent=2);(folder/f'revision-{revision}.json').write_text(raw)
  temp=folder/'current.tmp';temp.write_text(raw);os.replace(temp,folder/'current.json')
  return value
