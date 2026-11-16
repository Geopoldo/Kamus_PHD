"""Evidence-based review of existing transcripts. Does not run inference."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'extended_results'
REFERENCE = ROOT / 'assistant_reference/transcriptions.json'
ref = json.loads(REFERENCE.read_text())
prior = json.loads((OUT / 'comparison.json').read_text())
ORDER = ['qwen3.5-9b', 'qwen3-vl-8b', 'qwen3.6-27b', 'qwen3.8-27b', 'deepseek-ocr-2']
labels = {'qwen3.5-9b': 'Qwen3.5-9B', 'qwen3-vl-8b': 'Qwen3-VL-8B',
          'qwen3.6-27b': 'Qwen3.6-27B', 'qwen3.8-27b': 'Qwen3.8-27B', 'deepseek-ocr-2': 'DeepSeek-OCR-2'}
models = {m: json.loads((OUT/m/'transcriptions.json').read_text()) for m in ORDER}
texts = {m: {p['page_id']: p['transcription'] for p in d['pages']} for m,d in models.items()}
def flat(s):
    return ' '.join(s.casefold().split())
def found(s, term):
    return bool(re.search(r'\b'+re.escape(term)+r'\b', s, re.I))

names = ['Bagnell','Dietrich','Horton','Burrell','Burt','Wallace','Egbert','Baldwin','Tichenor','Chalmers','Greenfield','Spicer']
board = next(b['transcription'] for b in ref['documents'][0]['pages'][0]['blocks'] if b['id']=='T04')
assert all(found(board,n) for n in names)
summary = []
for m in ORDER:
    result = next(r for r in prior['models'] if r['model']==m)
    exact = {n:found(texts[m]['typed'],n) for n in names}
    summary.append({'model':m,'label':labels[m],
        'total_inference_seconds':result['total_inference_seconds'],
        'slowdown_vs_qwen35_9b':result['total_inference_seconds']/next(x['total_inference_seconds'] for x in prior['models'] if x['model']=='qwen3.5-9b'),
        'handwriting_subset':{'page_ids':['pdf_page_05','pdf_page_07'],
            'reference_words':result['clear_handwriting_reference_words'],
            'word_edits':result['clear_handwriting_word_edits'],
            'provisional_wer':result['clear_handwriting_weighted_wer']},
        'typed_board_surnames':{'reference_block_id':'T04','exact_matches':sum(exact.values()),
            'total_targets':len(names),'per_surname':exact,
            'method_es':'Presencia literal del apellido con límite de palabra, sin distinguir mayúsculas. No evalúa iniciales, nombres completos, orden ni falsos positivos. Una sola zona de una sola imagen; no es una prueba de apellidos Cree.'}})

cases = [
    {'id':'handwritten_addressee','page_id':'handwritten','reference':'Garfield',
     'importance_es':'Apellido del destinatario, relevante para búsquedas por nombre.',
     'outputs':{'qwen3-vl-8b':'My Dear Harfield','qwen3.5-9b':'My Dear Fairfield',
                'qwen3.6-27b':'My Dear Harfield','qwen3.8-27b':'My Dear Garfield',
                'deepseek-ocr-2':'I am Captain Coates.'}},
    {'id':'handwritten_date','page_id':'handwritten','reference':'1865',
     'importance_es':'Año de la carta. El WER anterior excluye cifras y no mide este dato.',
     'outputs':{'qwen3-vl-8b':'1828','qwen3.5-9b':'1865','qwen3.6-27b':'1848','qwen3.8-27b':'1865','deepseek-ocr-2':None}},
    {'id':'handwritten_levees','page_id':'handwritten','reference':'efficient levees',
     'importance_es':'Ninguno conserva literalmente esta expresión; cambiarla por un sinónimo pierde el término que se buscaría.',
     'outputs':{'qwen3-vl-8b':'official lines','qwen3.5-9b':'efficient means',
                'qwen3.6-27b':'artificial levees','qwen3.8-27b':'artificial dikes','deepseek-ocr-2':None}},
    {'id':'handwritten_revenue','page_id':'handwritten','reference':'matters of revenue',
     'importance_es':'La palabra fuente está dividida entre renglones como reve/nue; ninguno la recupera.',
     'outputs':{'qwen3-vl-8b':'matters of once','qwen3.5-9b':'matters of some once',
                'qwen3.6-27b':'matters of some force','qwen3.8-27b':'matters of new Coin','deepseek-ocr-2':None}},
    {'id':'pdf1_counsel_omission','page_id':'pdf_page_01','reference':'and arguments of parties or Counsel',
     'importance_es':'Todos los Qwen pierden or Counsel; 3.6 lo sustituye por in Court.',
     'outputs':{'qwen3-vl-8b':'and arguments of parties','qwen3.5-9b':'and arguments of parties sums',
                'qwen3.6-27b':'and arguments of parties in Court','qwen3.8-27b':'and arguments of parties sums','deepseek-ocr-2':None}},
    {'id':'pdf3_command','page_id':'pdf_page_03','reference':'Judge Martial of the Command',
     'importance_es':'Los 27B conservan la preposición de este pasaje. Los pequeños la cambian por &.',
     'outputs':{'qwen3-vl-8b':'Judge Martial & The Command','qwen3.5-9b':'Judge Martial & the Command',
                'qwen3.6-27b':'Judge Martial of the Command','qwen3.8-27b':'Judge Martial of the Command','deepseek-ocr-2':None}},
    {'id':'pdf5_counsel','page_id':'pdf_page_05','reference':'Trained App. Counsel provided',
     'importance_es':'Qwen3.5 cambia Counsel por Court: error de contenido en una página por lo demás legible.',
     'outputs':{'qwen3-vl-8b':'Trained App. Counsel provided','qwen3.5-9b':'Trained App. Court provided',
                'qwen3.6-27b':'Trained App. Counsel provided','qwen3.8-27b':'Trained App. Counsel provided','deepseek-ocr-2':'Trained App. Counsel/Proff'}},
    {'id':'pdf6_approval_initials','page_id':'pdf_page_06','reference':'approval by J.A.G.',
     'importance_es':'Qwen3.8 cambia la primera inicial a G. Una salida más grande no garantiza conservar siglas.',
     'outputs':{'qwen3-vl-8b':'Approval by J.A.G.','qwen3.5-9b':'Approval by J.A.G.',
                'qwen3.6-27b':'approval by J.A.G.','qwen3.8-27b':'Approval by G.A.G.','deepseek-ocr-2':None}},
    {'id':'pdf7_staff_initials','page_id':'pdf_page_07','reference':'Staff J.A.',
     'importance_es':'3-VL y 3.6 añaden una G en esta sigla; 3.5 y 3.8 conservan J.A.',
     'outputs':{'qwen3-vl-8b':'Staff:J.A.G.','qwen3.5-9b':'staff J.A.',
                'qwen3.6-27b':'Staff J.A.G.','qwen3.8-27b':'Staff J.A.','deepseek-ocr-2':None}},
    {'id':'pdf8_rated','page_id':'pdf_page_08','reference':'rated by his C.O.',
     'importance_es':'rated se refiere a evaluación; ruled y tried cambian el sentido. Solo 3-VL conserva todo el fragmento.',
     'outputs':{'qwen3-vl-8b':'rated by his C.O.','qwen3.5-9b':'ruled by his C.O.',
                'qwen3.6-27b':'ruled by his C.O.','qwen3.8-27b':'tried by his C.O.','deepseek-ocr-2':'rated by C.B.'}},
    {'id':'typed_place','page_id':'typed','reference':'Gloversville',
     'importance_es':'Topónimo del membrete. Todos lo cambian o lo omiten; 3.6 y 3.8 producen topónimos muy diferentes.',
     'outputs':{'qwen3-vl-8b':'GLOVERVILLE','qwen3.5-9b':'GLASGOWVILLE',
                'qwen3.6-27b':'ELIZABETHTOWN','qwen3.8-27b':'CLAYTONVILLE','deepseek-ocr-2':None}},
    {'id':'deepseek_invention','page_id':'pdf_page_07','reference':'Would assignment of defense Counsel and law officer by J.A.G. do it?',
     'importance_es':'DeepSeek introduce un tema y entidades que no aparecen en la fuente: fallo grave de fidelidad.',
     'outputs':{'deepseek-ocr-2':'Would assignment of federal lands to al Qaeda fit the criteria set by the 9/11 Commission?'}}
]
for case in cases:
    for m,quote in case['outputs'].items():
        if quote is not None:
            assert flat(quote) in flat(texts[m][case['page_id']]), (case['id'],m,quote)

page_notes = [
    {'page_id':'typed','finding_es':'DeepSeek, 3.5, 3.6 y 3.8 coinciden en las 341 palabras del cuerpo con la referencia revisada. 3-VL omite parte de una frase. El membrete pequeño produce apellidos y lugares erróneos en todos; DeepSeek omite toda la junta.'},
    {'page_id':'handwritten','finding_es':'3.8 conserva Garfield y 1865; 3.5 conserva solo el año. Todos alteran pasajes legibles, incluyendo efficient levees y revenue. No hay transcripción íntegra fiable de esta página.'},
    {'page_id':'pdf_page_01','finding_es':'Los Qwen recuperan gran parte del cuerpo pero mezclan notas marginales y omiten or Counsel. 3.6 y 3.8 sí incluyen Prosecution, ausente en los pequeños. DeepSeek genera repeticiones y contenido ajeno.'},
    {'page_id':'pdf_page_02','finding_es':'Zona con interlineados y tachaduras: todos los Qwen confunden varias notas. 3-VL escribe Finnish por Furnish; 3.8 sustituye Civilians por Officers. Ningún resultado representa consistentemente las tachaduras como tales.'},
    {'page_id':'pdf_page_03','finding_es':'3.8 es muy cercano a la referencia en el cuerpo. 3.6 desarrolla wtg. como writing y pluraliza Application; los pequeños cambian of por & y Ct. por at. DeepSeek reescribe el contenido.'},
    {'page_id':'pdf_page_04','finding_es':'Página casi vacía: todos transcriben la línea tachada sin indicar que está tachada. 3-VL además lee Brutish en el título. La prueba no demuestra capacidad de edición diplomática.'},
    {'page_id':'pdf_page_05','finding_es':'3.6 y 3.8 coinciden con el subconjunto normalizado de esta página. 3.5 cambia Counsel por Court y affirmance por affirmation, entre otras diferencias; DeepSeek presenta muchas sustituciones.'},
    {'page_id':'pdf_page_06','finding_es':'3.6 y 3.8 recuperan ambos rótulos marginales Court and Counsel y Judge; 3.5 recupera el primero y 3-VL omite ambos. 3.8 cambia J.A.G. por G.A.G.; todos insertan review tachado como si fuera texto activo. Las últimas líneas siguen siendo difíciles.'},
    {'page_id':'pdf_page_07','finding_es':'3.5 coincide en los tokens del cuerpo normalizado, pero da 4 como número de página donde la imagen muestra 6: ese error no cuenta en el WER. 3.8 cambia If por A y el marcador (a) por (as; 3.6 cambia defense por defence y J.A. por J.A.G. DeepSeek inventa contenido.'},
    {'page_id':'pdf_page_08','finding_es':'3-VL conserva rated; 3.5 y 3.6 escriben ruled, y 3.8 escribe tried. La palabra dudosa de la referencia no se usa para juzgar exactitud. 3.5 termina con Price en lugar de officer.'}
]

report = {
 'title_es':'Revisión detallada de las transcripciones locales',
 'created_on':'2026-11-14','source_reference_sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
 'scope_es':'Revisión de las 50 salidas guardadas: cinco modelos y diez páginas únicas. No se ejecutó inferencia nueva.',
 'reference_policy':{'author_label':'Astra Ultra','selected_by':'user','role_es':'Referencia fija para evaluar las salidas locales; Sol 6.1 realiza solo la comparación.','source_file_modified_by_this_review':False,'uncertainty_handling_es':'Se conservan las marcas de duda que Astra ya dejó. Esos pasajes no se usan para atribuir errores nuevos a los modelos locales.'},
 'metrics':summary, 'evidence_cases':cases, 'page_findings':page_notes,
 'conclusion_es':[
     'Mejor equilibrio observado: Qwen3.5-9B. Tarda unos 76 segundos de inferencia para estas diez páginas y conserva 8 de los 12 apellidos del membrete.',
     'Qwen3.8-27B aporta lecturas útiles como Garfield y 1865, mejor recuperación de algunos rótulos y menor WER en el subconjunto anterior. Tiene contraejemplos importantes y no domina página por página.',
     'Qwen3.6-27B no muestra una ventaja consistente frente a 3.5 en esta muestra que compense multiplicar por más de cinco el tiempo. Puede resolver pasajes donde el pequeño falla.',
     'Qwen3-VL-8B sirve como segunda lectura complementaria: conserva rated donde los otros Qwen fallan, pero omite palabras del cuerpo mecanografiado y falla más en fechas y membrete.',
     'DeepSeek-OCR-2 no es una opción fiable para estos manuscritos en la configuración probada: produce omisiones, repeticiones y contenido inventado. El cuerpo mecanografiado es una excepción mucho más sencilla.'
 ],
 'limitations_es':[
     'El WER disponible cubre solo 168 tokens normalizados de las páginas PDF 5 y 7, no todas las diez páginas. La ventaja de 3.8 sobre 3.5 y 3.6 en ese subconjunto es una palabra.',
     'La comprobación de apellidos cubre doce apellidos de un único membrete. Es presencia literal, no exactitud completa de entidades ni validación de los apellidos Cree del Excel.',
     'Números, fechas, mayúsculas y muchas diferencias de formato se excluyen de ese WER. Hay errores relevantes que el indicador no captura.',
     'La transcripción de Astra Ultra es la referencia elegida por el usuario. Se mantienen sus marcas de duda y no se puntúan esas palabras inciertas en esta revisión cualitativa.',
     'Los tiempos suman inferencia sin carga; las dos imágenes previas reutilizan sus resultados. Los 27B usaron CPU/RAM además de GPU y los pequeños estuvieron completos en GPU.',
     'La referencia y la selección de casos ya fueron vistas en esta conversación; no se trata de un ensayo ciego ni permite generalizar a toda la colección.'
 ]}
(OUT/'detailed_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

md=['# Revisión detallada de los resultados','','**Referencia fija: transcripción de Astra Ultra.** Sol 6.1 compara las salidas de los modelos locales contra esa referencia. Esta revisión no modifica la transcripción de Astra.','','## Conclusión','']+report['conclusion_es']
md+=['','## Qué se comparó','',report['scope_es'],'',
     'Se revisó el texto completo guardado de cada salida y se contrastaron pasajes con la transcripción de Astra Ultra. No se asigna una puntuación global de fidelidad a todo el corpus. Las métricas existentes se conservan con su alcance original.','',
     '| Modelo | Inferencia de 10 páginas | Errores en 168 tokens del subconjunto | Apellidos exactos del membrete |',
     '|---|---:|---:|---:|']
for row in summary:
    md.append(f"| {row['label']} | {row['total_inference_seconds']:.1f} s | {row['handwriting_subset']['word_edits']} | {row['typed_board_surnames']['exact_matches']}/12 |")
md+=['','Los errores en 168 tokens corresponden solo a las páginas PDF 5 y 7, después de normalizar puntuación, abreviaturas y eliminar cifras aisladas. La comprobación de apellidos es una prueba distinta. Las dos columnas no se deben sumar ni interpretar como exactitud global.','',
     '## Diferencias concretas entre Qwen','',
     '| Pasaje de referencia | Qwen3-VL-8B | Qwen3.5-9B | Qwen3.6-27B | Qwen3.8-27B |',
     '|---|---|---|---|---|']
for case in cases:
    if case['id']=='deepseek_invention':continue
    cells=[case['page_id']+': '+case['reference']]
    cells += [case['outputs'].get(m) or 'Omitido / no recuperado' for m in ['qwen3-vl-8b','qwen3.5-9b','qwen3.6-27b','qwen3.8-27b']]
    md.append('| '+' | '.join(c.replace('|','/').replace('\n',' ') for c in cells)+' |')
md+=['','## Revisión por página','']
for note in page_notes:md+=['- **'+note['page_id']+'**: '+note['finding_es']]
md+=['','## Por qué DeepSeek no resulta válido para los manuscritos','',
     'En PDF 7, la fuente pregunta por la asignación de abogado defensor y law officer por J.A.G. DeepSeek genera:',
     '', '> '+cases[-1]['outputs']['deepseek-ocr-2'], '',
     'Ese contenido no aparece en la página. En otras páginas repite frases y altera entidades. Sus 39 segundos de inferencia no representan una transcripción fiel.', '',
     '## Implicación para las búsquedas del Excel','',
     'Usaría Qwen3.5-9B como primera transcripción y guardaría siempre archivo, página y fragmento de imagen. Las variantes del Excel ayudan a recuperar algunas grafías, pero no corrigen por sí solas una persona, lugar o fecha inventados.', '',
     'Qwen3.8 puede aportar una segunda lectura de los casos dudosos. Un desacuerdo entre modelos debe volver a la imagen; el acuerdo tampoco garantiza exactitud, como muestra la pérdida de revenue en todos los Qwen.', '',
     '## Apellidos del membrete','',
     '| Apellido fuente | 3-VL | 3.5 | 3.6 | 3.8 | DeepSeek |', '|---|---:|---:|---:|---:|---:|']
for name in names:
    md.append('| '+name+' | '+' | '.join('Sí' if next(r for r in summary if r['model']==m)['typed_board_surnames']['per_surname'][name] else 'No' for m in ['qwen3-vl-8b','qwen3.5-9b','qwen3.6-27b','qwen3.8-27b','deepseek-ocr-2'])+' |')
md+=['','## Archivos para revisar','', '[Transcripción de Astra Ultra, referencia de esta comparación](../assistant_reference/transcriptions.md)','']
for m in ORDER:md.append(f"- [{labels[m]}]({m}/transcriptions.md)")
md+=['','## Límites','']+['- '+line for line in report['limitations_es']]
(OUT/'detailed_comparison.md').write_text('\n'.join(md)+'\n')
print(json.dumps({'models_reviewed':len(summary),'pages_reviewed':len(page_notes),'outputs_reviewed':sum(len(m['pages']) for m in models.values()),'evidence_cases':len(cases),'files':['detailed_comparison.md','detailed_comparison.json']},indent=2))
