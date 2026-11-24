// Pure local memory edit proposal. The caller owns persistence and authorization.
const validId=s=>typeof s==='string'&&/^[a-zA-Z0-9-]{1,80}$/.test(s);
const validNote=s=>typeof s==='string'&&s.length<=500&&s.trim().length>0;
function validateNotes(notes){
 if(!Array.isArray(notes)||notes.length>30)throw Error('invalid-memory-list');
 for(const note of notes)if(!validNote(note))throw Error('invalid-memory-note');
}
function validateOperation(op){
 if(!op||typeof op!=='object'||Array.isArray(op))throw Error('invalid-memory-edit');
 const keys=Object.keys(op).sort().join('|');
 if(op.kind==='add'&&keys==='kind|value'&&validNote(op.value))return {kind:'add',value:op.value};
 if(op.kind==='remove'&&keys==='index|kind'&&Number.isInteger(op.index)&&op.index>=0)return {kind:'remove',index:op.index};
 if(op.kind==='replace'&&keys==='index|kind|value'&&Number.isInteger(op.index)&&op.index>=0&&validNote(op.value))return {kind:'replace',index:op.index,value:op.value};
 throw Error('invalid-memory-edit');
}
function nextNotes(notes,op){
 const next=[...notes];
 if(op.kind==='add'){
  if(next.length>=30)throw Error('memory-capacity');
  next.push(op.value);
 }else{
  if(op.index>=next.length)throw Error('memory-index');
  if(op.kind==='replace')next[op.index]=op.value;
  else next.splice(op.index,1);
 }
 return next;
}
export function proposeMemoryEdit(projectId,notes,operation,{isolated=false}={}){
 if(isolated!==false)throw Error('isolated-memory-edit');
 if(!validId(projectId))throw Error('invalid-project');
 validateNotes(notes);
 const op=validateOperation(operation);
 nextNotes(notes,op);
 return Object.freeze({schema:'nexus.memory-edit.v1',project_id:projectId,
  expected:Object.freeze([...notes]),operation:Object.freeze(op)});
}
// Explicit acceptance is required, and the reviewed project and full original
// note list must still match. No persistence, hidden history or remote calls.
export function applyMemoryEdit(projectId,notes,proposal,{approved=false,isolated=false}={}){
 if(approved!==true||isolated!==false)throw Error('memory-edit-not-approved');
 if(!validId(projectId)||!proposal||proposal.schema!=='nexus.memory-edit.v1'||proposal.project_id!==projectId)throw Error('memory-edit-project-mismatch');
 validateNotes(notes);validateNotes(proposal.expected);
 if(notes.length!==proposal.expected.length||notes.some((note,i)=>note!==proposal.expected[i]))throw Error('stale-memory-review');
 return nextNotes(notes,validateOperation(proposal.operation));
}

// A tab-local one-use review controller. The host must supply its own
// monotonic revision and invalidate on lock, project switch, reset or teardown.
// Never serialize tickets, previews or the controller; no storage or I/O.
export function createMemoryEditReview(){
 let pending=null;
 const validRevision=n=>Number.isSafeInteger(n)&&n>=0;
 function stage(projectId,notes,operation,{revision,isolated=false}={}){
  pending=null; // Even a failed replacement invalidates the previous review.
  if(!validRevision(revision))throw Error('invalid-memory-revision');
  const proposal=proposeMemoryEdit(projectId,notes,operation,{isolated});
  const ticket=Object.freeze(Object.create(null));
  pending={ticket,proposal,revision};
  return Object.freeze({ticket,project_id:projectId,operation:proposal.operation});
 }
 function approve(ticket,projectId,notes,{approved=false,revision,isolated=false}={}){
  if(!pending||ticket!==pending.ticket)throw Error('inactive-memory-review');
  const current=pending;
  pending=null; // Consume on the first matching attempt, even if rejected.
  if(!validRevision(revision)||revision!==current.revision)throw Error('stale-memory-revision');
  return applyMemoryEdit(projectId,notes,current.proposal,{approved,isolated});
 }
 function cancel(ticket){
  if(!pending||ticket!==pending.ticket)return false;
  pending=null;
  return true;
 }
 function invalidate(){pending=null;}
 return Object.freeze({stage,approve,cancel,invalidate});
}

// Explicit human-authored structured preference only. No inference from ordinary chat.
// Returned operations are transient review candidates; never log or automatically apply.
export function reviewPreference(notes,message,{enabled=false,isolated=false,origin='unknown'}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off'};
 // Origin must come from the trusted host, not from message text.
 if(origin!=='human')return {status:'ignored-origin'};
 if(typeof message!=='string'||message.length>24000)throw Error('invalid-message');
 const parse=s=>{
  const m=/^\[preference\] ([\p{L}\p{N}][\p{L}\p{M}\p{N} _.-]{0,79}) = ([^\r\n]+)$/u.exec(s);
  if(!m||!m[2].trim())return null;
  return {key:m[1].normalize('NFC').trim(),value:m[2].normalize('NFC').trim()};
 };
 const marked=message.trim();
 if(!marked.startsWith('[preference]'))return {status:'no-explicit-preference'};
 if(marked.length>500)return {status:'invalid-preference'};
 const candidate=parse(marked);
 if(!candidate)return {status:'invalid-preference'};
 const note='[preference] '+candidate.key+' = '+candidate.value;
 if(note.length>500)return {status:'invalid-preference'};
 if(!Array.isArray(notes)||notes.length>30)throw Error('invalid-memory-list');
 const matches=[];
 for(let index=0;index<notes.length;index++){
  const old=notes[index];
  if(typeof old!=='string'||!old.trim()||old.length>500)throw Error('invalid-memory-note');
  const p=parse(old);
  if(p?.key===candidate.key)matches.push({index,value:p.value});
 }
 if(matches.length>1)return {status:'ambiguous',indices:matches.map(m=>m.index)};
 if(matches.length===1){
  if(matches[0].value===candidate.value)return {status:'unchanged',index:matches[0].index};
  return {status:'review-replacement',operation:{kind:'replace',index:matches[0].index,value:note}};
 }
 if(notes.length===30)return {status:'capacity'};
 return {status:'review-addition',operation:{kind:'add',value:note}};
}
