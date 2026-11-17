"""Local, versioned embedding index and durable incremental job scheduling."""
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
MODEL = 'Qwen3-Embedding-0.6B-Q8_0'
MODEL_REVISION = '370f27d7550e0def9b39c1f16d3fbaa13aa67728'
MODEL_SHA = '06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439'
WEIGHTS = PROJECT / 'benchmark/models/Qwen3-Embedding-0.6B-GGUF' / (MODEL + '.gguf')
POLICY = dict(version=1, characters=1800, overlap=200, dimensions=1024,
              pooling='last', normalization='l2', context_tokens=8192)
NAMESPACE = hashlib.sha256(json.dumps([MODEL_SHA, POLICY], sort_keys=True).encode()).hexdigest()
TERMINAL = {'complete', 'failed', 'interrupted'}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read(path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {} if default is None else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('w') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def event(root, kind, **fields):
    path = root / 'embeddings/events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(dict(time=time.time(), event=kind, **fields), ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


@contextlib.contextmanager
def lock(root, name, blocking=True):
    directory = root / 'embeddings'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (name + '.lock')).open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield handle


def scan(root):
    """Only live inventory pages. Every saved reading has independent provenance."""
    root = root.resolve()
    inventory = read(root / 'progress.json')
    if not isinstance(inventory.get('documents'), list):
        raise ValueError('No hay un inventario válido de transcripciones')
    secondary = {}
    for path in sorted((root / 'second_reading').glob('*/case_*/metadata.json')):
        meta = read(path)
        text_path = path.parent / 'transcription.md'
        if text_path.is_file() and text_path.resolve().is_relative_to(root / 'second_reading'):
            secondary.setdefault((meta.get('document'), meta.get('page')), []).append(
                (text_path.read_text(), 'second_reading:' + path.parent.parent.name, 'unreviewed', {}))
    records, pages = [], []
    for doc in inventory['documents']:
        output = Path(doc['output']).resolve()
        if not output.is_relative_to(root / 'documents'):
            raise ValueError('La salida del documento no pertenece al banco local')
        ident = digest(doc['source'])
        for page in range(1, doc['page_count'] + 1):
            pages.append(ident + ':' + str(page))
            path = output / f'page_{page:04}.md'
            original = path.read_text() if path.exists() else ''
            variants = [(original, 'original', 'unreviewed', {})]
            variants += secondary.get((doc['source'], page), [])
            human = read(root / 'reviews' / ident / f'{page}.json')
            if human:
                status = human['status'] if human['original_hash'] == digest(original) else 'stale'
                variants.append((human['text'], 'human', status,
                                 {k: human.get(k) for k in ('revision', 'updated', 'reviewer', 'original_hash')}))
            for text, version, status, metadata in variants:
                if not text.strip():
                    continue
                records.append(dict(key=f'{ident}:{page}:{version}', document_id=ident,
                                    document=doc['source'], folder=doc['folder'], page=page,
                                    version=version, review_status=status, metadata=metadata,
                                    text=text, text_sha256=digest(text)))
    records.sort(key=lambda r: r['key'])
    if len({r['key'] for r in records}) != len(records):
        raise ValueError('Hay lecturas duplicadas para una misma página y versión')
    fingerprint = digest(json.dumps([NAMESPACE, pages, [{k: v for k, v in r.items() if k != 'text'}
                                                        for r in records]], sort_keys=True))
    return dict(records=records, pages=pages, fingerprint=fingerprint)


def chunks(text):
    """Exact character offsets, bounded size, overlap; never crosses a page/version."""
    start = 0
    while start < len(text):
        end = min(len(text), start + POLICY['characters'])
        if end < len(text):
            boundary = max(text.rfind('\n', start + 900, end), text.rfind(' ', start + 900, end))
            if boundary > start:
                end = boundary + 1
        if text[start:end].strip():
            yield start, end, text[start:end]
        if end == len(text):
            break
        start = max(start + 1, end - POLICY['overlap'])


def connect(root):
    (root / 'embeddings').mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / 'embeddings/index.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS vectors (
          key TEXT PRIMARY KEY, namespace TEXT NOT NULL, text_sha256 TEXT NOT NULL,
          vector BLOB NOT NULL, dimensions INTEGER NOT NULL, tokens INTEGER NOT NULL,
          inference_seconds REAL NOT NULL, run_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS readings (
          key TEXT PRIMARY KEY, text_sha256 TEXT NOT NULL, record TEXT NOT NULL, run_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks (
          reading_key TEXT NOT NULL, ordinal INTEGER NOT NULL, start INTEGER NOT NULL,
          end INTEGER NOT NULL, vector_key TEXT NOT NULL, PRIMARY KEY(reading_key,ordinal));
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    return db


def process_stamp(pid):
    try:
        # comm may contain spaces; starttime is field 22 after the closing parenthesis.
        return Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, ValueError):
        return None


def current(root):
    pointer = read(root / 'embeddings/latest.json')
    key = pointer.get('run_id', '')
    if not re.fullmatch('[a-f0-9]{32}', key):
        return {}
    path = root / 'embeddings/runs' / key / 'manifest.json'
    value = read(path)
    if value.get('status') not in TERMINAL and time.time() - value.get('updated', 0) > 30:
        if not value.get('pid') or not process_stamp(value['pid']) or process_stamp(value['pid']) != value.get('pid_start'):
            with lock(root, 'jobs'):
                value = read(path)
                if value.get('status') not in TERMINAL and (not value.get('pid') or not process_stamp(value['pid']) or process_stamp(value['pid']) != value.get('pid_start')):
                    value.update(status='interrupted', finished=time.time(), error='El proceso se interrumpió; los vectores ya calculados se reutilizarán.')
                    write(path, value)
                    event(root, 'embedding_interrupted', run_id=key)
    return value


