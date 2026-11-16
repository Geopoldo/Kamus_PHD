const assert=require('node:assert/strict');
const fs=require('node:fs');
const B=require('./priority-balance-core.js');
const entities=[{id:'a',label:'John Diamond',kind:'person',sources:[{sheet:'Names',row:2}]},{id:'b',label:'Hannah Bay',kind:'place',sources:[{sheet:'Places',row:2}]},{id:'c',label:'Diamond',kind:'surname',sources:[{sheet:'Names',row:2}]},{id:'z',label:'Absent',kind:'surname',sources:[{sheet:'Names',row:3}]}];
const m=(entity,quality,offsets=[[0,4]])=>({entity,quality,offsets});
const page=(doc,num,versions)=>({document_id:doc,document:doc+'.pdf',folder:'folder',page:num,versions});
const v=(version,matches)=>({version,text:'John Diamond ... Hannah Bay',matches});
const pages=[
  page('one',1,[v('original',[m('a','literal',[[0,4],[5,12]]),m('a','literal',[[30,34],[35,42]]),m('b','candidate',[[16,22],[23,26]]),m('c','literal',[[5,12]])]),v('human',[m('a','literal',[[0,4],[5,12]]),m('b','alias',[[16,22],[23,26]])])]),
  page('one',2,[v('original',[m('a','near')]),v('human',[m('b','literal',[[16,26]])])]),
  page('two',1,[v('original',[m('b','clue',[[16,26]])])])
];

// Structured filters: OR within each dimension, AND between dimensions. IDs select
// whole referents, including alias evidence; readings remain separate.
const structuredEntities=entities.map(e=>({...e,priority:e.id==='a'?'Alta':'Media'}));
structuredEntities.push({id:'local',kind:'place',priority:'Baja',sources:[]},{id:'off',kind:'place',priority:'Alta',enabled:false,sources:[]});
assert.equal(B.filterEntities(structuredEntities,{}).length,5);
assert.deepEqual(B.filterEntities(structuredEntities,{refs:['a','b','local'],priority:['Alta','Media'],kind:['person','place']}).map(e=>e.id),['a','b']);
assert.deepEqual(B.filterEntities(structuredEntities,{sheet:['Places','user'],priority:['Baja','Media']}).map(e=>e.id),['b','local']);
assert.deepEqual(B.filterEntities(structuredEntities,{refs:['a'],kind:['place']}),[]);
const filteredStructured=B.filterEvidence(pages,{quality:['literal','alias'],version:['original','human'],document:['one.pdf']},new Set(['a','b']));
assert.equal(filteredStructured.length,2);
assert.deepEqual(filteredStructured[0].versions[0].matches.map(m=>m.entity),['a','a']);
assert.equal(filteredStructured[0].versions[1].matches.find(m=>m.entity==='b').quality,'alias');
assert.deepEqual(filteredStructured[1].versions.map(v=>v.version),['human']);
assert.equal(B.filterEvidence(pages,{folder:['missing']}).length,0);
assert.equal(B.filterEvidence(pages,{version:['human']},new Set(['a'])).length,1);
assert.equal(B.filterSource({folder:'folder',document:'one.pdf',version:'second_reading:run-1'},{folder:['folder'],document:['one.pdf'],version:['secondary']}),true);
assert.equal(B.filterSource({folder:'folder',document:'one.pdf',version:'original'},{version:['human','secondary']}),false);
assert.equal(B.count(B.analyze(entities,filteredStructured).total).pages,2);

// Distinct source pages, exclusive best evidence buckets, and true zeros.
const analysis=B.analyze(entities,pages);
// The general export always includes zeros and inactive criteria, not screen filters.
const report=B.generalRows({catalog:{entities:[...entities,{id:'off',label:'Disabled',kind:'place',enabled:false}],revision:7},pages,created:1000,coverage:{searched_pages:4,inventory_pages:5}},'Ana','2026-11-16T00:00:00Z');
assert.equal(report.length,6);
const reportValue=(id,column)=>report[id][report[0].indexOf(column)];
assert.equal(reportValue(1,'Páginas distintas'),2); // original + edited remains one page
assert.equal(reportValue(1,'Páginas con cruce persona/apellido y lugar'),1);
assert.equal(reportValue(1,'Páginas sin ese cruce (excluye nombres separados)'),1);
assert.equal(reportValue(4,'Estado del criterio'),'Sin hallazgos');
assert.equal(reportValue(5,'Estado del criterio'),'Inactivo: no buscado');
assert.equal(reportValue(5,'Páginas distintas'),0);
assert.equal(reportValue(1,'Exportado por'),'Ana');
assert.equal(reportValue(1,'Revisión de criterios'),7);
assert.equal(reportValue(1,'Páginas del inventario'),5);
assert.deepEqual(analysis.breakdown.total,{total:4,strong:3,review:0,context:0,none:1});
assert.equal(B.count(analysis.total).pages,3);
assert.equal(B.count(analysis.total).readings,5);
assert.equal(B.count(analysis.stats.get('a')).pages,2);
assert.equal(B.count(analysis.stats.get('a')).score,185); // 100 once, plus a near page at 85
assert.deepEqual(B.count(analysis.stats.get('a')).byGroup,{strong:1,review:1,context:0,none:0});
assert.equal(B.count(analysis.stats.get('z')).pages,0);

