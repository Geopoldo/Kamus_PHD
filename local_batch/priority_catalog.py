"""Versioned local edits layered over the workbook; never rewrite the source Excel."""
import json
import re
import time
from pathlib import Path

import priority_search as search
import priority_audit as audit


def settings(root):
    path = root/'priorities'/'catalog-overrides.json'
    value = search.read_json(path) if path.exists() else dict(revision=0, overrides={})
    for entry in value['overrides'].values():
        entry['priority'] = {'Segunda':'Media', 'Por definir':'Baja'}.get(entry['priority'], entry['priority'])
    return value


def editable(e):
    source = next((s['cells'] for s in e['sources'] if s['cells'].get('B') and s['cells'].get('C')), {})
    return dict(id=e['id'], label=e['label'], kind=e['kind'], priority=e['priority'], enabled=e.get('enabled', True),
                first_name=e.get('first_name', source.get('B', '') if e['kind']=='person' else ''),
                last_name=e.get('last_name', source.get('C', '') if e['kind']=='person' else ''),
                aliases=list(dict.fromkeys(p['label'] for p in e['patterns'] if p['origin']=='alias' and search.terms(p['label'])!=search.terms(e['label']))))


def rebuild(e, spec):
    patterns=[]
    def add(label, origin='canonical', reason=''):
        terms=search.terms(label)
        if terms and not any(p['terms']==terms for p in patterns):
            patterns.append(dict(label=label, terms=terms, origin=origin, reason=reason))
    add(spec['label'])
    for alias in spec['aliases']:
        add(alias, 'alias', 'Sinónimo configurado por el usuario')
    if spec['kind']=='person':
        first,last=spec['first_name'],spec['last_name']
        e['name_forms']=[dict(first_name=first,last_name=last)]
        for alias in spec['aliases']:
            if alias.casefold().endswith(' '+last.casefold()):
                e['name_forms'].append(dict(first_name=alias[:-len(last)].strip(),last_name=last))
        for form in e['name_forms']:
            given=re.sub(r'\b(?:Jr|Sr)\.?','',form['first_name'],flags=re.I).strip() or form['first_name']
            for label in [given+' '+last,last+' '+given,given.split()[0]+' '+last,given[0]+' '+last]:
                add(label,'generated','Abreviatura u orden invertido: comprobar la identidad')
    elif spec['kind']=='place':
        for label in [spec['label']]+spec['aliases']:
            core=' '.join(t for t in label.split() if search.normalize(t) not in {'lake','river','rivers','creek','lower'})
            if core!=label:add(core,'generated','Topónimo sin descriptor geográfico: revisar')
    e['patterns']=patterns


def catalog_for(root, workbook=None):
    catalog=search.build_catalog(workbook or search.WORKBOOK)
    saved=settings(root)
    by_id={e['id']:e for e in catalog['entities']}
    for ident,spec in saved['overrides'].items():
        e=by_id.get(ident)
        if e is None:
            e=dict(id=ident,label=spec['label'],kind=spec['kind'],priority=spec['priority'],patterns=[],sources=[],notes=[],traplines=[],user_added=True)
            catalog['entities'].append(e)
        previous=editable(e)
        changed=any(previous.get(k)!=spec.get(k) for k in ('label','kind','aliases','first_name','last_name'))
        e.update({k:spec[k] for k in ('label','kind','priority','enabled','first_name','last_name')})
        if changed:rebuild(e,spec)
        e['configured_by_user']=True
    families={e['id']:e for e in catalog['entities'] if e['kind']=='surname'}
    for e in catalog['entities']:
        family=families.get(e.get('surname_id'))
        if e['kind']!='person' or not family or not family.get('configured_by_user'):continue
        e['patterns']=[p for p in e['patterns'] if p['reason']!='Nombre con variante explícita del apellido']
        forms=e.get('name_forms') or [dict(first_name=s['cells']['B'],last_name=s['cells']['C']) for s in e['sources'] if s['cells'].get('B') and s['cells'].get('C')]
        for form in forms:
            if search.normalize(form['last_name']) not in (e['surname_id'].removeprefix('surname:'),search.normalize(family['label'])):continue
            for p in family['patterns']:
                if p['origin'] not in ('canonical','alias'):continue
                label=form['first_name']+' '+p['label'];tokens=search.terms(label)
                if not any(x['terms']==tokens for x in e['patterns']):
                    e['patterns'].append(dict(label=label,terms=tokens,origin='alias',reason='Nombre con variante explícita del apellido'))
    catalog['revision']=saved['revision']
    catalog['active_count']=sum(e.get('enabled',True) for e in catalog['entities'])
    return catalog


