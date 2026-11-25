import '../web/studio-core.js';
import {reviewArchivedExperience} from '../web/studio-experience-archive-recall.mjs';

function fixtures(S){
 let checks=0;
 const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('recall fixture '+checks+': '+JSON.stringify(a))};
 const reject=(fn,msg)=>{checks++;let error;try{fn()}catch(e){error=e}if(!error||!String(error.message).includes(msg))throw Error('recall rejection '+checks+': '+error)};
 const entry={criterion_id:'s1',correction_code:'fix',status:'active',supporting_pair_count:2};
 const snapshot={project_id:'p1',workflow_id:'w1',revision:2,entries:[entry]};
 const project={id:'p1',title:'Test',instructions:'',memories:[],threads:[{id:'t1',title:'Review',nodes:[],head:null}],sources:[],documents:[],experiences:[snapshot]};
 const value=S.state({schema:S.SCHEMA,projects:[project]});
 const ctx={enabled:true,vaultUnlocked:true,busy:false,isolated:false,projectId:'p1',threadId:'t1',revision:5};
 const criteria=[{id:'s1',required:true,evidence_kind:'human_review'}];
 const run=(name,result,evidence=name+'-e')=>{const scope={project_id:'p1',workflow_id:'w1',run_id:name,plan_sha256:'a'.repeat(64)};return {scope,observations:[{...scope,criterion_id:'s1',evidence_id:evidence,kind:'human_review',result}]}};
 const current=run('now','fail');
 const attempts=[1,2].map(n=>({correction_code:'fix',before:run('before'+n,'fail'),after:run('after'+n,'pass')}));
 const req={scope:current.scope,observations:current.observations,criteria,attempts,threadId:'t1',sessionRevision:5,snapshotRevision:2};
 const call=(v=value,c=ctx,q=req,o={enabled:true})=>reviewArchivedExperience(S.state,v,c,q,o);
 const raw=JSON.stringify(value);
 const good=call();
 eq(good.status,'review_only');eq(good.matches.map(m=>m.correction_code),['fix']);
 for(const k of ['automatic_application','execution_authorized','completion_verified','storage_authorized','model_context_authorized'])eq(good[k],false);
 eq(JSON.stringify(value),raw);eq(JSON.stringify(good).includes('before1-e'),false);
 const unread=()=>{throw Error('must-not-read')};
 eq(reviewArchivedExperience(unread,null,null,null).status,'off');
 eq(reviewArchivedExperience(unread,null,null,null,{enabled:true,isolated:true}).status,'isolated');
 reject(()=>call(value,ctx,req,{enabled:'true'}),'invalid-options');
 for(const x of [{enabled:false},{vaultUnlocked:false},{busy:true},{isolated:true}])reject(()=>call(value,{...ctx,...x}),'archive-recall-unavailable');
 for(const x of [{threadId:'t2'},{sessionRevision:4},{scope:{...current.scope,project_id:'other'}}])reject(()=>call(value,ctx,{...req,...x}),'archive-recall-scope');
 reject(()=>call(value,ctx,{...req,snapshotRevision:1}),'stale-archive-recall');
 for(const flag of ['temporary','isolated','archived']){const v=S.copy(value);v.projects[0].threads[0][flag]=true;reject(()=>call(v),'archive-recall-scope')}
 const empty=S.copy(value);empty.projects[0].experiences=[];eq(call(empty).status,'no_snapshot');
 const revoked=S.copy(value);revoked.projects[0].experiences[0].entries[0].status='revoked';eq(call(revoked).matches,[]);
 const changed=S.copy(value);changed.projects[0].experiences[0].entries[0].supporting_pair_count=3;eq(call(changed).matches,[]);eq(call(changed).withheld_count,1);
 eq(call(value,ctx,{...req,attempts:[]}).status,'no_current_evidence');
 eq(call(value,ctx,{...req,observations:run('now','pass').observations}).status,'no_reported_failure');
 eq(call(value,ctx,{...req,observations:[]}).status,'no_reported_failure');
 const conflicting=[...current.observations,...run('now','pass','now-pass').observations];
 eq(call(value,ctx,{...req,observations:conflicting}).status,'withheld_pending_reconciliation');
 const sameRun=[{...attempts[0],before:run('now','fail','separate-e')},attempts[1]];
 reject(()=>call(value,ctx,{...req,attempts:sameRun}),'current-run-in-experience');
 const sameReceipt=[{...attempts[0],before:run('before1','fail','now-e')},attempts[1]];
 reject(()=>call(value,ctx,{...req,attempts:sameReceipt}),'current-evidence-in-experience');
 const foreign=S.copy(attempts);foreign[0].before.scope.project_id='p2';foreign[0].before.observations[0].project_id='p2';reject(()=>call(value,ctx,{...req,attempts:foreign}),'scope');
 eq(JSON.stringify(value),raw);
 return checks;
}
console.log('ARCHIVE RECALL: PASS ('+fixtures(globalThis.NexusStudio)+' checks)');
