import assert from 'node:assert/strict';
import '../web/studio-core.js';
import '../web/studio-calendar.js';
const S=globalThis.NexusStudio;let checks=0;
const ok=(f)=>{f();checks++},reject=async(f)=>{await assert.rejects(f);checks++};
const p=S.project('Project'),initial=S.thread('Thread');p.threads=[initial];let c=S.append(initial,'user','original question','human');c=S.append(c,'assistant','original draft','model');const original=S.copy(c);const edited=S.append(c,'user','edited question','human',null);const branch=S.append(edited,'assistant','alternative answer','model');
ok(()=>assert.deepEqual(c,original));ok(()=>assert.equal(S.path(branch).length,2));ok(()=>assert.equal(branch.nodes.length,4));ok(()=>assert.equal(S.path(branch,original.head)[1].text,'original draft'));
// Model route identity is optional for legacy data, but strict and preserved
// when it comes from a complete, reviewed gateway receipt.
const receipt={model_slot:'secondary',model:'synthetic-model',configuration_id:'b'.repeat(64)};
const receiptQuestion=S.append(S.thread('Receipt test'),'user','Question','human');
const receiptThread=S.append(receiptQuestion,'assistant','Answer','model',undefined,[],receipt);
const receiptProject=S.project('Receipt archive');receiptProject.threads=[receiptThread];
const receiptArchive={schema:S.SCHEMA,projects:[receiptProject]};
ok(()=>assert.deepEqual(S.path(receiptThread).at(-1).model_receipt,receipt));
ok(()=>assert.deepEqual(S.state(receiptArchive).projects[0].threads[0].nodes.at(-1).model_receipt,receipt));
ok(()=>assert.deepEqual(S.state(S.copy(receiptArchive)).projects[0].threads[0].nodes.at(-1).model_receipt,receipt));
for(const forged of [
 {model_slot:'wrong',model:'synthetic-model',configuration_id:'b'.repeat(64)},
 {model_slot:'primary',model:'synthetic-model',configuration_id:'not-a-hash'},
 {model_slot:'primary',model:'',configuration_id:'b'.repeat(64)},
 {...receipt,unreviewed_key:'injected'}
])ok(()=>assert.throws(()=>S.append(receiptQuestion,'assistant','Spoofed','model',undefined,[],forged)));
ok(()=>assert.throws(()=>S.append(initial,'user','Not a model','human',undefined,[],receipt)));
ok(()=>assert.throws(()=>S.append(initial,'assistant','forged','human')));ok(()=>assert.throws(()=>S.append(initial,'assistant','orphan','model')));ok(()=>assert.throws(()=>S.append(c,'user','bad','human','missing')));
p.threads=[branch];let v={schema:S.SCHEMA,projects:[p]};ok(()=>assert.deepEqual(S.state(v),v));
for(const change of [x=>x.schema='future',x=>x.projects[0].threads[0].nodes[0].parent=x.projects[0].threads[0].nodes[0].id,x=>x.projects[0].threads.push(x.projects[0].threads[0]),x=>x.projects[0].threads[0].nodes[1].origin='human']){const b=S.copy(v);change(b);ok(()=>assert.throws(()=>S.state(b)))}
p.memories=['PRIVATE-MEMORY'];p.instructions='concise';p.sources=[{id:S.uid(),name:'source.txt',text:'The orchard has green trees.\nA project uses public sources.'}];let candidate=S.append(branch,'user','orchard trees','human');
ok(()=>assert(!JSON.stringify(S.context(p,candidate)).includes('PRIVATE-MEMORY')));ok(()=>assert(JSON.stringify(S.context(p,candidate,{memory:true})).includes('PRIVATE-MEMORY')));ok(()=>assert.equal(S.context(p,candidate,{sources:true}).citations[0].line,1));ok(()=>assert.equal(S.retrieve(p,'unmatched').length,0));ok(()=>assert.equal(S.retrieve(S.project('other'),'orchard').length,0));
p.threads=[branch];v={schema:S.SCHEMA,projects:[p]};ok(()=>assert.equal(S.search(v,'original question').length,1));p.threads[0].archived=true;ok(()=>assert.equal(S.search(v,'original').length,0));ok(()=>assert.equal(S.search(v,'original',true).length,1));p.threads[0].archived=false;
ok(()=>assert(S.guide('hello').includes('not a generative model')));ok(()=>assert(S.guide('سلام',true).includes('مدل مولد نیست')));
ok(()=>assert.equal(S.context(p,candidate).study,false));
ok(()=>assert.match(S.context(p,candidate).messages[0].content,/NEXUS response guidance/));
ok(()=>assert.doesNotMatch(S.context(p,candidate,{onDevice:true}).messages[0].content,/response guidance|For this choice/));
const deviceChoice=S.append(branch,'user','Should I launch today or wait?','human');
ok(()=>assert.match(S.context(p,deviceChoice,{onDevice:true}).messages[0].content,/For this choice, compare the main options/));
ok(()=>assert.match(S.guide('Should I launch today or wait?'),/reversible next step/));
ok(()=>assert.match(S.guide('الان منتشر کنم یا منتظر بمانم؟',true),/قدم برگشت‌پذیر/));
ok(()=>assert.doesNotMatch(S.guide('What does JSON or CSV mean?'),/reversible next step/));
ok(()=>assert.doesNotMatch(S.guide('Translate this: choose between the red and blue doors.'),/reversible next step/));

