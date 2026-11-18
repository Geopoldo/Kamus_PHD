// Interaction contract: gestures must preserve evidence, selection and camera.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {EventEmitter}=require('node:events'),core=require('./graphrag-result-core.js');
class Element{
 constructor(){this.style={};this.dataset={};this.children=[];this.clientWidth=900;this.clientHeight=600;this.isConnected=true;this.offsetWidth=280;this.offsetHeight=120;this.listeners={}}
 setAttribute(k,v){this[k]=v} append(...n){this.children.push(...n)} prepend(n){this.children.unshift(n)} before(){} after(){} remove(){} replaceChildren(...n){this.children=n} addEventListener(e,f){this.listeners[e]=f} querySelector(){return tooltip} querySelectorAll(){return []}
}
class Network{
 constructor(){this.n=new Map();this.e=new Map();network=this}
 addNode(id,a){this.n.set(id,a)} addEdgeWithKey(id,a,b,attrs){this.e.set(id,{a,b,attrs})}
 nodes(){return [...this.n.keys()]} getNodeAttribute(id,k){return this.n.get(id)[k]}
 updateEachNodeAttributes(fn){for(const [id,a] of this.n)this.n.set(id,fn(id,a))}
 extremities(id){const e=this.e.get(id);return [e.a,e.b]} getEdgeAttribute(id,k){return this.e.get(id).attrs[k]}
 forEachNode(fn){for(const [id,a] of this.n)fn(id,a)} forEachEdge(fn){for(const [id,e] of this.e)fn(id,e.attrs,e.a,e.b)}
}
class Renderer extends EventEmitter{
 constructor(n,c,s){super();renderer=this;this.settings=s;this.captor=new EventEmitter();this.state={x:.5,y:.5,ratio:1};this.camera=new EventEmitter();this.camera.getState=()=>this.state;this.camera.setState=s=>{Object.assign(this.state,s);this.camera.emit('updated')};this.camera.animate=s=>{Object.assign(this.state,s);this.camera.emit('updated')};this.camera.getBoundedRatio=x=>Math.max(.04,Math.min(3,x))}
 getCamera(){return this.camera} getMouseCaptor(){return this.captor} getBBox(){return {x:[-500,500],y:[-500,500]}} setCustomBBox(b){this.box=b}
 refresh(){this.emit('afterRender')} resize(){} kill(){this.killed=true} graphToViewport(p){return p} viewportToGraph(p){return p}
}
let renderer,network,now=0,frames=new Map(),next=0,observer,resizeCallback,resetCount=0,selected='',inspection=null,api;
const element=()=>new Element(),tooltip=element(),container=element(),stage=element(),details=element();
const input={nodes:['a','b','c','d','isolated'].map((id,i)=>({id,label:id,type:'PERSON',x:i*100,y:i*50})),relationships:[{source:'a',target:'b',fields:{relation:'known'},page:{document:'test',page:1}},{source:'b',target:'c',fields:{relation:'known'},page:{document:'test',page:2}},{source:'a',target:'d',fields:{relation:'known'},page:{document:'test',page:3}}]};
const layout={nodes:input.nodes,links:input.relationships.map(e=>({...e,edges:[e]}))};
const sandbox={window:{MaphGraphEngine:{Graph:Network,Sigma:Renderer,EdgeArrowProgram:{}},matchMedia:()=>({matches:false}),addEventListener(){},removeEventListener(){}},document:{createElement:()=>container,body:element()},uiLanguage:'en',GraphResultCore:core,gse:(tag,text)=>Object.assign(element(),{textContent:text}),gButton:(text,fn)=>Object.assign(element(),{textContent:text,onclick:fn}),gMsg:x=>x,performance:{now:()=>now},requestAnimationFrame:fn=>{frames.set(++next,fn);return next},cancelAnimationFrame:id=>frames.delete(id),ResizeObserver:class{constructor(fn){resizeCallback=fn}observe(){}disconnect(){}},MutationObserver:class{constructor(fn){observer=fn}observe(){}disconnect(){}},console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(__dirname+'/graph-webgl.js','utf8'),sandbox);
function settle(){now+=500;const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn(now))}
const event=(x=0,y=0)=>({x,y,original:{button:0,preventDefault(){}},preventSigmaDefault(){this.prevented=true}});
api=sandbox.graphWebGLMount({stage,svg:element(),layout,colors:{PERSON:'#fff'},names:new Map(input.nodes.map(n=>[n.id,n])),graph:input,details,inspect:(...args)=>{inspection=args;api.highlight('',new Set())},onSelect:id=>{selected=id;api.highlight(id,new Set())},onReset:()=>{resetCount++;api.reset();api.highlight('',new Set())}});
const before=JSON.stringify(input);
renderer.emit('clickNode',{node:'a',event:event()});settle();
assert.equal(selected,'a');assert.equal(container.dataset.view,'neighborhood');
renderer.state.ratio=.2;container.clientWidth=1100;resizeCallback();assert.equal(renderer.state.ratio,.82,'Resizing/fullscreen refits the neighborhood instead of retaining an off-screen camera');
assert.equal(renderer.settings.nodeReducer('c',network.n.get('c')).hidden,true,'Exclude second-hop nodes in a direct-neighbor view');
assert.equal(renderer.settings.nodeReducer('b',network.n.get('b')).hidden,false);
renderer.emit('enterNode',{node:'b'});assert.equal(container.dataset.selection,'a','Hover must not replace selection');
const center={...network.n.get('a')},neighbor={...network.n.get('b')},outside={...network.n.get('isolated')},camera={...renderer.state};
renderer.emit('downNode',{node:'a',event:event(10,10)});renderer.captor.emit('mousemovebody',event(110,60));renderer.captor.emit('mouseup');
assert.equal(network.n.get('a').x,center.x+100);assert.equal(network.n.get('a').y,center.y+50);
assert.equal(network.n.get('b').x,neighbor.x+16);assert.equal(JSON.stringify(network.n.get('isolated')),JSON.stringify(outside));assert.deepEqual(renderer.state,camera,'Node drag must not pan or renormalize the camera');
renderer.emit('clickNode',{node:'b',event:event()});assert.equal(selected,'a','A drag release must not select another node');
now+=400;const a={...network.n.get('a')},b={...network.n.get('b')};
renderer.emit('downEdge',{edge:'0',event:event()});renderer.captor.emit('mousemovebody',event(25,40));renderer.captor.emit('mouseup');
assert.equal(network.n.get('a').x,a.x+25);assert.equal(network.n.get('b').x,b.x+25,'Dragging a relation moves both endpoints');
now+=400;renderer.emit('clickEdge',{edge:'0',event:event()});settle();assert.equal(inspection[1][0].page.page,1);assert.equal(container.dataset.view,'neighborhood','Opening edge evidence must retain the focused view');
const dbl=event(800,500);renderer.emit('doubleClickStage',{event:dbl});settle();
assert.ok(dbl.prevented,'Do not also execute Sigma double-click zoom');assert.equal(resetCount,1);assert.equal(container.dataset.selection,'');assert.equal(container.dataset.view,'overview');assert.equal(renderer.state.ratio,1);
for(const n of layout.nodes){assert.equal(network.n.get(n.id).x,n.x);assert.ok(Math.abs(network.n.get(n.id).y+n.y)<1e-8);assert.equal(renderer.settings.nodeReducer(n.id,network.n.get(n.id)).hidden,false)}
renderer.emit('clickStage',{event:event(108,-50)});settle();assert.equal(container.dataset.selection,'b','Small nodes have a forgiving hit area and remain selectable after reset');
container.listeners.keydown({key:'Escape',preventDefault(){}});settle();assert.equal(resetCount,2);
assert.equal(JSON.stringify(input),before,'All gestures leave the historical data unchanged');
details.isConnected=false;observer();assert.equal(renderer.killed,true);assert.equal(renderer.captor.listenerCount('mousemovebody'),0);
console.log('WebGL: selection, neighbor focus, drag nodes/edges, camera stability, double-click/Escape reset, source inspection and cleanup passed.');
const dense={nodes:Array.from({length:16},(_,i)=>({id:String(i),label:'N'+i})),relationships:[]};
for(let i=0;i<16;i++)for(let j=i+1;j<16;j++)if(Math.floor(i/4)===Math.floor(j/4))dense.relationships.push({source:String(i),target:String(j)});
for(let i=0;i<12;i+=4)dense.relationships.push({source:String(i+3),target:String(i+4)});
const arranged=core.overview(dense,{compact:true}),positions=new Map(arranged.nodes.map(n=>[n.id,n]));
const distance=(a,b)=>Math.hypot(positions.get(a).x-positions.get(b).x,positions.get(a).y-positions.get(b).y);
const linked=dense.relationships.reduce((s,e)=>s+distance(e.source,e.target),0)/dense.relationships.length;
let unrelated=0,count=0;for(let i=0;i<4;i++)for(let j=12;j<16;j++){unrelated+=distance(String(i),String(j));count++}
assert.ok(linked<unrelated/count,'Direct connections should be closer than distant groups');
const focused=core.focusLayout(arranged,'3');assert.deepEqual(new Set(focused.map(n=>n.id)),new Set(['0','1','2','3','4']));
assert.ok(focused.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)));assert.equal(focused.find(n=>n.id==='3').x,0);
assert.deepEqual(core.focusLayout(arranged,'3'),focused,'Reopening a neighborhood has stable positions');
console.log('Topology: linked groups cluster, focused layout preserves all direct neighbors and is deterministic.');
