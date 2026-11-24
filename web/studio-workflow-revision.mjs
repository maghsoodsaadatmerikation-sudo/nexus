// Review-only structural diff. No plan generation, execution, storage or authorization.
// Unchanged declared fields do not prove equivalent tool behavior or preserved outcomes.
export function reviewPlanRevision(before,after,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',execution_authorized:false};
 const id=s=>typeof s==='string'&&/^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/.test(s);
 const text=s=>typeof s==='string'&&s.trim().length>0&&s.length<=500;
 const effects=['local_read','local_compute','network_read','external_write','destructive','spending','human_review','unknown'];
 function validate(p){
  if(!p||!text(p.goal)||!Array.isArray(p.steps)||p.steps.length<1||p.steps.length>12)throw Error('invalid-plan');
  const graph=new Map();
  for(const s of p.steps){
   if(!s||!id(s.id)||graph.has(s.id)||!effects.includes(s.effect)||!Array.isArray(s.needs)||s.needs.length>11||s.needs.some(x=>!id(x))||new Set(s.needs).size!==s.needs.length)throw Error('invalid-step');
   for(const k of ['success_criteria','recovery','target'])if(s[k]!==undefined&&!text(s[k]))throw Error('invalid-step-field');
   graph.set(s.id,s);
  }
  const done=new Set(),active=new Set();
  function visit(x){
   if(!graph.has(x))throw Error('unknown-dependency');
   if(active.has(x))throw Error('cyclic-plan');
   if(done.has(x))return;
   active.add(x);for(const d of graph.get(x).needs)visit(d);active.delete(x);done.add(x);
  }
  for(const x of graph.keys())visit(x);
  return graph;
 }
 const old=validate(before),next=validate(after),findings=[];
 const add=(step,code,level='blocking_review')=>findings.push({step,code,level});
 if(before.goal!==after.goal)add(null,'goal_changed');
 const added=[],removed=[],changed=[],unchanged=[];
 for(const [key,s] of old){
  const n=next.get(key);
  if(!n){removed.push(key);add(key,'step_removed');continue}
  let difference=false;
  if(s.effect!==n.effect){difference=true;add(key,'declared_effect_changed')}
  for(const field of ['success_criteria','target','recovery']){
   if(s[field]!==n[field]){
    difference=true;
    add(key,n[field]===undefined?field+'_removed':field+'_changed');
   }
  }
  if(s.needs.some(d=>!n.needs.includes(d))){difference=true;add(key,'dependency_removed')}
  if(n.needs.some(d=>!s.needs.includes(d))){difference=true;add(key,'dependency_added','review')}
  (difference?changed:unchanged).push(key);
 }
 for(const [key,s] of next)if(!old.has(key)){
  added.push(key);add(key,'new_step_requires_review');
 }
 return {status:'review_only',basis:'declared_plan_diff_not_safety_or_correctness_proof',execution_authorized:false,added,removed,changed,unchanged,findings,blocking_review_count:findings.filter(f=>f.level==='blocking_review').length};
}
