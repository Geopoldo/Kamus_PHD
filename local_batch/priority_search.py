"""Auditable, local batch search of workbook referents, across every page version.

The workbook is data, never executable instructions. No model or network is used.
"""
import collections
import difflib
import hashlib
import json
import re
import threading
import time
import zipfile
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

from content_search import normalize
import priority_audit as audit

WORKBOOK = Path('/home/ewok/Downloads/Book_priorities_15_11_2026.xlsx')
ENGINE = 'priorities-5'
MAX_INTERVENING_WORDS = 2
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
QUALITY = {'literal': 0, 'alias': 1, 'near': 2, 'candidate': 3, 'cooccurrence': 4, 'clue': 5}
SCORES = {'literal': 100, 'alias': 95, 'near': 85, 'candidate': 60, 'cooccurrence': 20, 'clue': 20}
LABELS = {'literal': 'Texto literal', 'alias': 'Variante del Excel', 'near': 'Proximidad (máx. 2 palabras)',
          'candidate': 'Candidata: revisar', 'cooccurrence': 'Solo palabras separadas: no es coincidencia del nombre completo', 'clue': 'Indicio geográfico parcial'}
_lock = threading.Lock()
_job = {'running': False}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def terms(text):
    return re.findall(r'\w+', normalize(text))


def workbook_rows(path):
    """Read cell values only, including inline/rich strings. Never evaluate formulas."""
    with zipfile.ZipFile(path) as book:
        strings = []
        if 'xl/sharedStrings.xml' in book.namelist():
            strings = [''.join(si.itertext()) for si in ET.fromstring(book.read('xl/sharedStrings.xml'))]
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))}
        sheets = []
        for sheet in ET.fromstring(book.read('xl/workbook.xml')).findall('m:sheets/m:sheet', NS):
            target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            rows = []
            for row in ET.fromstring(book.read(target)).findall('m:sheetData/m:row', NS):
                cells = {}
                for cell in row.findall('m:c', NS):
                    value = cell.find('m:v', NS)
                    value = value.text or '' if value is not None else ''
                    if cell.attrib.get('t') == 's':
                        value = strings[int(value)]
                    elif cell.attrib.get('t') == 'inlineStr':
                        value = ''.join(t.text or '' for t in cell.findall('.//m:t', NS))
                    cells[re.sub(r'\d+', '', cell.attrib['r'])] = value.strip()
                if any(cells.values()):
                    rows.append((int(row.attrib['r']), cells))
            sheets.append((sheet.attrib['name'], rows))
        return sheets


