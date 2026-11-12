/* NEXUS optional encrypted chat history. No network, tokens or DOM access. */
(function (root) {
'use strict';
const SCHEMA='nexus.chat-history.v1', ITERATIONS=310000, MAX_BYTES=4*1024*1024;
const encoder=new TextEncoder(), decoder=new TextDecoder('utf-8',{fatal:true});
const clone=x=>JSON.parse(JSON.stringify(x));
const fail=code=>{throw Error(code)};
function text(value,max){if(typeof value!=='string'||Array.from(value).length>max)fail('history-shape');return value}
function url(value){text(value,2048);const u=new URL(value);if(u.protocol!=='https:'||u.username||u.password||u.port||!u.hostname.includes('.')||/^\d+\./.test(u.hostname)||u.hostname.startsWith('[')||/(\.local|\.internal|\.localhost)\.?$/.test(u.hostname))fail('history-url');return u.href}
function reply(value){
 if(!value||value.schema!=='nexus.research-chat.v1'||value.mode!=='retrieval_assisted_extractive'||value.authority!=='none'||value.judgment_changed!==false)fail('history-reply');
 if(!Array.isArray(value.sources)||value.sources.length>8||!Array.isArray(value.claims)||value.claims.length>4||!Array.isArray(value.providers)||value.providers.length>4||!Array.isArray(value.unknowns)||value.unknowns.length>4)fail('history-reply');
 const sources=value.sources.map(s=>({id:text(s.id,20),title:text(s.title,160),url:url(s.url),excerpt:text(s.excerpt,2000),origin:text(s.origin,80),provider:text(s.provider,80),retrieved_at_unix:s.retrieved_at_unix===null?null:(Number.isSafeInteger(s.retrieved_at_unix)&&s.retrieved_at_unix>=0?s.retrieved_at_unix:fail('history-time'))}));
 const ids=new Set(sources.map(s=>s.id));if(ids.size!==sources.length)fail('history-citation');
 const claims=value.claims.map(c=>{if(!Array.isArray(c.citation_ids)||!c.citation_ids.length||c.citation_ids.length>8||c.citation_ids.some(id=>!ids.has(id)))fail('history-citation');return {text:text(c.text,300),truncated:c.truncated===true,citation_ids:[...c.citation_ids],origin:text(c.origin,80),uncertainty:text(c.uncertainty,80)}});
 return {schema:value.schema,mode:value.mode,authority:'none',judgment_changed:false,history_context_attached:value.history_context_attached===true,answer_status:text(value.answer_status,80),answer:text(value.answer,6000),context:value.context===null?null:text(value.context,250),context_origin:value.context_origin===undefined?null:text(value.context_origin||'',80),claims,sources,providers:value.providers.map(p=>({provider:text(p.provider,80),status:text(p.status,80)})),unknowns:value.unknowns.map(s=>text(s,1500)),next_question:text(value.next_question,1500)};
}
function conversation(value){
 if(!value||typeof value.id!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(value.id)||!Array.isArray(value.turns)||!value.turns.length||value.turns.length>80||value.turns.length%2)fail('history-conversation');
 const turns=value.turns.map((t,i)=>{if(t.role!==(i%2?'assistant':'human'))fail('history-role');const content=text(t.content,i%2?6000:1500);if(!content.trim())fail('history-content');const out={role:t.role,content};if(t.reply!==undefined){if(i%2===0)fail('history-role');out.reply=reply(t.reply);if(out.reply.answer!==content)fail('history-content')}return out});
 const created_at=text(value.created_at,40),updated_at=text(value.updated_at,40);if(!Number.isFinite(Date.parse(created_at))||!Number.isFinite(Date.parse(updated_at)))fail('history-time');
 return {id:value.id,title:text(value.title,100),created_at,updated_at,turns};
}
function archive(value){
 if(!value||value.schema!==SCHEMA||!Array.isArray(value.conversations))fail('history-shape');if(value.conversations.length>20)fail('history-capacity');
 const conversations=value.conversations.map(conversation);if(new Set(conversations.map(c=>c.id)).size!==conversations.length)fail('history-duplicate');
 const out={schema:SCHEMA,conversations};if(encoder.encode(JSON.stringify(out)).length>MAX_BYTES)fail('history-capacity');return out;
}
function b64(bytes){let out='';for(let i=0;i<bytes.length;i+=16384)out+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(out)}
function un64(value,max){if(typeof value!=='string'||value.length>Math.ceil(max/3)*4||!/^[A-Za-z0-9+/]*={0,2}$/.test(value))fail('history-envelope');let decoded;try{decoded=atob(value)}catch{fail('history-envelope')}const bytes=Uint8Array.from(decoded,c=>c.charCodeAt(0));if(bytes.length>max||b64(bytes)!==value)fail('history-envelope');return bytes}
function envelope(raw){
 if(typeof raw==='string'){if(encoder.encode(raw).length>6*1024*1024)fail('history-capacity');raw=JSON.parse(raw)}
 if(!raw||raw.schema!==SCHEMA||raw.iterations!==ITERATIONS||typeof raw.revision!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(raw.revision))fail('history-envelope');
 const salt=un64(raw.salt,16),iv=un64(raw.iv,12),cipher=un64(raw.ciphertext,MAX_BYTES+16);if(salt.length!==16||iv.length!==12||cipher.length<16)fail('history-envelope');
 return {schema:SCHEMA,iterations:ITERATIONS,revision:raw.revision,salt:raw.salt,iv:raw.iv,ciphertext:raw.ciphertext};
}
const aad=env=>encoder.encode([SCHEMA,ITERATIONS,env.salt,env.revision].join('|'));
async function derive(password,salt){if(typeof password!=='string'||Array.from(password).length<12||password.length>512)fail('history-passphrase');const material=await root.crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveKey']);return root.crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:ITERATIONS,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
async function seal(data,key,salt){const env={schema:SCHEMA,iterations:ITERATIONS,revision:root.crypto.randomUUID(),salt:b64(salt),iv:b64(root.crypto.getRandomValues(new Uint8Array(12)))};const bytes=encoder.encode(JSON.stringify(archive(data)));const cipher=await root.crypto.subtle.encrypt({name:'AES-GCM',iv:un64(env.iv,12),additionalData:aad(env)},key,bytes);return {...env,ciphertext:b64(new Uint8Array(cipher))}}
async function open(raw,password){const env=envelope(raw),salt=un64(env.salt,16),key=await derive(password,salt);let plain;try{plain=await root.crypto.subtle.decrypt({name:'AES-GCM',iv:un64(env.iv,12),additionalData:aad(env)},key,un64(env.ciphertext,MAX_BYTES+16))}catch{fail('history-unlock-failed')}return {env,key,salt,data:archive(JSON.parse(decoder.decode(plain)))}}
class IndexedStore {
 async database(){return new Promise((resolve,reject)=>{const r=root.indexedDB.open('nexus-private-chat-history',1);r.onupgradeneeded=()=>r.result.createObjectStore('encrypted');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('history-storage'));r.onblocked=()=>reject(Error('history-storage'))})}
 async read(){const db=await this.database();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('encrypted','readonly'),r=tx.objectStore('encrypted').get('vault');let value;r.onsuccess=()=>value=r.result||null;tx.oncomplete=()=>resolve(value);tx.onabort=tx.onerror=()=>reject(Error('history-storage'))})}finally{db.close()}}
 async commit(expected,value,guard){const db=await this.database();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('encrypted','readwrite'),store=tx.objectStore('encrypted');let error='history-storage';const r=store.get('vault');r.onsuccess=()=>{if(!guard()){error='history-locked';tx.abort();return}if((r.result?.revision||null)!==expected){error='history-conflict';tx.abort();return}if(value===null)store.delete('vault');else store.put(value,'vault')};tx.oncomplete=resolve;tx.onabort=()=>reject(Error(error));tx.onerror=()=>reject(Error('history-storage'))})}finally{db.close()}}
}
class Vault {
 constructor(store){this.store=store||new IndexedStore();this.epoch=0;this.tail=Promise.resolve();this.key=null;this.salt=null;this.data=null;this.env=null}
 get unlocked(){return this.key!==null}
 lock(){this.epoch++;this.key=null;this.salt=null;this.data=null;this.env=null}
 guard(epoch){if(epoch!==this.epoch)fail('history-locked')}
 run(operation){const epoch=this.epoch;const result=this.tail.catch(()=>{}).then(async()=>{this.guard(epoch);try{return await operation(epoch)}catch(e){if(e.message==='history-conflict')this.lock();throw e}});this.tail=result.catch(()=>{});return result}
 list(){if(!this.unlocked)fail('history-locked');return this.data.conversations.map(({id,title,created_at,updated_at,turns})=>({id,title,created_at,updated_at,turn_count:turns.length}))}
 get(id){if(!this.unlocked)fail('history-locked');const c=this.data.conversations.find(c=>c.id===id);if(!c)fail('history-not-found');return clone(c)}
 async create(password){return this.run(async epoch=>{if(await this.store.read())fail('history-exists');const salt=root.crypto.getRandomValues(new Uint8Array(16)),key=await derive(password,salt);this.guard(epoch);const data={schema:SCHEMA,conversations:[]},env=await seal(data,key,salt);this.guard(epoch);await this.store.commit(null,env,()=>epoch===this.epoch);this.guard(epoch);Object.assign(this,{key,salt,data,env});return this.list()})}
 async unlock(password){return this.run(async epoch=>{const raw=await this.store.read();if(!raw)fail('history-not-found');const opened=await open(raw,password);this.guard(epoch);Object.assign(this,opened);return this.list()})}
 async write(data,epoch){if(!this.unlocked)fail('history-locked');const clean=archive(data),env=await seal(clean,this.key,this.salt);this.guard(epoch);await this.store.commit(this.env.revision,env,()=>epoch===this.epoch);this.guard(epoch);this.data=clean;this.env=env;return this.list()}
 async save(value){const candidate=clone(value);return this.run(async epoch=>{if(!this.unlocked)fail('history-locked');const old=this.data.conversations.find(c=>c.id===candidate.id),now=new Date().toISOString();const c=conversation({...candidate,created_at:old?.created_at||now,updated_at:now});const rest=this.data.conversations.filter(x=>x.id!==c.id);return this.write({schema:SCHEMA,conversations:[c,...rest]},epoch)})}
 async remove(id){return this.run(async epoch=>{this.get(id);return this.write({schema:SCHEMA,conversations:this.data.conversations.filter(c=>c.id!==id)},epoch)})}
 async erase(){return this.run(async epoch=>{const current=await this.store.read();this.guard(epoch);await this.store.commit(current?.revision||null,null,()=>epoch===this.epoch);this.lock()})}
 async backup(){return this.run(async()=>{if(!this.unlocked)fail('history-locked');return JSON.stringify(this.env)})}
 async restore(password,raw){return this.run(async epoch=>{const opened=await open(raw,password);this.guard(epoch);const current=await this.store.read(),env=await seal(opened.data,opened.key,opened.salt);this.guard(epoch);await this.store.commit(current?.revision||null,env,()=>epoch===this.epoch);this.guard(epoch);Object.assign(this,{...opened,env});return this.list()})}
}
root.NexusChatHistory=Object.freeze({Vault,IndexedStore,SCHEMA,MAX_BYTES});
})(globalThis);
