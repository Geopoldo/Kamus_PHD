const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const sandbox={localStorage:{getItem:()=>null},console,uiLanguage:'es',document:{createTextNode:text=>({nodeValue:text,isConnected:true})},se:()=>new Element(),priorityButton:()=>new Element()};
class Element{
 constructor(){this.children=[];this.dataset={};this.attributes={};this.isConnected=true}
 replaceChildren(...children){this.children=children}
 setAttribute(key,value){this.attributes[key]=String(value)}
 set textContent(value){this.children=[{nodeValue:String(value)}]}
 get textContent(){return this.children.map(c=>c.nodeValue??c.textContent??'').join('')}
}
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(__dirname+'/graphrag-i18n.js','utf8'),sandbox);
const element=new Element(),input={value:'Pending draft',checked:true,nodeValue:''};sandbox.element=element;sandbox.input=input;
vm.runInContext("gSet(element,gMsg('Cerrar'));element.children.push(input)",sandbox);
for(const [lang,label]of [['en','Close'],['fr','Fermer'],['es','Cerrar']]){sandbox.uiLanguage=lang;vm.runInContext('graphApplyLanguage()',sandbox);assert.equal(element.children[0].nodeValue,label);assert.equal(element.children[1],input);assert.equal(input.value,'Pending draft');assert.equal(input.checked,true)}
vm.runInContext("gSet(element,'Lugar')",sandbox);sandbox.uiLanguage='en';vm.runInContext('graphApplyLanguage()',sandbox);assert.equal(element.textContent,'Lugar','Raw source text never becomes a message');
vm.runInContext("gSet(element,gMsg`${'<script>synthetic</script>'} · página ${3}`)",sandbox);assert.equal(element.textContent,'<script>synthetic</script> · page 3','Interpolations stay inert text');
// Exercise deterministic template matching separately from the observer/DOM adapter.
vm.runInContext(fs.readFileSync(__dirname+'/i18n.js','utf8'),sandbox);
vm.runInContext(fs.readFileSync(__dirname+'/interface-catalog.js','utf8'),sandbox);
const source=fs.readFileSync(__dirname+'/interface-i18n.js','utf8');vm.runInContext(source.slice(0,source.indexOf('function interfaceAllowed')),sandbox);
vm.runInContext(`for(const [key,translations] of Object.entries({...GRAPH_MESSAGES,...INTERFACE_MESSAGES})){for(const lang of ['en','fr']){if(!translations[lang])throw Error('Missing locale '+key);const a=(key.match(/\\{\\d+\\}/g)||[]).sort().join();const b=(translations[lang].match(/\\{\\d+\\}/g)||[]).sort().join();if(a!==b)throw Error('Placeholder mismatch '+key)}}`,sandbox);
assert.equal(vm.runInContext("interfaceText('Fuentes','en')",sandbox),'Sources');
assert.equal(vm.runInContext("interfaceText('Cerrar','fr')",sandbox),'Fermer');
assert.equal(vm.runInContext("interfaceText('Unknown manuscript text','fr')",sandbox),'Unknown manuscript text');
assert.equal(vm.runInContext("interfaceText('Nombre  X páginas de origen','en')",sandbox),'Nombre  X source pages','Template values retain spaces');
assert.equal(vm.runInContext("interfaceText('Ver telemetría ↓','en')",sandbox),'View telemetry ↓','Decorated controls translate');
console.log('All catalog locales/placeholders, live GraphRAG language switches, preserved drafts, and inert source text passed.');
