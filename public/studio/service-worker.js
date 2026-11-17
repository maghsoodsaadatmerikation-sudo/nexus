/* Reviewed public Studio application code only; model bytes use a separate opt-in cache. */
'use strict';
const EXPECTED_SHA256='3e8c2e7651b352a70003176dcf8fa3de20f70a1b705dbf6e2a91b4adb4768544';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+'0f891d683c0431ec';
const ENTRY=new URL('./',self.location.href).href;
const HTML={url:ENTRY,bytes:306426,sha256:EXPECTED_SHA256,kind:'html'};
const CODE=[{"path":"device/device-engine.js","bytes":5332,"sha256":"f940daf5d81017506de5ca33b9f9e6a0c34a529b06ac0ae85bdd8e2082922aa0","kind":"javascript"},{"path":"device/device-worker.js","bytes":7863,"sha256":"828adf678dbb9f5f2d7ce5099afe4214dc4ff5db576d1f476ac76ca72bb632d2","kind":"javascript"},{"path":"device/device-ui.js","bytes":8683,"sha256":"e9af684e54d9d73c414875a95439f1cc19061f71bacf24d3034b4a88852e9be5","kind":"javascript"},{"path":"device/model-manifest.json","bytes":3196,"sha256":"36ad3068fa8f91b278f1ce0a2328701ec7cda5fa949e9c5b315b70b9f3fb6dc0","kind":"json"}].map(a=>({...a,url:new URL(a.path,ENTRY).href}));
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
