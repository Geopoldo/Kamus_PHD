"""GPU-only Qwen embeddings. Immutable run evidence, reusable cache, atomic publication."""
import argparse
import array
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import embeddings as index

SERVER = Path(os.environ.get('MAPH_LLAMA_SERVER', str(Path.home() / '.lmstudio/extensions/backends/llama.cpp-linux-x86_64-nvidia-cuda12-avx2-2.28.2/llama-server')))
PORT = 18766


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def resources(pids=()):
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free,memory.used,temperature.gpu,utilization.gpu,power.draw',
                                   '--format=csv,noheader,nounits'], text=True, timeout=10).strip().splitlines()[0].split(',')
    result = dict(zip(('vram_free_mib', 'vram_used_mib', 'temperature_c', 'gpu_util_percent', 'power_watts'), map(float, raw)))
    memory = dict((k, int(v.split()[0])) for k, v in (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines()))
    rss = cpu = read_bytes = write_bytes = 0
    for pid in set(pids):
        try:
            stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            cpu += (int(stat[11]) + int(stat[12])) / os.sysconf('SC_CLK_TCK')
            rss += int(stat[21]) * os.sysconf('SC_PAGE_SIZE') / 1048576
            io = dict((k, int(v)) for k, v in (line.split(':') for line in Path(f'/proc/{pid}/io').read_text().splitlines()))
            read_bytes += io['read_bytes']; write_bytes += io['write_bytes']
        except (OSError, ValueError):
            continue
    result.update(time=time.time(), process_rss_mib=rss, process_cpu_seconds=cpu,
                  process_read_bytes=read_bytes, process_write_bytes=write_bytes,
                  ram_available_gib=memory['MemAvailable'] / 1048576,
                  ram_used_gib=(memory['MemTotal'] - memory['MemAvailable']) / 1048576,
                  cpu_load_1min=os.getloadavg()[0])
    return result


def request(path, data=None, token=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}' + path, data=body, headers=headers)
    # Never inherit HTTP proxy settings for documentary text.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=120) as response:
        return json.load(response)


