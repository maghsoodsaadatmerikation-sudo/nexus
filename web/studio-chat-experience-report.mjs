import {reviewCorrectionExperience} from './studio-workflow-outcome.mjs';

// The caller must capture a stable random session ID and compute the workflow
// hash over the exact draft and normalized criteria. Labels are not proof.
// This is an unencrypted report proposal; no download, persistence or learning.
export function buildChatExperienceReport(rounds,request,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(!enabled||isolated)return {status:isolated?'isolated':'off',report:null};
 const id=x=>typeof x==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(x);
 const hash=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
 if(!request||request.same_correction_reported!==true||request.complete_relevant_history_reported!==true||
    !id(request.project_id)||!hash(request.plan_sha256)||!id(request.session_id)||request.session_id.length>48||
    !id(request.correction_code)||!id(request.criterion_id)||!['accept','refresh'].includes(request.kind))throw Error('invalid-report-request');
 if(!Array.isArray(rounds)||rounds.length<4||rounds.length>24||rounds.length%2)throw Error('incomplete-paired-history');
 // Refuse gaps or a retained suffix: never silently select successful pairs.
 const first=rounds[0]?.steps;
 if(!Array.isArray(first)||first.length<2||first.length>6)throw Error('invalid-report-round');
 const signature=steps=>JSON.stringify(steps.map(s=>[s.command,s.criterion.trim()]));
 const valid=steps=>Array.isArray(steps)&&steps.length===first.length&&steps.every(s=>s&&id(s.command)&&typeof s.criterion==='string'&&s.criterion.trim().length>0&&s.criterion.trim().length<=260&&s.opened===true&&s.acknowledged===true&&s.observed!=='started'&&['pass','fail','inconclusive'].includes(s.verdict));
 if(!valid(first))throw Error('invalid-report-round');
 const expected=signature(first);
 const workflow_id='wf-'+request.plan_sha256;
 const criteria=first.map((_,i)=>({id:'s'+(i+1),required:true,evidence_kind:'human_review'}));
 if(!criteria.some(c=>c.id===request.criterion_id))throw Error('invalid-report-criterion');
 const runs=rounds.map((round,i)=>{
  if(!round||round.round!==i+1||!valid(round.steps)||signature(round.steps)!==expected)throw Error('incomplete-or-incomparable-history');
  const scope={project_id:request.project_id,workflow_id,run_id:request.session_id+'-r'+round.round,plan_sha256:request.plan_sha256};
  return {scope,observations:round.steps.map((s,j)=>({...scope,criterion_id:criteria[j].id,evidence_id:scope.run_id+'-h'+(j+1),kind:'human_review',result:s.verdict}))};
 });
 const attempts=[];
 for(let i=0;i<runs.length;i+=2)attempts.push({correction_code:request.correction_code,before:runs[i],after:runs[i+1]});
 const result=reviewCorrectionExperience({project_id:request.project_id,workflow_id},criteria,attempts,{enabled:true});
 const match=result.candidates.find(c=>c.criterion_id===request.criterion_id&&c.correction_code===request.correction_code);
 if(!match)return {status:'insufficient_reported_support',report:null,completion_verified:false,execution_authorized:false};
 const report={schema:'nexus.experience-review.v1',workflow_id,operation:{kind:request.kind,criterion_id:request.criterion_id,correction_code:request.correction_code},criteria,attempts};
 return {status:'review_only',report,supporting_pair_count:match.supporting_pair_count,completion_verified:false,execution_authorized:false,automatic_application:false};
}
