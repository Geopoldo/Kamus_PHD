const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(__dirname+'/unified-editor.js','utf8');
const section=source.slice(source.indexOf('openReview=async function('),source.indexOf('nextReview=async function('));
function fixture(){let fetches=0,resolve;const doc={source:'synthetic',pages:[{number:1,status:'complete'},{number:2,status:'complete'}]};const c={u:{page:null,loading:false,busy:false},uFlush:async()=>true,state:{documents:[doc]},docIds:new Map([['synthetic','id']]),uRefreshSelectors:()=>{},fetch:async()=>{fetches++;return await new Promise(r=>resolve=r)},uRead:()=>null,uStore:()=>{},uBuild:()=>{},uReveal:()=>{},showView:()=>{},uUpdateStatus:()=>{},ut:k=>k,resultsView:{},dirty:false,opened:null};vm.createContext(c);vm.runInContext(section,c);return {c,resolve:r=>resolve(r),count:()=>fetches}}
(async()=>{
 const f=fixture();const first=f.c.openReview('id',1);await new Promise(r=>setImmediate(r));assert.equal(await f.c.openReview('id',2),false);assert.equal(f.count(),1);f.resolve({ok:true,json:async()=>({metadata:{status:'complete'},original:'Synthetic',original_hash:'hash',image:true})});assert.equal(await first,true);assert.equal(f.c.opened.page,1);assert.equal(f.c.u.loading,false);
 f.c.uFlush=async()=>false;assert.equal(await f.c.openReview('id',2),false);assert.equal(f.c.opened.page,1);assert.equal(f.c.u.loading,false);
 const g=fixture();const load=g.c.openReview('id',1);await new Promise(r=>setImmediate(r));g.resolve({ok:false});assert.equal(await load,false);assert.equal(g.c.u.loading,false);
 console.log('Navigation: concurrent opens, blocked save and failed load passed');
})().catch(e=>{console.error(e);process.exitCode=1});
