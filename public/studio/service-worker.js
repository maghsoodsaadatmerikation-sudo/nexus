/* Reviewed public Studio application code only; model bytes use a separate opt-in cache. */
'use strict';
const EXPECTED_SHA256='7121c2bd7fa8c365a6facd9bdcbc5b9685775d499f65b32923d3d5bb005bb139';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+'23442a11161efac2';
const ENTRY=new URL('./',self.location.href).href;
const HTML={url:ENTRY,bytes:272678,sha256:EXPECTED_SHA256,kind:'html'};
const CODE=[{"path":"device/device-engine.js","bytes":2860,"sha256":"6fb0d40efe36509dfc99cb60e0cac412c0375a6ca4c5af046ca75398219cd873","kind":"javascript"},{"path":"device/device-worker.js","bytes":6974,"sha256":"e1bbd32c2e857d4ed79ce640d15d1b93593fa5551d53b73a990dc07b8af4f550","kind":"javascript"},{"path":"device/device-ui.js","bytes":3860,"sha256":"fd02a4a50f35bd870c1f8aeb148fe1591f1d038289e85e003c5bdb2a9903dff6","kind":"javascript"},{"path":"device/model-manifest.json","bytes":2812,"sha256":"9978cf46b0ec2af8e537f0e1b2b7af2590b3162a227b4ac1e89b0739ac5d607e","kind":"json"}].map(a=>({...a,url:new URL(a.path,ENTRY).href}));
async function verified(response,asset=HTML){
 if(!response||response.status!==200||response.redirected||response.type!=='basic')return false;
 const mime=(response.headers.get('content-type')||'').split(';')[0].trim().toLowerCase();
 if(asset.kind==='html'?mime!=='text/html':asset.kind==='json'?!['application/json','application/manifest+json'].includes(mime):!['text/javascript','application/javascript'].includes(mime))return false;
 const bytes=await response.clone().arrayBuffer();if(bytes.byteLength!==asset.bytes)return false;
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');return digest===asset.sha256;
}
async function cacheShell(){
 const cache=await caches.open(CACHE);
 for(const asset of [HTML,...CODE]){const response=await fetch(asset.url,{cache:'no-store',credentials:'omit',redirect:'error'});if(!await verified(response,asset))throw Error('studio-integrity-mismatch');await cache.put(asset.url,response)}
}
self.addEventListener('install',event=>event.waitUntil((async()=>{await cacheShell();await self.skipWaiting()})()));
self.addEventListener('message',event=>{if(event.data?.type!=='refresh-public-shell'||!event.ports[0])return;event.waitUntil(cacheShell().then(()=>event.ports[0].postMessage({ok:true}),()=>event.ports[0].postMessage({ok:false})))});
self.addEventListener('activate',event=>event.waitUntil((async()=>{await Promise.all((await caches.keys()).filter(n=>n.startsWith(PREFIX)&&n!==CACHE).map(n=>caches.delete(n)));await self.clients.claim()})()));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url),entry=new URL(ENTRY);
 if(request.method!=='GET'||url.origin!==entry.origin||url.search)return;
 const asset=CODE.find(a=>a.url===url.href)||(request.mode==='navigate'&&[entry.pathname,entry.pathname+'index.html'].includes(url.pathname)?HTML:null);if(!asset)return;
 event.respondWith((async()=>{try{const response=await fetch(request);if(await verified(response,asset))return response}catch{}const cache=await caches.open(CACHE),response=await cache.match(asset.url);if(await verified(response,asset))return response;return new Response('Studio offline code is unavailable. Reconnect and retry.',{status:503,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}})})());
});
