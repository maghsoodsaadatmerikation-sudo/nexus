import assert from 'node:assert/strict';
import '../web/studio-core.js';
const S=globalThis.NexusStudio;
function testArchive(S){
 let checks=0;
 const eq=(a,b)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture '+checks);checks++};
 const reject=fn=>{let failed=false;try{fn()}catch{failed=true}eq(failed,true)};
 const p={id:'p1',title:'Test',instructions:'',memories:[],threads:[],sources:[],documents:[]};
 const entry={correction_code:'synthetic_fix',criterion_id:'s1',status:'active',supporting_pair_count:2};
 const snap={project_id:'p1',workflow_id:'w1',revision:1,entries:[entry]};
 const input=x=>({schema:S.SCHEMA,projects:[{...p,...x}]});
 eq(S.state(input({})),input({}));
 eq(S.state(input({experiences:[snap]})).projects[0].experiences,[snap]);
 eq(S.retainHistory(input({experiences:[snap]})).projects[0].experiences,[snap]);
 for(const count of [0,1,2,3,12,13,99,2.5])for(const status of ['active','revoked','forged']){
  const value=input({experiences:[{...snap,entries:[{...entry,supporting_pair_count:count,status}]}]});
  if(Number.isInteger(count)&&count>=2&&count<=12&&status!=='forged')eq(S.state(value),value);else reject(()=>S.state(value));
 }
 for(const revision of [0,1,99,-1,1.2,Number.MAX_SAFE_INTEGER,NaN])for(const workflow_id of ['w1','wf_2','','x y']){
  const value=input({experiences:[{...snap,revision,workflow_id}]});
  if(Number.isSafeInteger(revision)&&revision>=0&&revision<Number.MAX_SAFE_INTEGER&&['w1','wf_2'].includes(workflow_id))eq(S.state(value),value);else reject(()=>S.state(value));
 }
 for(const code of ['x','x'.repeat(80),'a_b','a-b','', 'x'.repeat(81),'x y','<script>'])for(const key of ['criterion_id','correction_code']){
  const value=input({experiences:[{...snap,entries:[{...entry,[key]:code}]}]});
  if(/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(code))eq(S.state(value),value);else reject(()=>S.state(value));
 }
 for(const bad of [{...snap,project_id:'p2'},{...snap,raw_evidence:[]},{...snap,ticket:{}},{...snap,entries:[{...entry,instruction:'unsafe'}]},{...snap,entries:[entry,entry]},{...snap,entries:Array.from({length:31},(_,i)=>({...entry,criterion_id:'s'+i}))}])reject(()=>S.state(input({experiences:[bad]})));
 reject(()=>S.state(input({experiences:[snap,snap]})));
 reject(()=>S.state(input({experiences:Array.from({length:13},(_,i)=>({...snap,workflow_id:'w'+i}))})));
 eq(S.state(input({experiences:[]})).projects[0].experiences,[]);
 return checks;
}

const checks=testArchive(S);
// Use the existing real WebCrypto vault rather than a second key or store.
class Store{raw=null;async read(){return this.raw}async commit(expected,raw,guard){if(!guard())throw Error('locked');if((this.raw?JSON.parse(this.raw).revision:null)!==expected)throw Error('conflict');this.raw=raw}}
const store=new Store(),vault=new S.Vault(store),pass='synthetic archive experience passphrase';
const p=S.project('Synthetic archive');p.experiences=[{project_id:p.id,workflow_id:'w1',revision:1,entries:[{correction_code:'synthetic_fix',criterion_id:'s1',status:'active',supporting_pair_count:2}]}];
const data=S.state({schema:S.SCHEMA,projects:[p]});
await vault.create(pass);await vault.save(data);
assert(!store.raw.includes('synthetic_fix'));
assert.deepEqual((await S.decrypt(store.raw,pass)).data,data);
vault.lock();await vault.unlock(pass);assert.deepEqual(vault.data,data);
const t=S.append(S.thread('Synthetic'),'user','Review task','human');
for(const isolated of [false,true]){const context=S.context(p,{...t,isolated},{memory:true,sources:true,skyTone:false});assert(!JSON.stringify(context).includes('synthetic_fix'))}
const removed=S.copy(data);removed.projects[0].experiences=[];
await vault.save(removed);assert.deepEqual((await S.decrypt(store.raw,pass)).data.projects[0].experiences,[]);
console.log('EXPERIENCE ARCHIVE: PASS ('+checks+' validation cases plus real vault tests)');
