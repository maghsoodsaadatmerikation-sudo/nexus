#!/usr/bin/env python3
"""Real Chromium: local image preview, explicit provider review and text-only chat receipt."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.MIN_CHECKS = 11
base.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 const wait=async fn=>{for(let i=0;i<250;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('timeout')};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const png='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aT8AAAAASUVORK5CYII=';
 const bytes=Uint8Array.from(atob(png),x=>x.charCodeAt(0));
 const choose=()=>{const dt=new DataTransfer();dt.items.add(new File([bytes],'sample.png',{type:'image/png'}));
  $('studio-vision-file').files=dt.files;$('studio-vision-file').dispatchEvent(new Event('change'))};
 let statusCalls=0,uploads=0,seen=null,disabled=false,broken=false,statusReason='';
 const originalFetch=window.fetch;
 window.fetch=async (url,opts={})=>{
  if(String(url).endsWith('/studio-api/vision-status')){
   statusCalls++;
   return Response.json(statusReason?{configured:false,reason:statusReason,authority:'none'}:disabled?{configured:false,reason:'disabled',authority:'none'}:{
    configured:true,model:'synthetic-vision',provider_host:'provider.example',
    configuration_id:'a'.repeat(64),authority:'none'});
  }
  if(String(url).endsWith('/studio-api/vision')){
   uploads++;seen=JSON.parse(opts.body);
   assert(opts.method==='POST'&&opts.credentials==='omit'&&opts.redirect==='error','bounded-vision-transport-options');
   assert(opts.headers.authorization==='Bearer local-test-token','gateway-access-token-is-not-in-preview');
   if(broken)return new Response('unavailable',{status:503});
   return Response.json({text:'A single square in a test image.',origin:'model',
    modality:'image-and-text',model:'synthetic-vision',authority:'none'});
  }
  return originalFetch(url,opts);
 };
 try{
  assert(!!$('studio-vision-panel')&&!!$('studio-vision-open'),'image-tool-is-inside-chat');
  assert(NexusStudioVision.hasTransientWork()===false,'no-hidden-image-state');
  $('studio-vision-open').click();
  fill('gateway','https://provider.example');fill('gateway-token','local-test-token');
  assert($('studio-vision-preview').hidden && getComputedStyle($('studio-vision-preview')).display==='none',
   'hidden-preview-is-visually-hidden');
  $('studio-vision-settings').click();
  assert($('studio-model-settings').open&&document.activeElement===$('gateway'),
   'model-settings-open-directly-from-image-panel');
  $('studio-vision-check').click();
  await wait(()=>statusCalls===1&&$('studio-vision-status').textContent.includes('configured'));
  assert(uploads===0 && $('studio-vision-status').textContent.includes('No image was sent'),
   'preflight-connectivity-sends-no-image');
  choose();await wait(()=>$('studio-vision-preview').hidden===false);
  assert(statusCalls===1&&uploads===0,'selection-makes-no-provider-call');
  $('studio-vision-clear').click();
  assert(!NexusStudioVision.hasTransientWork()&&$('studio-vision-file').value===''&&
   $('studio-vision-preview').hidden&&getComputedStyle($('studio-vision-preview')).display==='none',
   'remove-image-button-clears-bytes-and-visual-preview');
  choose();await wait(()=>$('studio-vision-preview').hidden===false);
  assert(NexusStudioVision.hasTransientWork()&&NexusStudioUI.storageStatus().lossRisk,
   'temporary-vision-image-is-protected-against-loss');
  fill('studio-vision-question','What can you see?');
  $('studio-vision-review').click();
  await wait(()=>$('studio-vision-review-box').hidden===false);
  assert(statusCalls===2&&uploads===0&&$('studio-vision-send').disabled,
   'preview-and-status-are-not-consent');
  assert($('studio-vision-request-detail').textContent.includes('provider.example')&&
   $('studio-vision-request-detail').textContent.includes('SHA-256')&&
   $('studio-vision-request-detail').textContent.includes('What can you see?'),
   'review-shows-exact-provider-image-digest-and-question');
  $('studio-vision-consent').checked=true;
  $('studio-vision-consent').dispatchEvent(new Event('change'));
  $('studio-vision-send').click();
  await wait(()=>uploads===1&&NexusStudioUI.snapshot().projects[0]?.threads[0]?.nodes.length===2);
  const state=NexusStudioUI.snapshot(),str=JSON.stringify(state);
  assert(seen.consent===true&&seen.image_base64===png&&seen.mime_type==='image/png',
   'provider-receives-only-explicitly-approved-image');
  assert(!str.includes(png)&&str.includes('Image supplied (binary not saved)')&&
    str.includes('A single square'),'model-reply-stored-but-image-binary-is-not');
  assert(!NexusStudioVision.hasTransientWork()&&!$('studio-vision-preview').getAttribute('src'),
   'image-bytes-cleared-after-success');
  disabled=true;
  $('studio-vision-check').click();
  await wait(()=>statusCalls===3&&$('studio-vision-status').textContent.includes('not enabled'));
  assert(uploads===1,'disabled-gateway-preflight-is-read-only');
  choose();await wait(()=>$('studio-vision-preview').hidden===false);
  fill('studio-vision-question','Read the text');
  $('studio-vision-review').click();await wait(()=>$('studio-vision-status').textContent.includes('unavailable'));
  assert(uploads===1&&$('studio-vision-review-box').hidden,'disabled-provider-prevents-image-upload');
  disabled=false;
  statusReason='limit-reached';
  $('studio-vision-check').click();
  await wait(()=>$('studio-vision-status').textContent.includes('attempt limit'));
  assert(uploads===1&&!$('studio-vision-status').textContent.includes('configured'),
   'exhausted-process-guard-is-visible-and-no-upload');
  statusReason='limit-unconfigured';
  $('studio-vision-check').click();
  await wait(()=>$('studio-vision-status').textContent.includes('not configured a bounded'));
  assert(uploads===1,'missing-operator-guard-is-visible-and-no-upload');
  statusReason='';
  $('studio-vision-review').click();await wait(()=>$('studio-vision-review-box').hidden===false);
  fill('studio-vision-question','Changed question');
  assert($('studio-vision-review-box').hidden&&$('studio-vision-send').disabled,
   'editing-reviewed-question-revokes-consent');
  const home=NexusStudioUI.selection();
  window.confirm=()=>false;
  $('new-thread').click();
  assert(NexusStudioUI.selection().threadId===home.threadId&&NexusStudioVision.hasTransientWork(),
   'declined-new-chat-does-not-discard-private-image');
  window.confirm=()=>true;
  $('new-thread').click();
  assert(NexusStudioUI.selection().threadId!==home.threadId&&
   !NexusStudioVision.hasTransientWork()&&$('studio-vision-preview').hidden&&
   !$('studio-vision-question').value,'new-chat-clears-private-image');
  assert(NexusStudioUI.openConversation(home.projectId,home.threadId),'reopen-original-chat');
  const oldHead=NexusStudioUI.snapshot().projects[0].threads[0].head;
  $('messages').querySelector('article.message.user button').click();
  $('guide').click();
  assert($('branch').options.length===2,'original-and-new-branches-retained');
  choose();await wait(()=>$('studio-vision-preview').hidden===false);
  fill('studio-vision-question','Private branch image');
  $('branch').value=oldHead;
  $('branch').dispatchEvent(new Event('change'));
  assert(!NexusStudioVision.hasTransientWork()&&$('studio-vision-preview').hidden,
   'changing-chat-branch-clears-private-image');
  choose();await wait(()=>$('studio-vision-preview').hidden===false);
  fill('studio-vision-question','Private image before lock');
  $('lock').click();
  assert(!NexusStudioVision.hasTransientWork()&&$('studio-vision-question').value===''&&
    $('studio-vision-preview').hidden,'private-lock-clears-image-and-preview');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_vision_provider_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__ == '__main__':
    base.main()
