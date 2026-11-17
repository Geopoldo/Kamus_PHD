"""Read-only research ledger: all retained runs, including failures and earlier attempts."""
import csv
import io
import json
import math
from pathlib import Path
import zipfile

from embeddings import read, scan

STAGES = ('inventory', 'rendering', 'transcription', 'rules', 'model_audit', 'second_reading', 'human', 'embeddings', 'cross_analysis', 'matrix', 'graphrag', 'graph_query')


def lines(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        try:
            record=json.loads(line)
            # Earlier collectors stored some nvidia-smi readings as numeric strings.
            # Normalize for charts; bundles also retain the untouched source JSONL.
            for field in ('gpu_util_percent','vram_used_mib','vram_free_mib','ram_available_gib','process_rss_mib','process_cpu_percent','temperature_c','power_watts'):
                if isinstance(record.get(field),str):
                    try:
                        numeric=float(record[field])
                        if math.isfinite(numeric):record[field]=numeric
                    except ValueError:pass
            records.append(record)
        except ValueError:
            continue  # A concurrently written final line is retried on the next read.
    return records


def entries(root):
    progress = read(root/'progress.json')
    docs=progress.get('documents',[])
    folder_names={str(parent) for doc in docs for parent in Path(doc['source']).parents if str(parent)!='.'}
    source_root=Path(progress['source']) if progress.get('source') else None
    source_count=sum((source_root/doc['source']).is_file() for doc in docs) if source_root else None
    total_pages=sum(doc['page_count'] for doc in docs)
    yield 'inventory','current_inventory',dict(status='snapshot',processed=source_count,total=len(docs),
        folders=len(folder_names),documents=len(docs),inventory_pages=total_pages,
        documents_metadata=[{k:doc.get(k) for k in ('source','folder','sha256','page_count','status')} for doc in docs]),root,None
    for path in sorted((root/'inventories').glob('*/manifest.json')):
        yield 'inventory',path.parent.name,read(path),path.parent,'telemetry.jsonl'
    render_pages=[]
    for doc in docs:
        output=Path(doc['output']).resolve()
        if not output.is_relative_to((root/'documents').resolve()):continue
        saved={p['number']:p for p in doc.get('pages',[])}
        for page in range(1,doc['page_count']+1):
            image=output/f'page_{page:04}.png'
            render_pages.append(dict(document=doc['source'],folder=doc['folder'],page=page,
                                     available=image.is_file(),render_seconds=saved.get(page,{}).get('render_seconds')))
    times=[p['render_seconds'] for p in render_pages if isinstance(p['render_seconds'],(float,int))]
    available=sum(p['available'] for p in render_pages)
    yield 'rendering','page_images',dict(status='complete' if available==total_pages else 'partial',processed=available,
        total=total_pages,elapsed_seconds=sum(times) if times else None,render_seconds=sum(times) if times else None,
        model='Poppler · PDF → PNG',pages=render_pages,configuration={k:v for k,v in read(root/'config.json').items() if k in ('render_long_side','logical_page_policy')},
        measured_pages=len(times),note='Duration is the sum of measured per-page rendering times, not continuous wall time. GPU samples during rendering may include an already resident transcription model.'),root,'telemetry.jsonl'
    yield 'transcription', 'original', progress, root, 'telemetry.jsonl'
    for stage, folder, filename in [('rules','audits','manifest.json'), ('model_audit','model_audits','manifest.json'),
                                    ('second_reading','second_reading','manifest.json'), ('embeddings','embeddings/runs','manifest.json'),
                                    ('matrix','matrices','matrix.json'), ('graphrag','knowledge_graph/pilot_30/runs','manifest.json'),
                                    ('graph_query','knowledge_graph/questions','question.json')]:
        for path in sorted((root/folder).glob('*/'+filename)):
            yield stage, path.parent.name, read(path), path.parent, 'telemetry.jsonl'
    for record in lines(root/'priorities/events.jsonl'):
        if record.get('event') in ('search_completed', 'search_failed', 'search_interrupted'):
            yield 'cross_analysis', record['id'], record, root/'priorities', None
    # Human activity records show saved revisions, not invented time-on-task measurements.
    revisions = []
    for path in (root/'reviews').glob('*/*.history/*.json'):
        r = read(path)
        revisions.append({k:r.get(k) for k in ('document','page','revision','reviewer','updated','status')})
    yield 'human', 'saved_revisions', dict(status='recorded', processed=len({(r['document'],r['page']) for r in revisions}), revisions=revisions), root/'reviews', None


def measured(samples):
    result = {}
    for field in ('gpu_util_percent','vram_used_mib','vram_free_mib','ram_available_gib','process_rss_mib','process_cpu_percent','temperature_c','power_watts'):
        values = [s[field] for s in samples if isinstance(s.get(field), (int,float))]
        if values:
            result[field] = dict(peak=max(values), minimum=min(values), mean=sum(values)/len(values))
    return result


def samples_for(stage, directory, name):
    if stage in ('graphrag','graph_query'):
        return sorted([s for path in directory.glob('*/telemetry.jsonl') for s in lines(path)], key=lambda s:s['time'])
    samples = lines(directory/name) if name else []
    return [s for s in samples if s.get('stage')=='rendering'] if stage=='rendering' else samples


def summarize(stage, key, data, directory, samples):
    started = data.get('started', data.get('created'))
    finished = data.get('finished')
    elapsed = data.get('elapsed_seconds', data.get('seconds'))
    processed = data.get('processed', data.get('completed'))
    total = data.get('total_pages', data.get('total_readings', data.get('total')))
    status = data.get('status', data.get('stage', data.get('event', 'recorded')))
    inference = data.get('inference_seconds')
    render = data.get('render_seconds')
    if stage == 'transcription':
        processed = data.get('summary',{}).get('processed'); total = data.get('summary',{}).get('pdf_pages')
        finished = data.get('updated') if status == 'finished' else None
        pages = [p for d in data.get('documents',[]) for p in d.get('pages',[])]
        def total_of(field):
            values = [p[field] for p in pages if isinstance(p.get(field),(int,float))]
            return sum(values) if values else None
        inference, render = total_of('inference_seconds'), total_of('render_seconds')
    elif stage == 'second_reading':
        metrics = read(directory/'metrics.json')
        processed = metrics.get('pages',metrics.get('pages_available'))
        total = len(data.get('samples', []))
        inference = metrics.get('inference_seconds',metrics.get('run_inference_seconds'))
    elif stage == 'matrix':
        finished = data.get('updated') if status in ('complete','complete_with_errors','failed','interrupted','partial') else None
        timings = [p.get('response',{}).get('timings',{}) for c in data.get('cells',[]) for p in c.get('parts',[])]
        if any(timings):
            inference = sum(t.get('prompt_ms',0)+t.get('predicted_ms',0) for t in timings)/1000
    elif stage == 'cross_analysis':
        finished = data['timestamp']
        started = finished - elapsed if elapsed is not None else None
        processed = data.get('coverage',{}).get('searched_pages'); total = data.get('coverage',{}).get('inventory_pages')
    elif stage in ('graphrag','graph_query'):
        # Derived from the local engine timing lines, never the overall phase time.
        inference = read(directory/'runtime_summary.json').get('inference_seconds')
    if elapsed is None and started is not None and finished is not None:
        elapsed = max(0,finished-started)
    return dict(stage=stage, run_id=key, status=status, started=started, finished=finished,
                elapsed_seconds=elapsed, inference_seconds=inference, render_seconds=render,
                load_seconds=sum(p.get('load_seconds',0) for p in data.get('phases',[])) if stage in ('graphrag','graph_query') else data.get('load_seconds'), processed=processed,total=total,
                model='Microsoft GraphRAG · Qwen3.5-9B + Qwen3-Embedding-0.6B · piloto' if stage=='graphrag' else data.get('model'), error=data.get('error'), samples=len(samples),
                folders=data.get('folders'),documents=data.get('documents') if isinstance(data.get('documents'),int) else None,
                inventory_pages=data.get('inventory_pages'),
                resources=measured(samples), generated_vectors=data.get('generated_vectors'),
                reused_vectors=data.get('reused_vectors'), revision=data.get('revision'),
                reason=data.get('reason'),policy=data.get('policy'),
                hashing_seconds=data.get('hashing_seconds'),pdfinfo_seconds=data.get('pdfinfo_seconds'),
                discovery_seconds=data.get('discovery_seconds'),worker_cpu_seconds=data.get('worker_cpu_seconds'),tools_cpu_seconds=data.get('tools_cpu_seconds'),
                note='Transcription elapsed time spans the original inventory through the last update and may include interruptions.' if stage=='transcription' else data.get('file_read_cache_note'))


def listing(root):
    rows=[]
    for stage,key,data,directory,name in entries(root):
        samples=samples_for(stage,directory,name)
        rows.append(summarize(stage,key,data,directory,samples))
    rows.sort(key=lambda r:(STAGES.index(r['stage']),r['started'] or 0,r['run_id']))
    return dict(order=list(STAGES),runs=rows)


def locate(root, stage, key):
    # Resolve from the catalog, never join user-supplied paths.
    for entry in entries(root):
        if entry[:2]==(stage,key):
            return entry
    raise ValueError('Registro de proceso desconocido')


def detail(root, stage, key):
    _,_,data,directory,name=locate(root,stage,key)
    samples=samples_for(stage,directory,name)
    if stage=='inventory' and key!='current_inventory':
        pages=read(directory/'files.json',[]);manifest=data
    elif stage=='transcription':
        pages=[dict(document=d['source'],folder=d['folder'],**{k:p.get(k) for k in ('number','status','render_seconds','inference_seconds','wall_seconds','usage','attempts')}) for d in data.get('documents',[]) for p in d.get('pages',[])]
        manifest={k:v for k,v in data.items() if k!='documents'}
    elif stage=='rendering':
        pages=data['pages'];manifest={k:v for k,v in data.items() if k!='pages'}
    elif stage=='matrix':
        pages=[dict(row=c.get('row'),question=c.get('question'),status=c.get('status'),timings=[p.get('response',{}).get('timings') for p in c.get('parts',[])]) for c in data.get('cells',[])]
        manifest={k:v for k,v in data.items() if k not in ('rows','cells')}
    else:
        pages=[];manifest=data
    return dict(summary=summarize(stage,key,data,directory,samples),telemetry=samples,manifest=manifest,pages=pages)


def bundle(root, stage, key):
    _,_,data,directory,name=locate(root,stage,key)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('process_record.json',json.dumps(detail(root,stage,key),ensure_ascii=False,indent=2))
        if stage in ('rendering','transcription') or (stage=='inventory' and key=='current_inventory'):
            paths=[root/name for name in ('progress.json','inventory.json','config.json','scale_metrics.json','page_metrics.csv','events.jsonl','telemetry.jsonl','server.log')]
        elif stage=='cross_analysis':
            paths=[directory/'events.jsonl']+list((directory/'catalog_history').glob('*.json'))
        else:
            paths=directory.rglob('*')
        for path in paths:
            if path.is_file() and path.suffix in ('.json','.jsonl','.md','.log','.py','.csv','.yaml','.txt') and path.resolve().is_relative_to(directory.resolve()):
                archive.write(path,str(path.relative_to(directory)))
    return stream.getvalue()


def csv_bytes(root):
    fields=['stage','run_id','status','reason','started','finished','elapsed_seconds','load_seconds','render_seconds','inference_seconds','discovery_seconds','hashing_seconds','pdfinfo_seconds','worker_cpu_seconds','tools_cpu_seconds','processed','total','folders','documents','inventory_pages','model','samples','generated_vectors','reused_vectors','revision','error']
    resource_fields=['gpu_util_percent','vram_used_mib','ram_available_gib','process_rss_mib','temperature_c','power_watts']
    fields += [name+'_'+stat for name in resource_fields for stat in ('peak','mean','minimum')]
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for value in listing(root)['runs']:
        row={field:value.get(field) for field in fields}
        for name in resource_fields:
            for stat in ('peak','mean','minimum'):
                row[name+'_'+stat]=value['resources'].get(name,{}).get(stat)
        # Protect spreadsheet readers from user-derived formula text.
        for key,value in row.items():
            if isinstance(value,str) and value.startswith(('=','+','-','@')):row[key]="'"+value
        writer.writerow(row)
    return ('\ufeff'+stream.getvalue()).encode()


def page_coverage(root):
    snapshot=scan(root)
    hashes={r['key']:r['text_sha256'] for r in snapshot['records']}
    pages={key:{} for key in snapshot['pages']}
    for stage,folder,pointer in [('rules','audits','audit_latest.json'),('model_audit','model_audits','model_audit_latest.json')]:
        latest=read(root/pointer).get('run_id','')
        directory=(root/folder/latest).resolve()
        if not directory.is_relative_to((root/folder).resolve()):continue
        for record in read(directory/'all_pages.json',[]):
            key=record['document_id']+':'+str(record['page'])
            if key not in pages:continue
            input_hash=record.get('input_sha256',record.get('hashes',{}).get('.md'))
            pages[key][stage]=dict(stale=input_hash!=hashes.get(key+':original'), findings=len(record.get('findings',[])),classification=record['classification'])
    latest=read(root/'priorities/latest.json')
    coverage={}
    for record in latest.get('coverage',{}).get('snapshots',[]):
        key=record['document_id']+':'+str(record['page'])
        coverage.setdefault(key,[]).append(record)
    matched={r['document_id']+':'+str(r['page']):len({m['entity'] for v in r['versions'] for m in v['matches']}) for r in latest.get('pages',[])}
    for key,records in coverage.items():
        if key in pages:
            pages[key]['cross_analysis']=dict(count=matched.get(key,0),stale=any(hashes.get(key+':'+r['version'])!=r['hash'] for r in records),created=latest.get('created'))
    return pages
