/* One review workspace. All document data and automatic saves stay on localhost. */
const UE_WORDS={
 document:['Documento','Document','Document'],page:['Página','Page','Page'],previous:['Página anterior','Previous page','Page précédente'],next:['Página siguiente','Next page','Page suivante'],
 image:['Imagen original','Original image','Image originale'],text:['Transcripción','Transcription','Transcription'],changes:['Mostrar cambios','Show changes','Afficher les modifications'],original:['Ver transcripción original','View original transcription','Voir la transcription originale'],
 originalNote:['Original del modelo, sólo lectura. Las adiciones se resaltan en verde; el texto retirado aparece tachado abajo.','Read-only model original. Additions are green; removed text is struck through below.','Original du modèle en lecture seule. Les ajouts sont en vert ; les suppressions sont barrées ci-dessous.'],
 fit:['Ajustar','Fit','Ajuster'],pending:['Dejar pendiente','Leave pending','Laisser en attente'],finish:['Revisada y seguir','Reviewed · next','Révisée · suivante'],
 saving:['Guardando…','Saving…','Enregistrement…'],saved:['Guardado','Saved','Enregistré'],unsaved:['Cambios pendientes','Unsaved changes','Modifications en attente'],clean:['Sin cambios · guardado automático activo','No changes · autosave on','Aucune modification · enregistrement automatique actif'],
 failed:['No se pudo guardar. Tu texto sigue aquí.','Could not save. Your text is still here.','Échec de l’enregistrement. Votre texte est conservé ici.'],retry:['Reintentar','Retry','Réessayer'],
 conflict:['La revisión cambió en otra sesión. Reabre la página para comparar y recuperar tu borrador.','The review changed in another session. Reopen the page to compare and restore your draft.','La révision a changé dans une autre session. Rouvrez la page pour comparer et restaurer votre brouillon.'],reopen:['Reabrir página','Reopen page','Rouvrir la page'],
 mark:['Marcar duda','Mark uncertainty','Signaler un doute'],addNote:['Añadir nota','Add note','Ajouter une note'],doubts:['dudas','uncertainties','doutes'],resolve:['Resolver','Resolve','Résoudre'],remove:['Quitar marca','Remove mark','Retirer la marque'],
 fragment:['Nota sobre este fragmento','Note on this fragment','Note sur ce fragment'],pageNote:['Nota de la página (opcional)','Page note (optional)','Note de page (facultative)'],
 reviewer:['¿Quién revisa hoy?','Who is reviewing today?','Qui révise aujourd’hui ?'],name:['Tu nombre','Your name','Votre nom'],start:['Empezar a revisar','Start reviewing','Commencer la révision'],identity:['Revisor','Reviewer','Réviseur'],identityHelp:['Lo recordamos en esta pestaña. Las correcciones se guardan automáticamente como borrador.','Remembered in this tab. Edits are automatically saved as drafts.','Mémorisé dans cet onglet. Les corrections sont enregistrées automatiquement en brouillon.'],
 notReviewed:['Sin revisar','Not reviewed','Non révisée'],draft:['Borrador','Draft','Brouillon'],deferred:['Pendiente de revisión','Review pending','Révision en attente'],uncertain:['Pendiente por dudas','Uncertainties pending','Doutes en attente'],validated:['Validada','Validated','Validée'],
 noPages:['Todavía no hay páginas disponibles para revisar.','No pages available to review yet.','Aucune page disponible pour révision.'],loading:['Abriendo página…','Opening page…','Ouverture de la page…'],loadError:['No se pudo abrir la página. Puedes intentarlo de nuevo.','Could not open the page. You can try again.','Impossible d’ouvrir la page. Réessayez.'],
 recovery:['Hay un borrador recuperable de esta página.','A recoverable draft exists for this page.','Un brouillon peut être récupéré pour cette page.'],restore:['Recuperar borrador','Restore draft','Restaurer le brouillon'],discard:['Usar versión guardada','Use saved version','Utiliser la version enregistrée'],
 allDone:['Llegaste al final de las páginas disponibles.','You reached the end of the available pages.','Vous avez atteint la fin des pages disponibles.'],needsDoubts:['Quedará pendiente mientras haya dudas abiertas.','It will remain pending while uncertainties are open.','La page restera en attente tant que des doutes subsistent.'],
 removedMark:['Una duda se retiró porque cambiaste su fragmento. Puedes marcarlo de nuevo.','An uncertainty was removed because you edited its text. You can mark it again.','Un doute a été retiré car son texte a changé. Vous pouvez le signaler de nouveau.'],
 selectHint:['Corrige directamente. Selecciona texto para marcar una duda o añadir una nota.','Edit directly. Select text to mark an uncertainty or add a note.','Corrigez directement. Sélectionnez du texte pour signaler un doute ou ajouter une note.'],
 empty:['Una página vacía no puede validarse.','An empty page cannot be validated.','Une page vide ne peut pas être validée.'],noImage:['Imagen no disponible','Image unavailable','Image indisponible'],stale:['El original cambió: compara de nuevo esta revisión.','The original changed: check this review again.','L’original a changé : vérifiez cette révision à nouveau.'],
 savedPending:['Guardada como pendiente.','Saved as pending.','Enregistrée en attente.'],savedValidated:['Validación guardada.','Validation saved.','Validation enregistrée.'],tipFinish:['Al pulsar, confirmas que comparaste toda la página con la imagen.','By clicking, you confirm you checked the entire page against the image.','En cliquant, vous confirmez avoir comparé toute la page à l’image.'],
 download:['Descargar resultados','Download results','Télécharger les résultats'],copy:['Copiar mi texto','Copy my text','Copier mon texte'],copied:['Texto copiado','Text copied','Texte copié'],zoomIn:['Ampliar imagen','Zoom in','Agrandir'],zoomOut:['Reducir imagen','Zoom out','Réduire']
};
const ut=k=>UE_WORDS[k]?.[['es','en','fr'].indexOf(uiLanguage)]||k;
const u={page:null,loading:false,busy:false,promise:null,timer:null,changeTimer:null,selection:null,showChanges:false,zoom:100,composing:false,lang:uiLanguage,reviewer:'',identityOpen:false,history:[],future:[],message:'',error:null};
function uRead(key){try{return JSON.parse(sessionStorage.getItem(key)||'null')}catch{return null}}
function uStore(key,value){try{sessionStorage.setItem(key,JSON.stringify(value))}catch{}}
function uRemove(key){try{sessionStorage.removeItem(key)}catch{}}
u.reviewer=uRead('maph-reviewer')||'';
const uk=p=>'maph-draft:'+p.id+':'+p.number;
const uBy=id=>document.getElementById(id);
function uSnapshot(p){return {text:p.text,basis:p.basis||'9b',annotations:structuredClone(p.annotations),note:p.note}}
function uBackup(){const p=u.page;if(!p)return;uStore(uk(p),{...uSnapshot(p),reviewer:u.reviewer,original_hash:p.originalHash,revision:p.revision})}
function uMarkDirty(){const p=u.page;if(!p)return;p.generation++;dirty=true;u.error=null;uBackup();clearTimeout(u.timer);u.timer=setTimeout(()=>uSave(),900);uUpdateStatus()}
function uHistory(){u.history.push(uSnapshot(u.page));if(u.history.length>80)u.history.shift();u.future=[]}
function uUndo(redo=false){if(!u.page||u.busy)return;const from=redo?u.future:u.history,to=redo?u.history:u.future;if(!from.length)return;to.push(uSnapshot(u.page));Object.assign(u.page,from.pop());uMarkDirty();uPaintText();uDrawDoubts();uDrawOriginal()}

