"""Read-only pilot evidence and quote checks; never treats citation presence as truth."""
import csv
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import time

from embeddings import read, scan, write
from graphrag_state import available_run


def quote_checks(description, text):
    quotes = re.findall(r'QUOTE:\s*(?:«([^»]+)»|"([^"\n]+)")', description, re.I)
    evidence = [a or b for a, b in quotes]
    norm = lambda s: re.sub(r'\s+', ' ', s).strip()
    return [dict(quote=q, exact=q in text, whitespace_match=norm(q) in norm(text)) for q in evidence]


def source_availability(root, run_id):
    """Flag archived sources without rewriting evidence from a published run."""
    records = read(root / 'knowledge_graph/pilot_30/runs' / run_id / 'inputs.json').get('records', []) if run_id else []
    inventory = read(root / 'progress.json')
    if 'documents' not in inventory:
        return dict(known=False, archived_pages=0, archived_documents=0)
    active = {d['source'] for d in inventory['documents']}
    removed = [r for r in records if r['document'] not in active]
    return dict(known=True, archived_pages=len(removed),
                archived_documents=len({r['document'] for r in removed}))


def get(root):
    directory = root / 'knowledge_graph/pilot_30'
    key = available_run(directory)
    if not re.fullmatch(r'\d{8}T\d{6}', key):
        return dict(status='not_started', records=[])
    manifest = read(directory / 'runs' / key / 'manifest.json')
    result = read(directory / 'runs' / key / 'review.json')
    return dict(manifest=manifest, result=result, status=manifest.get('status'), source_changes=source_availability(root, key))


def status(root):
    directory = root / 'knowledge_graph/pilot_30'
    key = read(directory / 'latest.json').get('run_id', '')
    if not re.fullmatch(r'\d{8}T\d{6}', key): return dict(status='not_started')
    run = directory / 'runs' / key
    manifest = read(run / 'manifest.json')
    plan = read(directory / 'plan.json')
    if plan.get('input_sha256') != manifest.get('input_sha256'): plan = {}
    sample = {}
    for phase in reversed(manifest.get('phases', [])):
        log = run / phase['name'] / 'telemetry.jsonl'
        if not log.exists(): continue
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size-8192))
            for line in reversed(stream.read().splitlines()):
                try: sample = json.loads(line); break
                except (ValueError, UnicodeDecodeError): continue
        if sample: break
    fields = ['time','vram_used_mib','gpu_util_percent','temperature_c','power_watts','process_rss_mib','ram_available_gib']
    active_key = available_run(directory)
    active = read(directory / 'runs' / active_key / 'manifest.json')
    ready = (directory / 'runs' / active_key / 'review.json').is_file()
    prepared = read(directory / 'inputs.json')
    from graphrag_eta import estimate
    eta = estimate(manifest, [read(p) for p in (directory/'runs').glob('*/manifest.json') if p.parent != run])
    return dict(status=manifest.get('status'), manifest=manifest, plan=plan, server_time=time.time(),
                eta=eta,
                resources={k:sample.get(k) for k in fields}, result_ready=ready,
                available_run=active_key if ready else None, available_pages=active.get('total', 0) if ready else 0,
                source_changes=source_availability(root, active_key),
                prepared_pages=len(prepared['records']) if 'records' in prepared else None,
                build_result_ready=(run/'review.json').exists(),
                attempts=len(list((directory/'runs').glob('*/manifest.json'))))


def page(root, document, number, version, run_id=None):
    directory = root / 'knowledge_graph/pilot_30'
    key = run_id or available_run(directory)
    if not re.fullmatch(r'\d{8}T\d{6}',key): raise ValueError('No hay un piloto disponible')
    snapshot = read(directory / 'runs' / key / 'inputs.json')
    r = next((r for r in snapshot.get('records',[]) if r['document_id']==document and r['page']==number and r['version']==version),None)
    if not r: raise ValueError('La página no forma parte de este piloto')
    current = next((s for s in scan(root)['records'] if s['key']==r['key']),None)
    return dict(**r, changed=current is None or current['text_sha256']!=r['text_sha256'])


def csv_bytes(root):
    value = get(root)
    if not value.get('result'): raise ValueError('El piloto aún no tiene un balance disponible')
    return (root / 'knowledge_graph/pilot_30/runs' / value['manifest']['run_id'] / 'relationships.csv').read_bytes()


