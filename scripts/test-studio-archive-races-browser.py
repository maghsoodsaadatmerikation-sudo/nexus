#!/usr/bin/env python3
"""Real archive cancellation before deletion and stale UI completion after deletion."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 14
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const S=NexusStudio,$=id=>document.getElementById(id),checks=[];
 const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<500;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const tick=()=>new Promise(r=>setTimeout(r,0)),snapshot=()=>JSON.stringify(NexusStudioUI.snapshot());
 const store=new S.IndexedStore(),pass='synthetic archive race passphrase 123';
 const commit=S.IndexedStore.prototype.commit,erase=S.Vault.prototype.erase;
 async function save(){ $('status').textContent='';$('save').click();await wait(()=>$('status').textContent.includes('session saved')) }
 async function create(){fill('passphrase',pass);fill('repeat-passphrase',pass);$('create-vault').click();await wait(()=>!$('save').disabled);await save()}
 function project(title){fill('project-title',title);$('new-project').click()}
 // Pause the result after the real delete has committed, not the deletion itself.
 function pauseResult(){
  let release,entered=false,settled=false;const gate=new Promise(r=>release=r);
  S.Vault.prototype.erase=async function(options){await erase.call(this,options);entered=true;await gate;settled=true};
  return {release,entered:()=>entered,settled:()=>settled};
 }
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};
  project('ORIGINAL SYNTHETIC PROJECT');$('new-thread').click();fill('message','Original question');$('guide').click();await create();
  const original=await store.read();assert(!!original&&!original.includes('Original question'),'initial-session-is-encrypted');
  let entered=false,settled=false,release;const gate=new Promise(r=>release=r);
  S.IndexedStore.prototype.commit=async function(...args){if(args[1]===null){entered=true;await gate}try{return await commit.apply(this,args)}finally{if(args[1]===null)settled=true}};
  $('erase').click();await wait(()=>entered);assert(!$('stop').disabled,'pending-erase-can-be-stopped');$('stop').click();
  project('NEW WORK BEFORE DELETE');const next=snapshot(),status=$('status').textContent;release();await wait(()=>settled);await tick();
  S.IndexedStore.prototype.commit=commit;
  assert(await store.read()===original,'stop-before-commit-preserves-exact-ciphertext');
  assert(snapshot()===next,'cancelled-delete-preserves-new-project');
  assert($('status').textContent===status,'cancelled-delete-does-not-overwrite-new-status');
  assert(!$('save').disabled,'cancelled-delete-keeps-vault-unlocked');await save();
  assert(!!await store.read(),'save-still-works-after-cancelled-delete');

  const clean=snapshot(),afterCommit=pauseResult();$('erase').click();await wait(afterCommit.entered);
  assert(await store.read()===null,'post-commit-fixture-observes-actual-deletion');$('stop').click();afterCommit.release();await wait(afterCommit.settled);await tick();
  assert(snapshot()===clean,'stop-after-commit-retains-open-session');
  assert($('save').disabled,'completed-delete-does-not-leave-an-unlocked-key');
  const closing=new Event('beforeunload',{cancelable:true});window.dispatchEvent(closing);
  assert(closing.defaultPrevented,'retained-session-is-marked-unsaved-after-delete');
  S.Vault.prototype.erase=erase;await create();
  assert(!!await store.read(),'retained-session-can-be-saved-in-a-new-vault');

  const later=pauseResult();$('erase').click();await wait(later.entered);$('stop').click();
  project('NEWER WORK AFTER DELETE');const newer=snapshot();fill('gateway','https://synthetic.invalid');
  let newerSignal;window.fetch=async(url,options)=>{newerSignal=options.signal;return await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Synthetic abort','AbortError')),{once:true}))};
  $('check-model').click();await wait(()=>newerSignal);later.release();await wait(later.settled);await tick();
  assert(snapshot()===newer,'late-erase-result-cannot-clear-newer-projects');
  assert($('new-project').disabled&&!newerSignal.aborted,'late-erase-cannot-cancel-newer-operation');
  $('stop').click();assert(newerSignal.aborted,'newer-abort-controller-survives-old-cleanup');await tick();
  S.Vault.prototype.erase=erase;
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_indexeddb_tested:true,real_model:false,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
 finally{S.IndexedStore.prototype.commit=commit;S.Vault.prototype.erase=erase}
});
"""

if __name__ == '__main__':
    module.main()
