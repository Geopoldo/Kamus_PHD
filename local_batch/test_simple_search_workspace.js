const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/content-search.js','utf8'),context={};vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function searchFilterHits('),source.indexOf('function searchVersionName(')),context);
const reading=(version,criteria,approximate=false)=>({version,criteria:criteria.map(criterion=>({criterion})),approximate});
const data={hits:[
 {document:'A/one.pdf',folder:'A',page:1,matches:[reading('original',[0]),reading('human',[1])]},
 {document:'A/one.pdf',folder:'A',page:2,matches:[reading('original',[0,1],true)]},
 {document:'B/two.pdf',folder:'B',page:1,matches:[reading('original',[0,1]),reading('second_reading:model',[0])]},
 {document:'B/two.pdf',folder:'B',page:2,matches:[reading('original',[0]),reading('human',[1,2])]}
]};
const before=JSON.stringify(data),filter=f=>context.searchFilterHits(data,f);
assert.equal(filter({}).length,4);
assert.equal(filter({folder:'A',minimum:'2'}).length,1,'Criteria in different readings never form one match');
assert.equal(filter({version:'human',criterion:'0'}).length,0,'Criterion zero is a real filter');
assert.equal(filter({version:'human',criterion:'1'}).length,2);
assert.equal(filter({version:'second_reading'}).length,1);
assert.equal(filter({folder:'A',document:'B/two.pdf'}).length,0,'Keep conflicting source choices explicit');
assert.equal(context.searchFilterHits(data,{folder:'A',document:'B/two.pdf'},'folder').length,2,'A facet can inspect alternatives without its own limit');
assert.equal(filter({kind:'exact',minimum:'2'}).length,2);
assert.equal(filter({kind:'approximate',minimum:'2'}).length,1);
const filtered=filter({version:'original',criterion:'0',minimum:'2'});
assert.equal(filtered.length,2);assert.ok(filtered.every(h=>h.matches.every(m=>m.version==='original')));
const sorted=context.searchSortedHits(filtered,'relevance');assert.equal(sorted[0].document,'B/two.pdf','Exact evidence comes before equally complete approximate evidence');
const perReading=context.searchSortedHits(filter({}),'relevance');assert.equal(perReading[0].document,'B/two.pdf','Ranking counts criteria in one reading, not a union of versions');
assert.equal(context.searchSortedHits(filtered,'document')[0].document,'A/one.pdf');
assert.equal(context.searchUnicodeSlice('😀 Hannah Bay',2,8),'Hannah','Python code-point offsets preserve highlights after emoji');
assert.equal(JSON.stringify(data),before,'Filtering and ordering do not mutate saved result or evidence');
console.log('Simple search: same-reading filters, source dependencies, exact/approximate scope, ordering, immutable evidence and Unicode highlighting passed.');
