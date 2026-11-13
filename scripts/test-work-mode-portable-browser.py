#!/usr/bin/env python3
"""Real Chromium file:// offline Work Mode witness with synthetic private data.

Loads the generated single HTML directly as a file, not from a local server.
No production identity, token, network provider, original file or human data.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "work_mode_portable_build", ROOT / "scripts" / "build-work-mode-portable.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

WITNESS = r"""
<script>
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id);
 const checks=[],uploads=[],saved=[];
 const check=(ok,key)=>{if(!ok)throw Error(key);checks.push(key)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{fill(id,value);$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const flag=(id,value)=>{$(id).checked=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let n=0;n<600;n++){if(fn())return;await new Promise(r=>setTimeout(r,10))}throw Error('timeout')};
 const idle=()=>wait(()=>!busy);
 const pass='synthetic-very-long-private-password';
 window.confirm=()=>true;
 window.fetch=(...args)=>{uploads.push(args);throw Error('prohibited-network')};
 const original=URL.createObjectURL,blobs=new Map();
 URL.createObjectURL=blob=>{const url=original(blob);blobs.set(url,blob);return url};
 HTMLAnchorElement.prototype.click=function(){if(this.download)saved.push({name:this.download,blob:blobs.get(this.href)})};
 try{
  check(location.protocol==='file:','genuine-local-file-not-hosted');
  check(isSecureContext&&!!crypto.subtle,'offline-webcrypto-secure-context');
  check($('portable-mode')!==null&&document.documentElement.lang==='en','honest-offline-banner-and-english-default');
  check(document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("connect-src 'none'"),'network-csp-deny');
  check(document.querySelectorAll('script[src]').length===0,'all-scripts-inline');
  check(document.querySelector('[data-k="assist"]').closest('section').hidden,'server-only-assistant-hidden');
  check(current===null&&!vault.unlocked&&uploads.length===0,'no-background-work-or-server-call');
  fill('title','PRIVATE_PROJECT_TITLE');fill('goal','PRIVATE_GOAL_FOR_HUMAN_REVIEW');
  fill('criteria','Human verified evidence');fill('steps','Check evidence\nDraft result');
  $('create').click();
  check(current?.tasks?.length===2&&current.tasks.every(t=>t.status==='todo'),'task-creation-no-autonomous-completion');
  const id=current.id;
  select('task-status','done');$('apply-task').click();
  check(current.tasks[0].status==='todo','unreviewed-completion-rejected');
  fill('evidence','PERSON_REVIEWED_SYNTHETIC_EVIDENCE');
  select('task-status','done');flag('reviewed',true);$('apply-task').click();
  check(current.tasks[0].status==='done'&&current.tasks[0].reviewed,'human-evidence-completion');
  fill('note','PRIVATE_SYNTHETIC_NOTE');$('add-note').click();
  check(current.notes.length===1&&current.notes[0].origin==='human','private-note-created');
  const transfer=new DataTransfer();
  transfer.items.add(new File(['PRIVATE_SYNTHETIC_FILE'],'private.txt',{type:'text/plain'}));
  $('file').files=transfer.files;$('file').dispatchEvent(new Event('change'));
  await wait(()=>current.files.length===1);
  check(current.files[0].size===22&&uploads.length===0,'private-file-without-upload');
  fill('pass',pass);fill('repeat',pass);$('vault-create').click();await idle();
  check(vault.unlocked&&vault.list().length===0,'opt-in-archive-creation');
  $('save').click();await idle();
  check(vault.list().length===1&&!dirty,'explicit-encrypted-save');
  const raw=JSON.stringify(await vault.store.read());
  for(const secret of ['PRIVATE_PROJECT_TITLE','PRIVATE_GOAL_FOR_HUMAN_REVIEW','PRIVATE_SYNTHETIC_NOTE','PRIVATE_SYNTHETIC_FILE',pass])check(!raw.includes(secret),'encrypted-no-plaintext-'+secret.slice(0,9));
  $('backup').click();await idle();
  check(saved.some(x=>x.name==='nexus-work-mode.encrypted.json'),'portable-encrypted-backup-download');
  const backup=saved.find(x=>x.name==='nexus-work-mode.encrypted.json');
  const body=await backup.blob.text();
  check(JSON.parse(body).schema==='nexus.work-mode.v1'&&!body.includes('PRIVATE_PROJECT_TITLE'),'encrypted-backup-format-and-privacy');
  $('lock').click();check(!vault.unlocked&&current===null,'lock-clears-private-RAM-work');
  fill('pass',pass);$('unlock').click();await idle();
  check(vault.unlocked&&vault.list().length===1,'encrypted-offline-reopen');
  select('projects',id);$('open').click();
  check(current?.id===id&&current.files.length===1&&current.tasks[0].status==='done','verified-project-resume-with-file');
  select('language','fa');
  check(document.documentElement.dir==='rtl','persian-RTL-interface');
  check(uploads.length===0&&localStorage.length===0&&sessionStorage.length===0,'zero-app-network-and-plaintext-browser-storage');
  $('nexus-browser-result').textContent=JSON.stringify({
   status:'PASS',schema:'nexus.stage22.portable-chromium.v1',
   checks,width:innerWidth,server_requests:uploads.length,
   archive:'AES-GCM',authority:'human',production_tested:false
  });
 }catch(error){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message)});
 }
});
</script>
"""


def main():
    page = M.assemble(M.PAGE.read_text(), M.CORE.read_text()).decode()
    assert page.count("</body>") == 1
    page = page.replace("</body>", '<pre id="nexus-browser-result" hidden></pre>' + WITNESS + "</body>")
    chrome = next((shutil.which(name) for name in
                   ("google-chrome", "google-chrome-stable", "chromium")
                   if shutil.which(name)), None)
    if chrome is None:
        raise RuntimeError("real-chromium-required")
    reports = []
    with tempfile.TemporaryDirectory(prefix="nexus-stage22-file-witness-") as temp:
        root = Path(temp)
        path = root / "nexus-work-mode-portable.html"
        path.write_text(page)
        for device, dimensions in (("narrow", "500,980"), ("wide", "1280,980")):
            proc = subprocess.run([
                "node", str(ROOT / "scripts" / "workspace-browser-runner.mjs"),
                chrome, path.as_uri(), str(root / device), dimensions,
                "60000", "30000"
            ], capture_output=True, text=True, timeout=115)
            if proc.returncode:
                raise RuntimeError("private-browser-process-" + device +
                                   "-failure: " + proc.stderr[-600:])
            response = json.loads(proc.stdout)
            if response.get("status") != "PASS":
                raise RuntimeError("portable-" + device + "-" + str(response.get("reason")))
            if len(response.get("checks", [])) < 19 or response.get("server_requests") != 0:
                raise RuntimeError("insufficient-offline-acceptance")
            reports.append(response)
    print(json.dumps({
        "status": "PASS", "schema": "nexus.stage22.portable-real-file.v1",
        "reports": reports, "network_calls": 0, "authority": "human",
        "android_hardware_tested": False, "production_deployed": False
    }))


if __name__ == "__main__":
    main()
