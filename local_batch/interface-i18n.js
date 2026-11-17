/* Local, deterministic UI localization. Never sends content to a translation service.
 * Catalog templates own their words; interpolation values remain byte-for-byte intact.
 * Updating text nodes (not innerHTML or forms) preserves input, selection and handlers.
 */
const interfaceOptIn='#search-source-popup,#view-results,#view-sources,#view-selection,#view-priorities,#view-criteria,#process-method,#process-study,#embedding-panel,.research-guide,.sources-confirm,.ue-workbench,.matrix-select-label,.matrix-selection-bar';
const interfaceProtected='script,style,textarea,pre,code,blockquote,.prompt-box,[data-documentary],#ue-text,#ue-original-text,#ue-raw-original,#ue-original-content,#ue-quote,#ue-doubt-list,#ue-document option,.source-popup-transcription,.matrix-evidence,#view-graphrag,.graph-pilot,.graph-live,[data-graph-l10n]';
const interfaceRecords=new WeakMap(),interfaceAttrRecords=new WeakMap();
const interfaceWords={...MAPH_TRANSLATIONS,...GRAPH_MESSAGES,...INTERFACE_MESSAGES};
// Reuse the hand-authored dictionaries already present in the editor and search UI.
if(typeof UE_WORDS!=='undefined')for(const [es,en,fr]of Object.values(UE_WORDS))interfaceWords[es]={en,fr};
for(const dictionary of [typeof searchLabels==='undefined'?null:searchLabels,typeof queueWords==='undefined'?null:queueWords,typeof studyText==='undefined'?null:studyText]){
 if(!dictionary)continue;for(const [key,es]of Object.entries(dictionary.es))if(dictionary.en[key]&&dictionary.fr[key])interfaceWords[es]={en:dictionary.en[key],fr:dictionary.fr[key]};
}
const interfaceExact=new Map(),interfacePatterns=[];
const interfaceNormalize=text=>String(text).replace(/\s+/g,' ').trim();
const interfaceEscape=text=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
// Some older dictionaries also exposed their English/French values as source keys.
// Prefer the Spanish entry, so a newly rendered French label can return to Spanish.
const interfaceAliases=new Set(Object.entries(interfaceWords).flatMap(([source,values])=>[values.en,values.fr].filter(value=>value&&value!==source&&Object.hasOwn(interfaceWords,value))));
for(const [source,translations] of Object.entries(interfaceWords)){
 if(interfaceAliases.has(source))continue;
 const variants={es:source,...translations};
 for(const [language,text] of Object.entries(variants)){
  if(!text)continue;const key=interfaceNormalize(text);
  if(!/\{\d+\}/.test(key)){if(!interfaceExact.has(key)||language==='es')interfaceExact.set(key,variants);continue}
  const parts=key.split(/(\{\d+\})/),slots=parts.filter(p=>/^\{\d+\}$/.test(p));
  const literalLength=parts.filter(p=>!/^\{\d+\}$/.test(p)).join('').length;
  if(literalLength<8||slots.length>15)continue;
  const regex=new RegExp('^'+parts.map(p=>/^\{\d+\}$/.test(p)?'([\\s\\S]*?)':interfaceEscape(p).replace(/\s+/g,'\\s+')).join('')+'$');
  interfacePatterns.push({regex,slots,variants,literalLength,language});
 }
}
interfacePatterns.sort((a,b)=>b.literalLength-a.literalLength);
function interfaceText(source,language=uiLanguage){
 const key=interfaceNormalize(source);if(!key)return source;
 let value=interfaceExact.get(key)?.[language];
 if(value===undefined){for(const entry of interfacePatterns){const match=entry.regex.exec(source.trim());if(!match)continue;
  const captures={};let valid=true;entry.slots.forEach((slot,i)=>{if(slot in captures&&captures[slot]!==match[i+1])valid=false;captures[slot]=match[i+1]});if(!valid)continue;
  value=(entry.variants[language]||entry.variants.es).replace(/\{\d+\}/g,slot=>captures[slot]??slot);break;
 }}
 if(value===undefined){
  // Named filters keep their data value verbatim while translating the UI prefix.
  const labeled=source.trim().match(/^([^:]+): (.+)$/);
  const label=labeled&&interfaceExact.get(interfaceNormalize(labeled[1]));
  if(label)value=(label[language]||label.es)+': '+labeled[2];
 }
 if(value===undefined){
  // Decorative arrows/icons belong to controls, not their message keys.
  const decorated=key.match(/^([←→↗↓↑✓⚑▷⛶✕+−]\s+)?(.+?)(\s+[←→↗↓↑])?$/);
  const words=decorated&&interfaceExact.get(decorated[2]);
  if(words&&(decorated[1]||decorated[3]))value=(decorated[1]||'')+(words[language]||words.es)+(decorated[3]||'');
 }
 if(value===undefined)return source;
 const leading=source.match(/^\s*/)[0],trailing=source.match(/\s*$/)[0];return leading+value+trailing;
}
function interfaceAllowed(element){
 if(!element||element.closest(interfaceProtected))return false;
 // Older views protected their entire container. Only these known UI roots opt in;
 // nested source-data exclusions still take precedence.
 const boundary=element.closest('[data-no-i18n]');return !boundary||boundary.matches(interfaceOptIn);
}
function interfaceLocalize(root=document.body){
 if(!root)return;
 document.documentElement.lang=uiLanguage;
 document.title=({es:'MAP-H · Laboratorio documental',en:'MAP-H · Document Lab',fr:'MAP-H · Laboratoire documentaire'})[uiLanguage];
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
 while(node=walker.nextNode()){
  if(!interfaceAllowed(node.parentElement))continue;
  let record=interfaceRecords.get(node);if(!record||node.nodeValue!==record.last)record={source:node.nodeValue};
  const text=interfaceText(record.source);if(node.parentElement.tagName==='OPTION'&&!node.parentElement.hasAttribute('value'))node.parentElement.value=node.parentElement.textContent;if(node.nodeValue!==text)node.nodeValue=text;record.last=text;interfaceRecords.set(node,record);
 }
 for(const element of root.querySelectorAll('[placeholder],[aria-label],[title],[alt]')){
  // Textareas retain their value, while their UI placeholder/label may change.
  const permitted=element.matches('textarea')?interfaceAllowed(element.parentElement):interfaceAllowed(element);
  if(!permitted||element.hasAttribute('data-graph-l10n')||element.hasAttribute('data-documentary'))continue;
  let records=interfaceAttrRecords.get(element)||{};
  for(const attribute of ['placeholder','aria-label','title','alt']){if(!element.hasAttribute(attribute))continue;
   const current=element.getAttribute(attribute);let record=records[attribute];if(!record||current!==record.last)record={source:current};
   const text=interfaceText(record.source);if(text!==current)element.setAttribute(attribute,text);record.last=text;records[attribute]=record;
  }interfaceAttrRecords.set(element,records);
 }
}
let interfaceScheduled=false;
function interfaceSchedule(){if(interfaceScheduled)return;interfaceScheduled=true;requestAnimationFrame(()=>{interfaceScheduled=false;interfaceObserver.disconnect();try{interfaceLocalize()}finally{interfaceObserve()}})}
const interfaceObserver=new MutationObserver(interfaceSchedule);
function interfaceObserve(){interfaceObserver.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['placeholder','aria-label','title','alt']})}
const interfacePreviousLanguage=setLanguage;
setLanguage=function(language){if(!['es','en','fr'].includes(language))return;if(typeof u!=='undefined')u.lang=language;interfacePreviousLanguage(language);interfaceLocalize()};
interfaceLocalize();interfaceObserve();
