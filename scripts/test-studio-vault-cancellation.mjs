import assert from 'node:assert/strict';
import '../web/studio-core.js';
const S=globalThis.NexusStudio,pass='synthetic private cancellation passphrase';let checks=0;
class Store{
 raw=null;
 async read(){return this.raw}
 async commit(expected,raw,guard){if(!guard())throw Error('locked');if((this.raw?JSON.parse(this.raw).revision:null)!==expected)throw Error('conflict');this.raw=raw}
}
const initial=S.empty(),changed=S.state({schema:S.SCHEMA,projects:[S.project('Synthetic newer work')]}),store=new Store(),vault=new S.Vault(store);
await vault.create(pass);await vault.save(initial);const original=store.raw;vault.lock();
const cancelled=new AbortController();cancelled.abort();
for(const action of [()=>vault.unlock(pass,{signal:cancelled.signal}),()=>vault.export(changed,pass,{signal:cancelled.signal}),()=>S.decrypt(original,pass,{signal:cancelled.signal})]){
 await assert.rejects(action,/cancelled/);assert.equal(vault.unlocked,false);checks++;
}
let entered,release;const gate=new Promise(r=>release=r),started=new Promise(r=>entered=r),read=store.read.bind(store);
store.read=async()=>{entered();await gate;return read()};
const abortUnlock=new AbortController(),opening=vault.unlock(pass,{signal:abortUnlock.signal});await started;abortUnlock.abort();release();
await assert.rejects(opening,/cancelled/);assert.equal(vault.unlocked,false);assert.equal(vault.raw,null);checks++;
store.read=read;await vault.unlock(pass);assert.equal(vault.unlocked,true);checks++;

async function beforeCommit(vault,store,action){
 const raw=store.raw,commit=store.commit.bind(store);let entered,release;
 const started=new Promise(r=>entered=r),gate=new Promise(r=>release=r),abort=new AbortController();
 store.commit=async(...args)=>{entered();await gate;return commit(...args)};
 const pending=action(abort.signal);await started;abort.abort();release();await assert.rejects(pending);
 assert.equal(store.raw,raw);store.commit=commit;checks++;
}
await beforeCommit(vault,store,signal=>vault.save(changed,{signal}));assert.equal(vault.raw,original);assert.equal(vault.unlocked,true);checks++;
await vault.save(changed);assert.deepEqual((await S.decrypt(store.raw,pass)).data,changed);checks++;
const freshStore=new Store(),fresh=new S.Vault(freshStore);
await assert.rejects(fresh.create(pass,{signal:cancelled.signal}),/cancelled/);assert.equal(freshStore.raw,null);checks++;
await beforeCommit(fresh,freshStore,signal=>fresh.create(pass,{signal}));assert.equal(fresh.unlocked,false);checks++;
await fresh.create(pass);assert.equal(fresh.unlocked,true);checks++;

// If a save already committed, retain the actual revision so a later save is safe.
const commit=store.commit.bind(store),afterSave=new AbortController();
store.commit=async(...args)=>{await commit(...args);afterSave.abort()};
await vault.save(initial,{signal:afterSave.signal});assert.equal(vault.raw,store.raw);checks++;
store.commit=commit;await vault.save(changed);assert.deepEqual((await S.decrypt(store.raw,pass)).data,changed);checks++;
// A cancelled create that already committed must not install an unseen unlocked key.
const committedStore=new Store(),committedVault=new S.Vault(committedStore),afterCreate=new AbortController(),createCommit=committedStore.commit.bind(committedStore);
committedStore.commit=async(...args)=>{await createCommit(...args);afterCreate.abort()};
await assert.rejects(committedVault.create(pass,{signal:afterCreate.signal}),/cancelled/);
assert(committedStore.raw);assert.equal(committedVault.unlocked,false);checks++;
committedStore.commit=createCommit;await committedVault.unlock(pass);assert.equal(committedVault.unlocked,true);checks++;
// Cancellation belongs to one command, not a newer explicit Unlock queued behind it.
const queuedStore=new Store(),queuedVault=new S.Vault(queuedStore),queuedAbort=new AbortController(),queuedCommit=queuedStore.commit.bind(queuedStore);
let committed,finish;const committedGate=new Promise(r=>committed=r),finishGate=new Promise(r=>finish=r);
queuedStore.commit=async(...args)=>{await queuedCommit(...args);queuedAbort.abort();committed();await finishGate};
const cancelledCreation=queuedVault.create(pass,{signal:queuedAbort.signal});await committedGate;
const newerUnlock=queuedVault.unlock(pass);finish();await assert.rejects(cancelledCreation,/cancelled/);await newerUnlock;
assert.equal(queuedVault.unlocked,true);checks++;
const deletedStore=new Store(),deletedVault=new S.Vault(deletedStore),deletedAbort=new AbortController();await deletedVault.create(pass);
const deleteCommit=deletedStore.commit.bind(deletedStore);let deleted,finishDelete;
const deletedGate=new Promise(r=>deleted=r),finishDeleteGate=new Promise(r=>finishDelete=r);
deletedStore.commit=async(...args)=>{await deleteCommit(...args);if(args[1]===null){deletedAbort.abort();deleted();await finishDeleteGate}};
const cancelledDelete=deletedVault.erase({signal:deletedAbort.signal});await deletedGate;
const newerCreate=deletedVault.create(pass);finishDelete();await cancelledDelete;await newerCreate;
assert.equal(deletedVault.unlocked,true);assert(deletedStore.raw);checks++;
console.log(JSON.stringify({status:'PASS',checks,scope:'vault-cancellation-and-commit-boundaries',real_indexeddb_tested:false}));
