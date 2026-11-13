/* NEXUS Stage 23 mobile app shell: immutable public bytes, no private data. */
'use strict';
const PINS={"icons/nexus-192.png":{"bytes":1185,"sha":"b6f466a5ca3e026ab56cd0e8b68a562ba38546b8f403d1d7c270e6bd673ddf14"},"icons/nexus-512.png":{"bytes":2114,"sha":"3f9e0f840461189f55b9732fa98215e5e5115492480ac48a7dc015aa13d1fc48"},"index.html":{"bytes":52153,"sha":"cf1940cee5cbf3f3ecdfd7248f2e02271d08106269a154f7f7df3266433d5287"},"manifest.json":{"bytes":574,"sha":"210914216e2e740d0d25ea1ae768effdf38dd11e07e1ba60a682e4338589285d"}};
const CACHE='nexus-stage23-shell-'+PINS['index.html'].sha.slice(0,20);
const BASE=new URL('./',self.location.href);
const ALLOWED=['index.html','manifest.json','icons/nexus-192.png','icons/nexus-512.png'];
function canonical(request){
  if(request.method!=='GET')return null;
  const url=new URL(request.url);
  if(url.origin!==BASE.origin||url.search||url.hash)return null;
  if(request.mode==='navigate'){
    if(url.pathname===BASE.pathname||url.pathname===BASE.pathname+'index.html')return 'index.html';
    return null;
  }
  for(const relative of ALLOWED)
    if(url.pathname===BASE.pathname+relative)return relative;
  return null;
}
async function verified(response,relative){
  if(!response||response.status!==200||response.redirected||response.type!=='basic')return false;
  const pin=PINS[relative];if(!pin)return false;
  const mime=(response.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase();
  const matches=relative==='index.html'?mime==='text/html':
    relative==='manifest.json'?(mime==='application/json'||mime==='application/manifest+json'):
    mime==='image/png';
  if(!matches)return false;
  const bytes=await response.clone().arrayBuffer();
  if(bytes.byteLength!==pin.bytes||bytes.byteLength>200000)return false;
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),
    x=>x.toString(16).padStart(2,'0')).join('');
  return digest===pin.sha;
}
self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    for(const relative of ALLOWED){
      const url=new URL(relative,BASE).href;
      const response=await fetch(new Request(url,{
        credentials:'omit',cache:'reload',mode:'same-origin',redirect:'error'
      }));
      if(!await verified(response,relative))throw Error('unreviewed-mobile-shell');
      await cache.put(url,response);
    }
    await self.skipWaiting();
  })());
});
self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    for(const key of await caches.keys())
      if(key.startsWith('nexus-stage23-shell-')&&key!==CACHE)await caches.delete(key);
    await self.clients.claim();
  })());
});
self.addEventListener('fetch',event=>{
  const relative=canonical(event.request);
  if(!relative)return;
  event.respondWith((async()=>{
    try{
      const response=await fetch(event.request);
      if(await verified(response,relative))return response;
    }catch{}
    const cache=await caches.open(CACHE);
    const fallback=await cache.match(new URL(relative,BASE).href);
    if(fallback&&await verified(fallback,relative))return fallback;
    return new Response('NEXUS reviewed offline shell unavailable.',{
      status:503,headers:{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'}
    });
  })());
});