const related=S.project('Research project');
related.instructions='PRIVATE PROFILE';
related.memories=['PRIVATE MEMORY'];
related.sources=[{id:S.uid(),name:'project notes',text:'orchard PRIVATE SOURCE'}];
const prior=S.append(S.thread('Earlier plan'),'user','orchard PREFERRED VARIETY','human');
const activeBranch=S.append(prior,'assistant','orchard UNTRUSTED MODEL CLAIM','model');
const hiddenBranch=S.append(activeBranch,'user','orchard OTHER BRANCH','human',null);
activeBranch.nodes=hiddenBranch.nodes;
const recent=S.append(S.thread('Current plan'),'user','Which orchard variety did we prefer?','human');
const privateThread={...S.append(S.thread('Tab only'),'user','orchard PRIVATE THREAD','human'),temporary:true,isolated:true};
const archived={...S.append(S.thread('Archived'),'user','orchard ARCHIVED THREAD','human'),archived:true};
const expired={...S.append(S.thread('Expired'),'user','orchard EXPIRED THREAD','human'),last_activity:1};
related.threads=[activeBranch,recent,privateThread,archived,expired];
const recalled=S.context(related,recent,{relatedChats:true,historyDays:30});
ok(()=>assert.deepEqual(recalled.recalled_chats,[{title:'Earlier plan',thread:activeBranch.id,turn:1}]));
ok(()=>assert.match(recalled.messages[0].content,/PREFERRED VARIETY/));
ok(()=>assert.doesNotMatch(JSON.stringify(recalled),/PRIVATE THREAD|ARCHIVED THREAD|EXPIRED THREAD|OTHER BRANCH|UNTRUSTED MODEL CLAIM/));
ok(()=>assert.equal(S.context(related,recent).recalled_chats.length,0));
const isolated=S.context(related,privateThread,{relatedChats:true,memory:true,sources:true,astrology:true});
ok(()=>assert.doesNotMatch(JSON.stringify(isolated),/PRIVATE PROFILE|PRIVATE MEMORY|PRIVATE SOURCE|PREFERRED VARIETY/));
ok(()=>assert.deepEqual(S.context(related,recent).memory_review,{status:'off',requested_count:0,included_count:0}));
ok(()=>assert.deepEqual(S.context(related,recent,{memory:true}).memory_review,{status:'included',requested_count:1,included_count:1}));
ok(()=>assert.deepEqual(isolated.memory_review,{status:'isolated',requested_count:0,included_count:0}));
ok(()=>assert.deepEqual(S.context(S.project('Empty memory'),recent,{memory:true}).memory_review,{status:'empty',requested_count:0,included_count:0}));
const selective=S.project('Selective memory');
selective.memories=['orchard variety','PRIVATE UNRELATED','orchard variety','orchard notes'];
const match=S.context(selective,recent,{memory:'related'});
ok(()=>assert.deepEqual(match.memory_review,{status:'included',requested_count:4,included_count:2}));
ok(()=>assert.match(match.messages[0].content,/orchard variety/));
ok(()=>assert.doesNotMatch(JSON.stringify(match),/PRIVATE UNRELATED/));
ok(()=>assert.equal(S.context(selective,S.append(S.thread('No matches'),'user','unmatched','human'),{memory:'related'}).memory_review.status,'no_match'));
ok(()=>assert.equal(S.context(selective,privateThread,{memory:'related'}).memory_review.status,'isolated'));
ok(()=>assert.match(JSON.stringify(S.context(selective,recent,{memory:true})),/PRIVATE UNRELATED/));
const projectSession={schema:S.SCHEMA,projects:[related]};
ok(()=>assert.equal(S.search(projectSession,'PRIVATE THREAD',true).length,0));
ok(()=>assert(!S.retainHistory(projectSession).projects[0].threads.some(c=>c.id===privateThread.id)));

