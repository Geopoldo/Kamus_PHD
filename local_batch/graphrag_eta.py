"""Explainable wall-time estimate, separate from measured process telemetry."""
import math
import statistics
import time

ACTIVE = {'starting', 'graph', 'embeddings', 'query'}


def estimate(manifest, history=(), now=None):
    now = time.time() if now is None else now
    state = manifest.get('status')
    result = dict(version=1, calculated_at=now, status='calibrating', remaining_seconds=None,
                  lower_seconds=None, upper_seconds=None, estimated_finish=None,
                  basis='Recent non-reused chunks; later stages scaled by pages from a completed run. '
                        'Indicative range, not a statistical confidence interval. Future GPU waits are excluded.',
                  parts=[])
    if state == 'complete':
        return dict(result, status='complete', remaining_seconds=0, lower_seconds=0, upper_seconds=0)
    if state not in ACTIVE:
        return dict(result, status=state or 'not_started')
    phases = manifest.get('phases', [])
    if phases and phases[-1].get('status') == 'waiting_gpu':
        return dict(result, status='waiting_gpu')
    total = manifest.get('total_text_units', 0)
    done = manifest.get('extracted_chunks', 0)
    if not total:
        return result
    remaining = max(0, total-done)
    samples = [s for s in manifest.get('fresh_chunk_seconds', []) if isinstance(s, (int, float)) and math.isfinite(s) and s > 0]
    rate = statistics.mean(samples[-20:]) if len(samples) >= 3 else None
    result.update(sample_chunks=len(samples), rate_source='current_run', remaining_chunks=remaining)
    if rate is None:
        for old in sorted(history, key=lambda m:m.get('started', 0), reverse=True):
            fresh = old.get('extracted_chunks', 0)-old.get('reused_extraction_chunks', 0)
            extraction = next((w for w in old.get('workflows', []) if w['name']=='extract_graph'), None)
            if fresh < 3 or not extraction:
                continue
            stop = extraction.get('finished') or min(old.get('updated', 0), old.get('started', 0)+old.get('elapsed_seconds', 0))
            duration = stop-extraction['started']
            if duration > 0:
                rate = duration/fresh
                result.update(rate_source='previous_run', rate_run=old.get('run_id'), sample_chunks=fresh)
                break
    if remaining:
        if rate is None:
            return result
        result['parts'].append(dict(stage='extraction', remaining_seconds=remaining*rate))
    result['seconds_per_fresh_chunk'] = rate
    completed = sorted((m for m in history if m.get('status')=='complete' and m.get('total', 0)>0),
                       key=lambda m:m.get('started', 0), reverse=True)
    baseline = completed[0] if completed else None
    workflows = manifest.get('workflows', [])
    stages = [('communities', 'workflow', 'create_community_reports'),
              ('embeddings', 'phase', 'embeddings'), ('query', 'phase', 'query')]
    unknown = False
    overrun = False
    for label, kind, name in stages:
        records = workflows if kind=='workflow' else phases
        current = next((r for r in reversed(records) if r['name']==name), None)
        if current and (current.get('finished') or current.get('status')=='complete'):
            continue
        old_records = baseline.get('workflows' if kind=='workflow' else 'phases', []) if baseline else []
        old = next((r for r in old_records if r['name']==name and r.get('elapsed_seconds') is not None), None)
        if not old:
            unknown = True
            continue
        predicted = old['elapsed_seconds']*manifest.get('total', 0)/baseline['total']
        if current:
            predicted -= max(0, now-current['started']-current.get('wait_seconds', 0))
            if predicted <= 0:
                overrun = True
        result['parts'].append(dict(stage=label, remaining_seconds=max(0, predicted), baseline_run=baseline.get('run_id')))
    # Extraction includes a consolidation tail after the last chunk; never report
    # the full build complete while GraphRAG is still working on that tail.
    tail = not remaining and manifest.get('workflow')=='extract_graph' and not any(w['name']=='extract_graph' and w.get('finished') for w in workflows)
    if unknown or overrun or tail:
        return dict(result, status='reestimating' if overrun or tail else 'partial')
    seconds = sum(p['remaining_seconds'] for p in result['parts'])
    if seconds <= 0:
        return dict(result, status='finalizing')
    return dict(result, status='estimated', remaining_seconds=seconds,
                lower_seconds=seconds*.65, upper_seconds=seconds*1.75,
                estimated_finish=now+seconds)
