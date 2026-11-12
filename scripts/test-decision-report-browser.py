#!/usr/bin/env python3
"""Disposable real-browser acceptance: readable report never mutates a workspace."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
// Legacy behavior witnesses explicitly select Persian; English default has its own witness.
window.addEventListener('DOMContentLoaded',()=>{
 const language=document.getElementById('ui-language');
 if(language){language.value='fa';language.dispatchEvent(new Event('change',{bubbles:true}));}
},{once:true});
window.addEventListener('load', async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const tick=()=>new Promise(r=>setTimeout(r,50));
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const submit=id=>$(id).dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 let consent=true,confirms=0,prints=0,downloads=[],network=0;
 window.confirm=()=>{confirms++;return consent};
 window.print=()=>{prints++};
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 const nativeCreate=URL.createObjectURL;
 URL.createObjectURL=blob=>{downloads.push(blob);return nativeCreate(blob)};
 HTMLAnchorElement.prototype.click=function(){};
 const exportState=async()=>{const n=downloads.length;$('export').click();
  if(downloads.length!==n+1)throw Error('state-capture-failed');return await downloads.at(-1).text()};
 try{
  assert($('report-build').disabled&&$('report-download').disabled&&$('decision-report').hidden,'empty-workspace-cannot-report');
  fill('question','پرسش ساختگی <img src=x onerror=alert(1)>');fill('goal','هدف ساختگی');submit('ask-form');
  const before=await exportState();
  fill('decision','تصمیم ثبت‌نشده نباید صادر شود');fill('export-passphrase','never-include-this-test-secret');
  $('report-build').click();
  const text=$('decision-report').textContent;
  assert(text.includes('پرسش ساختگی')&&text.includes('هدف ساختگی')&&text.includes('هیچ تصمیم انسانی ثبت نشده'),'report-keeps-human-judgment-absent');
  assert(!text.includes('تصمیم ثبت‌نشده')&&!text.includes('never-include-this-test-secret'),'drafts-and-passwords-excluded');
  assert(!$('decision-report').querySelector('img')&&text.includes('<img'),'report-user-content-is-inert-text');
  assert(text.includes('شاهدی ثبت نشده')&&text.includes('گزینه‌ای ثبت نشده'),'missing-information-visible');
  assert(await exportState()===before,'building-report-preserves-workspace-and-audit');
  const count=downloads.length;consent=false;$('report-download').click();$('report-print').click();
  assert(downloads.length===count&&prints===0,'cancelled-plaintext-export-and-print-have-no-effect');
  consent=true;$('report-download').click();
  assert(downloads.at(-1).type==='text/plain;charset=utf-8'&&await downloads.at(-1).text()===text,'explicit-text-download-matches-preview');
  $('report-print').click();assert(prints===1&&confirms>=4,'print-requires-explicit-confirmation');
  $('report-hide').click();
  assert($('decision-report').hidden&&$('decision-report').textContent===''&&$('report-download').disabled,'hide-clears-report-only');
  assert(await exportState()===before,'report-actions-preserve-serialized-workspace');
  $('report-build').click();fill('claim','شاهد ساختگی');$('origin').value='external_evidence';fill('source','synthetic-source-id');$('uncertainty').value='high';submit('claim-form');
  assert($('decision-report').hidden&&$('report-print').disabled&&$('report-download').disabled,'committed-change-invalidates-stale-report');
  fill('option','گزینه ساختگی');fill('consequences','پیامد ساختگی');submit('option-form');
  fill('decision','تصمیم انسانی ساختگی');fill('rationale','دلیل ساختگی');submit('decision-form');
  const after=await exportState();$('report-build').click();
  const final=$('decision-report').textContent;
  assert(final.includes('synthetic-source-id')&&final.includes('عدم‌قطعیت: زیاد')&&final.includes('گزینه ساختگی')&&final.includes('پیامد ساختگی'),'sources-uncertainty-options-and-consequences-retained');
  assert(final.includes('تصمیم انسانی ساختگی')&&final.includes('دلیل ساختگی')&&final.includes('بدون رتبه‌بندی'),'only-explicit-human-decision-in-report');
  assert(await exportState()===after,'completed-report-preserves-workspace-and-audit');
  $('new').click();assert($('decision-report').hidden&&$('report-build').disabled,'new-workspace-clears-old-report');
  assert(network===0,'report-causes-no-network');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,authority:'none',synthetic_only:true,network_requests:network,production_verified:false});
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
    with tempfile.TemporaryDirectory(prefix='nexus-report-') as td:
        page=Path(td)/'index.html';page.write_text(page_html)
        for layout,dimensions in [('narrow','500,980'),('wide','1280,980')]:
            result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/layout),dimensions,'60000','30000'],capture_output=True,text=True,timeout=130)
            if result.returncode:
                raise RuntimeError('private-browser-did-not-complete')
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))!=17:
                raise RuntimeError('decision-report-rejected: '+str(report.get('reason','check-count')))
            assert (layout=='narrow')==(report['width']<=760)
            reports.append({'layout':layout,**report})
    print(json.dumps({'schema':'nexus.pilot-13.decision-report-witness.v1','status':'PASS','reports':reports,'authority':'none','real_user_tested':False}))

if __name__=='__main__':
    main()
