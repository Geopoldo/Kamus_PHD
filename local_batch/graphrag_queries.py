"""Persisted local GraphRAG questions; one GPU model at a time, frozen pilot inputs."""
import argparse
import asyncio
import csv
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import uuid

from embeddings import read, write, digest, PROJECT

ACTIVE = {'queued','waiting_pilot','waiting_gpu','embedding','query','preparing_results'}


def path_for(root, key):
    if not re.fullmatch(r'[a-f0-9]{32}', key): raise ValueError('Consulta no válida')
    return root/'knowledge_graph/questions'/key/'question.json'


def get(root, key):
    path = path_for(root, key)
    if not path.exists(): raise ValueError('Consulta no encontrada')
    value = read(path)
    if value.get('status') in ACTIVE:
        try:
            current = Path(f"/proc/{value['pid']}/stat").read_text().rsplit(')',1)[1].split()[19]
            alive = current == value.get('process_start')
        except (OSError,KeyError): alive = time.time()-value['created'] < 15
        if not alive: value = dict(value,status='interrupted',error='El trabajador se detuvo. La consulta y sus registros se conservan.')
        else: value = dict(value,elapsed_seconds=time.time()-value['started'])
    for phase in reversed(value.get('phases',[])):
        log=path.parent/phase['name']/'telemetry.jsonl'
        if not log.is_file(): continue
        with log.open('rb') as stream:
            stream.seek(max(0,log.stat().st_size-8192))
            for line in reversed(stream.read().splitlines()):
                try: sample=json.loads(line)
                except (ValueError,UnicodeDecodeError): continue
                value['resources_latest']={k:sample.get(k) for k in ('time','vram_used_mib','gpu_util_percent','temperature_c','power_watts','process_rss_mib')}
                break
        if value.get('resources_latest'): break
    value['runtime']=read(path.parent/'runtime_summary.json')
    analysis=read(path.parent/'answer_analysis.json')
    if analysis.get('version') in (1,2):
        value.update({k:analysis[k] for k in ('graph','citations','context_pages') if k in analysis})
        value['provenance_version']=analysis['version']
    value.setdefault('grounding_policy','legacy_mixed_local_prompt' if value.get('mode')=='local' else 'context_only_global')
    return value


def listing(root):
    fields = ['id','question','author','mode','pilot_run','created','status','elapsed_seconds','error','session_id']
    return [{k:value.get(k) for k in fields} for path in sorted((root/'knowledge_graph/questions').glob('*/question.json'),reverse=True) if (value:=get(root,path.parent.name))]


