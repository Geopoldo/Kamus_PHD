"""Record reproducibility evidence without transmitting any data."""
import hashlib,json,os,platform,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parent;OUT=ROOT/'results/second_reading/pilot_01'
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def command(args):
 try:return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT,timeout=20).strip()
 except Exception as e:return str(e)
def main():
 m=json.loads((OUT/'manifest.json').read_text());archive=OUT/'reproduction';archive.mkdir(exist_ok=True);files={}
 for p in [ROOT/'second_reading/run.py',ROOT/'second_reading/report.py',ROOT/'second_reading/provenance.py',PROJECT/'benchmark/run_qwen.py']:
  name=('benchmark_' if p.parent.name=='benchmark' else '')+p.name;dest=archive/name
  if not dest.exists():shutil.copy2(p,dest)
  files[str(p.relative_to(PROJECT))]=dict(sha256=digest(dest),archived_as=name)
 args=m['command'];binaries=[Path(args[0]),Path(args[args.index('-m')+1]),Path(args[args.index('--mmproj')+1])]
 for p in binaries:files[str(p)]=dict(sha256=digest(p),bytes=p.stat().st_size)
 record=dict(recorded=time.time(),run_id='pilot_01',python=sys.version,python_executable=sys.executable,platform=platform.platform(),machine=platform.machine(),cpu=command(['lscpu']),gpu=command(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader']),engine_version=command([args[0],'--version']),files=files,request_config=dict(temperature=0,seed=42,max_tokens=4096,stream=False,cache_prompt=False,visual_tokens=4096,context=8192,gpu_layers=48,cpu_threads=8,concurrency=1,timeout_seconds=600),input_policy='Saved 3000px PNGs used unchanged; SHA256 in manifest.json; no reference transcription supplied.',limits=dict(preflight_ram_gib=12,preflight_vram_mib=14000,monitor_min_ram_gib=4,monitor_min_vram_mib=1024,max_temperature_c=88,monitor_interval_seconds=3,total_runtime_seconds=2100),determinism_note='Same inputs, weights and seed improve reproducibility but CUDA/backend changes can change generated text. Preserve recorded outputs as evidence; do not promise bitwise identity.')
 tmp=OUT/'provenance.json.tmp';tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2));tmp.replace(OUT/'provenance.json');print('Provenance archived; hashes recorded:',len(files))
if __name__=='__main__':main()
