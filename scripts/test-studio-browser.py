#!/usr/bin/env python3
"""Disposable real Chromium: Studio UX, encryption, branching and consent races."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

MIN_CHECKS=48

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
  const offer=$('nexus-zen-offer'),compose=$('studio-compose-send');
  $('nexus-zen-suggestions').querySelector('button').click();
  assert(NexusStudioFocus.active()==='music-card'&&!$('message').value&&snapshot().projects.length===0,
   'empty-chat-chip-opens-tool-in-one-step');
  $('nexus-zen-home').click();
  change('studio-compose-mode','model');fill('message','/research Explicit tool');
  assert(compose.textContent==='Review Research','explicit-tool-discoverable-in-model-mode');
  compose.click();
  assert(!offer.hidden&&$('request-review').hidden&&network===0,'explicit-tool-does-not-start-model-review');
  change('studio-compose-mode','guide');
  fill('message','تحليل فايل CSV');
  assert(compose.textContent==='Review Data analysis','persian-intent-shows-tool-before-submit');
  fill('message','/research Old question');compose.click();
  assert(!offer.hidden,'tool-offer-opens-after-explicit-action');
  fill('message','Revised question');
  assert(offer.hidden&&offer.childElementCount===0,'editing-drops-stale-tool-offer');
  fill('research-query','Preserve existing research draft');
  fill('message','/research Replacement query');compose.click();offer.querySelector('button').click();
  assert(NexusStudioFocus.active()==='research-card'&&$('research-query').value==='Preserve existing research draft'&&
   $('message').value==='/research Replacement query','tool-navigation-preserves-both-drafts');
  fill('research-query','');$('nexus-zen-home').click();
  fill('message','جست‌وجو کن دربارهٔ پژوهش خواب');compose.click();offer.querySelector('button').click();
  assert($('research-query').value==='دربارهٔ پژوهش خواب'&&network===0,
   'natural-language-research-query-prefills-for-review');
  fill('research-query','');$('nexus-zen-home').click();
  fill('message','/research Exact query');compose.click();offer.querySelector('button').click();
  assert($('research-query').value==='Exact query','empty-tool-field-receives-reviewed-query');
  fill('research-query','');$('nexus-zen-home').click();
  fill('message','/research Guide fallback');compose.click();offer.querySelectorAll('button')[1].click();
  assert(offer.hidden&&current().threads[0].nodes.length===2&&network===0,
   'declining-tool-can-continue-with-local-guide');
  change('studio-compose-mode','model');$('studio-compose-config').click();
  assert($('nexus-zen-more').getAttribute('aria-expanded')==='true'&&$('studio-model-settings').open,
   'model-settings-shortcut-expands-chat-options');
  $('nexus-zen-more').click();
  assert($('nexus-zen-more').getAttribute('aria-expanded')==='false','chat-options-can-collapse-after-shortcut');
  change('studio-compose-mode','guide');

  fill('message','/research Synthetic private offer');compose.click();
  $('nexus-zen-menu').click();fill('nexus-zen-find','Synthetic private search');$('nexus-zen-archived').click();
  window.confirm=()=>false;$('lock').click();
  assert(!offer.hidden&&$('nexus-zen-find').value==='Synthetic private search','declined-lock-keeps-chat-and-search');
  window.confirm=()=>true;$('lock').click();
  assert(offer.hidden&&offer.childElementCount===0&&$('nexus-zen-drawer').hidden&&
   !$('nexus-zen-find').value&&!$('nexus-zen-archived').checked&&!$('nexus-zen-history').childElementCount,
   'accepted-lock-clears-private-chat-overlays');
  fill('project-title','PRIVATE PROJECT');$('new-project').click();$('new-thread').click();
  fill('message','ORIGINAL QUESTION');$('guide').click();
  assert(current().threads[0].nodes.length===2,'local-guide-multi-turn');
  assert($('messages').textContent.includes('not a generative model'),'guide-origin-honest');
  assert(network===0,'local-guide-does-not-connect');
  const firstHead=current().threads[0].head;
  $('messages').querySelector('button').click();fill('message','BRANCHED QUESTION');$('guide').click();
  assert(current().threads[0].nodes.length===4&&$('branch').options.length===2,'editing-preserves-two-branches');
  change('branch',firstHead);assert($('messages').textContent.includes('ORIGINAL QUESTION')&&!$('messages').textContent.includes('BRANCHED QUESTION'),'branch-selector-restores-original');
  fill('message','KEEP THIS DRAFT');window.confirm=()=>false;change('branch',current().threads[0].nodes.at(-1).id);assert($('branch').value===firstHead&&current().threads[0].head===firstHead&&$('message').value==='KEEP THIS DRAFT','declined-branch-change-restores-selection-and-draft');window.confirm=()=>true;fill('message','');
  $('messages').querySelector('button').click();
  assert($('request-review').hidden&&$('storage-center').dataset.unsaved==='true'&&$('branch-notice').textContent===EN.branching,'edit-branch-refreshes-draft-status');
  change('branch',current().threads[0].nodes.at(-1).id);
  assert(!$('message').value&&!$('branch-notice').textContent&&$('storage-chat-state').textContent===EN.storageChatNone,'accepted-branch-switch-clears-draft-before-render');
  change('branch',firstHead);
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
  const historyButton=title=>[...$('history').children].find(b=>b.textContent.endsWith(' · '+title));
  const canvasId=$('documents').value;
  fill('editor','Preserve the current canvas draft');
  fill('task-plan','Preserve the project task draft');
  let confirmations=0;
  window.confirm=()=>{confirmations++;return false};
  $('new-thread').click();
  assert(confirmations===0&&current().threads.length===2&&$('editor').value==='Preserve the current canvas draft',
   'new-chat-keeps-unrelated-draft-without-confirmation');
  assert(!$('use-memory').checked&&!$('use-sources').checked,'new-chat-resets-context-opt-ins');
  fill('message','Keep the composer draft on the active chat');
  $('use-memory').checked=true;$('use-sources').checked=true;
  const draftFiles=new DataTransfer();draftFiles.items.add(new File(['draft text'],'switch.txt'));
  $('chat-file').files=draftFiles.files;$('chat-file').dispatchEvent(new Event('change'));
  await wait(()=>$('chat-attachment-tray').textContent.includes('switch.txt'));
  $('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  historyButton(EN.newChat).click();
  assert(confirmations===0&&!$('request-review').hidden&&$('consent').checked,'reselecting-active-chat-keeps-draft-and-review');
  historyButton('Renamed conversation').click();
  assert(confirmations===1&&!$('request-review').hidden&&$('message').value.includes('Keep the composer'),
   'declining-chat-switch-keeps-review-and-draft');
  window.confirm=()=>{confirmations++;return true};
  historyButton('Renamed conversation').click();
  assert(confirmations===2&&$('request-review').hidden&&!$('request-context').textContent&&!$('consent').checked&&
   !$('message').value&&!$('use-memory').checked&&!$('use-sources').checked&&$('chat-attachment-tray').textContent.includes(EN.chatNoFiles),
   'accepted-chat-switch-clears-only-chat-context-and-review');
  assert($('documents').value===canvasId&&$('editor').value==='Preserve the current canvas draft'&&
   $('task-plan').value==='Preserve the project task draft'&&$('source-results').textContent.includes('notes.txt:1'),
   'same-project-chat-switch-keeps-canvas-tools-and-search-results');
  fill('instructions','Preserve unapplied project preferences');
  confirmations=0;window.confirm=()=>{confirmations++;return false};
  historyButton(EN.newChat).click();historyButton('Renamed conversation').click();
  assert(confirmations===0&&$('instructions').value==='Preserve unapplied project preferences'&&NexusStudioUI.storageStatus().drafts.preferences,
   'same-project-history-preserves-unapplied-preferences-without-warning');
  window.confirm=()=>true;$('apply-profile').click();$('save-version').click();
  fill('passphrase','long private password 123');fill('repeat-passphrase','long private password 123');$('create-vault').click();await wait(()=>!$('save').disabled);$('save').click();await wait(()=>$('status').textContent.includes('session saved'));
  const store=new NexusStudio.IndexedStore(),raw=await store.read();assert(raw&&!raw.includes('PRIVATE PROJECT')&&!raw.includes('REVIEWED SECRET MEMORY'),'indexeddb-contains-ciphertext-only');assert(!raw.includes('TRANSIENT ACCESS TOKEN'),'credentials-not-in-encrypted-state');
  fill('editor','UNSAVED CANVAS');fill('instructions','CHANGED PREFERENCE');$('apply-profile').click();$('save').click();assert($('status').textContent.includes('save document versions'),'profile-apply-does-not-hide-canvas-draft');$('save-version').click();$('save').click();await wait(()=>$('status').textContent.includes('session saved'));
  const projectId=current().id;$('lock').click();assert(snapshot().projects.length===0&&$('gateway-token').value===''&&$('editor').value==='','lock-clears-working-data-and-credential');
  fill('passphrase','wrong password 123');$('unlock').click();await wait(()=>$('status').textContent.includes('Operation failed'));assert(snapshot().projects.length===0,'wrong-password-does-not-open');
  fill('passphrase','long private password 123');$('unlock').click();await wait(()=>snapshot().projects.length===1);assert(current().id===projectId&&current().documents[0].versions.at(-1).text==='UNSAVED CANVAS','encrypted-reopen-restores-chats-memory-and-canvas');
  const unchangedDraftState=JSON.stringify(snapshot());fill('message','UNSENT PRIVATE DRAFT');fill('passphrase','long private password 123');window.confirm=()=>false;$('unlock').click();await sleep(30);assert($('message').value==='UNSENT PRIVATE DRAFT'&&JSON.stringify(snapshot())===unchangedDraftState&&$('passphrase').value==='long private password 123','unlock-requires-confirmation-for-unsent-draft');window.confirm=()=>true;fill('message','');fill('passphrase','');
  const oldId=current().id;fill('project-title','SECOND PROJECT');$('new-project').click();$('new-thread').click();assert(current().id!==oldId&&current().memories.length===0&&!$('use-memory').checked,'new-project-isolates-memory-and-context');
  fill('task-plan','Second project only');
  fill('instructions','Unapplied second-project preferences');
  const secondId=current().id;
  window.confirm=()=>false;historyButton('Renamed conversation').click();
  assert(current().id===secondId&&$('task-plan').value==='Second project only','declined-cross-project-history-keeps-current-work');
  window.confirm=()=>true;historyButton('Renamed conversation').click();
  assert(current().id===oldId&&!$('task-plan').value&&$('instructions').value==='CHANGED PREFERENCE',
   'accepted-cross-project-history-clears-project-scoped-work');
  change('language','fa');assert(document.documentElement.dir==='rtl'&&$('guide').textContent.includes('محلی'),'persian-rtl-interface');
  const unchanged=JSON.stringify(snapshot());
  const labels={};document.querySelectorAll('[data-t]').forEach(n=>labels[n.dataset.t]=n.textContent);
  // The template includes status/action labels not currently rendered in the page.
  Object.assign(labels,EN);
  const languageTransfer=new DataTransfer();languageTransfer.items.add(new File([JSON.stringify({schema:'nexus.studio.locale.v1',code:'es',dir:'ltr',messages:{...labels,conversation:'Conversación'}})],'spanish-labels.json',{type:'application/json'}));$('language-file').files=languageTransfer.files;$('language-file').dispatchEvent(new Event('change'));
  await wait(()=>document.documentElement.lang==='es');assert($('conversation-card').textContent.includes('Conversación'),'complete-local-language-pack');assert(JSON.stringify(snapshot())===unchanged,'language-import-does-not-touch-projects');
  const nativeBuffer=File.prototype.arrayBuffer;let rejectFile;File.prototype.arrayBuffer=()=>new Promise((_,reject)=>rejectFile=reject);const pendingFile=new DataTransfer();pendingFile.items.add(new File(['pending'],'late.txt'));$('source-file').files=pendingFile.files;$('source-file').dispatchEvent(new Event('change'));await wait(()=>rejectFile);$('lock').click();const lockedFileStatus=$('status').textContent;rejectFile(Error('late file failure'));await sleep(40);File.prototype.arrayBuffer=nativeBuffer;assert($('status').textContent===lockedFileStatus&&snapshot().projects.length===0,'late-file-failure-cannot-change-locked-session-status');
  let rejectStatus;window.fetch=()=>new Promise((_,reject)=>rejectStatus=reject);$('check-model').click();await wait(()=>rejectStatus);$('lock').click();const lockedStatus=$('status').textContent;rejectStatus(Error('late network failure'));await sleep(40);assert($('status').textContent===lockedStatus&&snapshot().projects.length===0,'late-failure-cannot-change-locked-session-status');
  const transcript=$('messages');
  for(let i=0;i<3;i++){
   fill('message',('Long local turn '+i+' ').repeat(170));compose.click();
  }
  await wait(()=>transcript.scrollHeight>transcript.clientHeight&&
   transcript.scrollHeight-transcript.scrollTop-transcript.clientHeight<2);
  assert(transcript.scrollTop>0,'new-replies-reveal-latest-turn-in-long-transcript');
  transcript.scrollTop=0;fill('search','Long local turn');await sleep(40);
  assert(transcript.scrollTop===0,'unrelated-search-keeps-reader-position');
  const requests=[];
  window.fetch=async(url,options)=>{
   requests.push({url,options});
   const body=options.body?JSON.parse(options.body):null;
   if(!body)return new Response(JSON.stringify({connections:[{provider:'github',target:'example/nexus',configuration_id:'b'.repeat(64),branch_creation:true,file_commit:true}]}));
   if(url.includes('/github/file-')){
    const result={target:'example/nexus',branch:'nexus/studio-'+body.slug,path:body.path,base_sha:'a'.repeat(40)};
    if(url.endsWith('/file-base'))result.text='Before\n';
    if(url.endsWith('/file-preview'))Object.assign(result,{diff:'-Before\n+'+body.text,review_id:'c'.repeat(64),expires_at:2000000000});
    if(url.endsWith('/file-commit'))result.commit='d'.repeat(40);
    return new Response(JSON.stringify(result));
   }
   if(url.endsWith('/github/branch-preview'))return new Response(JSON.stringify({target:'example/nexus',
    branch:'nexus/studio-'+body.slug,base_sha:'a'.repeat(40),expires_at:2000000000,review_id:'c'.repeat(64)}));
   if(url.endsWith('/github/branch'))return new Response(JSON.stringify({target:'example/nexus',
    branch:'nexus/studio-'+body.slug,base_sha:body.base_sha,status:'created'}));
   return new Response(JSON.stringify({provider:'github',target:'example/nexus',operation:body.operation,
    provenance:'external-untrusted',result:{path:body.path,blob_sha:'a'.repeat(40),text:'Synthetic repository source'}}));
  };
  fill('gateway','https://synthetic-gateway.example');fill('gateway-token','synthetic-operator-token');
  const draft='Keep this draft while reading the repository';fill('message',draft);
  assert($('studio-connections-open').textContent==='Connections','connections-shortcut-keeps-its-label');
  $('studio-connections-open').click();
  assert($('studio-connections').open&&requests.length===0,'opening-connections-does-not-contact-gateway');
  $('studio-connections-load').click();
  const actions=$('studio-connections').querySelector('select');
  await wait(()=>actions.options.length===4);
  actions.value='github.file';actions.dispatchEvent(new Event('change',{bubbles:true}));
  const filePath=$('studio-connection-path');
  filePath.value='README.md';filePath.dispatchEvent(new Event('input',{bubbles:true}));
  assert($('studio-connections').textContent.includes('example/nexus / README.md')&&requests.length===1,
   'connection-target-and-path-visible-before-approved-read');
  $('studio-connections-read').click();
  await wait(()=>!$('studio-connections-use').hidden);
  assert(requests.length===2&&JSON.parse(requests[1].options.body).consent===true&&
   $('studio-connections').textContent.includes('Synthetic repository source'),'reviewed-result-is-visible');
  $('studio-connections-use').click();
  assert(!$('studio-connections').open&&$('message').value===draft&&
   $('chat-attachment-tray').textContent.includes('README.md')&&!NexusStudioUI.uiStatus().pendingReview&&requests.length===2,
   'selected-file-attachment-preserves-draft-and-does-not-call-model');
  await sleep(40);
  $('studio-connections-open').click();$('studio-connections-load').click();
  await wait(()=>actions.options.length===4);
  actions.value='github.branch';actions.dispatchEvent(new Event('change',{bubbles:true}));
  filePath.value='example-change';filePath.dispatchEvent(new Event('input',{bubbles:true}));
  const create=$('studio-connections-create');
  assert(create.hidden,'branch-write-hidden-until-preview');
  $('studio-connections-read').click();await wait(()=>!create.hidden);
  assert(requests.every(x=>!x.url.endsWith('/github/branch'))&&
   $('studio-connections').textContent.includes('main @ '+'a'.repeat(40)),
   'branch-preview-shows-exact-main-with-no-write');
  filePath.value='other-change';filePath.dispatchEvent(new Event('input',{bubbles:true}));
  assert(create.hidden,'changing-branch-name-clears-approval');
  $('studio-connections-read').click();await wait(()=>!create.hidden);
  create.click();await wait(()=>$('studio-connections').textContent.includes('Branch created'));
  const writes=requests.filter(x=>x.url.endsWith('/github/branch')).map(x=>JSON.parse(x.options.body));
  assert(writes.length===1&&writes[0].slug==='other-change'&&writes[0].base_sha==='a'.repeat(40)&&
   writes[0].consent===true&&$('message').value===draft,'separate-approval-creates-only-reviewed-branch');
  actions.value='github.edit';actions.dispatchEvent(new Event('change',{bubbles:true}));
  fill('studio-file-topic','other-change');fill('studio-connection-path','docs/intro.md');
  $('studio-connections-read').click();
  const editor=$('studio-file-editor');
  await wait(()=>!editor.hidden);
  assert(editor.value==='Before\n'&&create.hidden,'file-editor-loads-original-without-write');
  fill('studio-file-editor','After\n');
  window.confirm=()=>false;$('studio-connections-close').click();
  assert($('studio-connections').open&&editor.value==='After\n','declining-close-keeps-source-edit');
  window.confirm=()=>true;
  $('studio-file-preview').click();await wait(()=>!create.hidden);
  assert($('studio-connections').textContent.includes('-Before\n+After')&&
   requests.every(x=>!x.url.endsWith('/github/file-commit')),'review-shows-diff-before-commit');
  fill('studio-file-editor','Final edit\n');
  assert(create.hidden,'editing-text-invalidates-the-reviewed-diff');
  $('studio-file-preview').click();await wait(()=>!create.hidden);
  create.click();await wait(()=>$('studio-connections').textContent.includes('Commit created'));
  const writesToFile=requests.filter(x=>x.url.endsWith('/file-commit')).map(x=>JSON.parse(x.options.body));
  assert(writesToFile.length===1&&writesToFile[0].base_sha==='a'.repeat(40)&&
   writesToFile[0].consent===true&&writesToFile[0].text==='Final edit\n'&&$('message').value===draft,
   'file-commit-only-sends-the-independently-approved-text');
  $('studio-connections-close').click();

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
   if len(report['checks'])<MIN_CHECKS:raise RuntimeError('missing-witness-checks')
   reports.append({'layout':label,**report})
 print(json.dumps({'status':'PASS','reports':reports}))
if __name__=='__main__':main()
