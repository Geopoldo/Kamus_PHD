// Reuse the library workbench in source dialogs; one editor and one autosave queue.
const sourceReviewAnchor=document.createComment('transcription-library-position');resultsView.before(sourceReviewAnchor);
let sourceReviewContext=null,sourceReviewClosing=false;
function sourceReviewRanges(page){
 const context=sourceReviewContext;if(!context||context.id!==page.id||context.page!==page.number)return [];
 const ranges=[];
 for(const item of context.highlights){if(!item.text.trim())continue;const escaped=item.text.trim().split(/\s+/).map(word=>word.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('\\s+');const pattern=new RegExp(escaped,'gu');let match;while((match=pattern.exec(page.text)))ranges.push({start:match.index,end:match.index+match[0].length,kind:item.kind})}
 return ranges;
}
function sourceReviewSync(){
 if(!sourceReviewContext||!u.page)return;
 const title=sourcePopup.querySelector(':scope > header h2');if(title)gSet(title,gMsg`${u.page.doc.source}${gMsg(' · página ')}${u.page.number}`);
 const notice=sourcePopup.querySelector('.source-review-notice');if(!notice)return;
 const same=u.page.id===sourceReviewContext.id&&u.page.number===sourceReviewContext.page;
 const message=same?gMsg('Editor del Banco de transcripciones: corrige la lectura vigente, identifica al revisor y guarda automáticamente un borrador. Los resaltados indican términos del resultado que todavía aparecen en esta lectura.'):gMsg('Estás revisando otra página con el mismo editor. La evidencia del resultado inicial se conserva en el apartado inferior.');
 const snapshotNotice=sourceReviewContext.graph?gMsg(' Knowledge Graph conserva la copia del piloto: las correcciones no reconstruyen automáticamente su grafo ni sus respuestas.'):sourceReviewContext.snapshot?gMsg(' La copia usada en la selección o la Matriz IA se conserva abajo. Las correcciones se guardan en la lectura vigente; no modifican esa copia ni las respuestas anteriores. Para analizar el texto corregido, selecciónalo y ejecuta nuevas preguntas.'):'';
 gSet(notice,gMsg`${message}${snapshotNotice}`);
}
function sourceReviewRelease(){
 const context=sourceReviewContext;if(!context)return;
 const changed=context.changed;
 u.modalHost=null;sourceReviewContext=null;sourceReviewAnchor.after(resultsView);resultsView.hidden=activeView!=='results';delete sourcePopup.dataset.unified;
 if(u.page)uPaintText();
 if(changed)priorityLoad(); // Simple search already refreshes through its existing save hook.
}
async function sourceReviewPrepare(){
 if(u.loading||u.busy)return false;
 if(!await uFlush()){if(!sourceReviewContext)showView('results');uBy('ue-name')?.focus();return false}
 sourceReviewRelease();return true;
}
async function sourceReviewMount(id,page,label,graph=false,snapshot=false){
 if(!sourcePopup.open||!sourcePopup.querySelector('.source-popup-transcription'))return;
 await Promise.all((state?.documents||[]).map(d=>docId(d.source)));
 if(!sourcePopup.open)return;
 const source=state?.documents.find(d=>docIds.get(d.source)===id);if(!source){sourcePopup.append(gse('p',gMsg('La fuente ya no está en el inventario disponible para corregir.')));return}
 const header=sourcePopup.querySelector(':scope > header'),evidence=gse('details');evidence.className='source-review-evidence';evidence.append(gse('summary',gMsg`${label} · evidencia guardada de ${source.source}, página ${page}`));
 const highlights=[...new Map([...sourcePopup.querySelectorAll('.source-popup-transcription mark')].map(mark=>[mark.textContent+'::'+(mark.dataset.entityKind||''),{text:mark.textContent,kind:mark.dataset.entityKind||''}])).values()];
 for(const child of [...sourcePopup.children])if(child!==header)evidence.append(child);
 const notice=gse('p');notice.className='source-review-notice';gAttr(notice,'role','status');const host=gse('div');host.className='source-unified-host';sourcePopup.append(notice,host,evidence);sourcePopup.dataset.unified='true';
 sourceReviewContext={id,page,label,graph,snapshot,highlights,startRevision:null,changed:false};u.modalHost=host;
 const ok=await openReview(id,page);if(!ok){gSet(notice,gMsg('No se pudo abrir el editor. La evidencia guardada sigue disponible abajo.'));return}
 sourceReviewContext.startRevision=u.page.revision;uPaintText();sourceReviewSync();
 evidence.addEventListener('change',()=>{if(!sourceReviewContext)return;sourceReviewContext.highlights=[...evidence.querySelectorAll('.source-popup-transcription mark')].map(mark=>({text:mark.textContent,kind:mark.dataset.entityKind||''}));uPaintText()});
}
const sourceReviewSave=uSave;uSave=async function(...args){const before=u.page?.revision,ok=await sourceReviewSave(...args);if(ok&&sourceReviewContext&&u.page?.revision!==before){sourceReviewContext.changed=true;sourceReviewSync()}return ok};
const sourceNativeClose=sourcePopup.close.bind(sourcePopup);
sourcePopup.close=async function(){
 if(sourceReviewClosing)return;
 if(u.modalHost&&(u.loading||u.busy)){const notice=sourcePopup.querySelector('.source-review-notice');if(notice)gSet(notice,gMsg('Espera a que termine de abrir o guardar la página.'));return}
 sourceReviewClosing=true;
 try{if(u.modalHost&&!await uFlush()){uBy('ue-name')?.focus();return}sourceReviewRelease();sourceNativeClose()}finally{sourceReviewClosing=false}
};
sourcePopup.addEventListener('cancel',event=>{if(u.modalHost){event.preventDefault();sourcePopup.close()}});
sourcePopup.addEventListener('close',sourceReviewRelease);
const sourceReadSearch=openSearchSource;openSearchSource=async function(source,page,version){
 if(!await sourceReviewPrepare())return false;
 const hit=searchData?.hits.find(h=>h.document===source&&h.page===page),ok=await sourceReadSearch(source,page,version);
 if(ok&&hit&&sourcePopup.open&&sourcePopup.querySelector('.source-popup-transcription')){
  const edit=searchButton(searchText('Corregir transcripción…','Correct transcription…','Corriger la transcription…'),async()=>{edit.disabled=true;await sourceReviewMount(hit.document_id,page,gMsg('Búsqueda sencilla'))});edit.className='simple-edit-source';sourcePopup.querySelector('.source-popup-tools').append(edit);
 }return ok;
};
const sourceReadPriority=prioritySource;prioritySource=async function(page){if(!page||!await sourceReviewPrepare())return;sourceReadPriority(page);await sourceReviewMount(page.document_id,page.page,gMsg('Análisis cruzado'))};
const sourceReadGraph=graphPilotSource;graphPilotSource=async function(edge){if(!await sourceReviewPrepare())return;await sourceReadGraph(edge);await sourceReviewMount(edge.page.document_id,edge.page.page,'Knowledge Graph',true)};
// Matrix cells, their quotes and saved selections share the same guarded editor.
// Keep the frozen row intact: only the current library reading may be edited.
const sourceReadMatrix=matrixSource;matrixSource=async function(row,quote='',label=gMsg('Matriz IA')){
 if(!await sourceReviewPrepare())return false;
 sourceReadMatrix(row,quote);
 await sourceReviewMount(row.document_id,row.page,gMsg`${label} · ${row.version}`,false,true);
 return true;
};
const sourceReviewCSS=gse('style');gSet(sourceReviewCSS,'#search-source-popup[data-unified]{width:calc(100vw - 40px);max-width:1800px;height:calc(100dvh - 40px);max-height:none;padding:16px;box-sizing:border-box;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto}#search-source-popup[data-unified]>header{padding:0 0 12px}#search-source-popup[data-unified]>header h2{font-size:17px}.source-review-notice{font-size:12px;line-height:1.7;padding:10px 14px;background:#edf3ef;border-left:3px solid #21786a;max-height:16vh;overflow:auto}.source-unified-host{min-height:0;overflow:auto}.source-unified-host #view-results{height:100%;min-height:360px;max-width:none;margin:0;padding:0}.source-unified-host .ue-workbench{display:flex;flex-direction:column}.source-unified-host .ue-workbench>div,.source-unified-host .ue-footer{flex-shrink:0}.source-unified-host .ue-panes{flex:1;min-height:120px}.source-unified-host [hidden]{display:none!important}.source-review-evidence{margin:0;border-top:1px solid var(--line);padding-top:10px;max-height:35vh;overflow:auto}.source-review-evidence>summary{cursor:pointer;font-size:12px;font-weight:600}.ue-source-hit{background:#ffe2a8}.ue-source-hit[data-source-kind=person]{background:#d8e8ff}.ue-source-hit[data-source-kind=surname]{background:#ffe2a8}.ue-source-hit[data-source-kind=place]{background:#d8ecd6}.ue-source-hit.ue-uncertain{border-bottom:2px dotted #b37d0f}.ue-source-hit.ue-added{box-shadow:inset 0 2px #388b50}@media(max-width:560px){#search-source-popup[data-unified]{width:calc(100vw - 12px);height:calc(100dvh - 12px);padding:8px}.source-unified-host #view-results{height:auto;min-height:0}}');document.head.append(sourceReviewCSS);
