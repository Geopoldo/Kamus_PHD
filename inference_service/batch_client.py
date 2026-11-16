"""Submit multiple documents and download results; persistent client manifest."""
import argparse,hashlib,json,os,time,urllib.error,urllib.request
from pathlib import Path
MAX_BYTES=30*1024*1024

def save(path,state):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def request(base,path,data=None):
 headers={'Content-Type':'application/octet-stream'}
 with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=120) as response:return response.read()

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('files',nargs='*',type=Path)
 ap.add_argument('--folder',type=Path,help='PDF/PNG/JPEG files directly inside this folder')
 ap.add_argument('--output-dir',type=Path,default=Path('ocr-results'))
 ap.add_argument('--interval',type=float,default=5)
 args=ap.parse_args()
 base=os.environ['OCR_API_URL'].rstrip('/')
 out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True);manifest=out/'batch_manifest.json'
 state=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {'server':base,'files':[]}
 if state['server']!=base:raise SystemExit('Manifest belongs to another server. Use another output directory.')
 files=list(args.files)
 if args.folder:files+=sorted(p for p in args.folder.iterdir() if p.is_file() and p.suffix.lower() in ('.pdf','.png','.jpg','.jpeg'))
 known={(r['path'],r['sha256']) for r in state['files']}
 for path in files:
  path=path.resolve()
  if not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES:raise SystemExit(f'Invalid file or size >30 MiB: {path}')
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if (str(path),digest) not in known:
   state['files'].append(dict(path=str(path),sha256=digest,status='pending',job_id=None));known.add((str(path),digest))
 if not state['files']:raise SystemExit('Specify files or --folder, or resume an existing output directory.')
 save(manifest,state)
 while True:
  active=sum(r['status'] in ('queued','processing') for r in state['files'])
  for row in state['files']:
   if row['status']=='pending' and active<20:
    path=Path(row['path']);body=path.read_bytes()
    if hashlib.sha256(body).hexdigest()!=row['sha256']:raise SystemExit(f'File changed: {path}')
    # Mark BEFORE POST: a lost response must never trigger a duplicate automatically.
    row['status']='submission_uncertain';save(manifest,state)
    try:job=json.loads(request(base,'/v1/jobs',body))
    except urllib.error.HTTPError as e:
     if e.code==429:
      row['status']='pending';save(manifest,state);break
     row['error']=f'HTTP {e.code}';save(manifest,state);raise
    row.update(job_id=job['job_id'],status='queued');active+=1;save(manifest,state)
    print(f"Submitted {path.name}: {row['job_id']}",flush=True)
   if row['job_id'] and row['status'] in ('queued','processing','complete','partial'):
    job=json.loads(request(base,'/v1/jobs/'+row['job_id']))
    row['status']=job['status'];row['error']=job.get('error');save(manifest,state)
    print(f"{Path(row['path']).name}: {row['status']}",flush=True)
    if row['status'] in ('complete','partial'):
     prefix=out/(Path(row['path']).stem+'-'+row['job_id'])
     for endpoint,suffix in [('result','.json'),('markdown','.md')]:
      body=request(base,f"/v1/jobs/{row['job_id']}/{endpoint}")
      path=prefix.with_name(prefix.name+suffix);path.write_bytes(body)
     row['server_status']=row['status'];row['status']='downloaded';save(manifest,state)
  if not any(r['status'] in ('pending','queued','processing','complete','partial') for r in state['files']):break
  time.sleep(max(1,args.interval))
 summary={s:sum(r['status']==s for r in state['files']) for s in ['downloaded','failed','submission_uncertain']}
 print(json.dumps(summary),flush=True)
 if summary['submission_uncertain']:print('A submission has no confirmed ID. Ask the owner to inspect the queue before resubmitting.',flush=True)
 return 1 if summary['failed'] or summary['submission_uncertain'] else 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except (OSError,urllib.error.URLError) as e:raise SystemExit(f'{e}\nResume with the same --output-dir. Do not delete batch_manifest.json.')
