// Test-only extraction of exact pure composer helper functions. No browser or production eval.
import {readFileSync} from 'node:fs';
import {reviewAssistantWorkflow} from '../web/studio-workflow-review.mjs';
import {buildChatExperienceReport} from '../web/studio-chat-experience-report.mjs';
const source=readFileSync(new URL('../web/studio-composer-ui.js',import.meta.url),'utf8');
const start='function humanCriterion(step){',end='async function showEngineReview(button,notice){';
if(source.split(start).length!==2||source.split(end).length!==2||source.indexOf(end)<source.indexOf(start))throw Error('chat bridge extraction markers changed');
const bridge=new Function(source.slice(source.indexOf(start),source.indexOf(end))+'\nreturn {humanCriterion,engineInput,reviewSnapshot,canCompareRound,restartReviewedRound,comparableFailureHistory,adaptiveChatDraft,forgetReviewedHistory,completeReportRounds};')();
function testChatBridge(bridge,review){
 const {humanCriterion,engineInput,reviewSnapshot,canCompareRound,restartReviewedRound,comparableFailureHistory,adaptiveChatDraft,forgetReviewedHistory,completeReportRounds}=bridge;
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
 check('consented comparable history',()=>{
  const step={result:{route:['code']},criterion:'test',opened:true,acknowledged:true,observed:'succeeded',verdict:'fail',runId:1};
  const first={draft:'test',round:1,index:1,steps:[step],history:[]};
  const second=restartReviewedRound(first);second.steps=[{...step,runId:2}];second.index=1;
  const third=restartReviewedRound(second);
  const snap=reviewSnapshot(third);
  const hist=comparableFailureHistory(third,hash,snap);
  eq(hist.length,2,'retained rounds');
  eq(hist.map(r=>r.scope.run_id),['review-1','review-2'],'distinct runs');
  const cur=engineInput(third.draft,snap,hash,third.round);
  cur.failure_history=hist;
  eq(review(cur,{enabled:true,experienceEnabled:true}).failure_patterns.patterns[0].historical_reported_failure,2,'repeated failure');
  eq(review(cur,{enabled:true}).failure_patterns.status,'off','disabled history');
  eq(comparableFailureHistory(third,hash,[{...snap[0],criterion:'different'}]),[],'changed criterion');
  eq(comparableFailureHistory(third,hash,[{...snap[0],command:'research'}]),[],'changed command');
  eq(comparableFailureHistory({...third,history:[...third.history,{round:3,steps:snap}]},hash,snap).length,2,'exclude current round');
 });
 check('bounded history',()=>{
  const step={result:{route:['code']},criterion:'test',opened:true,observed:'succeeded',verdict:'fail'};
  const current={round:32,index:1,steps:[step],history:Array.from({length:31},(_,i)=>({round:i+1,steps:reviewSnapshot({steps:[step]})}))};
  const next=restartReviewedRound(current);
  eq(next.history.length,30,'bounded');
  eq(next.history[0].round,3,'oldest removed');
  eq(next.history[29].round,32,'latest retained');
  eq(current.history.length,31,'input unchanged');
 });
 check('adaptive draft with repeated human-reported failures',()=>{
  const steps=[{command:'code',criterion:'Returns 42',opened:true,observed:'succeeded',verdict:'fail'},{command:'write',criterion:'Reviewed',opened:true,observed:null,verdict:'pass'}];
  const cur=engineInput('',steps,hash,3);
  cur.failure_history=[1,2].map(round=>{const p=engineInput('',steps,hash,round);return {scope:p.scope,observations:p.evidence}});
  const original=JSON.stringify(cur);
  const result=review(cur,{enabled:true,experienceEnabled:true});
  const draft=adaptiveChatDraft(cur,result);
  eq(draft.plan.steps.map(s=>s.id),['pre-s1','s1','s2'],'adds only recurrent checkpoint');
  eq(draft.plan.steps[0].effect,'human_review','human checkpoint');
  eq(draft.plan.steps[1].needs,['pre-s1'],'proposed dependency');
  eq(draft.checkpoints,[{criterion_id:'s1',check_step_id:'pre-s1',protected_step_ids:['s1']}],'mapping');
  const audited=review({...cur,adaptive_plan:{scope:{...cur.scope,run_id:'draft-3',plan_sha256:'b'.repeat(64)},...draft}},{enabled:true,experienceEnabled:true}).adaptive_plan;
  eq(audited.findings[0].status,'declared_checkpoint_present','structural finding');
  eq(audited.review_required,true,'human review remains required');
  eq(audited.execution_authorized,false,'no execution');
  eq(JSON.stringify(cur),original,'does not mutate current plan');
 });
 check('adaptive draft ignores sparse or disabled history',()=>{
  const steps=[{command:'code',criterion:'test',opened:true,observed:'succeeded',verdict:'fail'}];
  const cur=engineInput('',steps,hash,2),prior=engineInput('',steps,hash,1);
  cur.failure_history=[{scope:prior.scope,observations:prior.evidence}];
  eq(adaptiveChatDraft(cur,review(cur,{enabled:true,experienceEnabled:true})),null,'one prior failure');
  eq(adaptiveChatDraft(cur,review(cur,{enabled:true})),null,'history disabled');
 });
 check('adaptive draft bounds',()=>{
  const steps=Array.from({length:6},()=>({command:'code',criterion:'test',opened:true,observed:'succeeded',verdict:'fail'}));
  const cur=engineInput('',steps,hash,3);
  cur.failure_history=[1,2].map(round=>{const p=engineInput('',steps,hash,round);return {scope:p.scope,observations:p.evidence}});
  const draft=adaptiveChatDraft(cur,review(cur,{enabled:true,experienceEnabled:true}));
  eq(draft.plan.steps.length,12,'bounded plan');
  eq(draft.checkpoints.length,6,'one checkpoint per recurrent criterion');
 });
 check('explicit history deletion preserves current assessment',()=>{
  const step={result:{route:['code']},criterion:'test',opened:true,observed:'succeeded',verdict:'fail'};
  const previous={round:1,steps:reviewSnapshot({steps:[step]})};
  const state={draft:'test',round:2,epoch:5,index:1,steps:[step],baseline:previous,history:[previous]};
  const before=JSON.stringify(state),next=forgetReviewedHistory(state);
  eq(next.epoch,6,'invalidates pending review');eq(next.history,[],'clears history');eq(next.baseline,null,'clears baseline');
  eq(next.steps,state.steps,'keeps current assessment');eq(next.index,state.index,'keeps progress');
  eq(comparableFailureHistory(next,hash,reviewSnapshot(next)),[],'no prior receipts');
  eq(JSON.stringify(state),before,'input unchanged');
 });
 check('report export includes all complete rounds',()=>{
  const step={result:{route:['code']},criterion:'test',opened:true,acknowledged:true,observed:'succeeded',verdict:'fail'};
  const prior=[1,2,3].map(round=>({round,steps:reviewSnapshot({steps:[step]})}));
  const current={round:4,index:1,steps:[{...step,verdict:'pass'}],history:prior};
  const rounds=completeReportRounds(current);
  eq(rounds.map(r=>r.round),[1,2,3,4],'all rounds');
  eq(rounds[3].steps[0].verdict,'pass','current assessment');
  eq(completeReportRounds({...current,index:0}),null,'unfinished');
  eq(completeReportRounds({...current,round:5}),null,'unpaired');
  eq(completeReportRounds({...current,history:prior.slice(1)}),null,'missing history');
  eq(completeReportRounds({...current,history:[prior[0],prior[0],prior[2]]}),null,'duplicate history');
  eq(completeReportRounds({...current,round:26}),null,'bounded history');
  eq(current.history.length,3,'input unchanged');
 });
 check('isolation',()=>{eq(review(null,{enabled:true,isolated:true}).status,'isolated','isolated');eq(review(null).status,'off','disabled')});
 return cases;
}

