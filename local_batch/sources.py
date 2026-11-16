"""Local PDF intake, reversible source removal and durable pipeline jobs."""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import uuid
import review

HERE = Path(__file__).resolve().parent
MAX_UPLOAD = 100 * 1024 * 1024
RUNNING = {'queued', 'running'}


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {} if default is None else copy.deepcopy(default)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def base(root):
    return Path(read(root/'sources'/'config.json').get('source_root', HERE.parent/'Map-H-DATA')).resolve()


def ident(source):
    return hashlib.sha256(source.encode()).hexdigest()


def safe_path(root, name):
    if not isinstance(name, str) or len(name) > 600 or '\\' in name or any(ord(c) < 32 for c in name):
        raise ValueError('Nombre de fuente inválido')
    parts = name.split('/')
    if not parts or any(p in ('', '.', '..') or p.startswith('.') or len(p) > 180 for p in parts):
        raise ValueError('Usa carpetas y nombres de archivo, sin rutas absolutas ni puntos ocultos')
    path = base(root).joinpath(*parts)
    if not path.resolve().is_relative_to(base(root)) or any(base(root).joinpath(*parts[:n]).is_symlink() for n in range(1,len(parts)+1)):
        raise ValueError('Ruta de fuente no permitida')
    if PurePosixPath(name).suffix.lower() != '.pdf':
        raise ValueError('Esta versión admite fuentes PDF')
    return path


def metadata(root):
    return read(root/'sources'/'catalog.json', {'revision': 0, 'items': {}, 'trash': {}})


def audit(root, event, **fields):
    path = root/'sources'/'events.jsonl'; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(dict(event=event, time=time.time(), **fields), ensure_ascii=False)+'\n')
        stream.flush(); os.fsync(stream.fileno())


@contextmanager
def lock(root, blocking=False):
    path = root/'sources'/'management.lock'; path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError:
            raise FileExistsError('Hay un proceso de fuentes activo. Espera a que termine.')
        yield stream


def process_alive(job):
    try:
        stat = Path(f"/proc/{int(job['pid'])}/stat").read_text().split()
        return stat[21] == job['process_start'] and stat[2] != 'Z'
    except (OSError, KeyError, ValueError):
        return False


def job_status(root):
    job = read(root/'sources'/'job.json')
    if job.get('status') in RUNNING and not process_alive(job):
        job = dict(job, status='interrupted', error='El proceso se interrumpió. Puedes continuarlo; las páginas guardadas se conservan.')
    return job


def ensure_idle(root):
    if job_status(root).get('status') in RUNNING:
        raise FileExistsError('Ya hay fuentes en proceso. Espera a que termine.')


def summarize(progress):
    docs = progress['documents']; pages = [p for d in docs for p in d['pages']]; groups = {}
    finished = ('complete', 'needs_review', 'failed')
    for doc in docs:
        group = groups.setdefault(doc['folder'], dict(documents=0, finished=0, pages=0, processed=0, failed=0, review=0))
        group['documents'] += 1; group['finished'] += doc['status'] in finished; group['pages'] += doc['page_count']
        for page in doc['pages']:
            group['processed'] += page['status'] in finished
            group['failed'] += page['status'] == 'failed'; group['review'] += page['status'] == 'needs_review'
    total = sum(d['page_count'] for d in docs); processed = sum(p['status'] in finished for p in pages)
    progress['summary'] = dict(documents=len(docs), documents_finished=sum(d['status'] in finished for d in docs), pdf_pages=total,
                              processed=processed, remaining=total-processed, failed=sum(p['status']=='failed' for p in pages),
                              review=sum(p['status']=='needs_review' for p in pages), folders=groups,
                              elapsed_seconds=max(0, time.time()-progress.get('started', time.time())))
    progress['updated'] = time.time(); progress['current'] = None
    progress['stage'] = 'inventory' if total > processed else 'finished'
    progress['error'] = None
    return progress


def recover(root):
    # An interrupted move is rolled back before exposing a new inventory.
    for path in (root/'sources'/'transactions').glob('*.json'):
        transaction = read(path)
        if transaction.get('status') != 'prepared':
            continue
        for src, dest in reversed(transaction['moves']):
            src, dest = Path(src), Path(dest)
            if dest.exists() and not src.exists():
                src.parent.mkdir(parents=True, exist_ok=True); dest.replace(src)
        write(root/'progress.json', transaction['before_progress'])
        write(root/'inventory.json', transaction['before_progress']['documents'])
        write(root/'sources'/'catalog.json', transaction['before_catalog'])
        transaction['status'] = 'rolled_back'; write(path, transaction)
        audit(root, 'source_transaction_recovered', transaction=path.stem)


