"""Reuse an inspection only for the same active page, content and audit policy."""
import copy
import hashlib
import json
from pathlib import Path
import re

VERSION = 'text-model-audit-v2-full-page'


def select(root, documents, scope=None):
    previous = {}
    policies = {}
    pointer = root/'model_audit_latest.json'
    if pointer.exists():
        run = json.loads(pointer.read_text()).get('run_id', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', run):
            raise ValueError('Invalid previous audit')
        directory = root/'model_audits'/run
        manifest = json.loads((directory/'manifest.json').read_text())
        policies[run] = manifest.get('version') == VERSION
        if manifest.get('version') == VERSION:
            for path in (directory/'pages').glob('*/*/classification.json'):
                record = json.loads(path.read_text())
                previous[(record['document'], record['page'])] = record
    retained, pending = [], []
    for doc in documents:
        for page in doc['pages']:
            path = Path(doc['output'])/f"page_{page['number']:04}.md"
            if page['status'] not in ('complete', 'needs_review') or not path.is_file():
                continue
            record = previous.get((doc['source'], page['number']))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            def reusable(item):
                return (item and item.get('document') == doc['source'] and item.get('page') == page['number']
                        and item.get('input_sha256') == digest and item.get('classification') != 'model_inconclusive')
            # Restored PDFs may have disappeared from the latest active snapshot.
            # Recover an unchanged inspection from immutable history, never from a different policy.
            if not reusable(record):
                ident = hashlib.sha256(doc['source'].encode()).hexdigest()
                for old in sorted((root/'model_audits').glob(f'*/pages/{ident}/{page["number"]}/classification.json'), reverse=True):
                    run = old.parents[3].name
                    if run not in policies:
                        manifest_path = old.parents[3]/'manifest.json'
                        policies[run] = manifest_path.is_file() and json.loads(manifest_path.read_text()).get('version') == VERSION
                    if policies[run]:
                        candidate = json.loads(old.read_text())
                        if reusable(candidate):
                            record = candidate
                            break
            if reusable(record):
                record = copy.deepcopy(record)
                record['reused_from'] = record['run_id']
                retained.append(record)
            elif scope is None or doc['source'] in scope:
                pending.append((doc, page))
    return retained, pending


def aggregate(manifest, results):
    manifest.update(processed=len(results), flagged=0, errors=0, counts={}, folders={})
    for record in results:
        code = record['classification']
        manifest['flagged'] += bool(record['findings'])
        manifest['errors'] += code == 'model_inconclusive'
        manifest['counts'][code] = manifest['counts'].get(code, 0)+1
        folder = manifest['folders'].setdefault(record['folder'], dict(processed=0, flagged=0))
        folder['processed'] += 1
        folder['flagged'] += bool(record['findings'])
    fresh = [r for r in results if not r.get('reused_from')]
    manifest['new_pages'] = len(fresh)
    manifest['mean_page_seconds'] = sum(r['audit_seconds'] for r in fresh)/max(1,len(fresh))
    manifest['inference_seconds'] = sum(v['seconds'] for r in fresh for v in r['decisions'])
    manifest['completion_tokens'] = sum((v.get('usage') or {}).get('completion_tokens',0) for r in fresh for v in r['decisions'])
