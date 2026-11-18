// Question overview and clickable citations use saved provenance, never inferred URLs.
function graphQueryOverview(host,graph,options={}){
 const tr=(es,en,fr)=>({es,en,fr})[uiLanguage]||es;
 const entirePilot=options.scope==='pilot';
 const details=gse(entirePilot?'section':'details');details.open=true;details.className='graph-query-overview';details.dataset.scope=entirePilot?'pilot':'question';
 if(!entirePilot)details.append(gse('summary',options.filtered?({es:'Relaciones de las páginas enfocadas',en:'Relationships from focused pages',fr:'Relations des pages ciblées'})[uiLanguage]:gMsg('Todo el contexto recuperado')));
 const layout=GraphResultCore.overview(graph,{compact:entirePilot}),names=new Map(layout.nodes.map(n=>[n.id,n]));
 const help=gse('p',entirePilot?gMsg`${layout.nodes.length} entidades · ${graph.relationships.length} afirmaciones en ${layout.links.length} conexiones · ${layout.components} grupos conectados o entidades aisladas. Incluye todas las entidades y relaciones extraídas, también las entidades sin vínculos. Son resultados candidatos; la extracción puede haber omitido información.`:gMsg`${layout.nodes.length} entidades · ${graph.relationships.length} afirmaciones en ${layout.links.length} conexiones · ${layout.components} grupos conectados o entidades aisladas. Se muestra todo el contexto recuperado para esta pregunta; no garantiza recuperar todo lo relevante del piloto.`);
 if(options.filtered)gSet(help,({es:'Se muestran las relaciones de las páginas vinculadas a la hipótesis. Quita el enfoque para ver todo el contexto de la pregunta.',en:'Showing relationships from pages linked to the hypothesis. Clear focus to see the full question context.',fr:'Relations des pages liées à l’hypothèse. Effacez le focus pour voir tout le contexte de la question.'})[uiLanguage]);
 const controls=gse('div');controls.className='priority-actions graph-canvas-controls';
 const stage=gse('div');stage.className='graph-canvas-stage';
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('graph-query-svg');gAttr(svg,'role','group');gAttr(svg,'aria-label',entirePilot?gMsg('Grafo completo del piloto'):gMsg('Todo el grafo recuperado para la pregunta'));gAttr(svg,'tabindex','0');
 const tooltip=gse('div');tooltip.className='graph-edge-tooltip';tooltip.hidden=true;gAttr(tooltip,'role','tooltip');stage.append(tooltip);
 const inspector=gse('div');inspector.className='graph-neighborhood-inspector';gAttr(inspector,'aria-live','polite');inspector.hidden=true;
 let webgl=null;let focusId='',searchIds=new Set(),activeType='';const typeButtons=new Map();const neighbors=new Map(layout.nodes.map(n=>[n.id,new Set()]));for(const link of layout.links){neighbors.get(link.source).add(link.target);neighbors.get(link.target).add(link.source)}
 function highlight(id){webgl?.highlight(id,searchIds);svg.classList.toggle('graph-has-focus',!!id||searchIds.size>0);for(const element of svg.querySelectorAll('[data-entity]'))element.classList.toggle('graph-related',!!id&&(element.dataset.entity===id||neighbors.get(id)?.has(element.dataset.entity))||searchIds.has(element.dataset.entity));for(const element of svg.querySelectorAll('.graph-overview-link'))element.classList.toggle('graph-related',!!id&&(element.dataset.source===id||element.dataset.target===id)||searchIds.has(element.dataset.source)||searchIds.has(element.dataset.target))}
 const zoomStatus=gse('output');zoomStatus.className='graph-zoom-status';gAttr(zoomStatus,'aria-label',tr('Nivel de zoom','Zoom level','Niveau de zoom'));
 let bounds={x:0,y:0,w:layout.width,h:layout.height};const initial={...bounds};
 function updateLabels(){if(!entirePilot)return;const highlighted=new Set(searchIds);if(focusId)highlighted.add(focusId);const screenWidth=svg.clientWidth||1000,ids=GraphResultCore.labelIds(layout.nodes,bounds,initial.w,highlighted,screenWidth),fontSize=Math.max(12,Math.min(23,13*bounds.w/screenWidth));svg.dataset.zoomed=String(initial.w/bounds.w>=1.8);for(const element of svg.querySelectorAll('[data-entity]')){element.classList.toggle('graph-label-visible',ids.has(element.dataset.entity));const text=element.querySelector('.graph-node-label');if(text)text.setAttribute('font-size',fontSize)}}
 const setBounds=b=>{webgl?.bounds(b,initial);bounds=b;svg.setAttribute('viewBox',`${b.x} ${b.y} ${b.w} ${b.h}`);zoomStatus.textContent=Math.round(initial.w/b.w*100)+'%';updateLabels()};setBounds(bounds);placeMapNavigation(svg,()=>bounds,setBounds,GraphResultCore);
 const select=gse('select');gAttr(select,'aria-label',entirePilot?gMsg('Encontrar entidad en el grafo completo'):gMsg('Encontrar entidad en el contexto recuperado'));
 function populateSelect(items){select.replaceChildren();const empty=gse('option',gMsg('Selecciona una entidad para ver sus fuentes'));empty.value='';select.append(empty);for(const n of items){const o=gse('option',gMsg`${n.label} · ${graphTypeNames[n.type]||n.type}`);o.value=n.id;select.append(o)}}populateSelect(layout.nodes);
 const search=gse('input');search.type='search';gAttr(search,'placeholder',gMsg('Buscar una persona, familia, lugar…'));gAttr(search,'aria-label',gMsg('Buscar entidades en el grafo'));search.autocomplete='off';
 const searchStatus=gse('span');searchStatus.className='graph-search-status';gAttr(searchStatus,'aria-live','polite');
 function clearFocus(){focusId='';select.value='';highlight('');for(const n of svg.querySelectorAll('.graph-selected'))n.classList.remove('graph-selected');inspector.replaceChildren();inspector.hidden=true;options.onClear?.()}
 function reset(){if(entirePilot)window.KnowledgeGraphFilters?.clear('reset');webgl?.reset();search.value='';activeType='';updateSearch();bounds={...initial};svg.setAttribute('viewBox',`0 0 ${initial.w} ${initial.h}`);updateLabels();if(!webgl)setBounds({...initial})}
 const zoomIn=gButton('+',()=>webgl?webgl.zoom(.7):setBounds(GraphResultCore.zoomAt(bounds,.7))),zoomOut=gButton('−',()=>webgl?webgl.zoom(1.4):setBounds(GraphResultCore.zoomAt(bounds,1.4)));gAttr(zoomIn,'aria-label',gMsg('Acercar el grafo'));gAttr(zoomOut,'aria-label',gMsg('Alejar el grafo'));
 controls.append(zoomIn,zoomOut,zoomStatus,gButton(gMsg('Encuadrar todo'),reset));
 const searchBox=gse('div');searchBox.className='graph-canvas-search';searchBox.append(search,select);controls.prepend(searchBox);
 const fullscreenTarget=host.closest('.knowledge-workspace')||details;
 const fullscreenLabel=()=>tr('Ampliar Knowledge Graph','Expand Knowledge Graph','Agrandir Knowledge Graph');
 const exitLabel=()=>tr('Salir de pantalla completa','Exit full screen','Quitter le plein écran');
 function syncFullscreen(){const active=document.fullscreenElement===fullscreenTarget||fullscreenTarget.classList.contains('graph-expanded');gAttr(expand,'aria-pressed',String(active));gSet(expand,active?exitLabel():fullscreenLabel());updateLabels()}
 async function leaveFullscreen(){if(document.fullscreenElement===fullscreenTarget)await document.exitFullscreen();fullscreenTarget.classList.remove('graph-expanded');syncFullscreen();expand.focus()}
 const expand=gButton(fullscreenLabel(),async()=>{
  if(document.fullscreenElement===fullscreenTarget||fullscreenTarget.classList.contains('graph-expanded')){await leaveFullscreen();return}
  details.open=true;
  try{if(!fullscreenTarget.requestFullscreen)throw Error('unsupported');await fullscreenTarget.requestFullscreen()}catch{fullscreenTarget.classList.add('graph-expanded')}
  syncFullscreen();expand.focus();
 });gAttr(expand,'aria-pressed','false');controls.append(expand);
 const graphExpand=gButton(tr('Ampliar solo grafo','Expand graph only','Agrandir le graphe seul'),async()=>{
  if(document.fullscreenElement===details||details.classList.contains('graph-only-expanded')){if(document.fullscreenElement===details)await document.exitFullscreen();details.classList.remove('graph-only-expanded');syncGraphOnly();return}
  if(document.fullscreenElement)await document.exitFullscreen();fullscreenTarget.classList.remove('graph-expanded');details.open=true;
  try{await details.requestFullscreen()}catch{details.classList.add('graph-only-expanded')}
  syncGraphOnly();
 });
 function syncGraphOnly(){const active=document.fullscreenElement===details||details.classList.contains('graph-only-expanded');gSet(graphExpand,active?tr('Reducir grafo','Restore graph','Réduire le graphe'):tr('Ampliar solo grafo','Expand graph only','Agrandir le graphe seul'));gAttr(graphExpand,'aria-pressed',String(active));updateLabels()}
 gAttr(graphExpand,'aria-pressed','false');controls.insertBefore(graphExpand,expand);details.addEventListener('fullscreenchange',syncGraphOnly);details.addEventListener('keydown',event=>{if(event.key==='Escape'&&details.classList.contains('graph-only-expanded')){details.classList.remove('graph-only-expanded');syncGraphOnly()}});
 fullscreenTarget.addEventListener('fullscreenchange',syncFullscreen);
 fullscreenTarget.addEventListener('keydown',event=>{if(event.key==='Escape'&&fullscreenTarget.classList.contains('graph-expanded')){event.preventDefault();leaveFullscreen()}});
 function updateSearch(){const normalize=value=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(),query=normalize(search.value).trim(),items=layout.nodes.filter(n=>(!activeType||n.type===activeType)&&(!query||normalize(n.label).includes(query)));searchIds=new Set(query||activeType?items.map(n=>n.id):[]);populateSelect(items);clearFocus();for(const [type,b]of typeButtons)b.setAttribute('aria-pressed',String(type===activeType));gSet(searchStatus,query||activeType?tr(`${items.length} de ${layout.nodes.length} entidades destacadas`,`${items.length} of ${layout.nodes.length} entities highlighted`,`${items.length} sur ${layout.nodes.length} entités mises en évidence`):'');svg.classList.toggle('graph-no-matches',!!(query||activeType)&&!items.length);updateLabels()}
 search.oninput=()=>{updateSearch();if(entirePilot)window.KnowledgeGraphFilters?.set({query:search.value,type:activeType,entity:'',edges:[]},'graph')};
 function applySearchFocus(){updateSearch();if(!search.value.trim()&&!activeType){reset();return}if(webgl){webgl.focusMatches(searchIds);return}const visible=new Set(searchIds);for(const id of searchIds)for(const neighbor of neighbors.get(id)||[])visible.add(neighbor);svg.querySelectorAll('[data-entity]').forEach(n=>{n.style.display=visible.has(n.dataset.entity)?'':'none';n.classList.toggle('graph-selected',searchIds.has(n.dataset.entity))});svg.querySelectorAll('.graph-overview-link').forEach(n=>n.style.display=searchIds.has(n.dataset.source)||searchIds.has(n.dataset.target)?'':'none')}
 search.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();applySearchFocus()}};
 details.addEventListener('knowledge-search-submit',applySearchFocus);

 const node=(tag,attrs={},text)=>{const n=document.createElementNS(svg.namespaceURI,tag);for(const [k,v]of Object.entries(attrs))gAttr(n,k,v);if(text!=null)gSet(n,text);return n};
 const colors=entirePilot?{PERSON:'#7eb7ed',FAMILY:'#efb765',PLACE:'#66cbb4',TIME:'#bb9aec',ORGANIZATION:'#f18375',EVENT:'#c8cd7e',GROUP:'#afbed1',TOPIC:'#d6a68d'}:{PERSON:'#527fb5',FAMILY:'#b57b29',PLACE:'#21786a',TIME:'#7850a5',ORGANIZATION:'#b45b50',EVENT:'#797e42',GROUP:'#65727e',TOPIC:'#8d6955'};
 const markerId='overview-arrow-'+localUUID(),defs=node('defs'),marker=node('marker',{id:markerId,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto'});marker.append(node('path',{d:'M0 0L10 5L0 10Z',fill:entirePilot?'#9aa99f':'#879b90'}));defs.append(marker);svg.append(defs);
 function inspect(title,edges,entity=null){if(entirePilot)window.KnowledgeGraphFilters?.set({entity:entity?.id||'',edges:entity?[]:edges.map(e=>e.id)},'graph');if(entity){if(![...select.options].some(o=>o.value===entity.id))populateSelect(layout.nodes);select.value=entity.id}else select.value='';if(options.onInspect){if(options.externalInspector&&fullscreenTarget===details&&(fullscreenTarget.classList.contains('graph-expanded')||document.fullscreenElement===fullscreenTarget)){leaveFullscreen()}options.onInspect({title:gResolve(title),edges,entity});if(options.externalInspector){focusId=entity?.id||'';highlight(focusId);updateLabels();svg.querySelectorAll('[data-entity]').forEach(n=>n.classList.toggle('graph-selected',n.dataset.entity===focusId));return}}focusId=entity?.id||'';highlight(focusId);inspector.hidden=false;
  const header=gse('div');header.className='graph-inspector-header';header.append(gse('h4',title),gButton(gMsg('Cerrar'),()=>{clearFocus();updateLabels()}));
  inspector.replaceChildren(header,gse('p',gMsg`${edges.length} afirmaciones candidatas. Abre la fuente para comprobar la relación y su contexto.`));
  if(entity)inspector.append(researchBridgeActions(entity.label,'knowledge_graph'));
  svg.querySelectorAll('[data-entity]').forEach(n=>n.classList.toggle('graph-selected',n.dataset.entity===entity?.id));
  for(const edge of edges){const row=gse('p');row.append(gse('strong',gMsg`${names.get(edge.source)?.label||edge.source} → ${names.get(edge.target)?.label||edge.target}: `),gse('span',gMsg`${edge.fields.relation||gMsg('Relación candidata')} · ${graphDate(edge.fields.event_time)} · `),gButton(gMsg`${edge.page.document} · p. ${edge.page.page}`,()=>graphPilotSource(edge)));const pick=gButton(({es:'Añadir a mi selección',en:'Add to my selection',fr:'Ajouter à ma sélection'})[uiLanguage],()=>{researchGraphSelect(edge.page,{kind:'Knowledge Graph',query:options.question||'',pilot_run:graph.run_id,relationship:edge.fields.relation,source:edge.source,target:edge.target,quotes:edge.quotes||[],matches:[{label:names.get(edge.source)?.label||edge.source},{label:names.get(edge.target)?.label||edge.target}]});pick.disabled=true});row.append(pick);inspector.append(row)}
  if(entity&&!edges.length){inspector.append(gse('p',gMsg('Esta entidad fue recuperada sin un vínculo representado.')));for(const mention of entity.mentions||[])inspector.append(gButton(gMsg`${mention.page.document} · p. ${mention.page.page}`,()=>graphPilotSource({id:graph.run_id+':entity',page:mention.page,quotes:mention.quotes||[]})))}
  if(entity&&edges.length)inspector.append(gButton(gMsg('Explorar sólo los vecinos de esta entidad'),()=>{const box=gse('div');inspector.append(box);graphPilotNeighborhood(box,graph,entity.id);box.querySelector('details').open=true}));
 }
 select.onchange=()=>{const n=names.get(select.value);if(n){if(entirePilot&&!webgl){const w=Math.min(bounds.w,initial.w/3),h=w*initial.h/initial.w;setBounds({x:n.x-w/2,y:n.y-h/2,w,h})}inspect(n.label,graph.relationships.filter(e=>e.source===n.id||e.target===n.id),n)}else{clearFocus();updateLabels()}};
 if(layout.isolatedRegion){const r=layout.isolatedRegion;svg.append(node('rect',{x:r.x,y:r.y,width:r.width,height:r.height,rx:18,fill:entirePilot?'#192225':'#e8eee9',opacity:.65}),node('text',{x:r.x+22,y:r.y+28,'font-size':17,fill:entirePilot?'#a8b9b0':'#526459'},gMsg`${r.count} entidades sin vínculos extraídos · también puedes consultar sus fuentes`))}
 for(const link of layout.links){const a=names.get(link.source),b=names.get(link.target),dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),self=link.source===link.target;
  const path=self?`M ${a.x-8} ${a.y-4} C ${a.x-65} ${a.y-70}, ${a.x+65} ${a.y-70}, ${a.x+8} ${a.y-4}`:`M ${a.x+dx/d*12} ${a.y+dy/d*12} Q ${(a.x+b.x)/2-dy*.08} ${(a.y+b.y)/2+dx*.08} ${b.x-dx/d*14} ${b.y-dy/d*14}`;
  const g=node('g',{class:'graph-overview-link','data-source':link.source,'data-target':link.target,role:'button',tabindex:entirePilot?'-1':'0','aria-label':gMsg`${a.label} → ${b.label}: ${link.edges.length} afirmaciones`});g.append(node('path',{d:path,fill:'none',stroke:'transparent','stroke-width':16}),node('path',{d:path,fill:'none',stroke:entirePilot?'#6e8982':'#879b90','stroke-width':entirePilot?1.5:1.8,'marker-end':`url(#${markerId})`}));g.append(node('title',{},a.label+' → '+b.label+'\n'+link.edges.map(edge=>(edge.fields?.relation||gResolve(gMsg('Relación candidata')))+' · '+edge.page.document+' · p. '+edge.page.page).join('\n')));if(link.edges.length>1&&!entirePilot)g.append(node('text',{x:(a.x+b.x)/2,y:(a.y+b.y)/2-6,'text-anchor':'middle','font-size':12,fill:'#435b50'},link.edges.length));g.onpointerenter=event=>{tooltip.replaceChildren(gse('strong',a.label+' → '+b.label));for(const edge of link.edges.slice(0,5)){tooltip.append(gse('p',(edge.fields?.relation||gResolve(gMsg('Relación candidata')))+' · '+graphDate(edge.fields?.event_time)),gse('small',edge.page.document+' · p. '+edge.page.page))}if(link.edges.length>5)tooltip.append(gse('small','+ '+(link.edges.length-5)));tooltip.hidden=false;g.classList.add('graph-edge-hover');positionTooltip(event)};function positionTooltip(event){const rect=stage.getBoundingClientRect();tooltip.style.left=Math.max(8,Math.min(rect.width-340,event.clientX-rect.left+16))+'px';tooltip.style.top=Math.max(8,Math.min(rect.height-tooltip.offsetHeight-8,event.clientY-rect.top+16))+'px'}g.onpointermove=positionTooltip;g.onpointerleave=()=>{tooltip.hidden=true;g.classList.remove('graph-edge-hover')};g.onfocus=()=>{tooltip.replaceChildren(gse('strong',a.label+' → '+b.label));for(const edge of link.edges.slice(0,5))tooltip.append(gse('p',edge.fields?.relation||gMsg('Relación candidata')),gse('small',edge.page.document+' · p. '+edge.page.page));tooltip.style.left='12px';tooltip.style.top='12px';tooltip.hidden=false};g.onblur=()=>tooltip.hidden=true;g.onclick=()=>{tooltip.hidden=true;inspect(gMsg`${a.label} → ${b.label}`,link.edges)};g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();g.onclick()}};svg.append(g);
 }
 for(const n of layout.nodes){const g=node('g',{class:'graph-overview-node','data-entity':n.id,role:'button',tabindex:entirePilot?'-1':'0','aria-label':gMsg`${n.label}: consultar fuentes`});if(!entirePilot)g.append(node('title',{},gMsg`${n.label} · ${graphTypeNames[n.type]||n.type}`));g.append(node('circle',{cx:n.x,cy:n.y,r:entirePilot?Math.min(16,6+Math.sqrt(neighbors.get(n.id).size)*1.7):10,fill:colors[n.type]||'#afbed1'}),node('text',{class:'graph-node-label',x:n.x,y:n.y+26,'text-anchor':'middle','font-size':13,fill:entirePilot?'#f5f5f2':'#27312b','paint-order':'stroke',stroke:entirePilot?'#111619':'#f5f4ee','stroke-width':4},n.label.length>25?n.label.slice(0,24)+'…':n.label));g.onpointerenter=()=>highlight(n.id);g.onpointerleave=()=>highlight(focusId);g.onfocus=()=>highlight(n.id);g.onblur=()=>highlight(focusId);g.onclick=()=>{if(![...select.options].some(o=>o.value===n.id))populateSelect(layout.nodes);select.value=n.id;select.onchange()};g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();g.onclick()}};svg.append(g)}
 const legend=gse('div');legend.className='graph-type-legend';gAttr(legend,'role','group');gAttr(legend,'aria-label',tr('Destacar entidades por tipo','Highlight entities by type','Mettre en évidence par type'));for(const type of ['',...new Set(layout.nodes.map(n=>n.type))]){const label=gButton(type?graphTypeNames[type]||type:tr('Todas','All','Toutes'),()=>{activeType=activeType===type?'':type;updateSearch();if(entirePilot)window.KnowledgeGraphFilters?.set({type:activeType,query:search.value,entity:'',edges:[]},'graph')});label.style.setProperty('--entity-color',colors[type]||'#aebcb6');label.append(gse('small',type?layout.nodes.filter(n=>n.type===type).length:layout.nodes.length));gAttr(label,'aria-pressed',String(!type));typeButtons.set(type,label);legend.append(label)}
 if(entirePilot){const footer=gse('div');footer.className='graph-canvas-footer';footer.append(gse('span',tr('Selecciona un nodo para ver sus fuentes. Arrastra para recorrer · + / − para acercar.','Select a node to see its sources. Drag to explore · + / − to zoom.','Sélectionnez un nœud pour voir ses sources. Glissez pour explorer · + / − pour zoomer.')));stage.append(svg,inspector);details.append(controls,searchStatus,legend,stage,footer);const scope=gse('details');scope.className='graph-scope-details';scope.append(gse('summary',gMsg('Alcance y lectura del grafo')),help);details.append(scope)}else{stage.append(svg);details.append(help,controls,searchStatus,legend,stage,inspector)}
 host.append(details);updateLabels();
 webgl=typeof graphWebGLMount==='function'?graphWebGLMount({stage,svg,layout,colors,names,inspect,graph,details,onReset:reset,onSelect:id=>{if(![...select.options].some(o=>o.value===id))populateSelect(layout.nodes);select.value=id;select.onchange()},onZoom:ratio=>{zoomStatus.textContent=Math.round(100/ratio)+'%'}}):null;
 if(webgl){const footer=details.querySelector('.graph-canvas-footer');if(footer)footer.hidden=true}
 if(entirePilot&&typeof ResizeObserver!=='undefined'){const observer=new ResizeObserver(()=>{if(details.isConnected)updateLabels();else observer.disconnect()});observer.observe(svg)}
}

