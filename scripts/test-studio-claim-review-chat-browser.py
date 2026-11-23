#!/usr/bin/env python3
"""Integrated NEXUS Studio claim-review action in disposable real Chromium."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const ok=(yes,label)=>{if(!yes)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const fingerprint='f'.repeat(64),token='github_pat_'+'A'.repeat(40);
 let discovery=0,sends=0,allRequests=0;
 window.confirm=()=>true;
 window.fetch=async(url,opts={})=>{
  allRequests++;
  const target=String(url);
  if(target.endsWith('/studio-api/status')){discovery++;return Response.json({
    configured:true,model:'synthetic-provider',provider_host:'fixture.invalid',
    configuration_id:fingerprint,reply_receipt_version:1,authority:'none'})}
  if(!target.endsWith('/studio-api/respond')||opts.method!=='POST')throw Error('unreviewed-network');
  sends++;
  return Response.json({origin:'model',authority:'none',
   text:sends===1?'A report in 2025 included 200 patients. Treatment caused improvement.':
     'A result was described in 2026. '+token,
   model:'synthetic-provider',model_slot:'primary',configuration_id:fingerprint});
 };
 try{
  ok(typeof NexusClaimReview==='object','claim-review-module-loaded');
  fill('project-title','Claim Review Synthetic');$('new-project').click();$('new-thread').click();
  fill('gateway','https://fixture.invalid');fill('gateway-token','synthetic-gateway-token');
  change('studio-compose-mode','model');$('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().model==='synthetic-provider');
  fill('message','Summarize a synthetic study');$('prepare').click();$('consent').click();$('send-model').click();
  await wait(()=>$('messages').querySelector('[data-chat-review-claims]'));
  const button=$('messages').querySelector('[data-chat-review-claims]');
  ok(button?.textContent==='Review claims','button-under-model-reply');
  ok(!$('messages').querySelector('.claim-review-panel'),'review-opt-in-only');
  let before=allRequests;button.click();
  const panel=$('messages').querySelector('.claim-review-panel');
  ok(!!panel&&panel.querySelectorAll('.claim-review-entry').length===2,'local-per-answer-candidates');
  ok(panel.textContent.includes('not checked or verified')&&panel.textContent.includes('not-checked'),'no-false-fact-check');
  ok(allRequests===before,'review-never-contacts-network');
  ok(!JSON.stringify(NexusStudioUI.snapshot()).includes('claim-review-entry'),'review-not-added-to-archive');
  button.click();ok(!$('messages').querySelector('.claim-review-panel'),'panel-closes-without-mutation');
  change('language','fa');
  const fa=$('messages').querySelector('[data-chat-review-claims]');
  ok(fa?.textContent==='بررسی ادعاها','persian-localized-action');
  fa.click();ok($('messages').querySelector('.claim-review-panel').textContent.includes('تأیید نشده'),'persian-unverified-disclosure');
  change('language','en');
  fill('message','A second synthetic question');$('prepare').click();$('consent').click();$('send-model').click();
  await wait(()=>$('messages').querySelectorAll('[data-chat-review-claims]').length===2);
  const sensitive=$('messages').querySelectorAll('[data-chat-review-claims]')[1];
  before=allRequests;sensitive.click();
  const blocked=sensitive.closest('article').querySelector('.claim-review-panel');
  ok(blocked?.textContent.includes('Possible credential detected'),'secrets-block-claim-extraction');
  ok(!blocked.textContent.includes(token)&&!blocked.querySelector('.claim-review-entry'),'no-secret-echo-in-review');
  ok(allRequests===before&&sends===2&&discovery===1,'no-additional-remote-attempt');
  $('lock').click();
  ok(!$('messages').querySelector('.claim-review-panel')&&!JSON.stringify(NexusStudioUI.snapshot()).includes(token),'lock-disposes-transient-review');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,authority:'none',remote_provider_calls:0});
 }catch(error){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message),checks,authority:'none'});
 }
});
"""

def main():
 browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
 if not browser:raise RuntimeError('Chromium is required')
 html=(ROOT/'web/studio.html').read_text().replace(
    '</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 with tempfile.TemporaryDirectory(prefix='nexus-chat-claim-review-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  for label,size in [('narrow','420,900'),('wide','1280,900')]:
   cmd=['node',str(ROOT/'scripts/workspace-browser-runner.mjs'),
        browser,page.as_uri(),str(Path(td)/label),size,'60000','18000']
   run=subprocess.run(cmd,capture_output=True,text=True,timeout=130)
   if run.returncode:raise RuntimeError('claim-chat-runner-'+run.stderr[-1200:])
   report=json.loads(run.stdout)
   if report.get('status')!='PASS' or len(report.get('checks',[]))<12:
    raise RuntimeError(json.dumps(report,ensure_ascii=False))
 print('NEXUS integrated chat claim-review: PASS (narrow and wide)')

if __name__=='__main__':main()
