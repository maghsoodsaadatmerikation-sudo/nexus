import {evaluateWorkflowOutcome,reviewExperienceRecall} from './studio-workflow-outcome.mjs';

// Read-only archive bridge. The host supplies the live, unlocked session and
// expected revisions. Scope labels and supplied evidence are not authentication.
export function reviewArchivedExperience(validateState,value,session,request,{enabled=false,isolated=false}={}){
 const boundary={automatic_application:false,execution_authorized:false,completion_verified:false,storage_authorized:false,model_context_authorized:false};
 const result=status=>({status,matches:[],...boundary});
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return result(isolated?'isolated':'off');
 const id=x=>typeof x==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(x);
 if(typeof validateState!=='function'||!session||session.enabled!==true||session.vaultUnlocked!==true||session.busy!==false||session.isolated!==false||!id(session.projectId)||!id(session.threadId)||!Number.isSafeInteger(session.revision)||session.revision<0)throw Error('archive-recall-unavailable');
 const scope=request?.scope;
 if(!scope||scope.project_id!==session.projectId||!id(scope.workflow_id)||request.threadId!==session.threadId||request.sessionRevision!==session.revision||!Number.isSafeInteger(request.snapshotRevision)||request.snapshotRevision<0)throw Error('archive-recall-scope');
 const data=validateState(value),project=data.projects.find(p=>p.id===session.projectId),thread=project?.threads.find(t=>t.id===session.threadId);
 if(!thread||thread.temporary||thread.isolated||thread.archived)throw Error('archive-recall-scope');
 const snapshot=project.experiences?.find(s=>s.workflow_id===scope.workflow_id);
 if(!snapshot)return result('no_snapshot');
 if(snapshot.revision!==request.snapshotRevision)throw Error('stale-archive-recall');
 const assessment=evaluateWorkflowOutcome(scope,request.criteria,request.observations,{enabled:true});
 if(assessment.items.some(i=>i.required&&['conflicting_reports','requires_reconciliation'].includes(i.disposition)))return result('withheld_pending_reconciliation');
 const failed=assessment.items.filter(i=>i.disposition==='reported_failure'&&i.criterion_id===(request.criterion??i.criterion_id)).map(i=>i.criterion_id);
 if(!failed.length)return result('no_reported_failure');
 const recalled=reviewExperienceRecall(snapshot,{project_id:scope.project_id,workflow_id:scope.workflow_id,revision:snapshot.revision,criterion_ids:failed},request.criteria,request.attempts,{enabled:true});
 const receipts=new Set(request.observations.map(o=>o.evidence_id));
 for(const attempt of request.attempts)for(const run of [attempt.before,attempt.after]){
  if(run.scope.run_id===scope.run_id)throw Error('current-run-in-experience');
  if(run.observations.some(o=>receipts.has(o.evidence_id)))throw Error('current-evidence-in-experience');
 }
 return {...recalled,...boundary};
}

// Chat reports are bound to the exact current draft/criteria digest. Do not
// use arbitrary workflow labels, changed criteria or a report's own scope as
// the source of current observations. The host computes the digest locally.
export function prepareChatArchiveRecall(raw,{projectId,threadId,sessionRevision,sessionId,round,planHash,steps}={}){
 const id=x=>typeof x==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(x);
 const exact=(x,keys)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join('|')===keys;
 if(typeof raw!=='string'||!raw||raw.length>65536||!id(projectId)||!id(threadId)||!id(sessionId)||sessionId.length>48||!Number.isSafeInteger(sessionRevision)||sessionRevision<0||!Number.isSafeInteger(round)||round<1||round>100||typeof planHash!=='string'||!/^[a-f0-9]{64}$/.test(planHash)||!Array.isArray(steps)||steps.length<2||steps.length>6)throw Error('invalid-chat-recall-input');
 const report=JSON.parse(raw),workflow_id='wf-'+planHash;
 if(!exact(report,'attempts|criteria|operation|schema|workflow_id')||report.schema!=='nexus.experience-review.v1'||report.workflow_id!==workflow_id||!exact(report.operation,'correction_code|criterion_id|kind')||!['accept','refresh'].includes(report.operation.kind)||!id(report.operation.correction_code)||!id(report.operation.criterion_id)||!Array.isArray(report.attempts)||report.attempts.length<2||report.attempts.length>12)throw Error('invalid-chat-recall-report');
 const criteria=steps.map((s,i)=>{
  if(!s||typeof s.criterion!=='string'||!s.criterion.trim()||s.criterion.trim().length>260||s.opened!==true||s.acknowledged!==true||s.observed==='started'||!['pass','fail','inconclusive'].includes(s.verdict))throw Error('incomplete-chat-recall-round');
  return {id:'s'+(i+1),required:true,evidence_kind:'human_review'};
 });
 if(!Array.isArray(report.criteria)||report.criteria.length!==criteria.length||criteria.some((c,i)=>!exact(report.criteria[i],'evidence_kind|id|required')||Object.keys(c).some(k=>report.criteria[i][k]!==c[k]))||!criteria.some(c=>c.id===report.operation.criterion_id))throw Error('chat-recall-criteria-mismatch');
 for(const attempt of report.attempts){
  if(!exact(attempt,'after|before|correction_code')||attempt.correction_code!==report.operation.correction_code)throw Error('chat-recall-correction-mismatch');
  for(const run of [attempt.before,attempt.after]){
   if(!exact(run,'observations|scope')||!exact(run.scope,'plan_sha256|project_id|run_id|workflow_id')||run.scope.project_id!==projectId||run.scope.workflow_id!==workflow_id||run.scope.plan_sha256!==planHash||!Array.isArray(run.observations)||run.observations.length!==criteria.length||run.observations.some(o=>!exact(o,'criterion_id|evidence_id|kind|plan_sha256|project_id|result|run_id|workflow_id')||o.kind!=='human_review'))throw Error('chat-recall-evidence-scope');
  }
 }
 const scope={project_id:projectId,workflow_id,run_id:sessionId+'-r'+round,plan_sha256:planHash};
 const observations=steps.map((s,i)=>({...scope,criterion_id:criteria[i].id,evidence_id:scope.run_id+'-h'+(i+1),kind:'human_review',result:s.verdict}));
 return {scope,observations,criteria,attempts:report.attempts,threadId,sessionRevision,criterion:report.operation.criterion_id};
}