def commit(root, before, previous_catalog, progress, catalog, moves):
    path = root/'sources'/'transactions'/(uuid.uuid4().hex+'.json')
    transaction = dict(status='prepared', before_progress=before, before_catalog=previous_catalog,
                       moves=[[str(a), str(b)] for a, b in moves])
    write(path, transaction)
    try:
        for source, target in moves:
            if target.exists():
                raise FileExistsError('Ya existe un archivo en el destino')
            target.parent.mkdir(parents=True, exist_ok=True); source.replace(target)
        catalog['revision'] += 1
        write(root/'sources'/'catalog.json', catalog)
        write(root/'inventory.json', progress['documents'])
        write(root/'progress.json', summarize(progress))
        transaction['status'] = 'committed'; write(path, transaction)
    except BaseException:
        recover(root)
        raise


def needs_pipeline(doc, catalog):
    entry = catalog['items'].get(ident(doc['source']), {})
    return entry.get('pipeline_status') in ('pending', 'running', 'failed', 'partial') or not doc['pages'] or any(p['status'] not in ('complete', 'needs_review') or not (Path(doc['output'])/f"page_{p['number']:04}.md").is_file() for p in doc['pages'])


def listing(root):
    try:
        with lock(root): recover(root)
        busy = False
    except FileExistsError:
        busy = True
    progress = read(root/'progress.json', {'documents': []}); catalog = metadata(root); reviews = review.index(root)
    docs = []
    for doc in progress['documents']:
        key = ident(doc['source']); entry = catalog['items'].get(key, {})
        pages = [dict(number=p['number'], status=p['status'], transcribed=p['status'] in ('complete', 'needs_review') and (Path(doc['output'])/f"page_{p['number']:04}.md").is_file(),
                      human_status=reviews.get(key+':'+str(p['number']), {}).get('status', ''), flags=p.get('flags', [])) for p in doc['pages']]
        docs.append(dict(id=key, source=doc['source'], folder=doc['folder'], pages=pages, page_count=doc['page_count'],
                         transcribed=sum(p['transcribed'] for p in pages), status=doc['status'],
                         original_available=safe_path(root, doc['source']).is_file(),
                         pipeline_status=entry.get('pipeline_status', 'existing'), pending=needs_pipeline(doc, catalog)))
    job = job_status(root)
    return dict(documents=docs, trash=[dict(id=key, source=item['document']['source'], folder=item['document']['folder'],
                page_count=item['document']['page_count'], removed=item['removed']) for key, item in catalog['trash'].items()],
                revision=catalog['revision'], job=job, busy=busy or job.get('status') in RUNNING,
                pending=sum(d['pending'] for d in docs), max_upload_bytes=MAX_UPLOAD)


