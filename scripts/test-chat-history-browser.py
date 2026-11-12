#!/usr/bin/env python3
"""Synthetic real-browser acceptance for opt-in encrypted history (no providers)."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('research_fixture',Path(__file__).with_name('test-research-chat-browser.py'))
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
fixture.WITNESS=r"""
window.addEventListener('load',async()=>{
const el=id=>document.getElementById(id),checks=[],calls=[],exports=[];
const assert=(yes,key)=>{if(!yes)throw Error(key);checks.push(key)};
const fill=(id,value)=>{el(id).value=value;el(id).dispatchEvent(new Event('input',{bubbles:true}))};
const tick=()=>new Promise(r=>setTimeout(r,20));
const wait=async test=>{for(let i=0;i<500;i++){if(test())return;await tick()}throw Error('waiting-timeout')};
const idle=()=>wait(()=>!historyBusy);
const pass='synthetic-private-history-passphrase',secret='PRIVATE_HISTORY_QUESTION';
const answer=()=>({schema:'nexus.research-chat.v1',mode:'retrieval_assisted_extractive',authority:'none',judgment_changed:false,answer:'Synthetic historical passage. [S1]',context:null,context_origin:null,history_context_attached:false,answer_status:'source_excerpts_available',claims:[{text:'Synthetic historical passage.',citation_ids:['S1'],origin:'user_supplied_excerpt',uncertainty:'not_independently_verified'}],sources:[{id:'S1',title:'Synthetic historical source',url:'https://example.org/history',excerpt:'Synthetic historical passage.',origin:'user_supplied_excerpt',provider:'manual_review',retrieved_at_unix:null}],providers:[],unknowns:['Unverified synthetic context.'],next_question:'Review a primary source?'});
let respond=async()=>({ok:true,json:async()=>answer()});
window.fetch=async(url,options)=>{assert(url==='/v1/research-chat','only-own-chat-endpoint');calls.push(JSON.parse(options.body));return respond()};
window.confirm=()=>true;
const originalURL=URL.createObjectURL,blobs=new Map();URL.createObjectURL=b=>{const u=originalURL(b);blobs.set(u,b);return u};
HTMLAnchorElement.prototype.click=function(){if(this.download)exports.push({name:this.download,blob:blobs.get(this.href)})};
const send=async message=>{fill('message',message);el('chat-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await wait(()=>!busy)};
const select=id=>{el('history-list').value=id;el('history-list').dispatchEvent(new Event('change'))};
const toggle=(id,value)=>{el(id).checked=value;el(id).dispatchEvent(new Event('change'))};
const unlock=async password=>{fill('history-pass',password);el('history-unlock').click();await idle()};
const restore=async(raw,password)=>{fill('history-pass',password);const transfer=new DataTransfer();transfer.items.add(new File([raw],'synthetic.encrypted.json',{type:'application/json'}));el('history-file').files=transfer.files;el('history-file').dispatchEvent(new Event('change'));await idle()};
try{
 assert(!chatVault.unlocked&&!el('history-save').checked&&!el('history-use').checked,'saving-and-attachment-default-off');
 const initial=await indexedDB.databases();assert(!initial.some(d=>d.name==='nexus-private-chat-history'),'page-load-does-not-create-history-database');
 fill('token','PRIVATE_TOKEN_MUST_NOT_BE_SAVED');await send(secret);
 assert(calls.length===1&&calls[0].history_context===null,'ordinary-chat-has-no-hidden-history');
 assert(!chatVault.unlocked,'chat-does-not-unlock-or-save');
 fill('history-pass',pass);fill('history-repeat',pass);el('history-create').click();await idle();
 assert(chatVault.unlocked&&chatVault.list().length===0,'explicit-create-initializes-empty-archive');
 assert(el('history-pass').value===''&&el('history-repeat').value==='','passphrase-fields-cleared');
 assert(!el('history-save').checked&&!el('history-use').checked,'create-does-not-enable-saving-or-attachment');
 fill('history-name','PRIVATE_SYNTHETIC_TITLE');el('history-save-now').click();await idle();
 const id=chatVault.list()[0]?.id;assert(!!id&&chatVault.get(id).turns[0].content===secret,'manual-save-persists-selected-completed-chat');
 const raw=JSON.stringify(await chatVault.store.read());assert(![secret,'PRIVATE_SYNTHETIC_TITLE',pass,'PRIVATE_TOKEN_MUST_NOT_BE_SAVED'].some(s=>raw.includes(s)),'indexeddb-has-no-plaintext-message-title-token-or-key');
 assert(!el('history-save').checked,'one-time-save-does-not-enable-autosave');
 el('history-lock').click();await unlock('incorrect-long-passphrase');assert(!chatVault.unlocked,'wrong-passphrase-does-not-unlock');
 await unlock(pass);assert(chatVault.unlocked&&chatVault.list().length===1,'unlock-restores-saved-history');
 const fresh=new NexusChatHistory.Vault();await fresh.unlock(pass);assert(fresh.get(id).turns[0].content===secret,'fresh-vault-restores-from-real-indexeddb');fresh.lock();
 assert(!el('history-save').checked&&!el('history-use').checked,'unlock-does-not-reenable-consent');
 el('clear').click();assert(chatVault.list().length===1&&turns.length===0,'clear-active-chat-keeps-explicitly-saved-history');
 select(id);await send('New conversation without history');assert(calls.at(-1).history_context===null,'selection-alone-does-not-attach-history');
 toggle('history-use',true);await send('Use my selected old context');
 assert(calls.at(-1).history_context.conversation_id===id&&calls.at(-1).history_context.messages[0].content===secret,'explicit-attachment-sends-only-selected-conversation');
 assert(calls.at(-1).search===false&&calls.at(-1).query===null,'history-never-becomes-a-search-query-automatically');
 toggle('history-use',false);await send('No selected history now');assert(calls.at(-1).history_context===null,'unchecking-detaches-future-history');
 const beforeOpen=calls.length;select(id);el('history-open').click();assert(calls.length===beforeOpen&&turns.length===2&&turns[0].content===secret,'open-restores-current-chat-without-network');
 assert(!el('history-save').checked&&!el('history-use').checked,'opening-history-keeps-consent-off');
 toggle('history-save',true);await idle();await send('Keep my next successful reply');await idle();
 assert(chatVault.get(id).turns.length===4,'explicit-autosave-keeps-future-completed-replies');
 toggle('history-save',false);const revision=chatVault.env.revision;await send('Do not save this reply');await idle();assert(chatVault.env.revision===revision,'disabling-autosave-stops-persistent-writes');
 const commit=chatVault.store.commit;chatVault.store.commit=async()=>{throw Error('history-storage')};fill('message','UNSENT_DRAFT');el('history-save-now').click();await idle();
 assert(el('message').value==='UNSENT_DRAFT'&&turns.length===6&&chatVault.env.revision===revision,'storage-failure-preserves-draft-and-existing-saved-data');
 assert(el('history-status').dataset.k==='hStorage','storage-failure-does-not-claim-save');chatVault.store.commit=commit;
 el('history-backup').click();await idle();const backup=await exports.at(-1).blob.text();assert(exports.at(-1).name==='nexus-chat-history.encrypted.json'&&!backup.includes(secret),'encrypted-portable-download-excludes-plaintext');
 await restore(backup,'incorrect-long-passphrase');assert(!chatVault.unlocked&&JSON.stringify(await chatVault.store.read()).includes(revision),'wrong-passphrase-import-preserves-original-archive');
 await restore(backup,pass);assert(chatVault.unlocked&&chatVault.list().length===1&&chatVault.env.revision!==revision,'explicit-import-authenticates-and-rotates-revision');
 assert(!el('history-save').checked&&!el('history-use').checked,'restoring-does-not-enable-consent');
 select(id);toggle('history-use',true);let release;respond=()=>new Promise(r=>release=r);
 fill('message','Pending old context');el('chat-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await wait(()=>!!release);
 fill('token','DIFFERENT_SYNTHETIC_TOKEN');release({ok:true,json:async()=>answer()});await tick();
 assert(!chatVault.unlocked&&!el('history-use').checked&&!el('history-save').checked&&turns.length===0,'token-change-locks-detaches-and-discards-late-answer');
 await unlock(pass);select(id);el('history-open').click();el('history-delete').click();await idle();assert(chatVault.list().length===0&&turns.length===0,'delete-selected-removes-saved-and-open-copy');
 await restore(backup,pass);el('history-erase').click();await idle();assert(!chatVault.unlocked&&await chatVault.store.read()===null,'delete-all-removes-persisted-encrypted-archive');
 assert(localStorage.length===0&&sessionStorage.length===0,'no-plaintext-or-token-fallback-storage');
 el('language').value='fa';el('language').dispatchEvent(new Event('change'));assert(el('history-create').textContent.includes('رمز')&&document.documentElement.dir==='rtl','persian-history-controls-render');
 el('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,provider_requests:0,authority:'none'});
}catch(error){el('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message),checks})}
});
"""
if __name__=='__main__':fixture.main()
