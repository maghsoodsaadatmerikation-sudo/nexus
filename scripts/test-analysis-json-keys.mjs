import assert from 'node:assert/strict';
import '../web/table-core.js';
const T=NexusTable;let checks=0;const check=fn=>{fn();checks++};
const duplicates=[
 '[{"Score":1,"Score":99}]',
 '[{"Score":1,"\\u0053core":99}]',
 '[{"a":1,"\\u0061":2}]',
 '[{"__proto__":"first","__proto__":"second"}]',
 '[{"constructor":1,"constructor":2}]',
 '[{"":1,"":2}]',
 '[{"q\\\"":1,"q\\u0022":2}]',
 '[{"line\\n":1,"line\\u000a":2}]',
 '[{"value":null,"value":false}]',
 '[{"value":[1],"value":2}]',
 '[{"value":{"hidden":1},"value":2}]',
 '[{"other":1},{"value":2,"value":3}]',
 '[{"مقدار":1,"مقدار":2}]',
 '[{"😀":1,"\\ud83d\\ude00":2}]',
 '[{"a" \r\n : 1,"a"\t:2}]'
];
for(const raw of duplicates)check(()=>assert.throws(()=>T.parse(raw,'json'),/json-duplicate-key/));
check(()=>assert.deepEqual(T.parse('[{"Score":1},{"Score":99}]','json').rows,[['1'],['99']]));
check(()=>assert.deepEqual(T.parse('[{"a":1},{"\\u0061":2}]','json').rows,[['1'],['2']]));
check(()=>assert.deepEqual(T.parse('[{"Score":1,"score":2}]','json').columns,['Score','score']));
check(()=>assert.deepEqual(T.parse('[{"é":1,"é":2}]','json').rows,[['1','2']]));
check(()=>assert.deepEqual(T.parse('[{"__proto__":"p","constructor":"c","toString":"t"}]','json').rows,[['p','c','t']]));
check(()=>assert.deepEqual(T.parse('[{"text":"{\\\"a\\\":1,\\\"a\\\":2}","a":3}]','json').rows,[['{"a":1,"a":2}','3']]));
check(()=>assert.deepEqual(T.parse('[{"text":"braces } { and colon: and quote \\\"","a":3}]','json').rows,[['braces } { and colon: and quote "','3']]));
check(()=>assert.deepEqual(T.parse('[{"a:b":1,"a":2,"b":3}]','json').rows,[['1','2','3']]));
check(()=>assert.deepEqual(T.parse('[{"":1},{"":2}]','json').rows,[['1'],['2']]));
check(()=>assert.deepEqual(T.parse('[{"a":1},{"b":2}]','json').rows,[['1',''],['','2']]));
const raw=JSON.stringify(Array.from({length:T.MAX_ROWS},(_,i)=>({value:i})));check(()=>assert.equal(T.parse(raw,'json').rows.length,T.MAX_ROWS));
for(const raw of ['[{"a":1,}]','[{"a":1 "b":2}]','[{"a":{"b":1}}]','[{"a":[1]}]'])check(()=>assert.throws(()=>T.parse(raw,'json')));
console.log(JSON.stringify({status:'PASS',checks,scope:'ambiguous-json-fields-rejected-with-decoded-key-identity'}));