def get(root):
    catalog=catalog_for(root)
    return dict(revision=catalog['revision'],workbook=catalog['workbook'],entities=[dict(**editable(e),sources=e['sources'],notes=e['notes'],user_added=e.get('user_added',False)) for e in catalog['entities']])


def validate(item,known):
    if not isinstance(item,dict):raise ValueError('Cada referente debe ser un registro')
    ident=item.get('id','')
    if ident not in known and not re.fullmatch(r'user:[0-9a-f-]{36}',ident):raise ValueError('Referencia interna no válida')
    if item.get('kind') not in ('person','surname','place'):raise ValueError('Tipo no válido')
    if item.get('priority') not in ('Alta','Media','Baja'):raise ValueError('Prioridad no válida')
    if type(item.get('enabled')) is not bool:raise ValueError('Indica si el referente está activo')
    spec={k:item[k] for k in ('id','kind','priority','enabled')}
    for key in ('label','first_name','last_name'):
        value=item.get(key,'')
        if not isinstance(value,str) or len(value)>250:raise ValueError('Nombre demasiado largo o no válido')
        spec[key]=' '.join(value.split())
    if spec['kind']=='person':
        if not all(any(c.isalpha() for c in spec[key]) for key in ('first_name','last_name')):raise ValueError('Las personas requieren nombre(s) y apellido(s)')
        spec['label']=spec['first_name']+' '+spec['last_name']
    if not spec['label'] or not any(c.isalpha() for c in spec['label']):raise ValueError('Escribe un nombre; los ID no son términos de búsqueda')
    aliases=item.get('aliases',[])
    if not isinstance(aliases,list) or len(aliases)>80:raise ValueError('Máximo 80 sinónimos por referente')
    spec['aliases']=[]
    for alias in aliases:
        if not isinstance(alias,str) or len(alias)>250 or not any(c.isalpha() for c in alias):raise ValueError('Sinónimo no válido')
        alias=' '.join(alias.split())
        if alias and alias not in spec['aliases'] and search.terms(alias)!=search.terms(spec['label']):spec['aliases'].append(alias)
    return spec


def save(root,payload):
    if not isinstance(payload,dict) or not isinstance(payload.get('changes'),list) or not 1<=len(payload['changes'])<=500:
        raise ValueError('Envía entre 1 y 500 referentes modificados')
    with search._lock:
        current=settings(root)
        if type(payload.get('revision')) is not int or payload['revision']!=current['revision']:
            raise FileExistsError('Otra sesión cambió la lista. Recarga el editor antes de guardar para no sobrescribir cambios')
        catalog=catalog_for(root)
        known={e['id'] for e in catalog['entities']}
        changes=[validate(item,known) for item in payload['changes']]
        if len({s['id'] for s in changes})!=len(changes):raise ValueError('Hay referentes repetidos en el envío')
        overrides=dict(current['overrides'])
        overrides.update({s['id']:s for s in changes})
        if len(overrides)>2000:raise ValueError('Límite de 2000 referentes configurados')
        value=dict(revision=current['revision']+1,updated=time.time(),overrides=overrides)
        folder=root/'priorities';folder.mkdir(exist_ok=True)
        history=folder/'catalog_history';history.mkdir(exist_ok=True)
        encoded=json.dumps(value,ensure_ascii=False,indent=2)
        (history/f"revision_{value['revision']:06}.json").write_text(encoded,encoding='utf-8')
        temp=folder/'catalog-overrides.tmp';temp.write_text(encoded,encoding='utf-8');temp.replace(folder/'catalog-overrides.json')
        before={e['id']:editable(e) for e in catalog['entities']}
        audit.append(root,'catalog_saved',revision=value['revision'],previous_revision=current['revision'],changes=[dict(id=s['id'],label=s['label'],kind=s['kind'],fields={key:dict(before=before.get(s['id'],{}).get(key),after=val) for key,val in s.items() if key!='id' and before.get(s['id'],{}).get(key)!=val}) for s in changes])
    return dict(revision=value['revision'],job=search.start(root,requested_revision=value['revision'],reason='catalog_saved'))
