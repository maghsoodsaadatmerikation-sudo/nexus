import assert from 'node:assert/strict';
import {createHash,webcrypto} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';

const worker=await readFile(new URL('../public/studio/service-worker.js',import.meta.url),'utf8');
const html=await readFile(new URL('../public/studio/index.html',import.meta.url));
const handlers=new Map();
const cachedResponse=response([html]);
const cacheEntries=new Map();
let nextFetch,cacheOpens=0,cacheWrites=0;
const sandbox={
 self:{location:{href:'https://studio.example/service-worker.js'},addEventListener:(type,handler)=>handlers.set(type,handler)},
 caches:{
  match:async url=>cacheEntries.get(url),
  open:async()=>{cacheOpens++;return {put:async(url,value)=>{cacheWrites++;cacheEntries.set(url,value)}}},
  delete:async()=>{cacheEntries.clear();return true},
 },
 crypto:webcrypto, URL, Uint8Array, Response, AbortController,
 fetch:(request,options)=>nextFetch(request,options), setTimeout, clearTimeout,
};
const {verified,fetchVerified,ensureShell,discardShell}=runInNewContext(worker+'\n({verified,fetchVerified,ensureShell,discardShell})',sandbox);

function response(chunks,type='text/html'){
 const counts={reads:0,readerCancelled:0,bodyCancelled:0};
 return {
  type:'basic',status:200,redirected:false,headers:new Headers({'content-type':type}),
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

const root='https://studio.example/';
cacheEntries.set(root,cachedResponse);
const fetchAssets=new Map([[root,[html,'text/html']]]);
for(const path of ['device-engine.js','device-ui.js','device-worker.js','model-manifest.json']){
 const bytes=await readFile(new URL('../public/studio/device/'+path,import.meta.url));
 const url=root+'device/'+path,type=path.endsWith('.js')?'text/javascript':'application/json';
 fetchAssets.set(url,[bytes,type]);cacheEntries.set(url,response([bytes],type));
}
let network=0;
nextFetch=async()=>{network++;throw new Error('offline')};
await ensureShell();
assert.equal(network,0);
assert.equal(cacheOpens,0);

let requestedTimeout;
sandbox.setTimeout=(run,ms)=>{requestedTimeout=ms;queueMicrotask(run);return 0};
sandbox.clearTimeout=()=>{};
nextFetch=(_,options)=>new Promise((resolve,reject)=>{
 options.signal.addEventListener('abort',()=>reject(new Error('fixture-network-aborted')));
});
let delivery;
handlers.get('fetch')({
 request:{method:'GET',mode:'navigate',url:root+'?offline=1'},
 respondWith:value=>{delivery=value},
});
assert.equal(await delivery,cachedResponse);
assert.equal(requestedTimeout,8000);
assert.equal(cacheOpens,0);
cacheEntries.clear();
delivery=undefined;
handlers.get('fetch')({
 request:{method:'GET',mode:'navigate',url:root},
 respondWith:value=>{delivery=value},
});
assert.equal((await delivery).status,503);
assert.equal(cacheOpens,0);

sandbox.setTimeout=setTimeout;
sandbox.clearTimeout=clearTimeout;
let release;
const pause=new Promise(resolve=>{release=resolve});
network=0;
nextFetch=async url=>{
 network++;
 await pause;
 const [bytes,type]=fetchAssets.get(url);
 return response([bytes],type);
};
const preparation=ensureShell(),duplicate=ensureShell();
while(network<fetchAssets.size)await new Promise(setImmediate);
const removal=discardShell();
release();
const result=await Promise.allSettled([preparation,duplicate,removal]);
assert.deepEqual(result.map(item=>item.status),['rejected','rejected','fulfilled']);
assert.equal(network,fetchAssets.size);
assert.equal(cacheWrites,0);
assert.equal(cacheOpens,0);
assert.equal(cacheEntries.size,0);
await assert.rejects(ensureShell(),/disabled/);
nextFetch=async url=>{const [bytes,type]=fetchAssets.get(url);return response([bytes],type)};
let reply,refresh;
handlers.get('message')({
 data:{type:'refresh-public-shell',reopen:true},
 ports:[{postMessage:value=>{reply=value}}],
 waitUntil:value=>{refresh=value},
});
await refresh;
assert.equal(reply.ok,true);
assert.equal(cacheWrites,fetchAssets.size);
assert.equal(cacheEntries.size,fetchAssets.size);
console.log('STUDIO WORKER: verified bounded downloads, offline recheck, query fallback and safe removal');