def build_catalog(path=WORKBOOK):
    sheets = workbook_rows(path)
    expected = ['Last_Names_Colin+Camilo', 'Place highest priority', 'Second Priority', 'Lastnames']
    if [s[0] for s in sheets] != expected:
        raise ValueError('Cambió la estructura del Excel: revisar sus cuatro hojas antes de importar.')
    entities, families, persons = [], {}, {}

    def entity(key, label, kind, priority=''):
        e = dict(id=key, label=label, kind=kind, priority=priority, sources=[], patterns=[], notes=[], traplines=[])
        entities.append(e)
        return e

    def source(e, sheet, row, cells):
        record = dict(sheet=sheet, row=row, cells=cells)
        if record not in e['sources']:
            e['sources'].append(record)

    def pattern(e, label, origin='canonical', reason=''):
        tokens = terms(label)
        if tokens and not any(p['terms'] == tokens and p['origin'] == origin for p in e['patterns']):
            e['patterns'].append(dict(label=label, terms=tokens, origin=origin, reason=reason))

    def family(label):
        label = label.rstrip('?').strip()
        key = normalize(label)
        if key not in families:
            families[key] = entity('surname:' + key, label, 'surname')
            pattern(families[key], label)
            families[key]['notes'].append('El apellido no identifica por sí solo a una persona; también puede ser una palabra común.')
        return families[key]

    # Explicit aliases are retained as supplied. Overlapping families are not silently merged.
    for row, cells in sheets[3][1][1:]:
        raw = cells.get('A', '')
        if not raw:
            continue
        base = raw.split('(')[0].strip()
        e = family(base)
        source(e, sheets[3][0], row, cells)
        inside = re.search(r'\((.*?)\)', raw)
        if inside:
            for alias in re.split(r'[;,]', inside[1]):
                pattern(e, alias.strip(), 'alias', 'Variante escrita en el Excel')
        if '?' in raw:
            e['notes'].append('El Excel marca este apellido con interrogación.')

    for row, cells in sheets[0][1][1:]:
        last, first = cells.get('C', ''), cells.get('B', '')
        if not last:
            continue
        f = family(last)
        source(f, sheets[0][0], row, cells)
        if not first:
            continue
        fhid = cells.get('D', '')
        key = 'person:' + (fhid or normalize(first + ' ' + last))
        if key not in persons:
            persons[key] = entity(key, first + ' ' + last, 'person')
            persons[key].update(fhid=fhid, surname_id=f['id'])
            persons[key]['notes'].append('Coincidencia de nombre: comprobar identidad en contexto. El apellido solo se informa en su ficha de familia.')
        e = persons[key]
        source(e, sheets[0][0], row, cells)
        if cells.get('A') and cells['A'] not in e['traplines']:
            e['traplines'].append(cells['A'])
        pattern(e, first + ' ' + last, 'canonical' if e['label'] == first + ' ' + last else 'alias', 'Mismo FHID en el Excel')
        for p in f['patterns']:
            if p['origin'] == 'alias':
                pattern(e, first + ' ' + p['label'], 'alias', 'Nombre con variante explícita del apellido')
        given = re.sub(r'\b(?:Jr|Sr)\.?', '', first, flags=re.I).strip()
        for surname_pattern in f['patterns']:
            surname = surname_pattern['label']
            for variant in [given + ' ' + surname, surname + ' ' + given,
                            given.split()[0] + ' ' + surname, given[0] + ' ' + surname]:
                if not any(p['terms'] == terms(variant) for p in e['patterns']):
                    pattern(e, variant, 'generated', 'Nombre abreviado, sin sufijo o en orden invertido; identidad por revisar')

    # The following decompositions are explicit interpretations, never asserted synonyms.
    decomposed = {
        'Turgeon and Harricanaw/Harricana river': [('Turgeon', 'Turgeon'), ('Harricanaw', 'Harricanaw'), ('Harricana', 'Harricana')],
        'Lake Abitibinorthwesterly drainage': [('Lake Abitibi', 'Lake Abitibi'), ('Abitibi', 'Abitibi')],
        'the coastal strip running northwest from the mouth of the Moose River to Black Bear Point':
            [('Moose River', 'Moose River'), ('Black Bear Point', 'Black Bear Point'), ('Albany River', 'Albany River')],
    }
    for sheet, rows in sheets[1:3]:
        for row, cells in rows[1:]:
            label = cells.get('A', '')
            if not label:
                continue
            e = entity('place:' + str(len(entities)), label, 'place', 'Alta' if sheet == expected[1] else 'Media')
            source(e, sheet, row, cells)
            if cells.get('B'):
                e['notes'].append(cells['B'])
            pattern(e, label)
            aliases = [label]
            if label == 'Lawagamau/Katawagami':
                aliases = ['Lawagamau', 'Katawagami']
            elif label == 'Harricanaw/Harricana river':
                aliases = ['Harricanaw river', 'Harricana river']
            for alias in aliases:
                if alias != label:
                    pattern(e, alias, 'alias', 'Variante separada por / en el Excel')
            if label in decomposed:
                e['notes'].append('Área o referencia compuesta: las menciones de sus lugares son indicios parciales, no demuestran el área completa.')
                for anchor, _ in decomposed[label]:
                    pattern(e, anchor, 'context', 'Ancla de una descripción geográfica; comprobar relación en contexto')
            else:
                for alias in aliases:
                    tokens = alias.split()
                    core = ' '.join(t for t in tokens if normalize(t) not in {'lake', 'river', 'rivers', 'creek', 'lower'})
                    if core != alias:
                        pattern(e, core, 'generated', 'Topónimo sin descriptor geográfico; comprobar qué lugar designa')
                    if normalize(alias).endswith(' rivers'):
                        pattern(e, alias[:-1], 'generated', 'River/Rivers: variante generada')
                    if "'s " in alias:
                        pattern(e, alias.replace("'s ", ' '), 'generated', 'Posesivo omitido; variante generada')

    alias_owners = collections.defaultdict(set)
    for e in entities:
        # Research priority supplied by the user. It is independent of match quality.
        for s in e['sources']:
            s['priority'] = ('Alta' if s['sheet'] in (expected[0], expected[1]) else
                             'Media' if s['sheet'] == expected[2] else 'Baja')
        e['priority'] = min((s['priority'] for s in e['sources']), key={'Alta': 0, 'Media': 1, 'Baja': 2}.get)
        if e['kind'] == 'surname':
            for p in e['patterns']:
                alias_owners[tuple(p['terms'])].add(e['label'])
    for e in entities:
        if e['kind'] == 'surname':
            overlaps = set().union(*(alias_owners[tuple(p['terms'])] for p in e['patterns'])) - {e['label']}
            if overlaps:
                e['notes'].append('Comparte una variante con: ' + ', '.join(sorted(overlaps)) + '. Se conservan como entradas separadas.')
    return dict(workbook=str(path), workbook_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                sheets=[dict(name=name, data_rows=len(rows)-1) for name, rows in sheets],
                entities=entities, counts=dict(collections.Counter(e['kind'] for e in entities)))


