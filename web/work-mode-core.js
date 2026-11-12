/* NEXUS Work Mode: local project planning, explicit human review, optional encrypted persistence. */
(function(root){'use strict';
const SCHEMA='nexus.work-mode.v1',ITERATIONS=310000,MAX_BYTES=4*1024*1024;
const encoder=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true});
const clone=x=>JSON.parse(JSON.stringify(x));const fail=code=>{throw Error(code)};
function text(v,max){if(typeof v!=='string'||Array.from(v).length>max)fail('work-shape');return v}
function id(v){if(typeof v!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(v))fail('work-id');return v}
function stamp(v){text(v,40);if(!Number.isFinite(Date.parse(v)))fail('work-time');return v}
function project(v){
 if(!v||v.schema!==SCHEMA||!Array.isArray(v.tasks)||v.tasks.length>60||!Array.isArray(v.criteria)||v.criteria.length>12||!Array.isArray(v.notes)||v.notes.length>60||!Array.isArray(v.files)||v.files.length>12||!Array.isArray(v.activity)||v.activity.length>200)fail('work-shape');
 const title=text(v.title,100),goal=text(v.goal,3000);if(!title.trim()||!goal.trim())fail('work-required');
 let total=0;const files=v.files.map(f=>{const bytes=un64(f.content,1024*1024);total+=bytes.length;const name=text(f.name,160);if(!name||/[\\/\x00-\x1f]/.test(name))fail('work-file');return {id:id(f.id),name,size:bytes.length,content:b64(bytes)}});if(total>2*1024*1024)fail('work-file-capacity');
 const fileIDs=new Set(files.map(f=>f.id));if(fileIDs.size!==files.length)fail('work-duplicate');
 const tasks=v.tasks.map(t=>{if(!['todo','doing','blocked','review','done'].includes(t.status)||!Array.isArray(t.dependencies)||t.dependencies.length>60||!Array.isArray(t.file_ids)||t.file_ids.length>12)fail('work-task');const title=text(t.title,300);if(!title.trim())fail('work-required');return {id:id(t.id),title,status:t.status,dependencies:t.dependencies.map(id),evidence:text(t.evidence,2000),file_ids:t.file_ids.map(id),reviewed:t.reviewed===true}});
 const byID=new Map(tasks.map(t=>[t.id,t]));if(byID.size!==tasks.length)fail('work-duplicate');
 for(const t of tasks){if(new Set(t.dependencies).size!==t.dependencies.length||t.dependencies.includes(t.id)||t.dependencies.some(d=>!byID.has(d))||new Set(t.file_ids).size!==t.file_ids.length||t.file_ids.some(f=>!fileIDs.has(f)))fail('work-dependency');if(t.status==='done'&&(!t.reviewed||(!t.evidence.trim()&&!t.file_ids.length)||t.dependencies.some(d=>byID.get(d).status!=='done')))fail('work-review-required');if(t.status==='doing'&&t.dependencies.some(d=>byID.get(d).status!=='done'))fail('work-dependency-incomplete');}
 const visiting=new Set(),visited=new Set();function visit(t){if(visiting.has(t.id))fail('work-cycle');if(visited.has(t.id))return;visiting.add(t.id);t.dependencies.forEach(d=>visit(byID.get(d)));visiting.delete(t.id);visited.add(t.id)}tasks.forEach(visit);
 return {schema:SCHEMA,id:id(v.id),title,goal,criteria:v.criteria.map(c=>text(c,500)),created_at:stamp(v.created_at),updated_at:stamp(v.updated_at),tasks,files,notes:v.notes.map(n=>{if(!['human','machine_draft'].includes(n.origin))fail('work-note');return {id:id(n.id),text:text(n.text,4000),origin:n.origin,at:stamp(n.at)}}),activity:v.activity.map(a=>({at:stamp(a.at),action:text(a.action,100),target:text(a.target,100)}))};
}
function archive(v){if(!v||v.schema!==SCHEMA||!Array.isArray(v.projects))fail('work-shape');if(v.projects.length>20)fail('work-capacity');const projects=v.projects.map(project);if(new Set(projects.map(p=>p.id)).size!==projects.length)fail('work-duplicate');const clean={schema:SCHEMA,projects};if(encoder.encode(JSON.stringify(clean)).length>MAX_BYTES)fail('work-capacity');return clean}
function create({title,goal,criteria=[],steps=[]}){const now=new Date().toISOString();return project({schema:SCHEMA,id:root.crypto.randomUUID(),title,goal,criteria,created_at:now,updated_at:now,tasks:steps.map(title=>({id:root.crypto.randomUUID(),title,status:'todo',dependencies:[],evidence:'',file_ids:[],reviewed:false})),notes:[],files:[],activity:[{at:now,action:'project_created',target:''}]})}
function update(value,action,payload={}){
 const p=project(value),now=new Date().toISOString();let target=payload.id||'';
 if(action==='add_task'){const t={id:root.crypto.randomUUID(),title:payload.title,status:'todo',dependencies:payload.dependencies||[],evidence:'',file_ids:[],reviewed:false};p.tasks.push(t);target=t.id}
 else if(action==='edit_task'){const task=p.tasks.find(t=>t.id===payload.id);if(!task)fail('work-not-found');Object.assign(task,{title:payload.title,status:payload.status,dependencies:payload.dependencies,evidence:payload.evidence,file_ids:payload.file_ids,reviewed:payload.status==='done'&&payload.reviewed===true})}
 else if(action==='add_note'){const n={id:root.crypto.randomUUID(),text:payload.text,origin:payload.origin||'human',at:now};if(!n.text.trim())fail('work-required');p.notes.push(n);target=n.id}
 else if(action==='add_file'){const f={id:root.crypto.randomUUID(),name:payload.name,content:payload.content};p.files.push(f);target=f.id}
 else if(action==='remove_file'){if(p.tasks.some(t=>t.file_ids.includes(payload.id)))fail('work-file-in-use');p.files=p.files.filter(f=>f.id!==payload.id)}
 else if(action==='edit_project'){const changed=p.goal!==payload.goal||JSON.stringify(p.criteria)!==JSON.stringify(payload.criteria);p.title=payload.title;p.goal=payload.goal;p.criteria=payload.criteria;if(changed){for(const t of p.tasks)if(t.status==='done'){t.status='review';t.reviewed=false}for(const t of p.tasks)if(t.status==='doing'&&t.dependencies.some(d=>p.tasks.find(x=>x.id===d).status!=='done'))t.status='blocked'}}
 else fail('work-action');
 p.updated_at=now;p.activity.push({at:now,action,target});p.activity=p.activity.slice(-200);return project(p)
}
function next(value){const p=project(value);return p.tasks.find(t=>['todo','doing','review'].includes(t.status)&&t.dependencies.every(d=>p.tasks.find(x=>x.id===d).status==='done'))||null}
function context(value,taskID){const p=project(value),t=p.tasks.find(t=>t.id===taskID);if(!t)fail('work-not-found');return Array.from('Project goal: '+Array.from(p.goal).slice(0,600).join('')+'\nSuccess criteria: '+p.criteria.slice(0,3).map(c=>Array.from(c).slice(0,120).join('')).join('; ')+'\nCurrent task: '+Array.from(t.title).slice(0,300).join('')+'\nHelp examine this task. Separate evidence, interpretation, uncertainty and options. Keep final judgment with me.').slice(0,1500).join('')}
function b64(bytes){let out='';for(let i=0;i<bytes.length;i+=16384)out+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(out)}
function un64(value,max){if(typeof value!=='string'||value.length>Math.ceil(max/3)*4||!/^[A-Za-z0-9+/]*={0,2}$/.test(value))fail('work-envelope');let decoded;try{decoded=atob(value)}catch{fail('work-envelope')}const bytes=Uint8Array.from(decoded,c=>c.charCodeAt(0));if(bytes.length>max||b64(bytes)!==value)fail('work-envelope');return bytes}
function envelope(raw){
 if(typeof raw==='string'){if(encoder.encode(raw).length>6*1024*1024)fail('work-capacity');raw=JSON.parse(raw)}
 if(!raw||raw.schema!==SCHEMA||raw.iterations!==ITERATIONS||typeof raw.revision!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(raw.revision))fail('work-envelope');
 const salt=un64(raw.salt,16),iv=un64(raw.iv,12),cipher=un64(raw.ciphertext,MAX_BYTES+16);if(salt.length!==16||iv.length!==12||cipher.length<16)fail('work-envelope');
 return {schema:SCHEMA,iterations:ITERATIONS,revision:raw.revision,salt:raw.salt,iv:raw.iv,ciphertext:raw.ciphertext};
}
const aad=env=>encoder.encode([SCHEMA,ITERATIONS,env.salt,env.revision].join('|'));
async function derive(password,salt){if(typeof password!=='string'||Array.from(password).length<12||password.length>512)fail('work-passphrase');const material=await root.crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveKey']);return root.crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:ITERATIONS,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
async function seal(data,key,salt){const env={schema:SCHEMA,iterations:ITERATIONS,revision:root.crypto.randomUUID(),salt:b64(salt),iv:b64(root.crypto.getRandomValues(new Uint8Array(12)))};const bytes=encoder.encode(JSON.stringify(archive(data)));const cipher=await root.crypto.subtle.encrypt({name:'AES-GCM',iv:un64(env.iv,12),additionalData:aad(env)},key,bytes);return {...env,ciphertext:b64(new Uint8Array(cipher))}}
async function open(raw,password){const env=envelope(raw),salt=un64(env.salt,16),key=await derive(password,salt);let plain;try{plain=await root.crypto.subtle.decrypt({name:'AES-GCM',iv:un64(env.iv,12),additionalData:aad(env)},key,un64(env.ciphertext,MAX_BYTES+16))}catch{fail('work-unlock-failed')}return {env,key,salt,data:archive(JSON.parse(decoder.decode(plain)))}}
class IndexedStore {
 async database(){return new Promise((resolve,reject)=>{const r=root.indexedDB.open('nexus-private-work-mode',1);r.onupgradeneeded=()=>r.result.createObjectStore('encrypted');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('work-storage'));r.onblocked=()=>reject(Error('work-storage'))})}
 async read(){const db=await this.database();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('encrypted','readonly'),r=tx.objectStore('encrypted').get('vault');let value;r.onsuccess=()=>value=r.result||null;tx.oncomplete=()=>resolve(value);tx.onabort=tx.onerror=()=>reject(Error('work-storage'))})}finally{db.close()}}
 async commit(expected,value,guard){const db=await this.database();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('encrypted','readwrite'),store=tx.objectStore('encrypted');let error='work-storage';const r=store.get('vault');r.onsuccess=()=>{if(!guard()){error='work-locked';tx.abort();return}if((r.result?.revision||null)!==expected){error='work-conflict';tx.abort();return}if(value===null)store.delete('vault');else store.put(value,'vault')};tx.oncomplete=resolve;tx.onabort=()=>reject(Error(error));tx.onerror=()=>reject(Error('work-storage'))})}finally{db.close()}}
}
class Vault {
 constructor(store){this.store=store||new IndexedStore();this.epoch=0;this.tail=Promise.resolve();this.key=null;this.salt=null;this.data=null;this.env=null}
 get unlocked(){return this.key!==null}
 lock(){this.epoch++;this.key=null;this.salt=null;this.data=null;this.env=null}
 guard(epoch){if(epoch!==this.epoch)fail('work-locked')}
 run(operation){const epoch=this.epoch;const result=this.tail.catch(()=>{}).then(async()=>{this.guard(epoch);try{return await operation(epoch)}catch(e){if(e.message==='work-conflict')this.lock();throw e}});this.tail=result.catch(()=>{});return result}
 list(){if(!this.unlocked)fail('work-locked');return this.data.projects.map(({id,title,updated_at,tasks})=>({id,title,updated_at,completed:tasks.filter(t=>t.status==='done').length,total:tasks.length}))}
 get(id){if(!this.unlocked)fail('work-locked');const c=this.data.projects.find(c=>c.id===id);if(!c)fail('work-not-found');return clone(c)}
 async create(password){return this.run(async epoch=>{if(await this.store.read())fail('work-exists');const salt=root.crypto.getRandomValues(new Uint8Array(16)),key=await derive(password,salt);this.guard(epoch);const data={schema:SCHEMA,projects:[]},env=await seal(data,key,salt);this.guard(epoch);await this.store.commit(null,env,()=>epoch===this.epoch);this.guard(epoch);Object.assign(this,{key,salt,data,env});return this.list()})}
 async unlock(password){return this.run(async epoch=>{const raw=await this.store.read();if(!raw)fail('work-not-found');const opened=await open(raw,password);this.guard(epoch);Object.assign(this,opened);return this.list()})}
 async write(data,epoch){if(!this.unlocked)fail('work-locked');const clean=archive(data),env=await seal(clean,this.key,this.salt);this.guard(epoch);await this.store.commit(this.env.revision,env,()=>epoch===this.epoch);this.guard(epoch);this.data=clean;this.env=env;return this.list()}
 async save(value){const candidate=clone(value);return this.run(async epoch=>{if(!this.unlocked)fail('work-locked');const old=this.data.projects.find(c=>c.id===candidate.id),now=new Date().toISOString();const c=project({...candidate,created_at:old?.created_at||now,updated_at:now});const rest=this.data.projects.filter(x=>x.id!==c.id);return this.write({schema:SCHEMA,projects:[c,...rest]},epoch)})}
 async remove(id){return this.run(async epoch=>{this.get(id);return this.write({schema:SCHEMA,projects:this.data.projects.filter(c=>c.id!==id)},epoch)})}
 async erase(){return this.run(async epoch=>{const current=await this.store.read();this.guard(epoch);await this.store.commit(current?.revision||null,null,()=>epoch===this.epoch);this.lock()})}
 async backup(){return this.run(async()=>{if(!this.unlocked)fail('work-locked');return JSON.stringify(this.env)})}
 async restore(password,raw){return this.run(async epoch=>{const opened=await open(raw,password);this.guard(epoch);const current=await this.store.read(),env=await seal(opened.data,opened.key,opened.salt);this.guard(epoch);await this.store.commit(current?.revision||null,env,()=>epoch===this.epoch);this.guard(epoch);Object.assign(this,{...opened,env});return this.list()})}
}
root.NexusWorkMode=Object.freeze({SCHEMA,create,project,update,next,context,Vault,IndexedStore,encode:b64,decode:un64});
})(globalThis);
