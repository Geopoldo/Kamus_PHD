"""Private OCR API, Python standard library; one durable sequential worker."""
import argparse, ipaddress, json, os, sqlite3, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
DATA=ROOT/'data'
MAX_BYTES=30*1024*1024

def db():
 c=sqlite3.connect(DATA/'jobs.sqlite',timeout=30);c.row_factory=sqlite3.Row;return c

def initialize():
 DATA.mkdir(mode=0o700,exist_ok=True)
 with db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT,error TEXT,created REAL)')
  c.execute("UPDATE jobs SET status='failed',error='Service restarted; submit again' WHERE status='processing'")

def worker():
 while True:
  with db() as c:
   row=c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
   if row:c.execute("UPDATE jobs SET status='processing' WHERE id=?",(row['id'],))
  if not row:time.sleep(1);continue
  jid=row['id'];folder=DATA/jid
  try:
   source=folder/'input';images=folder/'images';images.mkdir(exist_ok=True)
   if source.read_bytes()[:5]==b'%PDF-':
    subprocess.run(['pdftoppm','-f','1','-l','51','-scale-to','2200','-png',str(source),str(images/'page')],check=True,timeout=180,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    paths=sorted(images.glob('*.png'))
    if len(paths)>50:raise ValueError('PDF limit: 50 pages')
   else:
    from PIL import Image,ImageOps
    Image.MAX_IMAGE_PIXELS=25_000_000
    with Image.open(source) as im:
     if im.width*im.height>25_000_000:raise ValueError('Image too large')
     ImageOps.exif_transpose(im).convert('RGB').save(images/'page.png')
    paths=[images/'page.png']
   if not paths:raise ValueError('No pages')
   cfg=json.loads((PROJECT/'benchmark/prompt_trial/pilot.json').read_text())
   cfg.update(max_runtime_seconds=3300,models=['qwen3.5-9b'],variant='baseline_original',samples={f'page_{i:03}':str(p) for i,p in enumerate(paths,1)})
   config=folder/'config.json';config.write_text(json.dumps(cfg))
   with (folder/'worker.log').open('w') as log:
    subprocess.run([sys.executable,str(PROJECT/'benchmark/prompt_trial/run.py'),'--execute','--config',str(config),'--run-id','api-'+jid],stdout=log,stderr=log,check=True,timeout=3600)
   run=PROJECT/'benchmark/experiments/prompt_pilot_v1'/('api-'+jid)
   pages=[]
   for name in cfg['samples']:
    meta=json.loads((run/'metadata/baseline_original/qwen3.5-9b'/f'{name}.json').read_text())
    raw=run/'raw/baseline_original/qwen3.5-9b'/f'{name}.txt'
    pages.append(dict(page=name,text=raw.read_text() if raw.exists() else '',status=meta['status'],finish_reason=meta.get('finish_reason'),review_status='unreviewed'))
   result=dict(job_id=jid,model='qwen3.5-9b',pages=pages)
   (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
   status='complete' if all(p['status']=='complete' for p in pages) else 'partial'
   with db() as c:c.execute('UPDATE jobs SET status=? WHERE id=?',(status,jid))
  except Exception as e:
   with db() as c:c.execute("UPDATE jobs SET status='failed',error=? WHERE id=?",(str(e)[:500],jid))

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,value,kind='application/json'):
  body=json.dumps(value,ensure_ascii=False).encode() if kind=='application/json' else value.encode()
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def allowed(self):
  address=ipaddress.ip_address(self.client_address[0])
  if not any(address in network for network in ALLOWED_NETWORKS):
   self.reply(403,{'error':'Client outside allowed intranet'});return False
  return True
 def do_GET(self):
  if not self.allowed():return
  parts=self.path.split('?')[0].strip('/').split('/')
  if parts==['health']:return self.reply(200,{'status':'ok','gpu_concurrency':1})
  if len(parts)<3 or parts[:2]!=['v1','jobs']:return self.reply(404,{})
  with db() as c:row=c.execute('SELECT * FROM jobs WHERE id=?',(parts[2],)).fetchone()
  if not row:return self.reply(404,{})
  if len(parts)==3:return self.reply(200,dict(row))
  result=DATA/row['id']/'result.json'
  if not result.exists():return self.reply(409,{'status':row['status']})
  obj=json.loads(result.read_text())
  if parts[3]=='result':return self.reply(200,obj)
  if parts[3]=='markdown':return self.reply(200,'\n\n'.join('# '+p['page']+'\n\n'+p['text'] for p in obj['pages']),'text/markdown; charset=utf-8')
  self.reply(404,{})
 def do_POST(self):
  if not self.allowed():return
  if self.path!='/v1/jobs':return self.reply(404,{})
  try:length=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.reply(400,{})
  if not 0<length<=MAX_BYTES:return self.reply(413,{'error':'File limit 30 MiB; Content-Length required'})
  with db() as c:
   if c.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','processing')").fetchone()[0]>=20:return self.reply(429,{'error':'Queue full'})
  self.connection.settimeout(60)
  jid=uuid.uuid4().hex;folder=DATA/jid;folder.mkdir()
  try:
   body=self.rfile.read(length)
   if len(body)!=length:raise ValueError('Incomplete upload')
   (folder/'input').write_bytes(body)
   with db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?)',(jid,'queued',None,time.time()))
   self.reply(202,{'job_id':jid,'status':'queued'})
  except (OSError,ValueError):self.reply(400,{'error':'Upload failed'})

if __name__=='__main__':
 import fcntl
 ap=argparse.ArgumentParser();ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=8090);ap.add_argument('--no-worker',action='store_true');ap.add_argument('--allow-network',action='append',default=[],help='Allowed client CIDR; loopback is always allowed');args=ap.parse_args()
 ALLOWED_NETWORKS=[ipaddress.ip_network(n) for n in ['127.0.0.0/8',*args.allow_network]]
 DATA.mkdir(exist_ok=True);lock=(DATA/'service.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 initialize()
 server=ThreadingHTTPServer((args.host,args.port),Handler)
 if not args.no_worker:threading.Thread(target=worker,daemon=True).start()
 print(f'Listening {args.host}:{args.port}; intranet mode: no authentication',flush=True)
 server.serve_forever()
