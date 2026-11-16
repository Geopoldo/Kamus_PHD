"""Usage: OCR_API_URL=http://private-address:8090 python3 client.py file.pdf"""
import argparse,json,os,time,urllib.request
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('file',type=Path);ap.add_argument('--output',type=Path,default=Path('ocr-result.json'));args=ap.parse_args()
base=os.environ['OCR_API_URL'].rstrip('/');headers={}
def call(path,data=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=120))
job=call('/v1/jobs',args.file.read_bytes())['job_id'];print('Job:',job,flush=True)
while True:
 state=call('/v1/jobs/'+job);print(state['status'],flush=True)
 if state['status'] in ('complete','partial'):break
 if state['status']=='failed':raise SystemExit(state.get('error','Failed'))
 time.sleep(5)
args.output.write_text(json.dumps(call('/v1/jobs/'+job+'/result'),ensure_ascii=False,indent=2),encoding='utf-8');print(args.output)
