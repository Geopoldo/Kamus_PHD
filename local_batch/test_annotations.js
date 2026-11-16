const assert=require('assert');const {shiftReviewMarks,reviewDiffTokens}=require('./annotations-core.js');
const mark={start:4,end:8,quote:'date',note:'check'};
assert.deepEqual(shiftReviewMarks([mark],'The date','New The date'),[{...mark,start:8,end:12}]);
assert.deepEqual(shiftReviewMarks([mark],'The date','The year'),[]);
assert.deepEqual(shiftReviewMarks([mark],'The date','The date!'),[mark]);
const diff=reviewDiffTokens('a old b old c','a new b new c');
assert.equal(diff.filter(t=>t.type!=='added').map(t=>t.text).join(''),'a old b old c');
assert.equal(diff.filter(t=>t.type!=='removed').map(t=>t.text).join(''),'a new b new c');
console.log('5 annotation and diff checks passed');
