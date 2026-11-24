// Review-only assessment of supplied criterion and evidence metadata, not actual verification.
// The host must verify evidence provenance, integrity, scope and authority independently.
// No execution, automatic completion, storage, network or data export.
export function evaluateWorkflowOutcome(scope,criteria,observations,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',completion_verified:false,execution_authorized:false};
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 if(!scope||!id(scope.project_id)||!id(scope.run_id)||typeof scope.plan_sha256!=='string'||!/^[a-f0-9]{64}$/.test(scope.plan_sha256))throw Error('invalid-scope');
 if(!Array.isArray(criteria)||criteria.length<1||criteria.length>30||!Array.isArray(observations)||observations.length>60)throw Error('invalid-outcome-input');
 const byId=new Map();
 for(const c of criteria){
  if(!c||!id(c.id)||byId.has(c.id)||typeof c.required!=='boolean'||!['automated_check','human_review','independent_witness'].includes(c.evidence_kind))throw Error('invalid-criterion');
  byId.set(c.id,c);
 }
 if(!criteria.some(c=>c.required))throw Error('missing-required-criteria');
 // Each observation ID is unique within a run; separate criterion-specific receipts are required.
 const grouped=new Map(),seenEvidence=new Set();
 for(const o of observations){
  if(!o||o.project_id!==scope.project_id||o.run_id!==scope.run_id||o.plan_sha256!==scope.plan_sha256)throw Error('observation-scope-mismatch');
  if(!byId.has(o.criterion_id)||!id(o.evidence_id)||!['pass','fail','inconclusive'].includes(o.result)||!['automated_check','human_review','independent_witness','self_report'].includes(o.kind))throw Error('invalid-observation');
  if(!grouped.has(o.criterion_id))grouped.set(o.criterion_id,new Map());
  const g=grouped.get(o.criterion_id);
  if(seenEvidence.has(o.evidence_id))throw Error('duplicate-evidence');
  seenEvidence.add(o.evidence_id);
  g.set(o.evidence_id,o);
 }
 const items=[];
 for(const c of criteria){
  const all=[...(grouped.get(c.id)?.values()??[])];
  const eligible=all.filter(o=>o.kind===c.evidence_kind);
  const pass=eligible.some(o=>o.result==='pass'),fail=eligible.some(o=>o.result==='fail'),uncertain=eligible.some(o=>o.result==='inconclusive');
  let disposition;
  if(pass&&fail)disposition='conflicting_reports';
  else if(fail)disposition='reported_failure';
  else if(pass&&uncertain)disposition='requires_reconciliation';
  else if(pass)disposition='reported_pass';
  else if(eligible.length)disposition='inconclusive';
  else disposition='missing_required_evidence_kind';
  items.push({criterion_id:c.id,required:c.required,disposition,eligible_count:eligible.length,excluded_count:all.length-eligible.length});
 }
 const required=items.filter(c=>c.required);
 const assessment=required.some(c=>c.disposition==='reported_failure')?'reported_required_failure':required.every(c=>c.disposition==='reported_pass')?'required_reports_present':'review_incomplete';
 const actionByDisposition={reported_failure:'review_failure',conflicting_reports:'reconcile_reports',requires_reconciliation:'reconcile_reports',inconclusive:'request_conclusive_evidence',missing_required_evidence_kind:'request_matching_evidence'};
 // Stable ordering: required criteria first; never request an automatic retry or action.
 const review_actions=[...required,...items.filter(c=>!c.required)].filter(c=>c.disposition!=='reported_pass').map(c=>({criterion_id:c.criterion_id,required:c.required,evidence_kind:byId.get(c.criterion_id).evidence_kind,action:actionByDisposition[c.disposition]}));
 return {review_actions,status:'review_only',basis:'supplied_evidence_metadata_not_authenticity_or_outcome_proof',assessment,completion_verified:false,execution_authorized:false,items};
}

