// One explicit source scope for the visible graph and the next saved question.
window.createKnowledgeSourceFilters=function(host,onchange){
 let graph=null,filters={folders:[],documents:[]},locked=false,enabled=true;
 const t=(es,en,fr)=>({es,en,fr})[uiLanguage]||es;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n};
 const box=el('section');box.className='kg-source-filters';box.dataset.noI18n='';host.append(box);
 function change(){draw();onchange(get())}
 function get(){return {folders:[...filters.folders],documents:[...filters.documents]}}
 function draw(){
  const previous=Object.fromEntries([...box.querySelectorAll('details')].map(d=>[d.dataset.key,{open:d.open,search:d.querySelector('input[type=search]')?.value||'',scroll:d.querySelector('.kg-scope-list')?.scrollTop||0}]));
  box.hidden=!enabled;box.replaceChildren();const title=el('strong',t('Fuentes de Knowledge Graph','Knowledge Graph sources','Sources du Knowledge Graph'));
  const reset=el('button',t('Todas las fuentes','All sources','Toutes les sources'));reset.type='button';reset.disabled=locked;reset.onclick=()=>{filters={folders:[],documents:[]};change()};
  const heading=el('div');heading.className='kg-scope-heading';heading.append(title,reset);box.append(heading);
  const controls=el('div');controls.className='kg-scope-controls';box.append(controls);
  const records=graph?.selection||[];
  for(const [key,label,field]of [['folders',t('Carpetas','Folders','Dossiers'),'folder'],['documents',t('Documentos','Documents','Documents'),'document']]){
   const details=el('details'),summary=el('summary',label+' · '+(filters[key].length||t('Todos','All','Tous')));details.dataset.key=key;details.open=!!previous[key]?.open;details.append(summary);controls.append(details);
   const search=el('input');search.type='search';search.placeholder=t('Buscar en esta lista…','Search this list…','Rechercher dans cette liste…');search.setAttribute('aria-label',label);search.disabled=locked;details.append(search);
   const list=el('div');list.className='kg-scope-list';details.append(list);
   const available=records.filter(p=>key==='folders'||GraphResultCore.matchesSource(p,{folders:filters.folders}));
   const options=[...new Set([...available.map(p=>p[field]),...filters[key]])].sort();
   for(const value of options){const row=el('label'),input=el('input');input.type='checkbox';input.checked=filters[key].includes(value);input.disabled=locked;row.dataset.search=value.toLocaleLowerCase();
    const count=available.filter(p=>p[field]===value).length;row.append(input,el('span',value||t('Raíz','Root','Racine')),el('small',String(count)));list.append(row);
    input.onchange=()=>{filters[key]=input.checked?[...filters[key],value]:filters[key].filter(v=>v!==value);if(key==='folders')filters.documents=filters.documents.filter(d=>records.some(p=>p.document===d&&GraphResultCore.matchesSource(p,{folders:filters.folders})));change()};
   }
   search.oninput=()=>{for(const row of list.children)row.hidden=!row.dataset.search.includes(search.value.toLocaleLowerCase())};
   search.value=previous[key]?.search||'';search.oninput();list.scrollTop=previous[key]?.scroll||0;
   if(!options.length)list.append(el('p',t('Sin fuentes publicadas','No published sources','Aucune source publiée')));
  }
  const selected=records.filter(p=>GraphResultCore.matchesSource(p,filters));
  const status=el('p',graph?t(`${selected.length} de ${records.length} páginas · ${new Set(selected.map(p=>p.document)).size} documentos de la versión publicada.`,`${selected.length} of ${records.length} pages · ${new Set(selected.map(p=>p.document)).size} documents in the published version.`,`${selected.length} sur ${records.length} pages · ${new Set(selected.map(p=>p.document)).size} documents de la version publiée.`):t('Cargando fuentes…','Loading sources…','Chargement des sources…'));status.setAttribute('role','status');box.append(status);
  box.append(el('small',locked?t('Alcance guardado de esta respuesta y su espina. Usa «Nueva pregunta» para cambiarlo.','Saved scope for this answer and its fishbone. Use “New question” to change it.','Portée enregistrée pour cette réponse et son diagramme. Utilisez « Nouvelle question » pour la modifier.'):t('Puedes elegir varias opciones. Los filtros se combinan y delimitan el grafo y la próxima pregunta. Las consultas filtradas usan Relaciones concretas, con evidencia de estas fuentes.','Choose multiple options. Filters combine to restrict the graph and the next question. Filtered queries use Specific relationships with evidence from these sources.','Choisissez plusieurs options. Les filtres combinés délimitent le graphe et la prochaine question. Les questions filtrées utilisent Relations précises et les preuves de ces sources.')));
 }
 const api={get,set(value){filters={folders:[...value?.folders||[]],documents:[...value?.documents||[]]};draw()},setGraph(value){graph=value;draw()},paint:draw,setLocked(value){locked=value;draw()},setEnabled(value){enabled=value;draw()},get run(){return graph?.run_id},get active(){return !!(filters.folders.length||filters.documents.length)}};
 window.KnowledgeSourceScope=api;draw();return api;
};
(()=>{const s=document.createElement('style');s.textContent='.kg-source-filters{margin:14px 0;padding:16px 20px;border:1px solid #cbd7cc;border-radius:10px;background:#f2f5ef}.kg-scope-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.kg-scope-controls{display:grid;grid-template-columns:1fr 2fr;gap:12px;margin:12px 0}.kg-scope-controls details{min-width:0;background:#fffefa;border:1px solid #d1dbcf;border-radius:6px;padding:12px}.kg-scope-controls summary{cursor:pointer;font-weight:600}.kg-scope-controls input[type=search]{box-sizing:border-box;width:100%;margin:12px 0}.kg-scope-list{max-height:240px;overflow:auto}.kg-scope-list label{display:flex;gap:8px;padding:7px;align-items:center;overflow-wrap:anywhere}.kg-scope-list label[hidden]{display:none}.kg-scope-list span{flex:1;min-width:0}.kg-scope-list small{color:#6c8070}.kg-source-filters>p{font-size:13px;margin:9px 0}.kg-source-filters>small{font-size:12px;color:#52685e;line-height:1.7}@media(max-width:700px){.kg-scope-controls{grid-template-columns:1fr}}';document.head.append(s)})();
