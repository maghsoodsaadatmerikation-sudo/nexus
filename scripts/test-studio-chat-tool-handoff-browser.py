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
 let providerCalls=0,searchCalls=0,catalogCalls=0,connectionActions=0;
 let crossrefCalls=0,rejectCrossref=false;
 let branchEnabled=false,delayRead=false,releaseRead,readSignal;
 let branchPreviews=0,branchWrites=0;
 const branchBase='d'.repeat(40);
 const closeConnection=async()=>{const d=$('studio-connections');const closed=new Promise(r=>d.addEventListener('close',r,{once:true}));$('studio-connections-close').click();await closed};
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  if(String(url).endsWith('/studio-api/status'))return new Response(JSON.stringify({configured:true,model:'synthetic',provider_host:'synthetic.invalid',configuration_id:'a'.repeat(64)}));
  if(String(url).endsWith('/studio-api/respond')){providerCalls++;return new Response(JSON.stringify({text:'Fake response',model:'synthetic',origin:'model',authority:'none'}))}
  if(String(url).endsWith('/studio-api/connections')){
   catalogCalls++;
   return new Response(JSON.stringify({connections:[
    {provider:'github',target:'example/nexus',configuration_id:'a'.repeat(64),branch_creation:branchEnabled},
    {provider:'render',target:'srv-test',configuration_id:'b'.repeat(64)}
   ]}));
  }
  if(String(url).endsWith('/studio-api/connections/read')){
   connectionActions++;
   const requested=JSON.parse(options.body||'{}');
   if(!requested.consent)throw Error('missing-explicit-consent');
   if(delayRead){
    readSignal=options.signal;
    await new Promise(resolve=>{releaseRead=resolve});
    if(requested.path)return Response.json({
     provenance:'external-untrusted',operation:'github.file',provider:'github',
     target:'example/nexus',result:{text:'Delayed private read',blob_sha:'c'.repeat(40)}
    });
   }
   if(requested.operation==='github.pulls')return new Response(JSON.stringify({
    provenance:'external-untrusted',operation:'github.pulls',provider:'github',
    target:'example/nexus',result:[{number:7,title:'UNTRUSTED synthetic pull request',head:'review'}]
   }),{headers:{'content-type':'application/json'}});
   throw Error('simulated-provider-unavailable');
  }
  if(String(url).endsWith('/studio-api/connections/github/branch-preview')){
   branchPreviews++;
   const {slug}=JSON.parse(options.body);
   return Response.json({target:'example/nexus',branch:'nexus/studio-'+slug,
    base_sha:branchBase,review_id:String(branchPreviews).repeat(64),expires_at:1900000000});
  }
  if(String(url).endsWith('/studio-api/connections/github/branch')){
   branchWrites++;
   return new Response(null,{status:409});
  }
  if(String(url).includes('/studio-api/connections/')){connectionActions++;throw Error('unreviewed-provider-call')}
  if(String(url).startsWith('https://en.wikipedia.org/')){searchCalls++;return new Response(JSON.stringify({query:{pages:{42:{pageid:42,title:'Source title',extract:'Unverified live source note from Wikipedia.'}}}}))}
  if(String(url).startsWith('https://api.crossref.org/')){
   crossrefCalls++;
   if(rejectCrossref)return new Response('',{status:503});
   return Response.json({message:{items:[{DOI:'10.1234/source',title:['Bibliographic source'],type:'journal-article'}]}});
  }
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
  const chatSend=$('studio-compose-send');
  const routeCatalog=NexusStudioCompose.catalog();
  const allRoutable=routeCatalog.every(item=>{
   fill('message','/'+item.command+' test');
   return chatSend.textContent.includes(item.en);
  });
  assert(allRoutable,'every-catalog-command-routes-to-its-reviewed-tool');
  fill('message','/github list open pull requests');
  assert(chatSend.textContent.includes('GitHub'),'github-slash-intent-discovered');
  chatSend.click();
  assert(!$('nexus-zen-offer').hidden,'github-discovery-requires-explicit-review');
  assert(providerCalls===2,'no-model-call-from-github-intent');
  $('nexus-zen-offer').querySelector('button').click();
  assert($('studio-connections').open,'github-proposal-opens-connection-review');
  assert($('message').value==='/github list open pull requests','github-draft-retained');
  assert($('studio-connections').textContent.includes('GitHub')&&catalogCalls===0,
   'github-provider-selected-without-implicit-network');
  fill('gateway-token','test-connector-access');
  $('studio-connections-load').click();
  await wait(()=>$('studio-connections').querySelector('select').options.length===2);
  let operations=$('studio-connections').querySelector('select');
  assert(operations.value==='github.pulls','github-appropriate-operation-selected');
  assert([...operations.options].every(x=>x.value.startsWith('github.')),'github-target-isolation');
  assert(catalogCalls===1&&connectionActions===0,'catalog-requires-approval-and-never-executes');
  assert($('studio-connection-receipt').hidden,'catalog-is-not-provider-read');
  $('studio-connections-read').click();
  await wait(()=>!$('studio-connection-receipt').hidden);
  const receipt=$('studio-connection-receipt');
  assert(connectionActions===1&&receipt.textContent.includes('UNTRUSTED synthetic pull request'),
   'approved-github-read-shows-untrusted-data-inline');
  assert($('studio-connections-view-chat').hidden===false,'explicit-view-in-chat-is-available');
  assert(!JSON.stringify(snapshot()).includes('UNTRUSTED synthetic pull request'),
   'provider-data-not-persisted-in-project-state');
  $('studio-connections-view-chat').click();
  await wait(()=>!$('studio-connections').open);
  assert(NexusStudioFocus.active()==='conversation-card'&&!receipt.hidden,
   'result-visible-after-dialog-closes');
  assert($('message').value==='/github list open pull requests','result-does-not-overwrite-chat-draft');
  $('studio-connection-attach').click();
  assert($('chat-attachment-tray').textContent.includes('github.pulls'),
   'reviewed-provider-result-explicitly-staged');
  assert(providerCalls===2,'staging-read-does-not-send-to-model');
  $('clear-chat-files').click();
  assert(!JSON.stringify(snapshot()).includes('UNTRUSTED synthetic pull request'),
   'cleared-connector-result-not-retained');
  // An explicit tool request in AI mode must offer reviewed local/connected
  // work instead of sending instructions to the text-only model by default.
  // Generic questions and writing topics must remain normal chat requests.
  const chooser=$('studio-compose-mode');
  chooser.value='model';chooser.dispatchEvent(new Event('change',{bubbles:true}));
  const beforeExplicitRoute={providerCalls,searchCalls,catalogCalls,connectionActions};
  for(const [request,tool] of [
   ['Open the data analysis tool','Data analysis'],
   ['Analyze this CSV','Data analysis'],
   ['Run JavaScript','Code'],
   ['Remind me to review the notes','Reminders'],
   ['Open GitHub pull requests','GitHub'],
   ['Open the writing canvas','Writing'],
   ['باز کن تحلیل داده','Data analysis'],
  ]){
   fill('message',request);
   assert(chatSend.textContent.includes('Review '+tool),'explicit-ai-mode-'+tool+'-shown');
   chatSend.click();
   const proposed=$('nexus-zen-offer');
   assert(!proposed.hidden&&proposed.textContent.includes('Open '+tool),
    'explicit-ai-mode-'+tool+'-requires-review');
   const dismiss=[...proposed.querySelectorAll('button')].find(b=>b.textContent.includes('Keep typing'));
   assert(Boolean(dismiss),'dismiss-proposal-available');
   dismiss.click();
   assert(proposed.hidden&&$('message').value===request,'dismiss-keeps-unsent-request');
  }
  for(const request of [
   'How do I use GitHub pull requests?',
   'Please write an essay about opening a code editor',
   'What does data analysis mean?',
   'Explain when to remind someone about a deadline'
  ]){
   fill('message',request);
   assert(chatSend.textContent.includes('Review before sending')&&$('nexus-zen-offer').hidden,
    'generic-question-stays-model-chat');
  }
  assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
   JSON.stringify(beforeExplicitRoute),'tool-proposals-do-not-call-provider-or-gateway');
  // Multi-step workflows are explicit temporary checklists, not automatic
  // provider/tool plans. Re-entering a plan never contacts a provider.
  fill('research-query','');
  const workflowDraft='/plan\n/research fictional study sources\n/data\n/write';
  fill('message',workflowDraft);
  assert(chatSend.textContent.includes('Review workflow'),'workflow-chat-command-available');
  const beforeWorkflow={providerCalls,searchCalls,catalogCalls,connectionActions};
  chatSend.click();
  const workflow=$('studio-chat-workflow');
  assert(!workflow.hidden&&workflow.querySelectorAll('li').length===3,
   'workflow-has-three-ordered-review-only-steps');
  assert(workflow.querySelectorAll('li button').length===2&&
   workflow.querySelectorAll('li button')[1].disabled,
   'workflow-next-step-locked-until-manual-confirmation');
  assert($('message').value===workflowDraft&&$('request-review').hidden,
   'workflow-preserves-draft-and-does-not-submit-model-message');
  workflow.querySelector('li button').click();
  assert(NexusStudioFocus.active()==='research-card'&&
   $('research-query').value==='fictional study sources',
   'workflow-first-step-opens-research-without-running-it');
  assert(!workflow.querySelectorAll('li button')[1].disabled,
   'workflow-first-step-now-requires-explicit-human-completion');
  workflow.querySelectorAll('li button')[1].click();
  assert(workflow.querySelectorAll('li')[0].textContent.includes('confirmed by you')&&
   workflow.querySelectorAll('li button')[1].disabled,
   'workflow-does-not-advance-second-step-without-review');
  const second=workflow.querySelector('li:nth-child(2) button');
  second.click();
  assert(NexusStudioFocus.active()==='data-card','workflow-second-step-opens-data-review');
  assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
   JSON.stringify(beforeWorkflow),'workflow-never-starts-provider-or-research-operations');
  fill('message',workflowDraft+' modified');
  assert(workflow.hidden,'workflow-edit-revokes-previous-steps');
  fill('message','/plan\n/github list pull requests\n/unknown invalid');
  chatSend.click();
  assert(!workflow.hidden&&workflow.textContent.includes('Unknown workflow tool')&&
   $('nexus-zen-offer').hidden,'invalid-plan-stays-local-and-visible');
  assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
   JSON.stringify(beforeWorkflow),'invalid-workflow-has-zero-network-side-effects');
  fill('message','/plan\n/github list pull requests\n/research study');
  chatSend.click();
  assert(workflow.querySelectorAll('li').length===2,'valid-plan-can-replace-invalid-plan');
  document.dispatchEvent(new Event('nexus-studio-private-clear'));
  assert(workflow.hidden,'privacy-clear-revokes-transient-workflow');
  fill('message','/plan\n/research study\n/data');
  chatSend.click();
  assert(!workflow.hidden,'workflow-can-be-recreated-after-clear');
  workflow.querySelector(':scope > button').click();
  assert(workflow.hidden&&$('message').value==='/plan\n/research study\n/data',
   'discard-workflow-keeps-unsent-chat-text');
  // A reviewed /plan observes an actual local worker lifecycle without
  // mistaking opening a tool or a human checkmark for verified execution.
  fill('message','/plan\n/code\n/write');
  chatSend.click();
  const receiptWorkflow=$('studio-chat-workflow');
  assert(!receiptWorkflow.textContent.includes('Local UI reported success'),
   'new-plan-has-no-invented-tool-result');
  receiptWorkflow.querySelector('li button').click();
  assert(NexusStudioFocus.active()==='code-card'&&!$('code-consent').checked,
   'workflow-opens-code-review-without-approval');
  fill('code','return 40 + 2;');
  $('code-consent').checked=true;$('code-run').click();
  assert(receiptWorkflow.querySelectorAll('li button')[1].disabled,
   'running-local-action-cannot-be-acknowledged-before-outcome');
  await wait(()=>$('code-result').textContent.includes('42'));
  await wait(()=>receiptWorkflow.textContent.includes('Local UI reported success'));
  assert(receiptWorkflow.textContent.includes('not independent proof'),
   'local-worker-success-is-labelled-tab-observed-not-attested');
  assert(receiptWorkflow.querySelector('li button')&&
   receiptWorkflow.querySelectorAll('li button').length===2,
   'observed-result-does-not-skip-manual-workflow-confirmation');
  receiptWorkflow.querySelectorAll('li button')[1].click();
  const oldCreateURL=URL.createObjectURL,oldAnchorClick=HTMLAnchorElement.prototype.click;
  let reportBlob=null,reportName='';
  URL.createObjectURL=blob=>{reportBlob=blob;return oldCreateURL.call(URL,blob)};
  HTMLAnchorElement.prototype.click=function(){reportName=this.download};
  try{
   receiptWorkflow.querySelector('[data-workflow-report]').click();
   assert(reportName==='nexus-workflow-review.json'&&reportBlob,
    'report-export-requires-explicit-user-action');
   const exported=JSON.parse(await reportBlob.text());
   assert(exported.schema==='nexus.workflow-review.v1'&&exported.authority==='none'&&
    exported.complete===false&&exported.steps[0].command==='code'&&
    exported.steps[0].local_ui_outcome==='succeeded'&&
    exported.steps[0].acknowledged_by_user===true&&
    exported.steps[1].local_ui_outcome===null&&exported.steps[1].acknowledged_by_user===false,
    'report-separates-local-observation-from-human-acknowledgment');
  }finally{
   URL.createObjectURL=oldCreateURL;HTMLAnchorElement.prototype.click=oldAnchorClick;
  }
  fill('message','/plan\n/code\n/write modified');
  assert(receiptWorkflow.hidden,'editing-workflow-invalidates-observed-local-receipts');
  fill('message','/plan\n/code\n/write');
  chatSend.click();receiptWorkflow.querySelector('li button').click();
  fill('code','while (true) {}');
  $('code-consent').checked=true;$('code-run').click();$('code-stop').click();
  assert(receiptWorkflow.textContent.includes('Local execution cancelled')&&
   !receiptWorkflow.textContent.includes('Local UI reported success'),
   'cancellation-records-no-completed-worker-result');
  fill('message','/plan\n/code\n/write changed');
  assert(receiptWorkflow.hidden,'canceled-workflow-receipt-is-cleared-with-draft');
  // The local-guide mode retains broad opt-in natural-language discovery.
  // Explicit slash commands still work in both modes.
  chooser.value='guide';chooser.dispatchEvent(new Event('change',{bubbles:true}));
  for(const [request,query] of [
   ['Search for Persian gardens, including water channels','Persian gardens, including water channels'],
   ['جست‌وجو کن معماری باغ‌های ایرانی','معماری باغ‌های ایرانی'],
   ['Search for Python package documentation','Python package documentation'],
  ]){
   fill('research-query','');
   fill('message',request);chatSend.click();
   assert($('nexus-zen-offer').textContent.includes('Open Research'),'explicit-search-in-chat-offers-research');
   $('nexus-zen-offer').querySelector('button').click();
   assert(NexusStudioFocus.active()==='research-card'&&$('research-query').value===query&&
    !$('research-consent').checked&&searchCalls===1,'search-handoff-preserves-query-and-waits-for-consent');
   NexusStudioFocus.openPanel('conversation-card');
  }
  fill('message','بررسی وضعیت انتشار در رندر');
  assert(chatSend.textContent.includes('Render'),'persian-render-intent-discovered');
  chatSend.click();
  assert(!$('nexus-zen-offer').hidden,'render-discovery-requires-review');
  $('nexus-zen-offer').querySelector('button').click();
  assert($('studio-connections').open,'render-proposal-opens-review-dialog');
  assert(catalogCalls===1,'render-preview-does-not-auto-load-catalog');
  $('studio-connections-load').click();
  await wait(()=>$('studio-connections').querySelector('select').options.length===1)
   .catch(()=>{throw Error('render-catalog-state:'+JSON.stringify({
    options:[...$('studio-connections').querySelector('select').options].map(x=>x.value),
    catalogCalls,connectionActions,dialogOpen:$('studio-connections').open,
    loadDisabled:$('studio-connections-load').disabled,
    hasToken:Boolean($('gateway-token').value),
    status:$('studio-connections').querySelector('[role="status"]')?.textContent
   }))});
  operations=$('studio-connections').querySelector('select');
  assert(operations.value==='render.deploys'&&catalogCalls===2,'render-deployments-preselected');
  assert(providerCalls===2&&searchCalls===1&&connectionActions===1,'connection-routing-has-no-hidden-provider-side-effects');
  $('studio-connections-read').click();
  await wait(()=>$('studio-connection-receipt').textContent.includes('Connection unavailable'));
  assert($('studio-connection-receipt').textContent.includes('Request')===false||
    !$('studio-connection-receipt').textContent.includes('simulated-provider-unavailable'),
   'provider-errors-do-not-expose-raw-exceptions');
  assert($('studio-connection-attach').hidden,'failed-read-not-attachable');
  assert(connectionActions===2,'failure-happens-only-after-explicit-approved-read');
  await closeConnection();
  fill('message','/github create branch');
  chatSend.click();$('nexus-zen-offer').querySelector('button').click();
  assert(catalogCalls===2,'branch-intent-does-not-read-remotely');
  $('studio-connections-load').click();
  await wait(()=>$('studio-connections').querySelector('select').options.length===2);
  operations=$('studio-connections').querySelector('select');
  assert(operations.selectedIndex===-1&&!$('studio-connections-read').offsetParent,
   'unavailable-write-action-never-silently-falls-back-to-read');
  assert(connectionActions===2,'unavailable-branch-not-executed');
  await closeConnection();
  // A single frozen catalog drives quick buttons, slash routing and the
  // opt-in palette. Browsing a tool never requests credentials or executes it.
  const catalog=NexusStudioCompose.catalog();
  assert(Object.isFrozen(catalog)&&catalog.length===16&&catalog.every(Object.isFrozen),
   'capability-catalog-is-read-only-and-complete');
  assert(new Set(catalog.map(x=>x.command)).size===catalog.length,
   'capability-commands-unique');
  assert(catalog.filter(x=>x.kind==='connection-review').map(x=>x.command).join(',')===
   'github,render,connections','connector-routes-identified-without-claiming-authority');
  const networkBefore={catalogCalls,connectionActions,providerCalls,searchCalls};
  fill('message','Keep this unsent draft');
  const toolButton=$('studio-open-capability-directory');
  toolButton.click();
  const palette=$('studio-capability-directory');
  assert(!palette.hidden&&toolButton.getAttribute('aria-expanded')==='true'&&
   $('message').value==='Keep this unsent draft','tools-visible-without-a-slash-command');
  window.confirm=()=>false;
  palette.querySelector('div button').click();
  assert($('message').value==='Keep this unsent draft'&&!palette.hidden,'decline-keeps-existing-draft');
  window.confirm=()=>true;
  palette.querySelector(':scope > button').click();
  assert(palette.hidden&&toolButton.getAttribute('aria-expanded')==='false','closing-tools-updates-trigger');
  fill('message','/tools');
  assert(chatSend.textContent.includes('Capabilities'),'tools-command-discovered');
  chatSend.click();
  assert(!palette.hidden&&palette.querySelector('div').children.length===16,
   'capability-palette-shows-all-reviewable-tools');
  assert(JSON.stringify({catalogCalls,connectionActions,providerCalls,searchCalls})===
   JSON.stringify(networkBefore),'capability-browser-has-no-network-effects');
  const pick=[...palette.querySelectorAll('button')].find(x=>x.textContent.startsWith('/github ·'));
  assert(Boolean(pick),'github-option-shown-with-provider-review');
  pick.click();
  assert(palette.hidden&&$('message').value==='/github ',
   'capability-selection-only-fills-draft');
  assert(catalogCalls===networkBefore.catalogCalls&&connectionActions===networkBefore.connectionActions,
   'capability-selection-never-performs-provider-operation');
  fill('message','/repo list open pull requests');
  assert(chatSend.textContent.includes('GitHub'),'alias-resolved-from-single-catalog');
  fill('message','/help');
  chatSend.click();
  assert(!palette.hidden,'help-alias-opens-capability-directory');
  document.dispatchEvent(new Event('nexus-studio-private-clear'));
  assert(palette.hidden,'private-clear-revokes-capability-directory');
  fill('message','/unknown do something');
  assert(!chatSend.textContent.includes('Review Connections'),'unsupported-command-not-misrouted');
  assert($('studio-connection-receipt').hidden,'private-clear-revokes-provider-receipt');
  branchEnabled=true;
  assert(NexusStudioConnections.openFor({provider:'github',operation:'github.branch'}),'open-branch-review');
  $('studio-connections-load').click();
  await wait(()=>$('studio-connections').querySelector('select').value==='github.branch');
  fill('studio-connection-path','branch-review');
  $('studio-connections-read').click();
  const confirmBranch=$('studio-connections-create');
  await wait(()=>!confirmBranch.hidden&&!confirmBranch.disabled);
  confirmBranch.click();
  await wait(()=>!receipt.hidden);
  assert(branchWrites===1&&confirmBranch.hidden,'branch-conflict-revokes-confirmation');
  confirmBranch.click();
  assert(branchWrites===1,'expired-approval-cannot-be-replayed');
  $('studio-connections-read').click();
  assert(receipt.hidden,'new-review-replaces-previous-receipt');
  await wait(()=>!confirmBranch.hidden&&!confirmBranch.disabled);
  assert(branchPreviews===2,'fresh-branch-review-restores-confirmation');
  await closeConnection();

  const prior=NexusStudioUI.selection();
  fill('message','');
  $('new-thread').click();
  const next=NexusStudioUI.selection();
  assert(prior.projectId===next.projectId&&prior.threadId!==next.threadId,'two-chats-share-a-project');
  assert(NexusStudioUI.openConversation(prior.projectId,prior.threadId),'select-origin-chat');
  assert(NexusStudioConnections.openFor({provider:'github',operation:'github.file'}),'open-file-review');
  $('studio-connections-load').click();
  await wait(()=>$('studio-connections').querySelector('select').value==='github.file');
  fill('studio-connection-path','private-notes.md');
  delayRead=true;
  $('studio-connections-read').click();
  await wait(()=>Boolean(releaseRead));
  const dialog=$('studio-connections');
  assert($('studio-connection-path').disabled&&dialog.querySelector('select').disabled,
   'pending-request-locks-reviewed-operation-and-path');
  assert(NexusStudioUI.openConversation(next.projectId,next.threadId),'change-chat-during-read');
  assert(!dialog.open&&readSignal.aborted,'chat-change-closes-dialog-and-aborts-read');
  releaseRead();
  await new Promise(resolve=>setTimeout(resolve,50));
  assert(receipt.hidden&&!receipt.textContent.includes('Delayed private read')&&
   !dialog.textContent.includes('Delayed private read')&&$('studio-connection-path').value==='',
   'late-connector-response-and-path-stay-out-of-new-chat');

  delayRead=false;
  assert(NexusStudioConnections.openFor({provider:'github',operation:'github.pulls'}),'open-fresh-review');
  $('studio-connections-load').click();
  await wait(()=>dialog.querySelector('select').value==='github.pulls');
  $('studio-connections-read').click();
  await wait(()=>!receipt.hidden);
  document.dispatchEvent(new Event('nexus-studio-private-clear'));
  assert(receipt.hidden&&!dialog.open,'private-clear-revokes-visible-provider-result');

  // Real browser DOM lifecycle, with a deterministic speech recognition double.
  let recognizer=null,starts=0;
  window.SpeechRecognition=class {
   start(){recognizer=this;starts++}
   stop(){this.onend()}
   abort(){this.abortCount=(this.abortCount||0)+1;this.aborted=true}
   emit(text){this.onresult({resultIndex:0,results:[Object.assign([{transcript:text}],{isFinal:true})]})}
  };
  const voice=$('studio-voice-toggle'),voiceStart=$('studio-voice-start'),voicePanel=$('studio-voice-panel');
  const beforeVoice=JSON.stringify(snapshot()),beforeVoiceNetwork=providerCalls;
  fill('message','Unsent');
  voice.click();
  assert(!voicePanel.hidden&&starts===0,'voice-disclosure-never-starts-microphone');
  voiceStart.click();
  assert(starts===1&&recognizer.lang==='en','explicit-voice-opt-in-selects-english');
  recognizer.emit('spoken question');
  assert($('message').value==='Unsent','recognition-buffer-does-not-change-unfinished-draft');
  $('studio-voice-stop').click();
  assert($('message').value==='Unsent spoken question'&&voicePanel.hidden,'final-transcript-appends-to-existing-draft');
  assert(JSON.stringify(snapshot())===beforeVoice&&providerCalls===beforeVoiceNetwork&&$('request-review').hidden,
   'dictation-does-not-send-save-or-authorize-model');

  const language=$('language');
  language.value='fa';language.dispatchEvent(new Event('change',{bubbles:true}));
  await wait(()=>document.documentElement.lang==='fa');
  voice.click();voiceStart.click();
  const abandoned=recognizer;
  assert(starts===2&&abandoned.lang==='fa-IR','farsi-dictation-uses-iranian-persian-locale');
  assert(NexusStudioUI.openConversation(prior.projectId,prior.threadId),'navigate-away-during-dictation');
  abandoned.emit('discarded words');abandoned.onend();
  assert(abandoned.aborted&&voicePanel.hidden&&!$('message').value.includes('discarded words'),
   'changing-chats-aborts-and-discards-late-speech');
  const abortCount=abandoned.abortCount;
  abandoned.onstart?.();
  assert(abandoned.abortCount===abortCount+1,'late-microphone-start-after-chat-change-is-aborted');

  voice.click();voiceStart.click();
  const denied=recognizer;
  denied.onerror({error:'not-allowed'});
  assert(denied.aborted&&!voiceStart.disabled&&!$('message').value,'microphone-refusal-leaves-typing-available');

  voiceStart.click();
  const edited=recognizer;
  fill('message','manual edit');
  edited.emit('late text');edited.onend();
  assert(edited.aborted&&$('message').value==='manual edit','typing-cancels-the-active-recognizer');

  const draft='a'.repeat($('message').maxLength-3);
  fill('message',draft);voice.click();voiceStart.click();
  recognizer.emit('😀more');$('studio-voice-stop').click();
  assert($('message').value===draft+' 😀','dictation-reserves-separator-space-and-preserves-an-emoji');
  const shortDraft=draft+'b';
  fill('message',shortDraft);voice.click();voiceStart.click();
  recognizer.emit('😀');$('studio-voice-stop').click();
  assert($('message').value===shortDraft,'dictation-does-not-insert-a-partial-emoji');

  language.value='en';language.dispatchEvent(new Event('change',{bubbles:true}));
  const researchProvider=$('research-provider');
  researchProvider.value='both';researchProvider.dispatchEvent(new Event('change',{bubbles:true}));
  fill('research-query','combined source query');
  const wikiBefore=searchCalls;
  $('research-run').click();
  assert(searchCalls===wikiBefore&&crossrefCalls===0,'combined-search-requires-explicit-query-consent');
  $('research-consent').click();$('research-run').click();
  await wait(()=>$('research-cards').children.length===2);
  assert(searchCalls===wikiBefore+1&&crossrefCalls===1,'combined-search-calls-each-reviewed-provider-once');
  const picks=$('research-cards').querySelectorAll('input[type="checkbox"]');
  picks[0].click();picks[1].click();
  const briefText=$('research-brief-text').textContent;
  assert(!$('research-brief').hidden&&briefText.includes('wikipedia.org')&&briefText.includes('https://doi.org/10.1234/source')&&
   briefText.includes('bibliographic-metadata-only'),'research-brief-retains-links-and-evidence-types');
  $('research-brief-chat').click();
  assert($('chat-attachment-tray').textContent.includes('Research brief')&&providerCalls===beforeVoiceNetwork&&
   !JSON.stringify(snapshot()).includes('Bibliographic source'),'brief-staged-for-review-without-model-send-or-archive');
  fill('research-query','revised combined source query');
  assert($('research-brief').hidden&&$('research-cards').children.length===0,'query-change-clears-old-brief');
  rejectCrossref=true;$('research-consent').click();$('research-run').click();
  await wait(()=>$('research-status').textContent.includes('Some providers failed'));
  assert($('research-cards').children.length===1&&$('research-status').textContent.includes('crossref'),
   'provider-failure-preserves-other-provider-results');



  $('nexus-zen-home').click();
  fill('message','/remind Review the next mix');
  const reminderState=JSON.stringify(snapshot());
  const beforeReminderCalls=providerCalls;
  $('studio-compose-send').click();
  assert(!$('nexus-zen-offer').hidden&&!$('reminder-title').value&&providerCalls===beforeReminderCalls,
   'reminder-command-suggests-tool-without-exporting');
  $('nexus-zen-offer').querySelector('button').click();
  assert(NexusStudioFocus.active()==='reminders-card'&&$('reminder-title').value==='Review the next mix',
   'reminder-command-prefills-reviewed-title');
  fill('reminder-start','2030-01-04T10:30');
  fill('reminder-repeat','daily');
  fill('reminder-advance','5');
  const originalObjectURL=URL.createObjectURL;
  let reminderBlob;
  URL.createObjectURL=blob=>{reminderBlob=blob;return originalObjectURL(blob)};
  $('reminder-download').click();
  URL.createObjectURL=originalObjectURL;
  const calendarText=await reminderBlob?.text();
  assert(reminderBlob.type.startsWith('text/calendar')&&calendarText.includes('DTSTART:20300104T103000')&&
   calendarText.includes('RRULE:FREQ=DAILY')&&calendarText.includes('TRIGGER:-PT5M'),
   'explicit-download-produces-calendar-event-and-alarm');
  assert(JSON.stringify(snapshot())===reminderState&&providerCalls===beforeReminderCalls,
   'reminder-export-leaves-chat-and-model-untouched');
  $('lock').click();
  assert(!$('reminder-title').value&&!$('reminder-start').value,'lock-clears-reminder-form');

  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__=='__main__':base.main()
