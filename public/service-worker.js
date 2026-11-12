/* NEXUS Pilot 12 — installed, user-opt-in, read-only public app shell.
 * This worker never sees/stores workspace JSON or private user content.
 * It handles ONLY same-origin GET navigation to / or /index.html.
 * Immutable expected HTML hash is maintained by reviewed source promotion.
 */
'use strict';
const EXPECTED_SHA256='de96fa64d051babf64f712eae74d0a65cec5fdfe43d39e0a3bdf8daac7625c85';
const CACHE_NAME='nexus-app-shell-v12-'+EXPECTED_SHA256.slice(0,16);
const ENTRY=new URL('/',self.location.origin).href;
const MARKERS=["connect-src 'none'","nexus.offline-pilot.v1"];
async function verified(response){
  if(!response||response.status!==200||response.redirected||
     response.type!=='basic'||!/^text\/html(?:\s*;|$)/i.test(response.headers.get('Content-Type')||''))return false;
  const bytes=await response.clone().arrayBuffer();
  if(bytes.byteLength<5000||bytes.byteLength>300000)return false;
  const hex=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),
    b=>b.toString(16).padStart(2,'0')).join('');
  if(hex!==EXPECTED_SHA256)return false;
  const content=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
  return MARKERS.every(x=>content.includes(x));
}
self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    if(!/^[a-f0-9]{64}$/.test(EXPECTED_SHA256))throw Error('unsealed-app-source');
    const response=await fetch(new Request(ENTRY,{cache:'reload',credentials:'omit',mode:'same-origin'}));
    if(!await verified(response))throw Error('unsafe-or-stale-published-app');
    const c=await caches.open(CACHE_NAME);
    await c.put(ENTRY,response);
    await self.skipWaiting();
  })());
});
self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(x=>x.startsWith('nexus-app-shell-')&&x!==CACHE_NAME).map(x=>caches.delete(x)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET'||req.mode!=='navigate')return;
  const target=new URL(req.url);
  if(target.origin!==self.location.origin||!['/','/index.html'].includes(target.pathname)||target.search)return;
  event.respondWith((async()=>{
    try{
      const response=await fetch(req);
      if(await verified(response))return response;
    }catch{}
    const c=await caches.open(CACHE_NAME);
    const fallback=await c.match(ENTRY);
    if(fallback&&await verified(fallback))return fallback;
    return new Response('NEXUS offline app shell is unavailable. Reconnect and retry.',{
      status:503,headers:{'Content-Type':'text/plain; charset=utf-8','Cache-Control':'no-store'}});
  })());
});
