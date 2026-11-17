"""One saved question, its frozen source readings, and its research diagram."""
import hashlib
import fcntl
import json
import re
import time
from pathlib import Path

import graphrag_queries
import reading_matrix


def key(row):
    return row['document_id'], row['page'], row.get('version', 'original')


def query(root, ident, kind='knowledge_graph', session_id=None):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):
        raise ValueError('Invalid question ID')
    if kind not in ('knowledge_graph', 'matrix'):
        raise ValueError('Invalid question type')
    value = (graphrag_queries.get if kind == 'knowledge_graph' else reading_matrix.get)(Path(root), ident)
    if value.get('session_id') != (session_id or None):
        raise ValueError('This question belongs to another research session')
    return value


def artifact_root(root, ident, kind='knowledge_graph', session_id=None):
    query(root, ident, kind, session_id)
    return (graphrag_queries.path_for if kind == 'knowledge_graph' else reading_matrix.job_path)(Path(root), ident).parent


def save_diagram(root, payload):
    import hypotheses
    ident, kind, session_id = payload.get('query_id'), payload.get('query_kind', 'knowledge_graph'), payload.get('session_id')
    value, rows, _ = evidence(root, ident, kind, session_id)
    allowed = {key(row) for row in rows}
    branches = payload.get('branches')
    if not isinstance(branches, list):
        raise ValueError('Invalid diagram branches')
    for branch in branches:
        if not isinstance(branch, dict) or not isinstance(branch.get('items'), list):
            raise ValueError('Invalid diagram branch')
        for item in branch['items']:
            if not isinstance(item, dict) or not isinstance(item.get('evidence'), list):
                raise ValueError('Invalid diagram evidence')
            for source in item['evidence']:
                if not isinstance(source, dict) or not isinstance(source.get('document_id'), str) or not isinstance(source.get('page'), int) or not isinstance(source.get('version', 'original'), str) or key(source) not in allowed:
                    raise ValueError('Diagram evidence must belong to this question')
    # The originating question is immutable, while hypothesis wording is editable.
    payload = dict(payload, question=value.get('question') or value['questions'][0], query_kind=kind)
    return hypotheses.save(artifact_root(root, ident, kind, session_id), payload)


def evidence(root, ident, kind='knowledge_graph', session_id=None):
    """Resolve sources from stored evidence, never from the generated answer prose."""
    value = query(root, ident, kind, session_id)
    if value['status'] not in ('complete', 'complete_with_errors', 'completed'):
        raise ValueError('Wait for the question to finish before generating its fishbone')
    if kind == 'matrix':
        if len(value['questions']) != 1:
            raise ValueError('Use a single-question run in the investigation workspace')
        return value, value['rows'], {'nodes': [], 'relationships': []}
    run = value.get('pilot_run', '')
    if not re.fullmatch(r'\d{8}T\d{6}', run):
        raise ValueError('Invalid frozen pilot')
    frozen = json.loads((Path(root)/'knowledge_graph/pilot_30/runs'/run/'inputs.json').read_text())['records']
    pages = {}
    def include(row):
        if isinstance(row, dict) and 'document_id' in row:
            pages[key(row)] = row
    graph = value.get('graph') or {'nodes': [], 'relationships': []}
    for row in value.get('context_pages', []):
        include(row['page'] if isinstance(row.get('page'), dict) else row)
    for node in graph.get('nodes', []):
        for mention in node.get('mentions', []):
            include(mention.get('page'))
    for edge in graph.get('relationships', []):
        include(edge.get('page'))
    for citation in value.get('citations', []):
        for record in citation.get('records', []):
            for source in record.get('pages', []):
                include(source.get('page'))
    # Older runs did not persist context_pages. Exact source substrings can safely
    # recover additional pages; no fuzzy or answer-based matching is performed.
    texts = [r.get('text', '') for r in value.get('context', {}).get('sources', [])
             if r.get('in_context', True) not in (False, 0, 'false')]
    rows = []
    for row in frozen:
        if key(row) not in pages and not any(text and text in row['text'] for text in texts):
            continue
        expected = pages.get(key(row), {}).get('text_sha256')
        actual = hashlib.sha256(row['text'].encode()).hexdigest()
        if (expected and expected != actual) or (row.get('text_sha256') and row['text_sha256'] != actual):
            raise ValueError('The frozen source no longer matches its recorded hash')
        rows.append(row)
    if not rows:
        raise ValueError('No source pages could be resolved for this question')
    return value, rows, graph


