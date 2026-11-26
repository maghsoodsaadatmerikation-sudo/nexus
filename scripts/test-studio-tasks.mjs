import assert from 'node:assert/strict';
import '../web/studio-tasks.js';
const {validate,Runner}=globalThis.NexusTasks;
const plan=jobs=>({version:1,jobs});let checks=0;
const reject=x=>{assert.throws(()=>validate(x));checks++};
for(const x of [null,[],{},plan([]),{...plan([{id:'a',code:'return 1'}]),concurrency:3},plan([{id:'a',code:''}]),plan([{id:'a',code:'x',needs:['missing']}]),plan([{id:'a',code:'x',needs:['a']}]),plan([{id:'a',code:'x',needs:['b']},{id:'b',code:'x',needs:['a']}]),plan([{id:'a',code:'x'},{id:'a',code:'x'}]),plan([{id:'__proto__',code:'x'}]),plan([{id:'a',code:'x',needs:['b','b']},{id:'b',code:'x'}]),plan([{id:'a',code:'x',input:'é'.repeat(65537)}]),plan(Array.from({length:13},(_,i)=>({id:'a'+i,code:'x'}))),plan([{id:'a',code:'x',unexpected:true}])])reject(x);
let active=0,peak=0,started=[],pending=new Map();
const factory=()=>({run(code,input){active++;peak=Math.max(peak,active);started.push(code);return new Promise((resolve,reject)=>pending.set(code,{resolve:x=>{active--;resolve(x)},reject:()=>{active--;reject(Error('failed'))},input}))},cancel(){}});
const tick=()=>new Promise(r=>setImmediate(r));
const runner=new Runner(factory),raw=plan([{id:'final',code:'final',needs:['left','right']},{id:'left',code:'left'},{id:'right',code:'right'},{id:'other',code:'other'}]);
const done=runner.run(raw);raw.jobs[0].needs=[];await tick();assert.deepEqual(started,['left','right']);assert.throws(()=>runner.run(plan([{id:'x',code:'x'}])));checks+=2;
pending.get('left').resolve('2');await tick();assert.deepEqual(started,['left','right','other']);checks++;
pending.get('right').resolve('3');await tick();assert(started.includes('final'));assert.deepEqual(JSON.parse(pending.get('final').input).dependencies,{left:'2',right:'3'});checks+=2;
pending.get('final').resolve('5');pending.get('other').resolve('7');const result=await done;assert(result.jobs.every(j=>j.status==='succeeded'));assert.equal(peak,2);checks+=2;
started=[];pending=new Map();const failed=runner.run(plan([{id:'child',code:'child',needs:['bad']},{id:'grandchild',code:'grandchild',needs:['child']},{id:'bad',code:'bad'},{id:'ok',code:'ok'}]));await tick();pending.get('bad').reject();pending.get('ok').resolve('1');const failure=await failed;assert.deepEqual(failure.jobs.map(j=>j.status),['blocked','blocked','failed','succeeded']);checks++;
const cancelled=runner.run(plan([{id:'a',code:'a'},{id:'b',code:'b'},{id:'c',code:'c'}]));await tick();runner.cancel();assert((await cancelled).jobs.every(j=>j.status==='cancelled'&&j.error==='cancelled'));checks++;
const throwing=new Runner(()=>{throw Error('factory failure')});const tr=await throwing.run(plan([{id:'a',code:'a'}]),{onUpdate(){throw Error('observer')}});assert.equal(tr.jobs[0].status,'failed');checks++;
const huge=new Runner(()=>({run:async()=> 'x'.repeat(64001)}));assert.equal((await huge.run(plan([{id:'a',code:'a'}]))).jobs[0].status,'failed');checks++;
const cancelledImmediately=runner.run(plan([{id:'fresh',code:'fresh'}]));runner.cancel();assert.equal((await cancelledImmediately).jobs[0].status,'cancelled');checks++;
await tick();assert.equal(runner.active,null);checks++;
const nativeSetTimeout=globalThis.setTimeout;
let deadline;
globalThis.setTimeout=(callback,delay,...args)=>{
 if(delay!==60000)return nativeSetTimeout(callback,delay,...args);
 deadline=callback;return null;
};
try{
 const timed=runner.run({...plan([{id:'good',code:'good'},{id:'slow',code:'slow'},{id:'queued',code:'queued'}]),concurrency:1});
 await tick();pending.get('good').resolve('2');await tick();
 deadline();
 const {jobs}=await timed;
 assert.equal(jobs[0].status,'succeeded');
 assert(jobs.slice(1).every(job=>job.status==='cancelled'&&job.error==='deadline-exceeded'));
 checks+=2;
}finally{globalThis.setTimeout=nativeSetTimeout}
console.log(JSON.stringify({status:'PASS',checks,real_browser_worker_tested:false}));

