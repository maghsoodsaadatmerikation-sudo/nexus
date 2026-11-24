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
