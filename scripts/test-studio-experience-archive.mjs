import assert from 'node:assert/strict';
import '../web/studio-core.js';
import {createArchiveExperienceReview,stageImportedExperience} from '../web/studio-experience-archive-edit.mjs';
const S=globalThis.NexusStudio;
function testArchive(S){
 let checks=0;
 const eq=(a,b)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture '+checks);checks++};
 const reject=fn=>{let failed=false;try{fn()}catch{failed=true}eq(failed,true)};
 const p={id:'p1',title:'Test',instructions:'',memories:[],threads:[],sources:[],documents:[]};
 const entry={correction_code:'synthetic_fix',criterion_id:'s1',status:'active',supporting_pair_count:2};
 const snap={project_id:'p1',workflow_id:'w1',revision:1,entries:[entry]};
 const input=x=>({schema:S.SCHEMA,projects:[{...p,...x}]});
 eq(S.state(input({})),input({}));
 eq(S.state(input({experiences:[snap]})).projects[0].experiences,[snap]);
 eq(S.retainHistory(input({experiences:[snap]})).projects[0].experiences,[snap]);
 for(const count of [0,1,2,3,12,13,99,2.5])for(const status of ['active','revoked','forged']){
  const value=input({experiences:[{...snap,entries:[{...entry,supporting_pair_count:count,status}]}]});
  if(Number.isInteger(count)&&count>=2&&count<=12&&status!=='forged')eq(S.state(value),value);else reject(()=>S.state(value));
 }
 for(const revision of [0,1,99,-1,1.2,Number.MAX_SAFE_INTEGER,NaN])for(const workflow_id of ['w1','wf_2','','x y']){
  const value=input({experiences:[{...snap,revision,workflow_id}]});
  if(Number.isSafeInteger(revision)&&revision>=0&&revision<Number.MAX_SAFE_INTEGER&&['w1','wf_2'].includes(workflow_id))eq(S.state(value),value);else reject(()=>S.state(value));
 }
 for(const code of ['x','x'.repeat(80),'a_b','a-b','', 'x'.repeat(81),'x y','<script>'])for(const key of ['criterion_id','correction_code']){
  const value=input({experiences:[{...snap,entries:[{...entry,[key]:code}]}]});
  if(/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(code))eq(S.state(value),value);else reject(()=>S.state(value));
 }
 for(const bad of [{...snap,project_id:'p2'},{...snap,raw_evidence:[]},{...snap,ticket:{}},{...snap,entries:[{...entry,instruction:'unsafe'}]},{...snap,entries:[entry,entry]},{...snap,entries:Array.from({length:31},(_,i)=>({...entry,criterion_id:'s'+i}))}])reject(()=>S.state(input({experiences:[bad]})));
 reject(()=>S.state(input({experiences:[snap,snap]})));
 reject(()=>S.state(input({experiences:Array.from({length:13},(_,i)=>({...snap,workflow_id:'w'+i}))})));
 eq(S.state(input({experiences:[]})).projects[0].experiences,[]);
 return checks;
}

