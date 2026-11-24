// Pure, review-only structural critique of declared plan effects. No inference, execution or authorization.
// An effect label is a caller assertion, never proof of what code or tools will actually do.
export function critiqueWorkflow(plan,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',execution_authorized:false};
 const id=s=>typeof s==='string'&&/^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/.test(s);
 const label=s=>typeof s==='string'&&s.length<=500&&s.trim().length>0;
 if(!plan||!label(plan.goal)||!Array.isArray(plan.steps)||plan.steps.length<1||plan.steps.length>12)throw Error('invalid-plan');
 const allowed=['local_read','local_compute','network_read','external_write','destructive','spending','human_review','unknown'];
 const graph=new Map();
 for(const step of plan.steps){
  if(!step||!id(step.id)||graph.has(step.id)||!Array.isArray(step.needs)||step.needs.length>11||step.needs.some(x=>!id(x))||new Set(step.needs).size!==step.needs.length||!allowed.includes(step.effect))throw Error('invalid-step');
  for(const key of ['success_criteria','recovery','target'])if(step[key]!==undefined&&!label(step[key]))throw Error('invalid-step-field');
  graph.set(step.id,step);
 }
 for(const s of graph.values())for(const d of s.needs)if(!graph.has(d))throw Error('unknown-dependency');
 const order=[],active=new Set(),seen=new Set();
 function visit(x){if(active.has(x))throw Error('cyclic-plan');if(seen.has(x))return;active.add(x);for(const d of graph.get(x).needs)visit(d);active.delete(x);seen.add(x);order.push(x)}
 for(const x of graph.keys())visit(x);
 const findings=[];
 const add=(step,code,level)=>findings.push({step,code,level});
 for(const x of order){
  const s=graph.get(x);
  if(!s.success_criteria)add(x,'missing_success_criteria','review');
  if(s.effect==='unknown')add(x,'undeclared_effect','blocking_review');
  if(['network_read','external_write','destructive','spending'].includes(s.effect)){
   add(x,'separate_exact_action_review_required','blocking_review');
   if(!s.target)add(x,'missing_target','blocking_review');
  }
  if(['external_write','destructive','spending'].includes(s.effect)&&!s.recovery)add(x,'missing_recovery_plan','blocking_review');
  if(s.effect==='human_review')add(x,'human_decision_required','blocking_review');
 }
 const terminal=order.filter(x=>!plan.steps.some(s=>s.needs.includes(x)));
 return {status:'review_only',basis:'declared_effects_and_plan_structure_not_verified_safety',execution_authorized:false,
  review_order:order,terminal_steps:terminal,findings,blocking_review_count:findings.filter(f=>f.level==='blocking_review').length};
}
