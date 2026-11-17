const assert=require('node:assert/strict'),progress=require('./graphrag-query-progress.js');
const job={id:'synthetic',mode:'local',status:'waiting_gpu',started:100,phases:[{name:'embedding',status:'waiting_gpu',started:101}]};
let state=progress.describe(job);assert.equal(state.state,'waiting_gpu');assert.equal(state.waiting,true);assert.equal(state.waitingSince,101);assert.equal(state.stages.length,4);assert.equal(state.stages[1].done,false);
state=progress.describe({...job,phases:[{...job.phases[0],status:'loading_model',wait_seconds:48}]});assert.equal(state.state,'loading_model');assert.equal(state.waiting,false);assert.equal(state.waitSeconds,48);assert.equal(state.current,'embedding');
const phases=[{name:'embedding',status:'complete',wait_seconds:48},{name:'query',status:'loading_model',wait_seconds:2}];state=progress.describe({...job,phases});assert.equal(state.current,'query');assert.equal(state.stages[1].done,true);assert.equal(state.waitSeconds,50);
state=progress.describe({...job,mode:'global',status:'query',phases:[{name:'query',status:'loading_model'}]});assert.equal(state.stages.length,3);assert.equal(state.stages.some(s=>s.key==='embedding'),false);
state=progress.describe({...job,status:'preparing_results',phases:phases.map(p=>({...p,status:'complete'}))});assert.equal(state.current,'results');assert.equal(state.active,true);
state=progress.describe({...job,status:'complete',phases:phases.map(p=>({...p,status:'complete'}))});assert.equal(state.active,false);assert.ok(state.stages.every(s=>s.done));
for(const status of ['failed','interrupted']){state=progress.describe({...job,status});assert.equal(state.failed,true);assert.equal(state.active,false);assert.equal(state.stages.at(-1).done,false)}
assert.equal(progress.describe(null),null);
console.log('GraphRAG progress: waiting, loading, embedding, query, assembly, completion and failure states passed; global queries skip the question embedding step.');