function graphQueryAnswer(host,value){
 const answer=String(value.answer||''),groups=new Map((value.citations||[]).map(c=>[c.raw,c]));
 // The saved resolver is authoritative: numeric IDs are scoped to this answer's context.
 // Keep old/unrecognized Data references visible as unresolved, never guess a source.
 for(const m of answer.matchAll(/\[Data:\s*[^\]]+\](?!\()/gi))if(!groups.has(m[0]))groups.set(m[0],{raw:m[0],records:[]});
 const numbered=new Map([...groups.keys()].map((raw,i)=>[raw,i+1]));
 const drawer=gse('dialog');drawer.className='graph-citation-dialog';drawer.dataset.noI18n='';document.body.append(drawer);drawer.addEventListener('close',()=>drawer.replaceChildren());
 const label={sources:gMsg('Fragmento'),entities:gMsg('Entidad'),relationships:gMsg('Relación'),reports:gMsg('Informe de comunidad'),claims:gMsg('Afirmación')};
 const close=()=>drawer.close();
 const needsReview=group=>!group.records?.length||group.records.some(r=>r.status!=='resolved');
 function sourcePages(records){
  const pages=new Map();
  for(const ref of records||[])for(const item of ref.pages||[]){
   const key=JSON.stringify([item.page.document_id,item.page.page,item.page.version]);
   if(!pages.has(key))pages.set(key,{...item,quotes:[],references:[]});
   const page=pages.get(key);page.quotes.push(...item.quotes||[]);
   if(ref.dataset)page.references.push(gMsg`${label[ref.dataset]||ref.dataset} ${ref.id}`);
   if(item.basis==='community_scope')page.communityScope=true;
  }
  return pages;
 }
 function openCitation(group,raw){
  drawer.replaceChildren();const header=gse('header');header.append(gse('h3',group?.contextOnly?gMsg('Contexto consultado'):gMsg('Fuentes de esta referencia')),gButton(gMsg('Cerrar'),close));drawer.append(header,gse('p',raw),gse('p',group?.contextOnly?gMsg('Estas páginas formaron parte del contexto recuperado. No significa que la respuesta las cite ni que todas respalden sus afirmaciones.'):gMsg('La referencia enlaza un registro del contexto con sus fuentes. Comprueba que el pasaje respalda la afirmación de la respuesta.')));
  if(!group?.records.length)drawer.append(gse('p',gMsg('No se pudo resolver esta referencia en el contexto guardado.')));
  const pages=sourcePages(group?.records);
  drawer.append(gse('p',gMsg`Páginas o lecturas: ${pages.size} · Documentos de origen: ${new Set([...pages.values()].map(p=>p.page.document_id)).size}.`));
  for(const item of pages.values()){
   const row=gse('div');row.className='graph-citation-source';const description=gse('div');
   description.append(gse('span',gMsg`${item.page.folder} · ${item.page.document} · p. ${item.page.page} · ${item.page.version}`));
   if(item.references.length)description.append(gse('p',gMsg`${gMsg('Referencias: ')}${gJoin(item.references)}`));
   if(item.communityScope)description.append(gse('p',gMsg('Fuente del informe de comunidad; su relación con esta afirmación requiere revisión.')));
   const error=gse('p');error.setAttribute('role','alert');
   const button=gButton(gMsg('Abrir imagen y transcripción'),async()=>{
    button.disabled=true;error.textContent='';
    try{await graphPilotSource({id:value.pilot_run+':citation',page:item.page,quotes:[...new Map(item.quotes.map(q=>[q.quote,q])).values()]});if(sourcePopup.open){drawer.close();sourcePopup.addEventListener('close',()=>{if(drawer.isConnected)openCitation(group,raw)},{once:true})}}
    catch(e){gSet(error,gMsg('No se pudo abrir esta fuente. La referencia se conserva; puedes volver a intentarlo.'))}
    finally{button.disabled=false}
   });
   row.append(description,button,error);drawer.append(row);
  }
  for(const ref of group?.records||[]){
   if(!ref.dataset)continue;
   const section=gse('section');section.append(gse('h4',gMsg`${label[ref.dataset]||ref.dataset} ${ref.id}`));
   if(ref.status==='invalid_id')section.append(gse('p',gMsg('El modelo no indicó un identificador válido. No se le asignó un documento.')));
   else if(ref.status!=='resolved')section.append(gse('p',ref.status==='not_in_context'?gMsg('Esta referencia no corresponde a un registro del contexto entregado al modelo. No se le asignó un documento.'):gMsg('El registro existe, pero no se pudo establecer su página de origen.')));
   if(ref.dataset==='reports'&&ref.pages.length)section.append(gse('p',gMsg('Estas páginas pertenecen a la comunidad resumida. No todas respaldan necesariamente la frase citada; revisa también el informe.')));
   if(ref.record){const details=gse('details');details.append(gse('summary',gMsg('Ver el registro citado')),gse('pre',ref.record.content||ref.record.text||ref.record.description||JSON.stringify(ref.record,null,2)));section.append(details)}drawer.append(section);
  }
  if(group?.has_more)drawer.append(gse('p',gMsg('El modelo añadió «+more»: sólo se enlazan los identificadores explícitos, sin adivinar las referencias omitidas.')));
  if(!drawer.open)drawer.showModal();
 }
 const allRecords=[...groups.values()].flatMap(g=>g.records||[]),citedPages=sourcePages(allRecords),pending=[...groups.values()].filter(needsReview).length;
 const summary=gse('div');summary.className='graph-citation-summary';
 summary.append(gse('strong',gMsg('Citas y documentos de origen')));
 summary.append(gse('p',groups.size?gMsg`Citas: ${groups.size} · Páginas o lecturas enlazadas: ${citedPages.size} · Citas sin resolver: ${pending}.`:gMsg('Esta respuesta no incluye citas identificables. Puedes revisar el contexto consultado, pero no atribuirlo automáticamente a cada afirmación.')));
 if(groups.size)summary.append(gse('p',gMsg('Pulsa una cita junto a la afirmación: verde tiene fuentes enlazadas; ámbar necesita revisión. Un enlace no valida la interpretación del modelo.')));
 const actions=gse('div');actions.className='graph-citation-actions';
 if(citedPages.size)actions.append(gButton(gMsg('Ver páginas citadas'),()=>openCitation({records:allRecords},gMsg('Todas las citas de esta respuesta'))));
 if(pending)actions.append(gButton(gMsg('Revisar citas sin resolver'),()=>openCitation({records:allRecords.filter(r=>r.status!=='resolved')},gMsg('Citas sin resolver'))));
 if(value.context_pages?.length)actions.append(gButton(gMsg('Contexto consultado'),()=>openCitation({contextOnly:true,records:[{pages:value.context_pages}]},gMsg('Páginas del contexto recuperado'))));
 summary.append(actions);host.append(summary);
 // Use text nodes for all model content. Limited Markdown formatting, no HTML/URLs.
 function inline(parent,text){const pattern=/\[[^\[\]]+\]|\*\*([^*\n]+)\*\*/g;let cursor=0;for(const match of text.matchAll(pattern)){
  parent.append(document.createTextNode(text.slice(cursor,match.index)));
  if(match[0].startsWith('**'))inline(gseInto(parent,'strong'),match[1]);
  else if(groups.has(match[0])){
   const group=groups.get(match[0]),count=sourcePages(group.records).size;
   const caption=count===1?gMsg`Cita ${numbered.get(match[0])} · 1 página`:count?gMsg`Cita ${numbered.get(match[0])} · ${count} páginas`:gMsg`Cita ${numbered.get(match[0])} · sin resolver`;
   const button=gButton(caption,()=>openCitation(group,match[0]));button.className='graph-citation-link';gAttr(button,'title',gMsg`${gMsg('Ver documentos y páginas de esta referencia')} · ${match[0]}`);
   if(needsReview(group)){button.dataset.unresolved='true';if(count)button.append(gse('span',gMsg(' · revisar')))}parent.append(button);
  }else parent.append(document.createTextNode(match[0]));
  cursor=match.index+match[0].length;
 }parent.append(document.createTextNode(text.slice(cursor)))}
 function gseInto(parent,tag){const child=gse(tag);parent.append(child);return child}
 inline(host,answer);
 // Result rerenders remove the owned dialog without leaking it into the document.
 return ()=>drawer.remove();
}
const graphResultStyle=gse('style');gSet(graphResultStyle,'.graph-query-svg{width:100%;height:560px;background:#f5f4ee;touch-action:none;border:1px solid var(--line);border-radius:6px}.graph-overview-node,.graph-overview-link{cursor:pointer}.graph-selected circle{stroke:#111;stroke-width:4}.graph-overview-node:focus circle{stroke:#111;stroke-width:3}.graph-type-legend{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0;font-size:11px}.graph-type-legend span{padding-left:6px}.graph-citation-link{display:inline;padding:2px 5px;font:inherit;line-height:1.5;border:0;border-bottom:1px solid #21786a;border-radius:3px;color:#126455;background:#e4eee7;white-space:normal;text-align:left;cursor:pointer}.graph-citation-link[data-unresolved]{background:#fff0d5;border-color:#ad781c;color:#825511}.graph-query-answer p{margin:0 0 10px}.graph-citation-dialog{width:850px;max-width:calc(100vw - 48px);max-height:85vh;overflow:auto;background:var(--white);border:1px solid var(--line);border-radius:8px;padding:22px}.graph-citation-dialog::backdrop{background:#182c2470}.graph-citation-dialog header{display:flex;align-items:center;justify-content:space-between;gap:15px}.graph-citation-dialog p{font-size:13px;line-height:1.7}.graph-citation-dialog section{border-top:1px solid var(--line);padding:12px 0}.graph-citation-source{display:flex;gap:12px;justify-content:space-between;align-items:center;margin:10px 0;font-size:12px}.graph-citation-source span{overflow-wrap:anywhere}.graph-citation-dialog pre{white-space:pre-wrap;line-height:1.7;max-height:240px;overflow:auto}.graph-citation-dialog summary{cursor:pointer}@media(max-width:600px){.graph-query-svg{height:430px}.graph-citation-source{display:block}.graph-citation-source button{margin-top:8px}}');document.head.append(graphResultStyle);