def tokens_with_offsets(text):
    # Join words split by OCR line-end hyphens, retaining offsets in untouched text.
    found = list(re.finditer(r'\w+(?:[-\u00ad][ \t]*\r?\n[ \t]*\w+)*', text))
    return [(normalize(re.sub(r'[-\u00ad]\s*', '', m.group())), m.start(), m.end()) for m in found]


def edit_distance(a, b):
    prev = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(cur[-1]+1, prev[j]+1, prev[j-1]+(x != y)))
        prev = cur
    return prev[-1]


def similar(term, word):
    if term == word:
        return True
    if min(len(term), len(word)) < 4:
        return False
    budget = 1 if min(len(term), len(word)) < 8 else 2
    return (abs(len(term)-len(word)) <= budget and
            difflib.SequenceMatcher(None, term, word).ratio() >= .82 and edit_distance(term, word) <= budget)


class Matcher:
    def __init__(self, catalog):
        self.patterns = [(e['id'], p) for e in catalog['entities'] if e.get('enabled', True) for p in e['patterns']]
        fuzzy_terms = {t for _, p in self.patterns for t in p['terms']}
        spacing = {}
        for entity, p in self.patterns:
            ts = p['terms']
            variants = [ts[:i] + [ts[i]+ts[i+1]] + ts[i+2:] for i in range(len(ts)-1)]
            variants += [ts[:i] + [t[:j], t[j:]] + ts[i+1:] for i, t in enumerate(ts)
                         if len(t) >= 6 for j in range(2, len(t)-1)]
            for tokens in variants:
                spacing[(entity, tuple(tokens), p['origin'])] = (entity, dict(p, terms=tokens, origin='spacing',
                    context=p['origin']=='context', reason='Separación o unión de palabras en la transcripción; comprobar en la imagen'))
        self.patterns.extend(spacing.values())
        self.terms = {t for _, p in self.patterns for t in p['terms']}
        self.by_length = collections.defaultdict(list)
        for term in fuzzy_terms:
            self.by_length[len(term)].append(term)
        self.cache = {}
        self.confluences = []
        families = {e['id']: e for e in catalog['entities'] if e['kind'] == 'surname'}
        for e in catalog['entities']:
            if e['kind'] != 'person' or not e.get('enabled', True):
                continue
            forms = e.get('name_forms') or [dict(first_name=s['cells']['B'], last_name=s['cells']['C']) for s in e['sources'] if s['cells'].get('B') and s['cells'].get('C')]
            given = sorted({terms(f['first_name'])[0] for f in forms if terms(f['first_name'])})
            surnames = [terms(f['last_name']) for f in forms]
            if not e.get('name_forms') and e.get('surname_id') in families:
                surnames += [p['terms'] for p in families[e['surname_id']]['patterns']]
            self.confluences.append((e['id'], given, surnames))

    def match(self, text):
        tokens = tokens_with_offsets(text)
        positions = collections.defaultdict(list)
        for i, (word, _, _) in enumerate(tokens):
            if word not in self.cache:
                self.cache[word] = [t for n in range(len(word)-2, len(word)+3)
                                    for t in self.by_length[n] if similar(t, word)]
                if word in self.terms and word not in self.cache[word]:
                    self.cache[word].append(word)
            for term in self.cache[word]:
                positions[term].append(i)
        best = {}
        for entity, pattern in self.patterns:
            ts = pattern['terms']
            max_gap = 0 if pattern['origin'] == 'spacing' else MAX_INTERVENING_WORDS
            for start in positions[ts[0]]:
                paths = [(start, [start], 0)]
                for term in ts[1:]:
                    next_paths = []
                    allowed = set(positions[term])
                    for last, path, gap in paths:
                        for j in range(last+1, min(len(tokens), last+2+max_gap-gap)):
                            if j in allowed:
                                next_paths.append((j, path+[j], gap+j-last-1))
                    paths = next_paths
                    if not paths:
                        break
                for _, path, gap in paths:
                    fuzzy = any(tokens[i][0] != t for i, t in zip(path, ts))
                    if fuzzy and pattern['origin'] == 'spacing':
                        continue
                    quality = ('clue' if pattern['origin'] == 'context' or pattern.get('context') else
                               'candidate' if fuzzy or pattern['origin'] in ('generated', 'spacing') else
                               'near' if gap else 'alias' if pattern['origin'] == 'alias' else 'literal')
                    offsets = [(tokens[i][1], tokens[i][2]) for i in path]
                    match = dict(entity=entity, alias=pattern['label'], quality=quality, approximate=fuzzy,
                                 gap=gap, origin=pattern['origin'], reason=pattern['reason'], offsets=offsets)
                    key = (entity, offsets[0][0], offsets[-1][1])
                    if key not in best or QUALITY[quality] < QUALITY[best[key]['quality']]:
                        best[key] = match
        # Remove redundant generated substrings of stronger evidence, retaining every occurrence.
        result = []
        by_entity = collections.defaultdict(list)
        for m in best.values():
            by_entity[m['entity']].append(m)
        for matches in by_entity.values():
            for m in matches:
                a, b = m['offsets'][0][0], m['offsets'][-1][1]
                if any(QUALITY[n['quality']] < QUALITY[m['quality']] and
                       n['offsets'][0][0] <= a and b <= n['offsets'][-1][1] for n in matches):
                    continue
                result.append(m)
        matched_entities = {m['entity'] for m in result}
        for entity, given, surnames in self.confluences:
            if entity in matched_entities:
                continue
            first_positions = {i for name in given if len(name) >= 3 for i in positions[name]}
            last_positions = set()
            for surname in surnames:
                if not surname:continue
                for start in positions[surname[0]]:
                    path = list(range(start, start+len(surname)))
                    if all(i in positions[t] for i,t in zip(path,surname)):
                        last_positions.update(path)
            if not first_positions or not last_positions or not (first_positions - last_positions):
                continue
            indices = sorted(first_positions | last_positions)
            result.append(dict(entity=entity, alias=' + '.join(given) + ' / ' + ' | '.join(' '.join(s) for s in surnames),
                               quality='cooccurrence', approximate=any(tokens[i][0] not in given + [t for s in surnames for t in s] for i in indices),
                               gap=None, origin='cooccurrence', reason='Nombre y apellido en la misma página, sin vínculo textual cercano. Puede tratarse de personas diferentes.',
                               offsets=[(tokens[i][1], tokens[i][2]) for i in indices]))
        for m in result:
            m['score'] = SCORES[m['quality']]
        return sorted(result, key=lambda m: (m['offsets'][0][0], m['entity'], QUALITY[m['quality']]))


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def input_paths(root, workbook):
    paths = [root/'progress.json', workbook, root/'priorities'/'catalog-overrides.json']
    docs = read_json(root/'progress.json')['documents']
    for d in docs:
        output = Path(d['output']).resolve()
        if output.is_relative_to((root/'documents').resolve()):
            paths.extend(output/f'page_{p:04}.md' for p in range(1, d['page_count']+1))
    paths.extend((root/'reviews').glob('*/*.json'))
    paths.extend((root/'second_reading').glob('*/case_*/metadata.json'))
    paths.extend((root/'second_reading').glob('*/case_*/transcription.md'))
    return paths