class Engine:
    def __init__(self, directory, manifest, checkpoint):
        self.directory, self.manifest, self.checkpoint = directory, manifest, checkpoint
        self.process = None
        self.log = self.lock = None
        self.stop = threading.Event()
        self.guard_error = None
        self.samples = []

    def __enter__(self):
        try:
            self.open()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def open(self):
        if not index.WEIGHTS.is_file():
            raise RuntimeError('Falta el modelo local. Consulta local_batch/README.md para instalar los pesos verificados.')
        if sha(index.WEIGHTS) != index.MODEL_SHA:
            raise RuntimeError('La huella del modelo no coincide con la versión registrada')
        if not SERVER.is_file():
            raise RuntimeError('No se encuentra llama-server; configura MAPH_LLAMA_SERVER')
        lock_path = index.PROJECT / 'benchmark/prompt_trial/execution.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = lock_path.open('a')
        self.manifest['status'] = 'waiting_gpu'
        waiting = time.monotonic()
        while True:
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                self.manifest['wait_seconds'] = time.monotonic() - waiting
                self.checkpoint()
                time.sleep(3)
        self.manifest['wait_seconds'] = time.monotonic() - waiting
        policy = index.read(index.HERE / 'inference_policy.json')
        self.reserve = max(1536, policy['minimum_vram_reserve_mib'])
        before = resources([os.getpid()])
        if before['vram_free_mib'] < index.WEIGHTS.stat().st_size / 1048576 + self.reserve + 1024 or before['ram_available_gib'] < 3:
            raise RuntimeError('No hay suficiente memoria libre para el modelo y la reserva GPU')
        if subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True).strip():
            raise RuntimeError('Hay otro proceso de cómputo en la GPU; reintenta cuando termine')
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1', PORT)) == 0:
                raise RuntimeError('El puerto local de embeddings está ocupado')
        command = [str(SERVER), '-m', str(index.WEIGHTS), '--host', '127.0.0.1', '--port', str(PORT),
                   '--embedding', '--pooling', 'last', '--embd-normalize', '2', '-ngl', 'all',
                   '-c', '8192', '-b', '8192', '-ub', '8192', '-np', '1', '-t', '4', '--no-webui', '--offline', '--verbose']
        self.manifest.update(status='loading_model', command=command, engine_sha256=sha(SERVER),
                             gpu_info=subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], text=True).strip(),
                             resource_baseline=before)
        self.checkpoint()
        self.log = (self.directory / 'engine.log').open('ab')
        started = time.monotonic()
        self.token = secrets.token_hex(32)
        self.process = subprocess.Popen(command, stdout=self.log, stderr=self.log, env=dict(os.environ, LLAMA_API_KEY=self.token))
        self.thread = threading.Thread(target=self.monitor, daemon=True)
        self.thread.start()
        while time.monotonic() - started < 180:
            self.check()
            try:
                if request('/health', token=self.token).get('status') == 'ok':
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.5)
        else:
            raise RuntimeError('El modelo no terminó de cargar')
        log_text = (self.directory / 'engine.log').read_text(errors='replace')
        offload = re.search(r'offloaded (\d+)/(\d+) layers to GPU', log_text)
        if not offload or offload[1] != offload[2]:
            raise RuntimeError('No se pudo verificar que todas las capas estén en GPU')
        self.manifest.update(load_seconds=time.monotonic() - started, status='running', gpu_layers=offload[0])
        self.checkpoint()

    def check(self):
        if self.guard_error:
            raise RuntimeError(self.guard_error)
        if self.process and self.process.poll() is not None:
            raise RuntimeError('El motor local se detuvo; consulta engine.log')

    def monitor(self):
        previous, failures = None, 0
        while not self.stop.is_set():
            try:
                sample = resources([os.getpid(), self.process.pid])
                sample.update(stage=self.manifest['status'], processed=self.manifest.get('processed', 0))
                if previous:
                    sample['process_cpu_percent'] = max(0, (sample['process_cpu_seconds'] - previous['process_cpu_seconds']) / (sample['time'] - previous['time']) * 100)
                previous = sample
                self.samples.append(sample)
                with (self.directory / 'telemetry.jsonl').open('a') as handle:
                    handle.write(json.dumps(sample) + '\n'); handle.flush()
                if sample['vram_free_mib'] < self.reserve or sample['ram_available_gib'] < 1.5 or sample['temperature_c'] >= 87:
                    self.guard_error = 'Se alcanzó el límite de seguridad de memoria o temperatura'
                failures = 0
            except Exception as error:
                failures += 1
                if failures >= 3:
                    self.guard_error = 'No se pueden medir los recursos: ' + str(error)
            if self.guard_error and self.process.poll() is None:
                self.process.terminate()
            self.stop.wait(2)

    def embed(self, text):
        self.check()
        tokenized = request('/tokenize', dict(content=text, add_special=True), self.token)['tokens']
        if len(tokenized) > index.POLICY['context_tokens'] - 2:
            raise RuntimeError('El fragmento excede el contexto; no se truncó el texto')
        started = time.monotonic()
        value = request('/v1/embeddings', dict(input=text, encoding_format='float'), self.token)
        self.check()
        return value['data'][0]['embedding'], value.get('usage', {}).get('prompt_tokens', len(tokenized)), time.monotonic() - started

    def __exit__(self, *_):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()
        self.stop.set()
        if hasattr(self, 'thread'):
            self.thread.join(timeout=12)
        if self.log:
            self.log.close()
        if self.lock:
            self.lock.close()
        if self.samples:
            metrics = ('gpu_util_percent', 'vram_used_mib', 'temperature_c', 'power_watts', 'process_rss_mib', 'ram_used_gib', 'process_cpu_percent')
            self.manifest['resources'] = {
                k: dict(peak=max(s[k] for s in self.samples if k in s), mean=sum(s[k] for s in self.samples if k in s) / sum(k in s for s in self.samples))
                for k in metrics if any(k in s for s in self.samples)}
            self.manifest['gpu_energy_wh_estimated'] = sum((b['time'] - a['time']) * (a['power_watts'] + b['power_watts']) / 7200 for a, b in zip(self.samples, self.samples[1:]))
            self.manifest['telemetry_samples'] = len(self.samples)


