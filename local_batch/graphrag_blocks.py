"""Publish cumulative Knowledge Graph releases, adding at most 80 pages each time."""
import json
from pathlib import Path
import subprocess
import sys
import time
import graphrag_pilot as pilot
from embeddings import read, write


def main():
    state_path = pilot.PILOT / 'blocks.json'
    while True:
        pilot.prepare(all_pages=True)
        snapshot = read(pilot.PILOT / 'inputs.json')
        active = read(pilot.PILOT / 'active.json').get('run_id', '')
        previous = read(pilot.PILOT / 'runs' / active / 'inputs.json').get('records', [])
        ready = {(r['document_id'], r['page']): r for r in previous}
        retained, pending = [], []
        for row in snapshot['records']:
            old = ready.get((row['document_id'], row['page']))
            (retained if old and old['text_sha256'] == row['text_sha256'] else pending).append(row)
        if not pending:
            write(state_path, dict(status='complete', published_pages=len(retained), total_pages=len(retained), updated=time.time()))
            return 0
        selected = retained + pending[:80]
        snapshot.update(records=selected, scope='partial_processed_pages' if len(pending)>80 else 'available_corpus')
        write(pilot.PILOT / 'inputs.json', snapshot)
        state = dict(status='running', block_size=80, published_pages=len(retained),
                     target_pages=len(selected), total_pages=len(retained)+len(pending),
                     added_pages=min(80,len(pending)), started=time.time(), updated=time.time())
        write(state_path, state)
        result = subprocess.run([sys.executable, str(Path(pilot.__file__)), '--run', '--publish'])
        state.update(status='published' if result.returncode==0 else 'stopped', updated=time.time(), returncode=result.returncode)
        write(state_path, state)
        if result.returncode:
            return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
