#!/usr/bin/env python3
"""Real Chromium regression of the privacy-only on-device self-test.

Runs isolated file:// test HTML; no user profile, no live device identifiers,
no network, no production services or credentials.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "static_preview", ROOT / "scripts/prepare-portable-pwa-preview.py")
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)

WITNESS = r"""
const output=document.createElement('pre');
output.id='nexus-browser-result';output.hidden=true;document.body.append(output);
(async()=>{
 let requests=0, captured=null;
 const expectedKeys=['secure','worker_api','cache_api','crypto_api','files_api',
   'worker_active','cached_shell_valid','standalone_display'];
 const assert=(ok,msg)=>{if(!ok)throw Error(msg)};
 const delay=ms=>new Promise(r=>setTimeout(r,ms));
 const timeout=Date.now()+12000;
 window.fetch=()=>{requests++;throw Error('network-forbidden')};
 window.XMLHttpRequest=class{constructor(){requests++;throw Error('network-forbidden')}};
 const realObjectURL=URL.createObjectURL.bind(URL);
 URL.createObjectURL=blob=>{captured=blob;return realObjectURL(blob)};
 try{
   assert(document.querySelector('meta[http-equiv="Content-Security-Policy"]')
     .content.includes("connect-src 'none'"),'no-csp');
   assert(!!window.__nexusDeviceReadiness,'missing-test-contract');
   assert(document.getElementById('export').disabled,'unsafe-export-before-check');
   assert(!document.getElementById('state').textContent,'implicit-check-before-consent');
   assert(!navigator.serviceWorker?.getRegistration ||
     !window.__nexusAutoRegistration,'unrequested-registration');
   document.getElementById('run').click();
   while(document.getElementById('export').disabled && Date.now()<timeout)
     await delay(50);
   assert(!document.getElementById('export').disabled,'check-did-not-finish');
   assert(document.querySelectorAll('#results>div').length===8,'missing-browser-checks');
   const API=window.__nexusDeviceReadiness;
   const automatic=await API.checks();
   const unselected=API.report(automatic);
   assert(unselected.schema==='nexus.device-readiness.self-report.v1','wrong-report-schema');
   assert(Object.keys(unselected.automatic).join(',')===expectedKeys.join(','),
     'unexpected-auto-report-fields');
   assert(unselected.independent_android_hardware_verification===false &&
      unselected.private_information_collected===false &&
      unselected.sent_to_server===false &&
      unselected.production_recovery_verified===false &&
      unselected.release_authorized===false &&
      unselected.authority==='none','unsafe-report-authority');
   assert(Object.values(unselected.owner_self_attestation).every(v=>v===false),
     'invented-owner-claims');
   assert(unselected.automatic.worker_active===false &&
      unselected.automatic.cached_shell_valid===false,'invented-offline-install');
   document.getElementById('language').value='fa';
   document.getElementById('language').dispatchEvent(new Event('change'));
   assert(document.documentElement.dir==='rtl'&&
       document.getElementById('run').textContent.includes('بررسی‌ها'),
       'persian-translation-incomplete');
   for(const id of ['installed','airplane','backup','android'])
     document.getElementById(id).checked=true;
   document.getElementById('export').click();
   for(let i=0;!captured&&i<100;i++)await delay(30);
   assert(captured&&captured.type==='application/json','missing-private-export');
   const contents=await captured.text();
   const exported=JSON.parse(contents);
   assert(JSON.stringify(exported)===JSON.stringify(API.report(automatic)),
     'download-differs-from-current-consent');
   assert(Object.values(exported.owner_self_attestation).every(v=>v===true),
     'missing-explicit-self-report');
   assert(!/userAgent|geolocation|ip_address|location_href|screen_width|timestamp|hostname|device_id|email/i.test(contents),
     'identifying-data-in-export');
   assert(requests===0,'unexpected-network-request');
   const remaining=JSON.stringify({status:'PASS',checks:11,
      zero_network_requests:requests===0,
      personal_identifiers_exported:false,
      real_android_hardware_tested:false,
      private_workspace_read:false,authority:'none'});
   output.textContent=remaining;
 }catch(e){
   output.textContent=JSON.stringify({status:'FAIL',
     reason:String(e?.message||'test-failed').replace(/[^A-Za-z0-9-]/g,'').slice(0,70)});
 }
})();
"""


def main():
    executable = next((shutil.which(name) for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if shutil.which(name)), None)
    if not executable:
        raise RuntimeError("real browser unavailable: no acceptance performed")
    original = preview.KIT.payloads()["index.html"]
    diagnostic = preview.device_check_page(original).decode("utf-8")
    assert diagnostic.count("</body>") == 1
    diagnostic = diagnostic.replace("</body>", "<script>" + WITNESS + "</script></body>")
    with tempfile.TemporaryDirectory(prefix="nexus-mobile-check-") as path:
        directory = Path(path)
        page = directory / "device-check.html"
        page.write_text(diagnostic, encoding="utf-8")
        command = ["node", str(ROOT / "scripts/workspace-browser-runner.mjs"),
                   executable, page.as_uri(), str(directory / "private-browser"),
                   "390,880", "60000", "30000"]
        result = subprocess.run(command, text=True, capture_output=True, timeout=140,
                                env={**os.environ, "NEXUS_CHROME_STARTUP_GRACE_MS": "30000"})
        if result.returncode:
            raise RuntimeError("private Chromium witness did not finish")
        outcome = json.loads(result.stdout)
        assert outcome["status"] == "PASS", outcome.get("reason", "browser-failed")
        assert outcome["checks"] == 11
        assert outcome["zero_network_requests"] is True
        assert outcome["personal_identifiers_exported"] is False
        assert outcome["real_android_hardware_tested"] is False
        assert outcome["private_workspace_read"] is False
        assert outcome["authority"] == "none"
    print(json.dumps({"schema":"nexus.mobile-device-readiness-browser.v1",
        **outcome, "production_verified":False, "authority":"none"},sort_keys=True))


if __name__ == "__main__":
    main()
