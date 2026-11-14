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
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_indexeddb_tested:true,network_requests:0,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
});
"""

if __name__ == '__main__':
    module.main()
