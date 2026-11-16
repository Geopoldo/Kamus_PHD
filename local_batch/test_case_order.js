const fs=require('fs'),vm=require('vm'),assert=require('assert');const s=fs.readFileSync(__dirname+'/case-review.js','utf8');const c={};vm.createContext(c);vm.runInContext(s.slice(s.indexOf('function casePendingOrder'),s.indexOf('async function caseNext')),c);
const row=(document,page,priority,triage='',sources=['rules'])=>({document,page,priority,triage,sources});
const rows=[row('z',4,1),row('a',3,0),row('a',1,0),row('b',1,0,'correct'),row('c',1,9,'',[]),row('d',1,4)];
assert.deepEqual(Array.from(c.casePendingOrder(rows),r=>r.document+':'+r.page),['a:1','a:3','z:4']);
assert.equal(c.casePendingOrder(rows.filter(r=>r!==rows[2]))[0].page,3);assert.equal(rows[0].document,'z');console.log('Priority order, next pending, decided exclusion and immutable input passed');
