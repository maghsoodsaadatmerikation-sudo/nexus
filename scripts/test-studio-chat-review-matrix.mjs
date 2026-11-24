// Test-only extraction of exact pure composer helper functions. No browser or production eval.
import {readFileSync} from 'node:fs';
import {reviewAssistantWorkflow} from '../web/studio-workflow-review.mjs';
const source=readFileSync(new URL('../web/studio-composer-ui.js',import.meta.url),'utf8');
const start='function humanCriterion(step){',end='async function showEngineReview(button,notice){';
if(source.split(start).length!==2||source.split(end).length!==2||source.indexOf(end)<source.indexOf(start))throw Error('chat bridge extraction markers changed');
const bridge=new Function(source.slice(source.indexOf(start),source.indexOf(end))+'\nreturn {humanCriterion,engineInput,reviewSnapshot,canCompareRound,restartReviewedRound};')();
function testChatBridge(bridge,review){
 const {humanCriterion,engineInput,reviewSnapshot,canCompareRound,restartReviewedRound}=bridge;
 let cases=0;
 const eq=(actual,expected,msg)=>{if(JSON.stringify(actual)!==JSON.stringify(expected))throw Error(msg+' '+JSON.stringify({actual,expected}));};
 const check=(label,fn)=>{try{fn();cases++}catch(e){throw Error(label+': '+e.message)}};
 const hash='a'.repeat(64);
 const validVerdicts=['pass','fail','inconclusive'];
 const statusMap={started:'running',succeeded:'succeeded',failed:'failed',cancelled:'cancelled',partial:'blocked'};
 const dispositions={pass:'reported_pass',fail:'reported_failure',inconclusive:'inconclusive',none:'missing_required_evidence_kind'};
 for(const [criterion,valid] of [['',false],['  ',false],['x',true],[' x ',true],['x'.repeat(260),true],['x'.repeat(261),false]])
 for(const opened of [false,true])
 for(const observed of [null,'started','succeeded','failed','cancelled','partial'])
 for(const verdict of [null,'pass','fail','inconclusive','forged']){
  check('criterion/open/status/verdict matrix '+cases,()=>{
   const step={command:'code',criterion,opened,observed,verdict};
   const expected=valid&&opened&&observed!=='started'&&validVerdicts.includes(verdict)?verdict:null;
   eq(humanCriterion(step),{criterion:valid?criterion.trim():'',verdict:expected},'criterion');
   const input=engineInput('',[step],hash,1);
   eq(input.evidence.length,expected?1:0,'evidence count');
   eq(input.step_observations.map(x=>x.status),observed?[statusMap[observed]]:[],'local status');
   const result=review(input,{enabled:true});
   eq(result.outcome.items[0].disposition,dispositions[expected||'none'],'disposition');
   eq([result.execution_authorized,result.completion_verified,result.automatic_application],[false,false,false],'authority');
   eq(result.experience.status,'off','memory disabled');
  });
 }
 const verdicts=[null,...validVerdicts];
 for(const before of verdicts)for(const after of verdicts){
  check('revision matrix '+cases,()=>{
   const step={command:'code',criterion:'criterion',opened:true,observed:'succeeded'};
   const old=engineInput('',[{...step,verdict:before}],hash,1),cur=engineInput('',[{...step,verdict:after}],hash,2);
   cur.prior_run={scope:old.scope,observations:old.evidence};
   const r=review(cur,{enabled:true});
   eq(r.revision.gained_count,before!=='pass'&&after==='pass'?1:0,'gain');
   eq(r.revision.lost_count,before==='pass'&&after!=='pass'?1:0,'loss');
   eq(r.revision.plan_changed,false,'same hash');
   eq(r.execution_authorized,false,'authority');
   if(old.evidence.length&&cur.evidence.length)eq(old.evidence[0].evidence_id===cur.evidence[0].evidence_id,false,'unique receipts');
  });
 }
 for(const n of [2,3,4,5,6]){
  check('restart '+n,()=>{
   const steps=Array.from({length:n},(_,i)=>({result:{route:['code']},criterion:'criterion '+i,opened:true,acknowledged:true,observed:'succeeded',verdict:'pass',runId:i+1}));
   const current={index:n,round:1,epoch:0,opened:false,steps};
   const copy=JSON.stringify(current);
   eq(canCompareRound(current),true,'ready');
   const next=restartReviewedRound(current);
   eq(JSON.stringify(current),copy,'input unchanged');
   eq(next.round,2,'round');eq(next.index,0,'index');
   eq(next.baseline.steps,reviewSnapshot(current),'baseline');
   eq(next.steps.map(s=>[s.opened,s.acknowledged,s.observed,s.verdict,s.runId]),Array.from({length:n},()=>[false,false,null,null,null]),'cleared receipts');
   eq(next.steps.map(s=>s.criterion),steps.map(s=>s.criterion),'criteria retained');
   eq(canCompareRound(next),false,'not ready');
  });
 }
 for(const round of [0,-1,1.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1]){
  check('invalid round '+String(round),()=>{
   let rejected=false;try{engineInput('',[],hash,round)}catch(e){rejected=e.message==='invalid-review-round'}eq(rejected,true,'invalid round refused');
  });
 }
 check('round limit',()=>{let rejected=false;try{restartReviewedRound({round:100,index:1,steps:[{criterion:'x',opened:true,verdict:'pass'}]})}catch(e){rejected=e.message==='review-round-unavailable'}eq(rejected,true,'round cap')});
 check('isolation',()=>{eq(review(null,{enabled:true,isolated:true}).status,'isolated','isolated');eq(review(null).status,'off','disabled')});
 return cases;
}

console.log('CHAT WORKFLOW REVIEW MATRIX: PASS ('+testChatBridge(bridge,reviewAssistantWorkflow)+' cases)');
