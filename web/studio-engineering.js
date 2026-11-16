/* NEXUS Studio Engineering Agent: inert, bounded review of local handoff artifacts.
   This module does not execute commands, contact a server, or approve a plan. */
(function(root){'use strict';
const MAX_BYTES=32768,enc=new TextEncoder();
const TOOLS={read:['tool','path'],write:['tool','path','text'],edit:['tool','path','before','after'],run:['tool','image','argv','timeout_seconds'],verify_sha256:['tool','path','expected_sha256'],package:['tool','output'],search:['tool','query','case_sensitive'],preview_edit:['tool','path','before','after'],research:['tool','provider','name']};
const RISK={read:'read-only',write:'writes-files',edit:'writes-files',run:'executes-container',verify_sha256:'read-only',package:'exports-archive',search:'read-only',preview_edit:'read-only',research:'network-metadata'};
const HASH=/^[0-9a-f]{64}$/,WORKSPACE=/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}$/;
const deny=x=>{throw Error('engineering-'+x)};
const obj=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const string=(s,min=0,max=1024)=>typeof s==='string'&&s.length>=min&&s.length<=max;
const keys=(x,expected)=>obj(x)&&Object.keys(x).length===expected.length&&expected.every(k=>Object.hasOwn(x,k));
const path=s=>string(s,1,512)&&!/[\\\x00]/.test(s)&&s.split('/').every(p=>p!==''&&p!=='.'&&p!=='..'&&enc.encode(p).length<=128);
function decode(raw){
 if(!string(raw,1,MAX_BYTES)||enc.encode(raw).length>MAX_BYTES)deny('size');
 let val;try{val=JSON.parse(raw)}catch{deny('json')}
 // First parse JSON syntax, then reject all duplicate object keys (including
 // escaped-key aliases). JSON strings are tokenized before structural braces.
 const scopes=[];const tokens=raw.match(/"(?:\\[\s\S]|[^"\\])*"(?:[ \t\r\n]*:)?|[{}]/g)||[];
 for(const token of tokens){
  if(token==='{')scopes.push(new Set());
  else if(token==='}')scopes.pop();
  else if(token.endsWith(':')){
   const name=JSON.parse(token.slice(0,-1));const scope=scopes[scopes.length-1];
   if(!scope||scope.has(name))deny('duplicate-key');scope.add(name);
  }
 }
 return val;
}
function steps(xs){
 if(!Array.isArray(xs)||xs.length<1||xs.length>12)deny('step-count');
 return xs.map((s,i)=>{
  if(!obj(s)||!Object.hasOwn(TOOLS,s.tool)||!keys(s,TOOLS[s.tool]))deny('step-shape');
  if('path'in s&&!path(s.path))deny('path');
  if(s.tool==='write'&&(!string(s.text,0,1048576)||enc.encode(s.text).length>1048576))deny('text');
  if(['edit','preview_edit'].includes(s.tool)&&(!string(s.before,1,1048576)||!string(s.after,0,1048576)))deny('edit');
  if(s.tool==='run'&&(!string(s.image,1,300)||!/^[a-zA-Z0-9][a-zA-Z0-9._:/-]*@sha256:[0-9a-f]{64}$/.test(s.image)||!Array.isArray(s.argv)||s.argv.length<1||s.argv.length>64||s.argv.some(a=>!string(a,1,16384)||a.includes('\0'))||!Number.isInteger(s.timeout_seconds)||s.timeout_seconds<1||s.timeout_seconds>120))deny('run');
  if(s.tool==='verify_sha256'&&!HASH.test(s.expected_sha256))deny('hash');
  if(s.tool==='package'&&(!string(s.output,1,1024)||!s.output.startsWith('/')))deny('archive');
  if(s.tool==='search'&&(!string(s.query,1,128)||/[\x00\r\n]/.test(s.query)||typeof s.case_sensitive!=='boolean'))deny('search');
  if(s.tool==='research'&&(!['pypi','crates','github-release'].includes(s.provider)||!string(s.name,1,128)||!(s.provider==='github-release'?/^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(s.name):/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(s.name))))deny('research');
  return {index:i,tool:s.tool,risk:RISK[s.tool]};
 });
}
function labeledSteps(s,{status=false}={}){
 if(!Array.isArray(s)||s.length>12)deny('steps');
 return s.map((x,i)=>{
  if(!obj(x)||!Number.isInteger(x.index)||x.index!==i||!Object.hasOwn(TOOLS,x.tool))deny('step-metadata');
  if(status){if(!keys(x,['index','tool','status'])||!['completed','failed','denied'].includes(x.status))deny('step-status')}
  else if(!keys(x,['index','tool','risk'])||x.risk!==RISK[x.tool])deny('step-risk');
  return {index:x.index,tool:x.tool,risk:RISK[x.tool],...(status?{status:x.status}:{})};
 });
}
function inspect(raw){
 const value=decode(raw);
 if(!obj(value)||!string(value.schema,1,80))deny('schema');
 if(value.schema==='nexus.engineering.proposal.v1'){
  if(!keys(value,['schema','workspace','steps'])||!WORKSPACE.test(value.workspace))deny('proposal');
  return {kind:'proposal',workspace:value.workspace,state:'proposal-not-executed',authority:'none',steps:steps(value.steps),private:true,raw};
 }
 if(value.schema==='nexus.engineering.review.v1'){
  if(!keys(value,['schema','authority','plan_sha256','workspace_sha256','workspace','plan_version','steps','status','review_required','note'])||
    value.authority!=='none'||!HASH.test(value.plan_sha256)||!HASH.test(value.workspace_sha256)||!WORKSPACE.test(value.workspace)||
    value.plan_version!==3||value.status!=='not-executed'||value.review_required!==true||!string(value.note,1,2048))deny('review');
  return {kind:'review',workspace:value.workspace,state:'not-executed',authority:'none',plan_sha256:value.plan_sha256,workspace_sha256:value.workspace_sha256,steps:labeledSteps(value.steps),private:false};
 }
 if(value.schema==='nexus.engineering.chat-receipt.v1'){
  if(!keys(value,['schema','origin','authority','verification','plan_sha256','journal_state','execution_status','workspace_sha256_before','workspace_sha256_after','steps','note'])||
    value.origin!=='local-engineering-worker'||value.authority!=='none'||value.verification!=='not-independent-attestation'||
    !HASH.test(value.plan_sha256)||!HASH.test(value.workspace_sha256_before)||!string(value.note,1,2048))deny('receipt');
  const started=value.journal_state==='started',finished=value.journal_state==='finished';
  if(!started&&!finished)deny('journal-state');
  if(started&&(value.execution_status!=='interrupted-or-in-progress'||value.workspace_sha256_after!==null||!Array.isArray(value.steps)||value.steps.length!==0))deny('started');
  if(finished&&(!['complete','execution-failed','step-denied','post-state-unverifiable'].includes(value.execution_status)||
    (value.workspace_sha256_after!==null&&!HASH.test(value.workspace_sha256_after))))deny('finished');
  return {kind:'receipt',state:value.execution_status,authority:'none',plan_sha256:value.plan_sha256,workspace_sha256:value.workspace_sha256_before,
    ...(typeof value.workspace_sha256_after==='string'?{workspace_after:value.workspace_sha256_after}:{}),steps:labeledSteps(value.steps,{status:true}),private:false};
 }
 deny('unknown-schema');
}
function report(view){
 if(!view||!['proposal','review','receipt'].includes(view.kind))deny('uninspected');
 const lines=['NEXUS Engineering Agent · '+view.kind,'Execution state: '+view.state,'Authority: none','Verified independently: no'];
 if(view.workspace)lines.push('Workspace label: '+view.workspace);
 if(view.plan_sha256)lines.push('Plan SHA-256: '+view.plan_sha256);
 if(view.workspace_sha256)lines.push('Workspace SHA-256 (before): '+view.workspace_sha256);
 if(view.workspace_after)lines.push('Workspace SHA-256 (after): '+view.workspace_after);
 lines.push('Steps: '+view.steps.length);
 for(const s of view.steps)lines.push((s.index+1)+'. '+s.tool+' · '+s.risk+(s.status?' · '+s.status:''));
 lines.push('Untrusted operator-local metadata. This is neither authorization nor a verified human decision. Full private plans and commands are not included.');
 return lines.join('\n');
}
root.NexusEngineering=Object.freeze({inspect,report,MAX_BYTES});
})(globalThis);
