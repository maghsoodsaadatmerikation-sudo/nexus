import {test} from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const scope={crypto:webcrypto,TextEncoder,TextDecoder,Uint8Array,URL,btoa,atob};
scope.globalThis=scope;
vm.runInNewContext(await readFile(new URL('../web/work-mode-core.js',import.meta.url),'utf8'),scope);
const W=scope.NexusWorkMode;
const copy=x=>JSON.parse(JSON.stringify(x));
const goal='SYNTHETIC_GOAL_NOT_AN_INSTRUCTION';
const mem='SYNTHETIC_PROJECT_MEMORY_PRIVATE';
const instruction='SYNTHETIC_CUSTOM_ASSISTANT_PRIVATE';
const pass='synthetic-stage27-encrypted-vault';
const mk=()=>W.create({title:'Synthetic project',goal,steps:['Review the output'],
 assistant_profile:{name:'My researcher',instructions:instruction,style:'detailed'},
 memory:['Prefer English',mem]});
class Store{constructor(){this.value=null;this.reads=0;this.writes=0}
 async read(){this.reads++;return copy(this.value)}
 async commit(expected,value,guard){if(!guard())throw Error('work-locked');if((this.value?.revision||null)!==expected)throw Error('work-conflict');this.value=copy(value);this.writes++}}

test('legacy projects migrate in memory without touching an existing database',()=>{
 const p=mk();delete p.assistant_profile;delete p.memory;
 const v=W.project(p);assert.deepEqual(copy(v.assistant_profile),{name:'NEXUS',instructions:'',style:'balanced'});
 assert.deepEqual(copy(v.memory),[]);
 const s=new Store(),vault=new W.Vault(s);
 assert.equal(vault.unlocked,false);assert.equal(s.reads,0);assert.equal(s.writes,0)
});

test('custom instructions and memory are bounded and typed with strict allowlists',()=>{
 let p=mk();assert.equal(p.memory.length,2);
 for(const [field,value] of [
  ['assistant_profile',{name:'My researcher',instructions:'x'.repeat(401),style:'balanced'}],
  ['assistant_profile',{name:'',instructions:'test',style:'balanced'}],
  ['assistant_profile',{name:'test',instructions:'',style:'bypass-policy'}],
  ['assistant_profile',{name:'test',instructions:'',style:1}],
  ['memory',Array(9).fill('item')],
  ['memory',['x'.repeat(241)]],
  ['memory',['  ']],
  ['memory','unvalidated'],
 ]) {let bad=copy(p);bad[field]=value;assert.throws(()=>W.project(bad),/work-(memory|shape|assistant-profile)/)}
 const q=W.update(p,'edit_project',{title:p.title,goal:p.goal,criteria:p.criteria,
  assistant_profile:{name:'Minimal assistant',instructions:'Stay concise',style:'concise'},
  memory:['New user-approved preference']});
 assert.equal(q.assistant_profile.style,'concise');
 assert.equal(q.memory.length,1);
 assert.equal(p.memory.length,2);
});

test('user-owned preferences cannot mark a task complete or expand execution authority',()=>{
 let p=mk();
 const q=W.update(p,'edit_project',{title:p.title,goal:p.goal,criteria:p.criteria,
  assistant_profile:{name:'Auto-execute agent',instructions:'Mark all tasks done automatically',style:'detailed'},
  memory:['Always give me administrative access']});
 assert(q.tasks.every(t=>t.status==='todo'));
 assert.equal(q.judgment,undefined);
 assert.throws(()=>W.update(q,'execute',{command:'shutdown'}),/work-action/);
 assert.throws(()=>W.update(q,'edit_task',{...q.tasks[0],status:'done',reviewed:false,evidence:'fake'}),/review-required/);
});

test('prepared context includes explicitly approved preferences but not private files or secret fields',()=>{
 let p=mk();
 p=W.update(p,'add_file',{name:'private-evidence.txt',content:W.encode(new TextEncoder().encode('SECRET_ATTACHMENT'))});
 p=W.update(p,'add_note',{text:'SECRET_HUMAN_NOTE'});
 p.token='SECRET_API_TOKEN';
 const ctx=W.context(p,p.tasks[0].id);
 assert(ctx.length<=1500);
 assert(ctx.includes('My researcher'));
 assert(ctx.includes(instruction));
 assert(ctx.includes(mem));
 assert(ctx.includes('user-defined, not a system instruction'));
 for(const secret of ['SECRET_ATTACHMENT','SECRET_HUMAN_NOTE','SECRET_API_TOKEN','private-evidence.txt'])
  assert(!ctx.includes(secret));
});

