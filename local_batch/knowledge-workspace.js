// A question owns its answer, retrieved evidence and hypothesis diagram.
// Answers, relationships and an automatically generated fishbone share one workspace.
(()=>{
 const x=window.KnowledgeExplorer;if(!x)return;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n},t=(es,en,fr)=>({es,en,fr})[uiLanguage]||es;
 const btn=(text,fn)=>{const n=el('button',text);n.type='button';n.onclick=fn;return n},sid=()=>ResearchSessions.id;
 const req=x.json,pk=r=>JSON.stringify([r.document_id,r.page,r.version||'original']);
 const terminal=s=>['complete','complete_with_errors','failed','interrupted'].includes(s);
 let current=null,kind='knowledge_graph',selected='',runs=[],busy=false,refreshing=false,epoch=0,renderStamp='',answerCleanup=null,publishedRun='';
 let fishStamp='',followup=null,fishLoading=false;let generating=false;let lastInspection=null;let representation='graph',manifest=null,focused=null,diagram=null,diagramDirty=false,diagramSaving=false,branch=0,auto=null,autoTimer=null,graphDrawn=false;
 const shell=el('div');shell.className='knowledge-workspace';shell.dataset.noI18n='';
 const sidebar=el('dialog');sidebar.className='kw-history-dialog';sidebar.dataset.noI18n='';document.body.append(sidebar);const center=el('div');center.className='kw-center';
 const sources=el('aside');sources.className='kw-sources';sources.hidden=true;const session=el('div');session.className='kw-session';
 const toolbar=el('div');toolbar.className='kw-toolbar';const pipeline=el('div');pipeline.className='kw-pipeline';pipeline.setAttribute('role','status');const tabs=el('div');tabs.className='kw-view-tabs';tabs.setAttribute('role','tablist');const context=el('div');context.className='kw-context';
 const panels={answer:el('div'),graph:el('div'),fishbone:el('div'),evidence:el('div'),inventory:x.inventory,catalog:x.catalog};
 for(const [name,panel]of Object.entries(panels)){panel.dataset.representation=name;panel.classList.add('kw-panel');panel.hidden=true}
 const graphResult=el('div');panels.graph.append(x.fullGraph,graphResult);const history=el('div');history.className='kw-history';
 const scope=el('select');scope.id='kw-question-scope';const scopeLabel=el('label');scopeLabel.append(scope);
 x.question.rows=4;x.question.maxLength=1000;const advanced=el('details');advanced.className='kw-options';advanced.append(el('summary'),x.form.querySelector('.graph-question-options'),x.help);
 x.form.querySelector('.graph-question-options')?.remove();x.form.prepend(scopeLabel);x.form.append(advanced);x.examples.remove();x.questions.remove();x.tabs.remove();x.result.remove();x.historyLabel.remove();
 const evidenceDetails=el('div');evidenceDetails.className='kw-evidence-details';evidenceDetails.append(panels.evidence);
 const historyClose=btn('×',()=>sidebar.close());historyClose.className='kw-dialog-close';sidebar.append(historyClose,history);
 const tools=el('div');tools.className='kw-session-toolbar';tools.append(session,toolbar);
 const sourceFilterHost=el('div'),rail=el('aside'),railTitle=el('h2');rail.className='kw-query-rail';rail.id='kw-query-rail';railTitle.className='kw-rail-title';
 const suggestions=el('details');suggestions.className='kw-suggestions';suggestions.append(el('summary'),x.examples);
 const statusDetails=el('details');statusDetails.className='kw-status-details';const statusSummary=el('summary');statusDetails.append(statusSummary,x.availability);
 const railToggle=btn('',()=>{if(!sources.hidden&&matchMedia('(min-width:801px) and (max-width:1550px)').matches){closeSources();shell.classList.remove('kw-rail-collapsed')}else shell.classList.toggle('kw-rail-collapsed');paintRailToggle()});railToggle.className='kw-rail-toggle';railToggle.setAttribute('aria-controls',rail.id);
 const tabbar=el('div');tabbar.className='kw-tabbar';tabbar.append(tabs,railToggle);
 const returnGraph=btn(t('← Volver al grafo original','← Return to original graph','← Revenir au graphe initial'),()=>newQuestion(true));returnGraph.className='kw-return-graph';tabbar.prepend(returnGraph);
 const exitFullscreen=btn(t('Salir de pantalla completa','Exit full screen','Quitter le plein écran'),async()=>{if(document.fullscreenElement===shell)await document.exitFullscreen();shell.classList.remove('graph-expanded')});exitFullscreen.className='kw-fullscreen-exit';tabbar.append(exitFullscreen);
 rail.append(railTitle,x.form,suggestions,sourceFilterHost);
 center.append(context,tabbar,pipeline,panels.answer,panels.graph,panels.fishbone,evidenceDetails,panels.inventory,panels.catalog);shell.append(tools,statusDetails,rail,center,sources);x.view.append(shell);x.view.classList.add('kw-view');
 const sourceFilters=createKnowledgeSourceFilters(sourceFilterHost,()=>{if(sourceFilters.active)x.mode.value='local';x.mode.disabled=scope.value==='selection'||sourceFilters.active;closeSources();if(['inventory','catalog'].includes(representation))choose(representation);else syncLayout()});
 sources.setAttribute('aria-label',t('Fuentes e hipótesis','Sources and hypotheses','Sources et hypothèses'));
 function closeSources(){const returnFocus=sources.contains(document.activeElement);sources.hidden=true;shell.classList.remove('kw-inspecting');lastInspection=null;paintRailToggle();if(returnFocus)tabButtons.get(representation)?.focus()}
 window.addEventListener('keydown',e=>{if(e.key==='Escape'&&!sources.hidden)closeSources()});
 function paintRailToggle(){const collapsed=shell.classList.contains('kw-rail-collapsed'),covered=!sources.hidden&&matchMedia('(min-width:801px) and (max-width:1550px)').matches;railToggle.textContent=collapsed||covered?t('Mostrar consulta','Show query','Afficher la question'):t('Ocultar consulta','Hide query','Masquer la question');railToggle.setAttribute('aria-expanded',String(!collapsed&&!covered));rail.hidden=collapsed}
 function focusQuestion(){shell.classList.remove('kw-rail-collapsed');if(matchMedia('(min-width:801px) and (max-width:1550px)').matches)closeSources();paintRailToggle();x.question.focus()}
 window.addEventListener('resize',paintRailToggle);
 const sharedFiltersHost=el('div');tabbar.after(sharedFiltersHost);const sharedFilters=mountKnowledgeFilters(sharedFiltersHost);
 window.addEventListener('knowledge-filter-change',event=>{if(event.detail.origin==='graph')return;closeSources();if(['inventory','catalog'].includes(representation))choose(representation);else if(representation==='graph'){if(current){graphDrawn=false;drawGraph()}else x.drawFullGraph()}});
 const iconPaths={graph:'M4 5L12 12L20 5M12 12L6 20M12 12L20 19M2 3h4v4H2zM10 10h4v4h-4zM18 3h4v4h-4zM4 18h4v4H4zM18 17h4v4h-4z',answer:'M3 3h18v14H8l-5 4zM7 7h10M7 11h7',fishbone:'M2 12h20M6 5l5 7-5 7M13 5l5 7-5 7',evidence:'M5 2h10l4 4v16H5zM15 2v5h4M8 11h8M8 15h8',inventory:'M12 3a4 4 0 1 0 0 8a4 4 0 0 0 0-8M4 22v-3a8 8 0 0 1 16 0v3',catalog:'M8 8l8 8M2 2h7v7H2zM15 15h7v7h-7zM13 9l6 0 0-6'};
 function tabIcon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');svg.classList.add('kg-tab-icon');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',iconPaths[name]);path.setAttribute('fill','none');path.setAttribute('stroke','currentColor');path.setAttribute('stroke-width','1.6');path.setAttribute('stroke-linejoin','round');svg.append(path);return svg}
 const tabLabels=()=>({graph:t('Grafo','Graph','Graphe'),answer:t('Respuesta','Answer','Réponse'),fishbone:t('Hipótesis','Hypotheses','Hypothèses'),evidence:t('Fuentes','Sources','Sources'),inventory:t('Entidades','Entities','Entités'),catalog:t('Relaciones','Relationships','Relations')});
 const tabButtons=new Map();
 for(const name of ['graph','answer','fishbone','evidence','inventory','catalog']){const b=btn('',()=>choose(name));b.id='kw-tab-'+name;b.dataset.tab=name;b.setAttribute('role','tab');b.setAttribute('aria-controls','kw-panel-'+name);tabButtons.set(name,b);tabs.append(b);panels[name].id='kw-panel-'+name;panels[name].setAttribute('role','tabpanel');panels[name].setAttribute('aria-labelledby',b.id);panels[name].tabIndex=0}
 tabs.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;const available=[...tabButtons.values()].filter(b=>!b.disabled),index=available.indexOf(document.activeElement);if(index<0)return;event.preventDefault();const next=event.key==='Home'?0:event.key==='End'?available.length-1:(index+(event.key==='ArrowRight'?1:-1)+available.length)%available.length;available[next].click();available[next].focus()};
 
 // Remove the old standalone form container and its empty explanatory material.
 x.fullGraph.hidden=false;
 const draftKey=()=>`maph-question-fishbone:${kind}:${selected}`;
 const params=()=>new URLSearchParams({query_id:selected,query_kind:kind,...(sid()?{session_id:sid()}: {})});
 const evidenceURL=()=>'/research-workspace/evidence?'+new URLSearchParams({id:selected,kind,...(sid()?{session_id:sid()}: {})});
 const artifactURL=()=>'/hypotheses?'+params();
 const contextQuestion=()=>current?.question||current?.questions?.[0]||'';
 const message=(text)=>{x.feedback.textContent=text};
 function persistView(){sessionStorage.setItem('maph-investigation:'+ (sid()||'unassigned'),JSON.stringify({selected,kind,representation}))}
 function caption(){
  context.replaceChildren(el('small',current?t('PREGUNTA ACTIVA','ACTIVE QUESTION','QUESTION ACTIVE'):t('EXPLORACIÓN DEL ARCHIVO','ARCHIVE EXPLORATION','EXPLORATION DES ARCHIVES')),el('h2',current?contextQuestion():t('Un archivo. Muchas conexiones.','One archive. Many connections.','Une archive. De nombreux liens.')));
  const label=current?(kind==='matrix'?t('Lecturas guardadas de la sesión','Saved session readings','Lectures enregistrées de la session'):t('Contexto recuperado del piloto','Context retrieved from the pilot','Contexte récupéré du pilote')):t('Explora el piloto o formula una pregunta para comenzar.','Explore the pilot or ask a question to begin.','Explorez le pilote ou posez une question pour commencer.');
  context.append(el('p',label+(manifest?' · '+manifest.pages.length+' '+t('lecturas de origen','source readings','lectures sources'):'')));
  if(current?.source_filters&&Object.values(current.source_filters).some(v=>v.length))context.append(el('p',t(`Alcance de esta respuesta: ${current.scope_pages} páginas de ${current.scope_documents} documentos.`,`Scope of this answer: ${current.scope_pages} pages from ${current.scope_documents} documents.`,`Portée de cette réponse : ${current.scope_pages} pages de ${current.scope_documents} documents.`)));
 }
 function paintPipeline(){pipeline.replaceChildren();pipeline.hidden=!current;if(!current)return;
  const answered=terminal(current.status)&&!['failed','interrupted'].includes(current.status),fs=auto?.status||followup?.status;
  const steps=[[t('Respuesta','Answer','Réponse'),answered?'done':'active'],[t('Relaciones y fuentes','Relationships and sources','Relations et sources'),manifest?'done':'pending'],[t('Espina automática','Automatic fishbone','Diagramme automatique'),fs&&terminal(fs)?(['failed','interrupted','complete_with_errors'].includes(fs)?'warning':'done'):answered&&current.auto_fishbone?'active':'pending']];
  steps.forEach(([label,state],i)=>{const n=el('span');n.className='kw-step '+state;n.append(el('b',state==='done'?'✓':String(i+1)),document.createTextNode(label));pipeline.append(n)});
  const state=el('small',!answered?statusName(current.status):fs&&!terminal(fs)?t('Puedes leer la respuesta mientras se construye la espina.','Read the answer while the fishbone is being built.','Lisez la réponse pendant la construction du diagramme.'):fs==='complete_with_errors'?t('Espina parcial: hay pasajes que no pudieron procesarse.','Partial fishbone: some passages could not be processed.','Diagramme partiel : certains passages n’ont pas pu être traités.'):t('Explora los hallazgos y comprueba sus fuentes.','Explore the findings and check their sources.','Explorez les résultats et vérifiez leurs sources.'));pipeline.append(state);
 }

 function statusName(status){return ({queued:t('En cola','Queued','En attente'),loading:t('Cargando modelo','Loading model','Chargement du modèle'),running:t('Examinando las lecturas','Examining readings','Examen des lectures'),complete_with_errors:t('Finalizado con errores: revisa el detalle','Finished with errors: check details','Terminé avec erreurs : consulter le détail')})[status]||gResolve(x.stateName(status))}
 function paintControls(){
  gSet(x.heading.querySelector('p'),t('Pregunta, explora relaciones y organiza hipótesis con sus fuentes en tu sesión de investigación.','Ask questions, explore relationships and organize source-linked hypotheses in your research session.','Posez des questions, explorez les relations et organisez des hypothèses sourcées dans votre session de recherche.'));

  session.replaceChildren(el('small',t('ESPACIO DE INVESTIGACIÓN','RESEARCH WORKSPACE','ESPACE DE RECHERCHE')),el('strong','Knowledge Graph'),el('span',ResearchSessions.current?.title||t('Exploración del archivo','Archive exploration','Exploration des archives')));
  if(ResearchSessions.current?.objective)session.append(el('span',ResearchSessions.current.objective));

  const old=scope.value;scope.replaceChildren();for(const [value,label]of [['pilot',t('Knowledge Graph · versión publicada','Knowledge Graph · published version','Knowledge Graph · version publiée')],['selection',t('Mi selección · lecturas de esta sesión','My selection · this session’s readings','Ma sélection · lectures de cette session')]]){const o=el('option',label);o.value=value;scope.append(o)}scope.value=old||'pilot';scopeLabel.firstChild!==scope&&scopeLabel.firstChild.remove();scopeLabel.prepend(document.createTextNode(t('Dónde buscar respuestas','Where to find answers','Où chercher les réponses')));
  advanced.querySelector('summary').textContent=t('Método, responsable y alcance','Method, author and scope','Méthode, responsable et portée');
  if(sourceFilters.active)x.mode.value='local';x.mode.disabled=scope.value==='selection'||sourceFilters.active;sourceFilters.setEnabled(scope.value==='pilot');sourceFilters.setLocked(!!current);gSet(x.send,t('Preguntar y analizar →','Ask and analyze →','Interroger et analyser →'));drawSelectionCount();
  toolbar.replaceChildren(btn(t('← Grafo original','← Original graph','← Graphe initial'),()=>newQuestion(true)),btn(t('Historial de preguntas','Question history','Historique des questions'),()=>sidebar.showModal()),btn(t('Mi selección','My selection','Ma sélection'),()=>showView('selection')));
  toolbar.prepend(btn(t('Nueva pregunta','New question','Nouvelle question'),()=>newQuestion()));
  historyClose.setAttribute('aria-label',t('Cerrar historial','Close history','Fermer l’historique'));
  railTitle.textContent=t('Pregunta al archivo','Ask the archive','Interroger les archives');rail.setAttribute('aria-label',railTitle.textContent);
  suggestions.querySelector('summary').textContent=t('Ideas para comenzar','Ideas to get started','Idées pour commencer');
  tabs.setAttribute('aria-label',t('Vistas de la investigación','Research views','Vues de recherche'));
  for(const [name,b]of tabButtons)b.replaceChildren(tabIcon(name),document.createTextNode(tabLabels()[name]));sharedFilters.paint();
  if(!statusSummary.textContent)statusSummary.textContent=t('Conectando con el archivo…','Connecting to the archive…','Connexion aux archives…');
  paintRailToggle();
  let note=x.form.querySelector('.kw-auto-note');if(!note){note=el('p');note.className='kw-auto-note';x.form.append(note)}note.textContent=t('Respuesta + relaciones + espina automática, con fuentes y procesamiento local.','Answer + relationships + automatic fishbone, with sources and local processing.','Réponse + relations + diagramme automatique, avec sources et traitement local.');
  drawHistory();caption();paintPipeline();syncLayout();
 }

 scope.onchange=()=>{paintControls();message(scope.value==='selection'?t('Se responderá por cada lectura seleccionada y guardada. Esto no reconstruye el grafo del piloto.','Each saved selected reading will be examined. This does not rebuild the pilot graph.','Chaque lecture sélectionnée et enregistrée sera examinée. Le graphe du pilote ne sera pas reconstruit.'):t('La recuperación consulta las fuentes elegidas de la versión publicada.','Retrieval uses the chosen sources from the published version.','La recherche utilise les sources choisies de la version publiée.'))};
 function syncLayout(){
  if(!current&&['answer','fishbone','evidence'].includes(representation))representation='graph';
  for(const [name,panel]of Object.entries(panels)){panel.hidden=name!==representation;const b=tabButtons.get(name);b.disabled=!current&&['answer','fishbone','evidence'].includes(name);b.setAttribute('aria-selected',String(name===representation));b.tabIndex=name===representation?0:-1;b.title=b.disabled?t('Disponible al realizar una pregunta','Available after asking a question','Disponible après une question'):''}
  // Keep large catalogs out of the live DOM while retaining their filters and rows.
  for(const name of ['inventory','catalog']){if(name===representation)center.append(panels[name]);else panels[name].remove()}
  evidenceDetails.hidden=representation!=='evidence';
  shell.dataset.representation=representation;returnGraph.hidden=!current;returnGraph.textContent=t('← Volver al grafo original','← Return to original graph','← Revenir au graphe initial');
  const hasQueryGraph=!!current;
  x.fullGraph.hidden=hasQueryGraph;graphResult.hidden=!current;
  if(!hasQueryGraph&&representation==='graph')x.drawFullGraph();
 }
 function choose(name){
  if(!tabButtons.has(name)||(!current&&['answer','fishbone','evidence'].includes(name)))return;
  representation=name;syncLayout();center.scrollTop=0;persistView();
  if(current&&['inventory','catalog'].includes(name)){
   const host=panels[name],graph=KnowledgeGraphFilters.filter(filteredGraph());host.replaceChildren(el('h3',name==='inventory'?t('Entidades de esta pregunta','Entities for this question','Entités de cette question'):t('Relaciones de esta pregunta','Relationships for this question','Relations de cette question')),el('p',contextQuestion()));
   const names=new Map(graph.nodes.map(n=>[n.id,n.label]));
   const items=name==='inventory'?graph.nodes:graph.relationships;
   if(!items.length)host.append(el('p',t('No se recuperaron elementos para esta pregunta con los filtros actuales.','No items retrieved for this question with the current filters.','Aucun élément retrouvé pour cette question avec les filtres actuels.')));
   for(const item of items){const row=el('article');row.className='kw-query-scope-row';row.append(el('strong',name==='inventory'?item.label:(names.get(item.source)||item.source)+' → '+(names.get(item.target)||item.target)),el('p',name==='inventory'?(item.description||item.type||''):(item.fields?.relation||item.description||'')));const pages=name==='inventory'?(item.mentions||[]).map(m=>m.page):[item.page];const seen=new Set();for(const page of pages){if(!page||seen.has(pk(page)))continue;seen.add(pk(page));row.append(btn(page.document+' · p. '+page.page,()=>openSource(page)))}host.append(row)}return;
  }
  if(['inventory','catalog'].includes(name)){
   if(name==='inventory'&&!panels.inventory.children.length)panels.inventory.append(el('p',t('Cargando entidades…','Loading entities…','Chargement des entités…')));
   if(name==='catalog')graphPilotRefresh(true).catch(e=>message(e.message));
   else req('/knowledge-graph').then(data=>{graphEntitiesRender(x.inventory,data.result?GraphResultCore.filterSources(data.result,sourceFilters.get()):null)}).catch(e=>message(e.message));return;
  }
  if(name==='fishbone')drawFishbone();if(name==='graph'&&current)drawGraph();if(name==='evidence')drawEvidence();
 }
 function newQuestion(full=false){if(full)sourceFilters.setLocked(false);if(full)KnowledgeGraphFilters.clear('graph');if(full)sourceFilters.set({});epoch++;representation='graph';fishStamp='';followup=null;selected='';current=null;manifest=null;focused=null;diagram=null;diagramDirty=false;auto=null;clearTimeout(autoTimer);closeSources();renderStamp='';graphDrawn=false;answerCleanup?.();answerCleanup=null;panels.answer.replaceChildren();graphResult.replaceChildren();x.question.value='';x.progress.update(null);paintControls();syncLayout();persistView();if(!full)focusQuestion()}
 const hiddenHistoryKey=()=> 'maph-hidden-knowledge-history:'+(sid()||'unassigned');
 function hiddenHistory(){try{return new Set(JSON.parse(localStorage.getItem(hiddenHistoryKey())||'[]'))}catch{return new Set()}}
 function setHistoryHidden(key,hidden){const items=hiddenHistory();if(hidden)items.add(key);else items.delete(key);localStorage.setItem(hiddenHistoryKey(),JSON.stringify([...items]));drawHistory()}
 function drawHistory(){
  history.replaceChildren(el('h3',t('Preguntas de esta sesión','Questions in this session','Questions de cette session')));
  const hidden=hiddenHistory(),visible=runs.filter(r=>!hidden.has(r.kind+':'+r.id));
  if(!visible.length)history.append(el('p',t('Tus preguntas aparecerán aquí.','Your questions will appear here.','Vos questions apparaîtront ici.')));
  for(const r of visible){const b=btn(r.question||r.questions?.join(' · ')||t('Pregunta guardada','Saved question','Question enregistrée'),()=>{sidebar.close();open(r.kind,r.id)});b.className='kw-history-item';b.setAttribute('aria-pressed',String(r.id===selected&&r.kind===kind));b.append(el('small',(r.kind==='matrix'?t('Selección','Selection','Sélection'):'Knowledge Graph')+' · '+statusName(r.status)));const row=el('div');row.className='kw-history-row';row.append(b);if(r.kind==='knowledge_graph'){const remove=btn(t('🗑 Quitar del historial','🗑 Remove from history','🗑 Retirer de l’historique'),()=>{const key=r.kind+':'+r.id;setHistoryHidden(key,true);if(selected===r.id&&kind===r.kind)newQuestion(true);const undo=el('p',t('Pregunta retirada de tu historial. ','Question removed from your history. ','Question retirée de votre historique. '));undo.setAttribute('role','status');undo.append(btn(t('Deshacer','Undo','Annuler'),()=>{setHistoryHidden(key,false)}));history.prepend(undo)});remove.className='kw-history-remove';remove.setAttribute('aria-label',t('Quitar del historial: ','Remove from history: ','Retirer de l’historique : ')+(r.question||r.id));row.append(remove)}history.append(row)}
  if(hidden.size){const restore=btn(t('Restaurar preguntas retiradas','Restore removed questions','Restaurer les questions retirées'),()=>{localStorage.removeItem(hiddenHistoryKey());drawHistory()});history.append(restore)}
 }
 async function refresh(){
  if(refreshing)return;refreshing=true;const sessionId=sid(),turn=epoch;
  try{
   const [status,all,matrices]=await Promise.all([req('/knowledge-graph/status'),req('/knowledge-graph/questions'),sid()?req('/research-sessions/jobs?id='+sid()):Promise.resolve([])]);
   if(sessionId!==sid()||turn!==epoch)return;
   if(publishedRun!==status.available_run){publishedRun=status.available_run;if(!current&&representation==='graph')x.drawFullGraph();else if(['inventory','catalog'].includes(representation))choose(representation)}
   runs=[...all.filter(r=>(r.session_id||null)===sessionId).map(r=>({...r,kind:'knowledge_graph'})),...matrices.filter(r=>r.kind==='matrix'&&r.questions?.length===1)].sort((a,b)=>b.created-a.created);
   drawHistory();const available=status.available_pages||0,building=status.control?.status==='running'||(!status.control?.status&&['starting','graph','embeddings','query'].includes(status.status));
   let scopeNote=x.form.querySelector('.kw-index-scope');if(!scopeNote){scopeNote=el('p');scopeNote.className='kw-index-scope';x.form.prepend(scopeNote)}scopeNote.textContent=available!==status.indexed_pages?t(`Grafo visible: ${available} páginas. Preguntas GraphRAG: ${status.indexed_pages} páginas del último índice completo. Puedes preguntar a las nuevas páginas desde Mi selección.`,`Visible graph: ${available} pages. GraphRAG questions: ${status.indexed_pages} pages in the last complete index. Query new pages from My selection.`,`Graphe visible : ${available} pages. Questions GraphRAG : ${status.indexed_pages} pages du dernier index complet. Interrogez les nouvelles pages depuis Ma sélection.`):'';
   x.availability.textContent=status.result_ready?t(`Grafo disponible: ${available} páginas. Las correcciones posteriores no reconstruyen esta versión automáticamente.`,`Available graph: ${available} pages. Later corrections do not automatically rebuild this version.`,`Graphe disponible : ${available} pages. Les corrections ultérieures ne reconstruisent pas automatiquement cette version.`):t('El grafo aún no está disponible. Consulta su proceso en Resumen.','The graph is not available yet. Check its process in Overview.','Le graphe n’est pas encore disponible. Consultez son état dans le résumé.');
   if(building)x.availability.textContent+=' '+t(`Ampliación en curso a ${status.manifest?.total||0} páginas. Puedes explorar la versión publicada; las preguntas con IA tienen prioridad y pausan automáticamente la construcción.`,`Expansion to ${status.manifest?.total||0} pages is in progress. You can explore the published version; AI questions take priority and automatically pause the build.`,`Extension à ${status.manifest?.total||0} pages en cours. Vous pouvez explorer la version publiée ; les questions IA sont prioritaires et suspendent automatiquement la construction.`);
   if(status.source_changes?.archived_pages)x.availability.textContent+=' '+t(`Atención: esta versión aún contiene ${status.source_changes.archived_pages} páginas de fuentes retiradas. Las búsquedas normales ya las excluyen; Knowledge Graph necesita reconstruirse para excluirlas.`,`Warning: this version still contains ${status.source_changes.archived_pages} pages from archived sources. Regular searches already exclude them; Knowledge Graph must be rebuilt to exclude them.`,`Attention : cette version contient encore ${status.source_changes.archived_pages} pages de sources retirées. Les recherches ordinaires les excluent déjà ; Knowledge Graph doit être reconstruit pour les exclure.`);
   statusSummary.textContent=(status.result_ready?t(`Grafo disponible · ${available} páginas`,`Graph available · ${available} pages`,`Graphe disponible · ${available} pages`):t('Grafo en preparación','Graph in preparation','Graphe en préparation'))+(building?t(' · Ampliación en curso',' · Expansion in progress',' · Extension en cours'):'')+(status.source_changes?.archived_pages?t(' · Fuentes retiradas: ver detalle',' · Archived sources: view details',' · Sources retirées : voir le détail'):'');
   statusDetails.dataset.state=status.source_changes?.archived_pages?'warning':status.result_ready?'ready':'pending';
   if(selected)await loadCurrent(turn);x.send.disabled=busy;
  }catch(e){message(e.message);statusDetails.dataset.state='warning';statusSummary.textContent=t('Sin conexión · ver detalle','Disconnected · view details','Déconnecté · voir le détail');x.availability.textContent=e.message}finally{refreshing=false}
 }
 async function open(nextKind,id){
  epoch++;representation='answer';fishStamp='';followup=null;clearTimeout(autoTimer);kind=nextKind;selected=id;current=null;manifest=null;diagram=null;diagramDirty=false;focused=null;auto=null;renderStamp='';graphDrawn=false;const turn=epoch;
  sources.hidden=true;shell.classList.remove('kw-inspecting');panels.answer.replaceChildren(el('p',t('Cargando investigación…','Loading investigation…','Chargement de la recherche…')));
  try{await loadCurrent(turn);if(turn===epoch){paintControls();persistView()}}catch(e){message(e.message)}
 }
 async function loadCurrent(turn=epoch){
  const id=selected,k=kind;const value=await req((k==='matrix'?'/matrix?id=':'/knowledge-graph/questions?id=')+id);
  if(turn!==epoch||selected!==id||kind!==k)return;
  if((value.session_id||null)!==sid())throw Error(t('La pregunta pertenece a otra sesión.','The question belongs to another session.','La question appartient à une autre session.'));
  if(current?.id!==value.id){sourceFilters.set(value.source_filters);sourceFilters.setLocked(true)}
  const becameComplete=current?.status!=='complete'&&value.status==='complete';current=value;const stamp=JSON.stringify([id,value.status,value.updated,value.completed,value.provenance_version]);if(stamp!==renderStamp){renderStamp=stamp;renderAnswer();caption();drawGraph();drawFishbone()}
  if(k==='knowledge_graph')x.progress.update(value);else x.progress.update(null);
  if(terminal(value.status)&&!['failed','interrupted'].includes(value.status)&&!manifest){
   try{const m=await req(evidenceURL());if(turn!==epoch)return;manifest=m;caption();drawEvidence()}
   catch(e){message(e.message)}
  }
  if(becameComplete&&k==='knowledge_graph'){representation='graph';graphDrawn=false;drawGraph();persistView()}
  syncLayout();paintPipeline();if(terminal(value.status)&&manifest)await refreshDiagram(turn);
 }
 x.form.onsubmit=async event=>{
  event.preventDefault();if(busy||!x.form.reportValidity())return;
  busy=true;x.send.disabled=true;const sessionId=sid(),text=x.question.value,matrix=scope.value==='selection';
  try{
   if(!await ResearchSessions.flush()||sessionId!==sid())return;
   if(matrix&&(!sid()||!matrixSelection.size))throw Error(t('Crea una sesión y selecciona lecturas antes de consultar esta opción.','Create a session and select readings first.','Créez une session et sélectionnez des lectures.'));
   const common={session_id:sessionId,author:x.author.value||ResearchSessions.current?.researcher||'',auto_fishbone:true,language:uiLanguage};
   const payload=matrix?{...common,questions:[text],records:[...matrixSelection.values()].map(({document_id,page,version})=>({document_id,page,version}))}:{...common,question:text,mode:x.mode.value,source_filters:sourceFilters.get(),pilot_run:sourceFilters.queryRun};
   message(t('Guardando pregunta y preparando el análisis…','Saving question and preparing the analysis…','Enregistrement de la question et préparation de l’analyse…'));
   const value=await req(matrix?'/matrix':'/knowledge-graph/questions',payload);if(sessionId!==sid())return;
   ResearchSessions.log(matrix?'session_question':'knowledge_graph',text,{job_id:value.id,scope:scope.value,mode:matrix?'per_reading':x.mode.value,pilot_run:value.pilot_run,source_filters:matrix?null:sourceFilters.get(),auto_fishbone:true});
   await open(matrix?'matrix':'knowledge_graph',value.id);message(t('El análisis continúa aunque cierres esta página.','Analysis continues even if you close this page.','L’analyse continue même si vous fermez cette page.'));await refresh();
  }catch(e){message(e.message)}finally{busy=false;x.send.disabled=false}
 };
 function renderAnswer(){
  answerCleanup?.();answerCleanup=null;const host=panels.answer;host.replaceChildren();if(!current)return;host.append(el('h3',t('Lo que dicen los documentos','What the documents say','Ce que disent les documents')));
  const bar=el('div');bar.className='kw-actions';bar.append(btn(t('Usar de nuevo la pregunta','Reuse question','Réutiliser la question'),()=>{x.question.value=contextQuestion();scope.value=kind==='matrix'?'selection':'pilot';scope.onchange();x.question.focus()}),btn(t('Descargar respuesta y registro','Download answer and record','Télécharger la réponse et le registre'),()=>priorityDownload(JSON.stringify(current,null,2),'question-'+selected+'.json','application/json')));host.append(bar);
  if(!terminal(current.status)){host.append(el('h3',statusName(current.status)),el('p',kind==='matrix'?(current.completed||0)+' / '+current.total+' '+t('lecturas procesadas','readings processed','lectures traitées'):t('El estado del modelo se muestra junto a la pregunta.','Model status is shown alongside the question.','L’état du modèle apparaît à côté de la question.')));return}
  if(current.error)host.append(el('p',current.error));if(current.grounding_policy==='legacy_mixed_local_prompt')host.append(el('p',t('Respuesta histórica: se generó antes de reforzar las instrucciones de uso exclusivo de las fuentes. Comprueba sus referencias.','Historical answer: generated before strengthening source-only instructions. Check its references.','Réponse historique : produite avant le renforcement des instructions limitant la réponse aux sources. Vérifiez ses références.')));
  if(kind==='knowledge_graph'){const body=el('div');body.className='graph-query-answer';host.append(body);answerCleanup=graphQueryAnswer(body,current)}
  else{for(const cell of current.cells||[]){const row=current.rows[cell.row],article=el('article');article.className='kw-answer-row';article.append(btn(row.document+' · p. '+row.page,()=>openSource(row)),el('small',cell.status));for(const part of cell.parts||[]){if(part.answer)article.append(el('p',part.answer));for(const quote of part.evidence_quotes||[part.evidence_quote])if(quote)article.append(btn('“'+quote+'”',()=>openSource(row,quote)))}host.append(article)}}
  host.append(el('p',t('Las respuestas y las relaciones propuestas requieren corroboración en las fuentes. El grafo no demuestra causalidad.','Answers and proposed relationships need source verification. The graph does not establish causality.','Les réponses et les relations proposées doivent être vérifiées dans les sources. Le graphe ne démontre pas la causalité.')));
  const actions=el('div');actions.className='kw-actions';actions.append(btn(t('Ver relaciones','View relationships','Voir les relations'),()=>choose('graph')),btn(t('Ver espina','View fishbone','Voir le diagramme'),()=>choose('fishbone')),btn(t('Comprobar evidencias','Check evidence','Vérifier les preuves'),()=>choose('evidence')));host.append(actions);
  const details=el('details');details.append(el('summary',t('Contexto y telemetría de esta pregunta','Question context and telemetry','Contexte et télémétrie de cette question')),el('pre',JSON.stringify({scope:current.scope||'saved_session_readings',model:current.model,status:current.status,elapsed_seconds:current.elapsed_seconds,phases:current.phases,runtime:current.runtime,resources_latest:current.resources_latest},null,2)));if(current.context){const raw=el('details');raw.append(el('summary',t('Contexto entregado al modelo','Context supplied to the model','Contexte fourni au modèle')),el('pre',JSON.stringify(current.context,null,2)));details.append(raw)}host.append(details);graphDrawn=false;
 }
 function filteredGraph(){
  const graph=current?.graph||{nodes:[],relationships:[]};if(!focused)return graph;
  const relationships=graph.relationships.filter(e=>focused.has(pk(e.page))),ids=new Set(relationships.flatMap(e=>[e.source,e.target]));return {...graph,relationships,nodes:graph.nodes.filter(n=>ids.has(n.id)||(n.mentions||[]).some(m=>focused.has(pk(m.page))))};
 }
 function drawGraph(){
  if(graphDrawn)return;graphDrawn=true;graphResult.replaceChildren();if(!current)return;graphResult.append(el('h3',t('Relaciones recuperadas','Retrieved relationships','Relations retrouvées')));
  if(kind==='matrix'){graphResult.append(el('p',t('Esta consulta examina las lecturas de la sesión una por una. Sus respuestas y su espina tienen fuentes; no se construyó un grafo nuevo con estas lecturas.','This query examines saved readings one by one. Its answers and fishbone have sources; no new graph was built from these readings.','Cette question examine les lectures enregistrées une par une. Les réponses et le diagramme ont des sources ; aucun nouveau graphe n’a été construit.')),btn(t('Ver las evidencias de la selección','View selection evidence','Voir les preuves de la sélection'),()=>choose('evidence')));return}
  const graph=filteredGraph();if(focused)graphResult.append(btn(t('Quitar enfoque de la espina','Clear fishbone focus','Effacer le focus du diagramme'),()=>{focused=null;graphDrawn=false;drawGraph();drawEvidence()}));
  if(!graph.nodes.length){graphResult.append(el('p',t('Esta pregunta no tiene relaciones recuperadas. Puedes explorar el grafo completo con el botón siguiente.','This question has no retrieved relationships. Use the button below to explore the full graph.','Cette question ne contient aucune relation retrouvée. Le graphe publié reste disponible ci-dessus.')),btn(t('Volver al grafo completo','Return to full graph','Revenir au graphe complet'),()=>newQuestion(true)));return}
  graphQueryOverview(graphResult,KnowledgeGraphFilters.filter({...graph,run_id:current.pilot_run}),{question:contextQuestion(),filtered:!!focused,onInspect:inspect,onClear:closeSources,externalInspector:true});
 }
 async function openSource(page,quote=''){
  if(kind==='matrix'&&current){const row=current.rows.find(r=>pk(r)===pk(page));if(row){await matrixSource(row,quote,t('Consulta de la sesión','Session question','Question de la session'));return}}
  return graphPilotSource({id:(current?.pilot_run||graphPilotData?.result?.run_id)+':workspace',page,quotes:quote?[{quote}]:[]});
 }
 function pick(page,edge){
  researchGraphSelect(page,{kind:'Knowledge Graph',query:contextQuestion(),query_id:selected||null,query_kind:kind,scope:current?(kind==='matrix'?'session_readings':'retrieved_context'):'pilot',pilot_run:current?.pilot_run||graphPilotData?.result?.run_id,relationship:edge?.fields?.relation,source:edge?.source,target:edge?.target});
  if(!sid())message(t('Página añadida. Crea una sesión en Mi selección para conservarla y exportarla.','Page added. Create a session in My selection to save and export it.','Page ajoutée. Créez une session dans Ma sélection pour la conserver et l’exporter.'));drawSelectionCount();
 }
 function drawSelectionCount(){let n=session.querySelector('.kw-selection-count');if(!n){n=el('small');n.className='kw-selection-count';session.append(n)}n.textContent=matrixSelection.size+' '+t('lecturas seleccionadas','selected readings','lectures sélectionnées')}
 function sourceCard(page,edge){const card=el('article');card.append(el('strong',page.document),el('small',(page.folder||'')+' · p. '+page.page+' · '+page.version));if(edge)card.append(el('p',edge.fields?.relation||''));const actions=el('div');actions.className='kw-actions';actions.append(btn(t('Ver y corregir fuente','View and correct source','Voir et corriger la source'),()=>openSource(page)),btn(t('Conservar','Keep','Conserver'),()=>pick(page,edge)));card.append(actions);return card}
 function inspect(detail){
  lastInspection={kind:'graph',detail};
  sources.hidden=false;shell.classList.add('kw-inspecting');sources.replaceChildren(btn(t('Cerrar fuentes','Close sources','Fermer les sources'),closeSources),el('small',detail.entity?gResolve(graphTypeNames[detail.entity.type]||detail.entity.type):t('RELACIÓN','RELATIONSHIP','RELATION')),el('h3',detail.title));
  const pages=new Set((detail.edges?.length?detail.edges.map(e=>e.page):(detail.entity?.mentions||[]).map(m=>m.page)).map(pk));
  sources.append(el('p',t(`${detail.edges?.length||0} relaciones · ${pages.size} lecturas de origen`,`${detail.edges?.length||0} relationships · ${pages.size} source readings`,`${detail.edges?.length||0} relations · ${pages.size} lectures sources`)));
  if(detail.entity){const ask=btn(t('Preguntar sobre esta entidad ↗','Ask about this entity ↗','Interroger cette entité ↗'),()=>{const label=detail.entity.label;newQuestion();x.question.value=t('¿Qué relaciones se documentan sobre ','What relationships are documented about ','Quelles relations sont documentées concernant ')+label+'?';focusQuestion()});ask.className='kw-inspector-ask';sources.append(ask)}
  sources.scrollTop=0;paintRailToggle();
  for(const edge of detail.edges||[]){const card=sourceCard(edge.page,edge);card.prepend(el('small',edge.source.replace(/^[A-Z]+::/,'')+' → '+edge.target.replace(/^[A-Z]+::/,'')));if(current&&kind==='knowledge_graph')card.append(btn(t('Proponer hipótesis con esta evidencia','Propose a hypothesis with this evidence','Proposer une hypothèse avec cette preuve'),()=>addHypothesis(edge)));sources.append(card)}
  if(!detail.edges?.length)for(const mention of detail.entity?.mentions||[])sources.append(sourceCard(mention.page));
 }
 function drawEvidence(){
  const host=panels.evidence;host.replaceChildren();if(!manifest){host.append(el('p',t('Las fuentes aparecerán al terminar la consulta.','Sources appear when the query finishes.','Les sources apparaîtront à la fin de la requête.')));return}
  const pages=manifest.pages.filter(p=>!focused||focused.has(pk(p)));host.append(el('h3',pages.length+' '+t('lecturas de origen','source readings','lectures sources')));if(focused)host.append(btn(t('Mostrar todas las evidencias','Show all evidence','Afficher toutes les preuves'),()=>{focused=null;graphDrawn=false;drawGraph();drawEvidence()}));
  const list=el('div');list.className='kw-evidence-list';for(const p of pages)list.append(sourceCard(p));host.append(list);
 }
 const branchLabels={es:['Parentesco y familias','Movilidad y residencia','Usos del territorio','Instituciones','Cambios temporales','Contexto'],en:['Kinship and families','Mobility and residence','Territory use','Institutions','Temporal change','Context'],fr:['Parenté et familles','Mobilité et résidence','Usages du territoire','Institutions','Évolution temporelle','Contexte']};
 const labels=()=>branchLabels[uiLanguage];
 const branchLabel=b=>{for(const list of Object.values(branchLabels)){const index=list.indexOf(b.label);if(index>=0)return labels()[index]}return b.label};
 async function refreshDiagram(turn=epoch){
  if(fishLoading||!selected||!manifest)return;fishLoading=true;
  try{
   const data=await req('/research-workspace/fishbone?'+new URLSearchParams({id:selected,kind,...(sid()?{session_id:sid()}:{})}));if(turn!==epoch)return;
   auto=data.generation;followup=data.followup;
   if(!diagram){let draft=null;try{draft=JSON.parse(sessionStorage.getItem(draftKey())||'null')}catch{}
    diagram=draft||{...data.saved,question:contextQuestion(),author:current.author||ResearchSessions.current?.researcher||'',query_id:selected,query_kind:kind,session_id:sid()};diagramDirty=!!draft;
    if(!diagram.branches.length)diagram.branches=labels().map(label=>({label,items:[]}));
   }
   if(!diagramDirty&&data.saved.revision>diagram.revision)diagram=data.saved;
   if(auto&&terminal(auto.status)&&auto.branches&&diagram.generation?.job!==auto.id){
    const count=auto.branches.reduce((n,b)=>n+b.items.length,0);
    if(count){for(let i=0;i<auto.branches.length;i++){
     const target=diagram.branches[i]||{label:auto.branches[i].label,items:[]};if(!diagram.branches[i])diagram.branches[i]=target;
     for(const item of auto.branches[i].items)if(!target.items.some(old=>old.generated_by===auto.id&&old.text===item.text&&JSON.stringify(old.evidence)===JSON.stringify(item.evidence)))target.items.push(structuredClone(item));
    }
    diagram.generation={job:auto.id,model:auto.model,scope:'query',automatic:true,status:auto.status};diagram.revision=Math.max(diagram.revision,data.saved.revision);dirty();}
   }
   const stamp=JSON.stringify([selected,auto?.id,auto?.status,auto?.processed,followup?.status,data.saved.revision,uiLanguage]);
   paintPipeline();
   if(stamp!==fishStamp&&!sources.contains(document.activeElement)){fishStamp=stamp;drawFishbone()}
  }catch(e){message(e.message)}finally{fishLoading=false}
 }
 async function loadDiagram(){if(!diagram)await refreshDiagram();return !!diagram}
 function dirty(){diagramDirty=true;sessionStorage.setItem(draftKey(),JSON.stringify(diagram));const s=panels.fishbone.querySelector('.kw-diagram-save');if(s)s.textContent=t('Cambios pendientes','Unsaved changes','Modifications non enregistrées')}
 async function saveDiagram(){
  if(diagramSaving||!diagram)return;if(!diagram.author?.trim()){message(t('Indica el responsable antes de guardar.','Enter an author before saving.','Indiquez le responsable avant d’enregistrer.'));return}
  diagramSaving=true;const turn=epoch,sent=JSON.stringify(diagram);
  try{const saved=await req('/hypotheses',{...diagram,query_id:selected,query_kind:kind,session_id:sid()});if(turn!==epoch)return;
   if(JSON.stringify(diagram)===sent){diagram=saved;diagramDirty=false;sessionStorage.removeItem(draftKey())}else{diagram.revision=saved.revision;dirty()}
   drawFishbone();message(t('Espina guardada con su pregunta y sus fuentes.','Fishbone saved with its question and sources.','Diagramme enregistré avec sa question et ses sources.'));
  }catch(e){message(e.message)}finally{diagramSaving=false}
 }
 async function addHypothesis(edge){
  try{if(!await loadDiagram())return;diagram.branches[branch||0].items.push({text:edge.fields?.relation||t('Hipótesis por revisar','Hypothesis to review','Hypothèse à réviser'),status:'explore',evidence:[{...edge.page,note:(edge.quotes||[]).map(q=>q.quote).join('\n')}],relationship_id:edge.id,source:edge.source,target:edge.target});dirty();drawFishbone();showBranchSources(diagram.branches[branch||0],true)}catch(e){message(e.message)}
 }
 function exportFishbone(){
  if(!diagram)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const lines=[diagram.question,...diagram.branches.flatMap(b=>[branchLabel(b),...b.items.map(item=>'• '+item.text+' ['+(item.evidence?.length||0)+' '+t('fuentes','sources','sources')+']')])];
  const wrapped=lines.flatMap(line=>{const words=String(line).split(/\s+/),out=[];let row='';for(const word of words){if(row.length+word.length>100){out.push(row);row=''}row+=(row?' ':'')+word}out.push(row);return out});
  const height=100+wrapped.length*26;
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="'+height+'" viewBox="0 0 1000 '+height+'"><rect width="100%" height="100%" fill="#fffefa"/><g font-family="sans-serif" font-size="16" fill="#173f34">'+wrapped.map((line,i)=>'<text x="32" y="'+(45+i*26)+'">'+esc(line)+'</text>').join('')+'</g></svg>';
  priorityDownload(svg,'fishbone-'+selected+'.svg','image/svg+xml');
 }
 function drawFishbone(){
  const host=panels.fishbone;host.replaceChildren();if(!current)return;
  const head=el('div');head.className='kw-section-heading';head.append(el('div'));head.firstChild.append(el('small',t('ESPINA DE PESCADO','FISHBONE DIAGRAM','DIAGRAMME EN ARÊTES')),el('h3',t('Una pregunta. Seis caminos para investigar.','One question. Six paths to investigate.','Une question. Six pistes de recherche.')));host.append(head);
  host.append(el('p',t('Pulsa una rama para leer sus hipótesis completas, revisar las citas y abrir las páginas de origen. Son propuestas de investigación, no causas demostradas.','Select a branch to read its full hypotheses, check quotations and open source pages. These are research proposals, not proven causes.','Choisissez une branche pour lire les hypothèses complètes, vérifier les citations et ouvrir les sources. Il s’agit de pistes de recherche, pas de causes démontrées.')));
  if(!manifest||!diagram){const waiting=el('div',['failed','interrupted'].includes(current.status)?t('La consulta no terminó. No se ha generado una espina.','The query did not finish. No fishbone was generated.','La requête n’a pas abouti. Aucun diagramme n’a été généré.'):t('La espina se construirá automáticamente después de la respuesta.','The fishbone will be built automatically after the answer.','Le diagramme sera construit automatiquement après la réponse.'));waiting.className='kw-fishbone-wait';host.append(waiting);return}
  const fs=auto?.status||followup?.status,count=diagram.branches.reduce((n,b)=>n+b.items.length,0),working=current.auto_fishbone&&!fs||fs&&!terminal(fs);
  const status=el('div');status.className='kw-fishbone-status';status.setAttribute('role','status');
  if(working){status.append(el('span',t('Construyendo la espina con el modelo local…','Building the fishbone with the local model…','Construction du diagramme avec le modèle local…')));if(auto?.total){const progress=el('progress');progress.max=auto.total;progress.value=auto.processed||0;status.append(progress,el('small',(auto.processed||0)+' / '+auto.total+' · '+Math.round(auto.elapsed_seconds||0)+' s'))}else status.append(el('small',t('En cola · la respuesta ya está disponible.','Queued · the answer is already available.','En attente · la réponse est déjà disponible.')))}
  else {const sourced=diagram.branches.flatMap(b=>b.items).filter(item=>item.evidence?.length).length;status.append(el('strong',count+' '+t('hipótesis','hypotheses','hypothèses')),el('span',sourced+' '+t('con fuentes','with sources','avec sources')+' · '+(count-sourced)+' '+t('por documentar','awaiting sources','à documenter')));if(!count)status.classList.add('kw-empty');}
  if(fs==='complete_with_errors'||fs==='failed'||fs==='interrupted'){status.classList.add('kw-partial');const errors=el('details');errors.append(el('summary',t('Resultado parcial · ver incidencias','Partial result · view issues','Résultat partiel · voir les problèmes')));if(auto?.error||followup?.error)errors.append(el('p',auto?.error||followup.error));for(const error of auto?.errors||[])errors.append(el('p',t('Pasaje ','Passage ','Passage ')+(error.task+1)+': '+error.error));status.append(errors)}host.append(status);
  const actions=el('div');actions.className='kw-actions';
  if(!working)actions.append(btn(count?t('Volver a generar','Generate again','Générer à nouveau'):t('Generar espina','Generate fishbone','Générer le diagramme'),generateFishbone));
  if(diagramDirty)actions.append(btn(t('Guardar mis cambios','Save my changes','Enregistrer mes modifications'),saveDiagram));
  actions.append(btn(t('Exportar datos JSON','Export JSON data','Exporter les données JSON'),()=>priorityDownload(JSON.stringify(diagram,null,2),'fishbone-'+selected+'.json','application/json')));
  actions.append(btn(t('Descargar resumen SVG','Download SVG summary','Télécharger le résumé SVG'),exportFishbone));
  const saved=el('small',diagramDirty?t('Cambios pendientes','Unsaved changes','Modifications non enregistrées'):diagram.revision?t('Guardado · revisión ','Saved · revision ','Enregistré · révision ')+diagram.revision:t('Borrador automático','Automatic draft','Brouillon automatique'));saved.className='kw-diagram-save';actions.append(saved);head.append(actions);
  if(!count){if(!working)host.append(el('p',t('No hay hipótesis con citas disponibles en esta ejecución. Puedes revisar las incidencias o crear una propuesta desde las relaciones del grafo.','This run has no hypotheses with available quotations. Review the issues or propose one from the graph relationships.','Aucune hypothèse avec citation disponible pour cette exécution. Consultez les problèmes ou proposez-en une depuis les relations du graphe.')));}
  const canvas=el('div');canvas.className='kw-fishbone-board';canvas.setAttribute('role','group');canvas.setAttribute('aria-label',t('Espina de hipótesis','Hypothesis fishbone','Diagramme des hypothèses'));
  const spine=el('div');spine.className='kw-bone-spine';canvas.append(spine);
  const question=el('div');question.className='kw-bone-question';question.append(el('small',t('PREGUNTA CENTRAL','CENTRAL QUESTION','QUESTION CENTRALE')),el('strong',diagram.question));canvas.append(question);
  diagram.branches.forEach((b,i)=>{
   const card=btn('',()=>{branch=i;focused=new Set(b.items.flatMap(item=>item.evidence||[]).map(pk));graphDrawn=false;drawGraph();drawEvidence();drawFishbone();showBranchSources(b,true)});card.className='kw-bone-branch '+(i%2===0?'kw-bone-top':'kw-bone-bottom');card.style.setProperty('--column',Math.floor(i/2)+1);card.setAttribute('aria-label',branchLabel(b)+' · '+b.items.length+' '+t('hipótesis','hypotheses','hypothèses'));card.setAttribute('aria-pressed',String(i===branch));
   const top=el('span');top.className='kw-branch-title';top.append(el('strong',branchLabel(b)),el('b',b.items.length));card.append(top);
   if(!b.items.length)card.append(el('span',t('Sin hipótesis · añadir propuesta','No hypotheses · add proposal','Aucune hypothèse · ajouter une proposition')));
   for(const item of b.items.slice(0,3)){const preview=el('span');preview.className='kw-branch-item';preview.append(el('span',item.text),el('small',({explore:t('Por explorar','To explore','À explorer'),evidence:t('Con evidencia','With evidence','Avec preuves'),contradicted:t('Contradicha','Contradicted','Contredite'),reviewed:t('Revisada','Reviewed','Révisée')})[item.status]||t('Por explorar','To explore','À explorer')),el('small',(item.evidence?.length||0)+' '+t('fuentes','sources','sources')));card.append(preview)}
   card.append(el('small',b.items.length?t('Ver todas · ','View all · ','Tout voir · ')+b.items.length+' →':t('Añadir hipótesis →','Add hypothesis →','Ajouter une hypothèse →')));canvas.append(card);
  });host.append(canvas);
  const details=el('details');details.className='kw-diagram-details';details.append(el('summary',t('Responsable, alcance y registro de la espina','Author, scope and fishbone record','Responsable, portée et registre du diagramme')));
  const author=el('label',t('Responsable de la revisión','Review author','Responsable de la révision')),input=el('input');input.value=diagram.author||'';input.setAttribute('aria-label',author.textContent);input.maxLength=160;input.oninput=()=>{diagram.author=input.value;dirty()};author.append(input);details.append(author,el('p',t('Usa las versiones congeladas de las páginas vinculadas a esta pregunta. La comprobación literal de una cita no valida su interpretación.','Uses frozen versions of the pages linked to this question. A literal quotation match does not validate its interpretation.','Utilise les versions figées des pages liées à cette question. La présence littérale d’une citation ne valide pas son interprétation.')));
  if(auto?.id)details.append(btn(t('Descargar ejecución y telemetría','Download run and telemetry','Télécharger l’exécution et la télémétrie'),async()=>{const value=await req('/hypotheses/auto?id='+auto.id);priorityDownload(JSON.stringify(value,null,2),'fishbone-run-'+value.id+'.json','application/json')}));host.append(details);
 }
 function showBranchSources(b,editable=false){
  lastInspection={kind:'branch',detail:b};sources.hidden=false;shell.classList.add('kw-inspecting');sources.replaceChildren(btn(t('Cerrar detalle','Close details','Fermer le détail'),closeSources),el('small',t('HIPÓTESIS Y EVIDENCIAS','HYPOTHESES AND EVIDENCE','HYPOTHÈSES ET PREUVES')),el('h3',branchLabel(b)));sources.scrollTop=0;paintRailToggle();
  if(!b.items.length)sources.append(el('p',t('Todavía no hay propuestas en esta rama.','There are no proposals in this branch yet.','Cette branche ne contient pas encore de propositions.')));
  for(const item of b.items){const card=el('article');card.className='kw-hypothesis-card';card.append(el('p',item.text));
   const state=el('select');state.setAttribute('aria-label',t('Estado de la hipótesis','Hypothesis status','État de l’hypothèse'));for(const [v,label]of [['explore',t('Por explorar','To explore','À explorer')],['evidence',t('Con evidencia','With evidence','Avec preuves')],['contradicted',t('Contradicha','Contradicted','Contredite')],['reviewed',t('Revisada','Reviewed','Révisée')]]){const o=el('option',label);o.value=v;state.append(o)}state.value=item.status;state.onchange=()=>{item.status=state.value;dirty();drawFishbone()};card.append(state);
   for(const page of item.evidence||[]){if(page.quote||page.note)card.append(el('blockquote',page.quote||page.note));card.append(sourceCard(page))}
   const edit=el('details');edit.append(el('summary',t('Editar hipótesis','Edit hypothesis','Modifier l’hypothèse')));const text=el('textarea');text.value=item.text;text.rows=4;text.setAttribute('aria-label',t('Texto de la hipótesis','Hypothesis text','Texte de l’hypothèse'));text.oninput=()=>{item.text=text.value;card.querySelector('p').textContent=text.value;dirty()};text.onblur=()=>drawFishbone();edit.append(text,btn(t('Eliminar hipótesis','Remove hypothesis','Supprimer l’hypothèse'),()=>{b.items.splice(b.items.indexOf(item),1);dirty();drawFishbone();showBranchSources(b,true)}));card.append(edit);sources.append(card);
  }
  if(editable)sources.append(btn(t('Añadir hipótesis','Add hypothesis','Ajouter une hypothèse'),()=>{b.items.push({text:t('Propuesta por redactar','Proposal to write','Proposition à rédiger'),status:'explore',evidence:[]});dirty();drawFishbone();showBranchSources(b,true)}));
  sources.append(btn(t('Guardar mis cambios','Save my changes','Enregistrer mes modifications'),saveDiagram));
 }
 async function generateFishbone(){
  if(generating||auto&&!terminal(auto.status))return;const turn=epoch;generating=true;
  try{if(!await ResearchSessions.flush()||turn!==epoch)return;await req('/hypotheses/auto',{scope:'query',query_id:selected,query_kind:kind,session_id:sid(),question:contextQuestion(),author:current.author||ResearchSessions.current?.researcher||'Local model',language:uiLanguage});fishStamp='';await refreshDiagram(turn)}catch(e){message(e.message)}finally{generating=false}
 }
 function restoreView(value){if(selected===value.selected&&kind===value.kind)choose(tabButtons.has(value.representation)?value.representation:'answer')}
 function sessionChanged(){runs=[];const remembered=sessionStorage.getItem('maph-investigation:'+(sid()||'unassigned'));newQuestion(true);if(remembered){try{const value=JSON.parse(remembered);if(value.selected)open(value.kind,value.selected).then(()=>restoreView(value)).catch(e=>message(e.message))}catch{}}refresh();paintControls();drawSelectionCount()}
 window.addEventListener('research-session-changed',sessionChanged);
 window.addEventListener('research-graph-handoff',event=>{newQuestion();x.question.value=t('¿Qué relaciones se documentan sobre ','What relationships are documented about ','Quelles relations sont documentées concernant ')+event.detail.label+'?'});
 const oldPersist=matrixPersist;matrixPersist=function(){oldPersist();drawSelectionCount()};
 const oldLanguage=setLanguage;setLanguage=function(language){oldLanguage(language);message('');paintControls();refresh();drawSelectionCount();if(current)renderAnswer();graphDrawn=false;syncLayout();if(current){drawGraph();drawFishbone();drawEvidence()}if(!sources.hidden&&lastInspection)(lastInspection.kind==='graph'?inspect:showBranchSources)(lastInspection.detail,true)};
 window.KnowledgeWorkspace={refresh,inspect,open,choose,closeSources};
 const remembered=sessionStorage.getItem('maph-investigation:'+(sid()||'unassigned'));paintControls();syncLayout();drawSelectionCount();if(remembered){try{const value=JSON.parse(remembered);if(value.selected)open(value.kind,value.selected).then(()=>restoreView(value)).catch(e=>message(e.message))}catch{}}
 x.progress.update(null);refresh();
 // Keep progress alive while the user is inspecting another representation.
 setInterval(()=>{if(activeView==='graphrag'&&!document.hidden)refresh()},4000);
})();
(()=>{const style=document.createElement('style');style.textContent=`
#view-graphrag.kw-view{padding:0;max-width:none;overflow:visible;background:#fffefa;border:1px solid #d8dfd8;border-radius:14px;margin-top:18px;box-shadow:0 6px 28px #203b2f06}
.kw-view .graph-explorer-heading{display:none}
.knowledge-workspace{--kw-pane-height:clamp(650px,calc(100dvh - 360px),980px);display:grid;grid-template-columns:290px minmax(0,1fr);position:relative;isolation:isolate}
.knowledge-workspace [hidden]{display:none!important}
.knowledge-workspace :is(button,input,select,textarea):focus-visible{outline:2px solid #c3542c;outline-offset:3px}
.kw-session-toolbar{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:23px 26px 18px}
.kw-session{display:flex;flex-wrap:wrap;align-items:baseline;gap:7px 14px;min-width:0}
.kw-session>small:first-child{flex-basis:100%;color:#9c4e32;letter-spacing:1.5px;font-size:9px;font-weight:700}
.kw-session>strong{font-size:27px;font-weight:600;letter-spacing:-1px}
.kw-session>span{font-size:12px;color:#5c7065}
.kw-selection-count{font-size:10px;color:#386b57;background:#edf3ed;padding:4px 8px;border-radius:5px;white-space:nowrap}
.kw-toolbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.kw-toolbar button{font-size:11px;padding:10px 12px;border-radius:7px;background:#fffefa;border-color:#d9dfd7}
.kw-toolbar button:first-child{background:#183f35;color:#fffefa;border-color:#183f35}
.kw-toolbar button:hover{box-shadow:0 2px 8px #1b4c3515}
.kw-status-details{grid-column:1/-1;border-top:1px solid #e6e9e1;border-bottom:1px solid #dbe3d9;background:#f2f5ef;padding:0 26px;font-size:11px;color:#446550}
.kw-status-details>summary{cursor:pointer;padding:10px 0;line-height:1.6;list-style-position:inside}
.kw-status-details[data-state=warning]{background:#faf5e9;color:#84612f}
.kw-status-details .graph-explorer-availability{background:none!important;border:0!important;padding:0 0 12px!important;margin:0!important;font-size:11px!important;line-height:1.8;color:inherit}
.kw-query-rail{grid-column:1;grid-row:3;min-width:0;max-height:var(--kw-pane-height);overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:22px 18px;background:#f4f6f1;border-right:1px solid #dbe2d9;border-radius:0 0 0 14px;box-sizing:border-box}
.kw-rail-title{font-size:17px;font-weight:600;letter-spacing:-.4px;margin:0 0 18px;color:#244e3e}
.kw-query-rail .graph-question-form{display:flex;flex-direction:column;gap:15px;padding:0;margin:0;border:0;border-radius:0;background:none}
.kw-query-rail .graph-question-form label{font-size:11px;gap:8px;color:#52665b;min-width:0}
.kw-query-rail .graph-question-form select,.kw-query-rail .graph-question-form input{width:100%;min-width:0;box-sizing:border-box;font-size:11px;padding:9px;border:1px solid #d2dbce;background:#fffefa;border-radius:6px}
.kw-query-rail .graph-question-form textarea{min-height:145px;max-height:300px;border:1px solid #b9cbbf;border-radius:8px;padding:12px;font-size:13px;line-height:1.8;background:#fffefa;color:#193b30;box-shadow:0 2px 5px #24442b05}
.kw-query-rail .graph-question-form textarea::placeholder{color:#7a8b7e}
.kw-query-rail .graph-question-form>button{width:100%;padding:12px 15px;border:1px solid #214a39;background:#214a39;color:#fffefa;border-radius:7px;font-size:12px;font-weight:600;white-space:normal;margin:0}
.kw-query-rail .graph-question-form>button:disabled{opacity:.55;cursor:wait}
.kw-query-rail .kw-auto-note{font-size:10px;line-height:1.7;color:#677b6a;margin:0}
.kw-query-rail .kw-options{font-size:11px;color:#516c5b;order:2;border-top:1px solid #dfe5db;padding-top:12px}
.kw-options summary,.kw-suggestions summary{cursor:pointer;line-height:1.6}
.kw-options .graph-question-options{grid-template-columns:1fr;margin:12px 0;gap:12px}
.kw-query-rail .graph-question-form p[role=status]{font-size:11px;color:#325d43;margin:0;overflow-wrap:anywhere}
.kw-query-rail .graph-question-form p[role=status]:empty{display:none}
.kw-query-rail .graph-query-progress{margin:0;padding:10px;font-size:11px}
.kw-query-rail .graph-query-progress[data-active=false]{display:none}
.kw-suggestions{padding:12px 0;font-size:11px;color:#516c5b;border-bottom:1px solid #dfe5db}
.kw-suggestions .priority-actions{display:flex;flex-direction:column;gap:6px;margin:10px 0 0}
.kw-suggestions button{width:100%;font-size:11px;white-space:normal;text-align:left;line-height:1.6;background:#fffefa;border:1px solid #d7dfd3;border-radius:6px;padding:9px}
.kw-query-rail .kg-source-filters{margin:20px 0 0;padding:0;background:none;border:0;border-radius:0}
.kw-query-rail .kg-scope-heading{align-items:start;gap:8px}
.kw-query-rail .kg-scope-heading strong{font-size:12px;line-height:1.6}
.kw-query-rail .kg-scope-heading button{font-size:10px;padding:5px 7px;background:transparent;white-space:normal}
.kw-query-rail .kg-scope-controls{grid-template-columns:1fr;gap:7px;margin:12px 0}
.kw-query-rail .kg-scope-controls details{padding:10px;font-size:11px;border-radius:6px;background:#fffefa}
.kw-query-rail .kg-scope-list{max-height:190px}
.kw-query-rail .kg-scope-list label{font-size:11px;line-height:1.5}
.kw-query-rail .kg-source-filters>p{font-size:11px;line-height:1.7}
.kw-query-rail .kg-source-filters>small{font-size:10px;line-height:1.7}
.kw-center{grid-column:2;grid-row:3;min-width:0;max-height:var(--kw-pane-height);overflow:auto;overscroll-behavior:contain;scrollbar-width:thin;padding:0 22px 20px;box-sizing:border-box;border-radius:0 0 14px 0}
.kw-context{padding:20px 0 8px}
.kw-context>small{font-size:9px;color:#a25435;letter-spacing:1.3px}
.kw-context h2{font-size:24px;font-weight:500;line-height:1.4;letter-spacing:-.7px;margin:7px 0;overflow-wrap:anywhere}
.kw-context p{font-size:11px;color:#64796b;line-height:1.7;margin:5px 0}
.kw-tabbar{display:flex;gap:10px;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:7;background:#fffefa;border-bottom:1px solid #dbe2d8;margin-bottom:16px}
.kw-view-tabs{display:flex;align-items:stretch;gap:0;min-width:0;flex-wrap:wrap}
.kw-view-tabs button{padding:13px 10px;font-size:11px;border:0;border-bottom:2px solid transparent;border-radius:0;background:transparent;color:#637267}
.kw-view-tabs button[aria-selected=true]{color:#a94d2c;border-bottom-color:#dd6b3e;background:#fcf5ee;font-weight:700}
.kw-view-tabs button:disabled{color:#647267;opacity:.45;cursor:not-allowed}
.kw-rail-toggle{font-size:10px;padding:6px 8px;border:1px solid #dbe2d8;border-radius:5px;background:transparent;color:#627566;flex-shrink:0}
.kw-rail-collapsed{grid-template-columns:minmax(0,1fr)}
.kw-rail-collapsed .kw-center{grid-column:1}
.kw-pipeline{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 12px;margin:0 0 16px;border:1px solid #dce4d9;border-radius:7px;background:#f5f8f2}
.kw-step{display:flex;align-items:center;gap:6px;font-size:10px;color:#7c857e}
.kw-step b{display:grid;place-items:center;background:#e6ece2;border-radius:50%;width:20px;height:20px;font-weight:500}
.kw-step.done{color:#267456}.kw-step.done b{background:#dceee4}.kw-step.active{color:#193f33;font-weight:600}.kw-step.active b{background:#ffe8d7;color:#a94d2b}.kw-step.warning b{background:#fff0ce;color:#885c12}
.kw-pipeline>small{font-size:10px;flex-basis:100%;color:#536b5e}
.kw-panel{min-width:0;scroll-margin-top:65px;animation:kw-panel-in .16s ease-out}
.kw-panel>h3,.kw-section-heading h3{font-size:21px;font-weight:500;letter-spacing:-.5px;margin:10px 0 15px}
.kw-panel>p{font-size:12px;line-height:1.8;color:#586d60}
.kw-panel .graph-query-answer{padding:20px;background:#faf9f4;border:1px solid #e1e4d9;border-left:3px solid #21786a;border-radius:8px;line-height:1.85;font-size:14px;margin:16px 0;max-height:none;overflow:visible;white-space:pre-wrap}
.kw-panel pre{overflow:auto;max-height:350px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}
.kw-panel details{margin:14px 0}.kw-panel details summary{cursor:pointer}
.kw-actions{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:12px 0}
.kw-actions button{font-size:11px;padding:8px 10px;border-radius:6px;white-space:normal}
.kw-actions small{font-size:10px;color:#647568}
.kw-section-heading{display:flex;justify-content:space-between;align-items:start;gap:16px}
.kw-section-heading small{font-size:9px;letter-spacing:1.3px;color:#a84a28}
.kw-section-heading h3{margin-bottom:7px}
.knowledge-workspace .graph-full-pilot{margin:0;border-radius:10px}
.knowledge-workspace .graph-full-hero{padding:17px 20px;display:block}
.knowledge-workspace .graph-full-hero>div:first-child{display:none}
.knowledge-workspace .graph-full-metrics{justify-content:space-between;gap:12px}
.knowledge-workspace .graph-full-metrics>div{padding-left:12px;min-width:0}
.knowledge-workspace .graph-full-metrics strong{font-size:27px}
.knowledge-workspace .graph-full-metrics span{font-size:10px;line-height:1.5}
.knowledge-workspace .graph-full-actions{display:none}
.knowledge-workspace .graph-query-overview{margin:0;padding:14px}
.knowledge-workspace .graph-query-svg{height:clamp(360px,calc(100dvh - 670px),620px);min-height:360px}
.knowledge-workspace .graph-canvas-search{display:flex;gap:7px;flex:1;flex-wrap:wrap;min-width:170px}
.knowledge-workspace .graph-canvas-search input{min-width:140px;width:100%;flex:1;padding:9px 10px;font-size:11px}
.knowledge-workspace .graph-canvas-search select{max-width:100%;width:210px;flex:1;font-size:11px}
.knowledge-workspace .graph-canvas-controls{gap:6px;align-items:center}
.knowledge-workspace .graph-canvas-controls button{font-size:11px;padding:8px;min-height:34px}
.knowledge-workspace .graph-canvas-footer{display:block;padding-top:10px}
.knowledge-workspace .graph-canvas-footer>span{display:block;text-align:left;max-width:none;font-size:10px;margin-top:10px}
.knowledge-workspace .graph-scope-details{margin:10px 0 0;font-size:10px;padding-top:8px}
.knowledge-workspace .graph-full-pilot .graph-expanded{padding:22px;overflow:auto}
.knowledge-workspace .graph-full-pilot .graph-expanded .graph-query-svg{height:100%;min-height:350px}
.knowledge-workspace .graph-full-pilot .graph-expanded .graph-canvas-footer{display:flex}
.kw-inspecting{grid-template-columns:250px minmax(0,1fr) 310px}
.kw-inspecting.kw-rail-collapsed{grid-template-columns:minmax(0,1fr) 330px}
.kw-inspecting.kw-rail-collapsed .kw-sources{grid-column:2}
.kw-inspector-ask{font-size:11px!important;padding:10px!important;width:100%;color:#27573e;background:#edf4e9;border-color:#cadbc9;border-radius:6px}
.kw-branch-item{display:flex;flex-direction:column;gap:4px;padding:10px 0;border-top:1px solid #dce3d9}
.kw-branch-item>span{font-size:13px;line-height:1.6;overflow-wrap:anywhere}.kw-branch-item>small{font-size:12px;color:#53675c}
.kw-fishbone-status.kw-empty{background:#f1f2ef;color:#53675c}
.kw-fishbone-board{position:relative;isolation:isolate;display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) minmax(190px,.85fr);grid-template-rows:1fr 100px 1fr;gap:20px;padding:28px;border:1px solid #dce4d8;border-radius:16px;background:radial-gradient(ellipse at top left,#fffaf0,transparent 65%),#f4f7ef;overflow:hidden;margin:18px 0}.kw-bone-spine{position:absolute;left:28px;right:40px;height:3px;background:#668c7b;top:50%;z-index:-1}.kw-bone-question{grid-column:4;grid-row:1/4;align-self:center;padding:23px;background:#173f34;color:#fffefa;border-radius:13px;box-shadow:0 10px 25px #1d463719}.kw-bone-question small{display:block;color:#accbbb;font-size:10px;letter-spacing:1px;margin-bottom:14px}.kw-bone-question strong{font-size:17px;font-weight:500;line-height:1.7;overflow-wrap:anywhere;display:block}.kw-bone-branch{grid-column:var(--column);position:relative;padding:18px!important;display:flex;flex-direction:column;align-items:stretch;text-align:left!important;gap:13px;white-space:normal!important;background:#fffefa!important;border:1px solid #cddccd!important;border-radius:11px!important;box-shadow:0 3px 9px #264e3210;transition:box-shadow .18s,border-color .18s}.kw-bone-branch:hover{box-shadow:0 6px 18px #264e3222;border-color:#6c9680!important}.kw-bone-branch[aria-pressed=true]{border:2px solid #d57444!important;background:#fff8f0!important}.kw-bone-top{grid-row:1;align-self:end}.kw-bone-bottom{grid-row:3;align-self:start}.kw-bone-top:after,.kw-bone-bottom:before{content:'';position:absolute;width:2px;height:86px;background:#89a692;left:52%;z-index:-1}.kw-bone-top:after{bottom:-86px;transform:rotate(-35deg);transform-origin:top}.kw-bone-bottom:before{top:-86px;transform:rotate(35deg);transform-origin:bottom}.kw-branch-title{display:flex;gap:12px;justify-content:space-between;align-items:center}.kw-branch-title>strong{font-size:15px;line-height:1.5;font-weight:600}.kw-branch-title>b{border-radius:50%;background:#e8f1e6;color:#2f6850;font-size:15px;min-width:31px;height:31px;display:grid;place-items:center}.kw-branch-preview{font-size:13px;line-height:1.7;color:#5c7163;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.kw-bone-branch>small{font-size:11px;color:#a6532d;margin-top:auto}.kw-fishbone-status{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:13px;color:#305d47;margin:18px 0;padding:12px 16px;background:#ecf4e9;border-radius:8px}.kw-fishbone-status progress{width:180px;height:7px;accent-color:#287c62}.kw-fishbone-status details{width:100%;margin:0}.kw-fishbone-status.kw-partial{background:#fff4dd;color:#7b5722}.kw-fishbone-wait{padding:25px;background:#f2f5ef;border:1px dashed #c6d7c2;border-radius:12px;color:#52735b;font-size:14px}.kw-diagram-details{font-size:12px;color:#5a6d60}.kw-diagram-details label{display:block;margin:15px 0}.kw-diagram-details input{margin-left:12px;padding:9px;width:230px}.kw-evidence-details{margin:28px 0;padding:20px 0;border-top:1px solid #dce3d9}.kw-evidence-details>summary{font-size:17px;cursor:pointer;font-weight:500}.kw-evidence-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:20px}
.kw-sources{position:relative;grid-column:3;grid-row:3;z-index:5;min-width:0;max-height:var(--kw-pane-height);overflow:auto;overscroll-behavior:contain;background:#fffefa;border:1px solid #cbd7c9;border-radius:0;border:0;border-left:1px solid #dbe2dc;box-shadow:none;padding:20px;box-sizing:border-box;scrollbar-width:thin}.kw-sources[hidden]{display:none}.kw-sources>button:first-child{position:sticky;top:0;z-index:2;background:#173f34;color:#fff;padding:9px 13px;border-radius:7px;margin-bottom:16px;float:right}.kw-sources>small{display:block;clear:both;font-size:10px;letter-spacing:1.5px;color:#aa532d}.kw-sources h3{font-size:23px;line-height:1.4;margin:12px 0 24px;overflow-wrap:anywhere}.kw-sources p{font-size:14px;line-height:1.8;overflow-wrap:anywhere}.kw-sources article,.kw-evidence-list article,.kw-answer-row{padding:16px;margin:10px 0;background:#f6f7f0;border:1px solid #dbe3d6;border-radius:9px;overflow-wrap:anywhere}.kw-sources article>small,.kw-evidence-list article>small{display:block;font-size:12px;margin-top:8px}.kw-sources article>strong{font-size:14px}.kw-hypothesis-card>p{margin-top:0;font-size:15px}.kw-hypothesis-card blockquote{font-size:13px;line-height:1.8;border-left:3px solid #c5a06a;padding:12px;margin:15px 0;background:#fbf5e8;white-space:pre-wrap}.kw-hypothesis-card textarea{width:100%;box-sizing:border-box;min-height:120px;font:inherit;line-height:1.7;padding:10px}.kw-hypothesis-card details{font-size:12px;margin:15px 0}.kw-hypothesis-card summary{cursor:pointer}.kw-hypothesis-card select{max-width:100%;padding:7px 10px}.kw-sources button{white-space:normal}.kw-sources .kw-actions{margin-bottom:0}

.kw-history-dialog{box-sizing:border-box;width:520px;max-width:94vw;max-height:85vh;overflow:auto;padding:26px;background:#fffefa;border:1px solid #cbd7c9;border-radius:12px;color:#183c31}
.kw-history-dialog::backdrop{background:#102c2855;backdrop-filter:blur(3px)}
.kw-dialog-close{float:right;border-radius:50%;font-size:22px;width:35px;height:35px;display:grid;place-items:center;padding:0}
.kw-history{clear:both}.kw-history h3{font-size:22px;font-weight:500}
.kw-history-item{display:block;width:100%;text-align:left;padding:16px;margin:10px 0;line-height:1.7;border-radius:8px;white-space:normal;font-size:13px}
.kw-history-row{display:grid;grid-template-columns:minmax(0,1fr) 100px;gap:10px;align-items:center;border-bottom:1px solid #dce3d8;padding:8px 0}.kw-history-row .kw-history-item{margin:0}.kw-history-remove{display:block!important;visibility:visible!important;background:#fff2eb;color:#893e29;border:1px solid #d9b3a3;border-radius:7px;padding:10px;font-size:12px;cursor:pointer;white-space:normal}@media(max-width:500px){.kw-history-row{grid-template-columns:1fr}.kw-history-remove{justify-self:end}}
.kw-history-item small{display:block;font-size:11px;color:#6d8070;margin-top:7px}
.kw-history-item[aria-pressed=true]{background:#173e35;color:#fff}.kw-history-item[aria-pressed=true] small{color:#bfd8ca}
.knowledge-workspace .kw-evidence-details{margin:0;padding:0;border:0}
.knowledge-workspace .graph-entity-inventory{padding:0}
.knowledge-workspace .graph-pilot{padding:0}
@keyframes kw-panel-in{from{opacity:.5;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}
@media(min-width:801px) and (max-width:1550px){
 .kw-inspecting{grid-template-columns:minmax(0,1fr) 300px}
 .kw-inspecting .kw-query-rail{display:none}
 .kw-inspecting .kw-center{grid-column:1}
 .kw-inspecting .kw-sources{grid-column:2}
}
@media(max-width:1250px){
 .knowledge-workspace{grid-template-columns:250px minmax(0,1fr)}
 .kw-inspecting{grid-template-columns:minmax(0,1fr) 300px}
 .kw-inspecting .kw-query-rail{display:none}
 .kw-inspecting .kw-center{grid-column:1}
 .kw-inspecting .kw-sources{grid-column:2}
 .kw-rail-collapsed{grid-template-columns:minmax(0,1fr)}
 .kw-session-toolbar{align-items:flex-start}.kw-toolbar{max-width:50%}
 .kw-fishbone-board{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:auto;gap:20px;padding-left:40px}
 .kw-bone-question{grid-column:1/3;grid-row:auto}.kw-bone-spine{left:20px;right:auto;top:25px;bottom:25px;height:auto;width:3px}
 .kw-bone-branch{grid-column:auto;grid-row:auto;align-self:stretch}.kw-bone-top:after,.kw-bone-bottom:before{display:none}
 .kw-section-heading{display:block}
}
@media(min-width:1251px){.kw-inspecting .kw-fishbone-board{grid-template-columns:1fr 1fr;grid-template-rows:auto}.kw-inspecting .kw-bone-question{grid-column:1/3;grid-row:auto}.kw-inspecting .kw-bone-branch{grid-column:auto;grid-row:auto}.kw-inspecting .kw-bone-top:after,.kw-inspecting .kw-bone-bottom:before,.kw-inspecting .kw-bone-spine{display:none}}
@media(max-width:800px){
 #view-graphrag.kw-view{padding:0;border-radius:10px}
 .knowledge-workspace,.kw-inspecting,.kw-inspecting.kw-rail-collapsed{grid-template-columns:minmax(0,1fr)}
 .kw-session-toolbar{padding:18px 16px;display:block}.kw-session>strong{font-size:25px}
 .kw-toolbar{max-width:none;justify-content:flex-start;margin-top:14px}.kw-toolbar button{font-size:10px;padding:9px}
 .kw-status-details{padding:0 16px}
 .kw-center,.kw-inspecting .kw-center{grid-column:1;grid-row:3;max-height:none;padding:0 12px 16px}
 .kw-query-rail{grid-column:1;grid-row:4;max-height:none;border:0;border-top:1px solid #dbe2d9;border-radius:0 0 10px 10px;padding:20px}
 .kw-inspecting .kw-query-rail{display:block}
 .kw-tabbar{position:relative;align-items:flex-start;gap:5px}.kw-view-tabs{flex-wrap:wrap}.kw-view-tabs button{padding:12px 8px;font-size:10px}
 .kw-rail-toggle{margin-top:6px;white-space:normal;max-width:75px;font-size:9px}
 .kw-context h2{font-size:22px}
 .knowledge-workspace .graph-full-metrics strong{font-size:24px}.knowledge-workspace .graph-full-hero{padding:16px 12px}
 .knowledge-workspace .graph-query-overview{padding:10px}.knowledge-workspace .graph-query-svg{height:400px;min-height:340px}
 .knowledge-workspace .graph-canvas-search{flex-basis:100%}.knowledge-workspace .graph-canvas-search select{width:100%;max-width:100%;flex-basis:100%}
 .kw-sources,.kw-inspecting .kw-sources{position:fixed;grid-column:auto;top:auto;bottom:8px;right:8px;left:8px;width:auto;max-height:72dvh;z-index:90;border:1px solid #cbd7c9;border-radius:12px;box-shadow:0 -12px 50px #173c3440;padding:18px}
 .kw-fishbone-board{grid-template-columns:1fr;padding:18px 18px 18px 36px}.kw-bone-question{grid-column:1}
 .kw-bone-question strong{font-size:16px}.kw-panel .graph-query-answer{padding:16px;font-size:13px}
 .kw-evidence-list{grid-template-columns:1fr}
}
.kw-fullscreen-exit{display:none}.knowledge-workspace:fullscreen,.knowledge-workspace.graph-expanded{box-sizing:border-box;background:#fffefa;color:#173f34;width:100%;height:100dvh;overflow:auto;padding:18px;position:fixed;inset:0;z-index:800}.knowledge-workspace:fullscreen .kw-fullscreen-exit,.knowledge-workspace.graph-expanded .kw-fullscreen-exit{display:block}.knowledge-workspace:fullscreen .kw-tabbar,.knowledge-workspace.graph-expanded .kw-tabbar{position:sticky;top:0;background:#fffefa;z-index:20;flex-wrap:wrap}.knowledge-workspace:fullscreen .graph-query-svg,.knowledge-workspace.graph-expanded .graph-query-svg{height:70dvh!important}.knowledge-workspace:fullscreen .kw-sources,.knowledge-workspace.graph-expanded .kw-sources{z-index:900}

/* Fullscreen rows must size to content rather than stretching across the viewport. */
.knowledge-workspace:is(:fullscreen,.graph-expanded){grid-template-rows:auto auto minmax(0,1fr);align-content:start;align-items:start;overflow:hidden;padding:8px;--kw-pane-height:100%;gap:0}
.knowledge-workspace:is(:fullscreen,.graph-expanded)>.kw-session-toolbar{padding:6px 12px;min-height:0;gap:12px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-session>small:first-child{display:none}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-session>strong{font-size:18px;letter-spacing:0}
.knowledge-workspace:is(:fullscreen,.graph-expanded)>.kw-status-details{padding:0 12px;min-height:0;align-self:start}
.knowledge-workspace:is(:fullscreen,.graph-expanded)>.kw-status-details>summary{padding:4px 0}
.knowledge-workspace:is(:fullscreen,.graph-expanded)>.kw-center{height:100%;max-height:none;min-height:0;align-self:stretch;overflow:auto;padding:0 10px 8px}
.knowledge-workspace:is(:fullscreen,.graph-expanded)>.kw-query-rail{min-height:0;max-height:100%;overflow:auto}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-context{display:none}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-tabbar{padding:4px 0;margin:0;min-height:0}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-full-hero{padding:6px 12px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-full-metrics strong{font-size:20px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-full-metrics{gap:8px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-query-overview{margin:0;padding:8px 12px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-query-svg{height:calc(100dvh - 390px)!important;min-height:260px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-panel .graph-canvas-controls{margin-top:0}
/* Fill the remaining workspace height through every graph wrapper, including WebGL. */
.knowledge-workspace:is(:fullscreen,.graph-expanded)>.kw-center{display:flex;flex-direction:column}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-panel[data-representation=graph]:not([hidden]){flex:1;min-height:0;display:flex;flex-direction:column}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-panel[data-representation=graph]>div:not([hidden]){flex:1;min-height:0;display:flex;flex-direction:column}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-full-pilot>.graph-query-overview,.knowledge-workspace:is(:fullscreen,.graph-expanded) .kw-panel[data-representation=graph] .graph-query-overview{flex:1;min-height:0;display:flex;flex-direction:column}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-canvas-stage{flex:1;min-height:260px;position:relative}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-webgl{position:absolute!important;inset:0;width:100%!important;height:100%!important;min-height:0!important}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-query-svg{height:100%!important;min-height:260px}
.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-full-hero,.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-canvas-controls,.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-type-legend,.knowledge-workspace:is(:fullscreen,.graph-expanded) .graph-visual-guide{flex-shrink:0}
@media(prefers-reduced-motion:reduce){.knowledge-workspace *{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
`;document.head.append(style)})();
