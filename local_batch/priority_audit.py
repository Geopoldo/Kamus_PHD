"""Local append-only history of catalogue edits and their search recalculations."""
import collections
import json
import os
import threading
import time
import uuid

_lock = threading.Lock()


def path(root):
    return root / 'priorities' / 'events.jsonl'


def append(root, event, **fields):
    entry = dict(id=str(uuid.uuid4()), timestamp=time.time(), event=event, **fields)
    destination = path(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _lock, destination.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return entry


def history(root, limit=100):
    destination = path(root)
    if not destination.exists():
        return dict(events=[], total=0)
    events = collections.deque(maxlen=limit)
    total = 0
    with _lock, destination.open(encoding='utf-8') as stream:
        for line in stream:
            entry = json.loads(line)
            events.append(entry)
            total += 1
    return dict(events=list(reversed(events)), total=total)
