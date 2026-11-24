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