const study=S.context(p,candidate,{study:true});
ok(()=>assert.equal(study.study,true));
ok(()=>assert(study.messages[0].content.includes('User-selected Study mode')));
ok(()=>assert.equal(study.messages.at(-1).content,S.context(p,candidate).messages.at(-1).content));
ok(()=>assert(S.guide('Fractions',false,{study:true}).includes('Local study guide')));
ok(()=>assert(S.guide('کسرها',true,{study:true}).includes('راهنمای مطالعهٔ محلی')));
let long=S.thread('Long');for(let i=0;i<30;i++){long=S.append(long,'user','turn '+i,'human');long=S.append(long,'assistant','draft '+i,'model')}long=S.append(long,'user','final question','human');const bounded=S.context(S.project('Long project'),long);ok(()=>assert(bounded.messages.length<=42&&bounded.omitted_messages>0));ok(()=>assert.equal(bounded.messages.at(-1).content,'final question'));
const pass='long private passphrase 123';
class Store{raw=null;async read(){return this.raw}async commit(expected,raw,guard){if(!guard())throw Error('locked');if((this.raw?JSON.parse(this.raw).revision:null)!==expected)throw Error('conflict');this.raw=raw}}
const store=new Store(),a=new S.Vault(store);await a.create(pass);checks++;await a.save(v);checks++;ok(()=>assert(!store.raw.includes('PRIVATE-MEMORY')));const raw=await a.export(v,pass);checks++;const opened=await S.decrypt(raw,pass);ok(()=>assert.deepEqual(opened.data,S.state(v)));await reject(()=>S.decrypt(raw,'wrong passphrase long'));const env=JSON.parse(raw);env.revision=S.uid();await reject(()=>S.decrypt(JSON.stringify(env),pass));
a.lock();ok(()=>assert.equal(a.key,null));ok(()=>assert.equal(a.data,null));await reject(()=>a.save(v));
const b=new S.Vault(store),d=new S.Vault(store);await b.unlock(pass);await d.unlock(pass);await b.save(v);await reject(()=>d.save(v));ok(()=>assert.equal(d.unlocked,false));
let resume;const gate=new Promise(r=>resume=r);const delayed=new Store();const old=delayed.commit.bind(delayed);delayed.commit=async(...args)=>{await gate;return old(...args)};const e=new S.Vault(delayed);const creation=e.create(pass);await new Promise(r=>setTimeout(r,150));e.lock();resume();await reject(()=>creation);ok(()=>assert.equal(delayed.raw,null));
await b.erase();ok(()=>assert.equal(store.raw,null));ok(()=>assert.equal(b.unlocked,false));
// A conflict callback delivered after Lock must not lock a later queued Unlock.
const raceStore=new Store(),raceVault=new S.Vault(raceStore);await raceVault.create(pass);await raceVault.save(v);
let signalCommit,releaseConflict;const entered=new Promise(r=>signalCommit=r),conflictGate=new Promise(r=>releaseConflict=r);
raceStore.commit=async(expected,raw,guard)=>{if(!guard())throw Error('locked');signalCommit();await conflictGate;throw Error('conflict')};
const obsoleteSave=raceVault.save(v);await entered;raceVault.lock();const reopen=raceVault.unlock(pass);releaseConflict();await reject(()=>obsoleteSave);const recovered=await reopen;checks++;
ok(()=>assert(raceVault.unlocked));ok(()=>assert.deepEqual(recovered,S.state(v)));
// The context builder must preserve a usable chat when opted-in memory,
// retrieved passages and multiple selected files exceed the model budget.
const fullProject=S.project('Full context');
fullProject.instructions='Answer the exact question without inventing sources.';
fullProject.memories=Array.from({length:30},(_,i)=>'PRIVATE-MEMORY-'+i+' '+'m'.repeat(480));
fullProject.sources=[{id:S.uid(),name:'orchard-records.txt',text:Array.from({length:25},(_,i)=>'orchard record '+i+' '+'s'.repeat(1600)).join('\n')}];
const fullFiles=Array.from({length:5},(_,i)=>({id:S.uid(),name:'attachment-'+i+'.txt',text:'orchard '+ 'a'.repeat(5000)}));
let fullThread=S.thread('Full context');
fullThread=S.append(fullThread,'user','orchard question','human');
const fullCtx=S.context(fullProject,fullThread,{memory:true,sources:true,attachments:fullFiles});
ok(()=>assert.equal(fullCtx.optional_context_truncated,true));
ok(()=>assert(fullCtx.messages[0].content.length<=24000));
ok(()=>assert(Buffer.byteLength(JSON.stringify(fullCtx.messages),'utf8')<=80000));
ok(()=>assert.equal(fullCtx.messages.at(-1).content,'orchard question'));
ok(()=>assert.equal(fullCtx.attachments_supplied.length,5));
ok(()=>assert(fullCtx.messages[0].content.includes('Some optional context was omitted')));
ok(()=>assert(!fullCtx.messages[0].content.includes('PRIVATE-MEMORY-')));
ok(()=>assert.deepEqual(fullCtx.memory_review,{status:'omitted_budget',requested_count:30,included_count:0}));
ok(()=>assert(fullCtx.citations.length>0));
let longHistory=S.thread('Many turns');
for(let i=0;i<23;i++){
 longHistory=S.append(longHistory,'user','orchard '+ 'u'.repeat(1650),'human');
 longHistory=S.append(longHistory,'assistant','reply '+ 'a'.repeat(1650),'model');
}
longHistory=S.append(longHistory,'user','orchard question','human');
const tightCtx=S.context(fullProject,longHistory,{memory:true,sources:true,attachments:fullFiles});
ok(()=>assert(Buffer.byteLength(JSON.stringify(tightCtx.messages),'utf8')<=80000));
ok(()=>assert(tightCtx.messages[0].content.length<=24000));
ok(()=>assert.equal(tightCtx.messages.at(-1).content,'orchard question'));
ok(()=>assert(tightCtx.omitted_messages>0));
ok(()=>assert(!tightCtx.messages[0].content.includes('Untrusted source passages;') ? tightCtx.citations.length===0 : tightCtx.citations.length>0));
ok(()=>assert(!tightCtx.messages[0].content.includes('one-turn local-file excerpts') ? tightCtx.attachments_supplied.length===0 : tightCtx.attachments_supplied.length===5));
const reminder={title:'مرور، برنامه; '.repeat(9),start:'2028-02-29T09:15',repeat:'weekly',advance:'15'};
const calendar=globalThis.NexusCalendar.calendarFile(reminder,{uid:'00000000-0000-4000-8000-000000000000',now:new Date('2026-11-20T08:00:00Z')});
const unfolded=calendar.replace(/\r\n /g,'');
ok(()=>assert(calendar.split('\r\n').every(line=>Buffer.byteLength(line)<=75)));
ok(()=>assert(unfolded.includes('DTSTART:20280229T091500\r\n')&&unfolded.includes('DTSTAMP:20261120T080000Z')));
ok(()=>assert(unfolded.includes('RRULE:FREQ=WEEKLY')&&unfolded.includes('TRIGGER:-PT15M')));
ok(()=>assert(unfolded.includes('SUMMARY:مرور، برنامه\\;')));
const single=globalThis.NexusCalendar.calendarFile({...reminder,title:'Review, a\r\nSUMMARY:unexpected',repeat:'once',advance:'0'});
ok(()=>assert(!single.includes('RRULE:')&&single.includes('TRIGGER:PT0S')&&!single.includes('\r\nSUMMARY:unexpected')));
ok(()=>assert.throws(()=>globalThis.NexusCalendar.calendarFile({...reminder,start:'2027-02-29T09:15'})));
ok(()=>assert.throws(()=>globalThis.NexusCalendar.calendarFile({...reminder,repeat:'yearly'})));
/* Synthetic credential shapes only; no real secrets or provider requests. */
const privacyClean=S.inspectSecrets([{role:'user',content:'Explain this public tutorial.'}]);
ok(()=>assert.equal(privacyClean.possible_secrets,false));
ok(()=>assert.deepEqual(privacyClean.categories,[]));
for(const [label,fixture] of [
 ['GitHub token','github_pat_'+'A'.repeat(40)],
 ['model API key','sk-proj-'+'b'.repeat(40)],
 ['AWS access key','AKIA'+'C'.repeat(16)],
 ['private-key block','-----BEGIN OPENSSH PRIVATE KEY-----\nSYNTHETIC'],
 ['bearer credential','Authorization: Bearer '+'x'.repeat(40)]
]){
 const result=S.inspectSecrets([{role:'user',content:fixture}]);
 ok(()=>assert.equal(result.possible_secrets,true));
 ok(()=>assert.deepEqual(result.categories,[label]));
 ok(()=>assert(!JSON.stringify(result).includes(fixture)));
}
const privacyTurns=S.inspectSecrets([{role:'user',content:'ghp_'+'Q'.repeat(40)},{role:'assistant',content:'AKIA'+'D'.repeat(16)}]);
ok(()=>assert.equal(privacyTurns.categories.length,2));
ok(()=>assert.equal(S.inspectSecrets([{role:'user',content:'-----BEGIN PUBLIC KEY-----, sk-demo and AKIA123 are examples'}]).possible_secrets,false));
ok(()=>assert.throws(()=>S.inspectSecrets([{role:'system',content:'not a chat turn'}]),/privacy-input/));
ok(()=>assert.throws(()=>S.inspectSecrets([{role:'user',content:4}]),/privacy-input/));
console.log(JSON.stringify({status:'PASS',checks,scope:'synthetic-state-and-encryption',live_model_tested:false}));
