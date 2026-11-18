// Shared exploration state. These filters never change the evidence of a saved answer.
(function(root){
 const empty=()=>({query:'',type:'',relation:'',entity:'',edges:[],evidence:'',eventDate:'',documentDate:''});
 const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 function filter(graph,state){
  if(!graph)return graph;
  const s={...empty(),...state},active=s.query||s.type||s.relation||s.entity||s.edges.length||s.evidence||s.eventDate||s.documentDate;
  if(!active)return graph;
  const matching=new Set(graph.nodes.filter(n=>(!s.type||n.type===s.type)&&(!s.query||norm(n.label).includes(norm(s.query)))).map(n=>n.id));
  const relationships=graph.relationships.filter(e=>(!s.entity||e.source===s.entity||e.target===s.entity)&&(!s.edges.length||s.edges.includes(e.id))&&(!s.type||e.source_type===s.type||e.target_type===s.type)&&(!s.query||matching.has(e.source)||matching.has(e.target)||norm(e.description).includes(norm(s.query)))&&(!s.relation||norm(e.fields?.relation).includes(norm(s.relation)))&&(!s.evidence||e.quote_status===s.evidence||(s.evidence==='conditional'&&e.flags?.includes('conditional_or_proposed_context'))||(s.evidence==='role'&&e.flags?.includes('unnamed_role_not_identified_person')))&&(!s.eventDate||(e.fields?.event_time||'unknown')===s.eventDate)&&(!s.documentDate||(e.fields?.document_time||'unknown')===s.documentDate));
  const ids=new Set(relationships.flatMap(e=>[e.source,e.target]));
  if(s.entity)ids.add(s.entity);
  if(!s.entity&&!s.edges.length&&!s.relation&&!s.evidence&&!s.eventDate&&!s.documentDate)for(const id of matching)ids.add(id);
  const nodes=graph.nodes.filter(n=>ids.has(n.id));
  const pageKey=p=>JSON.stringify([p.document_id,p.page,p.version]);
  const pages=new Set(relationships.map(e=>pageKey(e.page)));
  for(const n of nodes)for(const m of n.mentions||[])pages.add(pageKey(m.page));
  const selection=(graph.selection||[]).filter(p=>pages.has(pageKey(p))),entity_counts={};for(const n of nodes)entity_counts[n.type]=(entity_counts[n.type]||0)+1;
  const evidence_counts={total:relationships.length,quotes_found:relationships.filter(e=>e.quote_status==='found').length,quotes_pending:relationships.filter(e=>e.quote_status!=='found').length,human_validated:relationships.filter(e=>e.human_validation==='validated').length,entity_pairs:new Set(relationships.map(e=>JSON.stringify([e.source,e.target]))).size,pages_with_relationships:new Set(relationships.map(e=>pageKey(e.page))).size};
  for(const field of ['event_time','document_time'])evidence_counts[field+'_identified']=relationships.filter(e=>e.fields?.[field]&&e.fields[field].toLowerCase()!=='unknown').length;
  return {...graph,nodes,relationships,selection,pages:selection.length,entity_counts,evidence_counts,source_documents:new Set(selection.map(p=>p.document)).size,exploration_filters:s};
 }
 if(typeof module!=='undefined'){module.exports={filter,empty};return}
 let state=empty();const watchers=new Set();
 const api={get:()=>({...state,edges:[...state.edges]}),filter:graph=>filter(graph,state),set(patch,origin='controls'){state={...state,...patch};for(const fn of watchers)fn(state,origin);window.dispatchEvent(new CustomEvent('knowledge-filter-change',{detail:{origin}}))},clear(origin='controls'){api.set(empty(),origin)},subscribe(fn){watchers.add(fn);return()=>watchers.delete(fn)}};
 root.KnowledgeGraphFilters=api;
 root.mountKnowledgeFilters=function(host){
  const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n},t=(es,en,fr)=>({es,en,fr})[uiLanguage]||es;
  const bar=el('section');bar.className='kg-shared-filters';bar.dataset.noI18n='';const title=el('strong'),hint=el('small'),fields=el('div'),chips=el('p');chips.setAttribute('role','status');
  const query=el('input'),type=el('select'),relation=el('input'),clear=el('button');query.type=relation.type='search';clear.type='button';fields.append(query,type,relation,clear);bar.append(title,hint,fields,chips);host.append(bar);
  let timer;query.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>api.set({query:query.value,entity:'',edges:[]}),220)};relation.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>api.set({relation:relation.value,entity:'',edges:[]}),220)};type.onchange=()=>api.set({type:type.value,entity:'',edges:[]});clear.onclick=()=>{clearTimeout(timer);root.KnowledgeSourceScope?.set({});api.clear()};
  query.onkeydown=event=>{if(event.key!=='Enter')return;event.preventDefault();clearTimeout(timer);api.set({query:query.value,entity:'',edges:[]});requestAnimationFrame(()=>document.querySelectorAll('.graph-query-overview').forEach(n=>n.dispatchEvent(new Event('knowledge-search-submit'))))};
  function paint(){const s=api.get();title.textContent=t('Filtros compartidos · grafo, entidades y relaciones','Shared filters · graph, entities and relationships','Filtres partagés · graphe, entités et relations');hint.textContent=t('Explora una entidad o relación en cualquier vista. La selección te acompaña al cambiar de vista; no modifica el alcance de una respuesta guardada.','Explore an entity or relationship in any view. Your selection follows across views; saved answer scope stays unchanged.','Explorez une entité ou relation dans chaque vue. La sélection suit vos changements de vue sans modifier la portée des réponses enregistrées.');query.placeholder=t('Buscar entidad o contexto…','Find entity or context…','Chercher une entité ou un contexte…');query.setAttribute('aria-label',query.placeholder);relation.placeholder=t('Filtrar tipo de relación…','Filter relationship type…','Filtrer le type de relation…');relation.setAttribute('aria-label',relation.placeholder);type.setAttribute('aria-label',t('Tipo de entidad compartido','Shared entity type','Type d’entité partagé'));type.replaceChildren();for(const [k,v]of [['',t('Todos los tipos','All types','Tous les types')],...Object.entries(graphTypeNames)]){const o=el('option',typeof gResolve==='function'?gResolve(v):v);o.value=k;type.append(o)}type.value=s.type;query.value=s.query;relation.value=s.relation;clear.textContent=t('× Limpiar todos los filtros','× Clear all filters','× Effacer tous les filtres');chips.textContent=s.entity?s.entity.replace(/^(?:TYPE::)?[A-Z]+::/,''):s.edges.length?t(`${s.edges.length} relaciones seleccionadas`,`${s.edges.length} selected relationships`,`${s.edges.length} relations sélectionnées`):t('Selecciona un nodo, una relación o usa los filtros.','Select a node, a relationship, or use the filters.','Sélectionnez un nœud, une relation ou utilisez les filtres.');}
  api.subscribe(paint);paint();return {paint};
 };
 const css=document.createElement('style');css.textContent='.kg-shared-filters{padding:12px 16px;margin:0 0 14px;border:1px solid #cad7d1;border-radius:8px;background:#f0f5f2}.kg-shared-filters strong,.kg-shared-filters small{display:block}.kg-shared-filters small{font-size:11px;color:#546961;margin:5px 0 10px;line-height:1.5}.kg-shared-filters>div{display:flex;gap:8px;flex-wrap:wrap}.kg-shared-filters input{min-width:160px;flex:1}.kg-shared-filters p{font-size:11px;margin:8px 0 0}.kg-tab-icon{width:16px;height:16px;vertical-align:middle;margin-right:7px;flex:none}.kw-view-tabs button{display:inline-flex;align-items:center}.kg-shared-filters [hidden]{display:none}';document.head.append(css);
})(typeof window==='undefined'?this:window);
