"""Separate the last build attempt from the immutable, published graph."""
import re

from embeddings import read, write


def available_run(directory):
    # Compatibility for graphs published before the active pointer existed.
    key = read(directory / 'active.json').get('run_id') or read(directory / 'latest.json').get('run_id', '')
    return key if re.fullmatch(r'\d{8}T\d{6}', key) else ''


def preserve_available(directory):
    key = available_run(directory)
    run = directory / 'runs' / key
    if key and read(run / 'manifest.json').get('status') == 'complete' and (run / 'review.json').is_file() and (run / 'index_manifest.json').is_file():
        write(directory / 'active.json', dict(run_id=key))


def current_pages(snapshot):
    """One current reading per PDF page; keep original when a correction is stale."""
    pages = {(r['document_id'], r['page']): dict(r) for r in snapshot['records'] if r['version'] == 'original'}
    for row in snapshot['records']:
        if row['version'] == 'human' and row['review_status'] != 'stale':
            pages[(row['document_id'], row['page'])] = dict(row)
    return sorted(pages.values(), key=lambda r: (r['document'], r['page']))


def coverage_changes(records, previous):
    before = {(r['document_id'], r['page']): r for r in previous}
    after = {(r['document_id'], r['page']): r for r in records}
    common = before.keys() & after.keys()
    changed = sum(before[k]['text_sha256'] != after[k]['text_sha256'] or before[k]['version'] != after[k]['version'] for k in common)
    return dict(new_pages=len(after.keys() - before.keys()), changed_pages=changed,
                unchanged_pages=len(common)-changed, removed_pages=len(before.keys()-after.keys()))


def visible_run(directory):
    """An extraction checkpoint can be explored before the full query index exists."""
    pointer = read(directory / 'visible.json')
    active = read(directory / 'active.json')
    key = pointer.get('run_id', '')
    if re.fullmatch(r'\d{8}T\d{6}', key) and pointer.get('published',0) >= active.get('published',0) and (directory/'runs'/key/'review.json').is_file():
        return key
    return available_run(directory)