def create(root, payload, launch=True):
    import research_sessions
    session_id=research_sessions.validate_link(root,payload.get('session_id'))
    question, author, mode = payload.get('question'), payload.get('author',''), payload.get('mode','local')
    if not isinstance(question,str) or not 3<=len(question.strip())<=2000: raise ValueError('Escribe una pregunta de 3 a 2000 caracteres')
    if not isinstance(author,str) or len(author)>160: raise ValueError('Nombre del responsable no válido')
    if mode not in ('local','global'): raise ValueError('Modalidad no válida')
    pilot = root/'knowledge_graph/pilot_30'
    from graphrag_state import available_run
    key = available_run(pilot)
    if not re.fullmatch(r'\d{8}T\d{6}', key): raise ValueError('Todavía no hay un piloto para consultar')
    manifest = read(pilot/'runs'/key/'manifest.json')
    from graphrag_scope import normalize, matches
    inputs = read(pilot/'runs'/key/'inputs.json').get('records', [])
    filters = normalize(payload.get('source_filters'), inputs)
    scoped = any(filters.values())
    if scoped and payload.get('pilot_run', key) != key:
        raise ValueError('La versión publicada cambió. Actualiza el grafo antes de preguntar.')
    if scoped and mode != 'local':
        raise ValueError('Las preguntas por carpeta o documento usan Relaciones concretas; los informes globales reúnen varias fuentes.')
    if manifest.get('status') in ('failed','interrupted'): raise ValueError('El piloto está interrumpido; primero debe completarse')
    jobs = root/'knowledge_graph/questions'; jobs.mkdir(parents=True,exist_ok=True)
    with (jobs/'create.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        ident = uuid.uuid4().hex
        path = path_for(root,ident)
        value = dict(id=ident,run_id=ident,question=question.strip(),author=author.strip(),mode=mode,
                     pilot_run=key,input_sha256=manifest.get('input_sha256'),created=time.time(),started=time.time(),
                     status='queued',phases=[],total=1,processed=0,
                     model='Qwen3.5-9B + Qwen3-Embedding-0.6B' if mode=='local' else 'Qwen3.5-9B',
                     scope=f"Frozen graph snapshot: {manifest.get('total', 0)} pages. Retrieved context is not historical validation.",
                     corpus_pages=manifest.get('total', 0))
        value['session_id']=session_id
        value['auto_fishbone']=payload.get('auto_fishbone',True) is True
        value['language']=payload.get('language','es') if payload.get('language','es') in ('es','en','fr') else 'es'
        value['source_filters']=filters
        if scoped:
            selected = [r for r in inputs if matches(r,filters)]
            value.update(scope='Selected folders/documents from the frozen graph; source-restricted retrieval.',
                         scope_pages=len(selected), scope_documents=len({r['document'] for r in selected}),
                         scope_input_ids=[r['id'] for r in selected])
        write(path,value)
        if launch:
            python = PROJECT/'.venv-graphrag/bin/python'
            if not python.is_file():
                value.update(status='failed',error='Falta el entorno local de GraphRAG');write(path,value);raise ValueError(value['error'])
            with (path.parent/'worker.log').open('w') as log:
                try: subprocess.Popen([str(python),str(Path(__file__).resolve()),'--root',str(root),'--job',ident],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                except OSError:
                    value.update(status='failed',error='No se pudo iniciar el trabajador local');write(path,value);raise
        return value


def csv_bytes(root,key):
    value=get(root,key);stream=io.StringIO();fields=['question','author','mode','pilot_run','source','target','relation','event_time','document_time','folder','document','page','version','quote_status','human_validation']
    out=csv.DictWriter(stream,fieldnames=fields);out.writeheader()
    for edge in value.get('graph',{}).get('relationships',[]):
        row={k:value.get(k,'') for k in fields[:4]}
        row.update({k:edge.get(k,'') for k in ['source','target','quote_status','human_validation']})
        row.update({k:edge['fields'].get(k,'') for k in ['relation','event_time','document_time']})
        row.update({k:edge['page'].get(k,'') for k in ['folder','document','page','version']})
        out.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return ('\ufeff'+stream.getvalue()).encode()


def context_graph(context, review, reports, communities, mode, answer):
    """Only graph evidence from retrieved context; never create links from answer prose."""
    pairs = {(str(r.get('source')),str(r.get('target'))) for r in context.get('relationships',[])}
    labels = {str(r.get('entity',r.get('title',''))) for r in context.get('entities',[])}
    cited_reports = set()
    for group in re.findall(r'\[Data:\s*Reports?\s*\(([^)]+)\)',answer,re.I): cited_reports.update(re.findall(r'\d+',group))
    if mode=='global':
        selected = [r for r in reports if str(r.get('human_readable_id',r.get('community'))) in cited_reports]
        community_ids={str(r['community']) for r in selected}
        entity_ids={str(e) for c in communities if str(c['community']) in community_ids for e in c.get('entity_ids',[])}
        # Entity IDs here are mapped to titles by the caller, not guessed from the prose.
        labels={n['id'] for n in review['nodes'] if n.get('graph_entity_id') in entity_ids}
    edges=[e for e in review['relationships'] if (mode=='local' and ((e['source'],e['target']) in pairs or (e['target'],e['source']) in pairs)) or (mode=='global' and e['source'] in labels and e['target'] in labels)]
    kept={x for e in edges for x in [e['source'],e['target']]} | labels
    return dict(nodes=[n for n in review['nodes'] if n['id'] in kept],relationships=edges,
                basis='retrieved_relationships' if mode=='local' else 'communities_cited_in_answer',
                cited_reports=sorted(cited_reports), human_validated=0)


def verify_index(directory, manifest):
    """Check the immutable index before consulting it; never trust a manifest path."""
    base=directory.resolve()
    for relative,expected in manifest.get('files',{}).items():
        path=(base/relative).resolve()
        if not path.is_relative_to(base) or not path.is_file(): raise ValueError('Falta un archivo del índice guardado')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected: raise ValueError('Cambió un archivo del índice guardado')
    if not manifest.get('files'): raise ValueError('El índice no tiene huellas registradas')


async def execute(root,key):
    # No external endpoints or inherited HTTP proxy for documentary content.
    for name in list(os.environ):
        if name.lower().endswith('_proxy'): os.environ.pop(name)
    os.environ.update(MAPH_GRAPH_TOKEN=secrets.token_hex(32),LITELLM_LOCAL_MODEL_COST_MAP='True',DO_NOT_TRACK='1',ANONYMIZED_TELEMETRY='False',
                      TIKTOKEN_CACHE_DIR=str(root/'knowledge_graph/tokenizers'))
    import pandas as pd
    from types import SimpleNamespace
    from graphrag.api.query import local_search, global_search
    from graphrag.config.load_config import load_config
    import graphrag.query.factory as factory
    from graphrag_pilot import LocalEngine
    from embedding_worker import request
    from graphrag_review import runtime_summary
    path=path_for(root,key);job=read(path);directory=path.parent
    job.update(pid=os.getpid(),process_start=Path(f'/proc/{os.getpid()}/stat').read_text().rsplit(')',1)[1].split()[19])
    def checkpoint():
        job.update(updated=time.time(),elapsed_seconds=time.time()-job['started']);write(path,job)
    pilot=root/'knowledge_graph/pilot_30/runs'/job['pilot_run']
    try:
        job['status']='waiting_pilot';checkpoint()
        while True:
            manifest=read(pilot/'manifest.json')
            if manifest.get('status') in ('failed','interrupted'): raise ValueError('El piloto se interrumpió. La pregunta queda guardada para volver a ejecutarla.')
            if manifest.get('status')=='complete' and (pilot/'review.json').exists() and (pilot/'index_manifest.json').exists(): break
            if time.time()-job['started']>7200: raise ValueError('El piloto no estuvo disponible dentro del tiempo de espera')
            await asyncio.sleep(2);checkpoint()
        if manifest['input_sha256']!=job['input_sha256']: raise ValueError('Cambió la huella de las entradas del piloto')
        config=load_config(pilot)
        for group in [config.completion_models,config.embedding_models]:
            if any(not model.api_base.startswith('http://127.0.0.1:') for model in group.values()): raise ValueError('Se rechazó un endpoint de modelo no local')
        index_dir=pilot/'index';config.vector_store.db_uri=str(index_dir/'lancedb')
        index_manifest=read(pilot/'index_manifest.json');verify_index(index_dir,index_manifest)
        config.reporting.base_dir=str(directory/'logs')
        for group_name,models in [('completion_models',config.completion_models),('embedding_models',config.embedding_models)]:
            for model in models.values():
                model.metrics.base_dir=str(directory/'metrics'/group_name)
        for model in config.completion_models.values(): model.call_args.update(max_tokens=2400,timeout=180)
        from graphrag_provenance import STRICT_LOCAL_PROMPT
        prompt_path=directory/'local_search_prompt.txt'
        prompt_path.write_text(STRICT_LOCAL_PROMPT)
        config.local_search.prompt=str(prompt_path.resolve())
        job['grounding_policy']='context_only_v1'
        config.local_search.max_context_tokens=5000;config.local_search.top_k_entities=8;config.local_search.top_k_relationships=16
        tables={p.stem:pd.read_parquet(p) for p in index_dir.glob('*.parquet')}
        inputs = read(pilot/'inputs.json')['records']
        review = read(pilot/'review.json')
        scoped = any(job.get('source_filters',{}).values())
        if scoped:
            from graphrag_scope import restrict_tables
            tables, inputs, review = restrict_tables(tables, inputs, review, job['source_filters'])
            if {p['id'] for p in inputs} != set(job['scope_input_ids']):
                raise ValueError('El alcance guardado de la pregunta no coincide con sus fuentes')
            if tables['entities'].empty:
                raise ValueError('No hay entidades extraídas en estas fuentes para recuperar contexto del grafo')
            config.local_search.community_prop=0
            config.local_search.text_unit_prop=.6
            write(directory/'source_scope.json',dict(filters=job['source_filters'], input_ids=job['scope_input_ids'],
                  pages=len(inputs),entities=len(tables['entities']),relationships=len(tables['relationships']),
                  policy='Source-scoped descriptions and original text only. Shared community reports excluded. Existing vectors rank eligible entities only.'))
        write(directory/'index_used.json',dict(pilot_run=job['pilot_run'],input_sha256=job['input_sha256'],index_manifest=index_manifest))
        # Retain effective parameters without model authorization tokens.
        effective=config.model_dump(mode='json')
        for group in ('completion_models','embedding_models'):
            for model in effective.get(group,{}).values():
                model.pop('api_key',None)
        write(directory/'query_settings.json',effective)
        import shutil
        shutil.copy2(__file__,directory/'graphrag_queries.py')
        shutil.copy2(Path(__file__).with_name('graphrag_provenance.py'),directory/'graphrag_provenance.py')
        shutil.copy2(Path(__file__).with_name('graphrag_scope.py'),directory/'graphrag_scope.py')
        def phase(name):
            detail=dict(name=name,started=time.time(),status='starting');job['phases'].append(detail);job['status']='waiting_gpu';checkpoint();return detail
        vector=None
        if job['mode']=='local':
            detail=phase('embedding')
            with LocalEngine(directory/'embedding',detail,checkpoint,embedding=True) as engine:
                job['status']='embedding';checkpoint()
                request_started=time.monotonic()
                response=request('/v1/embeddings',dict(model='qwen3-embedding-0.6b',input=[job['question']]),engine.token)
                detail['request_seconds']=time.monotonic()-request_started
                vector=response['data'][0]['embedding']
                if len(vector)!=1024 or not all(math.isfinite(v) for v in vector): raise ValueError('Vector de consulta no válido')
                write(directory/'query_embedding.json',dict(question_sha256=digest(job['question']),vector=vector,model_sha256=detail['model_sha256']))
                engine.check()
            detail.update(status='complete',finished=time.time(),elapsed_seconds=time.time()-detail['started']);checkpoint()
        detail=phase('query')
        with LocalEngine(directory/'query',detail,checkpoint) as engine:
            job['status']='query';checkpoint()
            original=factory.create_embedding
            import graphrag.api.query as query_api
            original_store=query_api.get_embedding_store
            def scoped_store(*args,**kwargs):
                from graphrag_scope import restrict_store
                return restrict_store(original_store(*args,**kwargs),tables['entities'].id.tolist())
            class SavedEmbedding:
                def embedding(self,*,input,**kwargs):
                    if input!=[job['question']] or vector is None: raise ValueError('Se solicitó un vector distinto del calculado localmente')
                    return SimpleNamespace(first_embedding=vector)
            try:
                if job['mode']=='local':
                    factory.create_embedding=lambda settings:SavedEmbedding()
                    if scoped: query_api.get_embedding_store=scoped_store
                    answer,context=await local_search(config,tables['entities'],tables['communities'],tables['community_reports'],tables['text_units'],tables['relationships'],tables.get('covariates'),0,
                        'Answer in the language of the question. Explain uncertainty and attribution, distinguish event date from document date, never infer kinship from surnames, and cite supplied record IDs. Use only the supplied context.',job['question'])
                else:
                    answer,context=await global_search(config,tables['entities'],tables['communities'],tables['community_reports'],0,False,
                        'Answer in the language of the question, distinguish dates and attributed claims, do not infer kinship from surnames, and cite report IDs. Use only supplied context.',job['question'])
                engine.check()
            finally:
                factory.create_embedding=original
                query_api.get_embedding_store=original_store
        detail.update(status='complete',finished=time.time(),elapsed_seconds=time.time()-detail['started'])
        job['status']='preparing_results';checkpoint()
        clean_context={name:json.loads(frame.to_json(orient='records')) if hasattr(frame,'to_json') else frame for name,frame in context.items()}
        entity_ids={row['title']:str(row['id']) for row in tables['entities'].to_dict('records')}
        for node in review['nodes']:node['graph_entity_id']=entity_ids.get(node['id'])
        graph=context_graph(clean_context,review,tables['community_reports'].to_dict('records'),tables['communities'].to_dict('records'),job['mode'],str(answer))
        job.update(status='complete',processed=1,finished=time.time(),answer=answer,context=clean_context,graph=graph,
                   note='El grafo muestra contexto recuperado; sus relaciones no quedan validadas por aparecer en una respuesta. La consulta usa la copia fija del piloto.')
        from graphrag_provenance import analyze_answer, index_records
        write(directory/'answer_analysis.json',analyze_answer(job,index_records(tables),inputs,review))
    except BaseException as error:
        job.update(status='interrupted' if isinstance(error,(KeyboardInterrupt,asyncio.CancelledError)) else 'failed',finished=time.time(),error=str(error) or type(error).__name__)
        raise
    finally:
        checkpoint()
        # The common telemetry reader expects a manifest alongside the worker record.
        write(directory/'manifest.json',job)
        write(directory/'runtime_summary.json',runtime_summary(directory))
        if job.get('auto_fishbone') and job['status']=='complete':
            import research_workspace
            research_workspace.advance_followup(root,key,'knowledge_graph',job.get('session_id'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--job',required=True);args=parser.parse_args()
    asyncio.run(execute(args.root,args.job))
