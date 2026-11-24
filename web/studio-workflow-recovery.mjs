// Local advisory only, no tool calls, storage, retries or execution authority.
// Host must bind observations to the exact plan, run and project. Reported success is not proof.
export function reviewWorkflowRecovery(steps,observations,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',execution_authorized:false};
 const validId=s=>typeof s==='string'&&/^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/.test(s);
 if(!Array.isArray(steps)||steps.length<1||steps.length>12||!Array.isArray(observations)||observations.length>12)throw Error('invalid-recovery-input');
 const graph=new Map();
 for(const s of steps){
  if(!s||!validId(s.id)||graph.has(s.id)||!Array.isArray(s.needs)||s.needs.length>11||s.needs.some(d=>!validId(d))||new Set(s.needs).size!==s.needs.length)throw Error('invalid-step');
  graph.set(s.id,[...s.needs]);
 }
 for(const deps of graph.values())for(const d of deps)if(!graph.has(d))throw Error('unknown-dependency');
 const order=[],visited=new Set(),visiting=new Set();
 function visit(id){
  if(visiting.has(id))throw Error('cyclic-dependency');
  if(visited.has(id))return;
  visiting.add(id);for(const d of graph.get(id))visit(d);
  visiting.delete(id);visited.add(id);order.push(id);
 }
 for(const id of graph.keys())visit(id);
 const states=new Map();
 for(const o of observations){
  if(!o||!graph.has(o.id)||states.has(o.id)||!['queued','running','succeeded','failed','cancelled','blocked'].includes(o.status))throw Error('invalid-observation');
  states.set(o.id,o.status);
 }
 // A missing observation is unknown, not evidence that no action happened.
 const state=id=>states.get(id)||'unknown';
 const items=[],effective=new Map();
 for(const id of order){
  const observed=state(id),deps=graph.get(id),unresolved=deps.filter(d=>effective.get(d)!=='reported_success');
  let disposition;
  if(observed==='succeeded')disposition=unresolved.length?'inconsistent_observation':'reported_success';
  else if(observed==='running'||observed==='unknown')disposition='reconcile_before_action';
  else if(observed==='failed'||observed==='cancelled')disposition='review_retry';
  else if(unresolved.length)disposition='wait_for_dependencies';
  else if(observed==='blocked')disposition='review_blocked_state';
  else disposition='review_next_step';
  effective.set(id,disposition);
  items.push({id,observed,disposition,unresolved_dependencies:unresolved});
 }
 return {status:'review_only',basis:'supplied_statuses_not_verified_execution_evidence',execution_authorized:false,items};
}

// Review recurring failure codes across explicitly scoped, distinct reported runs.
// Caller must authenticate reports, criteria identity and code vocabulary. No causal inference,
// model training, persistence or automatic application. Failure codes must be nonsensitive.
export function reviewWorkflowLessons(scope,runs,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',candidates:[],automatic_learning:false};
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 const hash=s=>typeof s==='string'&&/^[a-f0-9]{64}$/.test(s);
 if(!scope||!id(scope.project_id)||!id(scope.workflow_id)||!hash(scope.criteria_sha256)||!Array.isArray(runs)||runs.length>30)throw Error('invalid-learning-input');
 const seen=new Set(),groups=new Map();
 for(const run of runs){
  if(!run||run.project_id!==scope.project_id||run.workflow_id!==scope.workflow_id||run.criteria_sha256!==scope.criteria_sha256)throw Error('learning-scope-mismatch');
  if(!id(run.run_id)||seen.has(run.run_id)||!hash(run.plan_sha256)||!['reported_pass','reported_failure','inconclusive'].includes(run.outcome)||!Array.isArray(run.failure_codes)||run.failure_codes.length>12||run.failure_codes.some(c=>!id(c))||new Set(run.failure_codes).size!==run.failure_codes.length)throw Error('invalid-run');
  seen.add(run.run_id);
  if(run.outcome==='reported_pass'&&run.failure_codes.length)throw Error('inconsistent-run');
  if(run.outcome!=='reported_failure')continue;
  for(const code of run.failure_codes){
   if(!groups.has(code))groups.set(code,[]);
   groups.get(code).push(run.run_id);
  }
 }
 const candidates=[...groups].filter(([,ids])=>ids.length>=2).map(([code,ids])=>({kind:'recurring_reported_failure',code,distinct_run_count:ids.length}));
 candidates.sort((a,b)=>b.distinct_run_count-a.distinct_run_count||(a.code<b.code?-1:a.code>b.code?1:0));
 return {status:'review_only',basis:'repeated_supplied_failure_reports_not_verified_causality',candidates,review_required:true,automatic_learning:false,execution_authorized:false};
}