// A single save queue preserves keystrokes entered during in-flight requests.
async function uSave(requested){
 clearTimeout(u.timer);if(!u.page)return true;
 if(u.promise){const ok=await u.promise;if(!ok)return false;return uSave(requested)}
 const p=u.page;if(!requested&&p.generation===p.savedGeneration)return true;
 if(!u.reviewer.trim()){u.identityOpen=true;uIdentity();return false}
 if(u.error==='conflict')return false;
 const generation=p.generation;
 const status=p.annotations.length?'deferred':requested||(p.status==='deferred'?'deferred':'draft');
 if(status==='validated'&&!p.text.trim()){u.message=ut('empty');uUpdateStatus();return false}
 const payload={document:p.id,page:p.number,original_hash:p.originalHash,revision:p.revision,text:p.text,annotations:structuredClone(p.annotations),note:p.note,reviewer:u.reviewer,basis:p.basis||'9b',status};
 u.promise=(async()=>{
  uUpdateStatus('saving');
  try{
   const r=await fetch('/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(20000)});
   if(!r.ok){u.error=r.status===409?'conflict':'failed';uBackup();return false}
   const saved=await r.json();p.revision=saved.revision;p.status=saved.status;p.updated=saved.updated;p.savedGeneration=generation;
   opened.data.review=saved;reviewIndex[p.id+':'+p.number]={status:saved.status,revision:saved.revision,updated:saved.updated};u.error=null;
   dirty=p.generation!==p.savedGeneration;if(!dirty)uRemove(uk(p));else uBackup();return true;
  }catch{u.error='failed';uBackup();return false}
  finally{u.promise=null;uUpdateStatus();drawInvitation()}
 })();
 const result=await u.promise;
 if(result&&p.generation!==p.savedGeneration)return uSave();
 return result;
}
async function uFlush(){if(u.promise&&!await u.promise)return false;return uSave()}
function uStatus(p){return p.annotations.length?'uncertain':({validated:'validated',deferred:'deferred',draft:'draft'})[p.status]||'notReviewed'}
function uUpdateStatus(forced){
 const p=u.page;if(!p)return;
 const status=uBy('ue-save');if(!status)return;
 const saving=forced==='saving'||!!u.promise;
 status.textContent=u.error?ut(u.error):saving?ut('saving'):p.generation!==p.savedGeneration?ut('unsaved'):p.updated?ut('saved')+' · '+new Date(p.updated*1000).toLocaleTimeString(uiLanguage,{hour:'2-digit',minute:'2-digit',second:'2-digit'}):ut('clean');
 status.dataset.state=u.error?'error':saving?'saving':'saved';
 uBy('ue-retry').hidden=!u.error||u.error==='conflict';uBy('ue-reopen').hidden=u.error!=='conflict';
 uBy('ue-status').textContent=ut(uStatus(p));uBy('ue-status').dataset.state=uStatus(p);
 uBy('ue-doubts').textContent=p.annotations.length+' '+ut('doubts');uBy('ue-doubts').hidden=!p.annotations.length;
 uBy('ue-finish').title=p.annotations.length?ut('needsDoubts'):ut('tipFinish');
 uBy('ue-notice').textContent=u.message;
 uBy('ue-finish').disabled=u.busy||!u.reviewer||!!u.error;
 uBy('ue-pending').disabled=u.busy||!u.reviewer||!!u.error;
 uBy('ue-text').contentEditable=String(!u.busy&&!!u.reviewer);
}

// The DOM contains only text plus annotation spans. Selection offsets match saved UTF-16 ranges.
function uSelection(){const el=uBy('ue-text'),s=getSelection();if(!el||!s.rangeCount)return null;const r=s.getRangeAt(0);if(!el.contains(r.startContainer)||!el.contains(r.endContainer))return null;
 const a=document.createRange();a.selectNodeContents(el);a.setEnd(r.startContainer,r.startOffset);const b=document.createRange();b.selectNodeContents(el);b.setEnd(r.endContainer,r.endOffset);return {start:a.toString().length,end:b.toString().length}}
function uSetSelection(start,end=start){const el=uBy('ue-text'),walk=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node,pos=0,a=null,b=null;
 while(node=walk.nextNode()){const next=pos+node.length;if(!a&&start<=next)a=[node,Math.max(0,start-pos)];if(end<=next){b=[node,Math.max(0,end-pos)];break}pos=next}
 if(!a||!b)return;const r=document.createRange();r.setStart(...a);r.setEnd(...b);const s=getSelection();s.removeAllRanges();s.addRange(r)}
function uPaintText(keep){
 const el=uBy('ue-text'),p=u.page;if(!el||!p||u.composing)return;
 const scroll=el.scrollTop,selection=keep?uSelection():null;
 const additions=[];if(u.showChanges){let offset=0;for(const t of reviewDiffTokens(p.original,p.text)){if(t.type==='removed')continue;if(t.type==='added')additions.push({start:offset,end:offset+t.text.length});offset+=t.text.length}}
 const sourceHits=typeof sourceReviewRanges==='function'?sourceReviewRanges(p):[];
 const points=new Set([0,p.text.length]);for(const m of [...p.annotations,...additions,...sourceHits]){points.add(m.start);points.add(m.end)}const sorted=[...points].sort((a,b)=>a-b),frag=document.createDocumentFragment();
 for(let i=0;i<sorted.length-1;i++){const start=sorted[i],end=sorted[i+1],mark=p.annotations.findIndex(m=>m.start<=start&&m.end>=end),added=additions.some(m=>m.start<=start&&m.end>=end);const node=document.createElement('span');node.textContent=p.text.slice(start,end);if(mark>=0){node.classList.add('ue-uncertain');node.dataset.mark=mark;node.title=p.annotations[mark].note||ut('mark')}if(added)node.classList.add('ue-added');const hit=sourceHits.find(m=>m.start<=start&&m.end>=end);if(hit){node.classList.add('ue-source-hit');node.dataset.sourceKind=hit.kind||'match'}frag.append(node)}
 if(!p.text)frag.append(document.createTextNode(''));el.replaceChildren(frag);if(selection)uSetSelection(selection.start,selection.end);el.scrollTop=scroll;
}
function uChangedText(next){const p=u.page;if(p.text===next)return;const oldCount=p.annotations.length;uBy('ue-fragment').hidden=true;uHistory();p.annotations=shiftReviewMarks(p.annotations,p.text,next);p.text=next;if(p.annotations.length<oldCount)u.message=ut('removedMark');else u.message='';uMarkDirty();uDrawDoubts();clearTimeout(u.changeTimer);u.changeTimer=setTimeout(()=>{uPaintText(true);uDrawOriginal()},250)}
function uInsert(text){if(u.busy||!u.reviewer)return;const s=uSelection();if(!s)return;const p=u.page,next=p.text.slice(0,s.start)+text+p.text.slice(s.end);uChangedText(next);uPaintText();uSetSelection(s.start+text.length)}
function uSelected(){u.selection=uSelection();const bar=uBy('ue-selection');if(!bar)return;bar.hidden=!u.selection||u.selection.start===u.selection.end||!u.reviewer}
function uAddMark(){const s=u.selection,p=u.page;if(!s||s.start===s.end)return;const existing=p.annotations.findIndex(m=>m.start<s.end&&m.end>s.start);if(existing>=0){uOpenNote(existing);return}uHistory();p.annotations.push({...s,quote:p.text.slice(s.start,s.end),note:''});uMarkDirty();uPaintText(true);uDrawDoubts();uOpenNote(p.annotations.length-1);uBy('ue-selection').hidden=true}
function uDrawDoubts(){const list=uBy('ue-doubt-list');if(!list)return;list.replaceChildren();u.page.annotations.forEach((m,i)=>{const row=document.createElement('button');row.type='button';row.textContent=(i+1)+'. '+m.quote;row.onclick=()=>uOpenNote(i);list.append(row)});uUpdateStatus()}
function uOpenNote(i){const m=u.page.annotations[i];if(!m)return;const panel=uBy('ue-fragment');panel.hidden=false;panel.dataset.index=i;uBy('ue-quote').textContent=m.quote;uBy('ue-fragment-note').value=m.note||'';uBy('ue-fragment-note').focus();uBy('ue-doubt-list').hidden=true}
function uRemoveMark(){const index=Number(uBy('ue-fragment').dataset.index);uHistory();u.page.annotations.splice(index,1);uBy('ue-fragment').hidden=true;uMarkDirty();uPaintText();uDrawDoubts()}
function uDrawOriginal(){const host=uBy('ue-original-text');if(!host)return;host.replaceChildren();for(const token of reviewDiffTokens(u.page.original,u.page.text)){const node=document.createElement(token.type==='removed'?'del':token.type==='added'?'ins':'span');node.textContent=token.text;host.append(node)}uBy('ue-raw-original').textContent=u.page.original}
function uIdentity(){const panel=uBy('ue-identity-panel');if(!panel)return;panel.hidden=!u.identityOpen&&!!u.reviewer;uBy('ue-reviewer').textContent=u.reviewer||ut('reviewer');if(u.reviewer)uBy('ue-reviewer').dataset.documentary='';else delete uBy('ue-reviewer').dataset.documentary;if(document.activeElement!==uBy('ue-name'))uBy('ue-name').value=u.reviewer;uUpdateStatus()}

function uBuild(){
 const p=u.page;if(!p)return;resultsView.replaceChildren();desk.hidden=true;
 resultsView.innerHTML=`<section class="ue-workbench" data-no-i18n>
 <div class="ue-navigation"><label class="ue-document"><span>${ut('document')}</span><select id="ue-document" aria-label="${ut('document')}"></select></label><div class="ue-page-nav"><button id="ue-prev" aria-label="${ut('previous')}">←</button><label>${ut('page')} <select id="ue-page" aria-label="${ut('page')}"></select></label><span id="ue-total"></span><button id="ue-next" aria-label="${ut('next')}">→</button></div><span id="ue-status" class="ue-badge"></span><button id="ue-doubts"></button><button id="ue-reviewer" title="${ut('identity')}"></button></div>
 <div id="ue-identity-panel" class="ue-identity"><label>${ut('reviewer')} <input id="ue-name" maxlength="120" placeholder="${ut('name')}" autocomplete="name"></label><button id="ue-start">${ut('start')}</button><small>${ut('identityHelp')}</small></div>
 <div id="ue-recovery" class="ue-recovery" hidden><span>${ut('recovery')}</span><button id="ue-restore">${ut('restore')}</button><button id="ue-discard">${ut('discard')}</button></div>
 <div id="ue-notice" role="status" class="ue-notice"></div>
 <div class="ue-panes"><div class="ue-image-panel"><div class="ue-panel-head"><strong>${ut('image')}</strong><div><button id="ue-minus" aria-label="${ut('zoomOut')}">−</button><output id="ue-zoom">100%</output><button id="ue-plus" aria-label="${ut('zoomIn')}">+</button><button id="ue-fit">${ut('fit')}</button></div></div><div id="ue-image-scroll">${p.image?`<img id="ue-image" src="/page-image?document=${p.id}&page=${p.number}" alt="${ut('image')} ${p.number}" draggable="false">`:`<p>${ut('noImage')}</p>`}</div></div>
 <div class="ue-text-panel"><div class="ue-panel-head"><strong>${ut('text')}</strong><label><input id="ue-changes" type="checkbox"> ${ut('changes')}</label><details class="ue-more"><summary aria-label="Options">⋯</summary><button id="ue-original">${ut('original')}</button><button id="ue-page-note-toggle">${ut('pageNote')}</button><a href="/download?document=${p.id}" download="maph-results.zip">${ut('download')}</a></details></div>
 <div class="ue-edit-area"><div id="ue-text" role="textbox" aria-label="${ut('text')}" aria-multiline="true" contenteditable="true" spellcheck="false"></div><div id="ue-selection" hidden><button id="ue-mark">${ut('mark')}</button><button id="ue-add-note">${ut('addNote')}</button></div></div>
 <p class="ue-hint">${ut('selectHint')}</p><div id="ue-doubt-list" class="ue-doubt-list" hidden></div>
 <div id="ue-fragment" class="ue-note-panel" hidden><div><mark id="ue-quote"></mark><button id="ue-note-close" aria-label="Close">×</button></div><label>${ut('fragment')}<textarea id="ue-fragment-note" maxlength="2000" rows="2"></textarea></label><button id="ue-resolve">${ut('resolve')}</button><button id="ue-unmark">${ut('remove')}</button></div>
 <div id="ue-page-note-panel" class="ue-note-panel" hidden><label>${ut('pageNote')}<textarea id="ue-page-note" rows="2" maxlength="10000"></textarea></label></div>
 </div></div>
 <footer class="ue-footer"><div><span id="ue-save" role="status"></span><button id="ue-retry" hidden>${ut('retry')}</button><button id="ue-reopen" hidden>${ut('reopen')}</button></div><div><button id="ue-pending">${ut('pending')}</button><button id="ue-finish" class="ue-primary">${ut('finish')} →</button></div></footer>
 </section><dialog id="ue-original-dialog"><button id="ue-original-close" aria-label="Close">×</button><h2>${ut('original')}</h2><pre id="ue-raw-original"></pre><p>${ut('originalNote')}</p><div id="ue-original-text"></div></dialog>`;
 uBy('ue-document').onchange=async e=>{const d=state.documents.find(x=>x.source===e.target.value);const page=d.pages.find(x=>['complete','needs_review','failed'].includes(x.status));if(page)await openReview(await docId(d.source),page.number);uRefreshSelectors()};
 uBy('ue-page').onchange=async e=>{await openReview(p.id,Number(e.target.value));uRefreshSelectors()};
 uBy('ue-prev').onclick=()=>uAdjacent(-1);uBy('ue-next').onclick=()=>uAdjacent(1);
 uBy('ue-reviewer').onclick=()=>{u.identityOpen=!u.identityOpen;uIdentity();if(u.identityOpen)uBy('ue-name').focus()};
 uBy('ue-start').onclick=()=>{const name=uBy('ue-name').value.trim();if(!name){uBy('ue-name').focus();return}u.reviewer=name;uStore('maph-reviewer',name);u.identityOpen=false;uIdentity();if(dirty)uSave();uBy('ue-text').focus()};
 uBy('ue-name').onkeydown=e=>{if(e.key==='Enter')uBy('ue-start').click()};
 const editor=uBy('ue-text');editor.oninput=()=>{if(!u.composing)uChangedText(editor.textContent)};editor.oncompositionstart=()=>u.composing=true;editor.oncompositionend=()=>{u.composing=false;uChangedText(editor.textContent)};
 editor.onpaste=e=>{e.preventDefault();uInsert(e.clipboardData.getData('text/plain'))};editor.ondrop=e=>e.preventDefault();
 editor.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();uInsert('\n')}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();uUndo(e.shiftKey)}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();uSave()}};
 editor.onpointerup=uSelected;editor.onkeyup=uSelected;editor.onclick=e=>{const m=e.target.closest('[data-mark]');if(m&&(!uSelection()||uSelection().start===uSelection().end))uOpenNote(Number(m.dataset.mark))};
 for(const id of ['ue-mark','ue-add-note']){uBy(id).onpointerdown=e=>e.preventDefault();uBy(id).onclick=uAddMark}
 uBy('ue-changes').checked=u.showChanges;uBy('ue-changes').onchange=e=>{u.showChanges=e.target.checked;uPaintText(true)};
 uBy('ue-doubts').onclick=()=>{uBy('ue-doubt-list').hidden=!uBy('ue-doubt-list').hidden};
 uBy('ue-note-close').onclick=()=>uBy('ue-fragment').hidden=true;
 uBy('ue-resolve').onclick=uRemoveMark;uBy('ue-unmark').onclick=uRemoveMark;
 uBy('ue-fragment-note').oninput=e=>{const m=u.page.annotations[Number(uBy('ue-fragment').dataset.index)];if(m){m.note=e.target.value;uMarkDirty()}};
 uBy('ue-page-note').value=p.note;uBy('ue-page-note').oninput=e=>{p.note=e.target.value;uMarkDirty()};
 uBy('ue-page-note-toggle').onclick=()=>{uBy('ue-page-note-panel').hidden=!uBy('ue-page-note-panel').hidden;uBy('ue-page-note').focus();resultsView.querySelector('.ue-more').open=false};
 uBy('ue-original').onclick=()=>{uDrawOriginal();uBy('ue-original-dialog').showModal();resultsView.querySelector('.ue-more').open=false};uBy('ue-original-close').onclick=()=>uBy('ue-original-dialog').close();
 uBy('ue-minus').onclick=()=>uZoom(-25);uBy('ue-plus').onclick=()=>uZoom(25);uBy('ue-fit').onclick=()=>{u.zoom=100;uZoom(0)};
 const pane=uBy('ue-image-scroll');let drag=null;pane.onpointerdown=e=>{if(u.zoom<=100)return;drag={x:e.clientX,y:e.clientY,left:pane.scrollLeft,top:pane.scrollTop};pane.setPointerCapture(e.pointerId)};pane.onpointermove=e=>{if(drag){pane.scrollLeft=drag.left+drag.x-e.clientX;pane.scrollTop=drag.top+drag.y-e.clientY}};pane.onpointerup=pane.onpointercancel=()=>drag=null;
 uBy('ue-retry').onclick=()=>uSave();uBy('ue-reopen').onclick=async()=>{uBackup();dirty=false;u.page.savedGeneration=u.page.generation;u.error=null;await openReview(p.id,p.number,true)};
 uBy('ue-pending').onclick=()=>uFinish(false);uBy('ue-finish').onclick=()=>uFinish(true);
 if(p.recovery){uBy('ue-recovery').hidden=false;uBy('ue-restore').onclick=()=>{uHistory();p.text=p.recovery.text;p.basis=p.recovery.basis||'9b';p.note=p.recovery.note||'';p.annotations=(p.recovery.annotations||[]).filter(m=>p.text.slice(m.start,m.end)===m.quote);p.recovery=null;uBy('ue-recovery').hidden=true;uBy('ue-page-note').value=p.note;uMarkDirty();uPaintText();uDrawDoubts()};uBy('ue-discard').onclick=()=>{p.recovery=null;uRemove(uk(p));uBy('ue-recovery').hidden=true}}
 uRefreshSelectors();uIdentity();uPaintText();uDrawDoubts();uZoom(0);uUpdateStatus();
}
function uRefreshSelectors(){if(!u.page||!uBy('ue-document'))return;const source=u.page.doc.source,docSelect=uBy('ue-document'),pages=uBy('ue-page');
 const docOptions=state.documents.map(d=>`<option value="${esc(d.source)}">${esc(d.source)}</option>`).join('');if(docSelect.dataset.options!==docOptions){docSelect.innerHTML=docOptions;docSelect.dataset.options=docOptions}docSelect.value=source;
 const live=state.documents.find(d=>d.source===source)||u.page.doc;const options=live.pages.map(p=>`<option value="${p.number}" ${p.status==='pending'?'disabled':''}>${p.number}</option>`).join('');if(pages.dataset.options!==options){pages.innerHTML=options;pages.dataset.options=options}pages.value=String(u.page.number);uBy('ue-total').textContent='/ '+live.page_count;
 for(const [id,n] of [['ue-prev',u.page.number-1],['ue-next',u.page.number+1]])uBy(id).disabled=u.loading||u.busy||!live.pages.some(p=>p.number===n&&p.status!=='pending');
}
function uZoom(delta){u.zoom=Math.max(50,Math.min(300,u.zoom+delta));const img=uBy('ue-image');if(img){img.style.width=u.zoom+'%';img.style.maxWidth='none'}uBy('ue-zoom').textContent=u.zoom+'%'}
async function uAdjacent(delta){if(u.page)await openReview(u.page.id,u.page.number+delta)}
async function uFinish(validate){
 if(u.busy||!u.page)return;u.busy=true;uUpdateStatus();
 const status=validate&&!u.page.annotations.length?'validated':'deferred';const saved=await uSave(status);u.busy=false;uUpdateStatus();
 if(!saved)return;u.message=ut(status==='validated'?'savedValidated':'savedPending');await uNextPage();
}
async function uNextPage(){
 if(!state||!u.page)return;const all=state.documents.flatMap(d=>d.pages.filter(p=>['complete','needs_review'].includes(p.status)).map(p=>({d,p})));const i=all.findIndex(x=>docIds.get(x.d.source)===u.page.id&&x.p.number===u.page.number);
 const next=all.slice(i+1).find(x=>quality(x.d,x.p)!=='validated');if(next)await openReview(await docId(next.d.source),next.p.number);else{u.message+=' '+ut('allDone');uUpdateStatus()}
}
function uReveal(){if(u.modalHost?.isConnected){u.modalHost.append(resultsView);resultsView.hidden=false;if(typeof sourceReviewSync==='function')sourceReviewSync()}else showView('results')}
openReview=async function(id,number,force=false){
 if(u.loading||u.busy)return false;if(u.page?.id===id&&u.page.number===number&&!force){uReveal();return true}
 u.loading=true;
 if(!await uFlush()){u.loading=false;uRefreshSelectors();return false}
 const doc=state?.documents.find(d=>docIds.get(d.source)===id);if(!doc){u.loading=false;return false}
 uRefreshSelectors();
 try{
  const r=await fetch(`/review?document=${encodeURIComponent(id)}&page=${number}&t=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw Error();const data=await r.json();
  if(!['complete','needs_review'].includes(data.metadata.status)){u.message=ut('loadError');uUpdateStatus();return false}
  const recovery=uRead('maph-draft:'+id+':'+number);
  u.page={id,number,doc,original:data.original,originalHash:data.original_hash,basis:data.review?.basis||'9b',text:data.review?.text??data.original,note:data.review?.note||'',annotations:data.review?.annotations||[],revision:data.review?.revision||0,status:data.stale?'draft':data.review?.status,updated:data.review?.updated,generation:0,savedGeneration:0,image:data.image,recovery:recovery?.original_hash===data.original_hash?recovery:null};
  dirty=false;opened={id,page:number,data};resultDoc=doc.source;resultPage=number;u.error=null;u.message=data.stale?ut('stale'):'';u.selection=null;u.history=[];u.future=[];u.zoom=100;
  uStore('maph-last-page',{id,page:number});uBuild();uReveal();return true;
 }catch{u.message=ut('loadError');if(u.page)uUpdateStatus();else resultsView.textContent=u.message;return false}
 finally{u.loading=false;uRefreshSelectors()}
};
nextReview=async function(){if(u.page){await uNextPage();return}const last=uRead('maph-last-page');await Promise.all(state.documents.map(d=>docId(d.source)));if(last&&state.documents.some(d=>docIds.get(d.source)===last.id&&d.pages.some(p=>p.number===last.page&&['complete','needs_review'].includes(p.status))))return openReview(last.id,last.page);return uFirstPage()};
async function uFirstPage(){if(!state||u.loading)return;for(const d of state.documents){const p=d.pages.find(p=>['complete','needs_review'].includes(p.status));if(p)return openReview(await docId(d.source),p.number)}resultsView.textContent=ut('noPages')}
saveReview=async status=>uSave(status);
renderResults=function(){if(u.lang!==uiLanguage&&!u.composing){u.lang=uiLanguage;if(u.page)uBuild()}uRefreshSelectors();if(activeView==='results'&&!u.page&&!u.loading)uFirstPage()};
showView=function(name){const explain=name==='technology';if(explain)name='overview';if(name==='review')name='results';activeView=name;overview.hidden=name!=='overview';reviewView.hidden=true;technology.hidden=name!=='overview';resultsView.hidden=name!=='results';desk.hidden=true;document.body.classList.toggle('ue-results-active',name==='results');drawNavigation();if(name==='results'){renderResults();if(!u.page&&!u.loading){resultsView.textContent=ut('loading');uFirstPage()}}else if(name==='overview')requestAnimationFrame(()=>render());if(explain)requestAnimationFrame(()=>technology.scrollIntoView({behavior:'smooth',block:'start'}))};
window.addEventListener('pagehide',()=>{if(dirty)uBackup()});
// Live metadata updates never rebuild the editable DOM.
const unifiedCss=document.createElement('link');unifiedCss.rel='stylesheet';unifiedCss.href='/unified-editor.css?v='+Date.now();document.head.append(unifiedCss);
const unifiedRender=render;render=function(){unifiedRender();if(activeView==='results')renderResults()};

// Folder explorer shares the editor's guarded navigation and autosave queue.
const libraryExplorer={folder:'',query:''};
function libraryWords(key){return ({es:{browse:'Explorar archivos',title:'Explorador de transcripciones',root:'Todas las fuentes',search:'Buscar carpeta o documento…',folders:'Carpetas',files:'Documentos',close:'Cerrar',up:'Subir carpeta',empty:'No hay documentos en esta carpeta.',open:'Abrir transcripción',pages:'páginas',ready:'transcritas',current:'Abierto',pending:'Pendiente de transcripción'},en:{browse:'Browse files',title:'Transcript explorer',root:'All sources',search:'Find folder or document…',folders:'Folders',files:'Documents',close:'Close',up:'Parent folder',empty:'No documents in this folder.',open:'Open transcript',pages:'pages',ready:'transcribed',current:'Open',pending:'Awaiting transcription'},fr:{browse:'Parcourir les fichiers',title:'Explorateur de transcriptions',root:'Toutes les sources',search:'Rechercher un dossier ou document…',folders:'Dossiers',files:'Documents',close:'Fermer',up:'Dossier parent',empty:'Aucun document dans ce dossier.',open:'Ouvrir la transcription',pages:'pages',ready:'transcrites',current:'Ouvert',pending:'En attente de transcription'}})[uiLanguage][key]}
function libraryReviewPages(doc){
 return doc.pages.filter(page=>typeof queueRecord==='function'?queueRecord(doc,page).priority<4:page.status==='needs_review'||page.status==='failed'||page.flags?.length);
}
function libraryReviewLabel(count){return ({es:'Revisión sugerida · '+count+' páginas',en:'Review suggested · '+count+' pages',fr:'Révision suggérée · '+count+' pages'})[uiLanguage]}
function libraryExplorerOpen(){
 const dialog=document.createElement('dialog');dialog.className='library-explorer';dialog.dataset.noI18n='';
 const element=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el},button=(text,action)=>{const b=element('button',text);b.type='button';b.onclick=action;return b};
 const docs=state?.documents||[],reviewPages=new Map(docs.map(d=>[d.source,libraryReviewPages(d)])),path=d=>d.source.split('/').slice(0,-1).join('/'),folders=new Set(['']);for(const d of docs){const parts=path(d).split('/').filter(Boolean);for(let i=1;i<=parts.length;i++)folders.add(parts.slice(0,i).join('/'))}
 libraryExplorer.folder=u.page?path(u.page.doc):libraryExplorer.folder;
 const header=element('header');header.append(element('h2',libraryWords('title')),button(libraryWords('close'),()=>dialog.close()));const search=element('input');search.type='search';search.placeholder=libraryWords('search');search.setAttribute('aria-label',libraryWords('search'));search.value=libraryExplorer.query;
 const body=element('div');body.className='library-explorer-body';const tree=element('nav');tree.setAttribute('aria-label',libraryWords('folders'));const content=element('div');content.className='library-explorer-content';body.append(tree,content);dialog.append(header,search,body);
 function navigate(folder){libraryExplorer.folder=folder;libraryExplorer.query='';search.value='';paint()}
 function paint(){tree.replaceChildren();content.replaceChildren();const selected=libraryExplorer.folder,q=libraryExplorer.query.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase(),matches=value=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(q);
  for(const folder of [...folders].sort()){const count=docs.filter(d=>!folder||path(d)===folder||path(d).startsWith(folder+'/')).length;const b=button((folder?'▸ '+folder.split('/').pop():libraryWords('root'))+'  ('+count+')',()=>navigate(folder));b.style.paddingLeft=(12+Math.max(0,folder.split('/').length-1)*16)+'px';b.setAttribute('aria-current',String(folder===selected));b.title=folder||libraryWords('root');const flagged=docs.filter(d=>(!folder||path(d)===folder||path(d).startsWith(folder+'/'))&&reviewPages.get(d.source).length).length;if(flagged){const badge=element('small',' ⚑ '+flagged);badge.className='library-review-badge';badge.title=({es:'Documentos con revisión sugerida',en:'Documents with suggested review',fr:'Documents avec révision suggérée'})[uiLanguage];b.append(badge)}tree.append(b)}
  const crumbs=element('nav');crumbs.className='library-breadcrumbs';crumbs.setAttribute('aria-label',libraryWords('folders'));crumbs.append(button(libraryWords('root'),()=>navigate('')));const parts=selected.split('/').filter(Boolean);parts.forEach((part,i)=>crumbs.append(element('span','/'),button(part,()=>navigate(parts.slice(0,i+1).join('/')))));content.append(crumbs);
  if(selected)content.append(button('↑ '+libraryWords('up'),()=>navigate(parts.slice(0,-1).join('/'))));
  if(!q){const children=[...folders].filter(f=>f&&f.split('/').slice(0,-1).join('/')===selected);for(const f of children){const row=button('▸ '+f.split('/').pop(),()=>navigate(f));row.className='library-folder-row';content.append(row)}}
  const visible=docs.filter(d=>q?matches(d.source):path(d)===selected);const label=element('p',libraryWords('files')+' · '+visible.length);content.append(label);if(!visible.length)content.append(element('p',libraryWords('empty')));
  for(const d of visible){const row=element('div');row.className='library-file-row';const info=element('div');info.append(element('strong',d.source.split('/').pop()),element('small',path(d)||libraryWords('root')));const processed=d.pages.filter(p=>['complete','needs_review','failed'].includes(p.status)),read=d.pages.filter(p=>['complete','needs_review'].includes(p.status)).length;info.append(element('small',read+' / '+(d.page_count||d.pages.length)+' '+libraryWords('pages')+' '+libraryWords('ready')));const flagged=reviewPages.get(d.source);if(flagged.length){const badge=element('span','⚑ '+libraryReviewLabel(flagged.length));badge.className='library-review-badge';info.append(badge)}const open=button(d.source===u.page?.doc.source?'✓ '+libraryWords('current'):libraryWords('open'),async()=>{open.disabled=true;try{const page=d.source===u.page?.doc.source?u.page.number:processed[0]?.number;if(page&&await openReview(await docId(d.source),page)!==false)dialog.close()}finally{open.disabled=false}});open.disabled=!processed.length;if(!processed.length)open.textContent=libraryWords('pending');const actions=element('div');actions.className='library-file-actions';actions.append(open);if(flagged.length){const review=button(({es:'Revisar primera alerta',en:'Review first alert',fr:'Examiner la première alerte'})[uiLanguage],async()=>{review.disabled=true;try{if(await openReview(await docId(d.source),flagged[0].number)!==false)dialog.close()}finally{review.disabled=false}});actions.append(review)}row.append(info,actions);content.append(row)}
 }
 search.oninput=()=>{libraryExplorer.query=search.value;paint()};dialog.onclose=()=>dialog.remove();document.body.append(dialog);paint();dialog.showModal();search.focus();
}
function libraryExplorerInstall(){const select=uBy('ue-document');if(!select||document.getElementById('library-browse'))return;const b=document.createElement('button');b.id='library-browse';b.type='button';b.textContent='▸ '+libraryWords('browse');b.onclick=libraryExplorerOpen;select.closest('label').before(b);select.closest('label').classList.add('library-legacy-document');select.closest('label').title=u.page?.doc.source||'';}
const libraryRefresh=uRefreshSelectors;uRefreshSelectors=function(){libraryRefresh();libraryExplorerInstall();const b=document.getElementById('library-browse');if(b)b.textContent='▸ '+libraryWords('browse')};
const libraryStyle=document.createElement('style');libraryStyle.textContent=`.library-explorer{width:1000px;max-width:calc(100vw - 40px);height:75vh;max-height:850px;box-sizing:border-box;border:1px solid var(--line);border-radius:12px;background:var(--paper);padding:22px;color:var(--ink)}.library-explorer::backdrop{background:#1118}.library-explorer header{padding:0 0 16px;margin:0;display:flex;justify-content:space-between}.library-explorer h2{margin:0;font-size:22px}.library-explorer>input{width:100%;box-sizing:border-box;margin:12px 0}.library-explorer-body{display:grid;grid-template-columns:230px 1fr;gap:20px;height:calc(100% - 120px);min-height:0}.library-explorer-body>nav,.library-explorer-content{overflow:auto}.library-explorer-body>nav{border-right:1px solid var(--line);padding-right:12px}.library-explorer-body>nav button{display:block;width:100%;text-align:left;border:0;margin:4px 0;background:transparent;overflow-wrap:anywhere}.library-explorer-body>nav button[aria-current=true]{background:#e1eae1;font-weight:600}.library-breadcrumbs{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin-bottom:14px}.library-breadcrumbs button{border:0;background:transparent;padding:5px;font-size:12px}.library-file-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 8px;border-bottom:1px solid var(--line)}.library-file-row strong,.library-file-row small{display:block;overflow-wrap:anywhere}.library-file-row small{font-size:11px;margin-top:5px}.library-file-row button{font-size:12px;flex-shrink:0}.library-folder-row{display:block;width:100%;text-align:left;margin:5px 0;background:#eeede7}.library-legacy-document{min-width:150px!important}#library-browse{white-space:nowrap}@media(max-width:650px){.library-explorer{padding:14px;max-width:calc(100vw - 16px);height:85vh}.library-explorer-body{grid-template-columns:145px 1fr;gap:10px}.library-file-row{align-items:start;flex-direction:column}.library-explorer h2{font-size:18px}}`;document.head.append(libraryStyle);libraryExplorerInstall();

const libraryBadgeStyle=document.createElement('style');libraryBadgeStyle.textContent='.library-review-badge{display:inline-block;background:#fff0cd;color:#805400;border:1px solid #ebce8c;border-radius:12px;padding:4px 8px;font-size:11px;margin-top:7px}.library-file-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end;max-width:230px}.library-explorer-body>nav .library-review-badge{font-size:10px;padding:2px 6px}';document.head.append(libraryBadgeStyle);
