/* Bounded asynchronous local DAG scheduler. It is not an LLM or OS agent. */
(function(root){'use strict';
const bytes=x=>new TextEncoder().encode(x).length;
const bad=()=>{throw Error('invalid-task-plan')};
function validate(raw){
 if(!raw||typeof raw!=='object'||Array.isArray(raw))bad();
 let text;try{text=JSON.stringify(raw)}catch{bad()}
 if(bytes(text)>524288)bad();
 if(Object.keys(raw).some(k=>!['version','jobs','concurrency'].includes(k))||raw.version!==1||!Array.isArray(raw.jobs)||!raw.jobs.length||raw.jobs.length>12)bad();
 const concurrency=raw.concurrency??2;if(!Number.isInteger(concurrency)||concurrency<1||concurrency>2)bad();
 const ids=new Set();const jobs=raw.jobs.map(j=>{
  if(!j||Object.keys(j).some(k=>!['id','code','input','needs'].includes(k))||typeof j.id!=='string'||!/^[a-zA-Z][a-zA-Z0-9_-]{0,39}$/.test(j.id)||ids.has(j.id))bad();ids.add(j.id);
  if(typeof j.code!=='string'||!j.code.trim()||bytes(j.code)>100000||typeof (j.input??'')!=='string'||bytes(j.input??'')>131072)bad();
  const needs=j.needs??[];if(!Array.isArray(needs)||needs.length>11||needs.some(n=>typeof n!=='string')||new Set(needs).size!==needs.length)bad();
  return {id:j.id,code:j.code,input:j.input??'',needs:[...needs]};
 });
 const seen=new Set(),visiting=new Set(),byId=new Map(jobs.map(j=>[j.id,j]));
 function visit(j){if(visiting.has(j.id))bad();if(seen.has(j.id))return;visiting.add(j.id);for(const n of j.needs){if(!byId.has(n))bad();visit(byId.get(n))}visiting.delete(j.id);seen.add(j.id)}jobs.forEach(visit);
 return {version:1,concurrency,jobs};
}
class Runner{
 constructor(factory=()=>new root.NexusLab.Sandbox()){this.factory=factory;this.active=null}
 cancel(){this.active?.cancel()}
 run(raw,{onUpdate=()=>{}}={}){
  const plan=validate(raw);if(this.active)throw Error('task-run-active');
  const rows=plan.jobs.map(j=>({id:j.id,status:'queued',output:null,error:null})),byId=new Map(rows.map(r=>[r.id,r]));
  const snapshot=()=>({version:1,jobs:rows.map(r=>({...r}))});
  let done=false,running=0,resolve,timer;const controls=new Map();const promise=new Promise(r=>resolve=r);
  const emit=()=>{try{onUpdate(snapshot())}catch{ /* observers cannot stall execution */ }};
  const finish=()=>{if(done)return;done=true;clearTimeout(timer);this.active=null;emit();resolve(snapshot())};
  const cancel=()=>{if(done)return;for(const r of rows)if(['queued','running'].includes(r.status)){r.status='cancelled';r.error='cancelled'}for(const c of controls.values()){c.abort.abort();try{c.worker.cancel()}catch{}}controls.clear();finish()};
  this.active={cancel};timer=setTimeout(cancel,60000);
  const pump=()=>{
   if(done)return;
   for(const j of plan.jobs){const r=byId.get(j.id);if(r.status!=='queued')continue;
    const deps=j.needs.map(id=>byId.get(id));if(deps.some(d=>['failed','cancelled','blocked'].includes(d.status))){r.status='blocked';r.error='dependency-failed';continue}
    if(running>=plan.concurrency||deps.some(d=>d.status!=='succeeded'))continue;
    const input=JSON.stringify({input:j.input,dependencies:Object.fromEntries(deps.map(d=>[d.id,d.output]))});
    if(bytes(input)>262144){r.status='failed';r.error='dependency-input-limit';continue}
    r.status='running';running++;const abort=new AbortController();let worker;
    // Factory and run failures must become job failures, never stranded promises.
    Promise.resolve().then(()=>{if(done)return;worker=this.factory();controls.set(j.id,{abort,worker});return worker.run(j.code,input,{signal:abort.signal})}).then(output=>{
     if(done)return;if(typeof output!=='string'||bytes(output)>64000)throw Error('output-limit');r.status='succeeded';r.output=output;
    }).catch(()=>{if(!done){r.status='failed';r.error='execution-failed'}}).finally(()=>{running--;controls.delete(j.id);if(!done){emit();pump()}});
   }
   emit();if(!running){if(rows.some(r=>r.status==='queued')){for(const r of rows)if(r.status==='queued'){r.status='blocked';r.error='dependency-failed'}}finish()}
  };
  pump();return promise;
 }
}
root.NexusTasks=Object.freeze({validate,Runner});
})(globalThis);