const checks=testArchive(S);
function testArchiveEdit(S){
 let checks=0;
 const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('archive edit fixture '+checks)};
 const reject=(fn,msg)=>{checks++;let error;try{fn()}catch(e){error=e}if(!error||!String(error.message).includes(msg))throw Error('archive edit rejection '+checks+' '+error)};
 const p={id:'p1',title:'Test',instructions:'',memories:[],threads:[{id:'t1',title:'Review',nodes:[],head:null}],sources:[],documents:[]};
 const data=S.state({schema:S.SCHEMA,projects:[p]});
 const session={enabled:true,vaultUnlocked:true,busy:false,isolated:false,projectId:'p1',threadId:'t1',revision:4};
 const criteria=[{id:'s1',required:true,evidence_kind:'human_review'}];
 const run=(name,result)=>{const scope={project_id:'p1',workflow_id:'w1',run_id:name,plan_sha256:'a'.repeat(64)};return {scope,observations:[{...scope,criterion_id:'s1',evidence_id:name+'-e',kind:'human_review',result}]}};
 const attempts=[1,2].map(n=>({correction_code:'fix',before:run('before'+n,'fail'),after:run('after'+n,'pass')}));
 const accept={kind:'accept',criterion_id:'s1',correction_code:'fix'},options={criteria,attempts};
 const adapter=createArchiveExperienceReview(S.state);
 const stage=(value=data,sess=session,op=accept,opts=options)=>adapter.stage(value,sess,'w1',op,opts);
 const approval={approved:true};
 const original=JSON.stringify(data);
 const report={schema:'nexus.experience-review.v1',workflow_id:'w1',operation:accept,criteria,attempts};
 const imported=stageImportedExperience(adapter,data,session,JSON.stringify(report));
 eq(imported.correction_code,'fix');
 eq(adapter.approve(imported.ticket,data,session,{approved:true}).state.projects[0].experiences[0].entries[0].supporting_pair_count,2);
 reject(()=>stageImportedExperience(adapter,data,session,'x'.repeat(65537)),'invalid-experience-import');
 for(const bad of [{...report,schema:'other'},{...report,raw_evidence:[]},{...report,attempts:[attempts[0]]},{...report,operation:{...accept,kind:'delete'}},{...report,operation:{...accept,extra:true}},{...report,criteria:[]}])reject(()=>stageImportedExperience(adapter,data,session,JSON.stringify(bad)),'invalid-experience-import');
 reject(()=>stageImportedExperience(adapter,data,{...session,isolated:true},JSON.stringify(report)),'archive-review-unavailable');
 eq(JSON.stringify(data),original);
 const proposal=stage();
 eq(proposal.storage_authorized,false);eq(proposal.review_required,true);
 eq(JSON.stringify(data),original);
 const result=adapter.approve(proposal.ticket,data,session,approval);
 eq(result.status,'proposed_state');eq(result.storage_authorized,false);eq(result.execution_authorized,false);eq(result.automatic_application,false);
 eq(result.state.projects[0].experiences,[{project_id:'p1',workflow_id:'w1',revision:1,entries:[{correction_code:'fix',criterion_id:'s1',status:'active',supporting_pair_count:2}]}]);
 eq(JSON.stringify(data),original);
 reject(()=>adapter.approve(proposal.ticket,data,session,approval),'inactive-archive-review');
 const revoke=stage(result.state,session,{...accept,kind:'revoke'},{});
 const revoked=adapter.approve(revoke.ticket,result.state,session,approval).state;
 eq(revoked.projects[0].experiences[0].entries[0].status,'revoked');
 eq(revoked.projects[0].experiences[0].revision,2);
 const removal=stage(revoked,session,{...accept,kind:'delete'},{});
 const removed=adapter.approve(removal.ticket,revoked,session,approval).state;
 eq(removed.projects[0].experiences[0].entries,[]);eq(removed.projects[0].experiences[0].revision,3);
 const refresh=stage(revoked,session,{...accept,kind:'refresh'},options);
 eq(adapter.approve(refresh.ticket,revoked,session,approval).state.projects[0].experiences[0].entries[0].status,'active');
 for(const change of [{enabled:false},{vaultUnlocked:false},{busy:true},{isolated:true}])reject(()=>stage(data,{...session,...change}),'archive-review-unavailable');
 reject(()=>stage(data,{...session,threadId:'other'}),'archive-review-scope');
 for(const flag of ['temporary','archived','isolated']){const altered=S.copy(data);altered.projects[0].threads[0][flag]=true;reject(()=>stage(altered),'archive-review-scope')}
 reject(()=>stage(data,session,accept,{criteria,attempts:[attempts[0]]}),'experience-not-supported');
 const foreign=JSON.parse(JSON.stringify(attempts));foreign[0].before.observations[0].workflow_id='foreign';
 reject(()=>stage(data,session,accept,{criteria,attempts:foreign}),'archive-evidence-scope');
 const denied=stage();reject(()=>adapter.approve(denied.ticket,data,session),'archive-review-not-approved');
 reject(()=>adapter.approve(denied.ticket,data,session,approval),'inactive-archive-review');
 const stale=stage();reject(()=>adapter.approve(stale.ticket,data,{...session,revision:5},approval),'stale-archive-review');
 const appeared=stage();reject(()=>adapter.approve(appeared.ticket,result.state,session,approval),'stale-archive-review');
 const cleared=stage();adapter.invalidate();reject(()=>adapter.approve(cleared.ticket,data,session,approval),'inactive-archive-review');
 const older=stage();const newer=stage();reject(()=>adapter.approve(older.ticket,data,session,approval),'inactive-archive-review');
 eq(adapter.approve(newer.ticket,data,session,approval).state.projects[0].experiences[0].revision,1);
 const changed=stage(result.state,session,{...accept,kind:'revoke'},{});
 reject(()=>adapter.approve(changed.ticket,revoked,session,approval),'stale-experience-review');
 eq(JSON.stringify(result).includes('before1-e'),false);
 return checks;
}
console.log('EXPERIENCE ARCHIVE EDIT: PASS ('+testArchiveEdit(S)+' checks)');
function testStoredRemoval(S){
 let checks=0;
 const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('stored removal fixture '+checks)};
 const reject=(fn,msg)=>{checks++;let error;try{fn()}catch(e){error=e}if(!error||!String(error.message).includes(msg))throw Error('stored removal rejection '+checks+' '+error)};
 const entry={correction_code:'fix',criterion_id:'s1',status:'active',supporting_pair_count:2};
 const snapshot={project_id:'p1',workflow_id:'w1',revision:1,entries:[entry]};
 const project={id:'p1',title:'Test',instructions:'',memories:['unchanged'],threads:[{id:'t1',title:'Review',nodes:[],head:null}],sources:[],documents:[],experiences:[snapshot]};
 const value=S.state({schema:S.SCHEMA,projects:[project]});
 const args={projectId:'p1',threadId:'t1',workflowId:'w1',expectedRevision:1,criterionId:'s1',correctionCode:'fix',kind:'revoke'};
 const original=JSON.stringify(value);
 const revoked=S.reviewStoredExperienceRemoval(value,args);
 eq(revoked.projects[0].experiences[0].entries[0].status,'revoked');eq(revoked.projects[0].experiences[0].revision,2);
 eq(revoked.projects[0].memories,['unchanged']);eq(JSON.stringify(value),original);
 const deleted=S.reviewStoredExperienceRemoval(revoked,{...args,expectedRevision:2,kind:'delete'});
 eq(deleted.projects[0].experiences[0].entries,[]);eq(deleted.projects[0].experiences[0].revision,3);
 reject(()=>S.reviewStoredExperienceRemoval(revoked,args),'stale-experience-removal');
 reject(()=>S.reviewStoredExperienceRemoval(revoked,{...args,expectedRevision:2}),'experience-already-revoked');
 reject(()=>S.reviewStoredExperienceRemoval(value,{...args,kind:'accept'}),'experience-removal-kind');
 reject(()=>S.reviewStoredExperienceRemoval(value,{...args,correctionCode:'other'}),'experience-not-found');
 reject(()=>S.reviewStoredExperienceRemoval(value,{...args,workflowId:'other'}),'stale-experience-removal');
 reject(()=>S.reviewStoredExperienceRemoval(value,{...args,projectId:'other'}),'experience-removal-scope');
 reject(()=>S.reviewStoredExperienceRemoval(value,{...args,threadId:'other'}),'experience-removal-scope');
 for(const flag of ['temporary','isolated','archived']){const altered=S.copy(value);altered.projects[0].threads[0][flag]=true;reject(()=>S.reviewStoredExperienceRemoval(altered,args),'experience-removal-scope')}
 const capped=S.copy(value);capped.projects[0].experiences[0].revision=Number.MAX_SAFE_INTEGER-1;
 reject(()=>S.reviewStoredExperienceRemoval(capped,{...args,expectedRevision:Number.MAX_SAFE_INTEGER-1}),'stale-experience-removal');
 return checks;
}
console.log('STORED EXPERIENCE REMOVAL: PASS ('+testStoredRemoval(S)+' checks)');

