#!/usr/bin/env python3
"""Create a self-contained native Android offline Work Mode asset and receipt.

This builder never contacts GitHub Pages, Android phones, cloud APIs or Railway.
An APK is produced only by scripts/build-stage25-apk.sh from these exact bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STAGE23=ROOT/"scripts"/"build-mobile-work-pwa.py"
SCRIPT="NEXUS_NATIVE_EXPORT"
APP_ORIGIN="https://appassets.androidplatform.net/nexus/index.html"
BRIDGE= """async function download(blob,name){
 if(!window.NEXUS_NATIVE_EXPORT||typeof window.NEXUS_NATIVE_EXPORT.save!=='function')throw Error('native-export-unavailable');
 if(!blob||blob.size>6*1024*1024)throw Error('native-export-too-large');
 const bytes=new Uint8Array(await blob.arrayBuffer());let encoded='';
 for(let n=0;n<bytes.length;n+=8192){
   encoded+=String.fromCharCode(...bytes.subarray(n,n+8192));
 }
 window.NEXUS_NATIVE_EXPORT.save(name,btoa(encoded));
}"""
ORIGINAL_DOWNLOAD="function download(blob,name){const u=URL.createObjectURL(blob),a=node('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}"
NATIVE_NOTICE="""<section id="native-android" aria-label="NEXUS offline Android test edition">
<strong>NEXUS Native Android · نسخه آزمایشی آفلاین</strong>
<p>This APK has no Internet permission. All project work remains on the device.
Select Save to protect the encrypted vault and Export backup to choose an
independent encrypted document outside the app. Do not store irreplaceable
private data in this experimental APK. This test build cannot be upgraded
without a future stable signing key; uninstalling clears local app data.</p>
<p lang="fa" dir="rtl">برنامه بدون مجوز اینترنت اجرا می‌شود. برای حفظ اطلاعات
ذخیرهٔ رمزنگاری‌شده و پشتیبان مستقل بگیرید. این نسخه آزمایشی است و حذف
آن داده‌های ذخیره‌شدهٔ داخلی را از بین می‌برد.</p></section>"""


class Blocked(ValueError):
    pass


def replace_exact(source: str, old: str, new: str, name: str) -> str:
    if source.count(old)!=1:
        raise Blocked("unexpected-"+name)
    return source.replace(old,new)


def stage23():
    spec=importlib.util.spec_from_file_location("nexus_stage23_native",STAGE23)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compile_html(stage23_page: bytes | None=None) -> bytes:
    base=stage23()
    original=base.assemble_html(base.portable_source()) if stage23_page is None else stage23_page
    if len(original)>100000:
        raise Blocked("oversize-upstream")
    page=original.decode("utf8")
    page=replace_exact(page,base.MOBILE_SECTION,NATIVE_NOTICE,"native-section")
    page=replace_exact(page,base.MOBILE_SCRIPT,"","native-no-service-worker")
    page=replace_exact(page,ORIGINAL_DOWNLOAD,BRIDGE,"native-saf-export")
    page=replace_exact(page,'<link rel="manifest" href="./manifest.json">',"","native-no-manifest")
    page=replace_exact(page,"worker-src 'self'; ","","native-no-worker")
    page=replace_exact(page,"manifest-src 'self'; ","","native-no-manifest-csp")
    page=replace_exact(page,"img-src 'self'; ","","native-no-external-image")
    if any(x in page for x in (
        "navigator.serviceWorker", "fetch(", "XMLHttpRequest", "https://api",
        "URL.createObjectURL", "http-equiv=\"refresh\"",
        'id="mobile-prepare"', 'id="mobile-remove"',
        '<iframe', '<form action=')):
        raise Blocked("unexpected-network-or-mobile-PWA-handler")
    if page.count("NEXUS_NATIVE_EXPORT.save(")!=1:
        raise Blocked("native-bridge-missing-or-duplicated")
    if "connect-src 'none'" not in page or "frame-src 'none'" not in page:
        raise Blocked("CSP-network-boundary")
    if "indexedDB.open('nexus-private-work-mode-mobile-v23',1)" not in page:
        raise Blocked("encrypted-store-not-compatible")
    return page.encode("utf8")


def produce(page: bytes | None=None) -> dict[str, bytes]:
    html=compile_html(page)
    icon=(ROOT/"public/icons/nexus-192.png").read_bytes()
    if icon[:8]!=b"\x89PNG\r\n\x1a\n" or len(icon)>100000:
        raise Blocked("missing-nexus-icon")
    receipt={
        "schema":"nexus.stage25.offline-android-preview.v1",
        "status":"BUILD_INPUT_NOT_SIGNED_OR_DEVICE_TESTED",
        "native_origin":APP_ORIGIN,
        "assets":{
            "nexus/index.html":{
                "sha256":hashlib.sha256(html).hexdigest(),
                "bytes":len(html)
            },
            "mipmap-nodpi/ic_launcher.png":{
                "sha256":hashlib.sha256(icon).hexdigest(),
                "bytes":len(icon)
            }
        },
        "internet_permission":False,
        "storage_permission":False,
        "third_party_dependencies":False,
        "native_webview_same_origin":True,
        "export_requires_android_document_picker":True,
        "upgrade_signing_key_persistent":False,
        "android_hardware_tested":False,
        "original_Railway_data_restored":False,
        "production_release":False,
        "pages_enabled":False,
    }
    return {"nexus/index.html":html,
            "mipmap-nodpi/ic_launcher.png":icon,
            "nexus-stage25-input-integrity.json":
                (json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode()}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--check",action="store_true")
    opts=parser.parse_args()
    try:
        for key,raw in produce().items():
            path=opts.out/key
            if opts.check:
                if path.read_bytes()!=raw:
                    raise Blocked("artifact-drift-"+key)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
        print("PASS: Stage25 offline WebView assets, source CSP, native export"
              if opts.check else "BUILT: Stage25 offline WebView assets")
        return 0
    except (Blocked,OSError,UnicodeError) as exc:
        print("BLOCKED: "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
