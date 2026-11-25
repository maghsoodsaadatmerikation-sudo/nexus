import {prepareChatArchiveRecall,reviewArchivedExperience} from './studio-experience-archive-recall.mjs';
import {reviewAssistantWorkflow} from './studio-workflow-review.mjs';

// Source-only bridge for multiple explicitly selected reports about one failed
// criterion. Host supplies a live session, exact draft digest and UI statuses.
// No estimates are inferred, no report is retained and no authority is granted.
export function reviewChatCorrectionOptions(validateState,value,session,input,{enabled=false,isolated=false}={}){
 const boundary={automatic_selection:false,automatic_application:false,execution_authorized:false,completion_verified:false,storage_authorized:false,model_context_authorized:false};
 const empty=status=>({status,comparison:null,scenarios:null,...boundary});
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return empty(isolated?'isolated':'off');
 if(!session||session.enabled!==true||session.vaultUnlocked!==true||session.busy!==false||session.isolated!==false)throw Error('archive-recall-unavailable');
 const {reports,context,snapshotRevision,comparison,scenarios}=input||{};
 if(!context||context.projectId!==session.projectId||context.threadId!==session.threadId||context.sessionRevision!==session.revision||!Number.isSafeInteger(snapshotRevision)||snapshotRevision<0)throw Error('archive-recall-scope');
 if(!Array.isArray(reports)||reports.length<2||reports.length>5||reports.some(r=>typeof r!=='string'||r.length<1||r.length>65536)||reports.reduce((n,r)=>n+r.length,0)>196608||!comparison||!Array.isArray(comparison.options)||comparison.options.length!==reports.length)throw Error('invalid-chat-comparison-input');
 const prepared=reports.map(raw=>prepareChatArchiveRecall(raw,context));
 const first=prepared[0],attempts=prepared.flatMap(p=>p.attempts);
 if(attempts.length>12)throw Error('chat-comparison-attempt-capacity');
 const codes=prepared.map(p=>p.attempts[0].correction_code),wanted=new Set(codes);
 if(wanted.size!==codes.length||comparison.options.some(o=>!wanted.has(o?.correction_code))||new Set(comparison.options.map(o=>o.correction_code)).size!==codes.length||reports.some(raw=>JSON.parse(raw).operation.criterion_id!==comparison.criterion_id))throw Error('chat-comparison-option-mismatch');
 if(scenarios!==undefined&&(!Array.isArray(scenarios?.options)||scenarios.criterion_id!==comparison.criterion_id||scenarios.options.some(o=>!wanted.has(o?.correction_code))))throw Error('chat-comparison-scenario-mismatch');
 const recall=reviewArchivedExperience(validateState,value,session,{...first,attempts,snapshotRevision},{enabled:true});
 if(recall.status!=='review_only')return empty(recall.status);
 const eligible=new Set(recall.matches.filter(m=>m.criterion_id===comparison.criterion_id).map(m=>m.correction_code));
 if(codes.some(c=>!eligible.has(c)))return empty('insufficient_recalled_support');
 // Preserve the existing central engine's effect and execution-status gates.
 // Unknown commands remain unknown; a human verdict is not a tool receipt.
 const phases={started:'running',succeeded:'succeeded',failed:'failed',cancelled:'cancelled',partial:'blocked'};
 const plan={goal:'Review prior correction alternatives',steps:context.steps.map((s,i)=>({id:'s'+(i+1),needs:[],effect:s.command==='code'?'local_compute':s.command==='research'?'network_read':'unknown',success_criteria:s.criterion.trim()}))};
 const step_observations=context.steps.flatMap((s,i)=>Object.hasOwn(phases,s.observed)?[{...first.scope,id:'s'+(i+1),status:phases[s.observed]}]:[]);
 const data=validateState(value),snapshot=data.projects.find(p=>p.id===session.projectId)?.experiences?.find(s=>s.workflow_id===first.scope.workflow_id);
 const review=reviewAssistantWorkflow({scope:first.scope,plan,criteria:first.criteria,step_observations,evidence:first.observations,experience:{snapshot,revision:snapshotRevision,attempts},correction_comparison:comparison,...(scenarios===undefined?{}:{correction_scenarios:scenarios})},{enabled:true,experienceEnabled:true});
 return {status:review.correction_comparison.status,comparison:review.correction_comparison,scenarios:review.correction_scenarios??null,...boundary};
}