def encode(vector):
    if len(vector) != index.POLICY['dimensions'] or not all(isinstance(x, (float, int)) and math.isfinite(x) for x in vector):
        raise ValueError('Vector inválido o dimensión incorrecta')
    norm = math.sqrt(sum(x*x for x in vector))
    if norm <= 0:
        raise ValueError('El modelo devolvió un vector vacío')
    value = array.array('f', (x/norm for x in vector))
    if sys.byteorder != 'little':
        value.byteswap()
    return value.tobytes()


def execute(root, key, factory=Engine):
    if not re.fullmatch('[a-f0-9]{32}', key):
        raise ValueError('Proceso inválido')
    directory = root / 'embeddings/runs' / key
    with index.lock(root, 'worker'):
        with index.lock(root, 'jobs'):
            manifest = index.read(directory / 'manifest.json')
            if manifest.get('status') in index.TERMINAL:
                return manifest
            manifest.update(pid=os.getpid(), pid_start=index.process_stamp(os.getpid()), status='scanning')
        def checkpoint():
            manifest.update(updated=time.time(), elapsed_seconds=time.time()-manifest['started'])
            generated = manifest.get('generated_vectors', 0)
            if generated:
                mean = manifest['inference_seconds'] / generated
                manifest['eta_seconds'] = max(0, manifest.get('vectors_needed', 0)-generated) * mean
            index.write(directory / 'manifest.json', manifest)
        checkpoint()
        db = None
        try:
            snapshot = index.scan(root)
            manifest.update(fingerprint=snapshot['fingerprint'], namespace=index.NAMESPACE, model=index.MODEL,
                            model_revision=index.MODEL_REVISION, model_sha256=index.MODEL_SHA,
                            policy=index.POLICY, platform=platform.platform(), python=sys.version,
                            code_sha256=sha(Path(__file__)), manager_sha256=sha(Path(index.__file__)),
                            placement='all_model_layers_gpu', total_readings=len(snapshot['records']),
                            total_pages=len(snapshot['pages']), processed=0, generated_vectors=0,
                            inference_seconds=0, tokens=0, changed_readings=0, reused_readings=0,
                            telemetry_scope='GPU/VRAM/power are whole-card measurements. RSS/CPU/IO include worker and engine only. Energy is sampled whole-card estimate, not attributable model-only energy.')
            index.write(directory / 'inputs.json', snapshot)
            shutil.copy2(__file__, directory / 'embedding_worker.py')
            shutil.copy2(index.__file__, directory / 'embeddings.py')
            db = index.connect(root)
            old = dict(db.execute('SELECT key,text_sha256 FROM readings'))
            existing = {r['key'] for r in db.execute('SELECT key FROM vectors WHERE namespace=? AND dimensions=? AND length(vector)=?', (index.NAMESPACE, index.POLICY['dimensions'], index.POLICY['dimensions']*4))}
            planned, missing = [], {}
            for record in snapshot['records']:
                manifest['reused_readings' if old.get(record['key']) == record['text_sha256'] else 'changed_readings'] += 1
                parts = []
                for ordinal, (start, end, text) in enumerate(index.chunks(record['text'])):
                    text_hash = index.digest(text)
                    vector_key = index.digest(index.NAMESPACE + ':' + text_hash)
                    part = dict(reading_key=record['key'], ordinal=ordinal, start=start, end=end,
                                vector_key=vector_key, text_sha256=text_hash)
                    parts.append(part)
                    if vector_key not in existing:
                        missing.setdefault(vector_key, (text, text_hash))
                planned.append((record, parts))
            manifest.update(total_chunks=sum(len(p) for _, p in planned), vectors_needed=len(missing),
                            reused_vectors=len({p['vector_key'] for _, parts in planned for p in parts} & existing),
                            removed_readings=len(set(old)-{r['key'] for r in snapshot['records']}))
            checkpoint()
            if missing:
                with factory(directory, manifest, checkpoint) as engine:
                    for vector_key, (text, text_hash) in missing.items():
                        vector, tokens, seconds = engine.embed(text)
                        encoded = encode(vector)
                        db.execute('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?,?,?,?,?)',
                                   (vector_key, index.NAMESPACE, text_hash, encoded, index.POLICY['dimensions'], tokens, seconds, key))
                        db.commit()  # Durable cache survives interruption; publication remains atomic.
                        manifest['generated_vectors'] += 1; manifest['tokens'] += tokens
                        manifest['inference_seconds'] += seconds
                        with (directory / 'vectors.jsonl').open('a') as handle:
                            handle.write(json.dumps(dict(vector_key=vector_key, text_sha256=text_hash,
                                                         tokens=tokens, seconds=seconds, completed=time.time())) + '\n')
                        checkpoint()
            manifest['status'] = 'publishing'; checkpoint()
            # A reader sees either complete generation, never partial page versions.
            with db:
                db.execute('DELETE FROM chunks'); db.execute('DELETE FROM readings')
                for record, parts in planned:
                    metadata = {k: v for k, v in record.items() if k != 'text'}
                    db.execute('INSERT INTO readings VALUES (?,?,?,?)', (record['key'], record['text_sha256'], json.dumps(metadata, ensure_ascii=False), key))
                    db.executemany('INSERT INTO chunks VALUES (:reading_key,:ordinal,:start,:end,:vector_key)', parts)
                for name, value in (('fingerprint', snapshot['fingerprint']), ('namespace', index.NAMESPACE), ('run_id', key)):
                    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (name, value))
            index.write(directory / 'chunks.json', [p for _, parts in planned for p in parts])
            manifest.update(status='complete', finished=time.time(), processed=len(planned),
                            processed_pages=len({(record['document_id'],record['page']) for record,_ in planned}),
                            changed_during_run=index.scan(root)['fingerprint'] != snapshot['fingerprint'],
                            index_bytes=(root / 'embeddings/index.sqlite3').stat().st_size,
                            tokens_per_second=manifest['tokens']/manifest['inference_seconds'] if manifest['inference_seconds'] else 0)
            index.event(root, 'embedding_completed', run_id=key, generated=manifest['generated_vectors'], reused=manifest['reused_vectors'], fingerprint=manifest['fingerprint'])
        except BaseException as error:
            manifest.update(status='interrupted' if isinstance(error, (SystemExit, KeyboardInterrupt)) else 'failed',
                            error=str(error), finished=time.time())
            index.event(root, 'embedding_' + manifest['status'], run_id=key, error=str(error))
            raise
        finally:
            if db:
                db.close()
            checkpoint()
        return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run')
    args = parser.parse_args()
    def stop(signum, frame):
        raise SystemExit('Proceso interrumpido; se conserva la caché de vectores')
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, stop)
    if args.run:
        execute(args.root.resolve(), args.run)
    else:
        for attempt in range(3):
            job = index.start(args.root.resolve(), 'source_pipeline')
            while job.get('status') not in index.TERMINAL:
                time.sleep(2)
                job = index.current(args.root.resolve())
            if job['status'] != 'complete':
                raise SystemExit(job.get('error', 'No se pudieron generar los embeddings'))
            if not index.status(args.root.resolve())['stale']:
                break
        else:
            raise SystemExit('Las lecturas siguen cambiando; el observador continuará la actualización incremental.')
