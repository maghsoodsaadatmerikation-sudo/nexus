import assert from 'node:assert/strict';
import '../web/table-core.js';
const T=NexusTable;let checks=0;
const ids=T.parse('[{"id":9007199254740992},{"id":9007199254740993}]','json');
assert.deepEqual(ids.rows,[['9007199254740992'],['9007199254740993']]);checks++;
const idReport=T.analyseTable(ids,{name:'ids.json',sha:'synthetic',size:1});assert.equal(idReport.column_stats[0].type,'categorical');assert.equal(idReport.column_stats[0].distinct,2);checks++;
assert.equal(T.groupReport(ids,0,-1).group_count,2);checks++;
assert.deepEqual(T.parse('[{"n":1},{"n":1.0},{"n":1e0}]','json').rows,[['1'],['1'],['1']]);checks++;
const escaped=T.parse('[{"text":"123 \\"quoted\\"","n":-7},{"text":"\\u0031","n":2}]','json');assert.equal(escaped.rows[0][0],'123 "quoted"');assert.equal(escaped.rows[1][0],'1');checks++;
assert.deepEqual(T.parse('[{"__proto__":9007199254740993}]','json').rows,[['9007199254740993']]);checks++;
assert.deepEqual(T.parse('[{"a":null,"b":true,"id":"9007199254740993"}]','json').rows,[['','true','9007199254740993']]);checks++;
assert.deepEqual(T.parse('[{"id":-9007199254740993},{"id":18446744073709551615}]','json').rows,[['-9007199254740993'],['18446744073709551615']]);checks++;
for(const bad of ['[{1:2}]','[{"n":01}]','[{"n":1e}]','[{"n":NaN}]','[{"n":1e309}]','[{"n":{"nested":1}}]']){assert.throws(()=>T.parse(bad,'json'));checks++}
for(const s of ['1e-400','-1e-400','0.00000001e-9999','۱e-۴۰۰']){assert.equal(T.strictNumeric(s),null);checks++}
for(const s of ['0e-400','-0.0e-400','۰e-۴۰۰']){assert.equal(T.strictNumeric(s)===0,true);checks++}
assert.equal(T.strictNumeric('5e-324'),Number.MIN_VALUE);checks++;
const tiny=T.numberStats([Number.MIN_VALUE,Number.MIN_VALUE]);for(const key of ['min','max','mean','median','q1','q3'])assert.equal(tiny[key],Number.MIN_VALUE);checks++;
const local=T.numberStats([Number.MIN_VALUE,Number.MIN_VALUE,1e308]);assert.equal(local.q1,Number.MIN_VALUE);assert.equal(local.median,Number.MIN_VALUE);checks++;
const huge=T.numberStats([-1e308,1e308]);assert.equal(huge.median,0);assert.equal(huge.q1,-5e307);assert.equal(huge.q3,5e307);checks++;
const mixed=T.parse('[{"v":1},{"v":2},{"v":3},{"v":4},{"v":1e-400}]','json'),summary=T.analyseTable(mixed,{name:'tiny.json',sha:'s',size:1}).column_stats[0];
assert.equal(summary.summary.mean,2.5);assert.equal(summary.summary.count,4);assert.equal(summary.invalid_numeric,1);assert.equal(mixed.rows.at(-1)[0],'1e-400');checks++;
const measured=T.parse('[{"v":1e307},{"v":2e307},{"v":3e307}]','json');assert.equal(T.analyseTable(measured,{name:'large.json',sha:'s',size:1}).column_stats[0].type,'numeric');checks++;
for(const values of [[-1e308,0,1e308],[-1.7e308,1.7e308],[Number.MIN_VALUE,Number.MIN_VALUE],[0,0,0],[-Number.MIN_VALUE,Number.MIN_VALUE]]){
 const bins=T.histogram(values);assert.equal(bins.length,8);assert.equal(bins.reduce((n,b)=>n+b.count,0),values.length);assert(bins.every(b=>Number.isSafeInteger(b.count)&&b.count>=0));checks++;
}
assert.deepEqual(T.histogram([]),[]);checks++;
for(const values of [[NaN],[Infinity],Array(5001).fill(1)]){assert.throws(()=>T.histogram(values));checks++}
for(const bins of [0,1.5,51]){assert.throws(()=>T.histogram([1],bins));checks++}
console.log(JSON.stringify({status:'PASS',checks,scope:'lossless-json-identifiers-and-numeric-range-boundaries'}));