// Compare distinct declared runs against one shared criterion list, never against a
// caller-supplied aggregate score. The caller must authenticate scope, criterion
// semantics and receipt provenance. No proof of regression, causality or success.
export function reviewOutcomeRevision(before,after,criteria,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',completion_verified:false,execution_authorized:false};
 const validId=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 const a=before?.scope,b=after?.scope;
 if(!a||!b||!validId(a.workflow_id)||a.workflow_id!==b.workflow_id||a.project_id!==b.project_id||a.run_id===b.run_id)throw Error('comparison-scope-mismatch');
 const old=evaluateWorkflowOutcome(a,criteria,before.observations,{enabled:true});
 const next=evaluateWorkflowOutcome(b,criteria,after.observations,{enabled:true});
 const priorIds=new Set(before.observations.map(o=>o.evidence_id));
 if(after.observations.some(o=>priorIds.has(o.evidence_id)))throw Error('reused-run-evidence');
 const changes=old.items.map((p,i)=>{
  const n=next.items[i],was=p.disposition,is=n.disposition;
  const transition=was===is?'unchanged':was==='reported_pass'?'reported_pass_lost':is==='reported_pass'?'reported_pass_gained':'unresolved_change';
  return {criterion_id:p.criterion_id,required:p.required,before:was,after:is,transition};
 });
 const lost=changes.filter(c=>c.transition==='reported_pass_lost');
 const gained=changes.filter(c=>c.transition==='reported_pass_gained');
 const unresolved=changes.filter(c=>c.after!=='reported_pass');
 const assessment=lost.some(c=>c.required)?'required_pass_lost':lost.length?'optional_pass_lost':
  unresolved.some(c=>c.required)?'required_review_incomplete':unresolved.length?'optional_review_incomplete':'all_criteria_reported_pass';
 return {status:'review_only',basis:'distinct_declared_runs_shared_criteria_not_verified_comparability',assessment,
  plan_changed:a.plan_sha256!==b.plan_sha256,changes,
  lost_count:lost.length,gained_count:gained.length,unresolved_count:unresolved.length,
  review_actions:next.review_actions,completion_verified:false,execution_authorized:false};
}

// Conservative, ephemeral experience candidates; correction codes are caller-declared
// nonsensitive labels, not instructions. Repeated associations are not causal evidence.
export function reviewCorrectionExperience(scope,criteria,attempts,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 const boundary={automatic_learning:false,completion_verified:false,execution_authorized:false};
 if(isolated||!enabled)return {status:isolated?'isolated':'off',candidates:[],...boundary};
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 if(!scope||!id(scope.project_id)||!id(scope.workflow_id)||!Array.isArray(attempts)||attempts.length<1||attempts.length>12)throw Error('invalid-experience-input');
 const groups=new Map(),runs=new Set(),receipts=new Set();
 for(const attempt of attempts){
  if(!attempt||!id(attempt.correction_code))throw Error('invalid-correction-code');
  const {before,after}=attempt;
  for(const r of [before,after]){
   if(r?.scope?.project_id!==scope.project_id||r.scope.workflow_id!==scope.workflow_id)throw Error('experience-scope-mismatch');
   if(runs.has(r.scope.run_id))throw Error('reused-experience-run');
   runs.add(r.scope.run_id);
  }
  const result=reviewOutcomeRevision(before,after,criteria,{enabled:true});
  for(const r of [before,after])for(const o of r.observations){
   if(receipts.has(o.evidence_id))throw Error('reused-experience-evidence');
   receipts.add(o.evidence_id);
  }
  if(!groups.has(attempt.correction_code))groups.set(attempt.correction_code,{total:0,non_supporting:0,regressions:0,counts:new Map()});
  const g=groups.get(attempt.correction_code);g.total++;
  if(result.lost_count)g.regressions++;
  const gains=result.changes.filter(c=>c.before==='reported_failure'&&c.after==='reported_pass');
  if(result.assessment!=='all_criteria_reported_pass'||!gains.length){g.non_supporting++;continue}
  for(const c of gains)g.counts.set(c.criterion_id,(g.counts.get(c.criterion_id)||0)+1);
 }
 const candidates=[],summaries=[];
 for(const [code,g] of groups){
  summaries.push({correction_code:code,attempt_count:g.total,non_supporting_count:g.non_supporting,regression_count:g.regressions});
  if(g.total<2||g.non_supporting||g.regressions)continue;
  for(const [criterion,count] of g.counts)if(count===g.total)candidates.push({correction_code:code,criterion_id:criterion,supporting_pair_count:count,review_required:true});
 }
 return {status:'review_only',basis:'repeated_supplied_failure_to_pass_associations_not_causal_evidence',candidates,summaries,...boundary};
}

