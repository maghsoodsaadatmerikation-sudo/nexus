#!/usr/bin/env python3
"""Disposable real-browser acceptance: English-first interface and inert locale packs preserve private work."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const tick=()=>new Promise(r=>setTimeout(r,30));
 const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await tick()}throw Error('language-wait-expired')};
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const choose=value=>{$('ui-language').value=value;$('ui-language').dispatchEvent(new Event('change',{bubbles:true}))};
 const submit=id=>$(id).dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 let blobs=[],network=0;window.confirm=()=>true;
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 const nativeCreate=URL.createObjectURL;URL.createObjectURL=b=>{blobs.push(b);return nativeCreate(b)};
 HTMLAnchorElement.prototype.click=function(){};
 const snapshot=async()=>{const n=blobs.length;$('export').click();if(blobs.length!==n+1)throw Error('snapshot-missing');return await blobs.at(-1).text()};
 const upload=async body=>{const dt=new DataTransfer();dt.items.add(new File([typeof body==='string'?body:JSON.stringify(body)],'locale.json',{type:'application/json'}));$('language-file').files=dt.files;$('language-file').dispatchEvent(new Event('change'));await wait(()=>!$('language-import').disabled&&$('language-file').value==='')};
 try{
  assert(document.documentElement.lang==='en'&&document.documentElement.dir==='ltr'&&$('ui-language').value==='en','english-is-explicit-default');
  assert(document.title.includes('Offline Decision Workshop')&&$('new').textContent==='New workspace','english-title-and-action-labels');
  assert($('question').placeholder.startsWith('What do I need')&&$('question').getAttribute('dir')==='auto','english-placeholder-and-auto-user-direction');
  // Deliberately identical to an interface string: it must never be translated.
  fill('question','Goal');fill('goal','هدف شخصی 中文');submit('ask-form');
  fill('claim','شاهد شخصی');fill('source','private://synthetic-evidence');submit('claim-form');
  const before=await snapshot();
  fill('decision','مسودة لم تُسجل');fill('rationale','Draft rationale');fill('export-passphrase','private-synthetic-test-passphrase');
  choose('fa');
  assert(document.documentElement.lang==='fa'&&document.documentElement.dir==='rtl'&&$('new').textContent==='کارگاه جدید','persian-switch-changes-interface-and-direction');
  assert($('question-view').textContent.includes('Goal')&&$('goal').value==='هدف شخصی 中文'&&$('claim').value==='','user-text-is-not-dictionary-translated');
  assert($('decision').value==='مسودة لم تُسجل'&&$('export-passphrase').value==='private-synthetic-test-passphrase'&&!$('draft-notice').hidden,'switch-preserves-drafts-and-password-fields');
  assert(await snapshot()===before,'switch-preserves-workspace-audit-and-authority');
  assert($('question-view').getAttribute('translate')==='no'&&$('question').getAttribute('translate')==='no','private-inputs-and-workspace-opt-out-of-browser-translation');
  $('report-build').click();const persian=$('decision-report').textContent;
  assert(persian.includes('گزارش اطلاعات ثبت‌شده')&&persian.includes('Goal')&&!persian.includes('مسودة'),'persian-report-localizes-labels-only');
  choose('en');
  assert($('decision-report').textContent.includes('Committed workspace report')&&$('decision-report').textContent.includes('Goal')&&$('decision').value==='مسودة لم تُسجل','open-report-relabels-without-changing-work');
  assert($('backup-proof-state').textContent==='No downloaded file has been tested yet.'&&$('new').textContent==='New workspace','roundtrip-restores-owned-labels-and-messages');
  const count=blobs.length;$('language-template').click();
  assert(blobs.length===count+1,'template-download-is-explicit');
  const template=JSON.parse(await blobs.at(-1).text());
  assert(template.schema==='nexus.ui-language.v1'&&Object.keys(template.messages).length===Number(document.querySelector('meta[name="nexus-ui-messages"]')?.content||277)&&template.source_sha256.length===64,'template-has-complete-version-bound-interface-catalog');
  const templateText=JSON.stringify(template);
  assert(!templateText.includes('private://synthetic-evidence')&&!templateText.includes('private-synthetic-test-passphrase')&&!templateText.includes('هدف شخصی'),'template-never-includes-private-workspace-or-password');
  const bads=[];
  const missing=structuredClone(template);delete missing.messages.m000;bads.push(missing);
  const stale=structuredClone(template);stale.source_sha256='0'.repeat(64);bads.push(stale);
  const reserved=structuredClone(template);reserved.locale='en';bads.push(reserved);
  const invalid=structuredClone(template);invalid.locale='not_a_locale';bads.push(invalid);
  const extra=structuredClone(template);extra.messages.__unexpected='untrusted';bads.push(extra);
  for(const bad of bads){await upload(bad);if(document.documentElement.lang!=='en'||!$('language-state').textContent.includes('rejected'))throw Error('invalid-pack-was-accepted')}
  assert(true,'missing-stale-reserved-invalid-and-extra-key-packs-rejected');
  await upload('{invalid-json');
  assert(document.documentElement.lang==='en'&&$('language-state').textContent.includes('rejected'),'malformed-json-leaves-language-unchanged');
  const arabic=structuredClone(template);arabic.locale='ar';arabic.name='العربية (اختبار)';arabic.direction='rtl';
  for(const key of Object.keys(arabic.messages))arabic.messages[key]='اختبار '+arabic.messages[key];
  arabic.messages.m001='<img src=x onerror=alert(1)> اختبار';await upload(arabic);
  assert(document.documentElement.lang==='ar'&&document.documentElement.dir==='rtl'&&$('ui-language').value==='ar','complete-arabic-test-pack-loads-with-rtl');
  assert(document.querySelector('h1').textContent===arabic.messages.m001&&!document.querySelector('h1 img')&&!$('language-review').hidden,'custom-labels-are-inert-and-marked-unreviewed');
  assert(await snapshot()===before&&$('question-view').textContent.includes('Goal'),'custom-pack-cannot-change-workspace-data');
  const rare=structuredClone(template);rare.locale='und-x-example';rare.name='Any script — ᏣᎳᎩ';rare.direction='ltr';await upload(rare);
  assert(document.documentElement.lang==='und-x-example'&&document.documentElement.dir==='ltr','language-import-is-not-limited-to-a-fixed-language-list');
  choose('en');
  assert($('ui-language').value==='en'&&document.querySelector('h1').textContent==='Offline Decision Workshop'&&$('language-review').hidden,'english-remains-available-after-custom-packs');
  fill('vault-new-password','synthetic-language-vault-secret');fill('vault-new-confirm','synthetic-language-vault-secret');$('vault-enable').click();
  await wait(()=>localStorage.getItem('nexus.offline-pilot.local-encrypted.v1')!==null);
  const ciphertext=localStorage.getItem('nexus.offline-pilot.local-encrypted.v1');choose('fa');
  await new Promise(r=>setTimeout(r,400));
  assert(localStorage.getItem('nexus.offline-pilot.local-encrypted.v1')===ciphertext,'language-change-does-not-resave-or-modify-active-vault');
  $('vault-delete').click();choose('en');
  assert(localStorage.length===0&&network===0,'language-features-use-no-network-or-new-persistent-storage');
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
    with tempfile.TemporaryDirectory(prefix='nexus-language-') as td:
        page=Path(td)/'index.html';page.write_text(page_html)
        for layout,dimensions in [('narrow','500,980'),('wide','1280,980')]:
            result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/layout),dimensions,'60000','30000'],capture_output=True,text=True,timeout=130)
            if result.returncode:
                raise RuntimeError('private-browser-did-not-complete')
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))!=23:
                raise RuntimeError('ui-language-rejected: '+str(report.get('reason','check-count')))
            assert (layout=='narrow')==(report['width']<=760)
            reports.append({'layout':layout,**report})
    print(json.dumps({'schema':'nexus.pilot-15.ui-language-witness.v1','status':'PASS','reports':reports,'authority':'none','real_user_tested':False}))

if __name__=='__main__':
    main()