def fingerprint(root, workbook=WORKBOOK):
    values = [ENGINE]
    for path in sorted(set(input_paths(root, workbook))):
        try:
            stat = path.stat()
            values.append([str(path), stat.st_size, stat.st_mtime_ns])
        except OSError:
            values.append([str(path), 'missing'])
    return digest(json.dumps(values))


def run(root, workbook=WORKBOOK, progress=None, catalog_snapshot=None, input_fingerprint=None):
    started = time.time()
    before = input_fingerprint or fingerprint(root, workbook)
    from priority_catalog import catalog_for
    catalog = catalog_snapshot if catalog_snapshot is not None else catalog_for(root, workbook)
    matcher = Matcher(catalog)
    docs = read_json(root/'progress.json')['documents']
    coverage = dict(documents=len(docs), inventory_pages=sum(d['page_count'] for d in docs),
                    searched_pages=0, versions=0, by_version={}, missing_pages=[], errors=[], snapshots=[])
    secondary = collections.defaultdict(list)
    for path in sorted((root/'second_reading').glob('*/case_*/metadata.json')):
        try:
            meta = read_json(path)
            secondary[(meta['document'], meta['page'])].append((path.parent/'transcription.md', 'second_reading:' + path.parent.parent.name))
        except (OSError, ValueError, KeyError) as exc:
            coverage['errors'].append(dict(path=str(path), error=str(exc)))
    pages = []
    for d in docs:
        output = Path(d['output']).resolve()
        ident = digest(d['source'])
        if not output.is_relative_to((root/'documents').resolve()):
            coverage['errors'].append(dict(document=d['source'], error='Ruta fuera del corpus permitido'))
            coverage['missing_pages'].extend(dict(document=d['source'], page=p) for p in range(1, d['page_count']+1))
            continue
        for number in range(1, d['page_count']+1):
            base = dict(document=d['source'], document_id=ident, folder=d['folder'], page=number)
            variants, original = [], ''
            paths = [(output/f'page_{number:04}.md', 'original')] + secondary[(d['source'], number)]
            for path, version in paths:
                try:
                    text = path.read_text(encoding='utf-8')
                    if version == 'original':
                        original = text
                    variants.append((text, version, 'unreviewed', str(path)))
                except (OSError, UnicodeError) as exc:
                    coverage['errors'].append(dict(**base, version=version, error=str(exc)))
            human_path = root/'reviews'/ident/f'{number}.json'
            if human_path.exists():
                try:
                    human = read_json(human_path)
                    status = human.get('status', 'draft') if human.get('original_hash') == digest(original) else 'stale'
                    if not isinstance(human.get('text'), str):
                        raise ValueError('Edición sin texto válido')
                    variants.append((human['text'], 'human', status, str(human_path)))
                except (OSError, ValueError) as exc:
                    coverage['errors'].append(dict(**base, version='human', error=str(exc)))
            versions = []
            searchable = False
            for text, version, status, path in variants:
                coverage['snapshots'].append(dict(**base, version=version, hash=digest(text), path=path, empty=not text.strip()))
                if not text.strip():
                    continue
                searchable = True
                coverage['versions'] += 1
                coverage['by_version'][version] = coverage['by_version'].get(version, 0)+1
                matches = matcher.match(text)
                if matches:
                    versions.append(dict(version=version, status=status, text=text, hash=digest(text), matches=matches))
            if searchable:
                coverage['searched_pages'] += 1
            else:
                coverage['missing_pages'].append(base)
            if versions:
                pages.append(dict(**base, versions=versions))
            if progress:
                progress(coverage['searched_pages'] + len(coverage['missing_pages']), coverage['inventory_pages'])
    hits_by_entity = collections.defaultdict(set)
    page_quality = collections.defaultdict(dict)
    qualities = collections.Counter()
    for p in pages:
        for v in p['versions']:
            for m in v['matches']:
                hits_by_entity[m['entity']].add((p['document_id'], p['page']))
                key = (p['document_id'], p['page'])
                page_quality[m['entity']][key] = min(page_quality[m['entity']].get(key, 99), QUALITY[m['quality']])
                qualities[m['quality']] += 1
    for e in catalog['entities']:
        e['pages'] = len(hits_by_entity.get(e['id'], set()))
        ranks = list(page_quality.get(e['id'], {}).values())
        e['near_pages'] = sum(rank < 4 for rank in ranks)
        e['distant_pages'] = sum(rank == 4 for rank in ranks)
        e['score'] = sum([100, 95, 85, 60, 20, 20][rank] for rank in ranks)
    result = dict(engine=ENGINE, created=time.time(), seconds=time.time()-started, fingerprint=before,
                  changed_during_run=before != fingerprint(root, workbook), catalog=catalog, coverage=coverage,
                  pages=pages, quality_labels=LABELS, score_policy=SCORES, max_intervening_words=MAX_INTERVENING_WORDS, summary=dict(pages=len(pages), documents=len({p['document'] for p in pages}),
                  entities_with_hits=len(hits_by_entity), entities_without_hits=catalog['active_count']-len(hits_by_entity),
                  active_entities=catalog['active_count'], disabled_entities=len(catalog['entities'])-catalog['active_count'], occurrences_by_quality=dict(qualities)))
    directory = root/'priorities'
    directory.mkdir(exist_ok=True)
    temp = directory/'latest.tmp'
    temp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    temp.replace(directory/'latest.json')
    return result