const graphFullStyle=gse('style');graphFullStyle.textContent=`
.graph-full-pilot{margin-top:26px;border-radius:12px;background:#101417;color:#f6f5f1;overflow:hidden}
.graph-full-hero{display:flex;align-items:center;justify-content:space-between;gap:32px;padding:30px 32px 22px;border-bottom:1px solid #ffffff18;background:transparent;color:inherit;margin:0;border-radius:0}
.graph-full-hero h2{font:italic 34px/1.15 Georgia,serif;color:#ff7649;letter-spacing:-.6px;margin:0 0 12px}
.graph-full-hero p{font-size:12px;color:#afbbb8;line-height:1.7;max-width:550px;margin:0}
.graph-full-metrics{display:flex;gap:26px;flex-shrink:0}.graph-full-metrics>div{border-left:1px solid #ffffff24;padding-left:18px}
.graph-full-metrics strong{display:block;font-size:30px;line-height:1.1;font-weight:500;letter-spacing:-1px;font-variant-numeric:tabular-nums}.graph-full-metrics span{display:block;font-size:11px;margin-top:7px;color:#afbbb8}
.graph-full-metrics [data-kind=PERSON] strong{color:#7eb7ed}.graph-full-metrics [data-kind=FAMILY] strong{color:#efb765}.graph-full-metrics [data-kind=PLACE] strong{color:#66cbb4}
.graph-full-pilot .graph-query-overview{padding:18px 22px 14px;max-height:none;overflow:visible;background:transparent;border:0;border-radius:0;color:inherit}.graph-canvas-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.graph-full-pilot .graph-canvas-controls button,.graph-full-pilot .graph-canvas-search input,.graph-full-pilot .graph-canvas-search select{color:#edf1ec;background:#1d2428;border:1px solid #ffffff25;min-height:40px;border-radius:5px;font-size:12px}
.graph-full-pilot .graph-canvas-controls button:hover{border-color:#ff7649;color:#ff916d}.graph-full-pilot :focus-visible{outline:2px solid #ff7649;outline-offset:3px}
.graph-full-pilot .graph-canvas-search{display:flex;gap:8px;flex:1;min-width:280px}.graph-full-pilot .graph-canvas-search input{min-width:160px;flex:1;padding:10px 12px}.graph-full-pilot .graph-canvas-search input::placeholder{color:#aeb9b7}.graph-full-pilot .graph-canvas-search select{width:260px;padding:8px;overflow:hidden;text-overflow:ellipsis}.graph-search-status:empty{display:none}.graph-search-status{display:block;font-size:12px;color:#ffac8d;padding:0 0 8px}
.graph-canvas-stage{position:relative}.graph-full-pilot .graph-query-svg{display:block;height:clamp(540px,72vh,880px);max-height:none;border:1px solid #ffffff12;border-radius:8px;background:radial-gradient(ellipse at 35% 40%,#18262a 0%,#101719 50%,#101417 100%);animation:graph-full-reveal .65s ease-out}
.graph-full-pilot .graph-query-svg .graph-node-label{visibility:hidden;pointer-events:none}.graph-full-pilot .graph-query-svg .graph-label-visible .graph-node-label{visibility:visible}
.graph-query-svg .graph-overview-link,.graph-query-svg .graph-overview-node{transition:opacity .18s}.graph-full-pilot .graph-overview-link{opacity:.52}.graph-query-svg.graph-has-focus .graph-overview-link,.graph-query-svg.graph-has-focus .graph-overview-node{opacity:.12}.graph-query-svg.graph-has-focus .graph-related{opacity:1}.graph-query-svg .graph-overview-node.graph-related circle{stroke:#fff;stroke-width:2;filter:drop-shadow(0 0 5px #7eb7ed80)}
.graph-full-pilot .graph-selected circle{stroke:#ff7649;stroke-width:4}.graph-full-pilot .graph-neighborhood-inspector:not([hidden]){position:absolute;right:14px;top:14px;bottom:14px;width:330px;max-width:calc(100% - 28px);overflow:auto;padding:20px;box-sizing:border-box;background:#f8f7f2f5;backdrop-filter:blur(12px);color:#1c2925;border:1px solid #fff7;border-radius:8px;box-shadow:0 12px 35px #0005;font-size:12px;line-height:1.7}
.graph-inspector-header{display:flex;align-items:start;justify-content:space-between;gap:12px}.graph-inspector-header h4{margin:3px 0 10px}.graph-inspector-header button{font-size:11px;padding:6px 9px}.graph-neighborhood-inspector p{overflow-wrap:anywhere}.graph-neighborhood-inspector>p{padding-bottom:14px;border-bottom:1px solid #d8ded7}.graph-neighborhood-inspector button{max-width:100%;white-space:normal;text-align:left}
.graph-canvas-footer{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-top:12px}.graph-canvas-footer>span{font-size:11px;color:#aebcb6;max-width:310px;text-align:right}.graph-full-pilot .graph-type-legend{display:flex;gap:12px;flex-wrap:wrap;margin:0}.graph-full-pilot .graph-type-legend span{padding-left:6px;font-size:10px;color:#cbd6d0}
.graph-scope-details{font-size:11px;line-height:1.8;margin-top:18px;padding-top:12px;border-top:1px solid #ffffff18;color:#afbbb8}.graph-scope-details summary{cursor:pointer}.graph-scope-details p{max-width:1000px}.graph-full-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:0 22px 22px}.graph-full-actions button{background:transparent;color:#e4ebe7;border:1px solid #ffffff2b;font-size:12px;padding:11px 15px}.graph-full-actions button:first-child{background:#ff5b22;border-color:#ff5b22;color:#111;font-weight:600}
.graph-query-overview.graph-expanded{position:fixed;inset:12px;z-index:800;background:#101417;border-radius:12px;box-shadow:0 0 0 20px #101417e6;display:flex;flex-direction:column;overflow:auto}.graph-expanded .graph-canvas-stage{flex:1;min-height:0}.graph-query-overview.graph-expanded .graph-query-svg{height:100%;min-height:350px}.graph-expanded .graph-scope-details{display:none}.graph-expanded .graph-canvas-footer{flex-shrink:0}
@keyframes graph-full-reveal{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@media(prefers-reduced-motion:reduce){.graph-full-pilot .graph-query-svg{animation:none}.graph-query-svg .graph-overview-link,.graph-query-svg .graph-overview-node{transition:none}}
@media(max-width:1100px){.graph-full-hero{flex-wrap:wrap;gap:20px}.graph-full-metrics{gap:24px}.graph-full-pilot .graph-canvas-search select{width:210px}}
.graph-query-overview:fullscreen{box-sizing:border-box;width:100vw;height:100dvh;margin:0;padding:18px;background:#fffefa;display:flex;flex-direction:column;overflow:auto;color:#173f34}.graph-full-pilot .graph-query-overview:fullscreen{background:#101417;color:#fffefa}.graph-query-overview:fullscreen .graph-canvas-stage{flex:1;min-height:250px}.graph-query-overview:fullscreen .graph-query-svg{height:100%!important;min-height:250px}.graph-query-overview:fullscreen .graph-scope-details{display:none}.graph-query-overview:fullscreen .graph-canvas-controls{flex-shrink:0}.graph-query-overview.graph-expanded:not([data-scope=pilot]){background:#fffefa;color:#173f34}
@media(max-width:700px){.graph-full-hero{padding:24px 18px 20px}.graph-full-hero h2{font-size:29px}.graph-full-metrics{width:100%;justify-content:space-between;gap:10px}.graph-full-metrics>div{padding-left:10px}.graph-full-metrics strong{font-size:25px}.graph-full-metrics span{font-size:10px}.graph-full-pilot .graph-query-overview{padding:12px}.graph-full-pilot .graph-canvas-search{flex-basis:100%;min-width:0;flex-direction:column}.graph-full-pilot .graph-canvas-search select{width:100%}.graph-canvas-footer{flex-direction:column;align-items:start}.graph-canvas-footer>span{text-align:left;max-width:none}.graph-full-pilot .graph-neighborhood-inspector:not([hidden]){top:auto;height:45%;width:auto;left:14px}.graph-full-pilot .graph-query-svg{height:570px}.graph-query-overview.graph-expanded{inset:4px}.graph-full-actions{padding:4px 12px 20px}}
`;document.head.append(graphFullStyle);