// Two occurrences and two versions do not count as four pages.
const distribution=B.buildMatrix(entities,pages,'folder',{columns:['empty-folder']});
assert.equal(distribution.cells.get('a').get('folder').pageRanks.size,2);
assert.equal(distribution.cells.get('a').get('folder').occurrences,4);
assert.equal(distribution.cells.get('z').size,0);
assert.ok(distribution.columns.includes('empty-folder'));
const evidence=B.materialize(distribution.cells.get('a').get('folder'));
assert.equal(evidence.length,2);assert.equal(evidence[0].versions.length,2);
assert.ok(evidence.every(p=>p.versions.every(v=>v.matches.every(m=>m.entity==='a'))));

// Co-occurrence must share a page AND version; the original/human split on page 2 is excluded.
const together=B.buildMatrix(entities,pages,'folder',{focus:'a'});
assert.equal(together.stats.get('b').pageRanks.size,1);
assert.equal(together.stats.get('b').best,1); // best shared evidence is the human alias
assert.deepEqual(B.materialize(together.stats.get('b')).map(p=>p.page),[1]);
assert.equal(together.stats.has('a'),false);
assert.equal(together.stats.get('c').pageRanks.size,1); // separate second John Diamond occurrence

// A surname nested in the only full-name occurrence is not an independent pair by default.
const overlapping=[page('same',1,[v('original',[m('a','literal',[[0,4],[5,12]]),m('c','literal',[[5,12]])])])];
assert.equal(B.buildMatrix(entities,overlapping,'folder',{focus:'a'}).stats.get('c').pageRanks.size,0);
assert.equal(B.buildMatrix(entities,overlapping,'folder',{focus:'a',includeOverlap:true}).stats.get('c').pageRanks.size,1);
const crossPages=[...pages,page('far',1,[v('original',[m('a','cooccurrence',[[0,4],[30,35]]),m('b','literal',[[16,26]])])])];
const cross=B.buildCross(entities.filter(e=>e.kind!=='place'),entities.filter(e=>e.kind==='place'),crossPages);
assert.equal(cross.cells.get('a').get('b').pageRanks.size,1);
assert.equal(B.count(cross.cells.get('a').get('b')).score,95);
const includingFar=B.buildCross(entities.filter(e=>e.kind!=='place'),entities.filter(e=>e.kind==='place'),crossPages,{closeNames:false});
assert.equal(includingFar.cells.get('a').get('b').pageRanks.size,2);
assert.equal(B.count(includingFar.cells.get('a').get('b')).score,115);
assert.deepEqual(B.typedRanges([m('a','literal',[[0,4],[5,12]]),m('c','literal',[[5,12]]),m('b','literal',[[16,26]])],new Map(entities.map(e=>[e.id,e.kind]))),[[0,4,'person'],[5,12,'person'],[16,26,'place']]);
assert.deepEqual(B.typedRanges([m('c','literal',[[5,12]])],new Map(entities.map(e=>[e.id,e.kind]))),[[5,12,'surname']]);
// A weak place clue lowers the pair score, without making a nearby name distant.
const weakPlace=B.buildCross([entities[0]],[entities[1]],[page('clue',1,[v('original',[m('a','literal',[[0,4],[5,12]]),m('b','clue',[[16,26]])])])]);
const weakPair=weakPlace.stats.get('a');
assert.equal(B.count(weakPair).score,20);
const nameEvidence=B.count(B.analyze([entities[0]],B.materialize(weakPair)).stats.get('a'));
assert.equal(nameEvidence.closePages,1);
assert.equal(nameEvidence.distantPages,0);
// Crosses retain standalone mentions; totals partition per entity and page, not per version.
assert.equal(cross.allPeople.get('a').pageRanks.size,2); // distant name excluded by default
assert.equal(cross.unpairedPeople.get('a').pageRanks.size,1); // name in original, place only in human
assert.equal(cross.allPlaces.get('b').pageRanks.size,4);
assert.equal(cross.unpairedPlaces.get('b').pageRanks.size,3);
assert.equal(cross.unpairedPlaceTotal.pageRanks.size,3);
for(const [id,all] of cross.allPeople)assert.equal(all.pageRanks.size,cross.stats.get(id).pageRanks.size+cross.unpairedPeople.get(id).pageRanks.size);
assert.deepEqual(B.materialize(cross.unpairedPeople.get('a')).map(p=>[p.document_id,p.page,p.versions.map(v=>v.version)]),[['one',2,['original']]]);
const mixed=B.buildCross([entities[0]],[entities[1]],[page('mixed',1,[v('original',[m('a','literal',[[0,12]]),m('b','literal',[[16,26]])]),v('human',[m('a','literal',[[0,12]])])])]);
assert.equal(mixed.allPeople.get('a').pageRanks.size,1);
assert.equal(mixed.unpairedPeople.get('a').pageRanks.size,0);
const onlyPlaces=B.buildCross([], [entities[1]], pages);
assert.equal(onlyPlaces.allPlaceTotal.pageRanks.size,onlyPlaces.unpairedPlaceTotal.pageRanks.size);
const types=new Map(entities.map(e=>[e.id,e]));
const sorted=[m('a','cooccurrence'),m('c','literal'),m('a','candidate'),m('a','near'),m('a','alias'),m('a','literal')].sort((a,b)=>B.relevance([a],types)-B.relevance([b],types));
assert.deepEqual(sorted.map(m=>m.quality),['literal','alias','near','candidate','literal','cooccurrence']);
assert.equal(B.relevance([m('a','cooccurrence'),m('b','literal')],types),4); // still a valid place result