console.log('CHAT WORKFLOW REVIEW MATRIX: PASS ('+testChatBridge(bridge,reviewAssistantWorkflow)+' cases)');
function testExperienceReport(){
 let checks=0;
 const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('report fixture '+checks+' '+JSON.stringify({a,b}))};
 const reject=(fn,msg)=>{checks++;let error;try{fn()}catch(e){error=e}if(error?.message!==msg)throw Error('report rejection '+checks+' '+error)};
 const req={project_id:'p1',plan_sha256:'a'.repeat(64),session_id:'session-1',correction_code:'fix',criterion_id:'s1',kind:'accept',same_correction_reported:true,complete_relevant_history_reported:true};
 const on={enabled:true};
 const rounds=['fail','pass','fail','pass'].map((verdict,i)=>({round:i+1,steps:[{command:'code',criterion:'Returns 42',opened:true,acknowledged:true,observed:'succeeded',verdict},{command:'write',criterion:'Reviewed',opened:true,acknowledged:true,verdict:'pass'}]}));
 const before=JSON.stringify(rounds);
 const result=buildChatExperienceReport(rounds,req,on);
 eq(result.status,'review_only');eq(result.supporting_pair_count,2);
 eq(result.completion_verified,false);eq(result.execution_authorized,false);eq(result.automatic_application,false);
 eq(result.report.schema,'nexus.experience-review.v1');eq(result.report.workflow_id,'wf-'+req.plan_sha256);
 eq(result.report.operation,{kind:'accept',criterion_id:'s1',correction_code:'fix'});
 eq(result.report.attempts.map(a=>[a.before.scope.run_id,a.after.scope.run_id]),[['session-1-r1','session-1-r2'],['session-1-r3','session-1-r4']]);
 eq(result.report.attempts.flatMap(a=>[a.before,a.after]).flatMap(r=>r.observations).every(o=>o.kind==='human_review'&&o.project_id==='p1'),true);
 eq(JSON.stringify(result.report).includes('Returns 42'),false);
 eq(JSON.stringify(result.report).includes('Reviewed'),false);
 eq(JSON.stringify(rounds),before);
 eq(buildChatExperienceReport(rounds,req,on),result);
 eq(buildChatExperienceReport(rounds,{...req,kind:'refresh'},on).report.operation.kind,'refresh');
 eq(buildChatExperienceReport(null,null).status,'off');
 eq(buildChatExperienceReport(null,null,{enabled:true,isolated:true}).status,'isolated');
 for(const change of [{same_correction_reported:false},{complete_relevant_history_reported:false},{plan_sha256:'bad'},{project_id:''},{session_id:'x'.repeat(49)},{kind:'delete'}])reject(()=>buildChatExperienceReport(rounds,{...req,...change},on),'invalid-report-request');
 reject(()=>buildChatExperienceReport(rounds,{...req,criterion_id:'s3'},on),'invalid-report-criterion');
 for(const list of [[],rounds.slice(0,2),rounds.slice(0,3),Array(26).fill(rounds[0])])reject(()=>buildChatExperienceReport(list,req,on),'incomplete-paired-history');
 for(const changed of [{round:5},{steps:[{...rounds[3].steps[0],criterion:'Changed'},rounds[3].steps[1]]},{steps:[{...rounds[3].steps[0],acknowledged:false},rounds[3].steps[1]]},{steps:[{...rounds[3].steps[0],observed:'started'},rounds[3].steps[1]]}]){
  reject(()=>buildChatExperienceReport([...rounds.slice(0,3),{...rounds[3],...changed}],req,on),'incomplete-or-incomparable-history');
 }
 const bad=JSON.parse(before);bad[3].steps[0].verdict='fail';
 eq(buildChatExperienceReport(bad,req,on).status,'insufficient_reported_support');
 const regression=JSON.parse(before);regression[3].steps[1].verdict='fail';
 eq(buildChatExperienceReport(regression,req,on).report,null);
 const incomplete=JSON.parse(before);incomplete[2].steps[0].verdict='inconclusive';
 eq(buildChatExperienceReport(incomplete,req,on).report,null);
 return checks;
}
console.log('CHAT EXPERIENCE REPORT: PASS ('+testExperienceReport()+' checks)');
