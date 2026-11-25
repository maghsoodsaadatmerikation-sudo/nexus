#!/usr/bin/env python3
"""Real IndexedDB: damaged records cannot be mistaken for an absent archive."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 20
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const S=NexusStudio,checks=[],assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const store=new S.IndexedStore(),vault=new S.Vault(store),pass='synthetic storage passphrase 123';
 const escaped=[];window.addEventListener('error',event=>{escaped.push(event.message);event.preventDefault()});
 async function fails(promise,code){try{await promise}catch(error){if(error.message===code)return;throw error}throw Error('missing-'+code)}
 async function direct(write,value){const db=await store.db();try{return await new Promise((resolve,reject)=>{
  const tx=db.transaction('vault',write?'readwrite':'readonly'),s=tx.objectStore('vault');let found;
  if(write)s.put(value,'archive');else{const r=s.get('archive');r.onsuccess=()=>found=r.result}
  tx.oncomplete=()=>resolve(found);tx.onabort=()=>reject(Error('fixture-storage'));
 })}finally{db.close()}}
 const $=id=>document.getElementById(id),fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};
  assert(await store.read()===null,'absent-key-is-an-empty-store');
  const project=S.project('SYNTHETIC PRIVATE STORAGE PROJECT');project.threads=[S.append(S.thread('Chat'),'user','SYNTHETIC PRIVATE QUESTION','human')];
  const data=S.state({schema:S.SCHEMA,projects:[project]});await vault.create(pass);await vault.save(data);let raw=await direct(false);
  assert(!raw.includes('SYNTHETIC PRIVATE'),'only-ciphertext-persisted');
  for(const [i,damaged] of ['',false,0,null,'{broken','{}',JSON.stringify({schema:S.SCHEMA})].entries()){
   await direct(true,damaged);await fails(store.read(),'archive-damaged');
   await fails(vault.save(data),'archive-damaged');await fails(vault.erase(),'archive-damaged');
   assert(await direct(false)===damaged,'damaged-record-'+i+'-is-preserved-after-read-save-erase');
   const backup=await vault.export(data,pass);assert(JSON.stringify((await S.decrypt(backup,pass)).data)===JSON.stringify(data),'damaged-record-'+i+'-does-not-prevent-encrypted-backup');
   await direct(true,raw);await vault.save(data);raw=await direct(false);
  }
  assert(escaped.length===0,'validation-failures-do-not-escape-transaction-callbacks');
  const revision=JSON.parse(raw).revision;
  await fails(store.commit(revision,null,()=>false),'locked');assert(await direct(false)===raw,'lock-guard-preserves-archive');
  await fails(store.commit(revision,null,()=>{throw Error('PRIVATE_GUARD_ERROR')}),'storage');assert(await direct(false)===raw,'throwing-guard-is-contained');
  const put=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=()=>{throw new DOMException('SYNTHETIC_WRITE_FAILURE','QuotaExceededError')};
  try{await fails(vault.save(data),'storage')}finally{IDBObjectStore.prototype.put=put}
  assert(await direct(false)===raw,'write-failure-preserves-last-ciphertext');await vault.save(data);raw=await direct(false);
  assert(raw&&raw!==null,'queue-recovers-after-write-failure');
  const other=new S.Vault(store);await other.unlock(pass);await vault.save(data);const saved=await direct(false);await fails(other.save(data),'conflict');
  assert(!other.unlocked&&await direct(false)===saved,'stale-tab-cannot-overwrite-newer-save');
  fill('project-title','UNSAVED UI PROJECT');$('new-project').click();const before=JSON.stringify(NexusStudioUI.snapshot());
  await direct(true,'');fill('passphrase',pass);fill('repeat-passphrase',pass);$('create-vault').click();await wait(()=>$('status').textContent.includes('damaged'));
  assert(await direct(false)===''&&JSON.stringify(NexusStudioUI.snapshot())===before,'failed-create-preserves-damaged-record-and-open-session');
  $('language').value='fa';$('language').dispatchEvent(new Event('change'));fill('passphrase',pass);$('unlock').click();await wait(()=>$('status').textContent.includes('آسیب'));
  assert(JSON.stringify(NexusStudioUI.snapshot())===before,'persian-recovery-message-retains-open-work');
  assert(escaped.length===0,'no-unhandled-storage-events');
  await direct(true,saved);await vault.erase();assert(await store.read()===null,'healthy-archive-can-still-be-erased');
  const oldTime=Date.now()-40*86400000;
  const old=S.append(S.thread('Expired chat'),'user','EXPIRED SAMPLE','human');
  old.last_activity=oldTime;
  const recent=S.append(S.thread('Recently active'),'user','RECENT SAMPLE','human');
  recent.last_activity=oldTime+20*86400000;
  const legacy=S.thread('Legacy chat');
  const retainedProject={...project,threads:[old,recent,legacy],experiences:[{project_id:project.id,workflow_id:'w1',revision:1,entries:[{correction_code:'synthetic_reviewed_fix',criterion_id:'s1',status:'active',supporting_pair_count:2}]}]};
  await vault.create(pass);
  await vault.save({schema:S.SCHEMA,projects:[retainedProject],history_days:30},{now:recent.last_activity});
  const beforePurge=await store.read();
  vault.lock();
  const retained=await vault.unlock(pass);
  assert(retained.projects[0].threads.map(t=>t.id).join()===recent.id+','+legacy.id,'expired-conversation-removed-on-unlock');
  const afterPurge=await store.read();
  assert(beforePurge!==afterPurge&&!(await S.decrypt(afterPurge,pass)).data.projects[0].threads.some(t=>t.id===old.id),
   'expiry-rewrites-encrypted-history');
  assert(Number.isSafeInteger(retained.projects[0].threads[1].last_activity),'legacy-retention-clock-initialized');
  assert(retained.projects[0].sources.length===retainedProject.sources.length,'expiry-keeps-project-material');

  $('language').value='en';$('language').dispatchEvent(new Event('change'));
  fill('passphrase',pass);$('unlock').click();await wait(()=>$('history-days').value==='30'&&!$('save').disabled);
  assert(!$('training-opt-in').checked&&$('training-review').disabled,'retaining-history-does-not-authorize-training');
  const experience=$('stored-experience-panel');
  assert(experience&&!experience.hidden&&experience.textContent.includes('synthetic_reviewed_fix'),'unlocked-project-shows-stored-review');
  experience.open=true;
  const beforeExperience=await store.read();
  window.confirm=()=>false;experience.querySelector('button').click();
  assert(NexusStudioUI.snapshot().projects[0].experiences[0].entries[0].status==='active','declined-revocation-preserves-experience');
  window.confirm=()=>true;experience.querySelector('button').click();
  assert(NexusStudioUI.snapshot().projects[0].experiences[0].entries[0].status==='revoked','revocation-applies-in-session');
  assert(await store.read()===beforeExperience,'revocation-does-not-autosave');
  $('save').click();await wait(()=>$('status').textContent.includes('encrypted data')&&!$('save').disabled);
  assert((await S.decrypt(await store.read(),pass)).data.projects[0].experiences[0].entries[0].status==='revoked','explicit-save-persists-revocation');
  experience.querySelector('button').click();
  assert(experience.hidden&&NexusStudioUI.snapshot().projects[0].experiences[0].entries.length===0,'delete-removes-entry-and-hides-empty-panel');
  $('save').click();await wait(()=>$('status').textContent.includes('encrypted data')&&!$('save').disabled);
  assert((await S.decrypt(await store.read(),pass)).data.projects[0].experiences[0].entries.length===0,'explicit-save-persists-removal');
  const importPanel=$('experience-import-panel');
  assert(importPanel&&!importPanel.hidden,'empty-experience-list-allows-report-import');
  const reportRun=(run,result)=>{const scope={project_id:project.id,workflow_id:'w1',run_id:run,plan_sha256:'a'.repeat(64)};return {scope,observations:[{...scope,evidence_id:run+'-private-evidence',criterion_id:'s1',kind:'human_review',result}]}};
  const report={schema:'nexus.experience-review.v1',workflow_id:'w1',operation:{kind:'accept',criterion_id:'s1',correction_code:'new_reviewed_fix'},criteria:[{id:'s1',required:true,evidence_kind:'human_review'}],attempts:[1,2].map(i=>({correction_code:'new_reviewed_fix',before:reportRun('before'+i,'fail'),after:reportRun('after'+i,'pass')}))};
  const importFile=()=>{const input=$('experience-import-file'),transfer=new DataTransfer();transfer.items.add(new File([JSON.stringify(report)],'review.json',{type:'application/json'}));input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));};
  const beforeImport=await store.read();
  let confirms=0;window.confirm=()=>{confirms++;return false};
  importFile();await wait(()=>confirms===1&&!$('experience-import-file').disabled);
  assert(NexusStudioUI.snapshot().projects[0].experiences[0].entries.length===0,'declined-import-retains-empty-snapshot');
  window.confirm=()=>true;importFile();
  await wait(()=>NexusStudioUI.snapshot().projects[0].experiences[0].entries.some(e=>e.correction_code==='new_reviewed_fix'));
  assert(await store.read()===beforeImport,'accepted-import-does-not-autosave');
  assert(!JSON.stringify(NexusStudioUI.snapshot()).includes('private-evidence'),'import-retains-metadata-not-raw-evidence');
  $('save').click();await wait(()=>$('status').textContent.includes('encrypted data')&&!$('save').disabled);
  assert((await S.decrypt(await store.read(),pass)).data.projects[0].experiences[0].entries[0].correction_code==='new_reviewed_fix','explicit-save-persists-import');
  // Direct session handoff uses the same review engine without a file.
  const directReport={...report,operation:{...report.operation,correction_code:'direct_fixture'},attempts:report.attempts.map((a,i)=>({...a,correction_code:'direct_fixture',before:reportRun('direct-private-before'+i,'fail'),after:reportRun('direct-private-after'+i,'pass')}))};
  const directBefore=await store.read(),directSelection=NexusStudioUI.selection(),directState=JSON.stringify(NexusStudioUI.snapshot());
  let directConfirms=0;
  window.confirm=()=>{directConfirms++;return false};
  assert(applyChatExperienceReport(directReport,directSelection)==='declined','direct-consent-declined');
  assert(directConfirms===1&&await store.read()===directBefore&&JSON.stringify(NexusStudioUI.snapshot())===directState,'direct-decline-preserves-state-and-ciphertext');
  window.confirm=()=>{directConfirms++;return true};
  assert(applyChatExperienceReport(directReport,{...directSelection,revision:directSelection.revision-1})==='unavailable','direct-stale-session-refused');
  assert(applyChatExperienceReport(directReport,{...directSelection,head:'different-head'})==='unavailable','direct-stale-head-refused');
  assert(applyChatExperienceReport({...directReport,workflow_id:'foreign-workflow'},directSelection)==='rejected','direct-inconsistent-report-refused');
  assert(directConfirms===1&&JSON.stringify(NexusStudioUI.snapshot())===directState&&await store.read()===directBefore,'invalid-direct-handoff-never-prompts-or-mutates');
  assert(applyChatExperienceReport(directReport,directSelection)==='applied','direct-session-apply');
  assert(directConfirms===2&&await store.read()===directBefore,'direct-does-not-autosave');
  assert(NexusStudioUI.snapshot().projects[0].experiences[0].entries.some(e=>e.correction_code==='direct_fixture'),'direct-metadata-visible');
  assert(!JSON.stringify(NexusStudioUI.snapshot()).includes('direct-private-'),'direct-raw-receipts-not-retained');
  const directAppliedState=JSON.stringify(NexusStudioUI.snapshot());
  assert(applyChatExperienceReport(directReport,directSelection)==='unavailable','direct-consumed-selection-refused');
  assert(directConfirms===2&&JSON.stringify(NexusStudioUI.snapshot())===directAppliedState&&await store.read()===directBefore,'direct-replay-never-prompts-or-mutates');
  $('save').click();await wait(()=>$('status').textContent.includes('encrypted data')&&!$('save').disabled);
  assert((await S.decrypt(await store.read(),pass)).data.projects[0].experiences[0].entries.some(e=>e.correction_code==='direct_fixture'),'direct-explicit-save');
  // The exact chat report must match the active archive and current failure.
  const recallSteps=['fail','pass'].map((verdict,i)=>({command:'code',criterion:'Check '+i,opened:true,acknowledged:true,observed:'succeeded',verdict}));
  const recallHash='b'.repeat(64),recallRounds=[1,2,3,4].map(round=>({round,steps:recallSteps.map((s,i)=>({...s,verdict:i===0&&round%2?'fail':'pass'}))}));
  const recalledReport=experienceImportEngine.buildChatExperienceReport(recallRounds,{project_id:project.id,plan_sha256:recallHash,session_id:'old-report',correction_code:'recall_fixture',criterion_id:'s1',kind:'accept',same_correction_reported:true,complete_relevant_history_reported:true},{enabled:true}).report;
  assert(recalledReport&&applyChatExperienceReport(recalledReport,NexusStudioUI.selection())==='applied','recall-fixture-retained');
  const recallContext=chatArchiveRecallContext(),recallArgs={sessionId:'current-report',round:1,planHash:recallHash,steps:recallSteps};
  const recallBefore=JSON.stringify(NexusStudioUI.snapshot()),recallCipher=await store.read();
  const recalled=recallChatExperienceReport(JSON.stringify(recalledReport),recallContext,recallArgs);
  assert(recalled.matches.length===1&&recalled.matches[0].correction_code==='recall_fixture','exact-chat-recall-matches');
  assert(!recalled.execution_authorized&&!recalled.model_context_authorized&&!recalled.storage_authorized,'recall-no-authority');
  assert(JSON.stringify(NexusStudioUI.snapshot())===recallBefore&&await store.read()===recallCipher,'recall-does-not-mutate-or-save');
  assert(recallChatExperienceReport(JSON.stringify(recalledReport),{...recallContext,revision:recallContext.revision-1},recallArgs).status==='unavailable','stale-recall-refused');
  const noFailure=recallChatExperienceReport(JSON.stringify(recalledReport),recallContext,{...recallArgs,steps:recallSteps.map(s=>({...s,verdict:'pass'}))});
  assert(noFailure.status==='no_reported_failure'&&!noFailure.matches.length,'passing-round-does-not-recall');
  const alternative=experienceImportEngine.buildChatExperienceReport(recallRounds,{project_id:project.id,plan_sha256:recallHash,session_id:'alternative-report',correction_code:'alt_fixture',criterion_id:'s1',kind:'accept',same_correction_reported:true,complete_relevant_history_reported:true},{enabled:true}).report;
  assert(alternative&&applyChatExperienceReport(alternative,NexusStudioUI.selection())==='applied','alternative-retained');
  const comparisonContext=chatArchiveRecallContext(),comparisonBefore=JSON.stringify(NexusStudioUI.snapshot()),comparisonCipher=await store.read();
  const option=(correction_code,cost_usd_cents,effort_minutes)=>({correction_code,cost_usd_cents,effort_minutes,risk:'low',reversible:true});
  const comparison={criterion_id:'s1',max_cost_usd_cents:100,max_effort_minutes:60,options:[option('recall_fixture',0,20),option('alt_fixture',50,10)]};
  const scenario={criterion_id:'s1',options:[{correction_code:'recall_fixture',cost_usd_cents:{best:0,expected:0,worst:90},effort_minutes:{best:10,expected:20,worst:30},rollback:{cost_usd_cents:20,effort_minutes:10,trigger:'check fails',restore_check:'verify restore'}}]};
  const selectedReports=[JSON.stringify(recalledReport),JSON.stringify(alternative)];
  const compared=compareChatExperienceReports(selectedReports,comparisonContext,recallArgs,comparison,scenario);
  assert(compared.status==='review_only'&&compared.comparison.options.every(o=>o.status==='tradeoff_candidate'),'live-host-comparison');
  assert(compared.scenarios.options[0].status==='rollback_reserve_outside_limits','live-host-rollback-reserve');
  assert(!compared.execution_authorized&&!compared.model_context_authorized&&!compared.storage_authorized,'comparison-no-authority');
  assert(JSON.stringify(NexusStudioUI.snapshot())===comparisonBefore&&await store.read()===comparisonCipher,'comparison-no-mutation');
  assert(compareChatExperienceReports(selectedReports,recallContext,recallArgs,comparison,scenario).status==='unavailable','comparison-rejects-stale-context');

  $('history-days').value='0';$('history-days').dispatchEvent(new Event('change',{bubbles:true}));
  $('save').click();await wait(()=>$('status').textContent.includes('encrypted data')&&!$('save').disabled);
  const off=(await S.decrypt(await store.read(),pass)).data;
  assert(off.history_days===0&&off.projects[0].threads.length===0&&off.projects[0].id===project.id,'history-off-only-removes-chat-from-ciphertext');
  assert(NexusStudioUI.snapshot().projects[0].threads.some(t=>t.id===recent.id),'temporary-chat-remains-available');
  $('training-opt-in').click();$('training-review').click();
  const review=JSON.parse($('training-preview').textContent);
  assert(review.messages.length===1&&review.messages[0].text==='RECENT SAMPLE','training-review-works-with-history-off');
  $('training-opt-in').click();
  assert($('training-preview').hidden&&$('training-download').hidden&&!$('training-preview').textContent,'withdrawal-clears-training-review');
  $('new-thread').click();
  fill('message','TEMPORARY MESSAGE');$('guide').click();
  assert(!$('message').value&&NexusStudioUI.snapshot().projects[0].threads.at(-1).temporary===true,
   'new-conversation-while-history-off-is-tab-only');
  $('history-days').value='';$('history-days').dispatchEvent(new Event('change',{bubbles:true}));
  $('save').click();await wait(()=>$('status').textContent.includes('encrypted data')&&!$('save').disabled);
  assert((await S.decrypt(await store.read(),pass)).data.projects[0].threads.length===0,'re-enabling-history-does-not-save-temporary-conversations');
  $('training-opt-in').click();$('training-review').click();
  assert(!$('training-preview').hidden&&$('training-preview').textContent.includes('TEMPORARY MESSAGE'),'review-binds-to-current-branch');
  const createURL=URL.createObjectURL,clickAnchor=HTMLAnchorElement.prototype.click;
  let downloaded;
  try{
   URL.createObjectURL=blob=>{downloaded=blob;return 'blob:synthetic-training-download'};
   HTMLAnchorElement.prototype.click=()=>{};
   window.confirm=()=>false;$('training-download').click();
   assert(!downloaded,'declined-training-download-does-not-export');
   window.confirm=()=>true;$('training-download').click();
   assert(downloaded&&await downloaded.text()===$('training-preview').textContent,'training-download-matches-reviewed-text');
  }finally{URL.createObjectURL=createURL;HTMLAnchorElement.prototype.click=clickAnchor;window.confirm=()=>true}
  $('lock').click();
  assert(!$('training-opt-in').checked&&$('training-preview').hidden&&!$('training-preview').textContent,'locking-revokes-training-opt-in');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_indexeddb_tested:true,network_requests:0,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
});
"""

if __name__ == '__main__':
    module.main()
