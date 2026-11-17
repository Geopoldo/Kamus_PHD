"""Measured, read-only re-inventory: recursive discovery, SHA-256 and pdfinfo.

Writes a new research record only. Never rewrites progress, sources or transcriptions.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import signal
import subprocess
import threading
import time
import uuid

import embeddings
import sources


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


@contextlib.contextmanager
def source_lock(root):
    inherited=os.environ.get('MAPH_SOURCE_LOCK_FD')
    if inherited:
        with os.fdopen(os.dup(int(inherited)),'a') as held:
            expected=root/'sources/management.lock'
            if os.fstat(held.fileno()).st_ino!=expected.stat().st_ino:
                raise ValueError('Invalid inherited source lock')
            yield
    else:
        with sources.lock(root,blocking=True):
            yield


def measure_resources(child=None):
    memory=dict((k,int(v.split()[0])) for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines()))
    result=dict(time=time.time(),ram_available_gib=memory['MemAvailable']/1048576,
                process_rss_mib=0,process_cpu_seconds=0,process_read_bytes=0,process_write_bytes=0)
    for pid in [os.getpid()]+([child] if child else []):
        try:
            fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            result['process_rss_mib']+=int(fields[21])*os.sysconf('SC_PAGE_SIZE')/1048576
            # CPU samples use worker only, avoiding resets as short-lived pdfinfo children exit.
            if pid==os.getpid():result['process_cpu_seconds']=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
            io=dict((k,int(v)) for k,v in (line.split(':') for line in Path(f'/proc/{pid}/io').read_text().splitlines()))
            result['process_read_bytes']+=io['read_bytes'];result['process_write_bytes']+=io['write_bytes']
        except (OSError,ValueError):pass
    return result


def execute(root,reason='remeasurement',source_root=None):
    root=root.resolve();source=(source_root or sources.base(root)).resolve()
    if not source.is_dir():raise ValueError('No existe la carpeta de fuentes')
    key=uuid.uuid4().hex;directory=root/'inventories'/key
    started=time.monotonic();wall=time.time()
    baseline_self=resource.getrusage(resource.RUSAGE_SELF);baseline_children=resource.getrusage(resource.RUSAGE_CHILDREN)
    manifest=dict(run_id=key,status='running',reason=reason,started=wall,updated=wall,
        source_root=str(source),model='Recorrido local + SHA-256 + pdfinfo',processed=0,total=0,documents=0,folders=0,inventory_pages=0,
        policy='New read-only measurement; not a reconstruction of the original inventory duration. Read every PDF, stream SHA-256, read page count with pdfinfo, compare with the saved catalog. No OCR or image regeneration.',
        code_sha256=sha(Path(__file__)),python=platform.python_version(),platform=platform.platform(),
        telemetry_interval_seconds=.25,telemetry_scope='RSS includes worker and live pdfinfo. CPU percent samples cover worker; final CPU seconds include worker and child tools. Disk I/O is OS physical I/O; cached file reads may be zero. System RAM is shared. GPU samples are whole-card observations; this process performs no GPU inference.')
    embeddings.write(directory/'manifest.json',manifest);embeddings.write(root/'inventory_latest.json',dict(run_id=key))
    shutil.copy2(__file__,directory/'inventory_audit.py')
    def save():
        manifest.update(updated=time.time(),elapsed_seconds=time.monotonic()-started)
        embeddings.write(directory/'manifest.json',manifest)
    stop=threading.Event();live={'pid':None,'source':None};samples=[]
    def sample():
        value=measure_resources(live['pid']);value['current']=live['source'];value['stage']='inventory'
        if samples:
            dt=value['time']-samples[-1]['time']
            if dt>0:value['process_cpu_percent']=max(0,(value['process_cpu_seconds']-samples[-1]['process_cpu_seconds'])/dt*100)
        samples.append(value)
        with (directory/'telemetry.jsonl').open('a') as handle:handle.write(json.dumps(value)+'\n');handle.flush()
    def monitor():
        while not stop.wait(.25):
            try:sample()
            except Exception as error:
                with (directory/'events.jsonl').open('a') as handle:handle.write(json.dumps(dict(time=time.time(),event='telemetry_error',error=str(error)))+'\n')
    thread=threading.Thread(target=monitor,daemon=True)
    rows=[];folders=set();errors=[];skipped=[];child=None
    try:
        sample();thread.start()
        try:
            version=subprocess.run(['pdfinfo','-v'],capture_output=True,text=True,timeout=10)
            manifest['pdfinfo_version']=(version.stdout+version.stderr).splitlines()[0]
        except (OSError,subprocess.SubprocessError):manifest['pdfinfo_version']='unavailable'
        waiting=time.monotonic()
        with source_lock(root):
            manifest['lock_wait_seconds']=time.monotonic()-waiting
            discovery=time.monotonic();candidates=[]
            for directory_name,dirs,files in os.walk(source,followlinks=False):
                base=Path(directory_name)
                for name in list(dirs):
                    if (base/name).is_symlink():dirs.remove(name);skipped.append(str((base/name).relative_to(source)))
                for name in files:
                    path=base/name
                    if path.suffix.lower()!='.pdf':continue
                    if path.is_symlink():skipped.append(str(path.relative_to(source)));continue
                    candidates.append(path)
                    folders.update(str(parent) for parent in path.relative_to(source).parents if str(parent)!='.')
            candidates.sort();manifest.update(discovery_seconds=time.monotonic()-discovery,total=len(candidates),folders=len(folders))
            prior={d['source']:d for d in embeddings.read(root/'progress.json').get('documents',[])}
            for path in candidates:
                before=time.monotonic();name=str(path.relative_to(source));live['source']=name
                record=dict(source=name,folder=str(path.relative_to(source).parent),started=time.time(),status='complete')
                try:
                    stat=path.stat();record['bytes']=stat.st_size
                    began=time.monotonic();record['sha256']=sha(path);record['hash_seconds']=time.monotonic()-began
                    began=time.monotonic()
                    child=subprocess.Popen(['pdfinfo',str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,LC_ALL='C'))
                    live['pid']=child.pid
                    try:stdout,stderr=child.communicate(timeout=60)
                    except subprocess.TimeoutExpired:child.kill();child.communicate();raise RuntimeError('pdfinfo excedió 60 segundos')
                    record['pdfinfo_seconds']=time.monotonic()-began
                    if child.returncode:raise ValueError('pdfinfo no pudo leer el PDF: '+stderr[-1000:])
                    match=re.search(r'^Pages:\s+(\d+)',stdout,re.M)
                    if not match:raise ValueError('pdfinfo no devolvió un número de páginas')
                    record['page_count']=int(match[1])
                    after=path.stat()
                    if (stat.st_ino,stat.st_size,stat.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('El archivo cambió durante la medición')
                    old=prior.get(name)
                    record['catalog_comparison']='new' if not old else 'unchanged' if old.get('sha256')==record['sha256'] and old.get('page_count')==record['page_count'] else 'changed'
                    manifest['inventory_pages']+=record['page_count'];manifest['documents']+=1
                except Exception as error:
                    record.update(status='failed',error=str(error));errors.append(dict(source=name,error=str(error)))
                finally:
                    if child and child.poll() is None:child.terminate();child.wait(timeout=10)
                    child=None;live['pid']=None
                record['seconds']=time.monotonic()-before;rows.append(record);manifest['processed']+=1
                with (directory/'files.jsonl').open('a') as handle:handle.write(json.dumps(record,ensure_ascii=False)+'\n');handle.flush()
                save()
            manifest['missing_from_disk']=sorted(set(prior)-{str(p.relative_to(source)) for p in candidates})
            manifest['changed_from_catalog']=[r['source'] for r in rows if r.get('catalog_comparison')=='changed']
            manifest['new_to_catalog']=[r['source'] for r in rows if r.get('catalog_comparison')=='new']
        manifest.update(status='partial' if errors or skipped or manifest['missing_from_disk'] else 'complete',errors=errors,skipped_links=skipped,
                        scan_seconds=time.monotonic()-started,total_bytes=sum(r.get('bytes',0) for r in rows),
                        hashing_seconds=sum(r.get('hash_seconds',0) for r in rows),pdfinfo_seconds=sum(r.get('pdfinfo_seconds',0) for r in rows))
    except BaseException as error:
        manifest.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',error=str(error))
        raise
    finally:
        stop.set()
        if thread.ident:thread.join(timeout=2)
        live['source']=None;live['pid']=None;sample()
        now=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
        manifest.update(finished=time.time(),worker_cpu_seconds=(now.ru_utime+now.ru_stime)-(baseline_self.ru_utime+baseline_self.ru_stime),
            tools_cpu_seconds=(children.ru_utime+children.ru_stime)-(baseline_children.ru_utime+baseline_children.ru_stime),
            telemetry_samples=len(samples),peak_process_rss_mib=max(s['process_rss_mib'] for s in samples),
            file_read_cache_note='The OS page cache was not flushed. This is a new measurement under current machine conditions.')
        embeddings.write(directory/'files.json',rows);save()
        with (directory/'events.jsonl').open('a') as handle:handle.write(json.dumps(dict(time=time.time(),event='inventory_'+manifest['status'],run_id=key,elapsed_seconds=manifest['elapsed_seconds']))+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'results');parser.add_argument('--source-root',type=Path);parser.add_argument('--reason',choices=('remeasurement','source_pipeline'),default='remeasurement');args=parser.parse_args()
    def stop(signum,frame):raise SystemExit('Inventario interrumpido; se conserva el registro parcial')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    result=execute(args.root,args.reason,args.source_root)
    print(json.dumps({k:result[k] for k in ('run_id','status','documents','inventory_pages','folders','elapsed_seconds','hashing_seconds','pdfinfo_seconds','peak_process_rss_mib')},indent=2))
    if result['status']!='complete':raise SystemExit(1)