// A serializable snapshot proposal, not a storage engine. Host owns authenticated
// human consent, monotonic revision/CAS, encryption, deletion and invalidation.
// Do not persist tickets, raw observations or untrusted instructions.
export function createExperienceEditReview(){
 let pending=null;
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 const key=(c,k)=>c+'|'+k;
 function read(snapshot){
  if(!snapshot||!id(snapshot.project_id)||!id(snapshot.workflow_id)||!Number.isSafeInteger(snapshot.revision)||snapshot.revision<0||snapshot.revision>=Number.MAX_SAFE_INTEGER||!Array.isArray(snapshot.entries)||snapshot.entries.length>30)throw Error('invalid-experience-snapshot');
  const seen=new Set(),entries=snapshot.entries.map(e=>{
   if(!e||!id(e.correction_code)||!id(e.criterion_id)||!['active','revoked'].includes(e.status)||!Number.isInteger(e.supporting_pair_count)||e.supporting_pair_count<2||e.supporting_pair_count>12)throw Error('invalid-experience-entry');
   const k=key(e.correction_code,e.criterion_id);
   if(seen.has(k))throw Error('duplicate-experience-entry');seen.add(k);
   return {correction_code:e.correction_code,criterion_id:e.criterion_id,status:e.status,supporting_pair_count:e.supporting_pair_count};
  });
  return {project_id:snapshot.project_id,workflow_id:snapshot.workflow_id,revision:snapshot.revision,entries};
 }
 function stage(snapshot,operation,{enabled=false,isolated=false,criteria,attempts}={}){
  pending=null;
  if(enabled!==true||isolated!==false)throw Error('experience-edit-disabled');
  const current=read(snapshot);
  if(!operation||!['accept','refresh','revoke','delete'].includes(operation.kind)||!id(operation.correction_code)||!id(operation.criterion_id))throw Error('invalid-experience-operation');
  const {kind,correction_code,criterion_id}=operation;
  const index=current.entries.findIndex(e=>e.correction_code===correction_code&&e.criterion_id===criterion_id);
  const entries=current.entries.map(e=>({...e}));
  if(kind==='accept'||kind==='refresh'){
   if(kind==='accept'&&index!==-1)throw Error('experience-already-present');
   if(kind==='refresh'&&index===-1)throw Error('experience-not-found');
   const result=reviewCorrectionExperience(current,criteria,attempts,{enabled:true});
   const match=result.candidates.find(c=>c.correction_code===correction_code&&c.criterion_id===criterion_id);
   if(!match)throw Error('experience-not-supported');
   const record={correction_code,criterion_id,status:'active',supporting_pair_count:match.supporting_pair_count};
   if(index===-1){if(entries.length>=30)throw Error('experience-capacity');entries.push(record)}else entries[index]=record;
  }else{
   if(index===-1)throw Error('experience-not-found');
   if(kind==='delete')entries.splice(index,1);
   else {if(entries[index].status==='revoked')throw Error('experience-already-revoked');entries[index].status='revoked'}
  }
  const ticket=Object.freeze(Object.create(null));
  pending={ticket,expected:JSON.stringify(current),next:{...current,revision:current.revision+1,entries}};
  return Object.freeze({ticket,kind,correction_code,criterion_id,project_id:current.project_id,workflow_id:current.workflow_id,revision:current.revision,review_required:true});
 }
 function approve(ticket,snapshot,{approved=false,enabled=false,isolated=false}={}){
  if(!pending||pending.ticket!==ticket)throw Error('inactive-experience-review');
  const p=pending;pending=null;
  if(approved!==true||enabled!==true||isolated!==false)throw Error('experience-edit-not-approved');
  if(JSON.stringify(read(snapshot))!==p.expected)throw Error('stale-experience-review');
  return p.next;
 }
 function invalidate(){pending=null}
 return Object.freeze({stage,approve,invalidate});
}
