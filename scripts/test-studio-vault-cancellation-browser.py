#!/usr/bin/env python3
"""Actual IndexedDB and crypto: cancelled vault work cannot adopt keys or stale data."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 20
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const S=NexusStudio,$=id=>document.getElementById(id),checks=[],pass='synthetic vault cancellation passphrase';
 const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 const wait=async fn=>{for(let i=0;i<500;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const tick=()=>new Promise(r=>setTimeout(r,0)),snapshot=()=>JSON.stringify(NexusStudioUI.snapshot());
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const project=name=>{fill('project-title',name);$('new-project').click()};
 const credentials=()=>{fill('passphrase',pass);fill('repeat-passphrase',pass)};
 const store=new S.IndexedStore(),commit=S.IndexedStore.prototype.commit,read=S.IndexedStore.prototype.read;
 const encrypt=crypto.subtle.encrypt,importKey=crypto.subtle.importKey,fileText=File.prototype.text,unlock=S.Vault.prototype.unlock;
 const downloads=[];HTMLAnchorElement.prototype.click=function(){downloads.push(this.download)};
 function latch(){let entered=false,settled=false,release;const gate=new Promise(r=>release=r);return {release,entered:()=>entered,settled:()=>settled,pause:async()=>{entered=true;await gate},finish:()=>settled=true}}
 function pauseCommit(){const l=latch();S.IndexedStore.prototype.commit=async function(...args){await l.pause();try{return await commit.apply(this,args)}finally{l.finish()}};return l}
 async function save(){$('status').textContent='';$('save').click();await wait(()=>$('status').textContent.includes('session saved'))}
 function restore(raw){const dt=new DataTransfer();dt.items.add(new File([raw],'synthetic.encrypted.json',{type:'application/json'}));$('restore-file').files=dt.files;$('restore-file').dispatchEvent(new Event('change'))}
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};
  project('ORIGINAL SYNTHETIC PROJECT');$('new-thread').click();fill('message','Original retained question');$('guide').click();
  const creating=pauseCommit();credentials();$('create-vault').click();await wait(creating.entered);$('stop').click();project('NEW WORK AFTER CREATE STOP');const afterCreate=snapshot();
  creating.release();await wait(creating.settled);await tick();S.IndexedStore.prototype.commit=commit;
  assert(await store.read()===null,'cancelled-create-does-not-write-an-archive');
  assert($('save').disabled,'cancelled-create-does-not-install-a-key');assert(snapshot()===afterCreate,'cancelled-create-retains-newer-work');
  credentials();$('create-vault').click();await wait(()=>!$('save').disabled);await save();let raw=await store.read();const saved=snapshot();
  assert(!!raw&&!raw.includes('Original retained question'),'retry-create-and-save-is-encrypted');

  $('lock').click();const opening=latch();let once=true,unlockSettled=false;
  S.Vault.prototype.unlock=async function(...args){try{return await unlock.apply(this,args)}finally{unlockSettled=true}};
  S.IndexedStore.prototype.read=async function(){if(once){once=false;await opening.pause();try{return await read.call(this)}finally{opening.finish()}}return read.call(this)};
  credentials();$('unlock').click();await wait(opening.entered);$('stop').click();project('NEW WORK AFTER UNLOCK STOP');const afterUnlock=snapshot();
  opening.release();await wait(()=>unlockSettled);await tick();S.IndexedStore.prototype.read=read;S.Vault.prototype.unlock=unlock;
  assert($('save').disabled,'stopped-unlock-cannot-enable-hidden-archive-overwrite');
  assert(snapshot()===afterUnlock,'stopped-unlock-cannot-replace-newer-work');assert(await store.read()===raw,'stopped-unlock-retains-exact-ciphertext');
  credentials();$('unlock').click();await wait(()=>!$('save').disabled);assert(snapshot()===saved,'explicit-unlock-retry-restores-original-session');

  project('BEFORE SAVE STOP');const saving=pauseCommit();$('save').click();await wait(saving.entered);$('stop').click();project('AFTER SAVE STOP');const afterSave=snapshot();
  saving.release();await wait(saving.settled);await tick();S.IndexedStore.prototype.commit=commit;
  assert(await store.read()===raw,'stopped-save-before-commit-preserves-previous-ciphertext');assert(snapshot()===afterSave,'stopped-save-retains-newer-work');
  assert($('retention').textContent.includes('unsaved'),'stopped-save-does-not-claim-new-work-was-saved');
  await save();raw=await store.read();assert(JSON.stringify((await S.decrypt(raw,pass)).data)===afterSave,'save-retry-persists-the-current-session');

  const backing=latch();crypto.subtle.encrypt=async function(...args){const result=await encrypt.apply(this,args);await backing.pause();backing.finish();return result};
  credentials();$('backup').click();await wait(backing.entered);$('stop').click();project('AFTER BACKUP STOP');const afterBackup=snapshot();
  backing.release();await wait(backing.settled);await tick();crypto.subtle.encrypt=encrypt;
  assert(downloads.length===0,'cancelled-backup-never-downloads-a-file');assert(snapshot()===afterBackup,'cancelled-backup-retains-newer-work');assert(await store.read()===raw,'cancelled-backup-does-not-change-storage');

  const restored=S.state({schema:S.SCHEMA,projects:[S.project('SYNTHETIC RESTORED PROJECT')]}),backup=await new S.Vault().export(restored,pass),restoring=latch();let keyImports=0;
  File.prototype.text=async function(){await restoring.pause();restoring.finish();return backup};
  crypto.subtle.importKey=function(...args){keyImports++;return importKey.apply(this,args)};
  credentials();restore(backup);await wait(restoring.entered);$('stop').click();project('AFTER RESTORE STOP');const afterRestore=snapshot(),status=$('status').textContent;
  restoring.release();await wait(restoring.settled);await tick();File.prototype.text=fileText;crypto.subtle.importKey=importKey;
  assert(keyImports===0,'cancelled-file-read-does-not-start-decryption');assert(snapshot()===afterRestore,'cancelled-restore-retains-newer-work');
  assert($('status').textContent===status,'cancelled-restore-cannot-replace-newer-status');assert(await store.read()===raw,'cancelled-restore-preserves-browser-archive');
  credentials();restore(backup);await wait(()=>snapshot()===JSON.stringify(restored));assert($('retention').textContent.includes('unsaved'),'successful-restore-remains-an-explicit-unsaved-session');
  assert(await store.read()===raw,'successful-restore-does-not-silently-replace-the-stored-archive');
  await save();assert(JSON.stringify((await S.decrypt(await store.read(),pass)).data)===JSON.stringify(restored),'explicit-save-persists-restored-data');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_indexeddb_tested:true,real_crypto_tested:true,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
 finally{S.Vault.prototype.unlock=unlock;S.IndexedStore.prototype.commit=commit;S.IndexedStore.prototype.read=read;crypto.subtle.encrypt=encrypt;crypto.subtle.importKey=importKey;File.prototype.text=fileText}
});
"""

if __name__ == '__main__':
    module.main()
