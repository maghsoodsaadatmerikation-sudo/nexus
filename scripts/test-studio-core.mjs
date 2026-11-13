import assert from 'node:assert/strict';
import '../web/studio-core.js';
const S=globalThis.NexusStudio;let checks=0;
const ok=(f)=>{f();checks++},reject=async(f)=>{await assert.rejects(f);checks++};
const p=S.project('Project'),initial=S.thread('Thread');p.threads=[initial];let c=S.append(initial,'user','original question','human');c=S.append(c,'assistant','original draft','model');const original=S.copy(c);const edited=S.append(c,'user','edited question','human',null);const branch=S.append(edited,'assistant','alternative answer','model');
ok(()=>assert.deepEqual(c,original));ok(()=>assert.equal(S.path(branch).length,2));ok(()=>assert.equal(branch.nodes.length,4));ok(()=>assert.equal(S.path(branch,original.head)[1].text,'original draft'));
ok(()=>assert.throws(()=>S.append(initial,'assistant','forged','human')));ok(()=>assert.throws(()=>S.append(initial,'assistant','orphan','model')));ok(()=>assert.throws(()=>S.append(c,'user','bad','human','missing')));
p.threads=[branch];let v={schema:S.SCHEMA,projects:[p]};ok(()=>assert.deepEqual(S.state(v),v));
for(const change of [x=>x.schema='future',x=>x.projects[0].threads[0].nodes[0].parent=x.projects[0].threads[0].nodes[0].id,x=>x.projects[0].threads.push(x.projects[0].threads[0]),x=>x.projects[0].threads[0].nodes[1].origin='human']){const b=S.copy(v);change(b);ok(()=>assert.throws(()=>S.state(b)))}
p.memories=['PRIVATE-MEMORY'];p.instructions='concise';p.sources=[{id:S.uid(),name:'source.txt',text:'The orchard has green trees.\nA project uses public sources.'}];let candidate=S.append(branch,'user','orchard trees','human');
ok(()=>assert(!JSON.stringify(S.context(p,candidate)).includes('PRIVATE-MEMORY')));ok(()=>assert(JSON.stringify(S.context(p,candidate,{memory:true})).includes('PRIVATE-MEMORY')));ok(()=>assert.equal(S.context(p,candidate,{sources:true}).citations[0].line,1));ok(()=>assert.equal(S.retrieve(p,'unmatched').length,0));ok(()=>assert.equal(S.retrieve(S.project('other'),'orchard').length,0));
p.threads=[branch];v={schema:S.SCHEMA,projects:[p]};ok(()=>assert.equal(S.search(v,'original question').length,1));p.threads[0].archived=true;ok(()=>assert.equal(S.search(v,'original').length,0));ok(()=>assert.equal(S.search(v,'original',true).length,1));p.threads[0].archived=false;
ok(()=>assert(S.guide('hello').includes('not a generative model')));ok(()=>assert(S.guide('سلام',true).includes('مدل مولد نیست')));
let long=S.thread('Long');for(let i=0;i<30;i++){long=S.append(long,'user','turn '+i,'human');long=S.append(long,'assistant','draft '+i,'model')}long=S.append(long,'user','final question','human');const bounded=S.context(S.project('Long project'),long);ok(()=>assert(bounded.messages.length<=42&&bounded.omitted_messages>0));ok(()=>assert.equal(bounded.messages.at(-1).content,'final question'));
const pass='long private passphrase 123';
class Store{raw=null;async read(){return this.raw}async commit(expected,raw,guard){if(!guard())throw Error('locked');if((this.raw?JSON.parse(this.raw).revision:null)!==expected)throw Error('conflict');this.raw=raw}}
const store=new Store(),a=new S.Vault(store);await a.create(pass);checks++;await a.save(v);checks++;ok(()=>assert(!store.raw.includes('PRIVATE-MEMORY')));const raw=await a.export(v,pass);checks++;const opened=await S.decrypt(raw,pass);ok(()=>assert.deepEqual(opened.data,S.state(v)));await reject(()=>S.decrypt(raw,'wrong passphrase long'));const env=JSON.parse(raw);env.revision=S.uid();await reject(()=>S.decrypt(JSON.stringify(env),pass));
a.lock();ok(()=>assert.equal(a.key,null));ok(()=>assert.equal(a.data,null));await reject(()=>a.save(v));
const b=new S.Vault(store),d=new S.Vault(store);await b.unlock(pass);await d.unlock(pass);await b.save(v);await reject(()=>d.save(v));ok(()=>assert.equal(d.unlocked,false));
let resume;const gate=new Promise(r=>resume=r);const delayed=new Store();const old=delayed.commit.bind(delayed);delayed.commit=async(...args)=>{await gate;return old(...args)};const e=new S.Vault(delayed);const creation=e.create(pass);await new Promise(r=>setTimeout(r,150));e.lock();resume();await reject(()=>creation);ok(()=>assert.equal(delayed.raw,null));
await b.erase();ok(()=>assert.equal(store.raw,null));ok(()=>assert.equal(b.unlocked,false));
// A conflict callback delivered after Lock must not lock a later queued Unlock.
const raceStore=new Store(),raceVault=new S.Vault(raceStore);await raceVault.create(pass);await raceVault.save(v);
let signalCommit,releaseConflict;const entered=new Promise(r=>signalCommit=r),conflictGate=new Promise(r=>releaseConflict=r);
raceStore.commit=async(expected,raw,guard)=>{if(!guard())throw Error('locked');signalCommit();await conflictGate;throw Error('conflict')};
const obsoleteSave=raceVault.save(v);await entered;raceVault.lock();const reopen=raceVault.unlock(pass);releaseConflict();await reject(()=>obsoleteSave);const recovered=await reopen;checks++;
ok(()=>assert(raceVault.unlocked));ok(()=>assert.deepEqual(recovered,S.state(v)));
console.log(JSON.stringify({status:'PASS',checks,scope:'synthetic-state-and-encryption',live_model_tested:false}));
