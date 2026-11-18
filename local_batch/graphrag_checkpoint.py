"""Publish completed page extractions on CPU, without claiming a query-ready index."""
from datetime import datetime, timedelta
import hashlib
import json
import time
from pathlib import Path
from embeddings import read, write
from graphrag_state import available_run, visible_run


def page_id(unit):
    if unit.get('document_id') is not None:
        return unit['document_id']
    ids = unit.get('document_ids', [])
    if len(ids) != 1:
        raise ValueError('Text unit crosses source pages')
    return ids[0]


def completed_pages(units, extractions):
    expected = {}
    for u in units:
        expected.setdefault(page_id(u), set()).add(u['id'])
    done = {r['source_id'] for r in extractions}
    return {p for p, ids in expected.items() if ids <= done}


def json_lines(path):
    if not path.exists(): return []
    rows = []
    for line in path.read_text().splitlines():
        try: rows.append(json.loads(line))
        except ValueError: continue  # interrupted trailing write is not completed evidence
    return rows


def successful_extractions(run, units):
    """Older GraphRAG versions swallowed failures as empty results. Exclude those."""
    manifest = read(run/'manifest.json')
    origin = run.parent/manifest['checkpoint_of'] if manifest.get('checkpoint_of') else run
    failed = {e.get('text_sha256') for e in read(origin/'manifest.json').get('extraction_errors', [])}
    invalid = {u['id'] for u in units if hashlib.sha256(u.get('text','').encode()).hexdigest() in failed}
    return [e for e in json_lines(run/'extractions.jsonl') if e['source_id'] not in invalid]


def publish_checkpoint(root):
    import pandas as pd
    from graphrag_review import publish
    root = Path(root); directory = root/'knowledge_graph/pilot_30'
    key = read(directory/'latest.json').get('run_id')
    if not key: return None
    run = directory/'runs'/key
    # The worker must have exited before output/ can be inspected.
    snapshot = read(run/'inputs.json'); records = snapshot.get('records', [])
    if not records: return None
    current = {r['id']: r for r in records}
    units_path = directory/'output/text_units.parquet'
    if not units_path.exists(): return None
    units = pd.read_parquet(units_path).to_dict('records')
    if any(page_id(u) not in current for u in units):
        raise ValueError('Text units do not match this frozen input snapshot')
    extractions = successful_extractions(run, units)
    complete = completed_pages(units, extractions)
    chosen = {r['id']:r for r in records if r['id'] in complete}
    kept_units = {u['id']:u for u in units if page_id(u) in chosen}
    kept_extracts = {e['source_id']:e for e in extractions if e['source_id'] in kept_units}
    # Preserve published completed pages if a newer attempt has not reached them yet.
    previous = directory/'runs'/visible_run(directory)
    old_records = read(previous/'inputs.json').get('records', [])
    old_index = previous/'index/text_units.parquet'
    if old_index.exists():
        same = {r['id']:r for r in old_records if r['id'] in current and r['text_sha256']==current[r['id']]['text_sha256'] and r['id'] not in chosen}
        old_units = pd.read_parquet(old_index).to_dict('records')
        old_extracts = successful_extractions(previous, old_units)
        valid = completed_pages(old_units,old_extracts)
        same = {k:r for k,r in same.items() if k in valid}
        chosen.update(same)
        kept_units.update({u['id']:u for u in old_units if page_id(u) in same})
        kept_extracts.update({e['source_id']:e for e in old_extracts if e['source_id'] in kept_units and e['source_id'] not in kept_extracts})
    if not chosen: return None
    stamp = datetime.now()
    while (directory/'runs'/stamp.strftime('%Y%m%dT%H%M%S')).exists(): stamp += timedelta(seconds=1)
    dest = directory/'runs'/stamp.strftime('%Y%m%dT%H%M%S'); (dest/'index').mkdir(parents=True)
    start = time.time()
    write(dest/'inputs.json',dict(snapshot,records=list(chosen.values()),scope='partial_processed_pages'))
    pd.DataFrame(list(kept_units.values())).to_parquet(dest/'index/text_units.parquet')
    (dest/'extractions.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in kept_extracts.values()))
    manifest = dict(run_id=dest.name,status='checkpoint',publication_kind='extraction_checkpoint',checkpoint_of=key,
                    total=len(chosen),processed=len(chosen),documents=len({r['document'] for r in chosen.values()}),
                    scope='partial_processed_pages',started=start,phases=[],
                    input_sha256=hashlib.sha256((dest/'inputs.json').read_bytes()).hexdigest())
    write(dest/'manifest.json',manifest)
    result = publish(root,checkpoint_run=dest.name)
    manifest.update(finished=time.time(),elapsed_seconds=time.time()-start)
    write(dest/'manifest.json',manifest)
    return dict(run_id=dest.name,pages=result['pages'],nodes=len(result['nodes']),relationships=len(result['relationships']),elapsed_seconds=manifest['elapsed_seconds'])
