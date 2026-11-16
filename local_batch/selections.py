"""Immutable, attributed exports of explicitly selected page versions. No inference."""
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path, PurePosixPath
import re
import time
import uuid

import reading_matrix
import sources


def required_text(value, label, maximum=160):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError(label+': escribe entre 1 y '+str(maximum)+' caracteres')
    return value.strip()


def get(root, ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):
        raise ValueError('Selección inválida')
    path=root/'selections'/ident/'selection.json'
    if not path.exists():raise ValueError('No se encontró la selección guardada')
    return sources.read(path)


def listing(root):
    result=[]
    for path in (root/'selections').glob('*/selection.json'):
        value=sources.read(path)
        result.append({k:value[k] for k in ('id','title','created','researcher','curator','pages','readings')})
    return sorted(result,key=lambda v:v['created'],reverse=True)


def context(value, text):
    if not isinstance(value,dict) or len(json.dumps(value,ensure_ascii=False))>32000:
        raise ValueError('El contexto de búsqueda es demasiado grande o inválido')
    # Metadata describes the user's selection; source quotes are checked independently.
    result={}
    for key in ('kind','query','mode','catalog_revision','search_created','filters','categories','matches'):
        if key in value:result[key]=value[key]
    quotes=value.get('excerpts',[])
    if not isinstance(quotes,list) or len(quotes)>10 or any(not isinstance(q,str) or len(q)>4000 for q in quotes):
        raise ValueError('Fragmentos de selección inválidos')
    if any(q not in text for q in quotes):raise FileExistsError('Un fragmento seleccionado ya no coincide con la transcripción. Vuelve a comprobar esa página.')
    result['excerpts']=quotes
    matches=result.get('matches',[])
    if not isinstance(matches,list) or len(matches)>500 or any(not isinstance(m,dict) for m in matches):
        raise ValueError('Coincidencias de selección inválidas')
    result['matches']=[{key:str(m[key])[:1000] for key in ('label','kind','priority','quality','alias') if key in m} for m in matches]
    return result


def create(root, payload):
    title=required_text(payload.get('title'),'Título de la selección')
    researcher=required_text(payload.get('researcher'),'Quién hizo la búsqueda')
    curator=required_text(payload.get('curator'),'Quién depuró la selección')
    records=payload.get('records')
    if not isinstance(records,list) or not 1<=len(records)<=2000:raise ValueError('Selecciona entre 1 y 2.000 lecturas')
    rows=[];seen=set()
    # Review saves are serialized; source membership is checked again before committing.
    # Existing pages remain exportable while unrelated new sources are transcribed.
    with reading_matrix.review.LOCK:
        for item in records:
            if not isinstance(item,dict):raise ValueError('Registro de selección inválido')
            if not isinstance(item.get('version','original'),str):raise ValueError('Versión de lectura inválida')
            try:row=reading_matrix.snapshot(root,item)
            except (ValueError,OSError,KeyError) as e:raise ValueError('Una página seleccionada ya no está disponible. Restaura su fuente o retírala de Mi selección: '+str(item.get('document',''))+' · p. '+str(item.get('page','')))
            key=(row['document_id'],row['page'],row['version'])
            if key in seen:continue
            seen.add(key)
            expected=item.get('text_sha256')
            if expected and expected!=row['text_sha256']:
                raise FileExistsError(row['document']+' · p. '+str(row['page'])+': la transcripción cambió desde que la seleccionaste. Comprueba la fuente y vuelve a marcarla.')
            note=item.get('note','')
            if not isinstance(note,str) or len(note)>5000:raise ValueError('La nota de relevancia admite hasta 5.000 caracteres')
            contexts=item.get('contexts',[])
            if not isinstance(contexts,list) or len(contexts)>30:raise ValueError('Contextos de búsqueda inválidos')
            row.update(note=note,contexts=[context(c,row['text']) for c in contexts],selected_at=item.get('selected_at'),selection_hash_verified=bool(expected))
            if row['selected_at'] is not None and (type(row['selected_at']) not in (int,float) or not 0<row['selected_at']<=time.time()+60):raise ValueError('Fecha de selección inválida')
            human=sources.read(root/'reviews'/row['document_id']/f"{row['page']}.json") if row['version']=='human' else {}
            row['transcription_reviewer']=human.get('reviewer','');row['review_revision']=human.get('revision','')
            doc,prefix=reading_matrix.review.locate(root,row['document_id'],row['page'])
            row['image_relative_path']=str(prefix.with_suffix('.png').relative_to(root.resolve()))
            row['source_sha256']=doc.get('sha256','');row['document_pages']=doc['page_count'];rows.append(row)
        active={sources.ident(d['source']):d for d in reading_matrix.review.catalog(root)}
        if any(r['document_id'] not in active or active[r['document_id']].get('sha256','')!=r['source_sha256'] for r in rows):
            raise FileExistsError('El inventario cambió durante la exportación. Actualiza Mi selección y vuelve a intentarlo.')
        ident=uuid.uuid4().hex
        value=dict(id=ident,title=title,researcher=researcher,curator=curator,created=time.time(),
                   pages=len({(r['document_id'],r['page']) for r in rows}),readings=len(rows),rows=rows,
                   attribution='Nombres declarados por el usuario al guardar la selección.',
                   policy='Solo lecturas marcadas explícitamente; texto guardado y fragmentos verificados. La selección de relevancia no valida la exactitud de la transcripción.')
        sources.write(root/'selections'/ident/'selection.json',value)
        sources.audit(root,'selection_export_created',selection=ident,title=title,researcher=researcher,curator=curator,pages=value['pages'],readings=value['readings'])
    return {k:value[k] for k in ('id','title','created','researcher','curator','pages','readings')}


