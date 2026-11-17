"""Restrict graph evidence before retrieval, including merged descriptions."""
from collections import Counter, defaultdict


def restrict_store(store, entity_ids):
    """Apply the source restriction before vector ranking, not after top-k."""
    from graphrag_vectors.filtering import Condition, Operator
    search = store.similarity_search_by_text
    restriction = Condition(field=store.id_field, operator=Operator.in_, value=list(entity_ids))
    def restricted_search(*args, **kwargs):
        kwargs['filters'] = restriction
        return search(*args, **kwargs)
    store.similarity_search_by_text = restricted_search
    return store


def matches(page, filters):
    folder = page.get('folder', '')
    return (not filters.get('folders') or any(folder==f or folder.startswith(f+'/') for f in filters['folders'])) and (
        not filters.get('documents') or page.get('document') in filters['documents'])


def normalize(value, records):
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value)-{'folders','documents'}:
        raise ValueError('Filtros de fuentes no válidos')
    result = {}
    for key, field in [('folders','folder'), ('documents','document')]:
        values = value.get(key, [])
        if not isinstance(values, list) or len(values)>10000 or any(not isinstance(v,str) for v in values):
            raise ValueError('Selecciona carpetas y documentos del catálogo')
        allowed = {r.get(field,'') for r in records}
        if any(v not in allowed for v in values):
            raise ValueError('Una fuente no pertenece a la versión publicada. Actualiza el catálogo.')
        result[key] = sorted(set(values))
    if any(result.values()) and not any(matches(r,result) for r in records):
        raise ValueError('La combinación de carpetas y documentos no contiene páginas publicadas')
    return result


def restrict_review(review, filters):
    edges = [e for e in review['relationships'] if matches(e['page'],filters)]
    ends = {v for e in edges for v in (e['source'],e['target'])}
    nodes = []
    for n in review['nodes']:
        mentions = [m for m in n.get('mentions',[]) if matches(m['page'],filters)]
        if mentions or n['id'] in ends:
            nodes.append(dict(n, mentions=mentions, sources=list({m['text_unit_id'] for m in mentions})))
    selection = [p for p in review.get('selection',[]) if matches(p,filters)]
    return dict(review, nodes=nodes, relationships=edges, selection=selection, pages=len(selection),
                source_documents=len({r['document'] for r in selection}), entity_counts=dict(Counter(n['type'] for n in nodes)))


def restrict_tables(tables, inputs, review, filters):
    """Never reuse a description/community report that mixes excluded sources.

    Existing vectors rank eligible entities, but only source-scoped evidence is
    passed to the language model. Original row indices preserve citation IDs.
    """
    scoped = restrict_review(review,filters)
    selected = [p for p in inputs if matches(p,filters)]
    pages = {p['id'] for p in selected}
    units = tables['text_units'].loc[tables['text_units'].document_id.isin(pages)].copy()
    unit_ids = set(units.id)
    nodes = {n['id']:n for n in scoped['nodes']}
    pairs = defaultdict(list)
    descriptions = defaultdict(list)
    for edge in scoped['relationships']:
        pairs[edge['source'],edge['target']].append(edge)
        for endpoint in (edge['source'],edge['target']):
            descriptions[endpoint].append(edge['description'])
    entities = tables['entities'].loc[tables['entities'].title.isin(nodes)].copy()
    for i, row in entities.iterrows():
        node = nodes[row.title]
        quotes = [q['quote'] for m in node['mentions'] for q in m.get('quotes',[])]
        entities.at[i,'description'] = '\n'.join(dict.fromkeys(quotes+descriptions[row.title])) or row.title
        entities.at[i,'text_unit_ids'] = [v for v in row.text_unit_ids if v in unit_ids]
        entities.at[i,'frequency'] = len(entities.at[i,'text_unit_ids'])
        entities.at[i,'degree'] = sum(row.title in pair for pair in pairs)
    rels = tables['relationships'].loc[tables['relationships'].apply(lambda r:(r.source,r.target) in pairs,axis=1)].copy()
    for i, row in rels.iterrows():
        edges = pairs[row.source,row.target]
        rels.at[i,'description'] = '\n'.join(dict.fromkeys(e['description'] for e in edges))
        rels.at[i,'text_unit_ids'] = list(dict.fromkeys(e['text_unit_id'] for e in edges if e['text_unit_id'] in unit_ids))
        rels.at[i,'weight'] = len(edges)
        rels.at[i,'combined_degree'] = sum(sum(endpoint in pair for pair in pairs) for endpoint in (row.source,row.target))
    entity_ids, rel_ids = set(entities.id), set(rels.id)
    for field, allowed in [('entity_ids',entity_ids),('relationship_ids',rel_ids),('covariate_ids',set())]:
        if field in units:
            units[field] = units[field].map(lambda values:[v for v in values if v in allowed])
    # A synthetic membership row keeps isolated entities in the official adapter;
    # no community summary is used for a restricted query.
    communities = tables['communities'].iloc[:0].copy()
    import pandas as pd
    membership = dict(id='source-scope', human_readable_id=0, community=0, level=0, parent=-1,
                      children=[], title='Selected sources', entity_ids=list(entity_ids),
                      relationship_ids=list(rel_ids), text_unit_ids=list(unit_ids), period='', size=len(entity_ids))
    communities = pd.DataFrame([membership], columns=communities.columns)
    result = dict(tables, entities=entities, relationships=rels, text_units=units,
                  communities=communities, community_reports=tables['community_reports'].iloc[:0].copy())
    if 'covariates' in result:
        result['covariates'] = result['covariates'].iloc[:0].copy()
    return result, selected, scoped
