#!/usr/bin/env python3
"""Independent, fast Chromium witness for server-owned model reply receipts.

Synthetic gateway only; no remote provider calls, credentials or deployment.
The general Studio E2E suite remains bounded by a separate 60-second witness.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(pass,name)=>{if(!pass)throw Error(name);checks.push(name)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<250;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const snapshot=()=>NexusStudioUI.snapshot();
 const selected=()=>snapshot().projects.find(p=>p.id===NexusStudioUI.selection().projectId)
   ?.threads.find(t=>t.id===NexusStudioUI.selection().threadId);
 const rid='e'.repeat(64),model='reviewed-synthetic-route',
       legacyId='d'.repeat(64),legacyModel='legacy-synthetic-route';
 let receiptCapable=true,replyCase='wrong-slot',calls=0;
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
   const address=String(url);
   if(address.endsWith('/studio-api/status'))return Response.json({
    configured:true,configuration_id:receiptCapable?rid:legacyId,
    model:receiptCapable?model:legacyModel,provider_host:'review.invalid',
    ...(receiptCapable?{reply_receipt_version:1}:{}),authority:'none'
   });
   assert(address.endsWith('/studio-api/respond')&&options.method==='POST',
    'receipt-test-never-contacts-other-endpoints');
   const request=JSON.parse(options.body);
   assert(request.consent===true&&
    request.configuration_id===(receiptCapable?rid:legacyId),
    'approved-request-binds-frozen-configuration');
   calls++;
   const result={text:'Reviewed model answer',
     model:receiptCapable?model:legacyModel,origin:'model',authority:'none'};
   if(replyCase==='wrong-slot')Object.assign(result,{model_slot:'secondary',configuration_id:rid});
   if(replyCase==='wrong-id')Object.assign(result,{model_slot:'primary',configuration_id:'f'.repeat(64)});
   if(replyCase==='partial')Object.assign(result,{model_slot:'primary'});
   if(replyCase==='valid')Object.assign(result,{model_slot:'primary',configuration_id:rid});
   if(replyCase==='empty-draft')result.text='  \n ';
   if(replyCase==='structural-warning'){result.text='```js\nconst x=1;';result.truncated=true}
   return Response.json(result);
 };
 try{
   fill('project-title','Synthetic receipt project');$('new-project').click();
   $('new-thread').click();
   assert(Boolean(selected()),'synthetic-conversation-started');
   fill('gateway','https://reviewed-route.invalid');fill('gateway-token','synthetic-tab-token');
   change('studio-compose-mode','model');$('studio-compose-model-check').click();
   await wait(()=>NexusStudioUI.modelAvailability().model===model);
   assert(NexusStudioUI.modelAvailability().configured,'v1-model-catalog-checked');
   const submit=async()=>{
    fill('message','Confirm the selected route');
    $('prepare').click();
    assert(!$('request-review').hidden&&!$('consent').checked,
     'exact-review-and-new-consent-required');
    $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
    $('send-model').click();
    await wait(()=>$('request-review').hidden);
   };
   const before=JSON.stringify(snapshot());
   await submit();
   assert(JSON.stringify(snapshot())===before&&$('message').value==='Confirm the selected route'&&calls===1,
    'wrong-slot-rejected-with-draft-preserved');
   assert($('status').textContent.includes('did not match the model or configuration')&&
    $('status').textContent.includes('Nothing was added'),
    'wrong-route-error-is-actionable-in-English');
   replyCase='wrong-id';await submit();
   assert(JSON.stringify(snapshot())===before&&calls===2,'stale-config-rejected-without-committing');
   change('language','fa');
   replyCase='partial';await submit();
   assert(JSON.stringify(snapshot())===before&&calls===3,'partial-v1-receipt-rejected');
   assert($('status').textContent.includes('مطابقت نداشت')&&$('status').textContent.includes('چیزی به گفتگو اضافه نشد'),
    'wrong-route-error-is-actionable-in-Persian');
   change('language','en');
   replyCase='missing';await submit();
   assert(JSON.stringify(snapshot())===before&&calls===4,'missing-v1-receipt-rejected');
   replyCase='valid';await submit();
   await wait(()=>selected()?.nodes.some(n=>n.model_receipt?.configuration_id===rid));
   const answer=NexusStudio.path(selected()).at(-1);
   assert(answer.model_receipt?.model_slot==='primary'&&answer.model_receipt?.model===model&&
     answer.model_receipt?.configuration_id===rid&&calls===5,
     'correct-route-receipt-is-preserved');
   assert($('messages').textContent.includes(model+' (primary)')&&
      !$('messages').textContent.includes('synthetic-tab-token'),
      'accepted-origin-label-is-visible-without-gateway-credential');
   assert(!JSON.stringify(snapshot()).includes('synthetic-tab-token'),
      'gateway-credential-is-not-archived');
   receiptCapable=false;replyCase='missing';
   $('studio-compose-model-check').click();
   await wait(()=>NexusStudioUI.modelAvailability().model===legacyModel);
   await submit();
   await wait(()=>NexusStudio.path(selected()).at(-1)?.text==='Reviewed model answer');
   const last=NexusStudio.path(selected()).at(-1);
   assert(!last.model_receipt&&calls===6,'legacy-unattributed-reply-is-not-falsely-verified');
   const beforeEmpty=JSON.stringify(snapshot());
   replyCase='empty-draft';await submit();
   assert(JSON.stringify(snapshot())===beforeEmpty&&$('message').value==='Confirm the selected route'&&calls===7,'empty-draft-rejected-with-original-draft');
   replyCase='structural-warning';await submit();
   const warned=NexusStudio.path(selected()).at(-1);
   assert(warned.text==='```js\nconst x=1;'&&calls===8,'structural-warning-does-not-rewrite-or-resend');
   assert($('status').textContent.includes('Unclosed code block.')&&$('status').textContent.includes('facts not verified'),'structural-warning-visible');

   // A deliberate second pass opens the existing exact consent review.
   const reviewButton=$('messages').querySelector('[data-chat-review-answer]');
   assert(reviewButton,'latest-model-answer-has-review-action');
   fill('message','Preserve my draft');reviewButton.click();
   assert($('message').value==='Preserve my draft'&&calls===8,'review-preserves-existing-draft');
   fill('message','');const beforeReview=JSON.stringify(snapshot());
   reviewButton.click();
   const preparedReview=JSON.parse($('request-context').textContent);
   const tail=preparedReview.messages.slice(-3);
   assert(!$('request-review').hidden&&!$('consent').checked&&calls===8,'review-prepares-without-sending');
   assert(tail[0].content==='Confirm the selected route'&&tail[1].content===warned.text&&tail[2].content.includes('unsupported factual claims'),'review-binds-original-question-and-answer');
   assert(JSON.stringify(snapshot())===beforeReview,'review-preparation-does-not-change-history');
   $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
   replyCase='missing';$('send-model').click();await wait(()=>$('request-review').hidden);
   assert(calls===9&&NexusStudio.path(selected()).some(n=>n.id===warned.id&&n.text===warned.text),'approved-review-adds-new-turn-preserving-answer');
   fill('message','Review local evidence');
   const quoteA='The observed value increased in the sample.';
   const quoteB='The observed value decreased in the sample.';
   assert(NexusStudioUI.stageChatContext('Evidence A',quoteA),'evidence-a-staged');
   assert(NexusStudioUI.stageChatContext('Evidence B',quoteB),'evidence-b-staged');
   $('prepare').click();
   const reviewed=JSON.parse($('request-context').textContent);
   assert(reviewed.temporary_attachment_passages.length===2,'two-excerpts-in-reviewed-context');
   $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
   $('send-model').click();await wait(()=>$('request-review').hidden);
   const evidence=$('messages').querySelector('[data-evidence-review]');
   assert(evidence&&calls===10,'evidence-panel-on-completed-reply');
   const beforeJudgment=JSON.stringify(snapshot());
   const areas=evidence.querySelectorAll('textarea'),selects=evidence.querySelectorAll('select');
   areas[0].value='Reviewed model answer';
   selects[0].value='A1';selects[0].dispatchEvent(new Event('change'));
   selects[2].value='A2';selects[2].dispatchEvent(new Event('change'));
   areas[1].value=quoteA;areas[2].value=quoteB;
   selects[1].value='supports';selects[3].value='contradicts';
   evidence.querySelector('[data-evidence-check]').click();
   assert(evidence.querySelector('pre').textContent.includes('conflicting_reported_evidence'),'human-judgments-conflict');
   assert(JSON.stringify(snapshot())===beforeJudgment&&calls===10,'no-new-request-or-history-mutation');
   fill('message','Next draft');
   assert(!$('messages').querySelector('[data-evidence-review]'),'draft-change-clears-evidence-panel');
   $('nexus-browser-result').textContent=JSON.stringify({
      status:'PASS',checks,width:innerWidth,provider_requests:0,authority:'none'});
 }catch(error){
   $('nexus-browser-result').textContent=JSON.stringify({
      status:'FAIL',reason:error.message,checks,authority:'none'});
 }
});
"""

def main():
 root=Path(__file__).resolve().parents[1]
 browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
 if not browser:raise RuntimeError('real Chromium required')
 html=(root/'web/studio.html').read_text().replace(
     '</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 reports=[]
 with tempfile.TemporaryDirectory(prefix='nexus-model-receipt-browser-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  for label,dimensions in [('narrow','420,900'),('wide','1280,900')]:
   run=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),
       browser,page.as_uri(),str(Path(td)/label),dimensions,'60000','30000'],
       capture_output=True,text=True,timeout=130)
   if run.returncode:raise RuntimeError('receipt-browser-witness-failed-'+run.stderr[-1200:])
   report=json.loads(run.stdout)
   if report.get('status')!='PASS' or len(report.get('checks',[]))<12:
    raise RuntimeError(json.dumps(report))
   reports.append({'layout':label,**report})
 print(json.dumps({'status':'PASS','reports':reports}))

if __name__=='__main__':main()
