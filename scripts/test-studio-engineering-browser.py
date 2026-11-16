#!/usr/bin/env python3
"""Real Chromium Engineering Agent UI acceptance: inert review, consent and lock."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.MIN_CHECKS=15
base.WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};
 const fill=(id,text)=>{$(id).value=text;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<150;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('timeout')};
 const h='a'.repeat(64),w='b'.repeat(64),other='c'.repeat(64);
 const proposal=()=>JSON.stringify({schema:'nexus.engineering.proposal.v1',workspace:'demo',steps:[{tool:'write',path:'src/private.py',text:'PRIVATE_AGENT_SECRET_CODE'}]});
 const review=()=>JSON.stringify({schema:'nexus.engineering.review.v1',authority:'none',plan_sha256:h,workspace_sha256:w,workspace:'demo',plan_version:3,steps:[{index:0,tool:'write',risk:'writes-files'}],status:'not-executed',review_required:true,note:'Untrusted'});
 const receipt=()=>JSON.stringify({schema:'nexus.engineering.chat-receipt.v1',origin:'local-engineering-worker',authority:'none',verification:'not-independent-attestation',plan_sha256:h,journal_state:'finished',execution_status:'complete',workspace_sha256_before:w,workspace_sha256_after:other,steps:[{index:0,tool:'write',status:'completed'}],note:'Not an independent attestation'});
 let network=0,downloads=0;
 // Never let native confirmation dialogs block the private CDP test runner.
 window.confirm=()=>true;
 window.fetch=()=>{network++;throw Error('unexpected-network')};
 const originalClick=HTMLAnchorElement.prototype.click;
 HTMLAnchorElement.prototype.click=function(){downloads++};
 try{
  assert(!!$('engineering-panel'),'panel-inside-conversation');
  assert($('engineering-download').disabled&&$('engineering-chat').disabled,'default-deny');
  fill('project-title','TEST ENGINEER');$('new-project').click();$('new-thread').click();
  fill('engineering-text',proposal());$('engineering-inspect').click();
  assert($('engineering-report').textContent.includes('writes-files'),'risk-preview');
  assert(!$('engineering-report').textContent.includes('PRIVATE_AGENT_SECRET_CODE'),'no-source-in-preview');
  assert($('engineering-download').disabled,'explicit-consent-required');
  $('engineering-consent').checked=true;$('engineering-consent').dispatchEvent(new Event('change'));
  assert(!$('engineering-download').disabled&&$('engineering-chat').disabled,'proposal-export-only');
  $('engineering-download').click();assert(downloads===1,'manual-download');
  fill('engineering-text',proposal().replace('src/private.py','../private.py'));
  assert($('engineering-download').disabled,'edited-source-invalidates-approval');
  $('engineering-inspect').click();assert($('engineering-status').textContent.includes('Invalid'),'invalid-path-rejected');
  fill('engineering-text',review());$('engineering-inspect').click();
  $('engineering-consent').checked=true;$('engineering-consent').dispatchEvent(new Event('change'));
  $('engineering-chat').click();
  assert($('chat-attachment-tray').textContent.includes('Engineering review'),'review-staged-into-chat');
  assert(!$('chat-attachment-tray').textContent.includes('PRIVATE_AGENT_SECRET_CODE'),'no-command-in-chat');
  assert($('engineering-chat').disabled,'single-stage-approval');
  $('clear-chat-files').click();
  fill('engineering-text',receipt());$('engineering-inspect').click();
  assert($('engineering-report').textContent.includes('complete'),'receipt-visible');
  $('engineering-consent').checked=true;$('engineering-consent').dispatchEvent(new Event('change'));
  $('engineering-chat').click();assert($('chat-attachment-tray').textContent.includes('Engineering receipt'),'receipt-review-staged');
  $('new-thread').click();fill('engineering-text',review());$('engineering-inspect').click();
  $('engineering-consent').checked=true;$('engineering-consent').dispatchEvent(new Event('change'));
  assert(!$('engineering-chat').disabled,'review-staged-to-active-thread-only');
  const oldThreadButton=[...$('history').querySelectorAll('button')].find(b=>!b.classList.contains('active'));
  assert(!!oldThreadButton,'another-thread-is-selectable');oldThreadButton.click();
  assert($('engineering-text').value===''&&$('engineering-report').textContent===''&&$('engineering-chat').disabled,'history-switch-erases-review-and-consent');
  let releaseRead;const originalBuffer=File.prototype.arrayBuffer;
  File.prototype.arrayBuffer=()=>new Promise(resolve=>releaseRead=resolve);
  const dt=new DataTransfer();dt.items.add(new File([review()],'review.json'));
  $('engineering-file').files=dt.files;$('engineering-file').dispatchEvent(new Event('change'));
  await wait(()=>!!releaseRead);$('lock').click();releaseRead(new TextEncoder().encode(review()).buffer);await new Promise(r=>setTimeout(r,60));
  File.prototype.arrayBuffer=originalBuffer;
  assert($('engineering-text').value===''&&$('engineering-report').textContent==='','lock-and-late-read-cleared');
  assert($('engineering-chat').disabled,'locked-cannot-stage');
  assert(network===0,'no-network');
  $('language').value='fa';$('language').dispatchEvent(new Event('change'));
  assert($('engineering-panel').textContent.includes('عامل مهندسی'),'persian-translation');
  assert(document.documentElement.scrollWidth<=innerWidth+2,'mobile-no-horizontal-overflow');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_docker_used:false,model_tool_execution:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
 finally{HTMLAnchorElement.prototype.click=originalClick}
});
"""
if __name__=='__main__':base.main()
