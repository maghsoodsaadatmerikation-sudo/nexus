#!/usr/bin/env python3
"""Isolated real-Chromium acceptance of non-echoing gateway error guidance.

All gateway outcomes are synthetic in-memory fetch responses. No paid model,
credential lookup, provider request, production connection or auto-retry.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,name)=>{if(!ok)throw Error(name);checks.push(name)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const snapshot=()=>JSON.stringify(NexusStudioUI.snapshot());
 const fingerprint='a'.repeat(64),streamFingerprint='b'.repeat(64),
       model='synthetic-gateway-model',streamModel='synthetic-stream-gateway-model',privateMarker='SYNTHETIC-PROVIDER-SECRET-MUST-NOT-ECHO';
 let mode='http',code=401,calls=0,streaming=false;
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  const address=String(url);
  if(address.endsWith('/studio-api/status'))return Response.json({
   configured:true,model:streaming?streamModel:model,
   configuration_id:streaming?streamFingerprint:fingerprint,provider_host:'synthetic.invalid',
   authority:'none',reply_receipt_version:1,...(streaming?{streaming:true}:{})
  });
  assert(address.endsWith(streaming?'/studio-api/respond-stream':'/studio-api/respond')&&
   options.method==='POST'&&options.credentials==='omit'&&options.redirect==='error'&&
   options.headers.authorization==='Bearer synthetic-gateway-access',
   'only-explicit-consented-request-hits-synthetic-gateway');
  const body=JSON.parse(options.body);
  assert(body.consent===true&&body.configuration_id===(streaming?streamFingerprint:fingerprint),
   'every-request-preserves-reviewed-fingerprint');
  calls++;
  if(mode==='network')throw new TypeError(privateMarker);
  if(mode==='abort')throw new DOMException(privateMarker,'AbortError');
  if(mode==='malformed'){
   return new Response(streaming?'{"type":"error","reason":"incomplete"}\n':'{not-json',
    {status:200,headers:{'content-type':streaming?'application/x-ndjson':'application/json'}});
  }
  if(mode==='untrusted')return Response.json({
   text:privateMarker,origin:'guide',model,authority:'none',
   model_slot:'primary',configuration_id:fingerprint
  });
  return Response.json({detail:privateMarker},{status:code});
 };
 try{
  fill('project-title','Synthetic gateway test');$('new-project').click();$('new-thread').click();
  fill('gateway','https://gateway.invalid');fill('gateway-token','synthetic-gateway-access');
  change('studio-compose-mode','model');
  $('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().model===model);
  const before=snapshot(),draft='Unsent synthetic example question';
  const attempt=async()=>{
   fill('message',draft);$('prepare').click();
   assert(!$('request-review').hidden&&!$('consent').checked,'fresh-reviewed-consent-required');
   $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
   const count=calls;$('send-model').click();
   await wait(()=>$('request-review').hidden);
   assert(calls===count+1,'never-retry-automatically');
   assert(snapshot()===before&&$('message').value===draft,
    'failed-gateway-request-does-not-commit-or-erase-draft');
   assert(!$('status').textContent.includes(privateMarker)&&
    !$('messages').textContent.includes(privateMarker)&&
    !$('request-context').textContent.includes(privateMarker),
    'server-response-details-never-echoed');
  };
  const statuses=[
   [401,'Gateway access denied'],[403,'Gateway access denied'],
   [409,'Gateway model changed'],[415,'Gateway rejected the request (415/422)'],
   [422,'Gateway rejected the request (415/422)'],[429,'Gateway busy'],
   [503,'Gateway or provider unavailable'],[502,'Gateway/provider error'],
   [504,'Gateway/provider error'],[404,'Gateway rejected the request']
  ];
  for(const [status,phrase] of statuses){
   mode='http';code=status;await attempt();
   assert($('status').textContent.includes(phrase),'http-'+status+'-shows-actionable-status');
  }
  mode='network';await attempt();
  assert($('status').textContent.includes('Gateway connection failed'),
   'network-and-cors-failure-never-leaks-internal-error');
  mode='abort';await attempt();
  assert($('status').textContent.includes('Model request timed out'),
   'aborted-model-fetch-is-treated-as-timeout-without-retry');
  mode='malformed';await attempt();
  assert($('status').textContent.includes('Incomplete or invalid model reply'),
   'invalid-json-is-rejected-with-actionable-guidance');
  mode='untrusted';await attempt();
  assert($('status').textContent.includes('Incomplete or invalid model reply'),
   'invalid-model-origin-is-rejected-without-leaking-body');
  // Streaming errors must retain the HTTP code rather than hiding it behind
  // a generic stream-format failure. A partially received stream is not saved.
  streaming=true;$('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().model===streamModel);
  mode='http';code=429;await attempt();
  assert($('status').textContent.includes('Gateway busy'),
   'streamed-429-retains-specific-reason');
  mode='malformed';await attempt();
  assert($('status').textContent.includes('Incomplete or invalid model reply'),
   'stream-malformed-reply-is-rejected');
  // Changing UI language affects only the explanation, not consent or data.
  change('language','fa');streaming=false;
  $('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().model===model);
  mode='http';code=401;await attempt();
  assert($('status').textContent.includes('دسترسی به درگاه رد شد'),
   'persian-auth-error-without-credentials');
  code=429;await attempt();
  assert($('status').textContent.includes('سهمیهٔ محلی'),
   'persian-budget-error-without-automatic-retry');
  $('nexus-browser-result').textContent=JSON.stringify({
   status:'PASS',checks,width:innerWidth,remote_provider_calls:0,
   encrypted_archive_mutated:false,authority:'none'});
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
 html=(root/'web/studio.html').read_text().replace('</body>',
  '<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 with tempfile.TemporaryDirectory(prefix='nexus-gateway-errors-browser-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  reports=[]
  for label,size in [('narrow','420,900'),('wide','1280,900')]:
   run=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,
    page.as_uri(),str(Path(td)/label),size,'60000','30000'],
    capture_output=True,text=True,timeout=130)
   if run.returncode:raise RuntimeError('gateway-error-browser-failure-'+run.stderr[-1200:])
   report=json.loads(run.stdout)
   if report.get('status')!='PASS' or len(report.get('checks',[]))<38:
    raise RuntimeError(json.dumps(report))
   reports.append({'layout':label,**report})
 print(json.dumps({'status':'PASS','reports':reports}))

if __name__=='__main__':main()
