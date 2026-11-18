"""Cumulative local graph releases, user pause and preemption for interactive questions."""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import graphrag_pilot as pilot
import graphrag_control as control
from graphrag_checkpoint import publish_checkpoint
from embeddings import read, write


def stop_child(child):
    """Interrupt only this build's process group, never a question's model."""
    if child.poll() is None:
        child.send_signal(signal.SIGINT)
        try: child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
    # Ensure an orphaned model in this dedicated session is gone before publishing.
    try: os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError: pass


def main():
    pilot.PILOT.mkdir(parents=True,exist_ok=True)
    with (pilot.PILOT/'worker.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 0
        return work()


def work():
    state_path=pilot.PILOT/'blocks.json'
    ident=dict(pid=os.getpid(),process_start=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19])
    def status(name,**values):
        write(pilot.PILOT/'worker.json',dict(ident,status=name,updated=time.time(),**values))
    def paused():return read(pilot.PILOT/'control.json').get('desired')=='paused'
    child=None;last_reason=None
    def interrupted(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    try:
        while True:
            jobs=control.interactive_jobs(pilot.ROOT)
            if paused() or jobs:
                reason='paused' if paused() else 'waiting_questions'
                status(reason,priority_jobs=jobs,gpu_released=True)
                if reason!=last_reason:control.event(pilot.ROOT,reason,priority_jobs=jobs);last_reason=reason
                time.sleep(2);continue
            if last_reason=='waiting_questions':
                # Allow chained fishbone work to enter the queue after an answer.
                time.sleep(3)
                if paused() or control.interactive_jobs(pilot.ROOT):continue
            last_reason=None
            status('preparing');pilot.prepare(all_pages=True)
            snapshot=read(pilot.PILOT/'inputs.json')
            active=read(pilot.PILOT/'active.json').get('run_id','')
            previous=read(pilot.PILOT/'runs'/active/'inputs.json').get('records',[])
            ready={(r['document_id'],r['page']):r for r in previous}
            retained,pending=[],[]
            for row in snapshot['records']:
                old=ready.get((row['document_id'],row['page']))
                (retained if old and old['text_sha256']==row['text_sha256'] else pending).append(row)
            if not pending:
                write(state_path,dict(status='complete',published_pages=len(retained),total_pages=len(retained),updated=time.time()))
                status('complete',gpu_released=True);return 0
            selected=retained+pending[:80]
            snapshot.update(records=selected,scope='partial_processed_pages' if len(pending)>80 else 'available_corpus')
            write(pilot.PILOT/'inputs.json',snapshot)
            state=dict(status='running',block_size=80,published_pages=len(retained),target_pages=len(selected),total_pages=len(retained)+len(pending),added_pages=min(80,len(pending)),started=time.time(),updated=time.time())
            write(state_path,state)
            # Recheck after scanning sources: a question may have arrived meanwhile.
            if paused() or control.interactive_jobs(pilot.ROOT):continue
            child=subprocess.Popen([sys.executable,str(Path(pilot.__file__)),'--run','--publish'],start_new_session=True)
            control.event(pilot.ROOT,'build_started',target_pages=len(selected),child_pid=child.pid)
            reason=None
            while child.poll() is None:
                jobs=control.interactive_jobs(pilot.ROOT)
                if paused() or jobs:
                    reason='paused' if paused() else 'waiting_questions'
                    status('stopping',reason=reason,priority_jobs=jobs,gpu_released=False)
                    control.event(pilot.ROOT,'build_preempted',reason=reason,priority_jobs=jobs)
                    stop_child(child);break
                status('running',child_pid=child.pid,gpu_released=False)
                time.sleep(2)
            result=child.returncode;child=None
            if reason:
                status('publishing',reason=reason,gpu_released=True)
                try:
                    checkpoint=publish_checkpoint(pilot.ROOT)
                    control.event(pilot.ROOT,'checkpoint_published',checkpoint=checkpoint)
                    state.update(status=reason,checkpoint=checkpoint,updated=time.time());write(state_path,state)
                    status(reason,checkpoint=checkpoint,gpu_released=True)
                except Exception as error:
                    control.event(pilot.ROOT,'checkpoint_failed',error=str(error))
                    # Keep evidence and the previous graph; expose the failure instead of claiming publication.
                    write(pilot.PILOT/'control.json',dict(desired='paused',requested=time.time()))
                    status('error',error=str(error),gpu_released=True)
                    return 1
                last_reason=reason;continue
            state.update(status='published' if result==0 else 'stopped',returncode=result,updated=time.time());write(state_path,state)
            if result:
                status('error',error='Build failed; saved extractions are retained.',gpu_released=True);return result
            control.event(pilot.ROOT,'block_published',pages=len(selected))
    except KeyboardInterrupt:
        if child:stop_child(child)
        status('offline',gpu_released=True)
        return 130


if __name__=='__main__':raise SystemExit(main())
