#!/usr/bin/env python3
"""Synthetic device transport in real Studio: consent, provenance, cancellation, lock."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 try{
  window.confirm=()=>true;const selector=document.createElement('select');selector.id='model-engine';selector.innerHTML='<option value="gateway">Gateway</option><option value="device">Device</option>';document.body.append(selector);selector.value='device';
  let calls=0,request=null,late=null,signal=null,unloaded=0;
  window.fetch=()=>{throw Error('unexpected-network')};
  const info={ready:true,configuration_id:'b'.repeat(64),model:'SYNTHETIC-DEVICE-ONLY',policy:'FIXED LOCAL POLICY',max_input_tokens:768,max_output_tokens:64};
  window.NexusDevice={info:()=>info,unload:()=>{unloaded++},generate:async(body,abort)=>{calls++;request=body;signal=abort;return new Promise(resolve=>late=resolve)}};
  fill('project-title','SYNTHETIC PROJECT');$('new-project').click();$('new-thread').click();fill('message','SYNTHETIC QUESTION');fill('model-budget','16');$('prepare').click();
  assert(!$('request-review').hidden&&!$('consent').checked,'device-review-required');
  assert($('request-context').textContent.includes('FIXED LOCAL POLICY')&&$('request-context').textContent.includes('no prompt transmission'),'fixed-policy-and-local-destination-visible');
  $('send-model').click();assert(calls===0,'no-generation-before-consent');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();await wait(()=>late);
  assert(request.consent===true&&request.configuration_id==='b'.repeat(64)&&request.max_output_tokens===16,'review-binds-exact-local-configuration');
  late({text:'SYNTHETIC LOCAL DRAFT',origin:'model',model:info.model,authority:'none'});await wait(()=>NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===2);
  assert($('messages').textContent.includes('[On-device draft')&&$('messages').textContent.includes('SYNTHETIC LOCAL DRAFT'),'local-origin-is-visible-in-history');
  fill('message','STALE SYNTHETIC QUESTION');$('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));late=null;$('send-model').click();await wait(()=>late);const before=NexusStudioUI.snapshot().projects[0].threads[0].nodes.length;
  $('stop').click();assert(signal.aborted,'stop-aborts-local-generation');late({text:'LATE SYNTHETIC DRAFT',origin:'model',model:info.model,authority:'none'});await new Promise(r=>setTimeout(r,50));
  assert(NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===before,'late-local-result-is-discarded');
  fill('message','x'.repeat(7000));$('prepare').click();assert($('request-review').hidden,'oversized-local-review-is-refused');
  $('lock').click();assert(unloaded===1&&NexusStudioUI.snapshot().projects.length===0&&$('gateway-token').value==='','lock-unloads-local-model-and-clears-session');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',checks,reason:error.message})}
});
"""

def main():
    root=Path(__file__).resolve().parents[1]
    browser=next((shutil.which(n) for n in ['google-chrome','chromium'] if shutil.which(n)),None)
    if not browser:raise RuntimeError('real Chromium required')
    html=(root/'web/studio.html').read_text().replace('</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
    with tempfile.TemporaryDirectory(prefix='nexus-device-ui-') as temporary:
        page=Path(temporary)/'index.html';page.write_text(html)
        result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(temporary)/'profile'),'420,1000','60000','30000'],capture_output=True,text=True,timeout=130)
        if result.returncode:raise RuntimeError('browser runner failed: '+result.stderr[-1000:])
        report=json.loads(result.stdout)
        assert report.get('status')=='PASS' and len(report.get('checks',[]))>=9,report
        print(json.dumps(report))
if __name__=='__main__':main()
