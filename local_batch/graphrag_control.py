"""Durable user intent, worker status and priority for interactive GPU questions."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
from embeddings import read, write


def directory(root): return Path(root)/'knowledge_graph/pilot_30'
def event(root, kind, **values):
    path=directory(root)/'control_events.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as stream:
        stream.write(json.dumps(dict(time=time.time(),event=kind,**values),ensure_ascii=False)+'\n')

def state(root):
    d=directory(root);value=read(d/'worker.json');intent=read(d/'control.json')
    value['desired']=intent.get('desired','running')
    try: value['alive']=Path(f"/proc/{value['pid']}/stat").read_text().rsplit(')',1)[1].split()[19]==value['process_start']
    except (OSError,KeyError):value['alive']=False
    if value['desired']=='paused' and value.get('status') not in ('paused','error'):value['status']='stopping'
    if not value['alive'] and value.get('status') not in ('paused','complete','error'):value['status']='offline'
    return value


def request(root,payload):
    action=payload.get('action')
    if action not in ('pause','resume'):raise ValueError('Acción no válida')
    d=directory(root);d.mkdir(parents=True,exist_ok=True)
    with (d/'control.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        write(d/'control.json',dict(desired='paused' if action=='pause' else 'running',requested=time.time()))
        event(root,'user_'+action)
        if action=='resume' and not state(root)['alive']:
            python=Path(__file__).resolve().parent.parent/'.venv-graphrag/bin/python'
            with (d/'blocks-worker.log').open('a') as log:
                subprocess.Popen([str(python),str(Path(__file__).with_name('graphrag_blocks.py'))],stdout=log,stderr=log,start_new_session=True)
    return state(root)


def interactive_jobs(root):
    """Use each job's own liveness check; abandoned queued jobs never hold the queue."""
    import graphrag_queries, reading_matrix, hypotheses_auto
    result=[]
    for pattern,module,active in [('knowledge_graph/questions/*/question.json',graphrag_queries,graphrag_queries.ACTIVE),('matrices/*/matrix.json',reading_matrix,reading_matrix.ACTIVE),('hypotheses/auto/*/job.json',hypotheses_auto,{'queued','waiting_gpu','loading','running'})]:
        for p in Path(root).glob(pattern):
            try:
                if read(p).get('status') not in active:continue
                job=module.get(root,p.parent.name)
                if job.get('status') in active:result.append(dict(id=p.parent.name,kind=module.__name__,status=job['status']))
            except (ValueError,KeyError,OSError):continue
    return result
