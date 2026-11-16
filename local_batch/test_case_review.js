const vm=require('vm'),fs=require('fs'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/case-review.js','utf8').split('const oldCaseDraw=')[0];
const c={uiLanguage:'es',docIds:new Map([['demo.pdf','id']]),reviewIndex:{},piUser:()=>null,qw:()=> 'Alta',queueRecord:()=>({priority:0,priorityLabel:'Urgente',status:'Sin revisar',action:'',sources:['rules']})};vm.createContext(c);vm.runInContext(source,c);
const d={source:'demo.pdf'},p={number:1};
function set(decision,extras={}){vm.runInContext('caseDecisions='+JSON.stringify({'id:1':{decision,applicable:true,review_revision:0,updated:20,...extras}}),c)}
set('correct');assert.equal(c.queueRecord(d,p).priority,4);assert.equal(c.queueRecord(d,p).status,'Alerta descartada');
set('incorrect');assert.equal(c.queueRecord(d,p).priority,1);
set('different_method',{method:'regions',note:'Synthetic note'});assert(c.queueRecord(d,p).action.includes('Dividir en regiones'));assert.equal(c.queueRecord(d,p).triageNote,'Synthetic note');
c.reviewIndex['id:1']={revision:1};assert.equal(c.queueRecord(d,p).triage,'');delete c.reviewIndex['id:1'];
c.piUser=()=>({updated:30});assert.equal(c.queueRecord(d,p).triage,'');
console.log('6 human decision routing and stale-decision checks passed');
