#!/usr/bin/env python3
"""Stage27 actual Chromium acceptance of custom user assistants and encrypted scoped memory."""
import importlib.util
from pathlib import Path
ref=Path(__file__).with_name("test-research-chat-browser.py")
spec=importlib.util.spec_from_file_location("nexus_fixture",ref)
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.WITNESS=r"""
window.addEventListener('load',async()=>{
 const el=id=>document.getElementById(id),checks=[];
 const assert=(value,key)=>{if(!value)throw Error(key);checks.push(key)};
 const fill=(id,value)=>{el(id).value=value;el(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<500;i++){if(fn())return;await new Promise(r=>setTimeout(r,10))}throw Error('timeout')};
 const pass='stage27-synthetic-private-passphrase';
 const MARK='STAGE27_SYNTHETIC_USER_MEMORY_PRIVATE';
 const INSTRUCTION='STAGE27_SYNTHETIC_USER_INSTRUCTION';
 const calls=[];
 window.fetch=(...args)=>{calls.push(args);throw Error('no_network_allowed')};
 window.confirm=()=>true;
 try{
  assert(!vault.unlocked&&current===null&&calls.length===0,'no-automatic-privileges');
  assert(el('assistant-name')&&el('assistant-instructions')&&el('assistant-memory'),'profile-memory-editors-rendered');
  fill('title','Synthetic medical research');
  fill('goal','Study a synthetic source');
  fill('steps','Verify citations');
  fill('assistant-name','My Source Analyst');
  fill('assistant-instructions',INSTRUCTION);
  fill('assistant-style','detailed');
  fill('assistant-memory','Prefer verified sources\n'+MARK);
  el('create').click();
  assert(current&&current.assistant_profile.name==='My Source Analyst'&&current.memory.length===2,
    'custom-assistant-and-user-memory-are-project-scoped');
  assert(current.tasks[0].status==='todo'&&!current.tasks[0].reviewed,
    'customization-does-not-complete-or-authorize-any-task');
  const originalID=current.id;
  const preview=NexusWorkMode.context(current,current.tasks[0].id);
  assert(preview.includes(INSTRUCTION)&&preview.includes(MARK)&&preview.includes('Current task'),
     'only-reviewed-project-context-with-task');
  el('prepare').click();
  assert(el('prompt').value.includes(INSTRUCTION)&&calls.length===0&&el('share').checked===false,
    'prepared-context-does-not-auto-send');
  fill('pass',pass);fill('repeat',pass);el('vault-create').click();await wait(()=>!busy);
  assert(vault.unlocked,'explicit-encrypted-archive-create');
  el('save').click();await wait(()=>!busy);
  const raw=JSON.stringify(await vault.store.read());
  assert(!raw.includes(MARK)&&!raw.includes(INSTRUCTION)&&!raw.includes('My Source Analyst'),
     'archive-ciphertext-does-not-expose-memory-or-custom-name');
  assert(current.id===originalID,'save-does-not-replace-project');
  el('lock').click();assert(!vault.unlocked&&current===null,'explicit-lock-clears-unlocked-project');
  fill('pass',pass);el('unlock').click();await wait(()=>!busy);
  assert(vault.unlocked&&current===null,'unlock-does-not-open-project-automatically');
  el('projects').value=originalID;el('projects').dispatchEvent(new Event('change'));el('open').click();
  assert(current.id===originalID&&current.memory[1]===MARK&&current.assistant_profile.instructions===INSTRUCTION,
    'encrypted-profile-and-scoped-memory-survive-reload');
  assert(el('assistant-memory').value.includes(MARK)&&el('assistant-instructions').value===INSTRUCTION,
    'profile-memory-editor-renders-restored-state');
  assert(el('assistant-style').value==='detailed'&&el('assistant-name').value==='My Source Analyst',
    'custom-style-and-name-resume-from-encrypted-storage');
  assert(current.tasks.length===1&&current.tasks[0].status==='todo',
    'encrypted-profile-reopen-cannot-complete-a-task');
  fill('assistant-memory',Array(9).fill('synthetic preference').join('\n'));
  el('edit-project').click();
  assert(current.memory.length===2&&projectDraft,'overlimit-edit-refused-atomically');
  fill('assistant-memory','Keep the structure minimal');
  el('edit-project').click();
  assert(current.memory.length===1&&current.memory[0]==='Keep the structure minimal',
    'user-reviews-and-explicitly-applies-memory-change');
  assert(dirty&&current.tasks[0].status==='todo'&&calls.length===0,
    'local-customization-does-not-write-or-send-unapproved-requests');
  el('save').click();await wait(()=>!busy);
  assert(!dirty,'explicit-save-completes-customization');
  el('language').value='fa';el('language').dispatchEvent(new Event('change'));
  assert(el('assistant-name').previousElementSibling.textContent.includes('دستیار'),
    'persian-profile-controls-are-translated');
  assert(localStorage.length===0&&sessionStorage.length===0,
    'no-plaintext-local-or-session-storage');
  el('nexus-browser-result').textContent=JSON.stringify({
    status:'PASS',checks,width:innerWidth,provider_requests:calls.length,
    mode:'custom_assistant_project_memory_encrypted_only',
    real_model_inference:false
  });
 }catch(err){el('nexus-browser-result').textContent=JSON.stringify({
   status:'FAIL',reason:String(err?.message||err),checks
 })}
});
"""
if __name__=="__main__":
    fixture.main('web/work-mode.html')
