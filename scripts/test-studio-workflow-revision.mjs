import {reviewPlanRevision} from '../web/studio-workflow-revision.mjs';
function testRevision(review){
 let checks=0;const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture mismatch '+checks)};
 const reject=(fn,msg)=>{checks++;let e;try{fn()}catch(x){e=x}if(!e||!String(e.message).includes(msg))throw Error('expected rejection '+checks)};
 const on={enabled:true},s=(id,effect,needs=[],extra={})=>({id,effect,needs,...extra});
 const old={goal:'private goal',steps:[s('draft','local_compute',[],{success_criteria:'private criterion'}),s('approve','human_review',['draft']),s('publish','external_write',['approve'],{target:'private target',recovery:'rollback'})]};
 const revised={goal:old.goal,steps:[s('draft','local_compute'),s('publish','external_write',['draft'],{target:'different target'}),s('verify','local_read',['publish'])]};
 const x=review(old,revised,on);
 eq(x.removed,['approve']);eq(x.added,['verify']);eq(x.changed,['draft','publish']);eq(x.unchanged,[]);
 eq(x.findings.map(f=>f.code),['success_criteria_removed','step_removed','target_changed','recovery_removed','dependency_removed','dependency_added','new_step_requires_review']);
 eq(x.blocking_review_count,6);eq(x.execution_authorized,false);eq(JSON.stringify(x).includes('private'),false);
 eq(review(old,old,on).findings,[]);eq(review(old,old,on).unchanged,['draft','approve','publish']);
 eq(review(old,{...old,goal:'new goal'},on).findings,[{step:null,code:'goal_changed',level:'blocking_review'}]);
 eq(review(old,{...old,steps:[...old.steps.slice(0,2),{...old.steps[2],effect:'local_read'}]},on).findings[0].code,'declared_effect_changed');
 eq(review(old,{...old,steps:[...old.steps].reverse()},on).findings,[]);
 eq(review(null,null).status,'off');eq(review(null,null,{...on,isolated:true}).status,'isolated');
 eq(review(old,old,on).execution_authorized,false);
 reject(()=>review(old,{goal:'g',steps:[s('a','local_read',['a'])]},on),'cyclic-plan');
 reject(()=>review(old,{goal:'g',steps:[s('a','local_read',['b'])]},on),'unknown-dependency');
 reject(()=>review(old,{goal:'g',steps:[s('a','local_read'),s('a','local_read')]},on),'invalid-step');
 reject(()=>review(old,{goal:'g',steps:[s('a','unknown',[],{target:''})]},on),'invalid-step-field');
 reject(()=>review(old,{goal:'g',steps:[]},on),'invalid-plan');
 reject(()=>review(old,old,{enabled:1}),'invalid-options');
 eq(old.steps[2].needs,['approve']);
 return checks;
}
console.log('WORKFLOW REVISION: PASS ('+testRevision(reviewPlanRevision)+' checks)');
