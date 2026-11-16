// Read-only local reading guide. Text is always inserted as text nodes.
const searchLabels={
 es:['Búsqueda sencilla','Búsqueda sencilla','Busca personas, lugares o datos en todas las transcripciones. Sin conexiones externas.','Persona, lugar, fecha o tema…','Todas las palabras','Frase en orden','Incluir variantes aproximadas','Buscar','páginas encontradas','documentos','páginas consultables','páginas sin texto disponible','No se encontraron coincidencias. Esto no demuestra que el dato esté ausente del original.','Página PDF','Abrir página de origen','Coincidencia aproximada: revisar','Coincidencia textual','Lectura original','Edición humana','Segunda lectura','Buscando…','No se pudo realizar la búsqueda.','Las palabras se buscan en una misma página, sin distinguir mayúsculas ni acentos. No traduce ni busca por significado. Las lecturas alternativas se agrupan sin duplicar páginas; las copias en otras carpetas conservan su referencia.','Pendiente de validación','Validada por una persona','Borrador / pendiente'],
 en:['Simple search','Simple search','Find people, places or facts across all transcriptions. No external connections.','Person, place, date or topic…','All words','Phrase in order','Include approximate variants','Search','matching pages','documents','searchable pages','pages without available text','No matches. This does not establish absence from the original.','PDF page','Open source page','Approximate match: review','Text match','Original reading','Human edit','Second reading','Searching…','Search failed.','Words must occur on the same page; case and accents are ignored. No translation or semantic search. Alternate readings are grouped without duplicate pages; copies in other folders retain their references.','Not human validated','Human validated','Draft / pending'],
 fr:['Recherche simple','Recherche simple','Recherchez personnes, lieux ou données dans toutes les transcriptions. Sans connexion externe.','Personne, lieu, date ou sujet…','Tous les mots','Expression dans l’ordre','Inclure les variantes approximatives','Chercher','pages trouvées','documents','pages consultables','pages sans texte disponible','Aucun résultat. Cela ne démontre pas une absence dans l’original.','Page PDF','Ouvrir la page source','Correspondance approximative : vérifier','Correspondance textuelle','Lecture originale','Édition humaine','Seconde lecture','Recherche…','Échec de la recherche.','Les mots doivent figurer sur la même page ; casse et accents ignorés. Sans traduction ni recherche sémantique. Les lectures alternatives sont regroupées ; les copies dans d’autres dossiers conservent leurs références.','Non validée par une personne','Validée par une personne','Brouillon / en attente']};
