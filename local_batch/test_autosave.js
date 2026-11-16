const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(__dirname+'/unified-editor.js','utf8');
const section=source.slice(source.indexOf('async function uSave('),source.indexOf('function uStatus('));
function fixture(){let requests=[],resolvers=[];const p={id:'fake',number:1,revision:0,text:'before',annotations:[],note:'',originalHash:'fakehash',generation:1,savedGeneration:0,status:null};const c={u:{page:p,reviewer:'Tester',promise:null,error:null},dirty:true,opened:{data:{}},reviewIndex:{},uBy:()=>null,uIdentity:()=>{},uUpdateStatus:()=>{},drawInvitation:()=>{},uBackup:()=>{},uRemove:()=>{},uk:()=>'',ut:k=>k,clearTimeout,structuredClone,AbortSignal,fetch:async(url,opts)=>{requests.push(JSON.parse(opts.body));return await new Promise(r=>resolvers.push(r))}};vm.createContext(c);vm.runInContext(section,c);return {c,p,requests,resolvers}}
async function tick(){await new Promise(r=>setImmediate(r))}
(async()=>{
 const f=fixture();const saving=f.c.uSave();assert.equal(f.requests.length,1);f.p.text='after';f.p.generation=2;
 f.resolvers.shift()({ok:true,json:async()=>({revision:1,status:'draft',updated:1})});await tick();
 assert.equal(f.requests.length,2);assert.equal(f.requests[1].text,'after');assert.equal(f.requests[1].revision,1);
 f.resolvers.shift()({ok:true,json:async()=>({revision:2,status:'draft',updated:2})});assert.equal(await saving,true);assert.equal(f.c.dirty,false);
 const g=fixture();const conflict=g.c.uSave();g.resolvers.shift()({ok:false,status:409});assert.equal(await conflict,false);assert.equal(g.c.u.error,'conflict');assert.equal(g.c.dirty,true);await g.c.uSave();assert.equal(g.requests.length,1);
 const h=fixture();h.p.annotations=[{start:0,end:1,quote:'b'}];const s=h.c.uSave('validated');assert.equal(h.requests[0].status,'deferred');h.resolvers.shift()({ok:true,json:async()=>({revision:1,status:'deferred',updated:1})});await s;
 console.log('Autosave: edits during save, revision sequencing, conflicts and open-doubt status passed');
})().catch(e=>{console.error(e);process.exitCode=1});
