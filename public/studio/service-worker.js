/* Reviewed public Studio application code only; model bytes use a separate opt-in cache. */
'use strict';
const EXPECTED_SHA256='672e3f2917884e8385dd4acb02dd2f3f0b23cadfe3e9eb1d80b4fd3200c9b905';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+'b6fa061194b69251';
const ENTRY=new URL('./',self.location.href).href;
const HTML={url:ENTRY,bytes:581339,sha256:EXPECTED_SHA256,kind:'html'};
const CODE=[{"path":"device/device-engine.js","bytes":5332,"sha256":"aa7efe4d708f854ca35ff863edb602da7a9fb164d62e427c6521ddbd957e9175","kind":"javascript"},{"path":"device/device-worker.js","bytes":7878,"sha256":"cf094c6c64f3532e4271c9a0582f1dfbe592b966d9eff275896dd1f4c2e2f3a3","kind":"javascript"},{"path":"device/device-ui.js","bytes":8683,"sha256":"08343f58bb01d1f26d37f55e1d3842e7f2fd22a02b23f8cfa4b7b7a2583192cd","kind":"javascript"},{"path":"device/model-manifest.json","bytes":3211,"sha256":"5055f8d8bf248707d3765f4ffac516f9e7d23e98636c890c1f34c6f09f544974","kind":"json"},{"path":"pdf/studio-pdf.mjs","bytes":4866,"sha256":"d506e6a2cf1ff9f5ee7849b82d53483980d407af40f0eadba07faa13184a3552","kind":"javascript"},{"path":"pdf/pdf.min.mjs","bytes":474284,"sha256":"3a88402882cfa3e7e72c2c9b5149f52f0f88baf1c5b62aa11a41abdbc2072440","kind":"javascript"},{"path":"pdf/pdf.worker.min.mjs","bytes":1271915,"sha256":"1e64c8240e54735ec5913b37acd5134747799cb8c6bb3777c70adbc01232d2aa","kind":"javascript"}].map(a=>({...a,url:new URL(a.path,ENTRY).href}));
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