def runtime_summary(directory):
    """Separate measured engine compute from end-to-end phase time and cache reuse."""
    manifest = read(directory / 'manifest.json')
    phases = []
    for phase in manifest.get('phases', []):
        values = dict(name=phase['name'], elapsed_seconds=phase.get('elapsed_seconds'),
                      load_seconds=phase.get('load_seconds'), timed_calls=0,
                      prompt_seconds=0., generation_seconds=0., prompt_tokens_evaluated=0, generated_tokens=0)
        log = directory / phase['name'] / 'engine.log'
        if log.exists():
            with log.open(errors='replace') as stream:
                for line in stream:
                    match = re.search(r'print_timing:.*?\|\s*(prompt eval|eval) time\s*=\s*([\d.]+) ms\s*/\s*(\d+) tokens', line)
                    if not match: continue
                    prompt = match[1] == 'prompt eval'
                    values['prompt_seconds' if prompt else 'generation_seconds'] += float(match[2]) / 1000
                    values['prompt_tokens_evaluated' if prompt else 'generated_tokens'] += int(match[3])
                    if not prompt: values['timed_calls'] += 1
        values['inference_seconds'] = values['prompt_seconds'] + values['generation_seconds'] if values['timed_calls'] else None
        phases.append(values)
    measured = [p['inference_seconds'] for p in phases if p['inference_seconds'] is not None]
    return dict(phases=phases, inference_seconds=sum(measured) if measured else None,
                scope='llama-server timing lines for this attempt, including retries with timing records. Cached replies do not rerun the engine. Prompt tokens count evaluated tokens, not the complete cached prompt.')


def entity_inventory(extractions, unit_map, inputs):
    """Include every extracted entity, also those without a retained relationship."""
    nodes = {}
    for record in extractions:
        unit = unit_map[record['source_id']]
        doc_id = unit.get('document_id')
        if doc_id is None:
            ids = unit.get('document_ids', [])
            if len(ids) != 1: raise ValueError('Text unit crosses source pages')
            doc_id = ids[0]
        page = {k:inputs[doc_id][k] for k in ('document_id','document','folder','page','version','review_status','text_sha256')}
        for entity in record['entities']:
            node = nodes.setdefault(entity['title'], dict(id=entity['title'],type=entity['type'],
                label=re.sub(r'^(?:TYPE::)?[A-Z]+::','',entity['title']),sources=[],mentions=[]))
            if record['source_id'] in node['sources']: continue
            node['sources'].append(record['source_id'])
            node['mentions'].append(dict(text_unit_id=record['source_id'],page=page,
                quotes=quote_checks(entity['description'],unit['text'])))
    return nodes