def manifest(root, ident, kind='knowledge_graph', session_id=None):
    value, rows, graph = evidence(root, ident, kind, session_id)
    fields = ('document_id', 'document', 'folder', 'page', 'version', 'text_sha256', 'review_status')
    return dict(query_id=ident, query_kind=kind, session_id=value.get('session_id'),
                question=value.get('question') or value['questions'][0],
                pages=[{k:r.get(k) for k in fields} for r in rows],
                scope='retrieved_pages' if kind == 'knowledge_graph' else 'saved_session_readings')


def _read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def linked_generation(root, ident, kind, session_id, state=None):
    """Recover the link even if a worker stopped between job creation and linking."""
    import hypotheses_auto
    matches=[]
    for path in (Path(root)/'hypotheses/auto').glob('*/job.json'):
        value=_read(path)
        if value.get('query_id')==ident and value.get('query_kind','knowledge_graph')==kind and value.get('session_id')==(session_id or None):
            matches.append(value)
    if not matches:return None
    return hypotheses_auto.get(root,max(matches,key=lambda v:v.get('started',0))['id'])


def diagram_state(root, ident, kind='knowledge_graph', session_id=None):
    import hypotheses
    value=query(root,ident,kind,session_id)
    base=artifact_root(root,ident,kind,session_id)
    state=_read(base/'fishbone_followup.json')
    generated=linked_generation(root,ident,kind,session_id,state)
    fields=('id','status','updated','started','processed','total','elapsed_seconds','branches','errors','error','model','pilot_run','language','resources_latest','inference_seconds')
    return dict(saved=hypotheses.load(base),generation={k:generated.get(k) for k in fields} if generated else None,
                followup=state,automatic=value.get('auto_fishbone',False))


def advance_followup(root, ident, kind='knowledge_graph', session_id=None, launch=True):
    """Exactly one automatic draft after a successful answer, independent of the UI."""
    import hypotheses, hypotheses_auto
    value=query(root,ident,kind,session_id)
    if not value.get('auto_fishbone') or value['status'] not in ('complete','complete_with_errors'):
        return
    base=artifact_root(root,ident,kind,session_id)
    with (base/'fishbone_followup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=base/'fishbone_followup.json';state=_read(path)
        if state.get('status') in ('complete','complete_with_errors','failed','interrupted'):return state
        job=linked_generation(root,ident,kind,session_id,state)
        try:
            if not job:
                if kind=='matrix' and len(value.get('questions',[]))!=1:raise ValueError('Automatic fishbone requires one question')
                created=hypotheses_auto.create(root,dict(scope='query',query_id=ident,query_kind=kind,session_id=session_id,
                    question=value.get('question') or value['questions'][0],author=value.get('author') or 'Local model',
                    language=value.get('language','es')),launch=launch)
                job=hypotheses_auto.get(root,created['id'])
            state=dict(job_id=job['id'],status=job['status'],updated=time.time())
            if job['status'] in ('complete','complete_with_errors','failed','interrupted'):
                # A saved human draft is never overwritten by the automated step.
                if not hypotheses.load(base)['revision']:
                    try:
                        hypotheses.save(base,dict(revision=0,question=value.get('question') or value['questions'][0],
                            author='Local model · automatic draft',query_id=ident,query_kind=kind,session_id=session_id,
                            branches=job['branches'],generation=dict(job=job['id'],model=job.get('model'),scope='query',automatic=True,status=job['status'])))
                    except ValueError:
                        if not hypotheses.load(base)['revision']:raise
                state['error']=job.get('error')
        except hypotheses_auto.BusyError:
            state=dict(status='queued',reason='waiting_fishbone_worker',updated=time.time())
        except (ValueError,OSError,KeyError) as error:
            state=dict(status='failed',error=str(error),updated=time.time())
        reading_matrix.write(path,state)
        return state


def followup_tick(root, launch=True):
    pending=[]
    for kind,pattern in [('knowledge_graph','knowledge_graph/questions/*/question.json'),('matrix','matrices/*/matrix.json')]:
        for path in Path(root).glob(pattern):
            value=_read(path)
            if value.get('auto_fishbone') and value.get('status') in ('complete','complete_with_errors'):
                pending.append((value.get('created',0),kind,value))
    for _,kind,value in sorted(pending,key=lambda item:item[0]):
        try:advance_followup(root,value['id'],kind,value.get('session_id'),launch)
        except (ValueError,OSError,KeyError):continue


def watch_followups(root):
    while True:
        try:followup_tick(root)
        except (ValueError,OSError,KeyError):pass
        time.sleep(4)
