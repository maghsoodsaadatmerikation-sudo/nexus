#!/usr/bin/env python3
"""Deterministically package Studio for an isolated static origin; no provider secrets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from studio_template_contract import replace_exact

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
'''


def render_public_shell(source: str, device_panel: str) -> bytes:
    """Assemble the public shell; refuse missing or duplicated integration slots."""
    source=replace_exact(source, "script-src 'unsafe-inline'", "script-src 'self' blob: 'unsafe-inline' 'wasm-unsafe-eval'")
    # Enable the public device worker in the page policy. The lab's srcdoc
    # keeps its independent opaque-origin, blob-only worker policy.
    source=replace_exact(source, "frame-src 'self' blob:; worker-src blob:",
                         "frame-src 'self' blob:; worker-src 'self' blob:")
    source=replace_exact(source, "img-src data:", "img-src 'self' data:; manifest-src 'self'")
    source=replace_exact(source, '<title>', '<link rel="manifest" href="./manifest.json"><link rel="icon" type="image/png" href="./icons/nexus-192.png"><link rel="apple-touch-icon" href="./icons/nexus-192.png"><meta property="og:image" content="https://nexus-studio-merikation.onrender.com/icons/nexus-512.png"><meta name="theme-color" content="#185e48"><title>')
    source=replace_exact(source, '</style>', '.studio-fa{display:none}html[lang="fa"] .studio-en{display:none}html[lang="fa"] .studio-fa{display:revert}</style>')
    source=replace_exact(source, '</header>', '</header>'+PANEL)
    source=replace_exact(source, '</main>', PRIVACY+'</main>')
    source=replace_exact(source, 'value="2048"></details>', 'value="2048">'+device_panel+'</details>')
    source=replace_exact(source, '<label for="gateway"', '<label for="model-engine"><span class="studio-en">Model engine</span><span class="studio-fa">موتور مدل</span></label><select id="model-engine"><option value="gateway">Remote gateway / درگاه سرور</option><option value="device">On-device small model / مدل کوچک روی دستگاه</option></select><label for="gateway"')
    source=replace_exact(source, '</body>', '<script>'+BOOTSTRAP+'</script><script type="module" src="./device/device-ui.js"></script></body>')
    return source.encode()


def artifacts():
    subprocess.run([sys.executable, str(ROOT/'scripts/build-studio.py'), '--check'], check=True)
    subprocess.run([sys.executable, str(ROOT/'scripts/build-device-model.py'), '--check'], check=True)
    html=render_public_shell(
        (ROOT/'web/studio.html').read_text(),
        (ROOT/'web/device/device-panel.html').read_text(),
    )
    manifest={"id":"./", "name":"NEXUS Studio", "short_name":"NEXUS", "start_url":"./", "scope":"./", "display":"standalone", "lang":"en", "dir":"ltr", "background_color":"#f1f5f3", "theme_color":"#185e48", "icons":[{"src":f"./icons/nexus-{size}.png","sizes":f"{size}x{size}","type":"image/png","purpose":"any"} for size in (192,512)]}
    code=[]
    for name in ['device-engine.js','device-worker.js','device-ui.js','model-manifest.json']:
        content=(ROOT/'public/studio/device'/name).read_bytes();code.append({'path':'device/'+name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'kind':'json' if name.endswith('.json') else 'javascript'})
    worker=replace_exact(WORKER, '__DIGEST__', hashlib.sha256(html).hexdigest())
    worker=replace_exact(worker, '__INDEX_BYTES__', str(len(html)))
    worker=replace_exact(worker, '__CODE_ASSETS__', json.dumps(code,separators=(',',':')))
    worker=replace_exact(worker, '__PACKAGE_ID__', hashlib.sha256(html+json.dumps(code,sort_keys=True).encode()).hexdigest()[:16])
    return {'index.html':html, 'service-worker.js':worker.encode(), 'manifest.json':(json.dumps(manifest,indent=2)+'\n').encode(), **{f'icons/nexus-{size}.png':(ROOT/f'public/icons/nexus-{size}.png').read_bytes() for size in (192,512)}}


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
