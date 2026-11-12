#!/usr/bin/env python3
"""Disposable real-browser acceptance: uncommitted input cannot be silently replaced."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const tick=()=>new Promise(r=>setTimeout(r,40));
 const wait=async fn=>{for(let i=0;i<250;i++){if(fn())return;await tick()}throw Error('bounded-wait-expired')};
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const submit=id=>$(id).dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 const pending=()=>!$('draft-notice').hidden;
 const leaving=()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented};
 let consent=true,prompts=0,blobs=[],network=0;
 window.confirm=()=>{prompts++;return consent};
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 const nativeCreate=URL.createObjectURL;
 URL.createObjectURL=b=>{blobs.push(b);return nativeCreate(b)};
 HTMLAnchorElement.prototype.click=function(){};
 const snapshot=async()=>{const n=blobs.length;$('export').click();if(blobs.length!==n+1)throw Error('export-missing');return await blobs.at(-1).text()};
 const fixture={schema:'nexus.offline-pilot.v1',authority:'none',storage:'memory_only',workspace:{id:'offline-synthetic-import',question:' imported question ',goal:'',constraints:['one,two'],values:[],claims:[],alternatives:[],judgment:null},events:[{sequence:1,kind:'question',at:'2026-11-12T00:00:00.000Z'}]};
 const upload=async()=>{const dt=new DataTransfer();dt.items.add(new File([JSON.stringify(fixture)],'synthetic.json',{type:'application/json'}));$('file').files=dt.files;$('file').dispatchEvent(new Event('change'));await wait(()=>$('file').value==='')};
 try{
  assert(!pending()&&!leaving(),'empty-workspace-has-no-draft-guard');
  fill('export-passphrase','password-only-not-a-draft');
  assert(!pending()&&!leaving(),'password-fields-never-count-as-workspace-drafts');
  fill('question','unsaved synthetic question');
  assert(pending()&&leaving()&&$('draft-state').textContent.includes('پرسش'),'uncommitted-question-has-visible-and-unload-guard');
  $('draft-focus').click();assert(document.activeElement===$('question'),'draft-shortcut-focuses-own-section');
  consent=false;const n=prompts;$('new').click();
  assert(prompts===n+1&&$('question').value==='unsaved synthetic question'&&pending(),'cancelled-new-preserves-uncommitted-first-question');
  $('load-demo').click();assert($('question').value==='unsaved synthetic question'&&!$('question-view').textContent.includes('ساختگی'),'cancelled-demo-preserves-first-draft');
  await upload();assert($('question').value==='unsaved synthetic question'&&pending(),'cancelled-file-import-preserves-first-draft');
  consent=true;await upload();
  assert($('question').value===fixture.workspace.question&&!pending()&&!leaving(),'confirmed-import-has-no-false-whitespace-or-comma-draft');
  const initial=await snapshot();
  fill('source','synthetic draft source');assert(pending()&&$('draft-state').textContent.includes('شواهد'),'source-only-draft-is-protected');
  fill('claim','committed synthetic claim');submit('claim-form');
  assert(!pending()&&!leaving(),'successful-claim-registration-clears-draft-guard');
  fill('option','draft alternative');fill('consequences','draft consequence');
  assert(pending()&&$('draft-state').textContent.includes('گزینه'),'alternative-draft-visible');
  submit('option-form');assert(!pending(),'registered-alternative-clears-draft-guard');
  fill('decision','not-yet-a-human-decision');fill('rationale','draft reasoning');
  const current=await snapshot();
  assert(JSON.parse(current).workspace.judgment===null&&!current.includes('not-yet-a-human-decision'),'drafts-never-become-judgment-or-exported-content');
  fill('export-passphrase','synthetic-export-passphrase');fill('confirm-passphrase','synthetic-export-passphrase');
  consent=false;const b=blobs.length;$('encrypt-export').click();await tick();
  assert(blobs.length===b&&$('decision').value==='not-yet-a-human-decision','cancelled-encrypted-export-keeps-draft-and-creates-no-file');
  consent=true;submit('decision-form');
  assert(!pending()&&!leaving(),'explicit-human-judgment-registration-clears-guard');
  // Retain a synthetic encrypted checkpoint, then test the async restore race.
  fill('vault-new-password','synthetic-vault-passphrase');fill('vault-new-confirm','synthetic-vault-passphrase');$('vault-enable').click();
  await wait(()=>localStorage.getItem('nexus.offline-pilot.local-encrypted.v1')!==null);
  $('vault-pause').click();$('new').click();
  fill('question','fresh draft before restore');fill('vault-open-password','synthetic-vault-passphrase');consent=false;
  $('vault-restore').click();await tick();
  assert($('question').value==='fresh draft before restore'&&!$('vault-restore').disabled,'cancelled-local-restore-preserves-first-draft');
  consent=true;fill('vault-open-password','synthetic-vault-passphrase');
  const nativeDerive=crypto.subtle.deriveKey.bind(crypto.subtle);let release;
  crypto.subtle.deriveKey=async(...args)=>{await new Promise(r=>release=r);return nativeDerive(...args)};
  $('vault-restore').click();await wait(()=>!!release);fill('question','new draft typed during decryption');release();
  await wait(()=>!$('vault-restore').disabled);crypto.subtle.deriveKey=nativeDerive;
  assert($('question').value==='new draft typed during decryption'&&$('status').textContent.includes('جایگزینی انجام نشد'),'decryption-race-cannot-overwrite-new-draft');
  fill('vault-open-password','synthetic-vault-passphrase');$('vault-restore').click();await wait(()=>!$('vault-restore').disabled);
  assert($('question').value===fixture.workspace.question&&!pending(),'confirmed-local-restore-clears-drafts-and-restores-committed-data');
  const restored=await snapshot();
  assert(JSON.parse(restored).workspace.judgment.decision==='not-yet-a-human-decision'&&JSON.parse(initial).workspace.judgment===null,'explicit-judgment-persists-without-retroactive-draft-authority');
  assert(network===0&&localStorage.length===1,'only-explicit-existing-encrypted-vault-is-stored');
  $('vault-delete').click();
  assert(localStorage.length===0,'explicit-vault-cleanup-leaves-no-draft-storage');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,network_requests:network,production_verified:false,authority:'none',synthetic_only:true});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e.message).replace(/[^a-z-]/g,'')})}
});
"""


def main():
    root = Path(__file__).resolve().parents[1]
    html = (root/'web/offline-pilot.html').read_text()
    assert "connect-src 'none'" in html and '@media print' in html
    browser = next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium') if shutil.which(n)),None)
    if not browser:
        raise RuntimeError('real-browser-required')
    page_html = html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    reports=[]
    with tempfile.TemporaryDirectory(prefix='nexus-draft-guard-') as td:
        page=Path(td)/'index.html';page.write_text(page_html)
        for layout,dimensions in [('narrow','500,980'),('wide','1280,980')]:
            result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/layout),dimensions,'60000','30000'],capture_output=True,text=True,timeout=130)
            if result.returncode:
                raise RuntimeError('private-browser-did-not-complete')
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))!=21:
                raise RuntimeError('draft-guard-rejected: '+str(report.get('reason','check-count')))
            assert (layout=='narrow')==(report['width']<=760)
            reports.append({'layout':layout,**report})
    print(json.dumps({'schema':'nexus.pilot-14.draft-guard-witness.v1','status':'PASS','reports':reports,'authority':'none','real_user_tested':False}))

if __name__=='__main__':
    main()
