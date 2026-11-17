const assert=require('node:assert/strict');
const {overview,zoomAt,labelIds}=require('./graphrag-result-core.js');
const nodes=Array.from({length:38},(_,i)=>({id:String(i),label:'Synthetic '+i,type:'PERSON'}));
const relationships=Array.from({length:35},(_,i)=>({source:'0',target:String(i+1)}));
relationships.push({source:'0',target:'1'},{source:'1',target:'0'},{source:'2',target:'2'});
const graph={nodes,relationships},result=overview(graph);
assert.equal(result.nodes.length,38,'No twelve-neighbor limit, including isolated nodes');
assert.equal(result.links.reduce((n,e)=>n+e.edges.length,0),relationships.length,'Preserve every assertion');
assert.equal(result.links.length,37,'Group duplicate directed links without merging opposite directions');
assert.equal(result.components,3);
for(const n of result.nodes){assert.ok(Number.isFinite(n.x)&&Number.isFinite(n.y));assert.ok(n.x>=0&&n.x<=result.width&&n.y>=0&&n.y<=result.height)}
assert.deepEqual(overview(graph),result,'Stable layout when reopening a saved question');
assert.equal(overview({nodes:[],relationships:[]}).nodes.length,0);
const compact=overview(graph,{compact:true});assert.equal(compact.nodes.length,nodes.length);assert.equal(compact.links.reduce((sum,link)=>sum+link.edges.length,0),relationships.length);assert.ok(compact.isolatedRegion.count===2);for(const n of compact.nodes)assert.ok(n.x>=0&&n.x<=compact.width&&n.y>=0&&n.y<=compact.height,'Full-pilot nodes remain in the frame');

assert.equal(zoomAt({x:0,y:0,w:1200,h:560},.7).w,840,'Graph zoom must not use the geographic 360-degree limit');
const labelNodes=[{id:'a',label:'Synthetic A',x:100,y:100},{id:'b',label:'Synthetic B',x:101,y:100},{id:'c',label:'Synthetic C',x:400,y:300}];
const wide={x:0,y:0,w:1000,h:600};
assert.equal(labelIds(labelNodes,wide,1000).size,0,'Overview has no persistent labels');
assert.deepEqual([...labelIds(labelNodes,wide,1000,new Set(['c']))],['c'],'Searching reveals matching labels without revealing unrelated labels');
assert.equal(labelIds(labelNodes,{...wide,w:500},1000).size,2,'Zoom reveals names while suppressing overlapping labels');
assert.equal(labelIds(labelNodes,wide,1000).size,0,'Fitting the graph hides labels again');
assert.equal(labelIds(labelNodes,{x:800,y:800,w:100,h:100},1000).size,0,'Off-screen labels are excluded');

