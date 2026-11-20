#!/usr/bin/env python3
"""Real Chromium acceptance: explicit research, analysis and code to chat handoff."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.MIN_CHECKS=18
base.WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,20))}throw Error('timeout')};
 const fill=(id,text)=>{$(id).value=text;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const file=(id,name,text)=>{const dt=new DataTransfer();dt.items.add(new File([text],name));$(id).files=dt.files;$(id).dispatchEvent(new Event('change'))};
 const snapshot=()=>NexusStudioUI.snapshot(),project=()=>snapshot().projects.find(p=>p.id===$('projects').value);
 let providerCalls=0,searchCalls=0;
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  if(String(url).endsWith('/studio-api/status'))return new Response(JSON.stringify({configured:true,model:'synthetic',provider_host:'synthetic.invalid',configuration_id:'a'.repeat(64)}));
  if(String(url).endsWith('/studio-api/respond')){providerCalls++;return new Response(JSON.stringify({text:'Fake response',model:'synthetic',origin:'model',authority:'none'}))}
  if(String(url).startsWith('https://en.wikipedia.org/')){searchCalls++;return new Response(JSON.stringify({query:{pages:{42:{pageid:42,title:'Source title',extract:'Unverified live source note from Wikipedia.'}}}}))}
  throw Error('unexpected-network');
 };
 try{
  fill('gateway','https://fake-gateway.example');$('check-model').click();await wait(()=>$('model-status').textContent.includes('synthetic'));
  fill('message','Explain the source with citations');
  fill('research-query','independent external source');
  $('research-consent').checked=true;$('research-run').click();await wait(()=>$('research-cards').children.length===1);
  const actions=$('research-cards').querySelectorAll('button');assert(actions.length===2,'research-card-two-separate-destinations');
  assert(snapshot().projects.length===0&&actions[0].disabled&&!actions[1].disabled,'first-run-research-can-go-to-chat');
  actions[1].click();
  assert(project().threads.length===1&&NexusStudioFocus.active()==='conversation-card'&&
   $('message').value==='Explain the source with citations'&&document.activeElement===$('message'),
   'first-handoff-creates-a-chat-and-retains-text');
  assert($('chat-file-panel').open&&NexusStudioCompose.mode()==='model'&&$('request-review').hidden&&
   $('research-query').value==='independent external source'&&$('research-cards').children.length===1,
   'handoff-shows-attachment-without-running-or-clearing-research');
  assert($('chat-attachment-tray').textContent.includes('Source title'),'research-excerpt-staged-in-chat');
  assert(project().sources.length===0,'research-handoff-not-permanent-source-enrollment');
  assert(providerCalls===0,'no-auto-model-send-for-research');
  $('prepare').click();let reviewed=JSON.parse($('request-context').textContent);
  assert(reviewed.messages[0].content.includes('https://en.wikipedia.org/?curid=42'),'research-url-in-reviewed-text');
  assert(reviewed.messages[0].content.includes('UNTRUSTED'),'research-text-marked-untrusted');
  assert(reviewed.temporary_attachment_passages.length>=1,'research-excerpt-provenance');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();
  await wait(()=>providerCalls===1&&project().threads[0].nodes.length===2);
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'research-transient-cleared-after-send');
  assert(!JSON.stringify(snapshot()).includes('Unverified live source note'),'research-result-bytes-not-persisted');

  // A local sandbox result can be explicitly used without pretending
  // the LLM ran the code itself.
  fill('message','Explain the calculation');
  $('code-sample').click();$('code-consent').checked=true;$('code-run').click();await wait(()=>$('code-result').textContent.includes('Local calculation'));
  $('code-chat').click();assert($('chat-attachment-tray').textContent.includes('Local code result'),'code-result-staged');
  assert(providerCalls===1,'code-execution-not-auto-sent');
  $('prepare').click();reviewed=JSON.parse($('request-context').textContent);
  assert(reviewed.messages[0].content.includes('Local calculation'),'review-includes-real-code-result');
  assert(reviewed.messages[0].content.includes('UNTRUSTED'),'code-result-not-instruction-authority');
  $('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();
  await wait(()=>providerCalls===2&&project().threads[0].nodes.length===4);

  // Real CSV parsing and group summaries can also become selected
  // next-turn context, without auto-registering a source file.
  const csv='Group,Score\nA,1\nA,3\nB,2\n';
  file('data-file','local.csv',csv);$('data-run').click();
  await wait(()=>$('data-status').textContent.includes('Analysis ready'));
  fill('message','Explain these descriptive statistics');
  assert(!$('data-chat').disabled,'analysis-handoff-enabled-after-run');
  $('data-chat').click();assert($('chat-attachment-tray').textContent.includes('local.csv'),'analysis-result-staged');
  assert(providerCalls===2,'data-analysis-does-not-auto-send');
  $('prepare').click();reviewed=JSON.parse($('request-context').textContent);
  assert(reviewed.messages[0].content.includes('Data analysis')&&reviewed.messages[0].content.includes('local.csv'),'analysis-summary-retrieved-for-chat');
  assert(reviewed.messages[0].content.includes('UNTRUSTED'),'analysis-not-model-policy');
  $('clear-chat-files').click();
  assert($('chat-attachment-tray').textContent.includes(EN.chatNoFiles),'explicit-clear-from-chat');
  assert($('request-review').hidden,'clear-revokes-previous-model-review');
  assert(NexusStudioCompose.mode()==='guide','clearing-handoff-restores-local-guide');
  const size=project().threads[0].nodes.length;
  fill('message','Different question');
  const rejected=NexusStudioUI.stageChatContext('Oversized','x'.repeat(131073));
  assert(rejected===false,'tool-output-size-cap');
  assert(project().threads[0].nodes.length===size,'invalid-tool-output-cannot-create-message');
  assert(searchCalls===1,'research-no-hidden-refetch');
  $('lock').click();
  file('data-file','fresh.csv','Name,Count\nA,2\nB,4\n');$('data-run').click();
  await wait(()=>$('data-status').textContent.includes('Analysis ready'));
  $('data-chat').click();
  assert(project()?.threads.length===1&&$('chat-attachment-tray').textContent.includes('fresh.csv')&&
   $('data-summary').textContent.includes('fresh.csv')&&providerCalls===2,
   'first-file-analysis-handoff-keeps-analysis-and-waits-for-approval');
  // The unified chat routes requests to reviewed connections, not directly to
  // provider APIs. No credentials or model execution are implied by a suggestion.
  fill('message','/github list open pull requests');
  const chatSend=$('studio-compose-send');
  assert(chatSend.textContent.includes('GitHub'),'github-slash-intent-discovered');
  chatSend.click();
  assert(!$('nexus-zen-offer').hidden,'github-discovery-requires-explicit-review');
  assert(providerCalls===2,'no-model-call-from-github-intent');
  $('nexus-zen-offer').querySelector('button').click();
  assert($('studio-connections').open,'github-proposal-opens-connection-review');
  assert($('message').value==='/github list open pull requests','github-draft-retained');
  $('studio-connections-close').click();
  fill('message','بررسی وضعیت انتشار در رندر');
  assert(chatSend.textContent.includes('Render'),'persian-render-intent-discovered');
  chatSend.click();
  assert(!$('nexus-zen-offer').hidden,'render-discovery-requires-review');
  $('nexus-zen-offer').querySelector('button').click();
  assert($('studio-connections').open,'render-proposal-opens-review-dialog');
  assert(providerCalls===2&&searchCalls===1,'connection-routing-has-no-hidden-provider-side-effects');
  $('studio-connections-close').click();
  fill('message','/unknown do something');
  assert(!chatSend.textContent.includes('Review Connections'),'unsupported-command-not-misrouted');

  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__=='__main__':base.main()
