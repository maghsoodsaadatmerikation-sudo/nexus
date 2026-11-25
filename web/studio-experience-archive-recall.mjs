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
 const failed=assessment.items.filter(i=>i.disposition==='reported_failure').map(i=>i.criterion_id);
 if(!failed.length)return result('no_reported_failure');
 const recalled=reviewExperienceRecall(snapshot,{project_id:scope.project_id,workflow_id:scope.workflow_id,revision:snapshot.revision,criterion_ids:failed},request.criteria,request.attempts,{enabled:true});
 const receipts=new Set(request.observations.map(o=>o.evidence_id));
 for(const attempt of request.attempts)for(const run of [attempt.before,attempt.after]){
  if(run.scope.run_id===scope.run_id)throw Error('current-run-in-experience');
  if(run.observations.some(o=>receipts.has(o.evidence_id)))throw Error('current-evidence-in-experience');
 }
 return {...recalled,...boundary};
}
