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
