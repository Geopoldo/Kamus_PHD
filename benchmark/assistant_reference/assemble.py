"""Package manually authored visual transcriptions; performs no OCR or inference."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/home/ewok/claude_code_env/uploads')

def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

def source_record(name):
    p = SOURCE / name
    return {'filename': name, 'absolute_path': str(p),
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'bytes': p.stat().st_size}

def prepare(doc, names, title, scope):
    doc['title_es'] = title
    doc['reference_status'] = 'provisional_ai_visual_transcription'
    doc['sources'] = [source_record(n) for n in names]
    assert len({s['sha256'] for s in doc['sources']}) == 1
    doc['benchmark_scope_es'] = scope
    doc.pop('source_filename', None)
    for page in doc['pages']:
        if 'blocks' not in page:
            page['blocks'] = [{'id': f"P{page['page_number']:02d}",
                               'role': 'page_text_with_editorial_annotations',
                               'transcription': page.pop('transcription')}]
        if isinstance(page.get('notes_es'), str):
            page['notes_es'] = [page['notes_es']]
        page['transcription'] = '\n\n'.join(b['transcription'] for b in page['blocks'])
        for block in page['blocks']:
            block['lines'] = [{'id': f"{block['id']}-L{i:02d}", 'text': t}
                              for i, t in enumerate(block['transcription'].splitlines(), 1)]
        page['uncertain_readings'] = page.get('uncertain_readings', [])
    return doc

typed = prepare(read('typed.json'), [
    'f67aa551-e1b3-477f-ab3c-322c97ca816b.png',
    'aa9033b9-a0a2-4132-ad97-ee61dd87cee3.png',
    'aac77aa3-0bf7-42f9-b5c9-0b750aec17ee.png'],
    'Carta mecanografiada a Theodore Roosevelt, 14 de julio de 1914',
    'Es la imagen mecanografiada usada en las pruebas locales. Las otras dos imágenes son duplicados exactos.')
typed['comparison_body_block_ids'] = ['T06', 'T07', 'T08', 'T09', 'T10']
body = '\n\n'.join(b['transcription'] for b in typed['pages'][0]['blocks']
                    if b['id'] in typed['comparison_body_block_ids'])
typed['comparison_body_text'] = re.sub(r'(?<=\w)-\n(?=\w)', '', body)

handwritten = prepare(read('handwritten.json'),
    ['75f90bd0-f4a2-459a-bd26-591e3e6122fd.png'],
    'Carta manuscrita a Garfield, 12 de octubre de 1865 — fecha leída en la imagen',
    'Es la imagen manuscrita usada en las pruebas locales. Contiene lecturas pendientes de revisión.')

pdf_pages = read('pdf_pages_1_4.json') + read('pdf_pages_5_8.json')
assert [p['page_number'] for p in pdf_pages] == list(range(1, 9))
pdf = prepare({'document_id': 'british_system_notes', 'language': 'en',
               'document_type': 'handwritten_notes', 'pages': pdf_pages},
    ['c49684ff-93c8-4336-9166-0cab94718485.pdf',
     'eef6f60f-771b-47e9-bea1-87a11e412e32.pdf'],
    'Apuntes manuscritos «British System» — ocho páginas',
    'Documento adicional encontrado en uploads. No fue procesado en las pruebas locales anteriores. Ambos PDF son idénticos.')

package = {
    'schema_version': '1.0', 'created_on': '2026-11-14',
    'timezone': 'America/Bogota', 'reference_status': 'provisional_ai_visual_transcription',
    'method_es': [
        'Transcripción por capacidad visual del asistente; no se ejecutó OCR ni se cargaron modelos en la GPU del equipo para esta tarea.',
        'Se revisaron las imágenes originales y recortes ampliados. Las páginas PDF se renderizaron para lectura visual.',
        'Se usó una lectura visual adicional del manuscrito y se distribuyó la lectura del PDF entre agentes de la misma conversación.',
        'Las palabras inciertas y las intervenciones editoriales se marcan entre corchetes. No son texto confirmado de la fuente.',
        'Se conserva el inglés, las abreviaturas y los saltos de renglón cuando se distinguen. La tipografía y el espaciado no se reproducen exactamente.',
        'Es una referencia provisional generada por IA, pendiente de validación humana. La conversación ya contenía resultados de los modelos; esta relectura visual no constituye una evaluación ciega independiente.'
    ],
    'conventions': {
        '[unclear: candidate]': 'Lectura tentativa; puede ser incorrecta.',
        '[illegible]': 'Texto que no se puede leer de forma fiable.',
        '[crossed-out: ...] / [Crossed out: ...]': 'Tachadura visible; el texto dentro puede ser tentativo o ilegible.',
        '[inserted: ...] / [insertion: ...]': 'Texto añadido entre renglones o fuera de su posición normal.',
        'Other bracketed notes': 'Intervenciones editoriales para ubicar márgenes, correcciones o anotaciones; no son palabras del documento.'
    },
    'comparison_guidance_es': [
        'Comparar cada salida con el mismo archivo y página; los duplicados no cuentan como muestras adicionales.',
        'Para la prueba mecanografiada anterior, usar comparison_body_text y excluir membrete, destinatario y pie de página.',
        'No calcular exactitud definitiva del manuscrito hasta resolver las lecturas inciertas y validar la referencia.',
        'No tratar las marcas editoriales como palabras de la fuente ni eliminarlas y puntuar como si el pasaje estuviera confirmado.',
        'Separar evaluación de palabras, fechas y nombres de la evaluación de formato, puntuación y orden de lectura.'
    ],
    'counts': {'source_files': 6, 'unique_documents': 3, 'unique_pages': 10,
               'previous_benchmark_pages': 2},
    'documents': [typed, handwritten, pdf]
}

ROLE_LABELS = {
    'letterhead_center': 'Membrete central', 'letterhead_left_top': 'Membrete izquierdo superior',
    'letterhead_left_bottom': 'Distrito de Nueva York', 'letterhead_right': 'Junta directiva',
    'date_and_addressee': 'Fecha y destinatario', 'salutation': 'Saludo',
    'body_paragraph': 'Cuerpo', 'printed_footer': 'Pie impreso', 'page_markings': 'Marcas de página',
    'date': 'Fecha', 'printed_folio': 'Folio impreso',
    'page_text_with_editorial_annotations': 'Transcripción'
}

md = ['# Transcripciones visuales de referencia', '',
      '14 de noviembre de 2026. **Referencia provisional generada por IA; requiere revisión humana.**', '',
      'Incluye 10 páginas únicas: las dos imágenes del ensayo y las ocho páginas del PDF adicional. '
      'Los seis archivos de entrada corresponden a tres documentos; se identificaron los duplicados por SHA-256.', '',
      '## Método y uso', '']
md += ['- ' + line for line in package['method_es']]
md += ['', '`[unclear: ...]` indica una lectura tentativa; `[illegible]`, texto no legible. '
       'Las otras anotaciones entre corchetes identifican tachaduras, inserciones o zonas de página. '
       'Son intervenciones editoriales, no texto confirmado del original.', '',
       'Para la comparación del cuerpo mecanografiado, el JSON contiene `comparison_body_text`. '
       'Las transcripciones manuscritas no deben usarse todavía como verdad de referencia para asignar porcentajes de exactitud.', '']
for doc in package['documents']:
    md += [f"## {doc['title_es']}", '', f"Identificador: `{doc['document_id']}`.", '', doc['benchmark_scope_es'], '', 'Archivos de origen:', '']
    md += [f"- [{s['filename']}]({s['absolute_path']})" for s in doc['sources']]
    for page in doc['pages']:
        md += ['', f"### Página {page['page_number']}", '']
        for block in page['blocks']:
            md += [f"**{block['id']} · {ROLE_LABELS.get(block['role'],block['role'])}**", '', '```text', block['transcription'], '```', '']
        if page['uncertain_readings']:
            md += ['Lecturas pendientes:', '']
            for uncertain in page['uncertain_readings']:
                alternatives = (' Alternativas: '+', '.join(uncertain['alternatives'])+'.') if uncertain.get('alternatives') else ''
                md += [f"- **{uncertain['text']}**: {uncertain['reason_es']}{alternatives}"]
            md += ['']
        if page.get('notes_es'):
            md += ['Notas de lectura:', ''] + ['- '+line for line in page['notes_es']] + ['']

json_path = ROOT / 'transcriptions.json'
md_path = ROOT / 'transcriptions.md'
json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
md_path.write_text('\n'.join(md)+'\n', encoding='utf-8')
check = json.loads(json_path.read_text())
assert sum(len(d['pages']) for d in check['documents']) == 10
assert sum(len(d['sources']) for d in check['documents']) == 6
assert all(p['transcription'].strip() for d in check['documents'] for p in d['pages'])
ids = [b['id'] for d in check['documents'] for p in d['pages'] for b in p['blocks']]
assert len(ids) == len(set(ids))
print(json.dumps({'files': [str(json_path), str(md_path)], 'counts': check['counts'],
                  'typed_comparison_words': len(re.findall(r'[a-z0-9]+', typed['comparison_body_text'].lower()))}, indent=2))
