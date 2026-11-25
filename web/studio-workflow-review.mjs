import {critiqueWorkflow} from './studio-workflow-critique.mjs';
import {reviewWorkflowRecovery} from './studio-workflow-recovery.mjs';
import {evaluateWorkflowOutcome,reviewOutcomeRevision,reviewExperienceRecall} from './studio-workflow-outcome.mjs';

// Read-only orchestration. No tool dispatcher, persistence, model context or
// permission grant. Scope labels are consistency checks, not authentication.
export function reviewAssistantWorkflow(input,{enabled=false,isolated=false,experienceEnabled=false}={}){
 if([enabled,isolated,experienceEnabled].some(v=>typeof v!=='boolean'))throw Error('invalid-options');
 const boundary={execution_authorized:false,completion_verified:false,automatic_application:false};
 if(isolated||!enabled)return {status:isolated?'isolated':'off',...boundary};
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 const scope=input?.scope;
 if(!scope||!id(scope.project_id)||!id(scope.workflow_id)||!id(scope.run_id)||typeof scope.plan_sha256!=='string'||!/^[a-f0-9]{64}$/.test(scope.plan_sha256))throw Error('invalid-review-scope');
 const on={enabled:true};
 const critique=critiqueWorkflow(input.plan,on);
 if(!Array.isArray(input.step_observations)||input.step_observations.length>12)throw Error('invalid-step-observations');
 for(const o of input.step_observations){
  if(!o||['project_id','workflow_id','run_id','plan_sha256'].some(k=>o[k]!==scope[k]))throw Error('step-scope-mismatch');
 }
 const recovery=reviewWorkflowRecovery(input.plan.steps,input.step_observations,on);
 const outcome=evaluateWorkflowOutcome(scope,input.criteria,input.evidence,on);
 const revision=input.prior_run===undefined?null:reviewOutcomeRevision(input.prior_run,{scope,observations:input.evidence},input.criteria,on);
 const unresolved=recovery.items.filter(i=>i.disposition!=='reported_success');
 const failed=outcome.items.filter(i=>i.disposition==='reported_failure').map(i=>i.criterion_id);
 // Contradictory required evidence is a reconciliation problem, not a
 // reliable basis for selecting a historical correction. Optional conflicts
 // remain visible in the outcome but do not suppress unrelated recall.
 const reconciliation=outcome.items.filter(i=>i.required&&['conflicting_reports','requires_reconciliation'].includes(i.disposition)).map(i=>i.criterion_id);
 // Only an explicit recall opt-in and present reported failures can expose
 // previous experience; missing evidence alone is not a failed criterion.
 let experience={status:'off',matches:[]};
 if(experienceEnabled){
  if(reconciliation.length)experience={status:'withheld_pending_reconciliation',matches:[]};
  else if(!failed.length)experience={status:'no_reported_failure',matches:[]};
  else if(input.experience===undefined)experience={status:'no_snapshot',matches:[]};
  else {
   const e=input.experience;
   experience=reviewExperienceRecall(e.snapshot,{project_id:scope.project_id,workflow_id:scope.workflow_id,revision:e.revision,criterion_ids:failed},input.criteria,e.attempts,on);
   // Recall validates the bounded attempt structure before this cross-check.
   // The current run cannot supply independent historical support for itself.
   const currentReceipts=new Set(input.evidence.map(o=>o.evidence_id));
   for(const attempt of e.attempts)for(const run of [attempt.before,attempt.after]){
    if(run.scope.run_id===scope.run_id)throw Error('current-run-in-experience');
    if(run.observations.some(o=>currentReceipts.has(o.evidence_id)))throw Error('current-evidence-in-experience');
   }
  }
 }
 const priority=critique.blocking_review_count?'review_plan_boundaries':
  unresolved.some(i=>['inconsistent_observation','reconcile_before_action'].includes(i.disposition))?'reconcile_execution_status':
  reconciliation.length?'review_outcome_evidence':
  revision?.lost_count?'review_lost_criteria':
  unresolved.length?'review_unfinished_steps':
  critique.findings.length?'review_plan_findings':
  outcome.review_actions.length?'review_outcome_evidence':'manual_final_review';
 const comparison=input.correction_comparison===undefined?{}:{correction_comparison:
  !experienceEnabled?{status:'off',options:[]}:
  critique.blocking_review_count||unresolved.length||reconciliation.length?{status:'withheld_pending_review',options:[]}:
  experience.status!=='review_only'?{status:'no_recalled_support',options:[]}:
  compareRecalledCorrections(experience,input.correction_comparison)};
 return {status:'review_only',priority,critique,recovery,outcome,revision,experience,...comparison,...boundary};
}

// Compare explicitly supplied estimates for one failed criterion, and only
// against already reviewed recall matches. Counts are not probabilities.
// No scoring weights, causal claims, spending or automatic selection.
function compareRecalledCorrections(experience,request){
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 const bounded=(v,max)=>Number.isSafeInteger(v)&&v>=0&&v<=max;
 const money=v=>bounded(v,100000000),minutes=v=>bounded(v,525600);
 const risks=['low','medium','high'];
 if(!request||!id(request.criterion_id)||!money(request.max_cost_usd_cents)||!minutes(request.max_effort_minutes)||!Array.isArray(request.options)||request.options.length<1||request.options.length>10)throw Error('invalid-correction-comparison');
 const supported=new Map(experience.matches.filter(m=>m.criterion_id===request.criterion_id).map(m=>[m.correction_code,m]));
 const seen=new Set(),rows=[];
 for(const o of request.options){
  if(!o||!id(o.correction_code)||seen.has(o.correction_code)||!(o.cost_usd_cents===null||money(o.cost_usd_cents))||!(o.effort_minutes===null||minutes(o.effort_minutes))||!(o.risk===null||risks.includes(o.risk))||!(o.reversible===null||typeof o.reversible==='boolean'))throw Error('invalid-correction-option');
  seen.add(o.correction_code);
  const match=supported.get(o.correction_code);
  const status=!match?'no_recalled_support':
   [o.cost_usd_cents,o.effort_minutes,o.risk,o.reversible].includes(null)?'missing_estimates':
   o.cost_usd_cents>request.max_cost_usd_cents||o.effort_minutes>request.max_effort_minutes?'outside_limits':'eligible';
  rows.push({correction_code:o.correction_code,cost_usd_cents:o.cost_usd_cents,effort_minutes:o.effort_minutes,risk:o.risk,reversible:o.reversible,supporting_pair_count:match?.supporting_pair_count??0,status});
 }
 const dimensions=o=>[o.cost_usd_cents,o.effort_minutes,risks.indexOf(o.risk),Number(!o.reversible)];
 const eligible=rows.filter(o=>o.status==='eligible');
 for(const o of eligible){
  const a=dimensions(o);
  o.status=eligible.some(other=>{
   const b=dimensions(other);
   return b.every((v,i)=>v<=a[i])&&b.some((v,i)=>v<a[i]);
  })?'dominated_estimates':'tradeoff_candidate';
 }
 return {status:'review_only',basis:'supplied_estimates_for_recalled_options_not_verified_cost_risk_or_success',criterion_id:request.criterion_id,options:rows,recall_truncated:experience.truncated,automatic_selection:false,execution_authorized:false};
}
