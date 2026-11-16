"""Local operational events. No document text or environment secrets are recorded."""
import fcntl,json,os,socket,time,uuid
from pathlib import Path
ROOT=Path(os.environ.get('MAPH_RESULTS_ROOT',Path(__file__).resolve().parent/'results'))
SESSION=uuid.uuid4().hex

def event(kind,**fields):
 ROOT.mkdir(exist_ok=True)
 record=dict(time=time.time(),event=kind,session=SESSION,pid=os.getpid(),ppid=os.getppid(),invocation=os.environ.get('INVOCATION_ID'),**fields)
 with (ROOT/'events.jsonl').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX);f.write(json.dumps(record,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())

def notify(message):
 address=os.environ.get('NOTIFY_SOCKET')
 if not address:return
 if address.startswith('@'):address='\0'+address[1:]
 with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as s:s.connect(address);s.sendall(message.encode())

if __name__=='__main__':
 event('service_exit',service_result=os.environ.get('SERVICE_RESULT'),exit_code=os.environ.get('EXIT_CODE'),exit_status=os.environ.get('EXIT_STATUS'))

def status():
 import subprocess
 selected=[]
 try:
  for line in (ROOT/'events.jsonl').read_text().splitlines():
   try:
    r=json.loads(line)
    if r.get('event') not in ('page_started','page_saved'):selected.append({k:r.get(k) for k in ['time','event','pid','session','signal','reason','error','service_result','exit_code','exit_status','previous_processed']})
   except ValueError:pass
 except OSError:pass
 manager={}
 for unit in ['maph-ocr-batch.service','maph-ocr-dashboard.service']:
  try:
   raw=subprocess.check_output(['systemctl','--user','show',unit,'--property=ActiveState,SubState,Result,NRestarts,MainPID,WatchdogUSec'],text=True,timeout=3)
   manager[unit]=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
  except (OSError,subprocess.SubprocessError):manager[unit]={'ActiveState':'unknown'}
 return dict(updated=time.time(),services=manager,events=selected[-40:],note='Signal sender is not identified by the Python handler; systemd result and process context provide additional evidence. SIGKILL/power loss cannot be logged by the killed process.')