const sl=i=>searchLabels[uiLanguage]?.[i]||searchLabels.es[i];
const searchView=document.createElement('section');searchView.id='view-search';searchView.hidden=true;searchView.dataset.noI18n='';main.append(searchView);
let searchData=null,searchBusy=false,searchSequence=0,searchLanguage=null;
const searchNav=drawNavigation;drawNavigation=function(){searchNav();const b=document.createElement('button');b.textContent=sl(0);b.dataset.view='search';b.setAttribute('aria-pressed',String(activeView==='search'));b.onclick=()=>showView('search');nav.append(b);if(activeView==='search'&&searchLanguage!==uiLanguage&&!searchBusy)drawSearch()};
const searchShow=showView;showView=function(name){searchShow(name);searchView.hidden=name!=='search';if(name==='search')drawSearch()};
function se(tag,text){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e}
let sourceSearch=null,sourceRanges=[],sourceRangeIndex=0;
const sourcePopup=se('dialog');sourcePopup.id='search-source-popup';document.body.append(sourcePopup);let popupRequest=0,popupAbort=null;
sourcePopup.addEventListener('close',()=>{popupRequest++;popupAbort?.abort()});
async function openSearchSource(source,page){
 const hit=searchData.hits.find(h=>h.document===source&&h.page===page);if(!hit)return;
 const request=++popupRequest;popupAbort?.abort();popupAbort=new AbortController();
 sourcePopup.replaceChildren();const header=se('header'),title=se('h2',source+' · '+sl(13)+' '+page),close=se('button',({es:'Cerrar',en:'Close',fr:'Fermer'})[uiLanguage]);close.type='button';close.onclick=()=>sourcePopup.close();header.append(title,close);sourcePopup.append(header);
 const message=se('p',sl(20));message.setAttribute('role','status');sourcePopup.append(message);if(!sourcePopup.open)sourcePopup.showModal();
 try{
  const response=await fetch('/content-search-page?'+new URLSearchParams({q:searchData.query,mode:searchData.mode,document:hit.document_id,page}),{cache:'no-store',signal:popupAbort.signal});if(!response.ok)throw Error();const data=await response.json();if(request!==popupRequest||!sourcePopup.open)return;
  const matches=data.hits[0]?.matches||[];message.textContent=({es:'Lecturas originales y ediciones humanas. Consulta de solo lectura; no modifica revisiones.',en:'Readings with matches. Read only; reviews are not modified.',fr:'Lectures avec correspondances. Consultation seule, sans modifier les révisions.'})[uiLanguage];
  const tools=se('div');tools.className='source-popup-tools';const select=se('select');select.setAttribute('aria-label',({es:'Versión de la transcripción',en:'Transcription version',fr:'Version de transcription'})[uiLanguage]);
  const versionName=m=>(m.version==='original'?sl(17):m.version==='human'?sl(18):sl(19)+' · '+m.version.split(':')[1])+' · '+(m.status==='stale'?({es:'El original cambió: requiere comparación',en:'Original changed: compare again',fr:'Original modifié : comparer de nouveau'})[uiLanguage]:m.status==='validated'?sl(24):m.version==='human'?sl(25):sl(23));
  matches.forEach((m,i)=>{const option=se('option',versionName(m));option.value=i;select.append(option)});tools.append(select);sourcePopup.append(tools);
  const panes=se('div');panes.className='source-popup-panes';const imageBox=se('div');imageBox.className='source-popup-image';const image=se('img');image.alt=source+' · '+sl(13)+' '+page;image.src='/page-image?'+new URLSearchParams({document:hit.document_id,page});image.onerror=()=>{imageBox.replaceChildren(se('p',({es:'Imagen no disponible',en:'Image unavailable',fr:'Image indisponible'})[uiLanguage]))};imageBox.append(image);
  let imageZoom=100;for(const [label,change] of [['−',-20],['+',20]]){const b=se('button',label);b.type='button';b.setAttribute('aria-label',label==='+'?'Acercar imagen':'Alejar imagen');b.onclick=()=>{imageZoom=Math.max(40,Math.min(300,imageZoom+change));image.style.width=imageZoom+'%'};tools.append(b)}
  const textBox=se('div');textBox.className='source-popup-text';panes.append(imageBox,textBox);sourcePopup.append(panes);
  const count=se('span');tools.append(count);let marks=[],index=0;
  const navigate=delta=>{if(!marks.length)return;index=(index+delta+marks.length)%marks.length;marks.forEach(m=>m.classList.remove('active'));marks[index].classList.add('active');textBox.scrollTop+=marks[index].getBoundingClientRect().top-textBox.getBoundingClientRect().top-textBox.clientHeight/3};
  for(const [label,delta] of [['←',-1],['→',1]]){const b=se('button',label);b.type='button';b.setAttribute('aria-label',delta<0?'Coincidencia anterior':'Siguiente coincidencia');b.onclick=()=>navigate(delta);tools.append(b)}
  function paint(){textBox.replaceChildren();const m=matches[Number(select.value)];if(!m){textBox.textContent=sl(12);return}const explanation=se('p',m.criteria.map(c=>c.label+(c.approximate?' ≈':'')).join(' · '));explanation.className='source-popup-reasons';textBox.append(explanation);const pre=se('div');pre.className='source-popup-transcription';const ranges=m.criteria.flatMap(c=>c.offsets).sort((a,b)=>a[0]-b[0]);let end=0;marks=[];
   for(const [a,b] of ranges){if(a<end)continue;pre.append(document.createTextNode(m.text.slice(end,a)));const mark=se('mark',m.text.slice(a,b));marks.push(mark);pre.append(mark);end=b}pre.append(document.createTextNode(m.text.slice(end)));textBox.append(pre);count.textContent=marks.length+' '+({es:'coincidencias',en:'matches',fr:'correspondances'})[uiLanguage];index=0;requestAnimationFrame(()=>{if(request===popupRequest)navigate(0)})
  }const choose=se('button','Marcar esta lectura como relevante');choose.type='button';choose.onclick=()=>{if(typeof matrixAdd==='function'){matrixAdd({...hit,matches},matches[Number(select.value)].version);choose.textContent='Lectura seleccionada ✓'}};tools.append(choose);select.onchange=()=>{choose.textContent='Marcar esta lectura como relevante';paint()};paint();return true;
 }catch(error){if(request===popupRequest&&error.name!=='AbortError')message.textContent=sl(21)}
}
function sourceNormalize(value){return value.normalize('NFD').replace(/\p{M}/gu,'').toLowerCase()}
function paintSourceSearch(){
 CSS.highlights?.delete('maph-search');sourceRanges=[];
 document.getElementById('source-search-tools')?.remove();
 const editor=document.getElementById('ue-text');if(!sourceSearch||!editor||!u.page)return;
 const tokens=[...editor.textContent.matchAll(/[\p{L}\p{N}_]+/gu)];
 const terms=[...sourceSearch.query.matchAll(/[\p{L}\p{N}_]+/gu)].map(m=>sourceNormalize(m[0]));
 const variants=new Set(terms);
 if(sourceSearch.mode==='approximate'){
  const hit=sourceSearch.hits.find(h=>h.document===u.page.doc.source&&h.page===u.page.number);
  for(const match of hit?.matches||[])for(const excerpt of match.excerpts)for(const [a,b] of excerpt.highlights)variants.add(sourceNormalize(excerpt.text.slice(a,b)));
 }
 const offsets=[];
 if(sourceSearch.mode==='phrase'){
  for(let i=0;i<=tokens.length-terms.length;i++)if(terms.every((term,j)=>sourceNormalize(tokens[i+j][0])===term))offsets.push([tokens[i].index,tokens[i+terms.length-1].index+tokens[i+terms.length-1][0].length]);
 }else for(const token of tokens)if(variants.has(sourceNormalize(token[0])))offsets.push([token.index,token.index+token[0].length]);
 const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT),nodes=[];let node,position=0;
 while(node=walker.nextNode()){nodes.push({node,start:position,end:position+node.length});position+=node.length}
 for(const [start,end] of offsets){const a=nodes.find(n=>n.start<=start&&start<n.end),b=nodes.find(n=>n.start<end&&end<=n.end);if(!a||!b)continue;const range=new Range();range.setStart(a.node,start-a.start);range.setEnd(b.node,end-b.start);sourceRanges.push(range)}
 if(CSS.highlights&&typeof Highlight!=='undefined')CSS.highlights.set('maph-search',new Highlight(...sourceRanges));
 const tools=se('div');tools.id='source-search-tools';tools.append(se('span','“'+sourceSearch.query+'” · '+sourceRanges.length+' '+({es:'coincidencias en esta lectura',en:'matches in this reading',fr:'correspondances dans cette lecture'})[uiLanguage]));
 for(const [label,action] of [['←',()=>focusSourceMatch(sourceRangeIndex-1)],['→',()=>focusSourceMatch(sourceRangeIndex+1)],['×',()=>{sourceSearch=null;paintSourceSearch()}]]){const button=se('button',label);button.type='button';button.disabled=label!=='×'&&!sourceRanges.length;button.setAttribute('aria-label',({es:label==='×'?'Quitar resaltado':label==='←'?'Coincidencia anterior':'Siguiente coincidencia',en:label==='×'?'Clear highlights':label==='←'?'Previous match':'Next match',fr:label==='×'?'Effacer le surlignage':label==='←'?'Correspondance précédente':'Correspondance suivante'})[uiLanguage]);button.onclick=action;tools.append(button)}
 editor.closest('.ue-text-panel').querySelector('.ue-panel-head').append(tools);
}
function focusSourceMatch(index){if(!sourceRanges.length)return;sourceRangeIndex=(index+sourceRanges.length)%sourceRanges.length;const editor=document.getElementById('ue-text'),rect=sourceRanges[sourceRangeIndex].getBoundingClientRect(),box=editor.getBoundingClientRect();editor.scrollTop+=rect.top-box.top-editor.clientHeight/3}
const searchPaintText=uPaintText;uPaintText=function(...args){const result=searchPaintText(...args);paintSourceSearch();return result};
const searchBuildSource=uBuild;uBuild=function(...args){const result=searchBuildSource(...args);paintSourceSearch();return result};
const sourceHighlightStyle=se('style');sourceHighlightStyle.textContent='::highlight(maph-search){background:#ffda54;color:#111}#source-search-tools{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:12px;flex-basis:100%}.ue-text-panel>.ue-panel-head:has(#source-search-tools){flex-wrap:wrap}#source-search-tools button{padding:3px 9px}';document.head.append(sourceHighlightStyle);
function drawSearch(){
 searchLanguage=uiLanguage;
 const old=searchView.querySelector('input'),value=old?.value||'',mode=searchView.querySelector('select')?.value||'flexible';
 searchView.replaceChildren(se('h2',sl(1)),se('p',sl(2)));
 const form=se('form'),label=se('label',sl(0)+' '),input=se('input');input.type='search';input.required=true;input.minLength=2;input.maxLength=200;input.placeholder=sl(3);input.value=value;label.append(input);
 const select=se('select');select.setAttribute('aria-label',sl(1));['flexible','words','approximate','phrase'].forEach((v,i)=>{const o=se('option',i===0?({es:'Flexible · cualquiera de los criterios',en:'Flexible · any criterion',fr:'Flexible · un des critères'})[uiLanguage]:sl(({words:4,approximate:6,phrase:5})[v]));o.value=v;select.append(o)});select.value=mode;
 const button=se('button',sl(7));button.type='submit';button.disabled=searchBusy;form.append(label,select,button);searchView.append(form,se('p',({es:'Escribe varios criterios separados por espacios. Entre comillas: palabras en orden con hasta dos palabras intermedias en total. Flexible incluye resultados parciales y variantes de escritura; ≈ indica una aproximación. Busca en originales y ediciones humanas; identifica cada lectura.',en:'Separate criteria with spaces. Quotes: ordered words with up to two intervening words in total. Flexible includes partial matches and spelling variants; ≈ marks approximate matches. Searches originals and human edits, identifying each reading.',fr:'Séparez les critères par des espaces. Guillemets : mots en ordre avec au plus deux mots intermédiaires au total. Flexible inclut les résultats partiels et les variantes ; ≈ indique une approximation. Recherche dans les originaux et éditions humaines.'})[uiLanguage]));
 const status=se('p',searchBusy?sl(20):'');status.setAttribute('role','status');searchView.append(status);
 const tree=se('div');searchView.append(tree);
 form.onsubmit=async e=>{e.preventDefault();const sequence=++searchSequence;searchBusy=true;button.disabled=true;status.textContent=sl(20);tree.replaceChildren();try{const r=await fetch('/content-search?'+new URLSearchParams({q:input.value,mode:select.value}),{cache:'no-store'});if(!r.ok)throw Error();const data=await r.json();if(sequence!==searchSequence)return;searchData=data;renderSearchTree(tree,status)}catch{if(sequence===searchSequence){searchData=null;status.textContent=sl(21)}}finally{if(sequence===searchSequence){searchBusy=false;button.disabled=false}}};
 if(searchData&&!searchBusy)renderSearchTree(tree,status);
}
function renderSearchTree(tree,status){
 tree.replaceChildren();const filters=se('div');filters.className='search-filters';const content=se('div');tree.append(filters,content);
 const controls={};
 function menu(key,label,options){const wrap=se('label',label),select=se('select');select.setAttribute('aria-label',label);for(const [value,text] of options){const o=se('option',text);o.value=value;select.append(o)}wrap.append(select);filters.append(wrap);controls[key]=select;select.onchange=apply;return select}
 const all=({es:'Todos',en:'All',fr:'Tous'})[uiLanguage];
 menu('folder',({es:'Carpeta',en:'Folder',fr:'Dossier'})[uiLanguage],[['',all],...[...new Set(searchData.hits.map(h=>h.folder))].map(v=>[v,v])]);
 menu('criterion',({es:'Criterio encontrado',en:'Matched criterion',fr:'Critère trouvé'})[uiLanguage],[['',all],...(searchData.criteria||[]).map(c=>[String(c.id),c.label])]);
 menu('minimum',({es:'Mínimo de criterios por lectura',en:'Minimum criteria per reading',fr:'Minimum de critères par lecture'})[uiLanguage],(searchData.criteria||[{}]).map((c,i)=>[String(i+1),String(i+1)]));
 menu('version',({es:'Versión',en:'Version',fr:'Version'})[uiLanguage],[['',all],['original',sl(17)],['human',sl(18)],['second_reading',sl(19)]]);
 menu('kind',({es:'Coincidencia',en:'Match',fr:'Correspondance'})[uiLanguage],[['',all],['exact',sl(16)],['approximate',sl(15)]]);
 function apply(){const hits=searchData.hits.filter(h=>!controls.folder.value||h.folder===controls.folder.value).map(h=>({...h,matches:h.matches.filter(m=>(!controls.version.value||m.version.split(':')[0]===controls.version.value)&&(!controls.criterion.value||m.criteria.some(c=>String(c.criterion)===controls.criterion.value))&&m.criteria.length>=Number(controls.minimum.value)&&(!controls.kind.value||(controls.kind.value==='approximate'?m.approximate:!m.approximate)))})).filter(h=>h.matches.length);const d={...searchData,hits,total_pages:hits.length,documents:new Set(hits.map(h=>h.document)).size};renderSearchTreeContent(content,status,d)}apply();
}
function renderSearchTreeContent(tree,status,d){tree.replaceChildren();status.textContent=`“${d.query}” · ${d.total_pages} ${sl(8)} · ${d.documents} ${sl(9)} · ${d.pages_searched} ${sl(10)} · ${d.pages_without_text} ${sl(11)}`;
 if(!d.hits.length){tree.append(se('p',sl(12)));return}
 const folders=new Map();for(const hit of d.hits){if(!folders.has(hit.folder))folders.set(hit.folder,new Map());const docs=folders.get(hit.folder);if(!docs.has(hit.document))docs.set(hit.document,[]);docs.get(hit.document).push(hit)}
 renderSearchGraph(tree,folders,status);
 const list=se('details');list.append(se('summary',({es:'Ver fragmentos y referencias',en:'Show excerpts and references',fr:'Voir les extraits et références'})[uiLanguage]));tree.append(list);
 for(const [folder,docs] of folders){const branch=se('details');branch.open=true;branch.append(se('summary',folder+' · '+docs.size+' '+sl(9)));list.append(branch);
 for(const [source,hits] of docs){const doc=se('details');doc.open=docs.size===1;doc.append(se('summary',source.split('/').pop()+' · '+hits.length+' '+sl(8)));branch.append(doc);
 for(const hit of hits){const page=se('article');page.append(se('h3',sl(13)+' '+hit.page));
 for(const match of hit.matches){const version=match.version==='human'?sl(18):match.version==='original'?sl(17):sl(19)+' · '+match.version.split(':')[1];page.append(se('p',version+' · '+sl(match.status==='validated'?24:match.version==='human'?25:23)+' · '+sl(match.approximate?15:16)));page.append(se('p',match.criteria.map(c=>c.label+(c.approximate?' ≈':'')).join(' · ')));if(typeof matrixToggle==='function')page.append(matrixToggle(hit,match.version));
 for(const excerpt of match.excerpts){const quote=se('blockquote');let offset=0;for(const [a,b] of excerpt.highlights){if(a<offset)continue;quote.append(document.createTextNode(excerpt.text.slice(offset,a)),se('mark',excerpt.text.slice(a,b)));offset=b}quote.append(document.createTextNode(excerpt.text.slice(offset)));page.append(quote)}}
 const open=se('button',sl(14)+' →');open.type='button';open.onclick=async()=>{try{if(!state){const r=await fetch('/progress.json');state=await r.json()}await openSearchSource(source,hit.page)}catch{status.textContent=sl(21)}};page.append(open);doc.append(page)}}}
}
function renderSearchGraph(container,folders,status,options={}){
 const graphData=options.data||searchData,openSource=options.openSource||openSearchSource;
 const markerId="sg-arrow-"+Math.random().toString(36).slice(2);
 const labels=({es:['Mapa de lectura','Arrastra el fondo para desplazarte. Usa la rueda o los botones para acercar. Las páginas coincidentes se conectan en orden numérico; los saltos no implican páginas faltantes.','Alejar','Acercar','Inicio','Abrir página de origen','Selecciona una página para ver sus coincidencias.'],en:['Reading map','Drag the background to pan. Scroll or use buttons to zoom. Matching pages connect in numerical order; gaps do not mean missing pages.','Zoom out','Zoom in','Home','Open source page','Select a page to inspect its matches.'],fr:['Carte de lecture','Faites glisser le fond pour déplacer la carte. Utilisez la molette pour zoomer. Les pages trouvées sont reliées dans l’ordre numérique.','Réduire','Agrandir','Début','Ouvrir la page source','Sélectionnez une page pour voir ses extraits.']})[uiLanguage];
 const panel=se('div');panel.className='search-graph-panel';panel.append(se('h3',labels[0]),se('p',labels[1]));
 const controls=se('div');controls.className='search-graph-controls';panel.append(controls);
 const viewport=se('div');viewport.className='search-graph-viewport';viewport.tabIndex=0;viewport.setAttribute('aria-label',labels[0]);panel.append(viewport);
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('role','group');svg.setAttribute('aria-label',labels[0]);viewport.append(svg);
 const inspector=se('div',labels[6]);inspector.className='sg-inspector';inspector.setAttribute('aria-live','polite');panel.append(inspector);container.append(panel);
 const closed=new Set();for(const docs of folders.values())for(const [source,hits] of docs)if(hits.length>12)closed.add('file:'+source);
 const jump=se('select');jump.setAttribute('aria-label',({es:'Ir al documento',en:'Go to document',fr:'Aller au document'})[uiLanguage]);const placeholder=se('option',jump.getAttribute('aria-label'));placeholder.value='';jump.append(placeholder);for(const docs of folders.values())for(const source of docs.keys()){const option=se('option',source);option.value='file:'+source;jump.append(option)}controls.append(jump);let positions=new Map();jump.onchange=()=>{const y=positions.get(jump.value);if(y!==undefined){camera.y=Math.max(0,y-70);camera.x=0;view()}};
 let camera={x:0,y:0,w:1080,h:520},drag=null,moved=false;
 function el(tag,attrs,text){const n=document.createElementNS(svg.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
 function view(){camera.h=camera.w*viewport.clientHeight/Math.max(1,viewport.clientWidth);svg.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.w} ${camera.h}`)}
 function zoom(factor,cx=.5,cy=.5){const next=Math.max(380,Math.min(2400,camera.w*factor)),ratio=next/camera.w;camera.x+=camera.w*cx*(1-ratio);camera.y+=camera.h*cy*(1-ratio);camera.w=next;view()}
 function inspect(hit){inspector.replaceChildren(se('strong',hit.document+' · '+sl(13)+' '+hit.page));
  for(const match of hit.matches){inspector.append(se('p',(match.version==='original'?sl(17):match.version==='human'?sl(18):sl(19))+' · '+sl(match.approximate?15:16)));inspector.append(se('p',match.criteria.map(c=>c.label+(c.approximate?' ≈':'')).join(' · ')));for(const excerpt of match.excerpts.slice(0,2))inspector.append(se('blockquote',excerpt.text))}
  const open=se('button',labels[5]+' →');open.type='button';open.onclick=async()=>{try{await openSource(hit.document,hit.page)}catch{status.textContent=sl(21)}};inspector.append(open);
 }
 function draw(){
  svg.replaceChildren();const defs=el('defs',{}),marker=el('marker',{id:markerId,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});marker.append(el('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#ff4d16'}));defs.append(marker);svg.append(defs);
  const nodes=[],edges=[];let y=110;
  function node(key,label,kind,x,y,w,hit){const n={key,label,kind,x,y,w,hit};nodes.push(n);return n}
  const root=node('query',graphData.query,0,24,30,240);
  for(const [folder,docs] of folders){const f=node('folder:'+folder,folder,1,24,y,170);edges.push([root,f,false]);
   if(closed.has(f.key)){y+=90;continue}
   for(const [source,hits] of docs){const file=node('file:'+source,source.split('/').pop()+' · '+hits.length,2,230,y,220);edges.push([f,file,false]);
    if(closed.has(file.key)){y+=90;continue}
    const sorted=hits.slice().sort((a,b)=>a.page-b.page);let previous=file;
    sorted.forEach((hit,i)=>{const row=Math.floor(i/4),col=row%2?3-i%4:i%4;
     const page=node('page:'+source+':'+hit.page,sl(13)+' '+hit.page,3,500+col*140,y+row*76,116,hit);edges.push([previous,page,true]);previous=page});
    y+=Math.max(1,Math.ceil(sorted.length/4))*76+36;
   }y+=30;
  }
  for(const [a,b,chain] of edges){let d;
   if(chain&&a.kind===3){if(a.y===b.y){const right=b.x>a.x;d=`M ${right?a.x+a.w:a.x} ${a.y+20} L ${right?b.x:b.x+b.w} ${b.y+20}`}else{const x=a.x+a.w/2;d=`M ${x} ${a.y+40} L ${x} ${b.y}`}}
   else if(a.kind===0){d=`M ${a.x+85} ${a.y+40} L ${b.x+85} ${b.y}`}
   else{const sx=a.x+a.w,sy=a.y+20;d=`M ${sx} ${sy} C ${sx+26} ${sy}, ${b.x-26} ${b.y+20}, ${b.x} ${b.y+20}`}
   svg.append(el('path',{d,class:chain?'sg-edge sg-chain':'sg-edge',...(chain?{'marker-end':'url(#'+markerId+')'}:{})}))
  }
  for(const n of nodes){const g=el('g',{transform:`translate(${n.x},${n.y})`,class:'sg-node sg-kind-'+n.kind,'data-key':n.key});g.append(el('rect',{width:n.w,height:40,rx:10}));
   const max=Math.floor((n.w-24)/7),label=n.hit?'p. '+n.hit.page+' · '+Math.max(...n.hit.matches.map(m=>m.criteria.length))+'/'+graphData.criteria.length:n.label.length>max?n.label.slice(0,max-1)+'…':n.label;
   g.append(el('text',{x:12,y:25},(n.kind===1||n.kind===2?(closed.has(n.key)?'▸ ':'▾ '):'')+label),el('title',{},n.label+(n.hit?' · '+n.hit.document+' · '+[...new Set(n.hit.matches.flatMap(m=>m.criteria.map(c=>c.label+(c.approximate?' ≈':''))))].join(', '):'')));
   if(n.kind>0){g.setAttribute('role','button');g.setAttribute('tabindex','0');g.setAttribute('aria-label',n.label+(n.hit?' · '+n.hit.document+' · '+[...new Set(n.hit.matches.flatMap(m=>m.criteria.map(c=>c.label+(c.approximate?' ≈':''))))].join(', '):''));if(n.kind<3)g.setAttribute('aria-expanded',String(!closed.has(n.key)));
    const activate=()=>{if(moved)return;if(n.hit){svg.querySelectorAll('.sg-selected').forEach(e=>e.classList.remove('sg-selected'));g.classList.add('sg-selected');inspect(n.hit);openSource(n.hit.document,n.hit.page)}else{closed.has(n.key)?closed.delete(n.key):closed.add(n.key);draw()}};g.onclick=activate;g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();moved=false;activate()}};
   }svg.append(g)
  }positions=new Map(nodes.map(n=>[n.key,n.y]));view();
 }
 svg.onpointerdown=e=>{moved=false;if(e.target.closest('[role=button]'))return;drag={x:e.clientX,y:e.clientY,cx:camera.x,cy:camera.y};moved=false;svg.setPointerCapture(e.pointerId)};
 svg.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;moved=Math.abs(dx)+Math.abs(dy)>3;camera.x=drag.cx-dx*camera.w/viewport.clientWidth;camera.y=drag.cy-dy*camera.h/viewport.clientHeight;view()};
 svg.onpointerup=()=>{drag=null};svg.onpointercancel=()=>{drag=null};
 viewport.addEventListener('wheel',e=>{e.preventDefault();const r=viewport.getBoundingClientRect();zoom(e.deltaY>0?1.12:1/1.12,(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height)},{passive:false});
 viewport.onkeydown=e=>{if(e.target!==viewport)return;const moves={ArrowDown:[0,80],ArrowUp:[0,-80],ArrowLeft:[-80,0],ArrowRight:[80,0]};if(moves[e.key]){e.preventDefault();camera.x+=moves[e.key][0];camera.y+=moves[e.key][1];view()}};
 for(const [label,action] of [[labels[2],()=>zoom(1.2)],[labels[3],()=>zoom(1/1.2)],[labels[4],()=>{camera={x:0,y:0,w:1080,h:520};view()}]]){const b=se('button',label);b.type='button';b.onclick=action;controls.append(b)}draw();
}
const searchStyle=se('style');searchStyle.textContent=`#view-search{padding:24px;max-width:1100px;margin:auto;max-height:none;overflow:visible}#view-search form{display:flex;gap:12px;align-items:end;flex-wrap:wrap}#view-search label{display:flex;flex-direction:column;gap:8px;flex:1}#view-search input{min-width:200px;width:100%;box-sizing:border-box}#view-search details{margin:14px 0 14px 12px;padding:12px;border-left:2px solid var(--line)}#view-search summary{cursor:pointer;font-weight:600;overflow-wrap:anywhere}#view-search article{padding:16px;margin:12px 0;background:var(--white,#fffefa);border:1px solid var(--line)}#view-search blockquote{white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0;line-height:1.6}#view-search article p{font-size:12px;color:var(--muted)}#view-search mark{background:#ffe0a3;color:#111}#view-search h3{font-size:17px}.search-graph-panel{margin:22px 0}.search-graph-controls{display:flex;gap:8px;margin:12px 0}.search-graph-viewport{overflow:hidden;height:520px;min-height:320px;max-height:65vh;touch-action:none;cursor:grab;border:1px solid var(--line);background:#fffefa;border-radius:12px}.search-graph-viewport svg{display:block;width:100%;height:100%;max-width:none}.sg-chain{stroke:#ff4d16;stroke-width:2}.sg-selected rect{stroke:#ff4d16;stroke-width:3;fill:#ffe4d6}.sg-inspector{padding:16px;border:1px solid var(--line);margin-top:12px;max-height:300px;overflow:auto}.sg-edge{fill:none;stroke:#a9a198;stroke-width:1.5}.sg-column{fill:#625d56;font-size:12px;font-weight:600}.sg-node rect{fill:#f6f5f1;stroke:#bbb4aa}.sg-node text{fill:#111215;font-size:13px}.sg-kind-0 rect{fill:#111215}.sg-kind-0 text{fill:white}.sg-kind-1 rect{fill:#ffe4d6;stroke:#ff4d16}.sg-kind-3 rect{fill:#fffefa}.sg-node[role=button]{cursor:pointer}.sg-node[role=button]:hover rect,.sg-node:focus rect{stroke:#ff4d16;stroke-width:3}.sg-node:focus{outline:none}`;document.head.append(searchStyle);drawNavigation();

const popupStyle=se('style');popupStyle.textContent=`#search-source-popup{width:94vw;max-width:1700px;height:92vh;max-height:94vh;box-sizing:border-box;background:var(--paper);color:var(--ink);border:1px solid var(--line);border-radius:12px;padding:18px;overflow:hidden}#search-source-popup[open]{display:flex;flex-direction:column;gap:10px}#search-source-popup::backdrop{background:#111a}#search-source-popup header{display:flex;justify-content:space-between;gap:15px;margin:0;padding:0}#search-source-popup h2{font-size:18px;overflow-wrap:anywhere;margin:0}#search-source-popup>p{font-size:12px;margin:0}.source-popup-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.source-popup-tools select{max-width:100%}.source-popup-panes{display:grid;grid-template-columns:1fr 1fr;min-height:0;flex:1;gap:12px}.source-popup-image,.source-popup-text{overflow:auto;min-height:0;background:#fffefa;border:1px solid var(--line);padding:16px}.source-popup-image{background:#e9e7e0}.source-popup-image img{display:block;width:100%;max-width:none}.source-popup-transcription{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.8 Georgia,serif}.source-popup-reasons{position:sticky;top:-16px;margin:0 0 16px;padding:10px;background:#f6f5f1;font-size:13px}.source-popup-text mark{background:#ffdf6b;color:#111}.source-popup-text mark.active{background:#ff9b45;outline:2px solid #bd350d}.search-filters{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}.search-filters label{font-size:12px;min-width:130px}#view-search .search-filters select{width:100%}@media(max-width:700px){.source-popup-panes{grid-template-columns:1fr;grid-template-rows:1fr 1fr}}`;document.head.append(popupStyle);
