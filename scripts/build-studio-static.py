#!/usr/bin/env python3
"""Deterministically package Studio for an isolated static origin; no provider secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from studio_assets import MAX_ASSET_BYTES, OFFLINE_DEVICE_ASSETS, PUBLIC_ASSETS

ROOT = Path(__file__).resolve().parents[1]
PANEL = '''<details id="studio-install-card">
<summary><span class="studio-en">Install or use offline</span><span class="studio-fa" lang="fa" dir="rtl">نصب یا استفادهٔ آفلاین</span></summary>
<div class="studio-install-content">
<p class="studio-en">Open the same Studio on the web or from your home screen. Projects and encrypted saves stay in your browser profile.</p>
<p class="studio-fa" lang="fa" dir="rtl">همین استودیو را از وب یا صفحهٔ اصلی گوشی باز کن. پروژه‌ها و ذخیره‌های رمزگذاری‌شده در پروفایل مرورگرت می‌مانند.</p>
<button id="studio-offline"><span class="studio-en">Prepare offline use</span><span class="studio-fa">آماده‌سازی آفلاین</span></button>
<button id="studio-install" hidden><span class="studio-en">Install app</span><span class="studio-fa">نصب برنامه</span></button>
<button id="studio-remove-offline" class="secondary"><span class="studio-en">Remove offline copy</span><span class="studio-fa">حذف نسخهٔ آفلاین</span></button>
<p class="help studio-en">If the install button is unavailable, use Chrome’s menu on Android or Safari’s Share → Add to Home Screen on iPhone. Offline preparation keeps the app code. Save your projects separately.</p>
<p class="help studio-fa" lang="fa" dir="rtl">اگر دکمهٔ نصب ظاهر نشد، در اندروید از منوی Chrome و در آیفون از گزینهٔ Share ← Add to Home Screen در Safari استفاده کن. آماده‌سازی آفلاین کد برنامه را نگه می‌دارد. پروژه‌ها را جدا ذخیره کن.</p>
<p id="studio-offline-state" role="status" aria-live="polite"></p>
<p id="studio-install-state" role="status" aria-live="polite"></p>
<a href="#studio-privacy"><span class="studio-en">Privacy policy</span><span class="studio-fa">سیاست حریم خصوصی</span></a>
</div></details>'''
PRIVACY = '''<section class="card" id="studio-privacy">
<div class="studio-en"><h2>NEXUS Studio privacy policy</h2>
<p>Studio runs in your browser, including when you install it. It requires no Studio account. Chats, drafts, source files, audio and analysis stay on your device during local use. Saving a project creates an encrypted archive in your browser profile. Exporting a backup or other file creates a copy at the location you choose.</p>
<p>The website host receives connection and request information, such as your IP address, when you load the site. If you request public research, the selected provider receives the approved query. If you approve an online model request, the configured gateway and its model provider process the reviewed content under their own policies. An optional on-device model download contacts its file host, then performs inference on your device. Browser speech and operating-system features are subject to your device and provider settings.</p>
<p>Use Private archive to erase the browser archive. Remove offline copy clears app code, and the device model panel can remove its downloaded model. You can also clear this site’s data in browser settings. Delete any exported copies separately. For privacy questions, contact the maintainer through the <a href="https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues" target="_blank" rel="noopener noreferrer">NEXUS issue tracker</a> without sharing private content.</p></div>
<div class="studio-fa" lang="fa" dir="rtl"><h2>سیاست حریم خصوصی نکسوس استودیو</h2>
<p>استودیو در مرورگر اجرا می‌شود، حتی وقتی آن را نصب می‌کنی. برای استفاده به حساب نکسوس نیاز نداری. در استفادهٔ محلی، گفتگوها، پیش‌نویس‌ها، فایل‌ها، صدا و تحلیل روی دستگاه می‌مانند. ذخیرهٔ پروژه یک آرشیو رمزگذاری‌شده در پروفایل مرورگر می‌سازد. با خروجی گرفتن، یک کپی در محل انتخابی خودت ایجاد می‌شود.</p>
<p>با باز کردن سایت، میزبان اطلاعات اتصال و درخواست، مانند IP، را دریافت می‌کند. در پژوهش عمومی، ارائه‌دهندهٔ انتخابی عبارت تأییدشده را دریافت می‌کند. اگر درخواست مدل آنلاین را تأیید کنی، درگاه انتخابی و ارائه‌دهندهٔ مدل محتوای بازبینی‌شده را طبق سیاست خود پردازش می‌کنند. مدل اختیاری روی دستگاه ابتدا از میزبان فایل دانلود می‌شود و سپس روی دستگاه اجرا می‌شود. امکانات گفتاری مرورگر تابع تنظیمات دستگاه و ارائه‌دهنده‌اند.</p>
<p>از بخش آرشیو خصوصی می‌توانی آرشیو مرورگر را پاک کنی. حذف نسخهٔ آفلاین، کد برنامه را پاک می‌کند. پنل مدل روی دستگاه امکان حذف فایل مدل را دارد. داده‌های سایت را می‌توانی از تنظیمات مرورگر هم پاک کنی. فایل‌های خروجی را جداگانه حذف کن. برای پرسش‌های حریم خصوصی در <a href="https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues" target="_blank" rel="noopener noreferrer">صفحهٔ مسائل نکسوس</a> پیام بگذار و اطلاعات خصوصی را در آن وارد نکن.</p></div>
</section>'''
BOOTSTRAP = r'''
(()=>{'use strict';
const $=id=>document.getElementById(id),base=new URL('./',location.href),prefix='nexus-studio-shell-v1-';
const text=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const install=$('studio-install'),installState=$('studio-install-state');
let installPrompt=null;
window.addEventListener('beforeinstallprompt',event=>{
 event.preventDefault();
 installPrompt=event;
 install.hidden=false;
});
window.addEventListener('appinstalled',()=>{
 installPrompt=null;
 install.hidden=true;
 installState.textContent=text('NEXUS Studio is installed.','نکسوس استودیو نصب شد.');
});
install.onclick=async()=>{
 const prompt=installPrompt;
 if(!prompt)return;
 installPrompt=null;
 install.hidden=true;
 try{await prompt.prompt();await prompt.userChoice}
 catch{installState.textContent=text('Use your browser menu to install.','برای نصب از منوی مرورگر استفاده کن.')}
};
const modelClick=$('check-model').onclick;
$('check-model').onclick=function(event){if($('model-engine')?.value!=='device'&&!$('gateway').value.trim()){$('model-status').textContent=text('No model hosted here. Local guide is available.','اینجا مدلی میزبانی نمی‌شود؛ راهنمای محلی در دسترس است.');return}return modelClick.call(this,event)};
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
WORKER = r'''/* Reviewed public Studio application code only; model bytes use a separate opt-in cache. */
'use strict';
const EXPECTED_SHA256='__DIGEST__';
const PREFIX='nexus-studio-shell-v1-',CACHE=PREFIX+'__PACKAGE_ID__';
const ENTRY=new URL('./',self.location.href).href;
const HTML={url:ENTRY,bytes:__INDEX_BYTES__,sha256:EXPECTED_SHA256,kind:'html'};
const CODE=__CODE_ASSETS__.map(a=>({...a,url:new URL(a.path,ENTRY).href}));
const NETWORK_DEADLINE_MS=8000;
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
 if(response?.body)void response.body.cancel().catch(()=>{});
 return null;
}
async function cacheShell(){
 const assets=[HTML,...CODE];
 const responses=await Promise.all(assets.map(asset=>fetchVerified(
  asset.url,asset,{cache:'no-store',credentials:'omit',redirect:'error'}
 )));
 if(responses.some(response=>!response)){
  for(const response of responses)if(response?.body)void response.body.cancel().catch(()=>{});
  throw Error('studio-integrity-mismatch');
 }
 const cache=await caches.open(CACHE);
 for(const [index,asset] of assets.entries())await cache.put(asset.url,responses[index]);
}
self.addEventListener('install',event=>event.waitUntil((async()=>{await cacheShell();await self.skipWaiting()})()));
self.addEventListener('message',event=>{if(event.data?.type!=='refresh-public-shell'||!event.ports[0])return;event.waitUntil(cacheShell().then(()=>event.ports[0].postMessage({ok:true}),()=>event.ports[0].postMessage({ok:false})))});
self.addEventListener('activate',event=>event.waitUntil((async()=>{await Promise.all((await caches.keys()).filter(n=>n.startsWith(PREFIX)&&n!==CACHE).map(n=>caches.delete(n)));await self.clients.claim()})()));
self.addEventListener('fetch',event=>{
 const request=event.request,url=new URL(request.url),entry=new URL(ENTRY);
 if(request.method!=='GET'||url.origin!==entry.origin||url.search)return;
 const asset=CODE.find(a=>a.url===url.href)||(request.mode==='navigate'&&[entry.pathname,entry.pathname+'index.html'].includes(url.pathname)?HTML:null);if(!asset)return;
 event.respondWith((async()=>{const online=await fetchVerified(request,asset);if(online)return online;const cache=await caches.open(CACHE),response=await cache.match(asset.url);try{if(await verified(response,asset))return response}catch{}if(response?.body)void response.body.cancel().catch(()=>{});return new Response('Studio offline code is unavailable. Reconnect and retry.',{status:503,headers:{'content-type':'text/plain; charset=utf-8','cache-control':'no-store'}})})());
});
'''


def artifacts():
    subprocess.run([sys.executable, str(ROOT/'scripts/build-studio.py'), '--check'], check=True)
    subprocess.run([sys.executable, str(ROOT/'scripts/build-device-model.py'), '--check'], check=True)
    source=(ROOT/'web/studio.html').read_text()
    source=source.replace("script-src 'unsafe-inline'", "script-src 'self' blob: 'unsafe-inline' 'wasm-unsafe-eval'")
    source=source.replace("worker-src blob:", "worker-src 'self' blob:").replace("img-src 'none'", "img-src 'self'; manifest-src 'self'")
    source=source.replace('<title>', '<link rel="manifest" href="./manifest.json"><meta name="theme-color" content="#185e48"><title>',1)
    source=source.replace('</style>', '.studio-fa{display:none}html[lang="fa"] .studio-en{display:none}html[lang="fa"] .studio-fa{display:revert}</style>',1)
    source=source.replace('</header>','</header>'+PANEL,1)
    source=source.replace('</main>',PRIVACY+'</main>',1)
    source=source.replace('value="2048"></details>', 'value="2048">'+(ROOT/'web/device/device-panel.html').read_text()+'</details>',1)
    source=source.replace('<label for="gateway"', '<label for="model-engine"><span class="studio-en">Model engine</span><span class="studio-fa">موتور مدل</span></label><select id="model-engine"><option value="gateway">Remote gateway / درگاه سرور</option><option value="device">On-device small model / مدل کوچک روی دستگاه</option></select><label for="gateway"',1)
    source=source.replace('</body>','<script>'+BOOTSTRAP+'</script><script type="module" src="./device/device-ui.js"></script></body>',1)
    html=source.encode()
    manifest={"id":"./", "name":"NEXUS Studio", "short_name":"NEXUS", "start_url":"./", "scope":"./", "display":"standalone", "lang":"en", "dir":"ltr", "background_color":"#f1f5f3", "theme_color":"#185e48", "icons":[{"src":f"./icons/nexus-{size}.png","sizes":f"{size}x{size}","type":"image/png","purpose":"any"} for size in (192,512)]}
    code = []
    for name in OFFLINE_DEVICE_ASSETS:
        content = (ROOT / 'public/studio' / name).read_bytes()
        code.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'kind':'json' if name.endswith('.json') else 'javascript'})
    # A worker-only change needs a fresh cache, so a failed update cannot write to the active worker's cache.
    package = hashlib.sha256(WORKER.encode() + html + json.dumps(code,sort_keys=True).encode()).hexdigest()[:16]
    worker = WORKER.replace('__DIGEST__',hashlib.sha256(html).hexdigest()).replace('__INDEX_BYTES__',str(len(html))).replace('__CODE_ASSETS__',json.dumps(code,separators=(',',':'))).replace('__PACKAGE_ID__',package)
    outputs = {'index.html':html, 'service-worker.js':worker.encode(), 'manifest.json':(json.dumps(manifest,indent=2)+'\n').encode(), **{f'icons/nexus-{size}.png':(ROOT/f'public/icons/nexus-{size}.png').read_bytes() for size in (192,512)}}
    for name in PUBLIC_ASSETS:
        size = len(outputs[name]) if name in outputs else (ROOT / 'public/studio' / name).stat().st_size
        if not 0 < size <= MAX_ASSET_BYTES:
            raise SystemExit(f'Static Studio asset exceeds shared size boundary: {name}')
    return outputs


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
