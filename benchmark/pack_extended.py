import json,re,hashlib,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parent
reference=json.loads((ROOT/'assistant_reference/transcriptions.json').read_text())
refs={'typed':reference['documents'][0]['pages'][0]['transcription'],'handwritten':reference['documents'][1]['pages'][0]['transcription']}
refs.update({f"pdf_page_{p['page_number']:02d}":p['transcription'] for p in reference['documents'][2]['pages']})
def words(s):return re.findall('[a-z0-9]+',s.lower())
def pdf_words(s):
    s=unicodedata.normalize('NFKC',s)
    s=re.sub(r'\.{2,}', '.',s)
    s=s.replace("'",'').replace('’','')
    s=re.sub(r'\b(?:[A-Za-z]\.[ \t]*)+[A-Za-z]\.?(?=\s|$|[,;:])',lambda m:re.sub('[^a-z]','',m.group().lower()),s)
    s=re.sub(r'\[(?:illegible|unclear[^\]]*)\]',' ',s,flags=re.I)
    return [t for t in words(s) if not t.isdigit()]
def edits(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):cur.append(min(cur[-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]
summary=[]
for folder in sorted((ROOT/'extended_results').iterdir()):
    if not folder.is_dir():continue
    pages=[]
    for name in refs:
        base=ROOT/'results'/folder.name if name in ['typed','handwritten'] else folder
        txt=base/(name+'.txt');meta=base/(name+'.json')
        if not txt.exists() or not meta.exists():continue
        pages.append({'page_id':name,'transcription':txt.read_text(),'run':json.loads(meta.read_text()),'reused_previous_run':name in ['typed','handwritten']})
    result={'model':folder.name,'reference':'../assistant_reference/transcriptions.json','reference_status':'provisional_ai_visual_transcription','pages':pages}
    (folder/'transcriptions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (folder/'transcriptions.md').write_text('# '+folder.name+'\n\n'+ '\n\n'.join('## '+p['page_id']+'\n\n```text\n'+p['transcription']+'\n```' for p in pages))
    # Page 5 has no uncertain reference readings. All other handwritten pages need review.
    p=next((p for p in pages if p['page_id']=='pdf_page_05'),None)
    metric=None
    if p:
        a=words(refs['pdf_page_05']);b=words(p['transcription']);n=edits(a,b)
        metric={'reference_words':len(a),'word_edits':n,'provisional_wer':n/len(a),'scope':'PDF page 5 only, case/punctuation ignored; provisional AI reference, not human-validated.'}
    clean_metrics=[]
    for name in ['pdf_page_05','pdf_page_07']:
        candidate=next((p for p in pages if p['page_id']==name),None)
        if candidate:
            a=pdf_words(refs[name]);b=pdf_words(candidate['transcription']);n=edits(a,b)
            clean_metrics.append({'page_id':name,'reference_words':len(a),'word_edits':n,'provisional_wer':n/len(a)})
    scored_words=sum(m['reference_words'] for m in clean_metrics)
    scored_edits=sum(m['word_edits'] for m in clean_metrics)
    summary.append({'model':folder.name,'completed_pages':len(pages),'total_inference_seconds':sum(p['run']['seconds'] for p in pages),'pdf_page_5_metric':metric,'clear_handwriting_pages':clean_metrics,'clear_handwriting_weighted_wer':scored_edits/scored_words if scored_words else None,'clear_handwriting_reference_words':scored_words,'clear_handwriting_word_edits':scored_edits})
inputs=[{'page_id':f'pdf_page_{i:02d}','sha256':hashlib.sha256((ROOT/'extended_inputs'/f'pdf_page_{i:02d}.png').read_bytes()).hexdigest()} for i in range(1,9)]
report={'input_note':'PDF embedded page images at native resolution; page 4 rotated 180 degrees to match PDF display. Same images for each local model.','inputs':inputs,'limitations':['AI reference is provisional. Handwriting WER on PDF pages 5 and 7 is indicative only and does not establish a whole-corpus winner.','Scored pages contain no tentative word candidates in the main transcription. Page 7 has an unreadable deleted fragment described separately, not scored.','Handwriting subset metric applies Unicode NFKC and ignores case, punctuation, standalone numeric tokens and illegible/unclear markers; it does not measure numeral/date accuracy.','Two previously tested PNG pages reuse the existing results.','27B models partly run on CPU/RAM; smaller models entirely on GPU.','Do not score bracketed uncertainty annotations as source words.'],'models':summary}
(ROOT/'extended_results/comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
md=['# Comparación local ampliada','','Referencia visual de IA provisional, pendiente de validación humana. Diez páginas únicas por modelo. Las dos imágenes del ensayo anterior reutilizan sus resultados; las ocho páginas PDF son nuevas.','','| Modelo | Páginas completadas | Inferencia total (s) | WER provisional PDF 5 y 7 |','|---|---:|---:|---:|']
for r in summary:
    wer=r['clear_handwriting_weighted_wer']
    md.append(f"| {r['model']} | {r['completed_pages']}/10 | {r['total_inference_seconds']:.1f} | {wer:.1%} |" if wer is not None else f"| {r['model']} | {r['completed_pages']}/10 | {r['total_inference_seconds']:.1f} | pendiente |")
md+=['','El porcentaje compara solo dos páginas manuscritas legibles (PDF 5 y 7). No mide todo el documento, ni exactitud de números o fechas. Menor WER significa menos diferencias respecto a la referencia provisional. Los tiempos excluyen carga y descarga de modelos.','','## Transcripciones','']
for r in summary:md.append(f"- {r['model']}: [Markdown]({r['model']}/transcriptions.md) · [JSON]({r['model']}/transcriptions.json)")
md+=['','## Lectura de los resultados','',
     'Qwen3.8-27B obtiene la menor diferencia en el subconjunto puntuado. La diferencia respecto a Qwen3.5-9B y Qwen3.6-27B es de muy pocas palabras y no demuestra superioridad general.',
     'Qwen3.5-9B ofrece un buen equilibrio entre fidelidad y velocidad en este equipo. Los 27B usan GPU y CPU/RAM y tardan bastante más.',
     'DeepSeek-OCR-2 produce errores graves de contenido en los manuscritos. En la página PDF 7 introduce referencias ajenas al documento, incluidas menciones a al Qaeda y una comisión del 9/11. Su rapidez no implica una transcripción válida.',
     'La carta manuscrita difícil de 1865 sigue necesitando revisión con la imagen. El cuerpo mecanografiado es mucho más sencillo; sus resultados previos se conservan en los archivos por modelo.',
     '', '## Límites', '',
     '- Referencia visual de IA provisional, pendiente de validación humana. El porcentaje cubre únicamente las páginas PDF 5 y 7; no todas las diez páginas.',
     '- Se ignoran mayúsculas, puntuación, variantes de puntuación de abreviaturas y números aislados en esa medida. No evalúa exactitud de fechas o cifras.',
     '- La página 7 tiene una tachadura ilegible descrita aparte, excluida del texto de referencia puntuado.',
     '- Las dos imágenes anteriores reutilizan sus resultados ya guardados; las ocho páginas PDF se procesaron en esta ampliación.',
     '- Los modelos se ejecutaron uno a uno. Las pruebas finales usaron controles de RAM y VRAM.',
     '- La referencia se corrigió visualmente en la página PDF 5: Appeal Court, en singular. La corrección está anotada en las notas de la fuente.']
(ROOT/'extended_results/comparison.md').write_text('\n'.join(md)+'\n')
print(json.dumps(summary,indent=2))
