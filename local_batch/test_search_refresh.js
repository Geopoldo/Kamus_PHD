// Query refreshes must use current results without losing filters or accepting
// an older response after a newer query. No production corpus is changed.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/content-search.js','utf8');
const implementation=source.slice(source.indexOf('async function runContentSearch('),source.indexOf('function drawSearch('));
function fixture({saveChanges=false,saveResult=true}={}){
 const pending=[],renders=[];let ui;
 const replaceUI=()=>ui={button:{disabled:false},status:{textContent:''},tree:{replaceChildren(){this.cleared=true}}};replaceUI();
 const c={URLSearchParams,searchData:null,searchBusy:false,searchSequence:0,searchLastRequest:null,searchFilterValues:{},activeView:'search',u:{page:{revision:1}},uSave:async()=>{if(saveChanges)c.u.page.revision++;return saveResult},window:{addEventListener(){}},sl:n=>String(n),
  searchView:{querySelector:s=>s==='button[type=submit]'?ui.button:s==='[data-search-status]'?ui.status:ui.tree},
  fetch:async(url,options)=>new Promise(resolve=>pending.push({url,options,resolve})),
  renderSearchTree:(tree,status)=>renders.push({data:c.searchData,tree,status})};
 vm.createContext(c);vm.runInContext(implementation,c);
 const reply=(index,data,ok=true)=>pending[index].resolve({ok,json:async()=>data});
 return {c,pending,renders,replaceUI,reply,get ui(){return ui}};
}
(async()=>{
 const f=fixture();let request=f.c.runContentSearch('Ruben','words');
 f.reply(0,{query:'Ruben',hits:[]});await request;
 f.c.searchFilterValues={folder:'folderA',version:'human'};
 request=f.c.runContentSearch('Ruben','words');const newUI=f.replaceUI();
 f.reply(1,{query:'Ruben',hits:[{page:2}]});await request;
 assert.equal(f.c.searchData.hits.length,1);assert.equal(f.renders.at(-1).tree,newUI.tree);
 assert.equal(f.c.searchFilterValues.folder,'folderA');assert.equal(newUI.button.disabled,false);
 assert.equal(f.pending[1].options.cache,'no-store');
 const older=f.c.runContentSearch('first','words'),newer=f.c.runContentSearch('second','words');
 f.reply(3,{query:'second',hits:[]});await newer;f.reply(2,{query:'first',hits:[{}]});await older;
 assert.equal(f.c.searchData.query,'second');assert.equal(Object.keys(f.c.searchFilterValues).length,0);
 request=f.c.runContentSearch('second','words');f.reply(4,null,false);await request;
 assert.equal(f.c.searchData,null);assert.equal(f.ui.status.textContent,'21');assert.equal(f.c.searchBusy,false);
 const g=fixture();g.c.searchLastRequest={query:'Ruben',mode:'words'};
 // A no-op save does not refresh; a successfully saved revision does.
 await g.c.uSave();assert.equal(g.pending.length,0);
 const saved=fixture({saveChanges:true});saved.c.searchLastRequest={query:'Ruben',mode:'words'};
 assert.equal(await saved.c.uSave(),true);assert.equal(saved.pending.length,1);saved.reply(0,{query:'Ruben',hits:[]});
 const failed=fixture({saveResult:false});failed.c.searchLastRequest={query:'Ruben',mode:'words'};
 assert.equal(await failed.c.uSave(),false);assert.equal(failed.pending.length,0);
 console.log('Search refresh: current text, filters, DOM replacement, response races and failure state passed');
})().catch(error=>{console.error(error);process.exitCode=1});