def iso(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat() if value else ''


def csv_bytes(value, origin):
    stream=io.StringIO(newline='');writer=csv.writer(stream,quoting=csv.QUOTE_ALL)
    writer.writerow(['Selección','Título','Buscado por','Depurado por','Fecha de exportación (UTC)','Fecha de selección (UTC)',
                     'Carpeta','Archivo','Ruta de origen','Página PDF','Páginas del documento','Versión de transcripción','Estado de revisión',
                     'Revisor de la transcripción','Revisión del texto','Referentes o términos encontrados','Tipos de referente','Prioridades',
                     'Tipos de coincidencia','Fragmentos relevantes','Motivo de selección','Búsquedas de origen','Filtros al seleccionar',
                     'Revisiones de criterios','Abrir página en la app','Imagen de origen','ID del documento','Huella del PDF','Huella del texto'])
    def unique(values):return ' | '.join(dict.fromkeys(str(v) for v in values if v is not None and str(v)))
    def cell(v):
        v=str(v)
        return "'"+v if re.match(r'^[\s]*[=+@-]',v) or v.startswith(('\t','\r','\n')) else v
    for index,row in enumerate(value['rows']):
        matches=[m for c in row['contexts'] for m in c.get('matches',[])]
        fields=[value['id'],value['title'],value['researcher'],value['curator'],iso(value['created']),iso(row['selected_at']),
                row['folder'],PurePosixPath(row['document']).name,row['document'],row['page'],row['document_pages'],
                {'original':'Original','human':'Edición humana'}.get(row['version'],row['version']),row['review_status'],
                row['transcription_reviewer'],row['review_revision'],unique(m.get('label') for m in matches),unique(m.get('kind') for m in matches),
                unique(m.get('priority') for m in matches),unique(m.get('quality') for m in matches),
                '\n\n'.join(dict.fromkeys(q for c in row['contexts'] for q in c.get('excerpts',[]))),row['note'],
                unique(c.get('query') or c.get('kind') for c in row['contexts']),
                json.dumps([c.get('filters',{}) for c in row['contexts']],ensure_ascii=False),unique(c.get('catalog_revision') for c in row['contexts']),
                origin+'/?view=selection&saved='+value['id']+'&row='+str(index),origin+'/selections-image?id='+value['id']+'&row='+str(index),row['document_id'],row['source_sha256'],row['text_sha256']]
        writer.writerow([cell(v) for v in fields])
    return ('\ufeff'+stream.getvalue()).encode('utf-8')


def image_path(root,ident,index):
    value=get(root,ident)
    if not 0<=index<len(value['rows']):raise ValueError('Página no válida')
    path=(root/value['rows'][index]['image_relative_path']).resolve()
    if not path.is_relative_to((root/'documents').resolve()) or path.suffix!='.png':raise ValueError('Imagen no válida')
    return path