// Seven kind combinations, with surname mentions inside a full name counted only as a person.
const combinations=B.pageCombinations(entities,Array.from({length:7},(_,index)=>{
  const mask=index+1,matches=[];
  if(mask&1)matches.push(m('a','literal',[[0,4],[5,12]]),m('c','literal',[[5,12]]));
  if(mask&2)matches.push(m('c','literal',[[30,37]]));
  if(mask&4)matches.push(m('b','literal',[[16,26]]));
  return page('kinds',mask,[v('original',matches)]);
}));
for(let mask=1;mask<8;mask++)assert.equal(combinations.combinations.get(mask).pageRanks.size,1);
assert.equal(combinations.total.pageRanks.size,7);
const split=B.pageCombinations(entities,[page('versions',1,[v('original',[m('a','literal',[[0,12]])]),v('human',[m('b','literal',[[16,26]])])])]);
assert.equal(split.combinations.get(1).pageRanks.size,1);
assert.equal(split.combinations.get(4).pageRanks.size,1);
assert.equal(split.combinations.get(5).pageRanks.size,0); // never combine original with edited text
assert.equal(split.total.pageRanks.size,1);
const union=B.combineRecords([split.combinations.get(1),split.combinations.get(4)]);
assert.equal(union.pageRanks.size,1); // multiple selected categories never duplicate a page
assert.equal(union.readings.size,2);
assert.deepEqual(B.materialize(B.combineRecords([split.combinations.get(1)]))[0].versions.map(v=>v.version),['original']);
const separated=B.pageCombinations(entities,[page('far',1,[v('original',[m('a','cooccurrence',[[0,4],[30,35]])])]),page('far',2,[v('original',[m('a','cooccurrence',[[0,4],[30,35]]),m('b','literal',[[16,26]])])])]);
assert.equal(separated.combinations.get(1).pageRanks.size,0);
assert.equal(separated.combinations.get(4).pageRanks.size,1);
assert.equal(separated.distant.pageRanks.size,1);

// Filters are inputs, not hidden overrides: only original produces the weaker pair.
const original=pages.map(p=>({...p,versions:p.versions.filter(v=>v.version==='original')}));
assert.equal(B.buildMatrix(entities,original,'quality',{focus:'a'}).stats.get('b').best,3);
const readings=B.buildMatrix(entities,pages,'version');
assert.equal(readings.stats.get('a').pageRanks.size,2);
assert.equal(readings.cells.get('a').get('original').pageRanks.size,2);
assert.equal(readings.cells.get('a').get('human').pageRanks.size,1);
assert.deepEqual(B.audit({sheets:[{name:'Names',data_rows:2},{name:'Places',data_rows:1}],entities}),[{sheet:'Names',expected:2,covered:2,complete:true},{sheet:'Places',expected:1,covered:1,complete:true}]);

// Reconcile the actual saved corpus with its search summary (without modifying it).
const saved=JSON.parse(fs.readFileSync(__dirname+'/results/priorities/latest.json','utf8'));
const actual=B.analyze(saved.catalog.entities.filter(e=>e.enabled!==false),saved.pages),totals=B.count(actual.total);
assert.equal(totals.pages,saved.summary.pages);
assert.equal(actual.breakdown.total.none,saved.summary.entities_without_hits);
assert.equal(actual.breakdown.total.total-actual.breakdown.total.none,saved.summary.entities_with_hits);
assert.ok(B.audit(saved.catalog).every(s=>s.complete));
console.log('Balance checks passed: deduplication, zeros, evidence buckets, same-version pairs, overlapping spans, filters, Excel coverage, real corpus reconciliation.');
console.log(JSON.stringify(actual.breakdown));
