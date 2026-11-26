/* Reviewed public Studio application code only; model bytes use a separate opt-in cache. */
'use strict';
const EXPECTED_SHA256='5cb5e4b16835f04aac65bcb160c43e00003a5edad828e5771717c7302277c200';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+'e7100bc077587697';
const ENTRY=new URL('./',self.location.href).href;
const HTML={url:ENTRY,bytes:636075,sha256:EXPECTED_SHA256,kind:'html'};
const CODE=[{"path":"device/device-engine.js","bytes":5670,"sha256":"87a04ac4fcb4aa382e1b774763e9b1a26ce400b9a9fcd88814214888029d0d90","kind":"javascript"},{"path":"device/device-worker.js","bytes":7863,"sha256":"a2b396fb0fe7a4411ba8a4e678b6c4f79bfc0eed673e1712f445baa8a9c60e85","kind":"javascript"},{"path":"device/device-ui.js","bytes":9622,"sha256":"6bc87a47e87754a3599b8ea7e16a094f98d1482f6117e231993c08e494901821","kind":"javascript"},{"path":"device/model-manifest.json","bytes":3196,"sha256":"49353c4a16f7912fd4251b6d048923fd41d2819f9fab2faf5bfbccab9a7e3983","kind":"json"},{"path":"pdf/studio-pdf.mjs","bytes":5774,"sha256":"edd140b80a539175bc424df4638fffcfebc021e0ee0673fcf5b2ce185e6e1c4c","kind":"javascript"},{"path":"pdf/pdf.min.mjs","bytes":474284,"sha256":"3a88402882cfa3e7e72c2c9b5149f52f0f88baf1c5b62aa11a41abdbc2072440","kind":"javascript"},{"path":"pdf/pdf.worker.min.mjs","bytes":1271915,"sha256":"1e64c8240e54735ec5913b37acd5134747799cb8c6bb3777c70adbc01232d2aa","kind":"javascript"},{"path":"vendor/astronomy-2.1.19.min.js","bytes":116424,"sha256":"f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6","kind":"javascript"},{"path":"studio-orchestra.js","bytes":27347,"sha256":"2a24fed79f74ef7a9e818e4b565895559bfc885dbfc554a63a7b1659ccec772e","kind":"javascript"}].map(a=>({...a,url:new URL(a.path,ENTRY).href}));
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
 event.respondWith((async()=>{
  // Code is immutable within this digest-bound package. Avoid network access
  // for verified cached modules; keep HTML navigation network-first.
  async function fromCache(){try{const cache=await caches.open(CACHE),response=await cache.match(asset.url);return await verified(response,asset)?response:null}catch{return null}}
  async function fromNetwork(){try{const response=await fetch(request);return await verified(response,asset)?response:null}catch{return null}}
  const response=asset===HTML?await fromNetwork()||await fromCache():await fromCache()||await fromNetwork();
  return response||new Response('Studio offline code is unavailable. Reconnect and retry.',{status:503,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}});
 })());
});
