"""One resumable local pipeline, using the existing OCR/auditors and GPU lock."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

import sources


def execute(root, key, runner=None, recalculate=None):
    if not __import__('re').fullmatch('[a-f0-9]{32}', key): raise ValueError('Invalid job')
    directory=root/'sources'/'jobs'/key
    with sources.lock(root, blocking=True) as held:
        job=sources.read(directory/'job.json'); catalog=sources.metadata(root)
        def save(stage, **fields):
            job.update(stage=stage, updated=time.time(), **fields)
            sources.write(directory/'job.json',job);sources.write(root/'sources'/'job.json',job)
            sources.audit(root,'source_pipeline_stage',job=key,stage=stage,status=job['status'])
        save('inventory',status='running')
        for name in job['documents']:
            catalog['items'].setdefault(sources.ident(name),{})['pipeline_status']='running'
        sources.write(root/'sources'/'catalog.json',catalog)
        env=dict(os.environ,MAPH_SOURCE_ROOT=str(sources.base(root)),MAPH_RESULTS_ROOT=str(root.resolve()),
                 MAPH_SOURCE_SCOPE=str(directory/'scope.json'),MAPH_SOURCE_LOCK_FD=str(held.fileno()))
        env.pop('NOTIFY_SOCKET',None); env['PYTHONUNBUFFERED']='1'
        def run(command):
            if runner is not None:return runner(command,env)
            child=subprocess.Popen(command,env=env,pass_fds=(held.fileno(),),start_new_session=True)
            try:
                while child.poll() is None:
                    job['heartbeat']=time.time();sources.write(directory/'job.json',job);sources.write(root/'sources'/'job.json',job)
                    time.sleep(2)
                if child.returncode:raise RuntimeError('Una etapa no pudo terminar. Consulta el registro del proceso y vuelve a continuar.')
            finally:
                if child.poll() is None:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=20)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        try:
            if not job['refresh_only']:
                save('transcription');run([sys.executable,str(sources.HERE/'run.py')])
            save('rules_audit')
            run([sys.executable,str(sources.HERE/'audit'/'run.py'),'--root',str(root),'--run-id','sources_'+key])
            save('model_audit')
            run([sys.executable,str(sources.HERE/'audit'/'model_run.py'),'--run-id','sources_'+key,'--incremental','--scope',str(directory/'scope.json')])
            save('cross_analysis')
            if recalculate is not None:recalculate()
            else:
                url=job['dashboard_url']
                def request(path,body=None):
                    data=json.dumps(body).encode() if body is not None else None
                    req=urllib.request.Request(url+path,data=data,headers={'Content-Type':'application/json','Origin':url})
                    with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)
                for attempt in range(3):
                    request('/priorities-run',{'reason':'sources_updated'})
                    while True:
                        value=request('/priorities')
                        if not value['job'].get('running'):break
                        job['heartbeat']=time.time();sources.write(root/'sources'/'job.json',job);time.sleep(2)
                    if value['job'].get('error'):raise RuntimeError('No se pudo actualizar el análisis: '+value['job']['error'])
                    if not value.get('stale'):break
                else:raise RuntimeError('Las transcripciones cambiaron durante el análisis. Vuelve a actualizarlo.')
            progress=sources.read(root/'progress.json');catalog=sources.metadata(root)
            failed=[]
            for doc in progress['documents']:
                if doc['source'] not in job['documents']:continue
                incomplete=any(p['status'] not in ('complete','needs_review') for p in doc['pages']) or not doc['pages']
                catalog['items'].setdefault(sources.ident(doc['source']),{})['pipeline_status']='partial' if incomplete else 'complete'
                if incomplete:failed.append(doc['source'])
            sources.write(root/'sources'/'catalog.json',catalog)
            save('complete',status='partial' if failed else 'complete',finished=time.time(),failed_documents=failed,
                 message='Proceso automático terminado. La revisión humana sigue pendiente.' if not failed else 'Algunas páginas fallaron. Sus resultados anteriores se conservan; puedes continuar las fuentes pendientes.')
        except BaseException as error:
            catalog=sources.metadata(root)
            for name in job['documents']:catalog['items'].setdefault(sources.ident(name),{})['pipeline_status']='failed'
            sources.write(root/'sources'/'catalog.json',catalog)
            save(job['stage'],status='interrupted' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'failed',finished=time.time(),error=str(error))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--job',required=True);args=parser.parse_args()
    def stop(signum,frame):raise SystemExit('Proceso interrumpido; las páginas guardadas se conservan.')
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    execute(args.root.resolve(),args.job)
