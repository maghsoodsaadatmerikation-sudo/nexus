import assert from 'node:assert/strict';
import '../web/studio-core.js';
const S=globalThis.NexusStudio,enc=new TextEncoder();let checks=0,reads=0;
const file=(name,body)=>{const bytes=typeof body==='string'?enc.encode(body):body;return {name,size:bytes.byteLength,arrayBuffer:async()=>{reads++;return bytes.slice().buffer}}};
const sources=await S.readSources([file('one.txt','Local orchard'),file('two.MD','ماه'),file('three.TSV','x\t1')]);
assert.deepEqual(sources.map(s=>[s.name,s.text]),[['one.txt','Local orchard'],['two.MD','ماه'],['three.TSV','x\t1']]);checks++;
assert.equal(new Set(sources.map(s=>s.id)).size,3);checks++;
const p=S.project('Sources');p.sources=sources;assert.deepEqual(S.state({schema:S.SCHEMA,projects:[p]}).projects[0].sources,sources);checks++;
for(const files of [null,[],Array.from({length:13},()=>file('x.txt','x')),[file('x.pdf','x')],[{...file('x.txt','x'),name:'x'.repeat(161)+'.txt'}],[{...file('x.txt','x'),size:-1}],[{...file('x.txt','x'),size:1.5}],[{...file('x.txt','x'),size:S.MAX_SOURCE_BYTES+1}],[{...file('x.txt','x'),arrayBuffer:null}]]){
 const before=reads;await assert.rejects(S.readSources(files));assert.equal(reads,before);checks++;
}
const before=reads;await assert.rejects(S.readSources([file('valid.txt','not read'),file('bad.pdf','x')]));assert.equal(reads,before);checks++;
for(const files of [[file('first.txt','valid'),file('invalid.txt',new Uint8Array([255,254]))],[file('empty.txt','')],[file('spaces.txt','  ')],[{...file('size.txt','x'),size:2}],[{name:'bad.txt',size:1,arrayBuffer:async()=>1}]]){await assert.rejects(S.readSources(files));checks++}
const aborted=new AbortController();aborted.abort();const noReads=reads;await assert.rejects(S.readSources([file('x.txt','x')],{signal:aborted.signal}),/cancelled/);assert.equal(reads,noReads);checks++;
let entered,release;const started=new Promise(r=>entered=r),gate=new Promise(r=>release=r),abort=new AbortController();
const slow={name:'slow.txt',size:1,arrayBuffer:async()=>{entered();await gate;return enc.encode('x').buffer}},pending=S.readSources([slow,file('next.txt','must not read')],{signal:abort.signal});
await started;const previous=reads;abort.abort();release();await assert.rejects(pending,/cancelled/);assert.equal(reads,previous);checks++;
const original=[file('original.txt','retained')];let finish;const waiting=new Promise(r=>finish=r);original[0].arrayBuffer=async()=>{await waiting;return enc.encode('retained').buffer};const copied=S.readSources(original);original.push(file('unselected.txt','must not import'));finish();assert.equal((await copied).length,1);checks++;
assert.equal((await S.readSources([file('limit.txt','x'.repeat(S.MAX_SOURCE_BYTES))]))[0].text.length,S.MAX_SOURCE_BYTES);checks++;
assert.equal((await S.readSources(Array.from({length:S.MAX_SOURCES},(_,i)=>file('file-'+i+'.txt','x')))).length,12);checks++;
console.log(JSON.stringify({status:'PASS',checks,scope:'bounded-cancellable-source-batches',real_file_inputs_tested:false}));