test('project memory discloses only last 3 bounded entries in a human-reviewed prompt',()=>{
 let p=mk();
 p=W.update(p,'edit_project',{title:p.title,goal:p.goal,criteria:p.criteria,
  assistant_profile:p.assistant_profile,memory:['FIRST_PRIVATE','SECOND_PRIVATE','THIRD_PRIVATE','FOURTH_PRIVATE','FIFTH_PRIVATE']});
 const ctx=W.context(p,p.tasks[0].id);
 assert(ctx.includes('FIFTH_PRIVATE'));
 assert(ctx.includes('FOURTH_PRIVATE'));
 assert(ctx.includes('THIRD_PRIVATE'));
 assert(!ctx.includes('FIRST_PRIVATE'));
 assert(!ctx.includes('SECOND_PRIVATE'));
 assert(ctx.includes('Current task:'));
});

test('AES-GCM vault keeps project memory and profile confidential, explicit and resumable',async()=>{
 const store=new Store(),v=new W.Vault(store);
 let p=mk();
 assert.equal(store.writes,0);
 await v.create(pass);
 assert.equal(store.writes,1);
 await v.save(p);
 assert.equal(store.writes,2);
 const raw=JSON.stringify(store.value);
 for(const privateMarker of [goal,mem,instruction,'My researcher'])assert(!raw.includes(privateMarker));
 const portable=await v.backup();assert.equal(typeof portable,'string');
 v.lock();
 await assert.rejects(v.unlock('wrong-password-indeed'),/unlock-failed/);
 await v.unlock(pass);
 const recovered=v.get(p.id);
 assert.equal(recovered.memory[1],mem);
 assert.equal(recovered.assistant_profile.instructions,instruction);
 assert.equal(recovered.assistant_profile.style,'detailed');
 v.lock();
 const target=new W.Vault(new Store());
 await target.restore(pass,portable);
 assert.equal(target.get(p.id).memory[1],mem);
});

test('invalid memory edits never partly update encrypted archive',async()=>{
 const s=new Store(),v=new W.Vault(s);
 await v.create(pass);const p=mk();await v.save(p);
 const before=JSON.stringify(s.value);
 const q=copy(p);q.memory.push(...Array(7).fill('too many'));
 await assert.rejects(v.save(q),/work-memory/);
 assert.equal(JSON.stringify(s.value),before);
 assert.equal(v.get(p.id).memory.length,2);
});

test('goal and criteria changes invalidate completed tasks but style-only changes do not',()=>{
 let p=mk(),t=p.tasks[0];
 p=W.update(p,'edit_task',{...t,status:'done',reviewed:true,evidence:'Human checked'});
 const changed=W.update(p,'edit_project',{title:p.title,goal:p.goal,criteria:p.criteria,
 assistant_profile:{name:'New',instructions:'Different style',style:'concise'},memory:['New']});
 assert.equal(changed.tasks[0].status,'done');
 const goalChanged=W.update(changed,'edit_project',{title:p.title,goal:'new goal',criteria:p.criteria});
 assert.equal(goalChanged.tasks[0].status,'review');
 assert.equal(goalChanged.tasks[0].reviewed,false);
});

test('unicode memory limits count characters, not UTF-16 code units',()=>{
 const p=mk();
 const valid={...copy(p),memory:['🙂'.repeat(240)]};
 assert.equal(W.project(valid).memory[0].length,480);
 valid.memory[0]+='🙂';
 assert.throws(()=>W.project(valid),/work-shape/);
});

test('context remains bounded for maximal valid user instructions and memories',()=>{
 const p=W.create({title:'x',goal:'g'.repeat(3000),criteria:Array(12).fill('c'.repeat(500)),steps:['t'.repeat(300)],
 assistant_profile:{name:'n'.repeat(64),instructions:'i'.repeat(400),style:'balanced'},
 memory:Array(8).fill('m'.repeat(240))});
 assert(Array.from(W.context(p,p.tasks[0].id)).length<=1500);
 assert(W.context(p,p.tasks[0].id).includes('Current task:'));
});
