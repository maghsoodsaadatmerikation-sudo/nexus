#!/usr/bin/env python3
"""Build a self-contained, integrity-pinned, opt-in mobile PWA from Stage 22.

This creates STATIC assets only. It never configures hosting, deploys, logs in,
reads user workspaces, or changes any Railway/Render production data.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "build-work-mode-portable.py"
ICON_PATHS = ("icons/nexus-192.png", "icons/nexus-512.png")
ASSETS = ("index.html", "manifest.json", *ICON_PATHS, ".nojekyll")
RECEIPT = "nexus-stage23-integrity.json"
BASE_CSP = "connect-src 'none'; base-uri 'none'"
PWA_CSP = "connect-src 'none'; worker-src 'self'; manifest-src 'self'; img-src 'self'; base-uri 'none'"
ARCHIVE_BEFORE = "indexedDB.open('nexus-private-work-mode',1)"
ARCHIVE_AFTER = "indexedDB.open('nexus-private-work-mode-mobile-v23',1)"
NAV = "<nav>Standalone, locally operated · مستقل و بدون سرور</nav>"

MOBILE_SECTION = """<section id="mobile-pwa" aria-label="Installable offline companion"
 style="border:2px solid #14675a">
<strong>Installable mobile Work Mode · نسخه قابل نصب</strong>
<p>On trusted HTTPS, choose Prepare offline once, then use your browser's
Install app / Add to Home Screen option. No account or subscription.
Only four public app-shell files are cached; no work, notes, files,
passwords or archive keys enter CacheStorage.</p>
<p lang="fa" dir="rtl">روی یک نشانی HTTPS معتبر، گزینهٔ آماده‌سازی آفلاین
را بزنید؛ سپس از منوی مرورگر برنامه را نصب کنید. اطلاعات پروژه
فقط به انتخاب شما و به‌صورت رمزنگاری‌شده ذخیره می‌شود.</p>
<div class="tools">
<button type="button" id="mobile-prepare">Prepare offline · آماده‌سازی آفلاین</button>
<button type="button" id="mobile-install" hidden>Install app · نصب برنامه</button>
<button type="button" id="mobile-remove">Remove offline shell · حذف نسخه آفلاین</button>
</div>
<p id="mobile-state" class="help" role="status" aria-live="polite">
Not prepared. Hosting requires HTTPS or localhost.</p>
</section>"""

MOBILE_SCRIPT = r"""
<script>
(function(){
'use strict';
const byId=id=>document.getElementById(id);
const status=message=>{byId('mobile-state').textContent=message};
const root=()=>new URL('./',window.location.href);
const script=()=>new URL('service-worker.js',root()).href;
const eligible=()=>window.isSecureContext && !!navigator.serviceWorker &&
 (location.protocol==='https:' ||
 (location.protocol==='http:' &&
 ['127.0.0.1','localhost'].includes(location.hostname)));
let installEvent=null;
window.addEventListener('beforeinstallprompt',event=>{
  event.preventDefault();installEvent=event;byId('mobile-install').hidden=false;
});
window.addEventListener('appinstalled',()=>{
  installEvent=null;byId('mobile-install').hidden=true;
  status('Installed on this device / نصب انجام شد');
});
byId('mobile-prepare').addEventListener('click',async()=>{
  if(!eligible()){status('Blocked: use trusted HTTPS or localhost / نشانی امن لازم است');return}
  const btn=byId('mobile-prepare');btn.disabled=true;
  status('Checking reviewed app files / در حال بررسی فایل‌ها');
  try{
    const reg=await navigator.serviceWorker.register(script(),{scope:root().pathname});
    await navigator.serviceWorker.ready;
    if(reg.scope!==root().href || !reg.active ||
       reg.active.scriptURL!==script())throw Error('registration');
    status('Offline shell prepared. Use your browser install menu. '
       +'Encrypted projects are separate / آمادهٔ استفاده آفلاین');
  }catch{
    status('Offline preparation failed. No install claim / آماده‌سازی ناموفق');
  }finally{btn.disabled=false}
});
byId('mobile-install').addEventListener('click',async()=>{
  const prompt=installEvent;installEvent=null;
  byId('mobile-install').hidden=true;
  if(!prompt)return;
  try{await prompt.prompt();await prompt.userChoice}
  catch{status('Use your browser install menu / از منوی مرورگر نصب کنید')}
});
byId('mobile-remove').addEventListener('click',async()=>{
  if(!eligible() ||
     !window.confirm('Remove only NEXUS mobile app-shell cache and registration? '
       +'Encrypted project data and downloaded files remain unchanged?'))return;
  const btn=byId('mobile-remove');btn.disabled=true;
  try{
    const reg=await navigator.serviceWorker.getRegistration(root().href);
    if(reg&&reg.scope===root().href && reg.active?.scriptURL===script())
      await reg.unregister();
    const keys=await caches.keys();
    for(const key of keys)
      if(key.startsWith('nexus-stage23-shell-'))await caches.delete(key);
    status('Offline shell removed; encrypted archive was not erased / حذف شد');
  }catch{
    status('Removal could not be verified / حذف تأیید نشد');
  }finally{btn.disabled=false}
});
})();
</script>
"""

SW = r"""/* NEXUS Stage 23 mobile app shell: immutable public bytes, no private data. */
'use strict';
const PINS=__ASSET_PIN_OBJECT__;
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
"""


class Blocked(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Blocked(reason)


def replace_once(source, old, new, label):
    require(source.count(old) == 1, "unexpected-" + label)
    return source.replace(old, new)


def portable_source():
    spec = importlib.util.spec_from_file_location("nexus_stage22_builder", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assemble(module.PAGE.read_text(), module.CORE.read_text())


def assemble_html(portable):
    require(type(portable) is bytes and 10000 < len(portable) <= 80000,
            "invalid-portable-source")
    page = portable.decode("utf-8", errors="strict")
    require("fetch(" not in page and "connect-src 'none'" in page,
            "portable-must-be-network-disabled")
    page = replace_once(page, BASE_CSP, PWA_CSP, "csp")
    page = replace_once(page, "</head>",
      '<link rel="manifest" href="./manifest.json">'
      '<meta name="theme-color" content="#14675a"></head>', "head")
    page = replace_once(page, ARCHIVE_BEFORE, ARCHIVE_AFTER, "independent-vault")
    page = replace_once(page, NAV, MOBILE_SECTION + NAV, "offline-navigation")
    page = replace_once(page, "</body>", MOBILE_SCRIPT + "</body>", "body")
    require(page.count("<script>") == 3 and page.count("</script>") == 3,
            "unexpected-active-scripts")
    require("fetch(" not in page and "connect-src 'none'" in page and
            "worker-src 'self'" in page and
            page.count("navigator.serviceWorker.register(") == 1 and
            page.count("id=\"mobile-prepare\"") == 1,
            "unexpected-network-or-service-worker")
    require(len(page.encode("utf-8")) <= 100000,"oversized-mobile-html")
    return page.encode("utf-8")


def manifest():
    return (json.dumps({
        "name": "NEXUS — Private Work Mode",
        "short_name": "NEXUS Work",
        "description": "Evidence-aware human-controlled project work, offline.",
        "lang": "en", "dir": "ltr",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#f1f6f5", "theme_color": "#14675a",
        "icons": [
            {"src": "icons/nexus-192.png", "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": "icons/nexus-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "any"}
        ]
    }, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def png(data, size):
    require(data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) <= 100000,
            "invalid-icon")
    require(struct.unpack(">II", data[16:24]) == (size, size),
            "invalid-icon-dimensions")
    return data


def produce(portable=None, icon_bytes=None):
    page = portable_source() if portable is None else portable
    html = assemble_html(page)
    files = {"index.html": html, "manifest.json": manifest(),
             ".nojekyll": b""}
    if icon_bytes is None:
        icon_bytes = {path: (ROOT / "public" / path).read_bytes()
                      for path in ICON_PATHS}
    for size, path in ((192,ICON_PATHS[0]),(512,ICON_PATHS[1])):
        files[path] = png(icon_bytes[path],size)
    pins = {key: {"sha": hashlib.sha256(files[key]).hexdigest(),
                  "bytes": len(files[key])}
            for key in ("index.html","manifest.json", *ICON_PATHS)}
    worker = SW.replace("__ASSET_PIN_OBJECT__",json.dumps(pins, sort_keys=True,
                                                          separators=(',',':')))
    require(worker.count("__ASSET_PIN_OBJECT__") == 0 and
            worker.count("self.addEventListener('fetch'") == 1,
            "worker-generation-error")
    files["service-worker.js"] = worker.encode("utf-8")
    receipt = {
        "schema":"nexus.stage23.mobile-pwa.v1",
        "status":"STATIC_ARTIFACT_NOT_HOSTED",
        "assets": {name:{"sha256":hashlib.sha256(value).hexdigest(),
                         "bytes":len(value)}
                   for name,value in sorted(files.items())},
        "source_portable_sha256":hashlib.sha256(page).hexdigest(),
        "requires_host":"HTTPS_or_localhost",
        "uses_network_only_for":"four_public_pinned_static_assets",
        "private_api_calls":False, "background_worker_registration":False,
        "browser_storage":"opt_in_AES_GCM_separate_mobile_namespace",
        "actual_mobile_tested":False,
        "public_deployment_proven":False,
        "railway_original_volume_restored":False,
        "release_seal":False, "authority":"human"
    }
    files[RECEIPT]=(json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode()
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        files = produce()
        for relative, raw in files.items():
            path = args.out / relative
            if args.check:
                require(path.read_bytes() == raw,"artifact-mismatch-"+relative)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
        print("NEXUS STAGE23 PWA: PASS" if args.check else "NEXUS STAGE23 PWA: BUILT")
    except (OSError, UnicodeError, Blocked) as exc:
        print("NEXUS STAGE23 PWA: BLOCKED (" + str(exc) + ")",file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