def start(root, reason='manual'):
    root = root.resolve()
    existing = current(root)
    with lock(root, 'jobs'):
        existing = read(root / 'embeddings/latest.json')
        if existing.get('run_id'):
            job = read(root / 'embeddings/runs' / existing['run_id'] / 'manifest.json')
            if job.get('status') not in TERMINAL:
                return job
        key = uuid.uuid4().hex
        directory = root / 'embeddings/runs' / key
        job = dict(run_id=key, reason=reason, status='queued', started=time.time(), updated=time.time(),
                   model=MODEL, namespace=NAMESPACE, processed=0, generated_vectors=0)
        write(directory / 'manifest.json', job)
        write(root / 'embeddings/latest.json', dict(run_id=key))
        write(root / 'embeddings/enabled.json', dict(enabled=True))
        event(root, 'embedding_requested', run_id=key, reason=reason)
        env = dict(os.environ)
        env.pop('NOTIFY_SOCKET', None)
        with (directory / 'worker.log').open('ab') as log:
            try:
                child = subprocess.Popen([sys.executable, str(HERE / 'embedding_worker.py'), '--root', str(root), '--run', key],
                                         stdout=log, stderr=log, env=env, start_new_session=True)
            except OSError as error:
                job.update(status='failed', error=str(error), finished=time.time())
                write(directory / 'manifest.json', job)
                raise
        # Worker takes jobs.lock before its first write; avoids a startup overwrite race.
        job.update(pid=child.pid, pid_start=process_stamp(child.pid))
        write(directory / 'manifest.json', job)
        threading.Thread(target=child.wait, daemon=True).start()
        return job


def status(root, snapshot=None):
    snapshot = snapshot or scan(root)
    job = current(root)
    indexed, counts, metadata = {}, {}, {}
    if (root / 'embeddings/index.sqlite3').exists():
        with contextlib.closing(connect(root)) as db:
            metadata = dict(db.execute('SELECT key,value FROM meta'))
            indexed = {r['key']: r['text_sha256'] for r in db.execute('SELECT key,text_sha256 FROM readings')}
            counts = dict(db.execute('SELECT reading_key,count(*) FROM chunks GROUP BY reading_key'))
    compatible = metadata.get('namespace') == NAMESPACE
    page_stats = {p: dict(total=0, current=0, chunks=0) for p in snapshot['pages']}
    for record in snapshot['records']:
        p = page_stats[record['document_id'] + ':' + str(record['page'])]
        p['total'] += 1
        if compatible and indexed.get(record['key']) == record['text_sha256']:
            p['current'] += 1
            p['chunks'] += counts.get(record['key'], 0)
    samples = []
    if job:
        path = root / 'embeddings/runs' / job['run_id'] / 'telemetry.jsonl'
        if path.exists():
            for line in path.read_text().splitlines()[-160:]:
                try:
                    samples.append(json.loads(line))
                except ValueError:
                    pass
    folders = {}
    for record in snapshot['records']:
        folders.setdefault(record['folder'], set()).add(record['document_id'] + ':' + str(record['page']))
    folder_stats = {folder: dict(current=sum(page_stats[p]['current'] == page_stats[p]['total'] for p in pages), total=len(pages))
                    for folder, pages in folders.items()}
    return dict(enabled=bool(read(root / 'embeddings/enabled.json').get('enabled')),
                model=MODEL, dimensions=POLICY['dimensions'], job=job,
                stale=metadata.get('fingerprint') != snapshot['fingerprint'],
                fingerprint=snapshot['fingerprint'], total_readings=len(snapshot['records']),
                current_readings=sum(p['current'] for p in page_stats.values()),
                total_pages=len(page_stats), current_pages=sum(p['total'] > 0 and p['total'] == p['current'] for p in page_stats.values()),
                pages_without_text=sum(p['total'] == 0 for p in page_stats.values()),
                chunks=sum(p['chunks'] for p in page_stats.values()), pages=page_stats, folders=folder_stats, telemetry=samples)


def history(root):
    values = [read(p) for p in (root / 'embeddings/runs').glob('*/manifest.json')]
    return sorted(values, key=lambda r: r.get('started', 0), reverse=True)


def bundle(root, key):
    if not re.fullmatch('[a-f0-9]{32}', key):
        raise ValueError('Proceso inválido')
    directory = root / 'embeddings/runs' / key
    if not directory.is_dir():
        raise ValueError('Proceso desconocido')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in directory.iterdir():
            if path.is_file() and path.suffix in ('.json', '.jsonl', '.log', '.py'):
                archive.write(path, path.name)
    return stream.getvalue()


def watch(root, interval=5):
    """Survives browser closure; coalesces saved edits and detects external file changes."""
    seen, since = None, time.monotonic()
    while True:
        try:
            if read(root / 'embeddings/enabled.json').get('enabled'):
                snapshot = scan(root)
                if snapshot['fingerprint'] != seen:
                    seen, since = snapshot['fingerprint'], time.monotonic()
                value = status(root, snapshot)
                source_job = read(root / 'sources/job.json')
                source_busy = source_job.get('status') in ('running', 'queued') and time.time() - source_job.get('heartbeat', source_job.get('updated', 0)) < 60
                job = value['job']
                running = job and job.get('status') not in TERMINAL
                failed_same_input = job.get('status') == 'failed' and job.get('fingerprint') == seen
                if value['stale'] and not source_busy and not running and not failed_same_input and time.monotonic() - since >= 15:
                    start(root, 'transcriptions_changed' if job else 'initial_index')
        except Exception as error:
            event(root, 'embedding_watcher_error', error=str(error))
        time.sleep(interval)
