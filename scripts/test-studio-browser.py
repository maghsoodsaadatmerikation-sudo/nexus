#!/usr/bin/env python3
"""Disposable real Chromium: Studio UX, encryption, branching and consent races."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const snapshot=()=>NexusStudioUI.snapshot();
 const current=()=>snapshot().projects.find(p=>p.id===$('projects').value);
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let network=0,posted=null,delayResponse=null,late=false;
 window.confirm=()=>true;window.prompt=()=> 'Renamed conversation';
 window.fetch=async(url,options={})=>{network++;if(String(url).endsWith('/status'))return new Response(JSON.stringify({configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'synthetic.invalid'}));posted=JSON.parse(options.body);const response=()=>new Response(JSON.stringify({text:'SYNTHETIC MODEL DRAFT',origin:'model',model:'synthetic-model',authority:'none'}));if(late)return new Promise(resolve=>delayResponse=()=>resolve(response()));return response()};
 try{
  assert(document.documentElement.lang==='en','english-first');
  assert(!snapshot().projects.length&&!$('use-memory').checked,'empty-temporary-session-memory-off');
  fill('project-title','PRIVATE PROJECT');$('new-project').click();$('new-thread').click();
  fill('message','ORIGINAL QUESTION');$('guide').click();
  assert(current().threads[0].nodes.length===2,'local-guide-multi-turn');
  assert($('messages').textContent.includes('not a generative model'),'guide-origin-honest');
  assert(network===0,'local-guide-does-not-connect');
  const firstHead=current().threads[0].head;
  $('messages').querySelector('button').click();fill('message','BRANCHED QUESTION');$('guide').click();
  assert(current().threads[0].nodes.length===4&&$('branch').options.length===2,'editing-preserves-two-branches');
  change('branch',firstHead);assert($('messages').textContent.includes('ORIGINAL QUESTION')&&!$('messages').textContent.includes('BRANCHED QUESTION'),'branch-selector-restores-original');
  $('rename-thread').click();assert(current().threads[0].title==='Renamed conversation','rename-chat');
  fill('search','BRANCHED');assert($('history').children.length===1,'search-includes-other-branches');
  fill('search','');$('archive-thread').click();assert($('history').children.length===0,'archive-hides-thread');
  $('archived').checked=true;$('archived').dispatchEvent(new Event('change'));assert($('history').children.length===1,'include-archived-search');$('archive-thread').click();
  fill('instructions','CUSTOM PREFERENCE');fill('memories','REVIEWED SECRET MEMORY');$('apply-profile').click();
  assert(current().memories[0]==='REVIEWED SECRET MEMORY','explicit-project-memory');
  const transfer=new DataTransfer();transfer.items.add(new File(['The orchard has green trees.\nA source is not a verified fact.'],'notes.txt',{type:'text/plain'}));$('source-file').files=transfer.files;$('source-file').dispatchEvent(new Event('change'));
  await wait(()=>current().sources.length===1);fill('source-query','orchard');$('search-sources').click();assert($('source-results').textContent.includes('notes.txt:1'),'local-source-name-and-line');
  fill('document-title','PRIVATE DOC');$('new-document').click();fill('editor','version one');$('save-version').click();fill('editor','version two');$('save-version').click();assert(current().documents[0].versions.length===2,'append-only-document-versions');
  change('versions',current().documents[0].versions[0].id);assert($('version-diff').textContent.includes('version one')&&$('version-diff').textContent.includes('version two'),'version-diff');$('load-version').click();assert($('editor').value==='version one','load-old-version-into-draft');$('save-version').click();
  const injection='<img src=x onerror=alert(1)>';fill('message',injection);$('guide').click();assert($('messages').textContent.includes(injection)&&!$('messages').querySelector('img'),'untrusted-message-is-inert');
  fill('gateway','https://synthetic.invalid');fill('gateway-token','TRANSIENT ACCESS TOKEN');$('check-model').click();await wait(()=>$('model-status').textContent.includes('synthetic-model'));
  fill('message','orchard trees');$('prepare').click();assert(!$('request-review').hidden&&!$('consent').checked,'review-required-before-send');assert(!$('request-context').textContent.includes('REVIEWED SECRET MEMORY'),'memory-not-sent-by-default');
  $('use-memory').checked=true;$('use-memory').dispatchEvent(new Event('input'));assert($('request-review').hidden,'context-change-invalidates-approval');$('use-sources').checked=true;$('prepare').click();assert($('request-context').textContent.includes('REVIEWED SECRET MEMORY')&&$('request-context').textContent.includes('notes.txt'),'exact-selected-context-visible');
  const count=network;$('send-model').click();assert(network===count,'unapproved-send-does-not-connect');$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();await wait(()=>current().threads[0].nodes.at(-1)?.origin==='model');assert(posted.consent===true&&posted.configuration_id==='a'.repeat(64),'approved-request-binds-configuration');assert(!JSON.stringify(posted).includes('TRANSIENT ACCESS TOKEN'),'gateway-token-excluded-from-context');
  $('regenerate').click();assert(!$('request-review').hidden,'regenerate-prepares-another-branch');$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();await wait(()=>$('request-review').hidden);assert($('branch').options.length>=3,'regenerate-keeps-original-answer');
  late=true;fill('message','STALE REQUEST');$('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));const before=current().threads[0].nodes.length;$('send-model').click();await wait(()=>delayResponse!==null);$('stop').click();delayResponse();await sleep(50);assert(current().threads[0].nodes.length===before,'stop-discards-late-model-answer');fill('message','');late=false;
  fill('passphrase','long private password 123');fill('repeat-passphrase','long private password 123');$('create-vault').click();await wait(()=>!$('save').disabled);$('save').click();await wait(()=>$('status').textContent.includes('session saved'));
  const store=new NexusStudio.IndexedStore(),raw=await store.read();assert(raw&&!raw.includes('PRIVATE PROJECT')&&!raw.includes('REVIEWED SECRET MEMORY'),'indexeddb-contains-ciphertext-only');assert(!raw.includes('TRANSIENT ACCESS TOKEN'),'credentials-not-in-encrypted-state');
  fill('editor','UNSAVED CANVAS');fill('instructions','CHANGED PREFERENCE');$('apply-profile').click();$('save').click();assert($('status').textContent.includes('save document versions'),'profile-apply-does-not-hide-canvas-draft');$('save-version').click();$('save').click();await wait(()=>$('status').textContent.includes('session saved'));
  const projectId=current().id;$('lock').click();assert(snapshot().projects.length===0&&$('gateway-token').value===''&&$('editor').value==='','lock-clears-working-data-and-credential');
  fill('passphrase','wrong password 123');$('unlock').click();await wait(()=>$('status').textContent.includes('Operation failed'));assert(snapshot().projects.length===0,'wrong-password-does-not-open');
  fill('passphrase','long private password 123');$('unlock').click();await wait(()=>snapshot().projects.length===1);assert(current().id===projectId&&current().documents[0].versions.at(-1).text==='UNSAVED CANVAS','encrypted-reopen-restores-chats-memory-and-canvas');
  const oldId=current().id;fill('project-title','SECOND PROJECT');$('new-project').click();$('new-thread').click();assert(current().id!==oldId&&current().memories.length===0&&!$('use-memory').checked,'new-project-isolates-memory-and-context');
  change('language','fa');assert(document.documentElement.dir==='rtl'&&$('guide').textContent.includes('محلی'),'persian-rtl-interface');
  const unchanged=JSON.stringify(snapshot());
  const labels={};document.querySelectorAll('[data-t]').forEach(n=>labels[n.dataset.t]=n.textContent);
  // The template includes status/action labels not currently rendered in the page.
  Object.assign(labels,EN);
  const languageTransfer=new DataTransfer();languageTransfer.items.add(new File([JSON.stringify({schema:'nexus.studio.locale.v1',code:'es',dir:'ltr',messages:{...labels,conversation:'Conversación'}})],'spanish-labels.json',{type:'application/json'}));$('language-file').files=languageTransfer.files;$('language-file').dispatchEvent(new Event('change'));
  await wait(()=>document.documentElement.lang==='es');assert($('conversation-card').textContent.includes('Conversación'),'complete-local-language-pack');assert(JSON.stringify(snapshot())===unchanged,'language-import-does-not-touch-projects');
  assert(document.documentElement.scrollWidth<=innerWidth+2,'no-horizontal-overflow');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,real_model_tested:false,authority:'none'});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""

def main():
 root=Path(__file__).resolve().parents[1]
 browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
 if not browser:raise RuntimeError('real Chromium required')
 html=(root/'web/studio.html').read_text().replace('</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 reports=[]
 with tempfile.TemporaryDirectory(prefix='nexus-studio-browser-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  for label,size in [('narrow','420,1000'),('wide','1280,1000')]:
   r=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/label),size,'60000','30000'],capture_output=True,text=True,timeout=130)
   if r.returncode:raise RuntimeError('browser-runner-failed-'+r.stderr[-1000:])
   report=json.loads(r.stdout)
   if report.get('status')!='PASS':raise RuntimeError(json.dumps(report))
   if len(report['checks'])<30:raise RuntimeError('missing-witness-checks')
   reports.append({'layout':label,**report})
 print(json.dumps({'status':'PASS','reports':reports}))
if __name__=='__main__':main()