def upload(root, name, stream, length):
    if not 0 < length <= MAX_UPLOAD:
        raise ValueError('Cada PDF puede ocupar como máximo 100 MB')
    target = safe_path(root, name)
    with lock(root):
        recover(root); ensure_idle(root)
        incoming = root/'sources'/'incoming'; incoming.mkdir(parents=True, exist_ok=True)
        temporary = incoming/(uuid.uuid4().hex+'.pdf')
        try:
            remaining = length; digest = hashlib.sha256()
            with temporary.open('xb') as output:
                while remaining:
                    block = stream.read(min(1024*1024, remaining))
                    if not block: raise ValueError('La carga del PDF quedó incompleta')
                    output.write(block); digest.update(block); remaining -= len(block)
                output.flush(); os.fsync(output.fileno())
            with temporary.open('rb') as uploaded:
                if b'%PDF-' not in uploaded.read(1024): raise ValueError('El archivo no es un PDF válido')
            try:info = subprocess.run(['pdfinfo', str(temporary)], capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:raise ValueError('El PDF tardó demasiado en abrirse; no se agregó al inventario')
            count = re.search(r'^Pages:\s+(\d+)', info.stdout, re.M)
            if info.returncode or not count: raise ValueError('No se puede leer el PDF. Comprueba que no esté dañado ni protegido.')
            count = int(count[1])
            if not 1 <= count <= 10000: raise ValueError('El PDF debe tener entre 1 y 10.000 páginas')
            sha = digest.hexdigest(); before = read(root/'progress.json'); old = metadata(root)
            exists = next((d for d in before['documents'] if d['source'] == name), None)
            if exists:
                if exists['sha256'] == sha and target.is_file():
                    return dict(id=ident(name), source=name, duplicate=True, pages=count)
                raise FileExistsError('Ya existe una fuente con ese nombre. Usa otro nombre o retira primero la existente.')
            if target.exists(): raise FileExistsError('Ese archivo ya existe en la carpeta de fuentes; no se sobrescribió.')
            rel = PurePosixPath(name); output = root/'documents'/str(rel.parent)/(rel.stem+'-'+sha[:10])
            doc = dict(source=name, folder=str(rel.parent), sha256=sha, page_count=count,
                       pages=[dict(number=n, status='pending') for n in range(1, count+1)], status='pending', output=str(output.resolve()))
            progress = copy.deepcopy(before); progress['documents'].append(doc); progress['documents'].sort(key=lambda d:d['source'])
            catalog = copy.deepcopy(old); catalog['items'][ident(name)] = dict(added=time.time(), pipeline_status='pending')
            commit(root, before, old, progress, catalog, [(temporary, target)])
            audit(root, 'source_added', source=name, document_id=ident(name), sha256=sha, pages=count, bytes=length)
            return dict(id=ident(name), source=name, duplicate=False, pages=count)
        finally:
            temporary.unlink(missing_ok=True)


def archive(root, ids):
    if not isinstance(ids, list) or not ids or len(ids) > 5000 or any(not isinstance(x,str) for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Selecciona fuentes válidas para retirar')
    with lock(root):
        recover(root); ensure_idle(root); before = read(root/'progress.json'); old = metadata(root)
        docs = [d for d in before['documents'] if ident(d['source']) in ids]
        if len(docs) != len(ids): raise ValueError('Alguna fuente ya no está en el inventario; actualiza la lista')
        catalog = copy.deepcopy(old); progress = copy.deepcopy(before); moves = []; keys = []
        for doc in docs:
            source = safe_path(root, doc['source']); key = uuid.uuid4().hex; keys.append(key)
            destination = root/'sources'/'trash'/key/'source.pdf'
            if source.is_file(): moves.append((source, destination))
            catalog['trash'][key] = dict(document=doc, removed=time.time(), stored=source.is_file(), metadata=catalog['items'].pop(ident(doc['source']), None))
        progress['documents'] = [d for d in progress['documents'] if ident(d['source']) not in ids]
        commit(root, before, old, progress, catalog, moves)
        audit(root, 'sources_archived', sources=[d['source'] for d in docs], documents=len(docs), pages=sum(d['page_count'] for d in docs), trash=keys)
        return dict(removed=len(docs), trash=keys)


def restore(root, key):
    if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key): raise ValueError('Fuente de papelera inválida')
    with lock(root):
        recover(root); ensure_idle(root); before = read(root/'progress.json'); old = metadata(root)
        item = old['trash'].get(key)
        if not item: raise ValueError('La fuente ya no está en la papelera')
        doc = item['document']; target = safe_path(root, doc['source']); stored = root/'sources'/'trash'/key/'source.pdf'
        if target.exists() or any(d['source']==doc['source'] for d in before['documents']): raise FileExistsError('Ya existe una fuente activa con ese nombre')
        if not stored.is_file(): raise ValueError('El PDF original no estaba disponible al retirarlo; no se puede restaurar')
        catalog = copy.deepcopy(old); del catalog['trash'][key]
        if item['metadata']: catalog['items'][ident(doc['source'])] = item['metadata']
        progress = copy.deepcopy(before); progress['documents'].append(doc); progress['documents'].sort(key=lambda d:d['source'])
        commit(root, before, old, progress, catalog, [(stored, target)])
        audit(root, 'source_restored', source=doc['source'], document_id=ident(doc['source']), trash=key)
        return dict(id=ident(doc['source']), source=doc['source'])


def start(root, ids=None, refresh_only=False, dashboard_url='http://127.0.0.1:8091', launch=True):
    if not re.fullmatch(r'http://127\.0\.0\.1:\d{1,5}', dashboard_url): raise ValueError('El proceso requiere el panel local')
    with lock(root):
        recover(root); ensure_idle(root); progress = read(root/'progress.json'); catalog = metadata(root)
        if ids is not None and (not isinstance(ids, list) or any(not isinstance(x,str) for x in ids)):
            raise ValueError('Selecciona fuentes válidas')
        docs = [] if refresh_only else [d for d in progress['documents'] if (ids is None or ident(d['source']) in ids) and needs_pipeline(d,catalog)]
        if not docs and not refresh_only: return dict(status='complete', stage='complete', no_work=True)
        if any(not safe_path(root,d['source']).is_file() for d in docs): raise ValueError('Falta el PDF original de alguna fuente pendiente')
        key = uuid.uuid4().hex; directory = root/'sources'/'jobs'/key; directory.mkdir(parents=True)
        job = dict(id=key, status='queued', stage='queued', created=time.time(), documents=[d['source'] for d in docs],
                   pages=sum(d['page_count'] for d in docs), refresh_only=refresh_only, dashboard_url=dashboard_url)
        write(directory/'scope.json', job['documents']); write(directory/'job.json',job); write(root/'sources'/'job.json', job)
        if launch:
            with (directory/'process.log').open('ab') as log:
                proc = subprocess.Popen([sys.executable, str(HERE/'source_worker.py'), '--root',str(root.resolve()),'--job',key], stdout=log,stderr=log,start_new_session=True)
            job.update(pid=proc.pid, process_start=Path(f'/proc/{proc.pid}/stat').read_text().split()[21])
            write(directory/'job.json',job);write(root/'sources'/'job.json',job)
        audit(root,'source_pipeline_requested',job=key,documents=job['documents'],refresh_only=refresh_only)
        return job