def start(root, requested_revision=None, reason='manual'):
    with _lock:
        if _job.get('running'):
            if requested_revision is not None:
                _job['pending_revision'] = max(requested_revision, _job.get('pending_revision') or 0)
                audit.append(root,'search_queued',revision=requested_revision,reason=reason)
            return dict(_job)
        if requested_revision is None:
            from priority_catalog import settings
            requested_revision=settings(root)['revision']
        _job.clear()
        _job.update(running=True, processed=0, total=0, started=time.time(),pending_revision=requested_revision)
        audit.append(root,'search_requested',revision=requested_revision,reason=reason)

    def progress(processed, total):
        with _lock:
            _job.update(processed=processed, total=total)

    def worker():
        from priority_catalog import settings, catalog_for
        while True:
            with _lock:
                revision=settings(root)['revision']
                snapshot=catalog_for(root)
                input_fingerprint=fingerprint(root)
                run_id=str(uuid.uuid4())
                _job.update(revision=revision,run_id=run_id,processed=0,total=0,pending_revision=None)
                _job.pop('error',None)
            started=time.time()
            try:
                audit.append(root,'search_started',revision=revision,run_id=run_id,engine=ENGINE)
                result=run(root,progress=progress,catalog_snapshot=snapshot,input_fingerprint=input_fingerprint)
                audit.append(root,'search_completed',revision=result['catalog']['revision'],run_id=run_id,seconds=round(time.time()-started,3),summary=result['summary'],coverage={k:result['coverage'][k] for k in ('inventory_pages','searched_pages','versions')},errors=len(result['coverage']['errors']),changed_during_run=result['changed_during_run'],fingerprint=result['fingerprint'])
            except Exception as exc:
                try:audit.append(root,'search_failed',revision=revision,run_id=run_id,error=str(exc))
                except OSError:pass
                with _lock:
                    if settings(root)['revision']>revision:
                        continue
                    _job.update(error=str(exc),running=False)
                return
            with _lock:
                newest=settings(root)['revision']
                if newest>result['catalog']['revision'] or (_job.get('pending_revision') or 0)>result['catalog']['revision']:
                    continue
                _job.update(running=False,pending_revision=None)
                return
    threading.Thread(target=worker, daemon=True).start()
    return dict(_job)


def get(root):
    path = root/'priorities'/'latest.json'
    result = read_json(path) if path.exists() else None
    with _lock:
        job = dict(_job)
    from priority_catalog import settings
    revision=settings(root)['revision']
    if not job.get('running') and not job.get('error') and revision>(result or {}).get('catalog',{}).get('revision',0):
        job=start(root,requested_revision=revision,reason='resume_catalog_update')
    stale = bool(result and (result['engine'] != ENGINE or result['fingerprint'] != fingerprint(root)))
    # A saved human correction is searchable when the analysis is opened again.
    # Reuse the existing worker/queue and audit log; never rerun OCR here.
    if stale and not job.get('running') and not job.get('error'):
        job = start(root, requested_revision=revision, reason='saved_text_or_inventory_changed')
    # Retired sources must stop appearing even while the replacement analysis runs.
    active = {d['source'] for d in read_json(root/'progress.json')['documents']}
    if result and any(p['document'] not in active for p in result.get('pages', [])):
        result = None
        stale = True
    if result:result=dict(result,quality_labels=LABELS,max_intervening_words=MAX_INTERVENING_WORDS)
    return dict(result=result, job=job, stale=stale)
