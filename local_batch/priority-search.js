// Local workbook catalog. Filters never change the saved corpus search or its evidence.
const priorityView=se('section');priorityView.id='view-priorities';priorityView.hidden=true;priorityView.dataset.noI18n='';main.append(priorityView);
let priorityResult=null,priorityEnvelope=null,priorityTimer=null,priorityRunBusy=false,prioritySelected='',priorityPage=0,priorityMode=['list','graph','balance','map'].includes(new URLSearchParams(location.search).get('mode'))?new URLSearchParams(location.search).get('mode'):'list';
const priorityEmptyFilters=()=>({refs:[],kind:[],sheet:[],quality:[],version:[],folder:[],document:[],priority:[],presence:''});
let priorityFilters=priorityEmptyFilters(),priorityFilterRefreshers=[];
const priorityCategorySelection=new Set();
const priorityKinds={person:'Personas',surname:'Apellidos / familias',place:'Lugares'};
let priorityFacetStamp='',priorityFacetCache={},priorityFilterLabels=new Map();
const priorityUI={combinationsOpen:false,catalogOpen:false,catalogQuery:'',sort:'relevance'};
const priorityModes=[
 ['list','Páginas','Lee los fragmentos, comprueba la fuente y marca lo relevante.','Fragmentos y fuentes'],
 ['balance','Cruces y balance','Compara personas, lugares, documentos y tipos de coincidencia.','Coincidencias y recuentos'],
 ['map','Mapa de lugares','Localiza las menciones y abre sus páginas de origen.','Ubicación de menciones'],
 ['graph','Grafo de referencias','Explora cómo se distribuyen los referentes entre las fuentes.','Referentes por documento']
];
function priorityFocus(id){const el=document.getElementById(id);if(el){el.style.scrollMarginTop=((document.getElementById('priority-applied-filters')?.offsetHeight||0)+24)+'px';el.tabIndex=-1;el.focus({preventScroll:true});el.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'})}}
function priorityReset(){priorityFilters=priorityEmptyFilters();prioritySelected='';priorityCategorySelection.clear();priorityPage=0;priorityUI.catalogQuery='';Object.assign(placeMapFilters,{category:'',query:'',includeEmpty:false});Object.assign(balanceState,{group:'',scene:'people_places',focus:'',includeOverlap:false,closeNames:true});placeMapBounds=null;priorityBuild();priorityFocus('priority-structured-filters')}
function prioritySetMode(mode){priorityMode=mode;priorityPage=0;prioritySyncURL('analysis');priorityDraw()}
function priorityChooseCategories(keys){priorityCategorySelection.clear();keys.forEach(key=>priorityCategorySelection.add(key));priorityPage=0;priorityDraw()}
function priorityHasFilters(){return priorityAppliedItems().length>0}
function prioritySortedPages(pages){return [...pages].sort(priorityUI.sort==='document'?(a,b)=>a.document.localeCompare(b.document)||a.page-b.page:priorityPageCompare)}
function priorityFacets(){
 if(!priorityResult)return {};const sources=prioritySourceInventory(),signature=JSON.stringify([priorityResult.created,priorityFilters,[...priorityCategorySelection],prioritySelected,sources.map(s=>s.document)]);
 if(signature!==priorityFacetStamp){priorityFacetStamp=signature;priorityFacetCache=PriorityBalance.facetValues(priorityResult.catalog.entities,priorityResult.pages,priorityFilters,{categories:[...priorityCategorySelection],focus:prioritySelected,sources})}return priorityFacetCache;
}
function priorityAvailable(key,value,kind=''){return !!priorityFacets()[kind?key+':'+kind:key]?.has(value)}
const priorityCategoryLabels={1:'Solo nombres completos',2:'Solo apellidos',4:'Solo lugares',3:'Nombres y apellidos',5:'Nombres y lugares',6:'Apellidos y lugares',7:'Nombres, apellidos y lugares',distant:'Solo palabras de nombres separadas'};
function priorityAppliedItems(){
 const items=[];for(const [key,value] of Object.entries(priorityFilters))for(const item of Array.isArray(value)?value:value?[value]:[]){const info=priorityFilterLabels.get(key+':'+item)||{title:'Disponibilidad de hallazgos',label:item==='yes'?'Con hallazgos':item==='no'?'Sin hallazgos':item};items.push({...info,key:key+':'+item,remove:()=>{priorityFilters[key]=Array.isArray(priorityFilters[key])?priorityFilters[key].filter(v=>v!==item):''}})}
 for(const category of priorityCategorySelection)items.push({title:'Cruce',label:priorityCategoryLabels[category],key:'category:'+category,remove:()=>priorityCategorySelection.delete(category)});
 if(prioritySelected)items.push({title:'En foco',label:priorityResult.catalog.entities.find(e=>e.id===prioritySelected)?.label||prioritySelected,data:true,key:'focus',remove:()=>prioritySelected=''});
 if(priorityMode==='map'){
  if(placeMapFilters.query)items.push({title:'Mapa · texto',label:placeMapFilters.query,data:true,key:'map-query',remove:()=>placeMapFilters.query=''});
  if(placeMapFilters.category)items.push({title:'Mapa · ubicación',label:geoStatuses[placeMapFilters.category],key:'map-category',remove:()=>placeMapFilters.category=''});
  if(placeMapFilters.includeEmpty)items.push({title:'Mapa',label:'Mostrar lugares sin menciones en estos filtros',key:'map-empty',remove:()=>placeMapFilters.includeEmpty=false});
 }
 if(priorityMode==='balance'){
  if(balanceState.scene==='together'&&balanceState.focus)items.push({title:'Matriz · comparar con',label:priorityResult.catalog.entities.find(e=>e.id===balanceState.focus)?.label||balanceState.focus,data:true,key:'balance-focus',remove:()=>{balanceState.scene='distribution';balanceState.focus=''}});
  if(balanceState.group)items.push({title:'Matriz · evidencia',label:balanceNames[balanceState.group],key:'balance-group',remove:()=>balanceState.group=''});
  if(!balanceState.closeNames)items.push({title:'Matriz',label:'Incluir nombres separados',key:'balance-close',remove:()=>balanceState.closeNames=true});
  if(balanceState.includeOverlap)items.push({title:'Matriz',label:'Incluir coincidencias que usan las mismas palabras',key:'balance-overlap',remove:()=>balanceState.includeOverlap=false});
 }
 return items;
}
function priorityRefreshApplied(){
 const items=priorityAppliedItems();for(const host of document.querySelectorAll('.priority-applied-panel')){const chips=host.querySelector('.priority-filter-chips');chips.replaceChildren();host.querySelector('strong').textContent=items.length?'Filtros aplicados · '+items.length:'Filtros aplicados';
 const empty=host.querySelector('p');empty.hidden=!!items.length;empty.textContent='Sin filtros aplicados. Estás explorando todos los resultados.';host.querySelector('.priority-reset').disabled=!items.length;
 for(const item of items){const chip=se('span'),caption=se('span');caption.append(se('span',item.title),document.createTextNode(': '),item.data?seData('span',item.label):se('span',item.label));chip.append(caption);const remove=priorityButton('×',()=>{item.remove();priorityPage=0;priorityDraw()});remove.dataset.priorityFocus='chip-'+item.key;remove.setAttribute('aria-label','Quitar filtro '+item.title+': '+item.label);chip.append(remove);chips.append(chip)}}
}
function priorityAppliedPanel(id='priority-applied-filters'){const active=se('section');active.id=id;active.className='priority-filter-active priority-applied-panel';active.setAttribute('aria-label','Filtros aplicados');const title=se('strong','Filtros aplicados');title.setAttribute('role','status');const chips=se('div');chips.className='priority-filter-chips';const clear=priorityButton('Quitar todos',priorityReset);clear.className='priority-reset';clear.dataset.priorityFocus='clear-all';active.append(title,clear,chips,se('p'));return active}
function priorityModeIcon(mode){
 const paths={
  list:['M14 3H5v18h14V8z','M14 3v5h5M8 12h8M8 16h6'],
  balance:['M3 4h18v16H3z','M3 9h18M3 14h18M9 4v16M15 4v16'],
  map:['M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z','M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
  graph:['M7.5 6.5l8 3M7 8l2 8M16 12l-5 5','M8 5a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM22 11a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM13 19a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z']
 };
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('priority-mode-icon');
 for(const [key,value]of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',focusable:'false'}))svg.setAttribute(key,value);
 for(const d of paths[mode]){const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',d);svg.append(path)}return svg;
}
function priorityToolbar(){
 const host=se('div');host.className='priority-toolbar';const modes=se('div');modes.className='priority-view-switch';modes.setAttribute('role','group');modes.setAttribute('aria-label','Cómo explorar los resultados');
 for(const [mode,label,description,summary] of priorityModes){const button=priorityButton('',()=>prioritySetMode(mode)),copy=se('span'),hint=se('small',summary);copy.className='priority-mode-copy';hint.id='priority-mode-summary-'+mode;copy.append(se('strong',label),hint);button.append(priorityModeIcon(mode),copy);button.dataset.priorityMode=mode;button.dataset.priorityFocus='mode-'+mode;button.title=description;button.setAttribute('aria-label',label);button.setAttribute('aria-describedby',hint.id);button.setAttribute('aria-controls','priority-results');modes.append(button)}
 const exports=se('details');exports.className='priority-exports';exports.append(se('summary','Exportar resultados'));const options=se('div');
 for(const [label,description,action] of [
  ['Mi selección y exportación','Solo las lecturas que marcaste como relevantes.',()=>showView('selection')],
  ['Exportar referencias filtradas CSV','Coincidencias de la vista actual, con sus fuentes.',()=>priorityCSV(priorityVisiblePages(),new Map(priorityResult.catalog.entities.map(e=>[e.id,e])))],
  ['Exportar balance general CSV','Todo el catálogo, incluidos los criterios sin hallazgos.',()=>priorityGeneralExport()],
  ['Descargar resultado completo JSON','Copia completa del análisis, sin aplicar filtros.',()=>priorityDownload(JSON.stringify(priorityResult,null,2),'referentes-completo.json','application/json')]
 ]){const button=priorityButton('',()=>{exports.open=false;action()});button.append(se('strong',label),se('small',description));options.append(button)}exports.append(options);exports.addEventListener('keydown',event=>{if(event.key==='Escape'){exports.open=false;exports.querySelector('summary').focus()}});host.append(modes,exports);return host;
}
function priorityVisiblePages(filtered=priorityFiltered()){
 let pages=filtered.pages;if(priorityCategorySelection.size){const combinations=PriorityBalance.pageCombinations(filtered.entities,pages);pages=PriorityBalance.materialize(PriorityBalance.combineRecords([...priorityCategorySelection].map(key=>key==='distant'?combinations.distant:combinations.combinations.get(key))))}if(prioritySelected)pages=pages.map(p=>({...p,versions:p.versions.filter(v=>v.matches.some(m=>m.entity===prioritySelected))})).filter(p=>p.versions.length);return prioritySortedPages(pages);
}
const priorityWorkspaceNav=se('nav');priorityWorkspaceNav.id='priority-workspace-nav';priorityWorkspaceNav.hidden=true;priorityWorkspaceNav.dataset.noI18n='';main.insertBefore(priorityWorkspaceNav,priorityCatalogView);
function priorityNavigationLabels(){return ({es:['Análisis cruzado','Criterios de búsqueda','Resultados'],en:['Cross analysis','Search criteria','Results'],fr:['Analyse croisée','Critères de recherche','Résultats']})[uiLanguage]||['Análisis cruzado','Criterios de búsqueda','Resultados']}
function priorityDrawSubnavigation(){
 const labels=priorityNavigationLabels();priorityWorkspaceNav.replaceChildren();priorityWorkspaceNav.setAttribute('aria-label',labels[0]);priorityWorkspaceNav.hidden=!['criteria','analysis'].includes(activeView);
 for(const [name,label] of [['analysis',labels[2]],['criteria',labels[1]]]){const b=priorityButton(label,()=>showView(name));b.setAttribute('aria-pressed',String(activeView===name));b.setAttribute('aria-controls',name==='criteria'?'view-criteria':'view-priorities');priorityWorkspaceNav.append(b)}
}
const priorityNav=drawNavigation;drawNavigation=function(){priorityNav();const b=priorityButton(priorityNavigationLabels()[0],()=>showView('analysis'));b.dataset.view='analysis';b.dataset.noI18n='';b.setAttribute('aria-pressed',String(['criteria','analysis'].includes(activeView)));nav.append(b);priorityDrawSubnavigation()};
function prioritySyncURL(name){const url=new URL(location.href);if(['criteria','analysis'].includes(name)){url.searchParams.set('view',name);if(name==='analysis')url.searchParams.set('mode',priorityMode);else url.searchParams.delete('mode')}else if(['criteria','analysis','priorities'].includes(url.searchParams.get('view'))){url.searchParams.delete('view');url.searchParams.delete('mode')}history.replaceState(null,'',url)}
const priorityShow=showView;showView=function(name){if(name==='priorities')name='analysis';priorityShow(name);priorityView.hidden=name!=='analysis';priorityCatalogView.hidden=name!=='criteria';prioritySyncURL(name);if(name==='criteria'){priorityCatalogLoad();priorityLoad()}else if(name==='analysis'){if(!priorityView.children.length)priorityBuild();priorityLoad()}};
function priorityButton(label,fn){const b=se('button',label);b.type='button';b.onclick=fn;return b}
function priorityVersion(v){return v==='original'?'Original':v==='human'?'Edición humana':'Segunda lectura · '+v.split(':')[1]}
function priorityNormalize(s){return s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase()}
function priorityPageRelevance(page){return PriorityBalance.relevance(page.versions.flatMap(v=>v.matches),new Map(priorityResult.catalog.entities.map(e=>[e.id,e])))}
function priorityPageCompare(a,b){return priorityPageRelevance(a)-priorityPageRelevance(b)||a.document.localeCompare(b.document)||a.page-b.page}
function priorityPageLabel(page){return ['Nombre completo literal','Nombre completo: variante explícita','Nombre y apellido cercanos','Nombre completo aproximado: revisar','Menciones de apellidos o lugares','Pistas de apellidos o lugares','Solo palabras separadas: no identifica a la persona'][priorityPageRelevance(page)]||''}
function priorityCombinationMetrics(entities,pages){
 const host=document.getElementById('priority-combinations');if(!host)return;host.replaceChildren();const data=PriorityBalance.pageCombinations(entities,pages);
 const shortcuts=se('div');shortcuts.className='priority-shortcuts';shortcuts.append(se('strong','Cruces rápidos'));
 for(const [keys,label] of [[[],'Todas las menciones'],[[5,7],'Personas + lugares'],[[6,7],'Apellidos + lugares']]){
  const button=priorityButton(label,()=>priorityChooseCategories(keys));button.dataset.priorityFocus='quick-'+(keys.join('-')||'all');button.setAttribute('aria-pressed',String(keys.length===priorityCategorySelection.size&&keys.every(k=>priorityCategorySelection.has(k))));shortcuts.append(button)
 }host.append(shortcuts);
 const details=se('details');details.className='priority-combination-details';details.open=priorityUI.combinationsOpen;details.ontoggle=()=>priorityUI.combinationsOpen=details.open;const summary=se('summary',priorityCategorySelection.size?'Combinaciones de menciones · '+priorityCategorySelection.size+' seleccionadas':'Más combinaciones de menciones');summary.dataset.priorityFocus='combinations';details.append(summary,se('p','Elige varias categorías para reunir sus páginas. Un cruce requiere menciones distintas en una misma lectura; no confirma una relación histórica.'));host.append(details);
 const cards=se('div');cards.className='priority-metrics priority-combination-cards';
 for(const [mask,label] of [[1,'Solo nombres completos'],[2,'Solo apellidos'],[4,'Solo lugares'],[3,'Nombres y apellidos'],[5,'Nombres y lugares'],[6,'Apellidos y lugares'],[7,'Nombres, apellidos y lugares'],['distant','Solo palabras de nombres separadas']]){
  const record=mask==='distant'?data.distant:data.combinations.get(mask),n=PriorityBalance.count(record);if(mask==='distant'&&!n.pages&&!priorityCategorySelection.has(mask))continue;
  const button=priorityButton('',()=>{if(priorityCategorySelection.has(mask))priorityCategorySelection.delete(mask);else priorityCategorySelection.add(mask);priorityPage=0;priorityDraw()});button.className='priority-combination-card';button.dataset.priorityFocus='category-'+mask;button.setAttribute('aria-label',label+' · '+n.pages+' páginas');button.setAttribute('aria-pressed',String(priorityCategorySelection.has(mask)));button.append(se('strong',n.pages),se('span',label));cards.append(button)
 }details.append(cards);
 if(priorityCategorySelection.size){const clear=priorityButton('Quitar selección de categorías',()=>priorityChooseCategories([]));clear.dataset.priorityFocus='clear-categories';details.append(clear)}
 details.append(se('p','Cada página se cuenta una vez en la lista. Puede pertenecer a varias categorías si sus lecturas difieren. El apellido dentro de un nombre completo no cuenta como mención independiente. “Solo” se refiere a los tipos visibles con los filtros actuales.'));
 return data;
}
async function priorityLoad(){
 clearTimeout(priorityTimer);
 try{const r=await fetch('/priorities?t='+Date.now(),{cache:'no-store'});const value=await r.json();if(!r.ok)throw Error(value.error||'No se pudo leer la búsqueda');priorityEnvelope=value;document.getElementById('priority-retry')?.remove();
  if(!priorityResult||priorityResult.created!==value.result?.created||!priorityView.children.length){priorityResult=value.result;priorityBuild()}
  priorityStatus();if(value.job.running||['criteria','analysis'].includes(activeView))priorityTimer=setTimeout(priorityLoad,value.job.running?1500:5000);
 }catch(error){if(!priorityView.children.length)priorityView.append(se('h1','Resultados del análisis cruzado'));let errorBox=priorityView.querySelector('#priority-status');if(!errorBox){errorBox=se('p');errorBox.id='priority-status';priorityView.append(errorBox)}errorBox.textContent=error.message;errorBox.classList.add('priority-warning');if(!document.getElementById('priority-retry')){const retry=priorityButton('Volver a intentar',priorityLoad);retry.id='priority-retry';errorBox.after(retry)}const catalogStatus=document.getElementById('catalog-search-status');if(catalogStatus)catalogStatus.textContent=error.message}
}
function priorityStatus(){
 priorityCatalogUpdateStatus();const status=document.getElementById('priority-status');if(!status)return;
 const job=priorityEnvelope?.job||{};
 status.textContent=priorityCatalogDraft.size?'Hay cambios en criterios pendientes de guardar. Estos resultados corresponden a la revisión anterior.':job.running?`Recorriendo el corpus: ${job.processed} / ${job.total||'…'} páginas.${job.pending_revision?' Hay cambios guardados pendientes; se recalcularán automáticamente.':''} ${priorityResult?'Puedes consultar el resultado anterior mientras termina.':'Los resultados aparecerán al terminar.'}`:
  job.error?'No se pudo actualizar: '+job.error:priorityEnvelope?.stale?'Hay nuevas correcciones o fuentes: actualizando las coincidencias.':priorityResult?'Resultado del '+new Date(priorityResult.created*1000).toLocaleString((uiLanguage==='fr'?'fr-CA':uiLanguage==='en'?'en-CA':'es-CO'),{timeZone:'America/Bogota'})+' · revisión '+priorityResult.catalog.revision+' de los criterios.':'Todavía no hay resultados. Recalcula desde Criterios de búsqueda, en Análisis cruzado.';
 status.classList.toggle('priority-warning',!!(priorityCatalogDraft.size||job.error||priorityEnvelope?.stale));
}
async function priorityRun(){
 if(priorityRunBusy||priorityEnvelope?.job.running)return;priorityRunBusy=true;priorityCatalogUpdateStatus();
 try{const r=await fetch('/priorities-run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const job=await r.json();if(!r.ok)throw Error(job.error||'No se pudo iniciar');priorityEnvelope={...priorityEnvelope,job};await priorityLoad()}
 catch(e){for(const id of ['priority-status','catalog-notice']){const status=document.getElementById(id);if(status)status.textContent=e.message}}
 finally{priorityRunBusy=false;priorityCatalogUpdateStatus()}
}
function prioritySourceInventory(){return [...(priorityResult?.pages||[]),...(state?.documents||[]).map(d=>({document:d.source,folder:d.folder}))]}
function priorityBuildFilters(){
 const r=priorityResult,filters=se('section');filters.id='priority-structured-filters';priorityFilterRefreshers=[];
 const live=se('p');live.id='priority-filter-live';live.setAttribute('role','status');live.setAttribute('aria-live','polite');filters.append(se('h2','¿Qué quieres encontrar?'),se('p','Elige nombres, apellidos o lugares. Puedes combinar varias opciones y explorar sus coincidencias.'));
 priorityFilterLabels=new Map();
 function changed(){priorityPage=0;priorityDraw()}
 function picker(parent,title,key,options,searchable=false,kind=''){
  const box=se('details');box.className='priority-filter-picker';const summary=se('summary');box.append(summary);parent.append(box);
  for(const option of options)priorityFilterLabels.set(key+':'+option.value,{title:option.prefix||title,label:option.label,data:['refs','folder','document','sheet'].includes(key)});
  const panel=se('div');panel.className='priority-filter-options';box.append(panel);let query='';
  const search=se('input');if(searchable){search.type='search';search.placeholder='Encontrar una opción…';search.setAttribute('aria-label','Buscar en '+title);panel.append(search)}
  const actions=se('div');actions.className='priority-filter-tools';panel.append(actions);const list=se('div');list.className='priority-filter-list';panel.append(list);const rows=[];
  const compatible=option=>priorityAvailable(key,option.value,kind),matches=option=>(compatible(option)||priorityFilters[key].includes(option.value))&&(!query||priorityNormalize([option.label,option.detail||'',option.search||''].join(' ')).includes(query));
  const all=priorityButton('Seleccionar visibles',()=>{priorityFilters[key]=[...new Set([...priorityFilters[key],...options.filter(o=>matches(o)&&compatible(o)).map(o=>o.value)])];changed()});all.setAttribute('aria-label','Seleccionar opciones visibles de '+title);
  const clear=priorityButton('Quitar selección',()=>{const own=new Set(options.map(o=>o.value));priorityFilters[key]=priorityFilters[key].filter(value=>!own.has(value));changed()});clear.setAttribute('aria-label','Quitar selección de '+title);actions.append(all,clear);
  for(const option of options){const row=se('label');row.className='priority-filter-option';const check=se('input');check.type='checkbox';check.setAttribute('aria-label',title+': '+option.label);const text=se('span');text.append(['refs','folder','document','sheet'].includes(key)?seData('span',option.label):se('span',option.label));if(option.aliases){const detail=se('small');detail.append(se('span',option.priority));if(option.aliases.length)detail.append(se('span',' · Sinónimos: '),seData('span',option.aliases.join(' · ')));text.append(detail)}else if(option.detail)text.append(se('small',option.detail));row.append(check,text);list.append(row);rows.push({row,check,option});check.onchange=()=>{priorityFilters[key]=check.checked?[...new Set([...priorityFilters[key],option.value])]:priorityFilters[key].filter(value=>value!==option.value);changed()}}
  const empty=se('p','No hay opciones con ese texto.');empty.className='priority-filter-empty';list.append(empty);
  function refresh(){const selected=options.filter(o=>priorityFilters[key].includes(o.value));summary.replaceChildren(se('strong',title),se('span',selected.length?selected.length+' seleccionados':options.filter(compatible).length+' disponibles'));clear.disabled=!selected.length;const visible=rows.filter(item=>matches(item.option)&&compatible(item.option));all.disabled=!visible.length||visible.every(item=>priorityFilters[key].includes(item.option.value));for(const item of rows){item.check.checked=priorityFilters[key].includes(item.option.value);item.row.hidden=!matches(item.option);item.row.classList.toggle('priority-filter-conflict',item.check.checked&&!compatible(item.option));item.row.title=item.check.checked&&!compatible(item.option)?'Sin coincidencias con los demás filtros. Puedes quitar esta opción.':''}empty.textContent=query?'No hay opciones con ese texto.':'No hay opciones compatibles con los demás filtros.';empty.hidden=rows.some(item=>!item.row.hidden)}
  if(searchable)search.oninput=()=>{query=priorityNormalize(search.value.trim());refresh()};priorityFilterRefreshers.push(refresh);refresh();
 }
 const references=se('div');references.className='priority-reference-filters';filters.append(references);
 for(const [kind,title,singular] of [['person','Nombres completos','Nombre'],['surname','Apellidos / familias','Apellido'],['place','Lugares','Lugar']]){
  const options=r.catalog.entities.filter(e=>e.enabled!==false&&e.kind===kind).sort((a,b)=>a.label.localeCompare(b.label)).map(e=>{const aliases=[...new Set((e.patterns||[]).filter(p=>p.origin==='alias').map(p=>p.label))];return {value:e.id,label:e.label,priority:e.priority,aliases,detail:e.priority+(aliases.length?' · Sinónimos: '+aliases.join(' · '):''),search:aliases.join(' '),prefix:singular}});
  picker(references,title,'refs',options,true,kind);
 }

 const advanced=se('details');advanced.className='priority-more-filters';advanced.append(se('summary','Afinar por prioridad, fuente o tipo de coincidencia'));const facets=se('div');facets.className='priority-facet-filters';advanced.append(facets);filters.append(advanced);
 const options=items=>items.map(([value,label])=>({value,label}));
 picker(facets,'Tipo de referente','kind',options([['person','Nombres completos'],['surname','Apellidos / familias'],['place','Lugares']]));
 picker(facets,'Prioridad','priority',options(['Alta','Media','Baja'].map(x=>[x,x])));
 picker(facets,'Procedencia','sheet',options([...r.catalog.sheets.map(s=>[s.name,s.name]),['user','Añadidos en la app']]));
 picker(facets,'Coincidencia','quality',options(Object.entries(r.quality_labels).map(([value,label])=>[value,label.replace('del Excel','del catálogo')])));
 picker(facets,'Lectura','version',options([['original','Original'],['human','Edición humana'],['secondary','Segundas lecturas']]));
 const sourceFacets=PriorityBalance.sourceFacets(prioritySourceInventory());
 picker(facets,'Carpeta','folder',options(sourceFacets.folders.map(x=>[x,x])),true);
 picker(facets,'Documento','document',options(sourceFacets.documents.map(x=>[x,x])),true);
 const presence=se('label','Disponibilidad de hallazgos'),select=se('select');select.setAttribute('aria-label','Disponibilidad de hallazgos');for(const [value,label] of [['','Con y sin hallazgos'],['yes','Con hallazgos'],['no','Sin hallazgos']]){const option=se('option',label);option.value=value;select.append(option)}select.value=priorityFilters.presence;select.onchange=()=>{priorityFilters.presence=select.value;changed()};presence.append(select);facets.append(presence);priorityFilterRefreshers.push(()=>{select.value=priorityFilters.presence;for(const option of select.options)option.disabled=!!option.value&&option.value!==select.value&&!priorityAvailable('presence',option.value)});const help=se('details');help.className='priority-filter-help';help.append(se('summary','Cómo se combinan los filtros'),se('p','Las opciones de cada lista se ajustan a los demás filtros. Puedes elegir varias dentro de una lista. Si combinas nombres, apellidos y lugares, deben aparecer en una misma lectura. Las selecciones sin coincidencias se conservan para que puedas quitarlas.'));advanced.append(help);
 filters.append(live);
 priorityView.insertBefore(filters,document.getElementById('priority-combinations'));
}
function priorityBuild(){
 priorityView.replaceChildren();const top=se('div');top.className='priority-heading';const title=se('div');title.append(se('p','EXPLORA · COMPRUEBA · SELECCIONA'),se('h1','Análisis cruzado'),se('p','Encuentra personas y lugares en tus documentos y reúne la evidencia que necesitas.'));top.append(title);
 const actions=se('div');actions.className='priority-actions';const selection=priorityButton('Mi selección y exportación →',()=>showView('selection'));selection.className='priority-primary';const selected=se('span');selected.dataset.matrixCount='';actions.append(selection,selected);top.append(actions);priorityView.append(top);
 const journey=se('ol');journey.className='priority-journey';for(const [label,detail,action] of [
  ['Elige qué buscar','Nombres, apellidos y lugares',()=>priorityFocus('priority-structured-filters')],
  ['Comprueba las fuentes','Abre la imagen y su transcripción',()=>priorityFocus('priority-results')],
  ['Reúne tu evidencia','Marca, revisa y exporta',()=>showView('selection')]
 ]){const item=se('li'),button=priorityButton('',action);button.append(se('strong',label),se('small',detail));item.append(button);journey.append(item)}priorityView.append(journey);
 const status=se('p');status.id='priority-status';status.setAttribute('role','status');priorityView.append(status);
 if(!priorityResult){const empty=se('div');empty.className='priority-empty';empty.append(se('h2',priorityEnvelope?.job?.running?'Actualizando las coincidencias…':priorityEnvelope?'Prepara tu primer análisis':'Cargando el análisis…'),se('p',priorityEnvelope?.job?.running?'Estamos aplicando la búsqueda de nombres y lugares completos. Los resultados aparecerán al terminar.':priorityEnvelope?'Añade los nombres, apellidos y lugares que quieres buscar. Después podrás explorar sus coincidencias aquí.':'Estamos consultando las coincidencias disponibles.'));
  if(priorityEnvelope)empty.append(priorityButton('Ir a criterios de búsqueda',priorityCatalogOpen));priorityView.append(empty);priorityStatus();matrixPersist();return}
 const r=priorityResult,c=r.coverage;if(r.search_policy?.full_terms_only){const policy=se('p','Nombres y lugares completos · máximo 2 palabras intermedias · sin cruzar párrafos');policy.className='priority-policy';priorityView.append(policy)}priorityView.append(priorityToolbar());const modeHint=se('p');modeHint.id='priority-mode-hint';priorityView.append(modeHint,priorityAppliedPanel());
 const metrics=se('div');metrics.id='priority-combinations';priorityView.append(metrics);
 const coverage=se('details');coverage.className='priority-method';coverage.append(se('summary','Sobre este análisis: cobertura y método'),se('p',`Corpus completo: ${r.catalog.active_count??r.catalog.entities.length} referentes activos · ${c.searched_pages} / ${c.inventory_pages} páginas recorridas · ${r.summary.entities_without_hits} referentes sin hallazgos.`));coverage.append(se('p',`${c.documents} documentos · ${c.versions} lecturas: `+Object.entries(c.by_version).map(([v,n])=>priorityVersion(v)+' '+n).join(' · ')),se('p','Se recorren todas las páginas del inventario y todas sus lecturas disponibles, sin un límite de resultados. Las ediciones humanas se buscan además del original. Se conserva la última edición de cada página; no se recorren revisiones históricas reemplazadas.'),se('p','Se normalizan mayúsculas y acentos, y se unen palabras cortadas por un guion al final de línea. También se buscan palabras unidas o separadas por errores de escritura (LaSarre / La Sarre); se marcan como candidatas. Los nombres completos y lugares compuestos admiten hasta dos palabras intermedias en total, dentro de un mismo párrafo. Se conservan las variantes explícitas del catálogo y las aproximaciones de escritura de la frase completa. No se buscan abreviaturas ni denominaciones incompletas generadas automáticamente.'),se('p','Las aproximaciones admiten 1 edición para palabras de 4–7 letras y hasta 2 para palabras de 8 o más, con similitud mínima de 0,82; las palabras cortas se buscan exactas. El nombre y el apellido alejados o en párrafos diferentes no se consideran coincidencias. Los ID y traplines sirven solo de referencia interna y no son términos de búsqueda.'),se('p','Un apellido no confirma la identidad de una persona. Las anclas geográficas y los nombres de lugar sin parte de su denominación no se cuentan como coincidencias, salvo que sean variantes explícitas del catálogo. No encontrar texto no demuestra ausencia en la imagen original. La numeración corresponde a páginas del PDF, no a folios manuscritos.'),se('p',`Sin texto: ${c.missing_pages.length} páginas · errores de lectura: ${c.errors.length}.`));
 if(c.missing_pages.length||c.errors.length){const pre=se('pre',JSON.stringify({sin_texto:c.missing_pages,errores:c.errors},null,2));coverage.append(pre)}if(r.changed_during_run)coverage.append(se('p','El corpus cambió durante el recorrido; actualiza para obtener un corte consistente.'));
 priorityBuildFilters();
 const browse=se('details');browse.className='priority-catalog-browser';browse.open=priorityUI.catalogOpen;browse.ontoggle=()=>priorityUI.catalogOpen=browse.open;const browseTitle=se('summary','Explorar un referente del catálogo');browseTitle.dataset.priorityFocus='catalog-toggle';browse.append(browseTitle);const catalog=se('aside');catalog.id='priority-catalog';browse.append(catalog);priorityView.append(browse);
 const body=se('div');body.className='priority-body';const results=se('div');results.id='priority-results';body.append(results);priorityView.append(body,coverage);priorityDraw();priorityStatus();matrixPersist();
}
function priorityEvidencePages(valid=null){const scope=PriorityBalance.filterScope(priorityResult.catalog.entities,priorityResult.pages,priorityFilters);return valid?PriorityBalance.filterEvidence(scope.pages,{},valid):scope.pages}
function priorityFiltered(){
 const {entities,pages}=PriorityBalance.filterScope(priorityResult.catalog.entities,priorityResult.pages,priorityFilters),counts=new Map(entities.map(e=>[e.id,new Set()]));
 for(const p of pages)for(const v of p.versions)for(const m of v.matches)counts.get(m.entity)?.add(PriorityBalance.pageKey(p));
 return {entities,counts:new Map([...counts].map(([id,keys])=>[id,keys])),pages:prioritySortedPages(pages),evidenceStats:PriorityBalance.analyze(entities,pages).stats};
}
function priorityDraw(){
 const active=document.activeElement,key=active?.dataset.priorityFocus,start=active?.selectionStart,end=active?.selectionEnd;
 try{priorityDrawContent()}finally{if(key&&!active.isConnected){const replacement=[...priorityView.querySelectorAll('[data-priority-focus]')].find(el=>el.dataset.priorityFocus===key);if(!replacement)document.querySelector('#priority-applied-filters .priority-reset')?.focus({preventScroll:true});if(replacement){replacement.focus({preventScroll:true});if(typeof start==='number'&&replacement.setSelectionRange)replacement.setSelectionRange(start,end)}}}
}
function priorityDrawContent(){
 priorityFilterRefreshers.forEach(refresh=>refresh());priorityRefreshApplied();
 const catalog=document.getElementById('priority-catalog'),results=document.getElementById('priority-results');if(!catalog)return;catalog.replaceChildren();results.replaceChildren();catalog.parentElement.hidden=['balance','map'].includes(priorityMode);
 const filtered=priorityFiltered(),{entities,counts,evidenceStats}=filtered,byId=new Map(priorityResult.catalog.entities.map(e=>[e.id,e]));priorityCombinationMetrics(entities,filtered.pages);const pages=priorityVisiblePages(filtered);
 priorityView.querySelectorAll('[data-priority-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.priorityMode===priorityMode)));document.getElementById('priority-mode-hint').textContent=priorityModes.find(([mode])=>mode===priorityMode)[2];
 const catalogSearch=se('input');catalogSearch.type='search';catalogSearch.placeholder='Buscar en los referentes filtrados…';catalogSearch.setAttribute('aria-label','Buscar en los referentes filtrados');catalogSearch.dataset.priorityFocus='catalog-search';catalogSearch.value=priorityUI.catalogQuery;catalogSearch.oninput=()=>{priorityUI.catalogQuery=catalogSearch.value;priorityDraw()};catalog.append(catalogSearch);
 const all=priorityButton('Todos los referentes filtrados',()=>{prioritySelected='';priorityPage=0;priorityDraw()});all.className=prioritySelected?'':'chosen';all.dataset.priorityFocus='catalog-all';all.setAttribute('aria-pressed',String(!prioritySelected));catalog.append(all);
 const query=priorityNormalize(priorityUI.catalogQuery.trim());let shown=0;
 for(const kind of ['person','surname','place']){const group=entities.filter(e=>e.kind===kind&&(!query||priorityNormalize([e.label,...(e.patterns||[]).map(p=>p.label)].join(' ')).includes(query))).sort((a,b)=>a.label.localeCompare(b.label));if(!group.length)continue;shown+=group.length;catalog.append(se('h3',priorityKinds[kind]));for(const e of group){const button=priorityButton('',()=>{prioritySelected=e.id;priorityPage=0;priorityDraw()});button.dataset.priorityFocus='entity-'+e.id;button.append(seData('span',e.label),se('small',counts.get(e.id).size+' p.'));button.className=prioritySelected===e.id?'chosen':'';button.setAttribute('aria-pressed',String(prioritySelected===e.id));catalog.append(button)}}
 if(!shown)catalog.append(se('p','No hay opciones con ese texto.'));
 const documentCount=new Set(pages.map(p=>p.document_id)).size,live=document.getElementById('priority-filter-live');if(live)live.textContent=`Páginas: ${pages.length} · Documentos: ${documentCount} · Referentes: ${entities.length}`;
 const entity=byId.get(prioritySelected)||(entities.length===1?entities[0]:null);const heading=se('div');heading.className='priority-results-heading';heading.append(entity?seData('h2',entity.label):se('h2',priorityMode==='balance'?'Balance de coincidencias':priorityMode==='map'?'Menciones geográficas':priorityCategorySelection.size?'Páginas con el cruce elegido':'Páginas para explorar'));
 if(prioritySelected){const clear=priorityButton('Quitar foco del referente',()=>{prioritySelected='';priorityPage=0;priorityDraw()});clear.dataset.priorityFocus='clear-focus';heading.append(clear)}
 if(priorityMode==='list'){const order=se('label','Ordenar por'),select=se('select');select.setAttribute('aria-label','Ordenar páginas');select.dataset.priorityFocus='sort';for(const [value,label] of [['relevance','Mejor coincidencia'],['document','Documento y página']]){const option=se('option',label);option.value=value;select.append(option)}select.value=priorityUI.sort;select.onchange=()=>{priorityUI.sort=select.value;priorityPage=0;priorityDraw()};order.append(select);heading.append(order)}results.append(heading);
 if(entity&&priorityMode!=='balance'){results.append(se('p',priorityKinds[entity.kind]+(entity.priority?' · Prioridad '+entity.priority:'')+' · '+(entity.kind==='person'?(priorityResult.search_policy?.full_terms_only?entity.pages+' páginas con nombre completo':entity.near_pages+' páginas con nombre cercano · '+entity.distant_pages+' con nombre y apellido separados'):entity.pages+' páginas en el recorrido completo')));for(const note of entity.notes||[])results.append(seData('p',note));const details=se('details');details.className='priority-method';details.append(se('summary','Denominaciones y referencias del Excel'));for(const origin of ['canonical','alias','generated','context']){const ps=(entity.patterns||[]).filter(p=>p.origin===origin);if(ps.length)details.append(se('p',({canonical:'Del Excel',alias:'Variantes explícitas',generated:'Variantes automáticas no usadas en la búsqueda estricta',context:'Anclas geográficas no usadas en la búsqueda estricta'})[origin]+': '+ps.map(p=>p.label).join(' · ')))}for(const s of entity.sources||[])details.append(se('p',`${s.sheet} · fila ${s.row}: `+Object.entries(s.cells).filter(([k])=>!(entity.kind==='person'&&['A','D'].includes(k))).map(([k,v])=>k+s.row+' = '+v).join(' · ')));if(entity.fhid)details.append(se('p','Referencia interna: FHID '+entity.fhid+' · '+entity.traplines.join(', ')+' (no se buscan)'));results.append(details)}
 const summary=se('p',`Páginas: ${pages.length} · Documentos: ${documentCount}. Un hallazgo es una coincidencia de texto, no una identidad confirmada.`);summary.id='priority-result-count';results.append(summary);
 results.append(matrixBulkControls(pages,pages.slice(priorityPage*20,(priorityPage+1)*20)));
 if(priorityMode==='balance'){priorityBalanceRender(results,entities,pages,priorityCategorySelection.size||prioritySelected?pages:null);return}
 if(priorityMode==='map'){priorityMapRender(results,{entities,pages});return}
 if(!pages.length){const empty=se('div');empty.className='priority-empty';empty.append(se('h3','No encontramos páginas con esta combinación'),se('p','Prueba con menos filtros, otras categorías o variantes del nombre. No encontrar texto no demuestra ausencia en la imagen original.'));if(priorityHasFilters())empty.append(priorityButton('Limpiar filtros y ver todas las páginas',priorityReset));empty.append(priorityButton('Revisar criterios de búsqueda',priorityCatalogOpen));results.append(empty);return}
 if(priorityMode==='graph'){
  const folders=new Map(),hits=pages.map(p=>({...p,matches:p.versions.map(v=>({...v,approximate:v.matches.some(m=>!['literal','alias'].includes(m.quality)),criteria:[...new Set(v.matches.map(m=>m.entity))].map(id=>({label:byId.get(id).label,approximate:v.matches.filter(m=>m.entity===id).every(m=>!['literal','alias'].includes(m.quality))})),excerpts:priorityExcerpts(v.text,v.matches).slice(0,2)}))}));
  for(const hit of hits){if(!folders.has(hit.folder))folders.set(hit.folder,new Map());const docs=folders.get(hit.folder);if(!docs.has(hit.document))docs.set(hit.document,[]);docs.get(hit.document).push(hit)}
  renderSearchGraph(results,folders,summary,{data:{query:entity?entity.label:'Análisis cruzado',criteria:entity?[entity]:entities},openSource:(doc,page)=>prioritySource(pages.find(p=>p.document===doc&&p.page===page))});return
 }
 results.append(priorityColorLegend());const pageSize=20,total=Math.ceil(pages.length/pageSize);priorityPage=Math.max(0,Math.min(priorityPage,total-1));
 function pagination(position){const pager=se('nav');pager.className='priority-pagination';pager.setAttribute('aria-label','Navegación de páginas · '+position);
  const move=delta=>{priorityPage+=delta;priorityDraw();priorityFocus('priority-result-count')},back=priorityButton('← Anterior',()=>move(-1)),next=priorityButton('Siguiente →',()=>move(1));back.disabled=priorityPage===0;next.disabled=priorityPage===total-1;
  pager.append(back,se('span',`${priorityPage*pageSize+1}–${Math.min((priorityPage+1)*pageSize,pages.length)} de ${pages.length} páginas`),next);return pager}
 results.append(pagination('arriba'));const pageList=se('div');pageList.className='priority-page-list';results.append(pageList);
 for(const p of pages.slice(priorityPage*pageSize,(priorityPage+1)*pageSize)){
  const card=se('article');card.className='priority-page';card.append(seData('small',p.folder));const pageHeading=se('div');pageHeading.className='priority-page-heading';pageHeading.append(seData('h3',p.document.split('/').pop()),se('span','Página PDF '+p.page));card.append(pageHeading,se('p',priorityPageLabel(p)));const open=priorityButton('Comprobar fuente ↗',()=>prioritySource(p));open.className='priority-source-action';open.setAttribute('aria-label','Comprobar fuente: '+p.document+' · página '+p.page);card.append(open);
  const matches=p.versions.flatMap(v=>v.matches),labels=[...new Set(matches.map(m=>m.entity))].sort((a,b)=>PriorityBalance.relevance(matches.filter(m=>m.entity===a),byId)-PriorityBalance.relevance(matches.filter(m=>m.entity===b),byId)).map(id=>byId.get(id).label+(byId.get(id).kind==='person'&&matches.filter(m=>m.entity===id).every(m=>m.quality==='cooccurrence')?' (palabras separadas; identidad sin confirmar)':''));card.append(seData('p',labels.join(' · ')));
  for(const v of p.versions){const line=se('div');line.className='priority-version';line.append(se('strong',priorityVersion(v.version)+' · '+(v.status==='validated'?'validada':v.status==='stale'?'original cambiado: comparar':v.version==='human'?'borrador':'sin validación humana')),matrixToggle(p,v.version),se('p',[...new Set(v.matches.map(m=>priorityResult.quality_labels[m.quality]))].join(' · ')));const excerpts=priorityExcerpts(v.text,v.matches),first=excerpts[0];if(first){const quote=se('blockquote'),chars=Array.from(first.text),limit=420;quote.className='priority-preview';priorityHighlight(quote,chars.slice(0,limit).join('')+(chars.length>limit?'…':''),first.offsets.filter(([a])=>a<limit).map(([a,b,kind])=>[a,Math.min(b,limit),kind]));line.append(quote);if(excerpts.length>1||chars.length>limit){const full=se('details');full.className='priority-all-excerpts';full.append(se('summary','Ver todos los fragmentos · '+excerpts.length));for(const ex of excerpts){const quote=se('blockquote');priorityHighlight(quote,ex.text,ex.offsets);full.append(quote)}line.append(full)}};card.append(line)}pageList.append(card)
 }results.append(pagination('abajo'));matrixPersist();
}
function priorityRanges(matches){return PriorityBalance.typedRanges(matches,new Map(priorityResult.catalog.entities.map(e=>[e.id,e.kind])))}
function priorityHighlight(el,text,ranges){uiData(el);const chars=Array.from(text);let end=0;for(const [a,b,kind] of ranges){const mark=se('mark',chars.slice(a,b).join(''));if(kind){mark.dataset.entityKind=kind;mark.title=priorityKinds[kind]}el.append(document.createTextNode(chars.slice(end,a).join('')),mark);end=b}el.append(document.createTextNode(chars.slice(end).join('')))}
function priorityColorLegend(){const legend=se('div');legend.className='priority-color-legend';legend.append(se('span','Colores del texto:'));for(const [kind,label] of [['person','Persona específica'],['surname','Apellido / familia'],['place','Lugar']]){const item=se('mark',label);item.dataset.entityKind=kind;legend.append(item)}return legend}
function priorityExcerpts(text,matches){const chars=Array.from(text),ranges=priorityRanges(matches),blocks=[];for(const [a,b] of ranges){const start=Math.max(0,a-70),end=Math.min(chars.length,b+110);if(blocks.length&&start<=blocks.at(-1)[1])blocks.at(-1)[1]=Math.max(end,blocks.at(-1)[1]);else blocks.push([start,end])}return blocks.map(([a,b])=>({text:chars.slice(a,b).join(''),offsets:ranges.filter(([s,e])=>a<=s&&e<=b).map(([s,e,kind])=>[s-a,e-a,kind])}))}
function prioritySource(page){
 if(!page)return;sourcePopup.replaceChildren();const byId=new Map(priorityResult.catalog.entities.map(e=>[e.id,e])),header=se('header');header.append(se('h2',page.document+' · página '+page.page),priorityButton('Cerrar',()=>sourcePopup.close()));sourcePopup.append(header,priorityColorLegend(),se('p','Copia de la transcripción usada en la búsqueda del '+new Date(priorityResult.created*1000).toLocaleString((uiLanguage==='fr'?'fr-CA':uiLanguage==='en'?'en-CA':'es-CO'),{timeZone:'America/Bogota'})+'. La imagen corresponde a la página PDF.'));
 if(priorityEnvelope.stale)sourcePopup.append(se('p','Hay cambios posteriores: actualiza la búsqueda antes de seleccionar esta lectura para un nuevo análisis.'));
 const tools=se('div');tools.className='source-popup-tools';const select=se('select');select.setAttribute('aria-label','Lectura del referente');page.versions.forEach((v,i)=>{const o=se('option',priorityVersion(v.version));o.value=i;select.append(o)});tools.append(select);const count=se('span');let index=0,marks=[],zoom=100;
 const panes=se('div');panes.className='source-popup-panes';const imageBox=se('div');imageBox.className='source-popup-image';const img=se('img');img.src='/page-image?'+new URLSearchParams({document:page.document_id,page:page.page});img.alt=page.document+' página '+page.page;img.onerror=()=>imageBox.replaceChildren(se('p','Imagen no disponible'));imageBox.append(img);const textBox=se('div');textBox.className='source-popup-text';panes.append(imageBox,textBox);
 const navigate=delta=>{if(!marks.length)return;index=(index+delta+marks.length)%marks.length;marks.forEach(m=>m.classList.remove('active'));marks[index].classList.add('active');count.textContent=(index+1)+' / '+marks.length+' resaltados';textBox.scrollTop+=marks[index].getBoundingClientRect().top-textBox.getBoundingClientRect().top-textBox.clientHeight/3};
 tools.append(priorityButton('← Coincidencia',()=>navigate(-1)),count,priorityButton('Coincidencia →',()=>navigate(1)));for(const [label,delta] of [['− Imagen',-20],['+ Imagen',20]])tools.append(priorityButton(label,()=>{zoom=Math.max(40,Math.min(300,zoom+delta));img.style.width=zoom+'%'}));sourcePopup.append(tools,panes);
 function paint(){textBox.replaceChildren();const v=page.versions[Number(select.value)];textBox.append(se('p',priorityVersion(v.version)+' · '+(v.status==='validated'?'Validada':v.status==='stale'?'El original cambió: comparar':v.version==='human'?'Borrador':'Sin validación humana')),matrixToggle(page,v.version));const reasons=se('details');reasons.append(se('summary',v.matches.length+' coincidencias: referentes y motivos'));for(const m of v.matches)reasons.append(se('p',byId.get(m.entity).label+' · '+priorityResult.quality_labels[m.quality]+' · '+(m.score??priorityResult.score_policy?.[m.quality]??'')+' puntos · buscado: '+m.alias+(m.approximate?' · aproximación de escritura':'')+(m.gap?' · '+m.gap+' palabras intermedias':'')+(m.reason?' · '+m.reason:'')));textBox.append(reasons);const pre=se('div');pre.className='source-popup-transcription';priorityHighlight(pre,v.text,priorityRanges(v.matches));textBox.append(pre);marks=[...pre.querySelectorAll('mark')];index=0;requestAnimationFrame(()=>navigate(0));matrixPersist()}
 select.onchange=paint;if(!sourcePopup.open)sourcePopup.showModal();paint();
}
function priorityDownload(data,name,type){const blob=new Blob([data],{type}),url=URL.createObjectURL(blob),a=se('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function priorityCSV(pages,byId){
 const rows=[['Referente','Tipo','Prioridad','Puntaje de la coincidencia','Hoja y fila Excel','Carpeta','Archivo','Página PDF','Lectura','Estado','Coincidencia','Término buscado','Texto encontrado','Motivo']];for(const p of pages)for(const v of p.versions)for(const m of v.matches){const e=byId.get(m.entity),chars=Array.from(v.text);rows.push([e.label,priorityKinds[e.kind],e.priority,m.score??priorityResult.score_policy?.[m.quality]??'',e.sources.map(s=>s.sheet+' fila '+s.row).join(' | '),p.folder,p.document,p.page,v.version,v.status,priorityResult.quality_labels[m.quality],m.alias,m.offsets.map(([a,b])=>chars.slice(a,b).join('')).join(' … '),m.reason])}const quote=value=>{let s=String(value);if(/^[=+@\-\t\r\n]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"'};priorityDownload('\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n'),'referentes-filtrados.csv','text/csv;charset=utf-8');
}
const priorityStyle=se('style');priorityStyle.textContent=`#priority-workspace-nav{display:flex;gap:8px;flex-wrap:wrap;max-width:1520px;margin:0 auto;padding:18px 26px 0}#priority-workspace-nav[hidden]{display:none}#priority-workspace-nav button{border-radius:8px 8px 0 0;padding:12px 18px}#priority-workspace-nav button[aria-pressed=true]{background:#111215;color:#fffefa;border-color:#111215}#priority-workspace-nav button:focus-visible{outline:2px solid #b64c26;outline-offset:3px}#view-priorities{padding:26px;max-width:1520px;margin:auto;overflow:visible;max-height:none}#view-priorities h1{font-size:32px;margin:10px 0}#view-priorities h2{font-size:22px;margin:12px 0}#view-priorities p{line-height:1.55;overflow-wrap:anywhere}#view-priorities button{white-space:normal;text-align:left}#view-priorities button[aria-pressed=true],#priority-catalog .chosen{background:#111215;color:#fffefa}#view-priorities mark{background:#ffe0a3;color:#111}.priority-heading{display:flex;justify-content:space-between;gap:26px}.priority-heading>div:first-child{max-width:780px}.priority-heading>div:first-child>p:first-child{font-size:11px;letter-spacing:1.7px;color:#a33b17}.priority-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:12px 0}.priority-heading .priority-actions{max-width:290px}.priority-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}.priority-metrics>div{padding:20px;border:1px solid var(--line);border-radius:10px;background:#fffefa;display:flex;flex-direction:column;gap:8px}.priority-metrics strong{font-size:28px}.priority-metrics span{font-size:13px}.priority-method{margin:16px 0;padding:14px;background:#f0ede5;border:1px solid var(--line);border-radius:8px}.priority-method summary{cursor:pointer;font-weight:600}.priority-method p{font-size:13px}.priority-method pre{white-space:pre-wrap;max-height:220px;overflow:auto}.priority-filters{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:14px;margin:24px 0;padding-bottom:22px;border-bottom:1px solid var(--line)}.priority-filters label{display:flex;flex-direction:column;gap:8px;font-size:12px}.priority-filters input,.priority-filters select{width:100%;min-width:0;box-sizing:border-box;padding:10px}.priority-filters>button{align-self:end}.priority-body{display:grid;grid-template-columns:300px minmax(0,1fr);gap:30px}#priority-catalog{max-height:80vh;overflow:auto;position:sticky;top:18px;padding-right:14px}#priority-catalog h3{font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-top:24px;color:#615c55}#priority-catalog button{width:100%;display:flex;justify-content:space-between;gap:12px;align-items:center;margin:4px 0;font-size:13px;background:transparent}#priority-catalog small{white-space:nowrap;font-size:11px}#priority-results{min-width:0}.priority-page{border:1px solid var(--line);border-radius:10px;background:#fffefa;padding:20px;margin:18px 0}.priority-page>small{display:block;color:#71695e;margin-bottom:8px}.priority-page>button{font-weight:700;font-size:17px}.priority-page>p{font-size:13px}.priority-version{padding-top:12px;margin-top:12px;border-top:1px solid var(--line)}.priority-version strong{font-size:12px}.priority-version p{font-size:12px;color:#60584f}.priority-version .matrix-select-label{margin:10px 0}.priority-version blockquote{margin:12px 0;padding-left:14px;border-left:2px solid #ef642f;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.6}.priority-warning{padding:12px;background:#fff0c2;border-left:3px solid #bc7020}#view-priorities .search-graph-viewport{height:540px}@media(max-width:1000px){.priority-body{grid-template-columns:230px minmax(0,1fr)}.priority-filters{grid-template-columns:repeat(2,1fr)}.priority-heading{display:block}.priority-heading .priority-actions{max-width:none}}@media(max-width:700px){#view-priorities{padding:16px}.priority-body{display:block}#priority-catalog{position:static;max-height:260px;margin-bottom:20px}.priority-metrics{grid-template-columns:repeat(2,1fr)}}`;document.head.append(priorityStyle);drawNavigation();
if(['priorities','analysis','criteria'].includes(new URLSearchParams(location.search).get('view')))showView(new URLSearchParams(location.search).get('view'));

const combinationStyle=se('style');combinationStyle.textContent=`
#priority-structured-filters{margin:22px 0;padding:20px;max-height:none;overflow:visible;background:#f7f5ef;border:1px solid var(--line);border-radius:10px}
#priority-structured-filters>p{font-size:12px;max-width:1100px}.priority-reference-filters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}.priority-facet-filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.priority-filter-picker{min-width:0;border:1px solid var(--line);border-radius:7px;background:#fffefa;align-self:start}.priority-filter-picker>summary{cursor:pointer;list-style-position:inside;padding:12px;font-size:12px}.priority-filter-picker>summary strong{font-weight:600}.priority-filter-picker>summary>span{display:block;color:#626368;margin:5px 0 0 15px;font-size:11px}.priority-reference-filters>.priority-filter-picker:nth-child(1){border-top:3px solid #5486bd}.priority-reference-filters>.priority-filter-picker:nth-child(2){border-top:3px solid #b77a2c}.priority-reference-filters>.priority-filter-picker:nth-child(3){border-top:3px solid #478644}
.priority-filter-options{padding:0 10px 10px}.priority-filter-options>input{width:100%;min-width:0;box-sizing:border-box;padding:9px}.priority-filter-tools{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0}.priority-filter-tools button{font-size:10px;padding:6px 8px}.priority-filter-list{max-height:210px;overflow:auto;overscroll-behavior:contain}.priority-filter-option{display:flex;align-items:flex-start;gap:9px;padding:8px 4px;font-size:12px;border-bottom:1px solid #eeebe4;cursor:pointer}.priority-filter-option>input{width:auto;margin:3px 0 0;flex-shrink:0;accent-color:#23776b}.priority-filter-option>span{min-width:0;overflow-wrap:anywhere}.priority-filter-option small{display:block;font-size:10px;line-height:1.5;color:#626368;margin-top:4px}.priority-filter-empty{font-size:12px}.priority-facet-filters>label{display:flex;flex-direction:column;gap:10px;font-size:12px;padding:8px 0}.priority-facet-filters>label>select{width:100%;padding:10px;box-sizing:border-box}
.priority-filter-active{border-top:1px solid var(--line);margin-top:16px;padding-top:10px}.priority-filter-active>p{font-size:12px}.priority-filter-chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.priority-filter-chips>span{display:inline-flex;align-items:center;gap:8px;background:#e7ece7;border-radius:6px;padding:4px 8px;font-size:11px;max-width:100%;overflow-wrap:anywhere}.priority-filter-chips button{border:0;background:transparent;padding:2px 4px;font-size:16px}
@media(max-width:1000px){.priority-facet-filters{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.priority-reference-filters{grid-template-columns:1fr}.priority-facet-filters{grid-template-columns:1fr}#priority-structured-filters{padding:12px}}
#view-priorities .priority-combination-card{padding:20px;border:1px solid var(--line);border-radius:10px;background:#fffefa;display:flex;flex-direction:column;gap:8px;text-align:left;border-top:3px solid #23776b}
#view-priorities .priority-combination-card:hover{background:#f0ede5}#view-priorities .priority-combination-card:focus-visible{outline:2px solid #b64c26;outline-offset:2px}
#view-priorities .priority-combination-card small{font-size:11px}#view-priorities .priority-combination-distant{border-top-color:#b87418}
#view-priorities .priority-combination-card[aria-pressed=true] small{color:#e4dfd5}
`;document.head.append(combinationStyle);

// Cross-analysis workspace: keep the task, its scope and its next action visible.
const priorityWorkspaceStyle=se('style');priorityWorkspaceStyle.textContent=`
#view-priorities{--cross-accent:#236c60;--cross-soft:#eaf1ed;padding:28px;box-sizing:border-box}
#view-priorities [hidden]{display:none!important}
#view-priorities :is(button,summary,input,select):focus-visible{outline:3px solid #b64c26;outline-offset:3px}
#view-priorities :is(button,summary){touch-action:manipulation}
#view-priorities .priority-heading{align-items:center;gap:20px}
#view-priorities h1{font-size:clamp(25px,2.5vw,36px);letter-spacing:-1px;margin:6px 0}
#view-priorities .priority-heading p{margin:6px 0;font-size:13px}
#view-priorities .priority-heading .priority-actions{max-width:none;flex-direction:column;align-items:flex-end;flex-shrink:0;gap:8px}
#view-priorities .priority-primary{background:#182b27;color:#fffefa;border-color:#182b27;font-weight:700;padding:13px 18px}
#view-priorities [data-matrix-count]{font-size:11px;color:#58645e}
#view-priorities .priority-journey{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;list-style:none;counter-reset:cross-step;padding:0;margin:22px 0 12px}
#view-priorities .priority-journey li{counter-increment:cross-step;min-width:0}
#view-priorities .priority-journey button{display:grid;grid-template-columns:30px 1fr;column-gap:10px;row-gap:4px;align-items:center;background:transparent;border:0;border-radius:6px;padding:9px;width:100%;font-size:12px}
#view-priorities .priority-journey button::before{content:counter(cross-step,decimal-leading-zero);grid-row:1/3;border:1px solid #c6cec6;border-radius:50%;width:28px;height:28px;display:grid;place-items:center;color:#356155;font-size:10px}
#view-priorities .priority-journey button:hover{background:#edf1e9}
#view-priorities .priority-journey small{font-size:11px;color:#666b64}
#view-priorities .priority-policy{font-size:12px;color:#285c4c;background:#edf3e9;border-left:3px solid #60856a;padding:10px 14px;margin:12px 0}
#view-priorities #priority-status{font-size:11px;color:#696a61;margin:8px 0 18px}
#view-priorities .priority-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;border-top:1px solid var(--line);padding-top:18px}
#view-priorities .priority-view-switch{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));flex:1;min-width:0;gap:4px;padding:4px;background:#ebece5;border-radius:9px}
#view-priorities .priority-view-switch button{display:flex;align-items:center;gap:10px;min-width:0;text-align:left;background:transparent;border:1px solid transparent;padding:12px;font-size:12px;border-radius:6px;font-weight:600;min-height:66px;color:#33453d}
#view-priorities .priority-view-switch button:hover{background:#f4f6ef;border-color:#cbd4c8}
#view-priorities .priority-mode-icon{width:23px;height:23px;flex-shrink:0;color:#536c5e}
#view-priorities .priority-mode-copy{min-width:0}
#view-priorities .priority-mode-copy strong{display:block;font:inherit;line-height:1.4}
#view-priorities .priority-mode-copy small{display:block;font-size:11px;font-weight:400;line-height:1.4;color:#5b665c;margin-top:4px}
#view-priorities .priority-view-switch button[aria-pressed=true]{background:#fffefa;color:#1f4e43;border-color:#cad2c9;box-shadow:0 1px 3px #14281e12}
#view-priorities .priority-view-switch button[aria-pressed=true] .priority-mode-icon{color:#236c60}
#view-priorities #priority-mode-hint{font-size:12px;color:#63675f;margin:10px 0 18px}
#view-priorities .priority-exports{position:relative;flex-shrink:0}
#view-priorities .priority-exports>summary{cursor:pointer;padding:12px 14px;border:1px solid var(--line);border-radius:7px;font-size:12px;background:#fffefa}
#view-priorities .priority-exports>div{position:absolute;right:0;top:calc(100% + 8px);width:min(360px,80vw);z-index:8;padding:8px;background:#fffefa;border:1px solid var(--line);border-radius:10px;box-shadow:0 12px 36px #172d2220}
#view-priorities .priority-exports button{display:block;width:100%;background:transparent;border:0;border-radius:6px;padding:13px;text-align:left}
#view-priorities .priority-exports button:hover{background:#edf1e9}
#view-priorities .priority-exports strong,#view-priorities .priority-exports small{display:block;font-size:12px}
#view-priorities .priority-exports small{font-size:11px;font-weight:400;color:#63675f;margin-top:5px;line-height:1.5}
#view-priorities #priority-structured-filters{padding:17px 20px;margin:0 0 16px;background:#f5f6f0;border-radius:10px}
#view-priorities #priority-structured-filters h2{font-size:17px;margin:0 0 4px}
#view-priorities #priority-structured-filters>p{margin:4px 0 10px}
#view-priorities .priority-reference-filters{gap:10px;margin:12px 0}
#view-priorities .priority-filter-picker>summary{padding:10px 12px;min-height:38px}
#view-priorities .priority-more-filters{margin:6px 0}
#view-priorities .priority-more-filters>summary{padding:8px 0}
#view-priorities .priority-facet-filters{padding:10px 0}
#view-priorities .priority-filter-tools button{min-height:32px}
#view-priorities #priority-filter-live{position:static;z-index:auto;display:block;background:transparent;color:#315b4b;padding:10px 0 0;margin:8px 0 0;border-top:1px solid #dce2d6;border-radius:0;font-size:12px}
#view-priorities .priority-filter-active{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:13px 16px;margin:14px 0;position:sticky;top:8px;z-index:7;background:#f0f5ec;border:1px solid #b6c9b6;border-left:3px solid #2d705a;border-radius:8px;box-shadow:0 3px 12px #1f382510}
#view-priorities .geo-shell .priority-applied-panel{display:none}
.geo-expanded .priority-applied-panel{display:flex;gap:10px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:8;padding:12px;background:#f0f5ec;border:1px solid #b6c9b6;border-radius:8px;font-size:12px}
.geo-expanded .priority-applied-panel .priority-filter-chips{flex-basis:100%;max-height:100px;overflow:auto}
.geo-expanded .priority-applied-panel .priority-reset{margin-left:auto}
.geo-expanded .priority-applied-panel [hidden]{display:none!important}
#view-priorities .priority-filter-active>strong{font-size:12px;color:#254e40}
#view-priorities .priority-filter-active .priority-filter-chips{flex-basis:100%;max-height:120px;overflow:auto}
#view-priorities .priority-filter-active .priority-filter-chips:empty{display:none}
#view-priorities .priority-filter-conflict{border-left:3px solid #b97722;background:#fff2db}
#view-priorities .priority-filter-active>p{font-size:11px;margin:0;flex-basis:100%;color:#57664f}
#view-priorities .priority-filter-active>button{margin-left:auto;font-size:11px}
#view-priorities .priority-filter-chips{margin:0;gap:6px}
#view-priorities .priority-filter-chips button{min-width:28px;min-height:28px}
#view-priorities #priority-combinations{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:12px 0}
#view-priorities .priority-shortcuts{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
#view-priorities .priority-shortcuts>strong{font-size:11px;margin-right:6px;color:#64695f}
#view-priorities .priority-shortcuts button{padding:9px 12px;border-radius:20px;font-size:11px;background:#fffefa;min-height:36px}
#view-priorities .priority-shortcuts button[aria-pressed=true]{background:#e5eee8;color:#205b4e;border-color:#9db6a6}
#view-priorities .priority-combination-details{font-size:12px;flex:1;min-width:210px}
#view-priorities .priority-combination-details>summary{padding:10px 0;cursor:pointer;text-align:right}
#view-priorities .priority-combination-details[open]{flex-basis:100%}
#view-priorities .priority-combination-details[open]>summary{text-align:left}
#view-priorities .priority-combination-details>p{font-size:12px;color:#666b62}
#view-priorities .priority-combination-cards{grid-template-columns:repeat(4,minmax(0,1fr));margin:12px 0;gap:8px}
#view-priorities .priority-combination-card{padding:12px;gap:5px;border-top-width:1px;flex-direction:row;align-items:center}
#view-priorities .priority-combination-card strong{font-size:20px;min-width:36px}
#view-priorities .priority-combination-card span{font-size:11px}
#view-priorities .priority-catalog-browser{margin:14px 0;font-size:12px;border-bottom:1px solid var(--line);padding-bottom:12px}
#view-priorities .priority-catalog-browser>summary{cursor:pointer;color:#4c5c51;padding:6px 0}
#view-priorities #priority-catalog{position:static;max-height:280px;overflow:auto;padding:10px;background:#f6f7f1;margin-top:10px;border-radius:8px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 12px}
#view-priorities #priority-catalog>input{grid-column:1/-1;box-sizing:border-box;width:100%;padding:10px}
#view-priorities #priority-catalog>h3{grid-column:1/-1;margin:12px 0 4px}
#view-priorities #priority-catalog button{font-size:12px;min-height:40px;padding:9px}
#view-priorities #priority-catalog button.chosen{background:#244f42;color:#fff}
#view-priorities .priority-body{display:block}
#view-priorities .priority-results-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin:18px 0 4px}
#view-priorities .priority-results-heading h2{font-size:22px;margin:0;min-width:0;overflow-wrap:anywhere}
#view-priorities .priority-results-heading label{display:flex;align-items:center;gap:8px;font-size:11px;color:#63665e}
#view-priorities .priority-results-heading select{font:inherit;font-size:12px;padding:10px;max-width:100%}
#view-priorities #priority-result-count{font-size:12px;color:#63675f;margin:6px 0 12px;scroll-margin-top:20px}
#view-priorities .priority-pagination{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 0;font-size:12px}
#view-priorities .priority-pagination button{padding:10px 14px;min-height:40px}
#view-priorities .priority-page-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-items:start}
#view-priorities .priority-page{padding:20px;margin:0;position:relative;min-width:0;border-radius:10px;border-color:#d8ded3}
#view-priorities .priority-page:hover{border-color:#9fae9c}
#view-priorities .priority-page-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
#view-priorities .priority-page-heading h3{font-size:16px;line-height:1.5;margin:4px 0;overflow-wrap:anywhere;min-width:0}
#view-priorities .priority-page-heading>span{white-space:nowrap;background:#edf1e8;padding:6px 8px;border-radius:5px;font-size:10px;margin-top:4px}
#view-priorities .priority-page>small{font-size:10px;overflow-wrap:anywhere}
#view-priorities .priority-page>p{font-size:12px;color:#596557;margin:8px 0}
#view-priorities .priority-page>.priority-source-action{font-size:12px;font-weight:700;color:#245b4d;border-color:#b9c9bc;background:#f2f6ed;margin:6px 0;padding:10px 14px}
#view-priorities .priority-all-excerpts>summary,#view-priorities .priority-filter-help>summary{font-size:12px;cursor:pointer;padding:8px 0;color:#285b4c}
#view-priorities .priority-filter-help p{font-size:12px}
#view-priorities .priority-version:has(.priority-all-excerpts[open])>.priority-preview{display:none}
#view-priorities .priority-version blockquote{font-size:13px;line-height:1.7;border-color:#b0c5ae}
#view-priorities .priority-version .matrix-select-label{font-size:12px;padding:10px;background:#f2f5ee;border-radius:6px;cursor:pointer}
#view-priorities .priority-empty{padding:32px;border:1px dashed #bcc9bb;border-radius:10px;background:#f5f7f0;margin:20px 0}
#view-priorities .priority-empty h3{font-size:20px;margin:0 0 8px}
#view-priorities .priority-empty p{max-width:680px;font-size:13px}
#view-priorities .priority-empty button{margin:8px 10px 0 0}
#view-priorities>.priority-method{font-size:12px;background:transparent;margin-top:24px}
@media(max-width:1100px){#view-priorities .priority-toolbar{flex-wrap:wrap}#view-priorities .priority-view-switch{flex-basis:100%}#view-priorities .priority-exports{margin-left:auto}}
@media(max-width:1000px){#view-priorities .priority-heading{display:flex}#view-priorities .priority-heading .priority-actions{align-items:flex-start}#view-priorities .priority-journey{gap:4px}#view-priorities .priority-view-switch button{padding:10px;gap:8px}#view-priorities .priority-combination-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){#view-priorities{padding:18px}#view-priorities .priority-heading{display:block}#view-priorities .priority-heading .priority-actions{flex-direction:row;align-items:center;margin:16px 0}#view-priorities .priority-journey{grid-template-columns:1fr;gap:2px;margin:12px 0}#view-priorities .priority-journey button{grid-template-columns:26px 1fr;padding:6px}#view-priorities .priority-journey button::before{width:24px;height:24px}#view-priorities .priority-journey small{display:none}#view-priorities .priority-toolbar{align-items:stretch;flex-direction:column;gap:10px}#view-priorities .priority-view-switch{display:grid;grid-template-columns:1fr 1fr}#view-priorities .priority-exports>summary{text-align:center}#view-priorities .priority-exports>div{box-sizing:border-box;width:100%}#view-priorities .priority-reference-filters{grid-template-columns:1fr}#view-priorities .priority-filter-picker>summary>span{display:inline;margin-left:8px}#view-priorities .priority-filter-picker>summary{min-height:20px}#view-priorities .priority-shortcuts>strong{flex-basis:100%}#view-priorities .priority-combination-details>summary{text-align:left}#view-priorities #priority-catalog{grid-template-columns:1fr}#view-priorities .priority-page-list{grid-template-columns:1fr}#view-priorities .priority-results-heading label{width:100%;justify-content:space-between}#view-priorities .priority-pagination{font-size:11px}#view-priorities .priority-pagination button{padding:8px 10px}#view-priorities .priority-page{padding:16px}#view-priorities .priority-page-heading{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){#view-priorities *{scroll-behavior:auto;transition:none;animation:none}}
`;document.head.append(priorityWorkspaceStyle);
