// Draft recovery stays in this browser tab; durable saves use the local review API.
const comfortWords={es:['Nota o duda de lectura','Dejar pendiente','Ver cambios','Borrador recuperable en esta pestaña','Recuperar borrador','Descartar borrador local','Guardado en el equipo','Cambios sin guardar','No quedan páginas por revisar','Revisión guardada · continuar','Continuar desde mi última página','Se encontró un borrador sin guardar.','Texto añadido','Texto retirado'],en:['Reading note or question','Leave pending','Show changes','Recoverable draft in this tab','Restore draft','Discard local draft','Saved on this computer','Unsaved changes','No pages left to review','Review saved · continue','Resume my last page','An unsaved draft was found.','Added text','Removed text'],fr:['Note ou doute de lecture','Laisser en attente','Voir les modifications','Brouillon récupérable dans cet onglet','Restaurer le brouillon','Ignorer le brouillon local','Enregistré sur cet ordinateur','Modifications non enregistrées','Aucune page à réviser','Révision enregistrée · continuer','Reprendre ma dernière page','Un brouillon non enregistré a été trouvé.','Texte ajouté','Texte retiré']};
const cw=i=>comfortWords[uiLanguage][i];
function draftKey(id,page){return 'maph-draft:'+id+':'+page}
function storeSession(key,value){try{sessionStorage.setItem(key,JSON.stringify(value));return true}catch{return false}}
function readSession(key){try{return JSON.parse(sessionStorage.getItem(key)||'null')}catch{return null}}
function clearSession(key){try{sessionStorage.removeItem(key)}catch{}}
const comfortableOpen=openReview;openReview=async function(id,page){
 await comfortableOpen(id,page);if(!opened||opened.id!==id||opened.page!==page||!desk.querySelector('#review-text')||desk.querySelector('#review-note'))return;
 storeSession('maph-last-page',{id,page});
 const key=draftKey(id,page),text=$('review-text'),name=$('review-name'),data=opened.data;
 const notes=document.createElement('label');notes.textContent=cw(0);const note=document.createElement('textarea');note.id='review-note';note.rows=2;note.value=data.review?.note||'';notes.append(note);text.parentElement.insertBefore(notes,text.parentElement.querySelector('p'));
 const status=document.createElement('p');status.className='save-state';status.setAttribute('role','status');status.textContent=data.review?cw(6):({es:'Sin revisar',en:'Not reviewed',fr:'Non révisée'})[uiLanguage];text.before(status);
 const diff=document.createElement('details');diff.className='review-diff';const sum=document.createElement('summary');sum.textContent=cw(2);const diffBody=document.createElement('div');diff.append(sum,diffBody);text.after(diff);
 function updateDiff(){const a=data.original,b=text.value;let start=0;while(start<a.length&&start<b.length&&a[start]===b[start])start++;let end=0;while(end<a.length-start&&end<b.length-start&&a[a.length-1-end]===b[b.length-1-end])end++;diffBody.replaceChildren();if(a===b){diffBody.textContent=b;return}diffBody.append(document.createTextNode(b.slice(0,start)));const del=document.createElement('del');del.textContent=a.slice(start,a.length-end);const ins=document.createElement('ins');ins.textContent=b.slice(start,b.length-end);diffBody.append(del,ins,document.createTextNode(end?b.slice(-end):''))}
 function recoverable(){dirty=true;const ok=storeSession(key,{text:text.value,reviewer:name.value,note:note.value,annotations:typeof getReviewAnnotations==='function'?getReviewAnnotations():[],original_hash:data.original_hash,revision:data.review?.revision||0});status.textContent=cw(ok?3:7);$('review-confirm').checked=false;updateDiff()}
 for(const field of [text,name,note])field.addEventListener('input',recoverable);
 const cached=readSession(key);
 if(cached&&cached.original_hash===data.original_hash&&cached.revision===(data.review?.revision||0)){
  const banner=document.createElement('div');banner.className='draft-banner';banner.textContent=cw(11)+' ';
  const restore=document.createElement('button');restore.textContent=cw(4);restore.onclick=()=>{text.value=cached.text;name.value=cached.reviewer;note.value=cached.note||'';recoverable();banner.remove()};
  const discard=document.createElement('button');discard.textContent=cw(5);discard.onclick=()=>{clearSession(key);banner.remove()};banner.append(restore,discard);status.before(banner);
 }
 const pending=document.createElement('button');pending.textContent=cw(1);pending.onclick=()=>{note.focus();saveReview('draft')};$('review-draft').after(pending);updateDiff();
};
const comfortableSave=saveReview;saveReview=async function(status){const current=opened;if(!current)return;await comfortableSave(status);if(opened===current&&!dirty&&current.data.review?.status===status){clearSession(draftKey(current.id,current.page));desk.querySelector('.save-state').textContent=cw(6);if(status==='validated')desk.querySelector('.save-state').textContent=cw(9)}};
const continueReview=nextReview;nextReview=async function(){
 const last=readSession('maph-last-page');if(!opened&&last&&state?.documents.some(d=>docIds.get(d.source)===last.id&&d.pages.some(p=>p.number===last.page&&['complete','needs_review'].includes(p.status)))){await openReview(last.id,last.page);return}
 const available=state?.documents.some(d=>d.pages.some(p=>['complete','needs_review'].includes(p.status)&&quality(d,p)!=='validated'));
 if(!available){const msg=document.createElement('p');msg.setAttribute('role','status');msg.textContent=cw(8);invitation.append(msg);return}await continueReview();
};
const comfortCSS=document.createElement('style');comfortCSS.textContent=`#review-note{height:80px;min-height:65px;font:14px/1.6 Manrope,sans-serif}.save-state{font-size:12px;color:#626368}.review-diff{margin:12px 0;border:1px solid var(--line);padding:12px}.review-diff>div{white-space:pre-wrap;max-height:220px;overflow:auto;font:14px/1.7 monospace}.review-diff del{background:#ffe0dc;color:#76251c}.review-diff ins{background:#d7efde;color:#16542d;text-decoration:none}.draft-banner{padding:14px;background:#fff0d5;border-left:3px solid #b9821b;margin:12px 0}.draft-banner button{margin:5px}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #bd350d;outline-offset:3px}.inline-desk .review-actions{gap:10px}.inline-desk label{line-height:1.8}`;document.head.append(comfortCSS);
