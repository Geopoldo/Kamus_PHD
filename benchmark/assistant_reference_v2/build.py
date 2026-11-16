#!/usr/bin/env python3
"""Build a frozen visual reference; never loads local models or rewrites v1.

Run with the Python environment that provides Pillow and jsonschema.
`--verify` verifies the frozen bundle without rewriting it.
"""
import argparse
import collections
import datetime
import difflib
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V1 = ROOT.parent / 'assistant_reference' / 'transcriptions.json'
EXPECTED_V1_SHA = '58f0472997a502ef8e24b8e0b7f84897998f5d159f5e6c549ef8ec84ed0eaa93'
PARTS = ['typed.json', 'handwritten.json', 'pdf_pages_1_4.json', 'pdf_pages_5_8.json']
DOC_ORDER = ['typed_letter_1914', 'handwritten_letter_1865', 'british_system_notes']
TITLES = {'typed_letter_1914': 'Carta mecanografiada de 1914',
          'handwritten_letter_1865': 'Carta manuscrita de 1865',
          'british_system_notes': 'Notas manuscritas British System'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def normalize(text):
    """Mechanical word comparison profile; does not modernize vocabulary."""
    text = unicodedata.normalize('NFKC', text).casefold()
    text = re.sub(r'\b[^\W\d_](?:\.[^\W\d_])+(?:\.)?(?!\w)',
                  lambda m: m[0].replace('.', ''), text)
    text = re.sub(r"(?<=\w)['’](?=\w)", '', text)
    return ' '.join(re.findall(r'[^\W_]+', text))


def render_segment(seg):
    text = seg['text']
    if seg['certainty'] == 'illegible':
        text = '⟦ilegible⟧'
    elif seg['certainty'] == 'uncertain':
        text = '⟦duda: ' + text + '⟧'
    if seg['state'] == 'deleted':
        text = '⟦tachado: ' + text + '⟧'
    elif seg['state'] == 'inserted':
        text = '⟦inserción: ' + text + '⟧'
    return text


def display_line(line):
    return ''.join(render_segment(s) for s in line['segments'])


def active_segments(line):
    return [s for s in line['segments'] if s['state'] != 'deleted']


def literal_active(line):
    return ''.join(s['text'] or '' for s in active_segments(line))


def unit_groups(region):
    """Never cut an annotated word continuation into independently scored units."""
    group = []
    for line in region['lines']:
        group.append(line)
        if line['join_next'] == 'none':
            yield group
            group = []
    if group:
        raise ValueError(f"Dangling word continuation in {region['region_id']}")


def joined_literal(lines):
    """Reconstruct complete words; raw literal text is exported separately."""
    out = ''
    for i, line in enumerate(lines):
        text = literal_active(line)
        if i:
            previous = lines[i-1]['join_next']
            if previous == 'hyphenated_continuation':
                if not out.rstrip().endswith(('-', '‐', '‑')):
                    raise ValueError('Annotated hyphenated continuation has no final hyphen')
                out = out.rstrip()[:-1] + text.lstrip()
            elif previous == 'word_continuation':
                out = out.rstrip() + text.lstrip()
            else:
                out += '\n' + text
        else:
            out = text
    return out


def bind_entity(entity, page):
    """Bind a literal mention to exact source characters, retaining text states."""
    line_lookup = {l['line_id']:(r,l) for r in page['regions'] for l in r['lines']}
    seg_lookup, chars, origin = {}, [], []
    for li, lid in enumerate(entity['line_ids']):
        region, line = line_lookup[lid]
        if li:
            chars.append('\n'); origin.append(None)
        for seg in line['segments']:
            sid = seg['segment_id']; seg_lookup[sid] = (region, seg)
            for offset, char in enumerate(seg['text'] if seg['text'] is not None else '\ufffd'):
                chars.append(char); origin.append((sid, offset))
    # Only whitespace is collapsed for matching. No case, punctuation or lexical repair.
    collapsed, positions = [], []
    for char, pos in zip(chars, origin):
        if char.isspace():
            if collapsed and collapsed[-1] == ' ':
                continue
            char = ' '
        collapsed.append(char); positions.append(pos)
    haystack = ''.join(collapsed)
    needle = ' '.join(entity['text'].split())
    matches, start = [], 0
    while True:
        at = haystack.find(needle, start)
        if at < 0: break
        grouped = collections.defaultdict(list)
        for pos in positions[at:at+len(needle)]:
            if pos is not None: grouped[pos[0]].append(pos[1])
        support = [seg_lookup[sid] for sid in grouped]
        states = sorted({s['state'] for _,s in support})
        clear = all(s['certainty']=='clear' for _,s in support)
        matches.append({'source_char_spans':[{'segment_id':sid,'start':min(offsets),
                        'end_exclusive':max(offsets)+1} for sid,offsets in grouped.items()],
                        'region_ids':list(dict.fromkeys(r['region_id'] for r,_ in support)),
                        'region_kinds':sorted({r['kind'] for r,_ in support}),
                        'states':states, 'all_supporting_segments_clear':clear,
                        'active_layer_eligible':clear and 'deleted' not in states,
                        'deleted_layer_eligible':clear and states==['deleted']})
        start = at + max(1,len(needle))
    assert matches, 'Entity is not literal in its linked lines: ' + entity['entity_id']
    return dict(entity, source_occurrences=matches, source_match_verified=True,
                strict_eligible=entity['certainty']=='clear' and len(matches)==1 and matches[0]['active_layer_eligible'],
                deleted_layer_eligible=entity['certainty']=='clear' and len(matches)==1 and matches[0]['deleted_layer_eligible'])


def schema():
    return {
      '$schema': 'https://json-schema.org/draft/2020-12/schema',
      'title': 'Visual transcription reference v2',
      'type': 'object', 'required': ['schema_version', 'documents'],
      'properties': {
        'schema_version': {'const': '2.0'},
        'documents': {'type': 'array', 'minItems': 3, 'maxItems': 3,
          'items': {'type': 'object', 'required': ['document_id', 'pages'],
            'properties': {'document_id': {'enum': DOC_ORDER},
              'pages': {'type': 'array', 'minItems': 1, 'items': {'$ref': '#/$defs/page'}}}}}},
      '$defs': {
        'segment': {'type': 'object', 'required': ['text', 'certainty', 'state'],
          'properties': {'text': {'type': ['string', 'null']},
            'certainty': {'enum': ['clear', 'uncertain', 'illegible']},
            'state': {'enum': ['active', 'deleted', 'inserted']},
            'alternatives': {'type': 'array', 'items': {'type': 'string'}},
            'note_es': {'type': 'string'}},
          'allOf': [
            {'if': {'properties': {'certainty': {'const': 'illegible'}}},
             'then': {'properties': {'text': {'type': 'null'}}, 'required': ['note_es']},
             'else': {'properties': {'text': {'type': 'string', 'minLength': 1}}}},
            {'if': {'properties': {'certainty': {'const': 'uncertain'}}},
             'then': {'required': ['note_es']}}]},
        'line': {'type': 'object', 'required': ['line_id', 'segments', 'join_next'],
          'properties': {'line_id': {'type': 'string'},
            'segments': {'type': 'array', 'minItems': 1, 'items': {'$ref': '#/$defs/segment'}},
            'join_next': {'enum': ['none', 'word_continuation', 'hyphenated_continuation']}}},
        'region': {'type': 'object', 'required': ['region_id', 'kind', 'bbox', 'reading_order', 'lines'],
          'properties': {'region_id': {'type': 'string'},
            'kind': {'enum': ['header', 'body', 'margin', 'footer', 'folio', 'deletion', 'other']},
            'bbox': {'type': 'array', 'minItems': 4, 'maxItems': 4,
                     'items': {'type': 'number', 'minimum': 0, 'maximum': 1}},
            'reading_order': {'type': 'integer', 'minimum': 1},
            'anchor_line_id': {'type': ['string', 'null']},
            'lines': {'type': 'array', 'minItems': 1, 'items': {'$ref': '#/$defs/line'}}}},
        'entity': {'type': 'object', 'required': ['entity_id', 'type', 'text', 'line_ids', 'certainty'],
          'properties': {'entity_id': {'type': 'string'},
            'type': {'enum': ['person', 'place', 'date', 'organization', 'identifier', 'other']},
            'text': {'type': 'string', 'minLength': 1},
            'line_ids': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': {'type': 'string'}},
            'certainty': {'enum': ['clear', 'uncertain', 'illegible']}}},
        'page': {'type': 'object', 'required': ['page_id', 'page_number', 'image_path', 'image_size', 'regions', 'entities', 'review_log', 'notes_es'],
          'properties': {'page_id': {'type': 'string'}, 'page_number': {'type': 'integer', 'minimum': 1},
            'image_path': {'type': 'string'},
            'image_size': {'type': 'array', 'minItems': 2, 'maxItems': 2,
                           'items': {'type': 'integer', 'minimum': 1}},
            'regions': {'type': 'array', 'minItems': 1, 'items': {'$ref': '#/$defs/region'}},
            'entities': {'type': 'array', 'items': {'$ref': '#/$defs/entity'}},
            'review_log': {'type': 'array', 'minItems': 2},
            'notes_es': {'type': 'array', 'items': {'type': 'string'}}}}
      }}


def verify():
    manifest = json.loads((ROOT/'manifest.json').read_text())
    failures = []
    for group in ('bundle_files', 'source_files'):
        for item in manifest[group]:
            p = Path(item['path'])
            if not p.is_absolute():
                p = ROOT/p
            if not p.exists() or sha(p) != item['sha256']:
                failures.append(str(p))
    if sha(V1) != EXPECTED_V1_SHA:
        failures.append(str(V1))
    if failures:
        raise SystemExit('Verification failed: ' + ', '.join(failures))
    print(json.dumps({'verified': True, 'bundle_files': len(manifest['bundle_files']),
                      'source_files': len(manifest['source_files']), 'v1_unchanged': True}))


def build():
    from PIL import Image
    import jsonschema
    if (ROOT/'manifest.json').exists():
        raise SystemExit('Reference already frozen. Use --verify; create a new version for edits.')
    assert sha(V1) == EXPECTED_V1_SHA, 'v1 changed since task started'
    # Snapshot exactly the bytes parsed, before opening v1 for the change log.
    input_paths = [ROOT/'build.py', ROOT/'PROTOCOL.md'] + [ROOT/'parts'/name for name in PARTS]
    input_bytes = {p:p.read_bytes() for p in input_paths}
    input_hashes = {str(p.relative_to(ROOT)):hashlib.sha256(data).hexdigest() for p,data in input_bytes.items()}
    reading_frozen_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    page_groups = collections.defaultdict(list)
    for name in PARTS:
        part = json.loads(input_bytes[ROOT/'parts'/name])
        page_groups[part['document_id']].extend(part['pages'])
    v1_bytes = V1.read_bytes()
    assert hashlib.sha256(v1_bytes).hexdigest() == EXPECTED_V1_SHA
    v1 = json.loads(v1_bytes)
    old_docs = {d['document_id']: d for d in v1['documents']}
    docs = []
    source_files = []
    for doc_id in DOC_ORDER:
        sources = old_docs[doc_id]['sources']
        for src in sources:
            assert sha(src['absolute_path']) == src['sha256'], 'Source image/PDF changed'
            source_files.append({'path': src['absolute_path'], 'sha256': src['sha256']})
        docs.append({'document_id': doc_id, 'title_es': TITLES[doc_id], 'language': 'en',
                     'sources': sources, 'pages': sorted(page_groups[doc_id], key=lambda p:p['page_number'])})
    assert [len(d['pages']) for d in docs] == [1,1,8]
    bundle = {'schema_version': '2.0', 'version': 'astra-reference-v2',
      'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'reading_frozen_before_v1_comparison_at_utc': reading_frozen_at,
      'reading_input_hashes': input_hashes,
      'status': 'frozen_working_reference', 'reference_model_requested_by_user': 'Astra Ultra',
      'method_es': [
        'Relectura visual y recortes ampliados; no se ejecutó OCR ni inferencia en la GPU local.',
        'Lecturas de membrete y PDF delegadas a gpt-6-astra con esfuerzo ultra y sin historial heredado.',
        'Carta manuscrita leída en la conversación principal; revisiones adicionales constan en review_log.',
        'No se usaron salidas locales ni la lista de prioridades para resolver palabras.',
        'El coordinador conservaba contexto de la conversación previa. No se afirma independencia ciega total.',
        'Referencia de trabajo elegida por el usuario; no equivale a validación humana.'],
      'parent_reference': {'path': str(V1), 'sha256': EXPECTED_V1_SHA, 'modified': False},
      'coordinate_system': {'origin':'top_left', 'units':'normalized_0_1', 'precision':'approximate_region_boxes',
                            'image_basis':'oriented_image_path'},
      'documents': docs}
    spec = schema()
    jsonschema.Draft202012Validator(spec).validate(bundle)
    all_ids = set()
    def unique(value):
        assert value not in all_ids, 'Duplicate ID: ' + value
        all_ids.add(value)
    counts = collections.Counter()
    units, uncertainties, entities, page_stats = [], [], [], []
    md = ['# Referencia visual v2', '',
          'Referencia de trabajo fija. Los marcadores ⟦duda⟧, ⟦ilegible⟧, ⟦tachado⟧ e ⟦inserción⟧ son editoriales; no son palabras de la fuente.',
          'El JSON conserva texto, estados y alternativas por separado. `clear` significa aceptado en esta lectura visual, no validado por una persona.', '']
    diff_md = ['# Cambios de v1 a v2', '',
      'Comparación de las representaciones legibles de cada página. Incluye cambios de segmentación, folios y notación; no toda diferencia es una corrección de lectura.',
      'La lectura v2 se terminó antes de generar este cotejo. v1 se conserva sin cambios.', '']
    diffs = []
    for doc in docs:
        md += ['## ' + doc['title_es'], '']
        for page in doc['pages']:
            pid = page['page_id']; unique(pid)
            assert pid == f"{doc['document_id']}.p{page['page_number']:02d}"
            im_path = Path(page['image_path']); im = Image.open(im_path)
            assert list(im.size) == page['image_size'], f'Wrong dimensions {pid}'
            page['image_sha256'] = sha(im_path)
            source_files.append({'path': str(im_path), 'sha256': page['image_sha256']})
            md += [f"### {pid}", '', f"[Imagen fuente]({im_path})", '']
            page_lines = {line['line_id'] for r in page['regions'] for line in r['lines']}
            order = [r['reading_order'] for r in page['regions']]
            assert len(order) == len(set(order)), f'Duplicate reading order {pid}'
            pc = collections.Counter()
            display = []
            for region in sorted(page['regions'], key=lambda r:r['reading_order']):
                rid = region['region_id']; unique(rid)
                assert rid.startswith(pid + '.')
                x1,y1,x2,y2 = region['bbox']; assert x1 < x2 and y1 < y2
                if region.get('anchor_line_id'):
                    assert region['anchor_line_id'] in page_lines
                pc['regions'] += 1
                md += [f"#### {rid} · {region['kind']}", '', f"Caja aproximada: `{region['bbox']}`.", '']
                display += [f"[{region['kind']}: {rid}]"]
                has_doubt = any(s['certainty'] != 'clear' for l in region['lines'] for s in l['segments'])
                crop_path = None
                if has_doubt:
                    crop_path = ROOT/'review_crops'/(rid+'.png'); crop_path.parent.mkdir(exist_ok=True)
                    w,h = im.size
                    crop = im.crop((int(x1*w),int(y1*h),min(w,int(x2*w)+1),min(h,int(y2*h)+1)))
                    scale = min(2, 1800/crop.width)
                    crop.resize((round(crop.width*scale),round(crop.height*scale)), Image.Resampling.LANCZOS).save(crop_path)
                for line in region['lines']:
                    unique(line['line_id']); assert line['line_id'].startswith(rid+'.')
                    pc['physical_lines'] += 1
                    if active_segments(line): pc['active_lines'] += 1
                    rendered = display_line(line); display.append(rendered)
                    md += [f"`{line['line_id']}` {rendered}  "]
                    for si, seg in enumerate(line['segments'], 1):
                        seg['segment_id'] = f"{line['line_id']}.s{si:02d}"
                        unique(seg['segment_id'])
                        pc[seg['state']+'_segments'] += 1
                        if seg['certainty'] != 'clear':
                            pc[seg['certainty']+'_segments'] += 1
                            uncertainties.append({'document_id': doc['document_id'], 'page_id': pid,
                              'region_id':rid, 'line_id':line['line_id'], 'segment_id':seg['segment_id'],
                              'kind':region['kind'], 'text':seg['text'], 'certainty':seg['certainty'],
                              'state':seg['state'], 'alternatives':seg.get('alternatives', []),
                              'note_es':seg['note_es'], 'line_context':rendered,
                              'image_path':str(im_path), 'bbox':region['bbox'], 'review_crop':str(crop_path)})
                md += ['']
                for lines in unit_groups(region):
                    segs = [s for line in lines for s in active_segments(line)]
                    eligible = bool(segs) and all(s['certainty']=='clear' for s in segs)
                    literal = '\n'.join(literal_active(l) for l in lines) if eligible else None
                    reconstructed = joined_literal(lines) if eligible else None
                    normalized = normalize(reconstructed) if eligible else None
                    unit = {'unit_id': lines[0]['line_id'] + '.u', 'document_id':doc['document_id'],
                      'page_id':pid, 'region_id':rid, 'kind':region['kind'],
                      'line_ids':[l['line_id'] for l in lines], 'strict_eligible':eligible,
                      'excluded_reason':None if eligible else ('no_active_text' if not segs else 'uncertain_active_text'),
                      'literal_active_text':literal, 'reconstructed_word_text':reconstructed,
                      'normalized_word_text':normalized,
                      'reference_token_count':len(normalized.split()) if eligible else None,
                      'deleted_segment_ids':[s['segment_id'] for l in lines for s in l['segments'] if s['state']=='deleted']}
                    units.append(unit)
                    if eligible:
                        pc['strict_units'] += 1; pc['strict_active_lines'] += len(lines)
                        pc['strict_reference_tokens'] += unit['reference_token_count']
                    elif segs: pc['excluded_active_units'] += 1
            for ent in page['entities']:
                unique(ent['entity_id'])
                assert set(ent['line_ids']) <= page_lines
                entities.append(dict(bind_entity(ent,page), document_id=doc['document_id'], page_id=pid))
            pc['entities'] += len(page['entities'])
            pc['clear_entities'] += sum(e['certainty']=='clear' for e in page['entities'])
            pc['pages'] += 1; counts.update(pc)
            page_stats.append(dict(page_id=pid,document_id=doc['document_id'],**pc))
            md += ['Notas:', ''] + ['- '+n for n in page['notes_es']] + ['']
            old_page = next(p for p in old_docs[doc['document_id']]['pages'] if p['page_number']==page['page_number'])
            oldtext = old_page['transcription']
            newtext = '\n'.join(display)
            diff = '\n'.join(difflib.unified_diff(oldtext.splitlines(),newtext.splitlines(),
                                  fromfile='v1/'+pid,tofile='v2/'+pid,lineterm=''))
            diffs.append({'page_id':pid,'unified_diff':diff})
            diff_md += ['## '+pid, '', '```diff', diff, '```', '']
    # Revalidate final serialized form and require all ten unique pages.
    jsonschema.Draft202012Validator(spec).validate(bundle)
    assert counts['pages']==10
    assert normalize("Staff J.A. 4645 don't") == 'staff ja 4645 dont'
    assert normalize('C.J') == normalize('C.J.') == 'cj'
    assert normalize('U.M.C.J.') != normalize('U.C.M.J.')
    assert sha(V1) == EXPECTED_V1_SHA
    counts['unique_documents'] = 3
    counts['original_source_files'] = 6
    bundle['counts'] = dict(counts)
    dump(ROOT/'reference.schema.json', spec)
    dump(ROOT/'transcriptions.json', bundle)
    (ROOT/'transcriptions.md').write_text('\n'.join(md)+'\n')
    profile = {'id':'literal_words_v2', 'steps_es':[
      'Seleccionar la misma página, región y capa textual en referencia y salida del modelo.',
      'Unir sólo continuaciones de palabra anotadas explícitamente; no unir unidades separadas por dudas.',
      'Unicode NFKC y casefold; retirar puntos de siglas de letras individuales, tengan o no punto final (C.J y C.J. coinciden).',
      'Retirar apóstrofos interiores; usar letras y dígitos Unicode como tokens; puntuación restante separa tokens.',
      'Conservar números, ortografía y orden de letras; no expandir siglas ni sustituir variantes léxicas.'],
      'literal_CER_es':'Usar literal_active_text, que conserva saltos y guiones físicos; declarar cómo se tratan los espacios. reconstructed_word_text une las continuaciones anotadas y sirve para la métrica de palabras, no para CER literal.',
      'warning_es':'Las unidades no son predicciones alineadas. No concatenarlas omitiendo dudas y comparar con la página completa: asignar primero las regiones y los tramos correspondientes, manteniendo inserciones.'}
    dump(ROOT/'evaluation_units.json', {'reference_version':bundle['version'], 'normalization':profile,
       'counts':dict(counts),'pages':page_stats,'units':units,'entities':entities})
    dump(ROOT/'uncertainties.json', {'reference_version':bundle['version'],'items':uncertainties})
    umd = ['# Pasajes para revisión', '',
      'Estas lecturas se conservan en la transcripción, pero no se aceptan como texto cierto para la puntuación estricta. Los recortes muestran la región completa; la línea y el segmento identifican la duda.', '']
    for u in uncertainties:
        umd += [f"## {u['segment_id']}", '', f"Estado: **{u['certainty']} / {u['state']}**. Región: {u['kind']}.", '',
                u['line_context'], '', 'Alternativas: '+(', '.join(u['alternatives']) or 'ninguna propuesta')+'.', '',
                u['note_es'], '', f"[Ver recorte]({u['review_crop']}) · [Imagen completa]({u['image_path']})", '']
    (ROOT/'uncertainties.md').write_text('\n'.join(umd)+'\n')
    dump(ROOT/'changes.json', {'v1_sha256':EXPECTED_V1_SHA,'pages':diffs})
    (ROOT/'CHANGELOG.md').write_text('\n'.join(diff_md)+'\n')
    dump(ROOT/'validation.json', {'valid':True,'schema':'reference.schema.json','v1_unchanged':True,
       'checks':['JSON Schema', 'unique IDs', 'page coverage', 'region boxes', 'entity/anchor line links',
                 'source hashes', 'image dimensions', 'word-continuation integrity', 'normalization invariants',
                 'literal entity character spans and source states', 'pre-comparison input snapshot'],
       'counts':dict(counts),'pages':page_stats,
       'limitations_es':['La validación estructural no prueba exactitud paleográfica.',
                         'Las entidades son menciones seleccionadas para evaluación, no un inventario exhaustivo de todas las entidades posibles.',
                         'Las cajas son aproximadas; no usar como verdad de segmentación a nivel píxel.']})
    readme = ['# Referencia Astra v2', '',
      f"10 páginas únicas; {counts['regions']} regiones; {counts['physical_lines']} renglones físicos.", '',
      f"{counts['strict_units']} unidades estrictas ({counts['strict_reference_tokens']} tokens normalizados) y {len(uncertainties)} segmentos inciertos o ilegibles registrados por separado.", '',
      'Estas cifras describen cobertura de la referencia, no exactitud de los modelos locales.', '',
      '- [Lectura por páginas y líneas](transcriptions.md)',
      '- [Datos estructurados](transcriptions.json)',
      '- [Dudas y recortes](uncertainties.md)',
      '- [Unidades y perfil de evaluación](evaluation_units.json)',
      '- [Protocolo](PROTOCOL.md)',
      '- [Diferencias con v1](CHANGELOG.md)',
      '- [Validación](validation.json)', '',
      'La referencia v1 y las salidas de los modelos locales permanecen intactas. Los informes anteriores siguen usando v1.', '',
      'Para comparar: alinear página, región y capa; puntuar sólo tramos aceptados, reportar cobertura, evaluar folios y tachados por separado y desglosar por página y clase documental. No convertir estas unidades discontinuas en un único texto global para WER.', '',
      'No se han recalculado puntuaciones ni ejecutado modelos locales en esta fase.', '',
      '## Integridad', '',
      '`manifest.json` fija las huellas de entradas y archivos entregados. Ejecutar `python build.py --verify` para comprobarlas. El constructor rehúsa sobrescribir una referencia ya congelada.', '',
      'Las lecturas dudosas siguen abiertas para revisión humana. Una corrección futura debe producir otra versión con su propio registro de cambios.']
    (ROOT/'README.md').write_text('\n'.join(readme)+'\n')
    for path, data in input_bytes.items():
        assert path.read_bytes() == data, 'Input changed during build: ' + str(path)
    assert sha(V1) == EXPECTED_V1_SHA
    files = [p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='manifest.json']
    manifest = {'version':bundle['version'],'frozen_at_utc':bundle['created_at_utc'],
       'reference_sha256':sha(ROOT/'transcriptions.json'),'parent_sha256':EXPECTED_V1_SHA,
       'bundle_files':[{'path':str(p.relative_to(ROOT)), 'sha256':sha(p)} for p in sorted(files)],
       'source_files':list({x['path']:x for x in source_files}.values()),
       'policy_es':'No editar esta versión congelada. Crear nueva versión para cambios documentales.'}
    dump(ROOT/'manifest.json', manifest)
    print(json.dumps(dict(counts),ensure_ascii=False))
    verify()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--verify', action='store_true')
    args=parser.parse_args()
    verify() if args.verify else build()
