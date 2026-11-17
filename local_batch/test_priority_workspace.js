// Exercise the page scope shared by previews and filtered CSV exports.
// A focused referent must retain the evidence that made a cross-reference valid.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const PriorityBalance=require('./priority-balance-core.js');
const source=fs.readFileSync(__dirname+'/priority-search.js','utf8');
const entities=[{id:'p',kind:'person',label:'Ana Fox',priority:'Alta'},{id:'s',kind:'surname',label:'Fox',priority:'Alta'},{id:'l',kind:'place',label:'River',priority:'Media'}];
const match=(entity,offsets)=>({entity,quality:'literal',offsets});
const person=match('p',[[0,7]]),surname=match('s',[[12,15]]),place=match('l',[[20,25]]);
const reading=(version,matches)=>({version,matches,text:'Ana Fox ... Fox ... River',hash:'synthetic-'+version});
const page=(id,number,versions)=>({document_id:id,document:id+'.pdf',folder:'folder',page:number,versions});
const pages=[
 page('b',2,[reading('original',[person,place]),reading('human',[person,surname,place])]),
 page('a',1,[reading('original',[person]),reading('human',[place])]),
 page('a',3,[reading('original',[surname,place])]),
 page('b',1,[reading('original',[person,place])])
];
const empty=()=>({refs:[],kind:[],sheet:[],quality:[],version:[],folder:[],document:[],priority:[],presence:''});
const c={PriorityBalance,priorityResult:{catalog:{entities},pages},priorityFilters:empty(),prioritySelected:'',priorityCategorySelection:new Set(),priorityUI:{sort:'relevance'},priorityMode:'list',priorityFilterLabels:new Map(),priorityPage:4,priorityDraw(){},priorityPageCompare:(a,b)=>b.page-a.page};
vm.createContext(c);
const part=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
vm.runInContext(part('function priorityChooseCategories(','function priorityToolbar(')+part('function priorityVisiblePages(','const priorityWorkspaceNav=')+part('function priorityEvidencePages(','function priorityDraw(){'),c);
const visible=()=>c.priorityVisiblePages();
assert.equal(visible().length,4);
c.priorityChooseCategories([5,7]);
assert.equal(c.priorityPage,0);
assert.equal(visible().length,2,'Two categories do not duplicate a source page');
assert.equal(visible().find(p=>p.page===2).versions.length,2,'Both matching readings remain available');
assert.ok(!visible().some(p=>p.document_id==='a'&&p.page===1),'Original and edited text never form a cross-reference together');
c.prioritySelected='p';
assert.equal(visible().length,2);
assert.ok(visible().every(p=>p.versions.every(v=>v.matches.some(m=>m.entity==='l'))),'Focus retains the place that substantiates the cross-reference');
c.priorityFilters.version=['human'];
assert.equal(visible().length,1);assert.equal(visible()[0].versions.length,1);
assert.equal(visible()[0].versions[0].version,'human');
c.priorityFilters.document=['a.pdf'];
assert.equal(visible().length,0,'An incompatible source filter produces an honest empty state');
c.priorityFilters=empty();c.prioritySelected='p';c.priorityChooseCategories([6,7]);
assert.equal(c.prioritySelected,'p','Changing a cross-reference preserves independently removable focus');
assert.equal(visible().length,1);c.prioritySelected='';
c.priorityChooseCategories([]);c.priorityUI.sort='document';
assert.deepEqual(Array.from(visible(),p=>p.document+':'+p.page),['a.pdf:1','a.pdf:3','b.pdf:1','b.pdf:2']);
assert.equal(pages[0].document_id,'b','Ordering never mutates stored evidence');
c.priorityFilters.refs=['l'];
assert.equal(visible().length,4,'Export scope responds to current filters without a redraw');
assert.ok(visible().every(p=>p.versions.every(v=>v.matches.every(m=>m.entity==='l'))));
assert.equal(c.priorityHasFilters(),true);c.priorityFilters=empty();assert.equal(c.priorityHasFilters(),false);
console.log('Cross-analysis workspace: category union, same-reading evidence, focused context, current export scope, empty results, reset and ordering passed.');

// Interdependent facets keep alternatives within their own dimension and constrain
// other dimensions by shared evidence, without mutating any selected filters.
const absent={id:'zero',kind:'person',label:'Absent',priority:'Baja'};
const catalog=[...entities,absent];
const f={...empty(),refs:['p','l']};
assert.equal(PriorityBalance.filterScope(catalog,pages,f).pages.length,2);
assert.ok(PriorityBalance.filterScope(catalog,pages,f).pages.every(p=>p.versions.every(v=>v.matches.some(m=>m.entity==='p')&&v.matches.some(m=>m.entity==='l'))));
let facets=PriorityBalance.facetValues(catalog,pages,{...empty(),refs:['p'],document:['b.pdf']});
assert.deepEqual([...facets['refs:place']],['l']);
assert.deepEqual([...facets.document],['a.pdf','b.pdf'],'The document facet ignores only its own selection');
assert.ok(!facets['refs:person'].has('zero'),'Unmatched names are excluded when sources limit the scope');
assert.ok(PriorityBalance.facetValues(catalog,pages,empty())['refs:person'].has('zero'),'The unfiltered catalog retains criteria without findings');
facets=PriorityBalance.facetValues(catalog,pages,{...empty(),refs:['p','l'],version:['human']});
assert.deepEqual([...facets.document],['b.pdf']);
assert.deepEqual([...facets.version].sort(),['human','original'],'Other compatible readings can still be added');
const conflict={...empty(),refs:['p','l'],document:['a.pdf'],version:['original']},before=JSON.stringify(conflict);
assert.equal(PriorityBalance.filterScope(catalog,pages,conflict).pages.length,0);
assert.ok(PriorityBalance.facetValues(catalog,pages,conflict).document.has('b.pdf'));
assert.equal(JSON.stringify(conflict),before,'Incompatible selections remain available for explicit removal');
facets=PriorityBalance.facetValues(catalog,pages,{...empty(),presence:'no'},{sources:[...pages,{folder:'empty/sub',document:'empty/sub/file.pdf'}]});
assert.ok(facets['refs:person'].has('zero'));
assert.ok(facets.document.has('empty/sub/file.pdf'),'No-findings searches can include sources without evidence');
assert.ok(facets.folder.has('empty'));
const narrowed=PriorityBalance.facetValues(catalog,pages,empty(),{categories:[5],focus:'p'});
assert.deepEqual([...narrowed.document],['b.pdf']);
console.log('Dependent filters: separate reference types, source/readings, disjunctive alternatives, zero findings, categories, focus and non-destructive conflicts passed.');
