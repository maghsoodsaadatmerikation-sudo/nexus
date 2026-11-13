/* Public Studio code only. Registration requires an explicit button click. */
'use strict';
const EXPECTED_SHA256='47281c15338d055766c66ddf76cac19a7770e31eb7b15a57ef4782f87cb85e15';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+EXPECTED_SHA256.slice(0,16);
const ENTRY=new URL('./',self.location.href).href;
async function verified(response){
 if(!response||response.status!==200||response.redirected||response.type!=='basic'||!/^text\/html(?:\s*;|$)/i.test(response.headers.get('content-type')||''))return false;
 const bytes=await response.clone().arrayBuffer();if(bytes.byteLength<5000||bytes.byteLength>500000)return false;
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 return digest===EXPECTED_SHA256;
}
self.addEventListener('install',event=>event.waitUntil((async()=>{
 const response=await fetch(ENTRY,{cache:'no-store',credentials:'omit',redirect:'error'});
 if(!await verified(response))throw Error('studio-integrity-mismatch');
 const cache=await caches.open(CACHE);await cache.put(ENTRY,response);await self.skipWaiting();
})()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 await Promise.all((await caches.keys()).filter(n=>n.startsWith(PREFIX)&&n!==CACHE).map(n=>caches.delete(n)));
 await self.clients.claim();
})()));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url),entry=new URL(ENTRY);
 if(request.method!=='GET'||request.mode!=='navigate'||url.origin!==entry.origin||url.search||![entry.pathname,entry.pathname+'index.html'].includes(url.pathname))return;
 event.respondWith((async()=>{
  try{const response=await fetch(request);if(await verified(response))return response}catch{}
  const cache=await caches.open(CACHE),response=await cache.match(ENTRY);
  if(await verified(response))return response;
  return new Response('Studio offline code is unavailable. Reconnect and retry.',{status:503,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}});
 })());
});
