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