const graphTooltipStyle=gse('style');graphTooltipStyle.textContent='.graph-edge-tooltip{position:absolute;z-index:6;max-width:310px;box-sizing:border-box;padding:14px 16px;border-radius:8px;background:#fffefa;color:#173e35;border:1px solid #c9d8cf;box-shadow:0 8px 30px #0005;pointer-events:none;font-size:12px;line-height:1.6;overflow-wrap:anywhere}.graph-edge-tooltip[hidden]{display:none}.graph-edge-tooltip strong{display:block}.graph-edge-tooltip p{margin:8px 0 2px!important;font-size:12px!important}.graph-edge-tooltip small{display:block;font-size:10px}.graph-query-svg .graph-edge-hover{opacity:1!important}.graph-edge-hover path:last-of-type{stroke:#ff966c;stroke-width:4}';document.head.append(graphTooltipStyle);

const citationSummaryStyle=gse('style');citationSummaryStyle.textContent=`
.graph-citation-summary{white-space:normal;border-bottom:1px solid #cddbd4;padding:0 0 18px;margin:0 0 20px;font-size:13px;line-height:1.6}
.graph-citation-summary>strong{font-size:15px;color:#184d40;display:block;margin-bottom:8px}
.graph-citation-summary p{margin:6px 0!important}.graph-citation-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.graph-citation-actions button{font-size:12px;padding:8px 12px;background:#fffefa;border:1px solid #bccdc4;border-radius:6px}
.graph-citation-link{font-size:.85em;padding:2px 7px;margin:0 2px;font-weight:600;vertical-align:baseline}
.graph-citation-link:focus-visible{outline:2px solid #126455;outline-offset:3px}.graph-citation-source{flex-wrap:wrap;border-top:1px solid #e0e5de;padding:12px 0}
.graph-citation-source>div{flex:1;min-width:210px}.graph-citation-source [role=alert]:empty{display:none}.graph-citation-source [role=alert]{flex-basis:100%;color:#9e411c}
`;document.head.append(citationSummaryStyle);

