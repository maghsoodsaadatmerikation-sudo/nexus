/* NEXUS Motion: PUBLIC CODE ONLY; no media, projects, archives or model weights. */
'use strict';
const PREFIX = 'nexus-motion-shell-v1-';
const CACHE = PREFIX + '__VERSION__';
const BASE = new URL('./', self.location.href);
const PUBLIC = /*STATIC_DESCRIPTOR__*/[];
const ENTRY = new URL('index.html', BASE).href;

function assetUrl(asset) { return new URL(asset.path, BASE).href; }
async function verified(response, asset) {
  if (!response || response.status !== 200 || response.redirected || response.type !== 'basic') return false;
  const mime = (response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
  const expected = asset.kind === 'html' ? ['text/html'] :
    asset.kind === 'javascript' ? ['application/javascript','text/javascript'] :
    asset.kind === 'json' ? ['application/json','application/manifest+json'] : ['image/png'];
  if (!expected.includes(mime)) return false;
  const data = await response.clone().arrayBuffer();
  if (data.byteLength !== asset.bytes) return false;
  const sum = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),
    item => item.toString(16).padStart(2,'0')).join('');
  return sum === asset.sha256;
}
async function rebuild() {
  const cache = await caches.open(CACHE);
  for (const asset of PUBLIC) {
    const url = assetUrl(asset);
    const response = await fetch(url,{cache:'no-store',credentials:'omit',redirect:'error'});
    if (!await verified(response,asset)) throw Error('motion-public-source-integrity-failed');
    await cache.put(url,response);
  }
}
self.addEventListener('install', event => event.waitUntil((async () => {
  await rebuild();
  await self.skipWaiting();
})()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  await Promise.all((await caches.keys()).filter(k => k.startsWith(PREFIX) && k !== CACHE).map(k=>caches.delete(k)));
  await self.clients.claim();
})()));
self.addEventListener('message', event => {
  if (event.data?.type !== 'refresh-motion-shell' || !event.ports?.[0]) return;
  event.waitUntil(rebuild().then(() => event.ports[0].postMessage({ok:true}),
    () => event.ports[0].postMessage({ok:false})));
});
self.addEventListener('fetch', event => {
  const request=event.request,url=new URL(request.url);
  if (request.method !== 'GET' || url.origin !== BASE.origin || url.search || url.hash) return;
  const isEntry=request.mode==='navigate' && [BASE.pathname,BASE.pathname+'index.html'].includes(url.pathname);
  const asset=isEntry ? PUBLIC.find(a=>a.path==='index.html') :
    PUBLIC.find(a=>assetUrl(a)===url.href);
  if (!asset) return;
  event.respondWith((async()=>{
    try {
      const live=await fetch(request);
      if (await verified(live,asset)) return live;
    } catch {}
    const cache=await caches.open(CACHE);
    const copy=await cache.match(assetUrl(asset));
    if (await verified(copy,asset)) return copy;
    return new Response('NEXUS Motion offline public files unavailable. Reconnect and prepare again.',{
      status:503,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}
    });
  })());
});
