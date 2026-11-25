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
 // Only an explicit recall opt-in and present reported failures can expose
 // previous experience; missing evidence alone is not a failed criterion.
 let experience={status:'off',matches:[]};
 if(experienceEnabled){
  if(!failed.length)experience={status:'no_reported_failure',matches:[]};
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
  revision?.lost_count?'review_lost_criteria':
  unresolved.length?'review_unfinished_steps':
  critique.findings.length?'review_plan_findings':
  outcome.review_actions.length?'review_outcome_evidence':'manual_final_review';
 return {status:'review_only',priority,critique,recovery,outcome,revision,experience,...boundary};
}
