import assert from 'node:assert/strict';
import '../web/studio-core.js';
const S=globalThis.NexusStudio;
// Controllable transaction events; real IndexedDB is covered by the browser witness.
function fixture(){
 const state={value:undefined,escaped:0,closed:0,writeFailure:false},store=new S.IndexedStore();
 store.db=async()=>({close(){state.closed++},transaction(){
  let aborted=false,staged=state.value;
  const tx={abort(){if(aborted)return;aborted=true;queueMicrotask(()=>tx.onabort?.())},objectStore(){return {
   get(){const request={result:state.value};queueMicrotask(()=>{
    try{request.onsuccess?.()}catch{state.escaped++;tx.abort()}
    queueMicrotask(()=>{if(!aborted){state.value=staged;tx.oncomplete?.()}});
   });return request},
   put(value){if(state.writeFailure)throw Error('PRIVATE_WRITE_ERROR');staged=value},
   delete(){staged=undefined}
  }}};return tx;
 }});
 return {store,state};
}
const pass='synthetic private passphrase 123',data=S.empty(),v=new S.Vault();
const raw=await v.export(data,pass),revision=JSON.parse(raw).revision;
let checks=0;
for(const damaged of ['',false,0,null,'{broken','{}',JSON.stringify({schema:S.SCHEMA})]){
 const {store,state}=fixture();state.value=damaged;
 await assert.rejects(store.read(),/archive-damaged/);checks++;
 await assert.rejects(store.commit(null,raw,()=>true),/archive-damaged/);checks++;
 assert.equal(state.value,damaged);assert.equal(state.escaped,0);assert.equal(state.closed,2);checks++;
}
const {store,state}=fixture();assert.equal(await store.read(),null);checks++;
await store.commit(null,raw,()=>true);assert.equal(await store.read(),raw);checks++;
await assert.rejects(store.commit('stale',null,()=>true),/conflict/);assert.equal(state.value,raw);checks++;
await assert.rejects(store.commit(revision,null,()=>false),/locked/);assert.equal(state.value,raw);checks++;
await assert.rejects(store.commit(revision,null,()=>{throw Error('PRIVATE_GUARD_ERROR')}),/storage/);assert.equal(state.escaped,0);checks++;
state.writeFailure=true;await assert.rejects(store.commit(revision,raw,()=>true),/storage/);assert.equal(state.value,raw);assert.equal(state.escaped,0);checks++;state.writeFailure=false;
const vault=new S.Vault(store);await vault.unlock(pass);state.value='{damaged';
await assert.rejects(vault.save(data),/archive-damaged/);assert.equal(state.value,'{damaged');checks++;
assert.deepEqual((await S.decrypt(await vault.export(data,pass),pass)).data,data);checks++;
state.value=raw;await vault.save(data);assert.notEqual(JSON.parse(state.value).revision,revision);checks++;
await vault.erase();assert.equal(state.value,undefined);assert.equal(vault.unlocked,false);checks++;
// Cancellation must be checked again at the actual destructive transaction.
const paused=fixture(),eraser=new S.Vault(paused.store);await eraser.create(pass);
const retained=paused.state.value,alreadyAborted=new AbortController();alreadyAborted.abort();
await assert.rejects(eraser.erase({signal:alreadyAborted.signal}),/cancelled/);assert.equal(paused.state.value,retained);checks++;
let entered,release;const started=new Promise(r=>entered=r),gate=new Promise(r=>release=r),commit=paused.store.commit.bind(paused.store);
paused.store.commit=async(...args)=>{if(args[1]===null){entered();await gate}return commit(...args)};
const abort=new AbortController(),erasing=eraser.erase({signal:abort.signal});await started;abort.abort();release();
await assert.rejects(erasing);assert.equal(paused.state.value,retained);assert.equal(eraser.unlocked,true);checks++;
paused.store.commit=commit;await eraser.save(data);await eraser.erase();assert.equal(paused.state.value,undefined);checks++;
console.log(JSON.stringify({status:'PASS',checks,scope:'synthetic-storage-faults',real_indexeddb_tested:false}));
