const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/source-review.js','utf8');
const rangeCode=source.slice(source.indexOf('function sourceReviewRanges('),source.indexOf('function sourceReviewSync('));
const rangeContext={sourceReviewContext:{id:'doc',page:1,highlights:[{text:'A+B',kind:'person'},{text:'near Lake',kind:'place'}]}};
vm.createContext(rangeContext);vm.runInContext(rangeCode,rangeContext);
const page={id:'doc',number:1,text:'😀 A+B lives near\nLake. A+B'};
const hits=rangeContext.sourceReviewRanges(page);
assert.deepEqual(Array.from(hits,m=>page.text.slice(m.start,m.end)),['A+B','A+B','near\nLake']);
assert.equal(hits[0].start,3,'UTF-16 offsets retain the preceding emoji');
assert.equal(rangeContext.sourceReviewRanges({...page,number:2}).length,0,'Do not transfer hits to another page');
assert.equal(rangeContext.sourceReviewRanges({...page,text:'Corrected text'}).length,0);
const closeCode=source.slice(source.indexOf('const sourceNativeClose='),source.indexOf("sourcePopup.addEventListener('cancel'"));
async function checkClose(){
 let closed=0,released=0,resolveSave;
 const context={sourceReviewClosing:false,u:{modalHost:{},loading:false,busy:false},sourcePopup:{close(){closed++}},sourceReviewRelease(){released++},uFlush:()=>new Promise(resolve=>{resolveSave=resolve}),uBy:()=>({focus(){}})};
 vm.createContext(context);vm.runInContext(closeCode,context);
 const pending=context.sourcePopup.close();assert.equal(closed,0);assert.equal(released,0);resolveSave(false);await pending;
 assert.equal(closed,0,'A failed save must keep the editor open');assert.equal(released,0);
 const saved=context.sourcePopup.close();assert.equal(closed,0);resolveSave(true);await saved;
 assert.equal(closed,1);assert.equal(released,1,'Return the shared editor only after saving');
}
async function checkMatrixSources(){
 const matrixCode=source.slice(source.indexOf('const sourceReadMatrix='),source.indexOf('const sourceReviewCSS='));
 const calls=[];let allow=false;
 const context={
  sourceReviewPrepare:async()=>{calls.push('prepare');return allow},
  matrixSource:(row,quote)=>{calls.push(['snapshot',row,quote])},
  sourceReviewMount:async(...args)=>{calls.push(['editor',...args])},
  gMsg:(strings,...args)=>typeof strings==='string'?strings:strings.reduce((s,part,i)=>s+part+(args[i]??''),'')
 };
 vm.createContext(context);vm.runInContext(matrixCode,context);
 const row=Object.freeze({document_id:'doc',page:3,version:'original',text:'Frozen source quote',image_url:'/saved-image'});
 assert.equal(await context.matrixSource(row,'source quote'),false);
 assert.deepEqual(calls,['prepare'],'A failed flush must not replace the open editor with a snapshot');
 calls.length=0;allow=true;
 assert.equal(await context.matrixSource(row,'source quote'),true);
 assert.deepEqual(calls,['prepare',['snapshot',row,'source quote'],['editor','doc',3,'Matriz IA · original',false,true]]);
 assert.equal(row.text,'Frozen source quote','The frozen matrix text must remain unchanged');
 assert.equal(calls[1][1].image_url,'/saved-image','Retain the archived image URL for saved evidence');
 calls.length=0;
 await context.matrixSource(row,'','Saved selection · Research');
 assert.equal(calls[2][3],'Saved selection · Research · original');
}
Promise.all([checkClose(),checkMatrixSources()]).then(()=>console.log('Shared source editor: literal highlights, page isolation, matrix/saved sources and close/save guard passed')).catch(error=>{console.error(error);process.exitCode=1});
