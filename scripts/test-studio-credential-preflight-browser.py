#!/usr/bin/env python3
"""Real isolated Chromium: two-step consent for synthetic credentials.

No production provider calls, secrets, billing, or deployment.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const ok=(yes,name)=>{if(!yes)throw Error(name);checks.push(name)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<250;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const id='a'.repeat(64),token='github_pat_'+'A'.repeat(40);
 let discovery=0,send=0,reviewed=null;
 window.confirm=()=>true;
 window.fetch=async(url,opts={})=>{
  const link=String(url);
  if(link.endsWith('/studio-api/status')){
   discovery++;return Response.json({
    configured:true,model:'synthetic-provider',provider_host:'fixture.invalid',
    configuration_id:id,reply_receipt_version:1,authority:'none'
   });
  }
  ok(link.endsWith('/studio-api/respond')&&opts.method==='POST'&&opts.credentials==='omit',
   'mock-provider-only-requested-after-review');
  send++;reviewed=JSON.parse(opts.body);
  return Response.json({origin:'model',authority:'none',text:'Synthetic completion',
    model:'synthetic-provider',model_slot:'primary',configuration_id:id});
 };
 try{
  fill('project-title','Synthetic credential review');$('new-project').click();
  $('new-thread').click();
  fill('gateway','https://fixture.invalid');fill('gateway-token','synthetic-studio-operator-token');
  change('studio-compose-mode','model');$('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().model==='synthetic-provider');
  ok(discovery===1&&send===0,'configuration-check-never-sends-model-prompt');
  fill('message','Please analyze '+token);
  $('prepare').click();
  const panel=$('studio-credential-preflight'),ack=$('studio-credential-override');
  ok(!$('request-review').hidden&&!panel.hidden&&panel.textContent.includes('GitHub token'),
   'synthetic-github-token-gets-clear-local-warning');
  ok(!panel.textContent.includes(token)&&!panel.textContent.includes('github_pat_'),
   'warning-discloses-category-only');
  ok(!ack.checked&&!$('consent').checked&&$('send-model').disabled,
   'neither-approval-is-implicitly-given');
  $('consent').click();
  ok($('send-model').disabled,'single-consent-does-not-enable-provider-send');
  $('send-model').click();
  ok(send===0,'disabled-action-produces-no-provider-call');
  change('language','fa');
  ok(panel.hidden&&$('request-review').hidden&&!ack.checked,
   'language-change-revokes-old-warning-and-both-consents');
  $('prepare').click();
  ok(!panel.hidden&&panel.textContent.includes('اطلاعات ورود محرمانه')&&
    !panel.textContent.includes(token),'fresh-persian-warning-remains-non-echoing');
  change('language','en');
  ok(panel.hidden&&!ack.checked,'return-to-English-needs-fresh-review');
  $('prepare').click();
  $('consent').click();
  ack.click();
  ok(!$('send-model').disabled,'two-fresh-consents-enable-reviewed-send');
  fill('message','A clean question');
  ok($('request-review').hidden&&panel.hidden&&!ack.checked,
   'editing-message-revokes-both-model-and-credential-approvals');
  $('prepare').click();
  ok(panel.hidden&&!ack.checked&&!$('consent').checked,
   'clean-prompt-does-not-inherit-previous-approval');
  fill('message','Review '+token);
  $('prepare').click();
  ok(!panel.hidden&&!ack.checked,'new-risk-review-needs-fresh-override');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  ack.checked=true;ack.dispatchEvent(new Event('change'));
  $('send-model').click();
  await wait(()=>$('messages').textContent.includes('Synthetic completion'));
  ok(send===1&&reviewed?.consent===true&&reviewed?.configuration_id===id,
   'two-approvals-send-the-exact-reviewed-route-to-synthetic-gateway');
  ok(reviewed.messages.some(x=>x.content.includes(token))&&
     !JSON.stringify(NexusStudioUI.snapshot()).includes('synthetic-studio-operator-token'),
   'the-approved-text-is-unchanged-and-gateway-token-is-never-archived');
  ok($('studio-credential-preflight').hidden&&!ack.checked,
   'successful-completion-clears-private-approval');
  $('nexus-browser-result').textContent=JSON.stringify({
    status:'PASS',checks,width:innerWidth,real_provider_tested:false,authority:'none'});
 }catch(e){
  $('nexus-browser-result').textContent=JSON.stringify({
    status:'FAIL',reason:e.message,checks,authority:'none'});
 }
});
"""

def main():
 root=Path(__file__).resolve().parents[1]
 browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
 if not browser: raise RuntimeError('Real Chromium required')
 html=(root/'web/studio.html').read_text().replace(
  '</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 reports=[]
 with tempfile.TemporaryDirectory(prefix='nexus-credential-preflight-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  for label,size in [('narrow','420,900'),('wide','1280,900')]:
   run=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),
    browser,page.as_uri(),str(Path(td)/label),size,'60000','30000'],
    capture_output=True,text=True,timeout=130)
   if run.returncode:raise RuntimeError('preflight-browser-failed-'+run.stderr[-1000:])
   report=json.loads(run.stdout)
   if report.get('status')!='PASS' or len(report.get('checks',[]))<14:
    raise RuntimeError(json.dumps(report))
   reports.append({'layout':label,**report})
 print(json.dumps({'status':'PASS','reports':reports}))

if __name__=='__main__':main()