const {reviewWorkflowRecovery}=await import('../web/studio-workflow-recovery.mjs');
function testRecovery(review){
 let checks=0;
 const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture mismatch '+checks)};
 const reject=(fn,msg)=>{checks++;let e;try{fn()}catch(x){e=x}if(!e||!String(e.message).includes(msg))throw Error('expected rejection '+checks)};
 const on={enabled:true},plan=Object.freeze([{id:'final',needs:['left','right']},{id:'left',needs:[]},{id:'right',needs:[]},{id:'independent',needs:[]}]);
 const obs=(id,status)=>({id,status}),st=[obs('left','succeeded'),obs('right','failed'),obs('final','queued'),obs('independent','queued')];
 const result=review(plan,st,on);
 eq(result.items.map(x=>[x.id,x.disposition]),[['left','reported_success'],['right','review_retry'],['final','wait_for_dependencies'],['independent','review_next_step']]);
 eq(result.items[2].unresolved_dependencies,['right']);eq(result.execution_authorized,false);
 eq(review(plan,[obs('left','succeeded'),obs('right','succeeded'),obs('final','queued')],on).items[2].disposition,'review_next_step');
 eq(review(plan,[obs('final','succeeded')],on).items[2].disposition,'inconsistent_observation');
 eq(review(plan,[obs('right','running')],on).items[1].disposition,'reconcile_before_action');
 eq(review(plan,[],on).items.every(x=>x.disposition==='reconcile_before_action'),true);
 eq(review(plan,[obs('left','cancelled')],on).items[0].disposition,'review_retry');
 // A failed or cancelled dependent is not a retry candidate until prerequisites succeed.
 for(const status of ['failed','cancelled']){
  const pending=review(plan,[obs('left','failed'),obs('right','succeeded'),obs('final',status)],on).items[2];
  eq(pending.disposition,'wait_for_dependencies');eq(pending.unresolved_dependencies,['left']);
  const ready=review(plan,[obs('left','succeeded'),obs('right','succeeded'),obs('final',status)],on).items[2];
  eq(ready.disposition,'review_retry');eq(ready.unresolved_dependencies,[]);
  const unknown=review(plan,[obs('final',status)],on).items[2];
  eq(unknown.disposition,'wait_for_dependencies');eq(unknown.unresolved_dependencies,['left','right']);
 }
 const chain=[{id:'a',needs:[]},{id:'b',needs:['a']},{id:'c',needs:['b']}];
 const inconsistent=review(chain,[obs('a','failed'),obs('b','succeeded'),obs('c','cancelled')],on);
 eq(inconsistent.items.map(x=>x.disposition),['review_retry','inconsistent_observation','wait_for_dependencies']);
 eq(inconsistent.execution_authorized,false);

 eq(review(plan,[obs('left','blocked')],on).items[0].disposition,'review_blocked_state');
 eq(review(null,null).status,'off');eq(review(null,null,{enabled:true,isolated:true}).status,'isolated');
 eq(review([{id:'a',needs:[]},{id:'b',needs:['a']},{id:'c',needs:['b']}],[obs('a','failed'),obs('b','succeeded'),obs('c','queued')],on).items.map(x=>x.disposition),['review_retry','inconsistent_observation','wait_for_dependencies']);
 eq(JSON.stringify(result).includes('code'),false);eq(plan[0].needs,['left','right']);eq(st.length,4);
 reject(()=>review([{id:'a',needs:['a']}],[],on),'cyclic-dependency');
 reject(()=>review([{id:'a',needs:['b']}],[],on),'unknown-dependency');
 reject(()=>review([{id:'a',needs:[]},{id:'a',needs:[]}],[],on),'invalid-step');
 reject(()=>review([{id:'a',needs:[]},{id:'b',needs:['a','a']}],[],on),'invalid-step');
 reject(()=>review(plan,[obs('left','queued'),obs('left','failed')],on),'invalid-observation');
 reject(()=>review(plan,[obs('ghost','succeeded')],on),'invalid-observation');
 reject(()=>review(plan,[obs('left','done')],on),'invalid-observation');
 reject(()=>review([],[],on),'invalid-recovery-input');
 reject(()=>review(plan,st,{enabled:1}),'invalid-options');
 return checks;
}
console.log('WORKFLOW RECOVERY REVIEW: PASS ('+testRecovery(reviewWorkflowRecovery)+' checks)');

