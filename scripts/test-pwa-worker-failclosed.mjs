#!/usr/bin/env node
// Deterministic Service Worker policy/failure tests with disposable in-memory
// browser primitives. This does NOT replace real public-origin Chromium checks.
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';

const html=await readFile(new URL('../web/offline-pilot.html',import.meta.url));
const worker=await readFile(new URL('../public/service-worker.js',import.meta.url),'utf8');
const sha=value=>createHash('sha256').update(value).digest('hex');
const expected=sha(html);
assert(worker.includes("const EXPECTED_SHA256='"+expected+"'"),'worker HTML digest must be pinned');
const ORIGIN='https://nexus-pilot12-disposable.example';
const ENTRY=ORIGIN+'/';
const CACHE_PREFIX='nexus-app-shell-v12-';
const checked=[];

function basicResponse(body,{status=200,mime='text/html',redirected=false,type='basic'}={}){
  const bytes=Buffer.from(body);
  const options={status,mime,redirected,type};
  return {
    status,redirected,type,headers:new Headers({'Content-Type':mime}),
    clone(){return basicResponse(bytes,options)},
    async arrayBuffer(){return Uint8Array.from(bytes).buffer}
  };
}

function harness(initialResponse=basicResponse(html)){
  let online=true,networkResponse=initialResponse,networkCalls=0,claimed=0;
  const handlers=new Map(),stores=new Map();
  const cacheName=name=>{
    if(!stores.has(name))stores.set(name,new Map());
    const records=stores.get(name);
    const key=x=>typeof x==='string'?x:x.url;
    return {
      async put(k,r){records.set(key(k),r.clone())},
      async match(k){const v=records.get(key(k));return v?.clone()},
      async keys(){return [...records.keys()].map(url=>({url}))}
    };
  };
  const caches={
    open:async name=>cacheName(name),
    keys:async()=>[...stores.keys()],
    delete:async name=>stores.delete(name)
  };
  const self={
    location:{origin:ORIGIN},
    addEventListener:(type,fn)=>handlers.set(type,fn),
    skipWaiting:async()=>{},
    clients:{claim:async()=>{claimed++}}
  };
  const fetch=async()=>{
    networkCalls++;
    if(!online)throw Error('synthetic-offline-network');
    return networkResponse.clone();
  };
  runInNewContext(worker,{self,URL,Request,Response,TextDecoder,
    crypto:webcrypto,Uint8Array,Array,fetch,caches},
    {filename:'service-worker.js',timeout:1200});
  async function dispatchWait(type){
    let operation;
    const handler=handlers.get(type);
    assert(handler,type+' handler registered');
    handler({waitUntil(promise){operation=promise}});
    assert(operation,type+' waitUntil used');
    return operation;
  }
  async function navigate(url=ENTRY,method='GET',mode='navigate'){
    let response;
    handlers.get('fetch')({request:{url,method,mode},
      respondWith(promise){response=promise}});
    return response===undefined?null:await response;
  }
  return {caches,stores,dispatchWait,navigate,
    setOnline:v=>{online=v},
    setNetworkResponse:v=>{networkResponse=v},
    stats:()=>({claimed,networkCalls})};
}

const h=harness();
await h.dispatchWait('install');
const names=await h.caches.keys();
assert.equal(names.length,1);
assert(names[0].startsWith(CACHE_PREFIX));
const cache=await h.caches.open(names[0]);
const cached=await cache.match(ENTRY);
assert.equal(sha(Buffer.from(await cached.arrayBuffer())),expected);
checked.push('install-only-exact-pinned-app-shell');

await h.caches.open('unrelated-private-store');
await h.caches.open('nexus-app-shell-old');
await h.dispatchWait('activate');
const afterActivate=await h.caches.keys();
assert.deepEqual(afterActivate.sort(),[names[0],'unrelated-private-store'].sort());
assert.equal(h.stats().claimed,1);
checked.push('activation-deletes-only-old-app-shell-cache');

h.setOnline(false);
let response=await h.navigate();
assert.equal(response.status,200);
assert.equal(sha(Buffer.from(await response.arrayBuffer())),expected);
checked.push('offline-navigation-uses-verified-cached-shell');

assert.equal(await h.navigate(ORIGIN+'/v1/requests'),null);
assert.equal(await h.navigate(ORIGIN+'/?token=private'),null);
assert.equal(await h.navigate('https://untrusted.example/'),null);
assert.equal(await h.navigate(ENTRY,'POST'),null);
assert.equal(await h.navigate(ENTRY,'GET','cors'),null);
checked.push('worker-does-not-intercept-apis-external-or-nonnavigation');

const corrupt=Buffer.from(html);
corrupt[corrupt.length-128]^=1;
assert.equal(corrupt.length,html.length);
await cache.put(ENTRY,basicResponse(corrupt));
response=await h.navigate();
assert.equal(response.status,503);
assert((await response.text()).includes('offline app shell is unavailable'));
checked.push('same-sized-tampered-cached-html-is-rejected-offline');

await cache.put(ENTRY,basicResponse(html,{mime:'application/octet-stream'}));
assert.equal((await h.navigate()).status,503);
await cache.put(ENTRY,basicResponse(html,{redirected:true}));
assert.equal((await h.navigate()).status,503);
await cache.put(ENTRY,basicResponse(html,{status:404}));
assert.equal((await h.navigate()).status,503);
checked.push('cached-mime-redirect-and-status-fail-closed');

await cache.put(ENTRY,basicResponse(html));
h.setOnline(true);
h.setNetworkResponse(basicResponse(corrupt));
response=await h.navigate();
assert.equal(response.status,200);
assert.equal(sha(Buffer.from(await response.arrayBuffer())),expected);
checked.push('invalid-online-response-does-not-override-exact-cached-shell');

h.setNetworkResponse(basicResponse(html));
response=await h.navigate();
assert.equal(response.status,200);
assert.equal(sha(Buffer.from(await response.arrayBuffer())),expected);
checked.push('reviewed-online-response-is-accepted');

const refused=harness(basicResponse(corrupt));
await assert.rejects(refused.dispatchWait('install'),/unsafe-or-stale-published-app/);
assert.deepEqual(await refused.caches.keys(),[]);
checked.push('unreviewed-install-never-creates-app-cache');

assert.equal(checked.length,9);
process.stdout.write(JSON.stringify({schema:'nexus.pilot-12.worker-negative.v1',
  status:'PASS',checks:checked,source_sha256:expected,
  disposable_vm_only:true,real_chromium:false,public_https_tested:false,
  production_mutation:false,private_data_used:false,authority:'none'})+'\n');
