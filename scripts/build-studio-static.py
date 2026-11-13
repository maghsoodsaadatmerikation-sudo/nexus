#!/usr/bin/env python3
"""Deterministically package Studio for an isolated static origin; no provider secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PANEL = '''<section class="card" id="studio-install-card">
<p class="studio-en">This static edition runs in your browser. The local guide is not a generative model. Saving your work is explicit and encrypted. A real model requires your separately configured gateway.</p>
<p class="studio-fa" lang="fa" dir="rtl">این نسخه در مرورگر اجرا می‌شود. راهنمای محلی مدل مولد نیست. ذخیرهٔ کار دستی و رمزگذاری‌شده است. پاسخ مدل واقعی به درگاه جداگانهٔ پیکربندی‌شده نیاز دارد.</p>
<button id="studio-offline"><span class="studio-en">Prepare offline use</span><span class="studio-fa">آماده‌سازی آفلاین</span></button>
<button id="studio-remove-offline" class="secondary"><span class="studio-en">Remove offline copy</span><span class="studio-fa">حذف نسخهٔ آفلاین</span></button>
<p class="help studio-en">After preparation, use your browser's Install app or Add to Home screen menu. Availability depends on your browser. Offline caching saves public app code only; save your session separately.</p>
<p class="help studio-fa" lang="fa" dir="rtl">پس از آماده‌سازی از منوی مرورگر «نصب برنامه» یا «افزودن به صفحهٔ اصلی» را انتخاب کن. این امکان به مرورگر بستگی دارد. کش آفلاین فقط کد عمومی برنامه را نگه می‌دارد؛ نشست را جدا ذخیره کن.</p>
<p id="studio-offline-state" role="status" aria-live="polite"></p></section>'''
BOOTSTRAP = r'''
(()=>{'use strict';
const $=id=>document.getElementById(id),base=new URL('./',location.href),prefix='nexus-studio-shell-v1-';
const text=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const modelClick=$('check-model').onclick;
$('check-model').onclick=function(event){if(!$('gateway').value.trim()){$('model-status').textContent=text('No model hosted here. Local guide is available.','اینجا مدلی میزبانی نمی‌شود؛ راهنمای محلی در دسترس است.');return}return modelClick.call(this,event)};
let changing=false;
async function change(fn){if(changing)return;changing=true;$('studio-offline').disabled=$('studio-remove-offline').disabled=true;try{if(!isSecureContext||!('serviceWorker'in navigator))throw Error('unsupported');await fn()}catch{$('studio-offline-state').textContent=text('Offline setup failed. Reconnect and try again in a supported browser.','آماده‌سازی آفلاین انجام نشد؛ با اتصال اینترنت و مرورگر پشتیبانی‌شده دوباره تلاش کن.')}finally{changing=false;$('studio-offline').disabled=$('studio-remove-offline').disabled=false}}
$('studio-offline').onclick=()=>change(async()=>{
 const registration=await navigator.serviceWorker.register(new URL('service-worker.js',base),{scope:base.href,updateViaCache:'none'});
 const limit=Date.now()+15000;while(registration.installing||registration.waiting||!registration.active||registration.active.state!=='activated'){if(Date.now()>limit)throw Error('activation-timeout');await new Promise(r=>setTimeout(r,100))}
 await new Promise((resolve,reject)=>{const channel=new MessageChannel(),timer=setTimeout(()=>{channel.port1.close();reject(Error('cache-refresh-timeout'))},10000);channel.port1.onmessage=event=>{clearTimeout(timer);channel.port1.close();event.data?.ok?resolve():reject(Error('cache-refresh-failed'))};registration.active.postMessage({type:'refresh-public-shell'},[channel.port2])});
 const names=(await caches.keys()).filter(n=>n.startsWith(prefix));let present=false;
 for(const name of names){const cache=await caches.open(name);if(await cache.match(base.href))present=true}
 if(!present)throw Error('missing-shell');
 $('studio-offline-state').textContent=text('Offline app code is ready. Save your session separately.','کد برنامه برای حالت آفلاین آماده است؛ نشست را جدا ذخیره کن.');
});
$('studio-remove-offline').onclick=()=>change(async()=>{
 const registration=await navigator.serviceWorker.getRegistration(base.href);
 if(registration&&registration.scope===base.href)await registration.unregister();
 await Promise.all((await caches.keys()).filter(n=>n.startsWith(prefix)).map(n=>caches.delete(n)));
 $('studio-offline-state').textContent=text('Offline copy removed. Your open session and encrypted archives were retained.','نسخهٔ آفلاین حذف شد؛ نشست باز و آرشیوهای رمزگذاری‌شده حفظ شدند.');
});
})();
'''
WORKER = r'''/* Public Studio code only. Registration requires an explicit button click. */
'use strict';
const EXPECTED_SHA256='__DIGEST__';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+EXPECTED_SHA256.slice(0,16);
const ENTRY=new URL('./',self.location.href).href;
async function verified(response){
 if(!response||response.status!==200||response.redirected||response.type!=='basic'||!/^text\/html(?:\s*;|$)/i.test(response.headers.get('content-type')||''))return false;
 const bytes=await response.clone().arrayBuffer();if(bytes.byteLength<5000||bytes.byteLength>500000)return false;
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
 return digest===EXPECTED_SHA256;
}
async function cacheShell(){
 const response=await fetch(ENTRY,{cache:'no-store',credentials:'omit',redirect:'error'});
 if(!await verified(response))throw Error('studio-integrity-mismatch');
 const cache=await caches.open(CACHE);await cache.put(ENTRY,response);
}
self.addEventListener('install',event=>event.waitUntil((async()=>{await cacheShell();await self.skipWaiting()})()));
self.addEventListener('message',event=>{
 if(event.data?.type!=='refresh-public-shell'||!event.ports[0])return;
 event.waitUntil(cacheShell().then(()=>event.ports[0].postMessage({ok:true}),()=>event.ports[0].postMessage({ok:false})));
});
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
'''


def artifacts():
    subprocess.run([sys.executable, str(ROOT/'scripts/build-studio.py'), '--check'], check=True)
    source=(ROOT/'web/studio.html').read_text()
    source=source.replace("worker-src blob:", "worker-src 'self' blob:").replace("img-src 'none'", "img-src 'self'; manifest-src 'self'")
    source=source.replace('<title>', '<link rel="manifest" href="./manifest.json"><meta name="theme-color" content="#185e48"><title>',1)
    source=source.replace('</style>', '.studio-fa{display:none}html[lang="fa"] .studio-en{display:none}html[lang="fa"] .studio-fa{display:revert}</style>',1)
    source=source.replace('<body><main>','<body><main>'+PANEL,1)
    source=source.replace('</body>','<script>'+BOOTSTRAP+'</script></body>',1)
    html=source.encode()
    manifest={"id":"./", "name":"NEXUS Studio", "short_name":"NEXUS", "start_url":"./", "scope":"./", "display":"standalone", "lang":"en", "dir":"ltr", "background_color":"#f1f5f3", "theme_color":"#185e48", "icons":[{"src":f"./icons/nexus-{size}.png","sizes":f"{size}x{size}","type":"image/png","purpose":"any"} for size in (192,512)]}
    return {'index.html':html, 'service-worker.js':WORKER.replace('__DIGEST__',hashlib.sha256(html).hexdigest()).encode(), 'manifest.json':(json.dumps(manifest,indent=2)+'\n').encode(), **{f'icons/nexus-{size}.png':(ROOT/f'public/icons/nexus-{size}.png').read_bytes() for size in (192,512)}}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for name,content in artifacts().items():
        path=ROOT/'public/studio'/name
        if args.check:
            if not path.is_file() or path.read_bytes()!=content:raise SystemExit('Static Studio asset is stale: '+name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    print('STATIC STUDIO PACKAGE: PASS')

if __name__=='__main__':main()