def publish(root):
    import pandas as pd
    directory = root / 'knowledge_graph/pilot_30'
    key = read(directory / 'latest.json')['run_id']
    run_dir = directory / 'runs' / key
    m = read(run_dir / 'manifest.json')
    if m['status'] != 'complete':
        raise ValueError('The pilot has not completed successfully')
    source = directory / 'inputs.json'
    if hashlib.sha256(source.read_bytes()).hexdigest() != m['input_sha256']:
        raise ValueError('Input snapshot changed after this run')
    snapshot = read(source); inputs = {r['id']: r for r in snapshot['records']}
    write(run_dir / 'inputs.json', snapshot)
    # Questions must keep using the exact index even if a later pilot replaces output/.
    frozen_index = run_dir / 'index'
    if not frozen_index.exists(): shutil.copytree(directory/'output', frozen_index)
    write(run_dir / 'index_manifest.json', dict(files={str(p.relative_to(frozen_index)):hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen_index.rglob('*') if p.is_file()}))
    runtime = runtime_summary(run_dir)
    write(run_dir / 'runtime_summary.json', runtime)
    units = pd.read_parquet(directory / 'output/text_units.parquet')
    unit_map = {r['id']: r for r in units.to_dict('records')}
    edges = []
    extractions = [json.loads(line) for line in (run_dir / 'extractions.jsonl').read_text().splitlines()]
    nodes = entity_inventory(extractions,unit_map,inputs)
    entity_types = {key:node['type'] for key,node in nodes.items()}
    for record in extractions:
        unit = unit_map[record['source_id']]
        doc_id = unit.get('document_id')
        if doc_id is None:
            ids = unit.get('document_ids', [])
            if len(ids) != 1: raise ValueError('Text unit crosses source pages')
            doc_id = ids[0]
        page = inputs[doc_id]
        for r in record['relationships']:
            checks = quote_checks(r['description'], unit['text'])
            fields = {}
            for name in ['relation', 'assertion', 'attribution', 'event_time', 'document_time']:
                match = re.search(r'\b'+name+r'\s*=\s*([^;\n]+)', r['description'], re.I)
                fields[name] = match[1].strip() if match else None
            flags = []
            if not checks: flags.append('missing_quote')
            elif not all(q['whitespace_match'] for q in checks): flags.append('quote_not_found')
            if not fields['event_time'] or not fields['document_time']: flags.append('time_not_structured')
            if not fields['attribution']: flags.append('attribution_not_structured')
            if not fields['assertion']: flags.append('assertion_not_structured')
            if r['source'] not in nodes or r['target'] not in nodes: flags.append('missing_entity')
            if any(re.search(r'\b(can|could|would|may|might|if|should|suggest|possible|suspicions)\b',q['quote'],re.I) for q in checks):
                flags.append('conditional_or_proposed_context')
            if any(re.fullmatch(r'(?:TYPE::)?PERSON::(?:REGIONAL SUPERVISOR|CHIEF|INFORMANT|FATHER|MOTHER|AUTHOR|WRITER|UNKNOWN)',s) for s in [r['source'],r['target']]):
                flags.append('unnamed_role_not_identified_person')
            edges.append(dict(id=f'{key}:{len(edges)+1}', source=r['source'], target=r['target'],
                source_type=entity_types.get(r['source'], 'UNKNOWN'), target_type=entity_types.get(r['target'], 'UNKNOWN'),
                description=r['description'], quotes=checks, fields=fields, flags=flags,
                quote_status='found' if checks and all(q['whitespace_match'] for q in checks) else 'needs_review',
                human_validation='unreviewed', text_unit_id=record['source_id'],
                page={k:page[k] for k in ('document_id','document','folder','page','version','review_status','text_sha256')}))
    # Every original record remains accessible, including empty extractions.
    query = read(run_dir / 'query.json')
    reports = pd.read_parquet(directory / 'output/community_reports.parquet')
    completion_reasons = {}
    for path in (directory/'cache').rglob('*'):
        if not path.is_file(): continue
        try:
            cached=json.loads(path.read_text())['result']['response']
            for choice in cached.get('choices',[]):
                reason=choice.get('finish_reason','unknown');completion_reasons[reason]=completion_reasons.get(reason,0)+1
        except (ValueError,KeyError,UnicodeDecodeError):continue
    rejected = []
    structured = run_dir / 'structured_extractions.jsonl'
    if structured.exists():
        for line in structured.read_text().splitlines():
            entry=json.loads(line)
            rejected += [dict(candidate, text_sha256=entry['text_sha256']) for candidate in entry['rejected']]
    result = dict(run_id=key, created=time.time(), pages=len(inputs), source_documents=len({r['document'] for r in inputs.values()}),
        cache_completion_reasons=completion_reasons,
        rejected_candidates=rejected,
        nodes=list(nodes.values()), relationships=edges,
        entity_counts=dict(Counter(n['type'] for n in nodes.values())),
        spot_checks=read(run_dir / 'pilot_spot_checks.json'), runtime=runtime,
        evidence_counts=dict(total=len(edges), quotes_found=sum(e['quote_status']=='found' for e in edges),
                             entity_pairs=len({(e['source'],e['target']) for e in edges}),
                             pages_with_relationships=len({(e['page']['document_id'],e['page']['page']) for e in edges}),
                             quotes_pending=sum(e['quote_status']!='found' for e in edges),
                             structured_time=sum(e['fields']['event_time'] is not None and e['fields']['document_time'] is not None for e in edges),
                             event_time_identified=sum(bool(e['fields']['event_time']) and e['fields']['event_time'].lower()!='unknown' for e in edges),
                             document_time_identified=sum(bool(e['fields']['document_time']) and e['fields']['document_time'].lower()!='unknown' for e in edges),
                             conditional_context=sum('conditional_or_proposed_context' in e['flags'] for e in edges),
                             human_validated=0),
        selection=[{k:v for k,v in r.items() if k!='text'} for r in inputs.values()],
        query=query, communities=json.loads(reports.to_json(orient='records')),
        scope=m.get('scope', 'purposive_pilot_30'), corpus_pages=snapshot.get('corpus_pages'),
        limitations=[('Partial publication: only pages with completed saved extractions are included; remaining corpus pages are deferred.'
                      if m.get('scope') == 'partial_processed_pages' else 'All available transcribed pages at snapshot time; extraction is not guaranteed exhaustive.'
                      if m.get('scope') == 'available_corpus' else 'Purposive pilot, not a corpus-wide result or statistical evaluation.'),
                     'Frozen pilot snapshot: edits and new sources do not automatically rebuild this experimental graph.',
                     'Output token limits and extraction errors can omit entities or relations; this is not exhaustive retrieval.',
                     'Literal quote presence does not establish entity type, relationship, date or historical truth.',
                     'All links and generated community summaries require human review.'])
    write(run_dir / 'review.json', result)
    stream = io.StringIO(); fields = ['source','source_type','target','target_type','description','quote_status','quotes','flags',
        'relation','assertion','attribution','event_time','document_time','folder','document','page','version','review_status','text_sha256','human_validation']
    out = csv.DictWriter(stream, fieldnames=fields); out.writeheader()
    for edge in edges:
        row = {**{k:edge[k] for k in fields if k in edge}, **edge['fields'], **edge['page']}; row.pop('document_id',None)
        row['quotes'] = json.dumps(edge['quotes'], ensure_ascii=False); row['flags'] = '; '.join(edge['flags'])
        for k,v in row.items():
            if isinstance(v,str) and v.startswith(('=','+','-','@')): row[k] = "'"+v
        out.writerow(row)
    (run_dir / 'relationships.csv').write_text('\ufeff'+stream.getvalue())
    # Last operation: failed or incomplete publication keeps the old graph usable.
    write(directory / 'active.json', dict(run_id=key, published=time.time(), pages=len(inputs)))
    return result


if __name__ == '__main__':
    result = publish(Path(__file__).resolve().parent / 'results')
    print(json.dumps(dict(pages=result['pages'], nodes=len(result['nodes']), **result['evidence_counts'])))
