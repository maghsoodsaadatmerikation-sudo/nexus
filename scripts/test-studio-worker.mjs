import assert from 'node:assert/strict';
import {createHash,webcrypto} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';

const worker=await readFile(new URL('../public/studio/service-worker.js',import.meta.url),'utf8');
const html=await readFile(new URL('../public/studio/index.html',import.meta.url));
const handlers=new Map();
const cachedResponse=response([html]);
let nextFetch,cacheOpens=0;
const sandbox={
 self:{location:{href:'https://studio.example/service-worker.js'},addEventListener:(type,handler)=>handlers.set(type,handler)},
 caches:{open:async()=>{cacheOpens++;return {match:async()=>cachedResponse}}},
 crypto:webcrypto, URL, Uint8Array, Response, AbortController,
 fetch:(request,options)=>nextFetch(request,options), setTimeout, clearTimeout,
};
const {verified,fetchVerified}=runInNewContext(worker+'\n({verified,fetchVerified})',sandbox);

function response(chunks){
 const counts={reads:0,readerCancelled:0,bodyCancelled:0};
 return {
  type:'basic',status:200,redirected:false,headers:new Headers({'content-type':'text/html'}),
  body:{cancel:async()=>{counts.bodyCancelled++}},counts,
  clone:()=>({body:{getReader:()=>{
   let index=0;
   return {
    read:async()=>{counts.reads++;return index<chunks.length?{done:false,value:chunks[index++]}:{done:true}},
    cancel:async()=>{counts.readerCancelled++},releaseLock:()=>{},
   };
  }}}),
 };
}
const body=new TextEncoder().encode('shell');
const asset={kind:'html',bytes:body.length,sha256:createHash('sha256').update(body).digest('hex')};
assert(await verified(response([body.subarray(0,2),body.subarray(2)]),asset));
assert.equal(await verified(response([body.subarray(0,2)]),asset),false);
assert.equal(await verified(response([Buffer.from('wrong')]),asset),false);
const oversized=response([body,new Uint8Array(1),new Uint8Array(2000)]);
nextFetch=async()=>oversized;
assert.equal(await fetchVerified('https://studio.example/',asset),null);
assert.equal(oversized.counts.reads,2);
assert.equal(oversized.counts.readerCancelled,1);
assert.equal(oversized.counts.bodyCancelled,1);

nextFetch=async url=>response([url==='https://studio.example/'?html:Buffer.from('invalid asset')]);
let installation;
handlers.get('install')({waitUntil:value=>{installation=value}});
await assert.rejects(installation,/studio-integrity-mismatch/);
assert.equal(cacheOpens,0);

let requestedTimeout;
sandbox.setTimeout=(run,ms)=>{requestedTimeout=ms;queueMicrotask(run);return 0};
sandbox.clearTimeout=()=>{};
nextFetch=(_,options)=>new Promise((resolve,reject)=>{
 options.signal.addEventListener('abort',()=>reject(new Error('fixture-network-aborted')));
});
let delivery;
handlers.get('fetch')({
 request:{method:'GET',mode:'navigate',url:'https://studio.example/'},
 respondWith:value=>{delivery=value},
});
assert.equal(await delivery,cachedResponse);
assert.equal(requestedTimeout,8000);
console.log('STUDIO WORKER: verified bounded streaming and offline fallback');
