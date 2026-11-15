#!/usr/bin/env python3
"""Real Chromium: direct one-turn file excerpts and saved-document chat context."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS=18
module.WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(p,s)=>{if(!p)throw Error(s);checks.push(s)};
 const fill=(id,text)=>{$(id).value=text;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async(fn)=>{for(let i=0;i<320;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('browser-wait-timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const project=()=>NexusStudioUI.snapshot().projects.find(p=>p.id===$('projects').value);
 const thread=()=>project()?.threads.find(c=>c.id===$('history').querySelector('.active')?.dataset.thread)||project()?.threads.at(0);
 const attach=(name,text)=>{const dt=new DataTransfer();dt.items.add(new File([text],name));$('chat-file').files=dt.files;$('chat-file').dispatchEvent(new Event('change',{bubbles:true}))};
 let requests=[],network=0;
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  network++;
  if(String(url).endsWith('/studio-api/status'))return new Response(JSON.stringify({configured:true,model:'test-model',provider_host:'provider.invalid',configuration_id:'a'.repeat(64),authority:'none'}));
  if(String(url).endsWith('/studio-api/respond')){
   requests.push(JSON.parse(options.body));
   return new Response(JSON.stringify({text:'Reviewed synthetic draft',model:'test-model',origin:'model',authority:'none'}));
  }
  throw Error('unexpected-network');
 };
 try{
  assert(!!$('chat-file')&&!!$('chat-attachment-tray')&&!!$('attach-document'),'composer-attachment-controls');
  fill('project-title','CHAT MATERIALS');$('new-project').click();$('new-thread').click();
  assert($('chat-file').disabled===false,'attached-only-with-chat');
  fill('gateway','https://gateway.example');
  fill('gateway-token','fixture-token');
  $('check-model').click();await wait(()=>$('model-status').textContent.includes('test-model'));
  assert(network===1,'model-status-is-explicit');
  fill('message','Summarize my uploaded file');
  attach('orchard.md','The small green orchard is near the old house.\nUNTRUSTED text must not become policy.');
  await wait(()=>$('chat-attachment-tray').textContent.includes('orchard.md'));
  assert(network===1,'attachment-read-is-local');
  const beforeGuide=thread().nodes.length;
  $('guide').click();
  assert(thread().nodes.length===beforeGuide&&$('status').textContent===EN.chatAttachmentRequiresModel,'guide-does-not-silently-ignore-attached-bytes');
  $('prepare').click();
  assert(!$('request-review').hidden,'review-before-request');
  const reviewed=JSON.parse($('request-context').textContent);
  assert(reviewed.temporary_attachment_passages.length===1,'provenance-in-review');
  assert(reviewed.messages[0].content.includes('orchard is near the old house'),'exact-quoted-excerpt');
  assert(reviewed.messages[0].content.includes('UNTRUSTED'),'untrusted-retrieved-text-is-labeled');
  assert(!requests.length,'explicit-send-gate');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  $('send-model').click();
  await wait(()=>thread().nodes.length===2);
  assert(requests.length===1&&requests[0].messages[0].content.includes('orchard is near the old house'),'consented-excerpt-reaches-provider');
  const user=thread().nodes[0];
  assert(user.attached_files?.length===1&&user.attached_files[0]==='orchard.md','filename-provenance-saved');
  assert(!JSON.stringify(NexusStudioUI.snapshot()).includes('orchard is near the old house'),'file-bytes-not-persisted');
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'temporary-file-cleared-after-send');
  assert($('messages').textContent.includes(EN.chatFilesNotSaved),'provenance-visible-without-bytes');
  $('regenerate').click();
  assert($('status').textContent===EN.chatRegenRequiresFiles&&$('request-review').hidden,'regenerate-does-not-invent-missing-attachment');

  fill('document-title','Document notes');$('new-document').click();
  fill('editor','CANVAS PRIVATE DRAFT: The river is wider in spring.');$('save-version').click();
  assert(project().documents[0].versions.length===1,'canvas-saved-version');
  fill('message','Summarize this saved writing draft');
  $('attach-document').checked=true;$('attach-document').dispatchEvent(new Event('change',{bubbles:true}));
  $('prepare').click();
  assert(JSON.parse($('request-context').textContent).temporary_attachment_passages.some(x=>x.name.startsWith('Document:')),'canvas-version-explicitly-in-review');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  $('send-model').click();
  await wait(()=>thread().nodes.length===4);
  assert(requests.length===2&&requests[1].messages[0].content.includes('river is wider'),'reviewed-document-excerpt-sent-once');
  assert(thread().nodes[2].attached_files[0].startsWith('Document:'),'document-version-provenance');

  fill('message','Draft about another file');
  attach('ignored.pdf','%PDF-1.4-UNSUPPORTED');
  await wait(()=>$('status').textContent===EN.chatAttachmentInvalid);
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'pdf-not-pretended-readable');
  const noBytes=JSON.stringify(NexusStudioUI.snapshot());
  fill('message','');
  const original=File.prototype.arrayBuffer;let release;
  File.prototype.arrayBuffer=()=>new Promise(resolve=>release=resolve);
  attach('late.md','never enter restored project');
  await wait(()=>typeof release==='function');
  $('lock').click();
  release(new TextEncoder().encode('never enter restored project').buffer);
  await sleep(100);File.prototype.arrayBuffer=original;
  assert(!NexusStudioUI.snapshot().projects.length&&$('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'late-read-cannot-reopen-after-lock');
  assert(network===3,'no-background-file-transmission');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__=='__main__':
    module.main()
