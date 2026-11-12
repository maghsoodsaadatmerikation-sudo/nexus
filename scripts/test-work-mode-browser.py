#!/usr/bin/env python3
"""Real browser Work Mode acceptance with synthetic projects and no provider calls."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('research_fixture',Path(__file__).with_name('test-research-chat-browser.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.WITNESS=r"""
window.addEventListener('load',async()=>{
const el=id=>document.getElementById(id),checks=[],calls=[],downloads=[];
const assert=(v,key)=>{if(!v)throw Error(key);checks.push(key)};
const fill=(id,v)=>{el(id).value=v;el(id).dispatchEvent(new Event('input',{bubbles:true}))};
const change=(id,v)=>{fill(id,v);el(id).dispatchEvent(new Event('change',{bubbles:true}))};
const check=(id,v)=>{el(id).checked=v;el(id).dispatchEvent(new Event('input',{bubbles:true}))};
const wait=async test=>{for(let i=0;i<500;i++){if(test())return;await new Promise(r=>setTimeout(r,10))}throw Error('waiting-timeout')};
const idle=()=>wait(()=>!busy);
const choose=i=>el('tasks').children[i].querySelector('button').click();
const pass='synthetic-work-mode-passphrase';
const reply=()=>({schema:'nexus.research-chat.v1',mode:'retrieval_assisted_extractive',authority:'none',judgment_changed:false,answer:'Synthetic excerpt, not a completed task. [S1]',context:null,answer_status:'source_excerpts_available',claims:[{text:'Synthetic excerpt.',citation_ids:['S1'],origin:'user_supplied_excerpt',uncertainty:'not_independently_verified'}],sources:[{id:'S1',title:'Synthetic',url:'https://example.org/entry',excerpt:'Synthetic excerpt.',origin:'user_supplied_excerpt',provider:'manual_review',retrieved_at_unix:null}],providers:[],unknowns:['Unverified synthetic evidence.'],next_question:'What should we examine?'});
let respond=async()=>({ok:true,json:async()=>reply()});window.fetch=async(url,options)=>{calls.push({url,options,payload:JSON.parse(options.body)});return respond()};
window.confirm=()=>true;const original=URL.createObjectURL,blobs=new Map();URL.createObjectURL=b=>{const u=original(b);blobs.set(u,b);return u};HTMLAnchorElement.prototype.click=function(){if(this.download)downloads.push({name:this.download,blob:blobs.get(this.href)})};
try{
 assert(calls.length===0&&!vault.unlocked&&current===null,'no-automatic-network-archive-or-project');
 assert(!(await indexedDB.databases()).some(d=>d.name==='nexus-private-work-mode'),'opening-work-mode-does-not-open-history-or-create-storage');
 fill('title','PRIVATE_WORK_TITLE');fill('goal','PRIVATE_GOAL: prepare a reviewed report');fill('criteria','Check original evidence');fill('steps','Review inputs\nPrepare output');el('create').click();
 assert(current.tasks.length===2&&current.tasks.every(t=>t.status==='todo')&&dirty,'user-steps-become-pending-tasks-without-execution');
 const projectID=current.id,first=current.tasks[0].id,second=current.tasks[1].id;
 change('task-status','done');el('apply-task').click();assert(current.tasks[0].status==='todo','completion-needs-evidence-and-human-review');
 choose(1);el('dependencies').options[0].selected=true;el('dependencies').dispatchEvent(new Event('input'));change('task-status','doing');el('apply-task').click();assert(current.tasks[1].status==='todo','incomplete-prerequisite-blocks-start');
 choose(0);fill('evidence','Checked against original source');change('task-status','done');check('reviewed',true);el('apply-task').click();assert(current.tasks[0].status==='done'&&current.tasks[0].reviewed,'human-reviewed-evidence-can-complete-task');
 choose(1);el('dependencies').options[0].selected=true;el('dependencies').dispatchEvent(new Event('input'));change('task-status','doing');el('apply-task').click();assert(current.tasks[1].status==='doing','completed-prerequisite-allows-start');
 fill('note','PRIVATE_NOTE_NOT_SHARED');el('add-note').click();
 const transfer=new DataTransfer();transfer.items.add(new File(['PRIVATE_FILE_NOT_SHARED'],'private.txt',{type:'text/plain'}));el('file').files=transfer.files;el('file').dispatchEvent(new Event('change'));await wait(()=>current.files.length===1);
 assert(current.notes.length===1&&current.files[0].size===23&&calls.length===0,'notes-and-files-stay-local-and-never-execute');
 fill('evidence','UNAPPLIED_REVIEW');const transfer2=new DataTransfer();transfer2.items.add(new File(['Other'],'other.txt'));el('file').files=transfer2.files;el('file').dispatchEvent(new Event('change'));await wait(()=>current.files.length===2);assert(el('evidence').value==='UNAPPLIED_REVIEW'&&taskDraft,'file-attachment-preserves-unapplied-task-editor');
 el('apply-task').click();el('prepare').click();const prepared=el('prompt').value;assert(prepared.includes('PRIVATE_GOAL')&&!prepared.includes('PRIVATE_NOTE_NOT_SHARED')&&!prepared.includes('PRIVATE_FILE_NOT_SHARED')&&!prepared.includes('UNAPPLIED_REVIEW'),'prepared-context-excludes-notes-files-and-evidence');
 fill('token','PRIVATE_NEXUS_TOKEN');el('send').click();assert(calls.length===0,'task-context-needs-explicit-send-approval');
 check('share',true);el('send').click();assert(!el('share').checked,'sharing-approval-consumed-at-dispatch');await wait(()=>!chatBusy);
 assert(calls.length===1&&calls[0].url==='/v1/research-chat'&&calls[0].payload.history_context===null&&calls[0].payload.messages.length===1,'task-chat-uses-only-explicit-message-and-no-history');
 assert(!JSON.stringify(calls[0].payload).includes('PRIVATE_FILE_NOT_SHARED')&&!JSON.stringify(calls[0].payload).includes('PRIVATE_NOTE_NOT_SHARED'),'private-project-files-and-notes-are-not-sent');
 assert(current.tasks[1].status==='doing','assistant-reply-never-completes-task');el('keep-reply').click();assert(current.notes.at(-1).origin==='machine_draft'&&current.tasks[1].status==='doing','keeping-draft-preserves-machine-origin-and-task-state');
 check('share',true);fill('prompt','Edited task message');assert(!el('share').checked,'message-edit-revokes-sharing-approval');
 check('search',true);fill('query','approved public query');check('share',true);el('send').click();assert(calls.length===1,'search-needs-separate-query-approval');
 check('search-consent',true);el('send').click();assert(!el('search-consent').checked,'search-consent-consumed-at-dispatch');await wait(()=>!chatBusy);assert(calls.at(-1).payload.query==='approved public query','only-reviewed-query-is-shared-for-search');
 check('search',false);fill('pass',pass);fill('repeat',pass);el('vault-create').click();await idle();assert(vault.unlocked&&vault.list().length===0&&current.id===projectID,'archive-create-does-not-automatically-save-current-work');
 el('save').click();await idle();assert(vault.list().length===1&&!dirty,'explicit-save-persists-project');
 const encrypted=JSON.stringify(await vault.store.read());for(const secret of ['PRIVATE_WORK_TITLE','PRIVATE_NOTE_NOT_SHARED','PRIVATE_FILE_NOT_SHARED','PRIVATE_NEXUS_TOKEN',pass])assert(!encrypted.includes(secret),'encrypted-archive-excludes-readable-'+secret);
 const fresh=new W.Vault();await fresh.unlock(pass);assert(fresh.get(projectID).files.length===2,'fresh-vault-restores-project-and-files');fresh.lock();
 fill('note','A change after save');el('add-note').click();const revision=vault.env.revision,commit=vault.store.commit;vault.store.commit=async()=>{throw Error('work-storage')};el('save').click();await idle();assert(dirty&&current.notes.at(-1).text==='A change after save'&&vault.env.revision===revision,'failed-save-keeps-work-dirty-and-preserves-saved-version');vault.store.commit=commit;
 el('save').click();await idle();el('backup').click();await idle();const backup=await downloads.at(-1).blob.text();assert(downloads.at(-1).name==='nexus-work-mode.encrypted.json'&&!backup.includes('PRIVATE_WORK_TITLE'),'encrypted-backup-is-portable-without-readable-titles');
 el('export').click();const markdown=await downloads.at(-1).blob.text();assert(markdown.includes('PRIVATE_GOAL')&&!markdown.includes('PRIVATE_NEXUS_TOKEN')&&!markdown.includes('PRIVATE_FILE_NOT_SHARED'),'explicit-markdown-export-excludes-credentials-and-binary-files');
 let release;respond=()=>new Promise(r=>release=r);check('share',true);el('send').click();await wait(()=>!!release);el('lock').click();release({ok:true,json:async()=>reply()});await new Promise(r=>setTimeout(r,30));
 assert(!vault.unlocked&&current===null&&el('token').value===''&&el('reply').textContent===''&&lastReply===null,'lock-clears-project-key-token-and-discards-late-chat');
 fill('pass',pass);el('unlock').click();await idle();assert(vault.unlocked&&current===null&&el('projects').options.length===2,'unlock-does-not-autoload-a-project');
 el('projects').value=projectID;el('projects').dispatchEvent(new Event('change'));el('open').click();assert(current.id===projectID&&current.files.length===2&&!dirty,'explicit-resume-restores-selected-project');
 choose(1);fill('evidence','Verified output');change('task-status','done');check('reviewed',true);el('apply-task').click();assert(current.tasks.every(t=>t.status==='done')&&el('progress').textContent.includes('2/2'),'completion-count-reflects-reviewed-state');
 choose(0);change('task-status','todo');el('apply-task').click();assert(current.tasks[0].status==='done','reopening-prerequisite-cannot-invalidate-completed-dependent');choose(0);
 const before=JSON.stringify(current);fill('evidence','New unsaved edit');el('save').click();assert(JSON.stringify(current)===before&&taskDraft,'saving-does-not-silently-discard-unapplied-fields');choose(0);
 fill('criteria','Updated acceptance criterion');el('edit-project').click();assert(current.tasks.every(t=>t.status==='review'&&!t.reviewed)&&!el('reviewed').checked,'changed-criteria-invalidates-old-completions-and-editor-review');
 el('erase').click();await idle();assert(current===null&&!vault.unlocked&&await vault.store.read()===null,'erase-removes-encrypted-archive-and-open-work');
 fill('pass',pass);const imported=new DataTransfer();imported.items.add(new File([backup],'project.encrypted.json'));el('restore-file').files=imported.files;el('restore-file').dispatchEvent(new Event('change'));await idle();assert(vault.unlocked&&current===null&&vault.list().length===1,'explicit-restore-authenticates-archive-without-autoload');
 change('language','fa');assert(document.documentElement.dir==='rtl'&&el('create').textContent.includes('پروژه'),'persian-work-mode-and-rtl-layout');
 assert(localStorage.length===0&&sessionStorage.length===0,'no-plaintext-persistent-work-or-token-storage');assert(document.documentElement.scrollWidth<=innerWidth,'work-layout-fits-viewport');
 el('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,provider_requests:0,authority:'none'});
}catch(error){el('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message),checks})}
});
"""
if __name__=='__main__':fixture.main('web/work-mode.html')