// Use the existing real WebCrypto vault rather than a second key or store.
class Store{raw=null;async read(){return this.raw}async commit(expected,raw,guard){if(!guard())throw Error('locked');if((this.raw?JSON.parse(this.raw).revision:null)!==expected)throw Error('conflict');this.raw=raw}}
const store=new Store(),vault=new S.Vault(store),pass='synthetic archive experience passphrase';
const p=S.project('Synthetic archive');p.experiences=[{project_id:p.id,workflow_id:'w1',revision:1,entries:[{correction_code:'synthetic_fix',criterion_id:'s1',status:'active',supporting_pair_count:2}]}];
const data=S.state({schema:S.SCHEMA,projects:[p]});
await vault.create(pass);await vault.save(data);
assert(!store.raw.includes('synthetic_fix'));
assert.deepEqual((await S.decrypt(store.raw,pass)).data,data);
vault.lock();assert.deepEqual(await vault.unlock(pass),data);
const t=S.append(S.thread('Synthetic'),'user','Review task','human');
for(const isolated of [false,true]){const context=S.context(p,{...t,isolated},{memory:true,sources:true,skyTone:false});assert(!JSON.stringify(context).includes('synthetic_fix'))}
const removed=S.copy(data);removed.projects[0].experiences=[];
await vault.save(removed);assert.deepEqual((await S.decrypt(store.raw,pass)).data.projects[0].experiences,[]);
// Integration: stage/approve the real adapter, then explicitly save through
// the existing encrypted vault. Never persist a ticket or an evidence receipt.
const project=S.project('Adapter integration'),thread=S.thread('Review');
project.threads=[thread];
const start=S.state({schema:S.SCHEMA,projects:[project]});
const store2=new Store(),primary=new S.Vault(store2),secondary=new S.Vault(store2);
await primary.create(pass);await primary.save(start);
await secondary.unlock(pass);
const ctx={enabled:true,vaultUnlocked:true,busy:false,isolated:false,projectId:project.id,threadId:thread.id,revision:1};
const catalog=[{id:'s1',required:true,evidence_kind:'human_review'}];
const report=(name,result)=>{const scope={project_id:project.id,workflow_id:'w1',run_id:name,plan_sha256:'b'.repeat(64)};return {scope,observations:[{...scope,criterion_id:'s1',evidence_id:name+'-private-receipt',kind:'human_review',result}]}};
const support=[1,2].map(i=>({correction_code:'reviewed_fix',before:report('before'+i,'fail'),after:report('after'+i,'pass')}));
const edit=createArchiveExperienceReview(S.state),op={kind:'accept',correction_code:'reviewed_fix',criterion_id:'s1'};
const savedBefore=store2.raw,expectedArchiveRevision=primary.archiveRevision;
assert.equal(expectedArchiveRevision,JSON.parse(savedBefore).revision);
const ticket=edit.stage(start,ctx,'w1',op,{criteria:catalog,attempts:support});
assert.equal(store2.raw,savedBefore,'stage does not save');
const next=edit.approve(ticket.ticket,start,ctx,{approved:true}).state;
assert.equal(store2.raw,savedBefore,'approval does not save');
await primary.save(next,{expectedArchiveRevision});
assert.notEqual(store2.raw,savedBefore);
await assert.rejects(primary.save(start,{expectedArchiveRevision}),/stale-archive-revision/);
assert.equal(primary.unlocked,true,'stale proposal does not lock current vault');
assert.deepEqual((await S.decrypt(store2.raw,pass)).data,next,'stale proposal cannot overwrite experience');
assert(!store2.raw.includes('reviewed_fix'));
assert(!JSON.stringify(next).includes('private-receipt'));
assert.deepEqual((await S.decrypt(store2.raw,pass)).data,next);
await assert.rejects(secondary.save(start),/conflict/);
assert.equal(secondary.unlocked,false,'stale vault writer locks');
assert.deepEqual((await S.decrypt(store2.raw,pass)).data,next,'stale save preserves committed experience');
primary.lock();
await assert.rejects(primary.save(next),/locked/);
const reopened=await primary.unlock(pass);
assert.deepEqual(reopened,next,'experience survives lock and unlock');
const nextCtx={...ctx,revision:2};
const remove=edit.stage(reopened,nextCtx,'w1',{...op,kind:'delete'});
const deleted=edit.approve(remove.ticket,reopened,nextCtx,{approved:true}).state;
const removalVersion=primary.archiveRevision;
const savedRemoval=primary.save(deleted,{expectedArchiveRevision:removalVersion});
const staleQueued=assert.rejects(primary.save(next,{expectedArchiveRevision:removalVersion}),/stale-archive-revision/);
await savedRemoval;await staleQueued;
primary.lock();
assert.equal(primary.archiveRevision,null);
const final=await primary.unlock(pass);
assert.deepEqual(final.projects[0].experiences[0].entries,[]);
assert.equal(final.projects[0].experiences[0].revision,2);
assert.equal(final.projects[0].threads[0].id,thread.id,'unrelated thread retained');
console.log('EXPERIENCE ADAPTER VAULT INTEGRATION: PASS (explicit save, stale writer, lock/unlock and deletion)');
console.log('EXPERIENCE ARCHIVE: PASS ('+checks+' validation cases plus real vault tests)');