const {reviewWorkflowLessons}=await import('../web/studio-workflow-recovery.mjs');
function testLessons(review){
 let checks=0;const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture mismatch '+checks)};
 const reject=(fn,msg)=>{checks++;let e;try{fn()}catch(x){e=x}if(!e||!String(e.message).includes(msg))throw Error('expected rejection '+checks)};
 const scope={project_id:'p',workflow_id:'w',criteria_sha256:'a'.repeat(64)},on={enabled:true};
 const run=(run_id,outcome,failure_codes=[],extra={})=>({...scope,run_id,plan_sha256:'b'.repeat(64),outcome,failure_codes,...extra});
 const runs=Object.freeze([run('r1','reported_failure',['timeout','bad-input']),run('r2','reported_failure',['timeout']),run('r3','reported_failure',['bad-input','timeout']),run('r4','reported_pass'),run('r5','inconclusive',['other'])]);
 const result=review(scope,runs,on);
 eq(result.candidates,[{kind:'recurring_reported_failure',code:'timeout',distinct_run_count:3},{kind:'recurring_reported_failure',code:'bad-input',distinct_run_count:2}]);
 eq(result.automatic_learning,false);eq(result.execution_authorized,false);eq(result.review_required,true);
 eq(review(scope,[runs[0]],on).candidates,[]);
 eq(review(scope,[run('r1','inconclusive',['x']),run('r2','inconclusive',['x'])],on).candidates,[]);
 eq(review(scope,[],on).candidates,[]);
 eq(review(null,null).status,'off');eq(review(null,null,{...on,isolated:true}).status,'isolated');
 eq(JSON.stringify(result).includes('r1'),false);eq(JSON.stringify(result).includes(scope.criteria_sha256),false);
 eq(review(scope,[run('r1','reported_failure',['z','a']),run('r2','reported_failure',['z','a'])],on).candidates.map(x=>x.code),['a','z']);
 reject(()=>review(scope,[runs[0],runs[0]],on),'invalid-run');
 reject(()=>review(scope,[run('r1','reported_pass',['x'])],on),'inconsistent-run');
 reject(()=>review(scope,[run('r1','reported_failure',['x','x'])],on),'invalid-run');
 reject(()=>review(scope,[run('r1','reported_failure',['x'],{project_id:'other'})],on),'scope-mismatch');
 reject(()=>review(scope,[run('r1','reported_failure',['x'],{workflow_id:'other'})],on),'scope-mismatch');
 reject(()=>review(scope,[run('r1','reported_failure',['x'],{criteria_sha256:'c'.repeat(64)})],on),'scope-mismatch');
 reject(()=>review(scope,[run('r1','reported_failure',['x'],{plan_sha256:'bad'})],on),'invalid-run');
 reject(()=>review(scope,Array(31).fill(runs[0]),on),'invalid-learning-input');
 reject(()=>review(scope,runs,{enabled:1}),'invalid-options');
 eq(runs.length,5);return checks;
}
console.log('WORKFLOW LESSON REVIEW: PASS ('+testLessons(reviewWorkflowLessons)+' checks)');