// Exercise citation rendering with inert DOM nodes; model prose is always text.
const fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag,text=''){this.tag=tag;this.text=text;this.children=[];this.dataset={};this.isConnected=true}
 setAttribute(name,value){this[name]=value}
 get textContent(){return this.children.length?this.children.map(n=>n.nodeValue??n.textContent??n.text??'').join(''):this.text}
 set textContent(value){this.text=value;this.children=[]}
 append(...nodes){this.children.push(...nodes)}
 addEventListener(){}
 replaceChildren(...nodes){this.children=nodes}
 showModal(){this.open=true}
 close(){this.open=false}
 remove(){this.isConnected=false}
}
const body=new Element('body'),host=new Element('div'),raw='[Data:\nSources (0); Relationships (8, +more)]';
const page={document_id:'d',document:'Synthetic.pdf',folder:'Fixture',page:1,version:'original'};
const sandbox={document:{body,createTextNode:text=>({nodeValue:text,isConnected:true})},se:(tag,text)=>new Element(tag,text),priorityButton:(text,action)=>Object.assign(new Element('button',text),{onclick:action}),Map,Set};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/graphrag-i18n.js','utf8'),sandbox);
const source=fs.readFileSync(__dirname+'/graphrag-result-ui.js','utf8');vm.runInContext(source.slice(source.indexOf('function graphQueryAnswer'),source.indexOf('const graphResultStyle')),sandbox);
const cleanup=sandbox.graphQueryAnswer(host,{answer:'<img src=x onerror=alert(1)> **Claim** '+raw+' [Data: Sources (999)]',pilot_run:'test',citations:[{raw,has_more:true,records:[{dataset:'sources',id:'0',status:'resolved',pages:[{page,quotes:[]}]},{dataset:'relationships',id:'8',status:'resolved',pages:[{page,quotes:[]}]}]}]});
const buttons=host.children.filter(n=>n.tag==='button');assert.equal(buttons.length,2,'Multiline references remain clickable');
assert.equal(host.children.filter(n=>n.tag==='img').length,0,'Never interpret model HTML');assert.equal(buttons[1].dataset.unresolved,'true');
buttons[0].onclick();const drawer=body.children[0];assert.equal(drawer.children.filter(n=>n.className==='graph-citation-source').length,1,'Merge duplicate source pages across IDs');
assert.ok(drawer.children.some(n=>String(n.textContent).includes('«+more»')));
cleanup();assert.equal(drawer.isConnected,false);
const variantHost=new Element('div'),variant='[Sources (0); Relationships: 8]',missing='[Entities (999)]';
const variantCleanup=sandbox.graphQueryAnswer(variantHost,{answer:'**Evidence '+variant+'** Again '+variant+' '+missing,pilot_run:'frozen',context_pages:[{page:{...page,page:2},quotes:[]}],citations:[{raw:variant,records:[{dataset:'sources',id:'0',status:'resolved',pages:[{page,quotes:[{quote:'Exact passage'}]}]}]},{raw:missing,records:[{dataset:'entities',id:'999',status:'not_in_context',pages:[]}]}]});
const descendants=n=>[n,...(n.children||[]).flatMap(descendants)];
const variants=descendants(variantHost).filter(n=>n.className==='graph-citation-link');
assert.equal(variants.length,3,'References without Data prefix and inside bold text are clickable');
assert.equal(variants[0].textContent,variants[1].textContent,'Repeated references use the same citation number');
assert.match(variants[0].textContent,/Cita 1 · 1 página/);
assert.equal(variants[2].dataset.unresolved,'true');
const summary=variantHost.children[0];assert.match(summary.textContent,/Citas: 2 · Páginas o lecturas enlazadas: 1 · Citas sin resolver: 1/);
const contextButton=descendants(summary).find(n=>n.tag==='button'&&n.textContent==='Contexto consultado');contextButton.onclick();
const variantDrawer=body.children[1];assert.match(variantDrawer.textContent,/No significa que la respuesta las cite/);
assert.match(variantDrawer.textContent,/p. 2/);assert.ok(!variantDrawer.textContent.includes('p. 1'),'Do not mix context and cited pages');
variants[2].onclick();assert.match(variantDrawer.textContent,/no corresponde a un registro del contexto/);
variants[0].onclick();const openButton=descendants(variantDrawer).find(n=>n.tag==='button'&&n.textContent==='Abrir imagen y transcripción');
let opened;sandbox.graphPilotSource=async source=>{opened=source};sandbox.sourcePopup={open:true,addEventListener:()=>{}};
(async()=>{
 await openButton.onclick();assert.equal(opened.id,'frozen:citation');assert.equal(opened.page.page,1);assert.equal(opened.quotes[0].quote,'Exact passage');assert.equal(variantDrawer.open,false);
 variants[0].onclick();sandbox.graphPilotSource=async()=>{throw Error('Synthetic source failure')};
 await descendants(variantDrawer).find(n=>n.tag==='button'&&n.textContent==='Abrir imagen y transcripción').onclick();
 assert.match(variantDrawer.textContent,/No se pudo abrir esta fuente/);assert.equal(variantDrawer.open,true,'Keep citations available after an opening failure');variantCleanup();
})().catch(error=>{console.error(error);process.exitCode=1});
const noCites=new Element('div');sandbox.graphQueryAnswer(noCites,{answer:'No citations',context_pages:[{page,quotes:[]}]});assert.match(noCites.textContent,/no incluye citas identificables/);assert.ok(!noCites.textContent.includes('Ver páginas citadas'));

console.log('Graph overview retains all assertions, large neighborhoods, isolated nodes and directed links.');
console.log('Citations: multiline references, page deduplication, unresolved IDs and inert model HTML passed.');
const {filterSources}=require('./graphrag-result-core.js');
const pageA={folder:'A',document:'A/a.pdf'},pageB={folder:'B',document:'B/b.pdf'};
const scopedFixture={selection:[pageA,pageB],nodes:[{id:'a',type:'PERSON',mentions:[{page:pageA},{page:pageB}]},{id:'b',type:'PLACE',mentions:[]},{id:'c',type:'PERSON',mentions:[{page:pageB}]},{id:'isolated',type:'TIME',mentions:[{page:pageA}]}],relationships:[{source:'a',target:'b',page:pageA},{source:'a',target:'c',page:pageB}]};
const filtered=filterSources(scopedFixture,{folders:['A']});
assert.deepEqual(filtered.nodes.map(n=>n.id),['a','b','isolated']);assert.equal(filtered.relationships.length,1);assert.equal(filtered.pages,1);assert.equal(filtered.nodes[0].mentions.length,1);assert.equal(scopedFixture.nodes[0].mentions.length,2);
assert.equal(filterSources(scopedFixture,{folders:['A'],documents:['B/b.pdf']}).nodes.length,0);
assert.equal(filterSources(scopedFixture,{}),scopedFixture);
console.log('Source filters retain scoped edges and isolated nodes, preserve originals and conjoin filters.');