// The legend acts as a visual focus control without changing source scope.
(()=>{const style=document.createElement('style');style.textContent=`
.graph-type-legend button{display:inline-flex;align-items:center;gap:6px;padding:6px 8px;font:inherit;font-size:10px;border:1px solid #cbd5ca;border-radius:5px;background:transparent;color:#526459;cursor:pointer}
.graph-type-legend button:before{content:'';width:6px;height:6px;border-radius:50%;background:var(--entity-color);flex-shrink:0}
.graph-type-legend button small{font-size:9px;opacity:.7;font-variant-numeric:tabular-nums}
.graph-type-legend button[aria-pressed=true]{border-color:#527e68;background:#e8f0e5;color:#234c37}
.graph-full-pilot .graph-type-legend{gap:6px!important;margin:0 0 12px!important}
.graph-full-pilot .graph-type-legend button{color:#b7c7c4;border-color:#ffffff20;background:#192427}
.graph-full-pilot .graph-type-legend button[aria-pressed=true]{color:#fff;border-color:var(--entity-color);background:#293b3d}
.graph-type-legend button:hover{border-color:var(--entity-color)}
.graph-zoom-status{font-size:10px;color:#6a8175;min-width:34px;text-align:center;font-variant-numeric:tabular-nums}
.graph-full-pilot .graph-zoom-status{color:#acbeb8}
.graph-query-svg.graph-no-matches .graph-overview-node,.graph-query-svg.graph-no-matches .graph-overview-link{opacity:.08}
`;document.head.append(style)})();

const graphOnlyStyle=gse('style');graphOnlyStyle.textContent=`
.graph-query-overview:is(:fullscreen,.graph-only-expanded){box-sizing:border-box;position:fixed;inset:0;z-index:950;width:100%;height:100dvh;max-height:none;margin:0!important;padding:14px!important;background:#10191c!important;color:#e4eeeb!important;display:flex;flex-direction:column;overflow:hidden}
.graph-query-overview:is(:fullscreen,.graph-only-expanded)>.graph-canvas-stage{flex:1;min-height:0!important;position:relative}
.graph-query-overview:is(:fullscreen,.graph-only-expanded) .graph-query-svg{height:100%!important;min-height:0!important}
.graph-query-overview:is(:fullscreen,.graph-only-expanded) .graph-webgl{position:absolute!important;inset:0;height:100%!important;min-height:0!important}
.graph-query-overview:is(:fullscreen,.graph-only-expanded)>summary,.graph-query-overview:is(:fullscreen,.graph-only-expanded)>.graph-scope-details{display:none}
.graph-query-overview:is(:fullscreen,.graph-only-expanded) .graph-canvas-controls{flex-shrink:0}
`;document.head.append(graphOnlyStyle);
