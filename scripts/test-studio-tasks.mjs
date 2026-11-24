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
