"""Local geography annotations; displaying the map never contacts a geocoder."""
import json
import math
import os
import threading
import time
from urllib.parse import urlsplit

import priority_catalog

_lock = threading.Lock()


def read(root):
    path = root / 'geography' / 'locations.json'
    return json.loads(path.read_text()) if path.exists() else {'revision': 0, 'items': {}}


def get(root):
    value = read(root)
    places = [e for e in priority_catalog.get(root)['entities'] if e['kind'] == 'place' and e['enabled']]
    items = {}
    for e in places:
        entry = dict(value['items'].get(e['id'], {}))
        entry['needs_recheck'] = bool(entry and entry.get('label') != e['label'])
        items[e['id']] = entry
    return {'revision': value['revision'], 'items': items}


def save(root, payload):
    with _lock:
        value = read(root)
        if payload.get('revision') != value['revision']:
            raise FileExistsError('Las ubicaciones cambiaron. Vuelve a abrir el mapa.')
        entity = next((e for e in priority_catalog.get(root)['entities']
                       if e['id'] == payload.get('entity') and e['kind'] == 'place' and e['enabled']), None)
        if not entity:
            raise ValueError('Selecciona un lugar activo del catálogo.')
        status = payload.get('status')
        if status not in ('proposed', 'unconfirmed', 'confirmed', 'unlocated'):
            raise ValueError('Estado geográfico inválido.')
        entry = {'label': entity['label'], 'status': status, 'updated': time.time()}
        for key, limit in [('feature_name', 200), ('source_url', 2000), ('note', 2000), ('reviewer', 200)]:
            text = payload.get(key, '')
            if not isinstance(text, str) or len(text) > limit:
                raise ValueError('Revisa los campos de la ubicación.')
            entry[key] = text.strip()
        if entry['source_url'] and (urlsplit(entry['source_url']).scheme not in ('https', 'http') or not urlsplit(entry['source_url']).netloc):
            raise ValueError('La referencia debe ser una URL http o https.')
        if status == 'confirmed' and not entry['reviewer']:
            raise ValueError('Indica quién confirmó la correspondencia geográfica.')
        if status == 'unconfirmed' and not entry['note']:
            raise ValueError('Explica qué falta por confirmar sobre esta localización.')
        if status != 'unlocated':
            for key, limit in [('latitude', 90), ('longitude', 180)]:
                number = payload.get(key)
                if isinstance(number, bool) or not isinstance(number, (float, int)) or not math.isfinite(number) or not -limit <= number <= limit:
                    raise ValueError('Latitud o longitud inválida.')
                entry[key] = number
            if not entry['feature_name']:
                raise ValueError('Indica el nombre de la ubicación elegida.')
        previous = value['items'].get(entity['id'])
        if previous and previous.get('candidates'):
            entry['candidates'] = previous['candidates']
        value['items'][entity['id']] = entry
        value['revision'] += 1
        directory = root / 'geography'; directory.mkdir(exist_ok=True, parents=True)
        # Write the audit first so a successful replacement always has evidence.
        with (directory / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': 'location_saved', 'revision': value['revision'],
                'entity': entity['id'], 'before': previous, 'after': entry, 'time': time.time()}, ensure_ascii=False) + '\n')
            stream.flush(); os.fsync(stream.fileno())
        temporary = directory / 'locations.tmp'
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        temporary.replace(directory / 'locations.json')
        return get(root)
