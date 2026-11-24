import {critiqueWorkflow} from '../web/studio-workflow-critique.mjs';
function testCritique(critique){
 let checks=0;const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture mismatch '+checks)};
 const reject=(fn,msg)=>{checks++;let e;try{fn()}catch(x){e=x}if(!e||!String(e.message).includes(msg))throw Error('expected rejection '+checks)};
 const on={enabled:true},step=(id,effect,needs=[],extra={})=>({id,effect,needs,...extra});
 const plan={goal:'private goal',steps:[step('publish','external_write',['draft']),step('draft','local_compute',[],{success_criteria:'private criterion'}),step('buy','spending'),step('verify','human_review',['publish'],{success_criteria:'check'}),step('unknown','unknown')]};
 const x=critique(plan,on);
 eq(x.review_order,['draft','publish','buy','verify','unknown']);eq(x.terminal_steps,['buy','verify','unknown']);
 eq(x.findings.filter(f=>f.step==='publish').map(f=>f.code),['missing_success_criteria','separate_exact_action_review_required','missing_target','missing_recovery_plan']);
 eq(x.findings.filter(f=>f.step==='verify').map(f=>f.code),['human_decision_required']);
 eq(x.findings.filter(f=>f.step==='unknown').map(f=>f.code),['missing_success_criteria','undeclared_effect']);
 eq(x.blocking_review_count,8);eq(x.execution_authorized,false);eq(JSON.stringify(x).includes('private'),false);
 const safe={goal:'g',steps:[step('a','local_read',[],{success_criteria:'check'})]};
 eq(critique(safe,on).findings,[]);eq(critique(safe,on).execution_authorized,false);
 const write={goal:'g',steps:[step('a','external_write',[],{success_criteria:'check',target:'t',recovery:'undo'})]};
 eq(critique(write,on).findings,[{step:'a',code:'separate_exact_action_review_required',level:'blocking_review'}]);
 eq(critique(null).status,'off');eq(critique(null,{...on,isolated:true}).status,'isolated');
 reject(()=>critique({goal:'g',steps:[step('a','local_read',['a'])]},on),'cyclic-plan');
 reject(()=>critique({goal:'g',steps:[step('a','local_read',['b'])]},on),'unknown-dependency');
 reject(()=>critique({goal:'g',steps:[step('a','local_read'),step('a','local_read')]},on),'invalid-step');
 reject(()=>critique({goal:'g',steps:[step('a','anything')]},on),'invalid-step');
 reject(()=>critique({goal:'g',steps:[step('a','local_read',[],{target:' '})]},on),'invalid-step-field');
 reject(()=>critique({goal:'g',steps:[]},on),'invalid-plan');
 reject(()=>critique(safe,{enabled:1}),'invalid-options');
 eq(plan.steps[0].needs,['draft']);return checks;
}
console.log('WORKFLOW CRITIQUE: PASS ('+testCritique(critiqueWorkflow)+' checks)');
