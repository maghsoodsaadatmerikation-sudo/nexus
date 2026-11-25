import {createExperienceEditReview} from './studio-workflow-outcome.mjs';

// Host-owned session metadata is a consistency boundary, not authentication.
// Returns a validated proposed state only: no persistence, execution or model context.
export function createArchiveExperienceReview(validateState){
 if(typeof validateState!=='function')throw Error('invalid-state-validator');
 const engine=createExperienceEditReview();
 let pending=null;
 const id=s=>typeof s==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(s);
 function invalidate(){pending=null;engine.invalidate()}
 function read(value,session,workflow){
  if(!session||session.enabled!==true||session.vaultUnlocked!==true||session.busy!==false||session.isolated!==false||
     !id(session.projectId)||!id(session.threadId)||!Number.isSafeInteger(session.revision)||session.revision<0||!id(workflow))throw Error('archive-review-unavailable');
  const data=validateState(value),project=data.projects.find(p=>p.id===session.projectId),thread=project?.threads.find(t=>t.id===session.threadId);
  if(!thread||thread.temporary||thread.isolated||thread.archived)throw Error('archive-review-scope');
  const snapshot=project.experiences?.find(s=>s.workflow_id===workflow);
  return {data,project,exists:!!snapshot,snapshot:snapshot||{project_id:project.id,workflow_id:workflow,revision:0,entries:[]}};
 }
 const binding=s=>JSON.stringify([s.projectId,s.threadId,s.revision]);
 function stage(value,session,workflow,operation,{criteria,attempts}={}){
  invalidate();
  const current=read(value,session,workflow);
  if(!current.exists&&(current.project.experiences||[]).length>=12)throw Error('archive-experience-capacity');
  // Enforce workflow labels even on older compatible outcome-engine versions.
  if(['accept','refresh'].includes(operation?.kind)){
   if(!Array.isArray(attempts)||attempts.length<1||attempts.length>12)throw Error('invalid-experience-input');
   for(const a of attempts)for(const run of [a?.before,a?.after]){
    if(!run||run.scope?.project_id!==session.projectId||run.scope?.workflow_id!==workflow||!Array.isArray(run.observations)||
       run.observations.length>60||run.observations.some(o=>o?.workflow_id!==workflow))throw Error('archive-evidence-scope');
   }
  }
  const review=engine.stage(current.snapshot,operation,{enabled:true,criteria,attempts});
  const ticket=Object.freeze(Object.create(null));
  pending={ticket,inner:review.ticket,session:binding(session),workflow,exists:current.exists};
  const {ticket:discard,...summary}=review;
  return Object.freeze({...summary,ticket,storage_authorized:false});
 }
 function approve(ticket,value,session,{approved=false}={}){
  if(!pending||pending.ticket!==ticket)throw Error('inactive-archive-review');
  const review=pending;pending=null;
  try{
   if(approved!==true)throw Error('archive-review-not-approved');
   const current=read(value,session,review.workflow);
   if(binding(session)!==review.session||current.exists!==review.exists)throw Error('stale-archive-review');
   const snapshot=engine.approve(review.inner,current.snapshot,{enabled:true,approved:true});
   const list=(current.project.experiences||[]).filter(s=>s.workflow_id!==review.workflow);
   // Preserve empty snapshots as revision tombstones, not as active experience.
   current.project.experiences=[...list,snapshot];
   const next=validateState(current.data);
   return {status:'proposed_state',state:next,storage_authorized:false,execution_authorized:false,automatic_application:false};
  }finally{engine.invalidate()}
 }
 return Object.freeze({stage,approve,invalidate});
}

// Local JSON import is a user-supplied report, not authenticated evidence.
// Restrict the import to one explicit accept/refresh operation.
export function stageImportedExperience(adapter,value,session,raw){
 if(typeof raw!=='string'||raw.length>65536)throw Error('invalid-experience-import');
 const report=JSON.parse(raw);
 const exact=(x,keys)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join('|')===keys;
 if(!exact(report,'attempts|criteria|operation|schema|workflow_id')||report.schema!=='nexus.experience-review.v1'||
 !exact(report.operation,'correction_code|criterion_id|kind')||!['accept','refresh'].includes(report.operation.kind)||
 !Array.isArray(report.criteria)||report.criteria.length<1||report.criteria.length>30||
 !Array.isArray(report.attempts)||report.attempts.length<2||report.attempts.length>12)throw Error('invalid-experience-import');
 return adapter.stage(value,session,report.workflow_id,report.operation,{criteria:report.criteria,attempts:report.attempts});
}
