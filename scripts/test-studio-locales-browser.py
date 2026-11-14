#!/usr/bin/env python3
"""Real file inputs: persistent locale choices and isolated asynchronous imports."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 25
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=code=>{$('language').value=code;$('language').dispatchEvent(new Event('change'))};
 const title=()=>$('conversation-card').querySelector('h2').textContent,snapshot=()=>JSON.stringify(NexusStudioUI.snapshot());
 const pack=(code,label,dir='ltr')=>JSON.stringify({schema:'nexus.studio.locale.v1',code,dir,messages:{...EN,conversation:label}});
 const handle=$('language-file').onchange,tasks=[],nativeText=File.prototype.text,delays=new Map();let reads=0;
 $('language-file').onchange=event=>{const task=Promise.resolve(handle(event));tasks.push(task);return task};
 File.prototype.text=async function(){reads++;const delay=delays.get(this.name);if(delay){delay.entered=true;await delay.gate}return nativeText.call(this)};
 function upload(raw,name='locale.json'){const dt=new DataTransfer();if(raw!==null)dt.items.add(new File([raw],name,{type:'application/json'}));$('language-file').files=dt.files;$('language-file').dispatchEvent(new Event('change'));return tasks.at(-1)}
 function pause(name){let resolve,reject;const delay={entered:false,gate:new Promise((a,b)=>{resolve=a;reject=b})};delays.set(name,delay);return {...delay,ready:()=>delay.entered,resolve,reject}}
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};fill('project-title','SYNTHETIC LOCALE PROJECT');$('new-project').click();const original=snapshot();
  await upload(pack('es','Conversación'));assert(document.documentElement.lang==='es'&&title()==='Conversación','first-pack-applies');
  await upload(pack('he','שיחה','rtl'));assert(document.documentElement.dir==='rtl','rtl-pack-applies');
  change('es');assert(title()==='Conversación','earlier-pack-remains-usable-after-second-import');
  change('he');assert(title()==='שיחה'&&document.documentElement.dir==='rtl','earlier-rtl-pack-retains-labels-and-direction');assert(snapshot()===original,'language-packs-do-not-modify-projects');

  const manual=pause('manual.json'),pendingManual=upload(pack('es','STALE MANUAL'),'manual.json');await wait(manual.ready);change('en');manual.resolve();await pendingManual;
  assert(document.documentElement.lang==='en','late-import-cannot-override-manual-language-choice');change('es');assert(title()==='Conversación','late-import-is-not-installed-in-background');
  const older=pause('older.json'),pendingOlder=upload(pack('es','STALE OLDER'),'older.json');await wait(older.ready);await upload(pack('fr','Conversation FR'));older.resolve();await pendingOlder;
  assert(document.documentElement.lang==='fr'&&title()==='Conversation FR','newest-file-selection-wins');change('es');assert(title()==='Conversación','superseded-import-does-not-replace-old-pack');change('fr');

  const failed=pause('failed.json'),pendingFailure=upload('{broken','failed.json');await wait(failed.ready);$('lock').click();const lockedStatus=$('status').textContent;failed.reject(Error('PRIVATE_STALE_FILE_ERROR'));await pendingFailure;
  assert($('status').textContent===lockedStatus,'late-file-failure-cannot-change-locked-status');assert(NexusStudioUI.snapshot().projects.length===0,'lock-retains-empty-session');
  const locked=pause('locked.json'),pendingLocked=upload(pack('he','STALE LOCK','rtl'),'locked.json');await wait(locked.ready);$('lock').click();locked.resolve();await pendingLocked;
  assert(document.documentElement.lang==='fr','late-success-cannot-change-locked-language');change('he');assert(title()==='שיחה','late-success-after-lock-is-not-installed');change('fr');

  fill('project-title','NEWER SYNTHETIC WORK');$('new-project').click();const newer=snapshot();fill('gateway','https://synthetic.invalid');
  const checking=pause('checking.json'),pendingCheckImport=upload(pack('es','STALE CHECK'),'checking.json');await wait(checking.ready);let statusSignal,finishStatus;
  window.fetch=async(url,options)=>{statusSignal=options.signal;return await new Promise(r=>finishStatus=r)};$('check-model').click();await wait(()=>finishStatus);
  assert($('language-file').disabled,'language-import-is-disabled-during-an-operation');const beforeReads=reads;await upload(pack('he','BUSY','rtl'),'busy.json');assert(reads===beforeReads,'busy-file-selection-does-not-read-or-apply');
  checking.resolve();await pendingCheckImport;assert(!statusSignal.aborted&&$('new-project').disabled,'old-language-import-cannot-stop-newer-status-request');assert(snapshot()===newer,'old-language-import-preserves-newer-projects');
  finishStatus(new Response(JSON.stringify({configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'synthetic.invalid'})));await wait(()=>$('model-status').textContent.includes('synthetic-model'));
  $('new-thread').click();fill('message','Approved synthetic question');$('prepare').click();assert(!$('request-review').hidden,'model-review-is-prepared');
  const sending=pause('sending.json'),pendingSendImport=upload(pack('es','STALE SEND'),'sending.json');await wait(sending.ready);let sendSignal,finishSend;
  window.fetch=async(url,options)=>{sendSignal=options.signal;return await new Promise(r=>finishSend=r)};$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();await wait(()=>finishSend);
  sending.resolve();await pendingSendImport;assert(!sendSignal.aborted&&document.documentElement.lang==='fr','old-language-import-cannot-cancel-approved-generation');
  finishSend(new Response(JSON.stringify({text:'Synthetic model draft',origin:'model',model:'synthetic-model',authority:'none'})));await wait(()=>NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===2);
  assert($('messages').textContent.includes('Synthetic model draft'),'approved-generation-still-completes');

  const status=$('status').textContent;await upload(null);assert($('status').textContent===status,'cancelled-picker-is-silent');
  await upload('{invalid');assert(document.documentElement.lang==='fr'&&$('status').textContent.includes('Operation failed'),'invalid-pack-does-not-change-language');
  for(const code of ['de','it','pt','nl','ja'])await upload(pack(code,'Label '+code));
  assert($('language').options.length===10,'eight-custom-packs-are-retained-with-two-builtins');const bounded=snapshot();
  await upload(pack('sv','Overflow'));assert(document.documentElement.lang==='ja'&&!Array.from($('language').options).some(o=>o.value==='sv'),'ninth-pack-is-rejected-without-evicting-existing-packs');
  await upload(pack('es','Conversación actualizada'));assert(title()==='Conversación actualizada'&&$('language').options.length===10,'existing-pack-can-be-updated-at-capacity');
  change('he');assert(title()==='שיחה'&&document.documentElement.dir==='rtl','capacity-and-updates-preserve-other-packs');assert(snapshot()===bounded,'capacity-errors-and-updates-preserve-projects');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_file_inputs_tested:true,real_provider:false,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
 finally{File.prototype.text=nativeText}
});
"""

if __name__ == '__main__':
    module.main()
