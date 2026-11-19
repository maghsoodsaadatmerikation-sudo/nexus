/* Reviewed public Studio application code only; model bytes use a separate opt-in cache. */
'use strict';
const EXPECTED_SHA256='d630b4bc46e2b7cc3eddcd38c2efb5bd428632924e20ea0d8f67e646f8833307';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+'75acea543bb567ab';
const ENTRY=new URL('./',self.location.href).href;
const HTML={url:ENTRY,bytes:468016,sha256:EXPECTED_SHA256,kind:'html'};
const CODE=[{"path":"device/device-engine.js","bytes":5332,"sha256":"aa7efe4d708f854ca35ff863edb602da7a9fb164d62e427c6521ddbd957e9175","kind":"javascript"},{"path":"device/device-ui.js","bytes":8683,"sha256":"08343f58bb01d1f26d37f55e1d3842e7f2fd22a02b23f8cfa4b7b7a2583192cd","kind":"javascript"},{"path":"device/device-worker.js","bytes":7863,"sha256":"a2b396fb0fe7a4411ba8a4e678b6c4f79bfc0eed673e1712f445baa8a9c60e85","kind":"javascript"},{"path":"device/model-manifest.json","bytes":3196,"sha256":"49353c4a16f7912fd4251b6d048923fd41d2819f9fab2faf5bfbccab9a7e3983","kind":"json"}].map(a=>({...a,url:new URL(a.path,ENTRY).href}));
const ASSETS=[HTML,...CODE],NETWORK_DEADLINE_MS=8000;
let preparing=null,removing=null,discarded=false;
async function verified(response,asset=HTML){
 if(!response||response.status!==200||response.redirected||response.type!=='basic'||!response.body)return false;
 const mime=(response.headers.get('content-type')||'').split(';')[0].trim().toLowerCase();
 if(asset.kind==='html'?mime!=='text/html':asset.kind==='json'?!['application/json','application/manifest+json'].includes(mime):!['text/javascript','application/javascript'].includes(mime))return false;
 const reader=response.clone().body.getReader(),bytes=new Uint8Array(asset.bytes);
 let size=0,finished=false;
 try{
  while(true){
   const {done,value}=await reader.read();
   if(done){finished=true;break}
   if(value.byteLength>bytes.byteLength-size)return false;
   bytes.set(value,size);size+=value.byteLength;
  }
  if(size!==asset.bytes)return false;
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
  return digest===asset.sha256;
 }finally{
  // A cloned stream shares its source. Awaiting cancellation here can wait for the other branch.
  if(!finished)void reader.cancel().catch(()=>{});
  reader.releaseLock();
 }
}
async function fetchVerified(request,asset,options={}){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),NETWORK_DEADLINE_MS);
 let response;
 try{
  response=await fetch(request,{...options,signal:controller.signal});
  if(await verified(response,asset))return response;
 }catch{}finally{clearTimeout(timer)}
 controller.abort();
 releaseBody(response);
 return null;
}
function releaseBody(response){if(response?.body)void response.body.cancel().catch(()=>{})}
async function cachedAsset(asset){
 let response;
 try{
  response=await caches.match(asset.url,{cacheName:CACHE});
  if(await verified(response,asset))return response;
 }catch{}
 releaseBody(response);
 return null;
}
async function hasShell(){
 for(const asset of ASSETS){
  const response=await cachedAsset(asset);
  if(!response)return false;
  releaseBody(response);
 }
 return true;
}
async function cacheShell(){
 const responses=await Promise.all(ASSETS.map(asset=>fetchVerified(
  asset.url,asset,{cache:'no-store',credentials:'omit',redirect:'error'}
 )));
 if(discarded||responses.some(response=>!response)){
  responses.forEach(releaseBody);
  throw Error('studio-integrity-mismatch');
 }
 const cache=await caches.open(CACHE);
 for(const [index,asset] of ASSETS.entries())await cache.put(asset.url,responses[index]);
}
async function ensureShell(){
 if(discarded)throw Error('studio-offline-disabled');
 if(!preparing)preparing=(async()=>{if(!await hasShell())await cacheShell()})().finally(()=>{preparing=null});
 await preparing;
 if(discarded)throw Error('studio-offline-disabled');
}
async function discardShell(){
 discarded=true;
 if(!removing)removing=(async()=>{
  if(preparing)await preparing.catch(()=>{});
  await caches.delete(CACHE);
 })().finally(()=>{removing=null});
 await removing;
}
async function refreshShell(reopen){
 if(removing)throw Error('studio-removal-in-progress');
 if(reopen)discarded=false;
 await ensureShell();
}
self.addEventListener('install',event=>event.waitUntil((async()=>{await ensureShell();await self.skipWaiting()})()));
self.addEventListener('message',event=>{
 const port=event.ports[0];
 if(!port)return;
 const type=event.data?.type;
 const action=type==='refresh-public-shell'?()=>refreshShell(event.data.reopen===true):type==='discard-public-shell'?discardShell:null;
 if(action)event.waitUntil(action().then(()=>port.postMessage({ok:true}),()=>port.postMessage({ok:false})));
});
self.addEventListener('activate',event=>event.waitUntil((async()=>{await Promise.all((await caches.keys()).filter(n=>n.startsWith(PREFIX)&&n!==CACHE).map(n=>caches.delete(n)));await self.clients.claim()})()));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url),entry=new URL(ENTRY);
 if(discarded||request.method!=='GET'||url.origin!==entry.origin)return;
 const isEntry=request.mode==='navigate'&&[entry.pathname,entry.pathname+'index.html'].includes(url.pathname);
 const asset=isEntry?HTML:!url.search?CODE.find(a=>a.url===url.href):null;
 if(!asset)return;
 event.respondWith((async()=>{
  const online=await fetchVerified(request,asset);
  if(online)return online;
  const cached=await cachedAsset(asset);
  if(cached)return cached;
  return new Response('Studio offline code is unavailable. Reconnect and retry.',{status:503,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}});
 })());
});
