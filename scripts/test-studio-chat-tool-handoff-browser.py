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
 let branchPreviews=0,branchWrites=0,planCalls=0,invalidPlan=false,delayPlan=false,releasePlan;
 const branchBase='d'.repeat(40);
 const closeConnection=async()=>{const d=$('studio-connections');const closed=new Promise(r=>d.addEventListener('close',r,{once:true}));$('studio-connections-close').click();await closed};
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  if(String(url).endsWith('/studio-api/status'))return new Response(JSON.stringify({configured:true,model:'synthetic',provider_host:'synthetic.invalid',configuration_id:'a'.repeat(64)}));
  if(String(url).endsWith('/studio-api/respond')){providerCalls++;return new Response(JSON.stringify({text:'Fake response',model:'synthetic',origin:'model',authority:'none'}))}
  if(String(url).endsWith('/studio-api/assistant/plan-preview')){
   planCalls++;
   assert(options.method==='POST'&&JSON.parse(options.body).consent===true,
    'assistant-preview-explicit-consent-on-wire');
   assert(options.headers.authorization==='Bearer '+$('gateway-token').value.trim(),
    'assistant-preview-only-uses-studio-gateway-token');
   if(delayPlan)await new Promise(resolve=>{releasePlan=resolve});
   return Response.json(invalidPlan?{kind:'review_only',steps:[{tool:'shell',instruction:'Run everything'}]}:{
    kind:'review_only',authority:'none',execution:'not_started',
    provider_requests:0,tools_executed:0,steps:[
     {number:1,tool:'research',command:'/research',instruction:'Research fictional study',status:'not_started',requires_separate_user_review:true},
     {number:2,tool:'data',command:'/data',instruction:'analyze CSV data',status:'not_started',requires_separate_user_review:true},
     {number:3,tool:'write',command:'/write',instruction:'draft a report',status:'not_started',requires_separate_user_review:true}
    ]
   });
  }
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
  assert(workflow.querySelectorAll('li button').length===3&&
   workflow.querySelectorAll('li button')[1].disabled,
   'workflow-next-step-locked-until-manual-confirmation');
  assert($('message').value===workflowDraft&&$('request-review').hidden,
   'workflow-preserves-draft-and-does-not-submit-model-message');
  workflow.querySelector('li button').click();
  assert(NexusStudioFocus.active()==='research-card'&&
   $('research-query').value==='fictional study sources',
   'workflow-first-step-opens-research-without-running-it');
  assert(workflow.querySelectorAll('li button')[1].disabled,
   'opening-research-cannot-be-mistaken-for-a-completed-run');
  // Invalid, explicitly approved tool input cannot produce a receipt.
  fill('research-query','');
  $('research-consent').checked=true;$('research-run').click();
  await wait(()=>$('research-run').disabled===false);
  assert(workflow.querySelectorAll('li button')[1].disabled,
   'failed-research-cannot-advance-reviewed-workflow');
  fill('research-query','fictional study sources');
  $('research-consent').checked=true;$('research-run').click();
  await wait(()=>!workflow.querySelectorAll('li button')[1].disabled);
  const workflowSearches=searchCalls-beforeWorkflow.searchCalls;
  assert(workflowSearches>0&&providerCalls===beforeWorkflow.providerCalls,
   'explicit-research-runs-while-model-and-other-tools-remain-idle');
  workflow.querySelectorAll('li button')[1].click();
  assert(workflow.querySelectorAll('li')[0].textContent.includes('local tool completed')&&
   workflow.querySelectorAll('li button')[1].disabled,
   'reviewed-research-result-distinguished-from-manual-report');
  const second=workflow.querySelector('li:nth-child(2) button');
  second.click();
  assert(NexusStudioFocus.active()==='data-card','workflow-second-step-opens-data-review');
  assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
   JSON.stringify({...beforeWorkflow,searchCalls:beforeWorkflow.searchCalls+workflowSearches}),
   'opening-second-workflow-step-never-runs-another-tool');
  assert(workflow.querySelector('li:nth-child(2) button:nth-of-type(2)').disabled,
   'opening-data-panel-does-not-create-an-analysis-receipt');
  file('data-file','invalid-workflow.json','[{"score":1,"score":2}]');
  $('data-run').click();
  await wait(()=>$('data-status').textContent.includes('Analysis unavailable'));
  assert(workflow.querySelector('li:nth-child(2) button:nth-of-type(2)').disabled,
   'failed-duplicate-key-analysis-cannot-advance-workflow');
  const analysisRunsBefore={providerCalls,searchCalls,catalogCalls,connectionActions};
  file('data-file','workflow-analysis.csv','Group,Score\nA,1\nB,2\n');
  $('data-run').click();
  await wait(()=>!workflow.querySelector('li:nth-child(2) button:nth-of-type(2)').disabled);
  assert($('data-status').textContent.includes('Analysis ready')&&
   workflow.textContent.includes('SHA256 ')&&
   JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
     JSON.stringify(analysisRunsBefore),
   'consented-local-data-run-yields-only-a-provenance-bounded-receipt');
  workflow.querySelector('li:nth-child(2) button:nth-of-type(2)').click();
  assert(workflow.querySelector('li:nth-child(2)').textContent.includes('local tool completed')&&
   workflow.querySelectorAll('li').length===3,
   'analysis-result-not-inferred-from-panel-open-or-old-file');
  fill('message',workflowDraft+' modified');
  assert(workflow.hidden,'workflow-edit-revokes-previous-steps');
  fill('message','/plan\n/github list pull requests\n/unknown invalid');
  chatSend.click();
  assert(!workflow.hidden&&workflow.textContent.includes('Unknown workflow tool')&&
   $('nexus-zen-offer').hidden,'invalid-plan-stays-local-and-visible');
  assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
   JSON.stringify({...beforeWorkflow,searchCalls:beforeWorkflow.searchCalls+workflowSearches}),
   'invalid-workflow-has-zero-network-side-effects');
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
  // Natural-language preview requires independent gateway approval.
   NexusStudioFocus.openPanel('conversation-card');
   const planButton=$('studio-assistant-plan-preview');
   const naturalDraft='Research fictional study then analyze CSV data then draft a report';
   fill('research-query',''); // Previous /plan step left a reviewed draft; do not overwrite it implicitly.
   fill('gateway-token','studio-preview-token-01234567890123456789');
   fill('message',naturalDraft);
   assert(!planButton.disabled,'assistant-natural-plan-entry-enabled');
   const beforePlan={providerCalls,searchCalls,catalogCalls,connectionActions};
   planButton.click();
   assert(!workflow.hidden&&workflow.querySelector('pre').textContent===naturalDraft&&
    planCalls===0,'assistant-plan-exact-draft-displayed-before-gateway-request');
   workflow.querySelector('button').click();
   await wait(()=>planCalls===1&&workflow.querySelectorAll('li').length===3);
   assert(workflow.querySelectorAll('li button').length===3&&
    workflow.querySelectorAll('li button')[1].disabled,
    'assistant-plan-gateway-result-requires-separate-tool-review');
   assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
    JSON.stringify(beforePlan),'assistant-preview-does-not-execute-model-or-tools');
   assert($('message').value===naturalDraft,'assistant-preview-preserves-user-draft');
   workflow.querySelector('li button').click();
   assert(NexusStudioFocus.active()==='research-card'&&
    $('research-query').value==='fictional study','assistant-plan-opens-review-surface-only');
   fill('message',naturalDraft+' altered');
   assert(workflow.hidden,'assistant-plan-revoked-on-draft-edit');
   invalidPlan=true;fill('message',naturalDraft);planButton.click();
   workflow.querySelector('button').click();
   await wait(()=>planCalls===2&&workflow.textContent.includes('Preview unavailable'));
   assert(workflow.querySelectorAll('li').length===0,
    'assistant-malformed-gateway-result-cannot-create-workflow');
   invalidPlan=false;
   planButton.click();
   assert(planCalls===2,'assistant-restage-never-sends-automatically');
   delayPlan=true;
   workflow.querySelector('button').click();
   await wait(()=>planCalls===3&&Boolean(releasePlan));
   fill('message','A changed draft cancels the pending plan');
   releasePlan();
   await new Promise(resolve=>setTimeout(resolve,50));
   delayPlan=false;releasePlan=null;
   assert(workflow.hidden,'assistant-inflight-plan-revoked-by-edit');
   assert(JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
    JSON.stringify(beforePlan),'assistant-plan-never-spends-or-executes');
   // The natural-language workflow now has a fully offline route; no gateway
   // token, account, model or network call is required. No tool is auto-run.
   fill('gateway-token','');
   fill('message','Research fictional study then analyze CSV data then draft a report');
   const previousPlanCalls=planCalls,previousNetwork=JSON.stringify(
    {providerCalls,searchCalls,catalogCalls,connectionActions});
   planButton.click();
   const localPlan=$('studio-assistant-local-preview');
   assert(Boolean(localPlan)&&!localPlan.disabled&&workflow.querySelector('pre').textContent===
    $('message').value,'assistant-offline-plan-displays-exact-draft');
   localPlan.click();
   assert(workflow.querySelectorAll('li').length===3&&
    workflow.querySelectorAll('li button')[1].disabled,
    'assistant-offline-plan-requires-manual-result-review');
   assert(planCalls===previousPlanCalls&&JSON.stringify(
    {providerCalls,searchCalls,catalogCalls,connectionActions})===previousNetwork,
    'assistant-offline-plan-makes-zero-network-requests');
   fill('message','Research fictional study then analyze CSV data then draft a report edited');
   assert(workflow.hidden,'assistant-offline-plan-revokes-on-draft-edit');
   // Persian numbered instructions must work without a gateway.
   fill('message','برنامه:\n۱. پژوهش درباره انرژی\n۲. تحلیل داده‌های CSV\n۳. بنویس گزارش');
   planButton.click();$('studio-assistant-local-preview').click();
   assert(workflow.querySelectorAll('li').length===3&&planCalls===previousPlanCalls,
    'assistant-offline-plan-supports-numbered-persian-steps');
   fill('message','Write a report and export document');
   planButton.click();$('studio-assistant-local-preview').click();
   assert(workflow.querySelectorAll('li').length===0&&workflow.textContent.includes(
    'Local plan not recognized'),'assistant-offline-plan-rejects-compound-unordered-actions');
   fill('message','/plan\n/code run python\n/write a report');
   planButton.click();$('studio-assistant-local-preview').click();
   assert(workflow.querySelectorAll('li').length===0,
    'assistant-offline-plan-never-claims-python-execution');
   fill('message','Draft a report then export document as DOCX');
   planButton.click();$('studio-assistant-local-preview').click();
   assert(workflow.querySelectorAll('li').length===2&&
    workflow.querySelectorAll('li')[1].textContent.includes('export document'),
    'assistant-offline-plan-covers-reviewed-document-export');
   assert(planCalls===previousPlanCalls&&JSON.stringify(
    {providerCalls,searchCalls,catalogCalls,connectionActions})===previousNetwork,
    'assistant-offline-plan-parity-does-not-contact-providers');
   fill('message','Continue regular chat after the private plan');
   assert(workflow.hidden,'assistant-offline-plan-clears-on-context-edit');
   // Restore the unrelated connector fixture for the pre-existing Render cases.
   fill('gateway-token','studio-preview-token-01234567890123456789');
   // Music must produce a NEW local score after the reviewed tool opens.
   // A preexisting score, panel visit or an export action never counts.
   fill('message','/plan\n/music original instrumental score\n/write summary');
   chatSend.click();
   assert(workflow.querySelectorAll('li').length===2,'music-workflow-staged');
   assert(workflow.querySelector('li button:nth-of-type(2)').disabled,
    'music-step-not-complete-by-staging');
   workflow.querySelector('li button').click();
   assert(NexusStudioFocus.active()==='music-card'&&
    workflow.querySelector('li button:nth-of-type(2)').disabled,
    'music-panel-open-is-not-a-score-receipt');
   $('music-bars').value='0';
   $('music-bars').dispatchEvent(new Event('change',{bubbles:true}));
   $('music-build').click();
   assert(workflow.querySelector('li button:nth-of-type(2)').disabled,
    'failed-music-composition-does-not-produce-a-receipt');
   $('music-bars').value='32';
   $('music-bars').dispatchEvent(new Event('change',{bubbles:true}));
   $('music-build').click();
   assert(NexusMusicUI.hasScore()&&!NexusMusicUI.hasWav()&&
    !workflow.querySelector('li button:nth-of-type(2)').disabled,
    'fresh-local-score-only-enables-separate-confirmation');
   assert(workflow.textContent.includes('New original score composed locally.')&&
    !workflow.textContent.includes('WAV ready'),
    'music-score-receipt-does-not-claim-wav-or-download');
   workflow.querySelector('li button:nth-of-type(2)').click();
   assert(workflow.querySelector('li').textContent.includes('local tool completed')&&
    workflow.querySelector('li:nth-child(2)').textContent.includes('current'),
    'music-confirmation-advances-only-one-exact-step');
   // A new workflow must not reuse a previous score's temporary receipt.
   fill('message','/plan\n/music new instrumental score\n/write summary');
   chatSend.click();workflow.querySelector('li button').click();
   assert(workflow.querySelector('li button:nth-of-type(2)').disabled,
    'earlier-score-cannot-complete-new-workflow');
   fill('message','No longer reviewing this score');
   assert(workflow.hidden,'music-workflow-edit-revokes-score-review');
   NexusMusicUI.clear();
   assert(!NexusMusicUI.hasScore(),'music-fixture-clears-private-score');
   // Only a NEW local orchestral score can unlock reviewed orchestration.
   fill('message','Orchestrate a score then write a report');
   planButton.click();$('studio-assistant-local-preview').click();
   assert(workflow.querySelectorAll('li').length===2&&
    workflow.querySelector('li button:nth-of-type(2)').disabled,
    'orchestra-natural-language-plan-stages-without-execution');
   workflow.querySelector('li button').click();
   assert(NexusStudioFocus.active()==='orchestra-card'&&
    workflow.querySelector('li button:nth-of-type(2)').disabled,
    'orchestra-panel-opening-is-not-completion');
   fill('orchestra-prompt','opera rap impossible word');
   $('orchestra-parse').click();
   assert($('orchestra-compose').disabled&&
    workflow.querySelector('li button:nth-of-type(2)').disabled,
    'unrecognized-orchestra-prompt-cannot-complete-step');
   fill('orchestra-prompt','hypnotic airy soprano choir harp flute in D minor 120 bpm 4 bars bird chime');
   $('orchestra-parse').click();
   assert(!$('orchestra-compose').disabled&&
    workflow.querySelector('li button:nth-of-type(2)').disabled,
    'parsed-orchestra-plan-is-not-a-finished-score');
   $('orchestra-compose').click();
   assert(NexusOrchestraUI.hasScore()&&!NexusOrchestraUI.hasWav()&&
    !NexusOrchestraUI.hasMixedWav()&&!NexusOrchestraUI.hasOriginalVocal()&&
    !workflow.querySelector('li button:nth-of-type(2)').disabled,
    'new-local-orchestra-score-unlocks-confirmation-without-voice-or-wav');
   assert(workflow.textContent.includes('Synthetic orchestra score built;')&&
    !workflow.textContent.includes('WAV ready'),
    'orchestra-score-receipt-never-claims-vocal-mix-or-rendered-wav');
   workflow.querySelector('li button:nth-of-type(2)').click();
   assert(workflow.querySelector('li').textContent.includes('local tool completed')&&
    workflow.querySelector('li:nth-child(2)').textContent.includes('current'),
    'orchestra-score-receipt-requires-separate-human-confirmation');
   fill('message','/plan\n/orchestra a second score\n/write review');
   chatSend.click();workflow.querySelector('li button').click();
   assert(workflow.querySelector('li button:nth-of-type(2)').disabled,
    'stale-orchestra-score-cannot-complete-new-workflow');
   fill('message','Return to ordinary chat');
   assert(workflow.hidden,'orchestra-workflow-clears-on-chat-edit');
   NexusOrchestraUI.clear();
   assert(!NexusOrchestraUI.hasScore()&&!NexusOrchestraUI.hasOriginalVocal(),
    'orchestra-private-work-revoked');
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
    !$('research-consent').checked&&searchCalls===1+workflowSearches,'search-handoff-preserves-query-and-waits-for-consent');
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
  assert(providerCalls===2&&searchCalls===1+workflowSearches&&connectionActions===1,'connection-routing-has-no-hidden-provider-side-effects');
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
  assert(Object.isFrozen(catalog)&&catalog.length===17&&catalog.every(Object.isFrozen),
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
  assert(!palette.hidden&&palette.querySelector('div').children.length===17,
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
  // A reviewed connector step needs an actual read response, not merely
  // a dialog open, catalog load, or self-reported successful execution.
  NexusStudioFocus.openPanel('conversation-card');
  const receiptPlan='/plan\n/github list pull requests\n/write';
  fill('message',receiptPlan);
  $('studio-compose-send').click();
  const reviewedPlan=$('studio-chat-workflow');
  assert(reviewedPlan.querySelectorAll('li').length===2,'receipt-workflow-created');
  assert(reviewedPlan.querySelector('li button:nth-of-type(2)').disabled,
   'read-not-confirmed-before-open');
  const priorRead=connectionActions;
  reviewedPlan.querySelector('li button').click();
  assert($('studio-connections').open,'receipt-step-opened-connector-review');
  assert(reviewedPlan.querySelector('li button:nth-of-type(2)').disabled&&
   connectionActions===priorRead,'tool-open-is-not-a-read-receipt');
  $('studio-connections-load').click();
  await wait(()=>$('studio-connections').querySelector('select').value==='github.pulls');
  assert(reviewedPlan.querySelector('li button:nth-of-type(2)').disabled,
   'catalog-is-not-a-read-receipt');
  $('studio-connections-read').click();
  await wait(()=>connectionActions===priorRead+1&&!reviewedPlan.querySelector('li button:nth-of-type(2)').disabled);
  assert(reviewedPlan.textContent.includes('Approved read response received'),
   'reviewed-provider-read-unlocks-receipt-bound-step');
  await closeConnection();
  reviewedPlan.querySelector('li button:nth-of-type(2)').click();
  assert(reviewedPlan.querySelector('li').textContent.includes('gateway read returned')&&
   reviewedPlan.querySelectorAll('li').length===2,
   'gateway-read-result-distinguished-from-self-report');
  reviewedPlan.querySelector('li:nth-child(2) button:last-of-type').click();
  assert(reviewedPlan.textContent.includes('gateway reads: 1')&&
   reviewedPlan.textContent.includes('skipped: 1')&&
   !reviewedPlan.textContent.includes('All steps marked done'),
   'skipped-step-not-reported-as-a-successful-execution');
  fill('message',receiptPlan);
  $('studio-compose-send').click();
  reviewedPlan.querySelector('li button:last-of-type').click();
  assert(reviewedPlan.querySelector('li').textContent.includes('skipped by you'),
   'skip-is-not-gateway-receipt');
  fill('message',receiptPlan+' changed');
  assert(reviewedPlan.hidden,'changing-draft-revokes-scoped-receipts');
  assert(connectionActions===priorRead+1,'no-automatic-connector-retries-or-actions');
  // Existing code output is NOT a receipt. Only a fresh consented sandbox
  // run observed after the exact workflow step opened can unlock completion.
  // A previous private-lock test erased the code field, so create an explicit
  // old result before opening this new reviewed workflow.
  $('code-sample').click();
  $('code-consent').checked=true;$('code-run').click();
  await wait(()=>$('code-result').textContent.includes('Local calculation'));
  NexusStudioFocus.openPanel('conversation-card');
  const codePlan='/plan\n/code\n/write';
  fill('message',codePlan);$('studio-compose-send').click();
  const codeWorkflow=$('studio-chat-workflow');
  assert(codeWorkflow.querySelectorAll('li').length===2,
   'code-workflow-created-without-running-code');
  codeWorkflow.querySelector('li button').click();
  assert(NexusStudioFocus.active()==='code-card'&&
   codeWorkflow.querySelector('li button:nth-of-type(2)').disabled,
   'old-code-output-does-not-satisfy-new-reviewed-step');
  const beforeCodeCalls={providerCalls,searchCalls,catalogCalls,connectionActions};
  $('code-consent').checked=true;$('code-run').click();
  await wait(()=>!codeWorkflow.querySelector('li button:nth-of-type(2)').disabled);
  assert(codeWorkflow.textContent.includes('consented local tool run')&&
   JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
   JSON.stringify(beforeCodeCalls),'consented-code-execution-emits-local-only-receipt');
  codeWorkflow.querySelector('li button:nth-of-type(2)').click();
  assert(codeWorkflow.querySelector('li').textContent.includes('local tool completed'),
   'code-step-records-tool-result-not-human-guess');
  codeWorkflow.querySelector('li:nth-child(2) button:last-of-type').click();
  assert(codeWorkflow.textContent.includes('local tool runs: 1')&&
   codeWorkflow.textContent.includes('skipped: 1'),
   'code-result-counted-separately-from-skipped-step');
  fill('message',codePlan);$('studio-compose-send').click();
  codeWorkflow.querySelector('li button').click();
  assert(codeWorkflow.querySelector('li button:nth-of-type(2)').disabled,
   'previous-local-receipt-cannot-be-replayed-in-new-workflow');
  codeWorkflow.querySelector('li button:last-of-type').click();
  assert(codeWorkflow.querySelector('li').textContent.includes('skipped by you'),
   'skipping-local-tool-does-not-count-as-an-execution');
  fill('message','Different draft invalidates local proof');
  assert(codeWorkflow.hidden,'editing-a-draft-revokes-local-proof');
  // Writing requires a NEW, nonempty, changed version accepted by the
  // project state validator. Neither opening the editor nor saving identical
  // text may unlock a new document-writing workflow.
  NexusStudioFocus.openPanel('conversation-card');
  const writePlan='/plan\n/write\n/research manuscript background';
  fill('message',writePlan);$('studio-compose-send').click();
  const writing=$('studio-chat-workflow');
  assert(writing.querySelectorAll('li').length===2&&
   writing.querySelector('li button:nth-of-type(2)').disabled,
   'writing-plan-created-without-an-automatic-document-edit');
  writing.querySelector('li button').click();
  assert(NexusStudioFocus.active()==='canvas-card'&&
   writing.querySelector('li button:nth-of-type(2)').disabled,
   'opening-writing-canvas-does-not-satisfy-save-receipt');
  fill('document-title','Review-only version witness');
  $('new-document').click();
  assert(writing.querySelector('li button:nth-of-type(2)').disabled,
   'document-creation-is-not-a-version-save');
  $('save-version').click();
  assert(writing.querySelector('li button:nth-of-type(2)').disabled,
   'empty-or-rejected-version-is-not-a-new-writing-result');
  fill('editor','A locally written paragraph; not sent to any model or provider.');
  $('save-version').click();
  assert(!writing.querySelector('li button:nth-of-type(2)').disabled&&
   writing.textContent.includes('Save your encrypted archive separately'),
   'new-changed-version-unlocks-session-only-writing-receipt');
  const currentDoc=NexusStudioUI.snapshot().projects
   .find(p=>p.id===NexusStudioUI.selection().projectId).documents.find(d=>d.id===$('documents').value);
  assert(currentDoc.versions.at(-1).text===$('editor').value,
   'writing-receipt-follows-an-actual-applied-document-version');
  // Retrying reopens review; it never saves automatically or reuses proof.
  const versionsBeforeRetry=currentDoc.versions.length;
  writing.querySelector('li button').click();
  assert(writing.querySelector('li button:nth-of-type(2)').disabled&&
   NexusStudioUI.snapshot().projects.find(p=>p.id===NexusStudioUI.selection().projectId)
    .documents.find(d=>d.id===$('documents').value).versions.length===versionsBeforeRetry,
   'retry-review-revokes-old-receipt-without-creating-a-version');
  $('save-version').click();
  assert(writing.querySelector('li button:nth-of-type(2)').disabled,
   'saving-identical-document-text-is-not-a-fresh-writing-receipt');
  fill('editor','Updated manuscript after review and deliberate correction.');
  $('save-version').click();
  assert(!writing.querySelector('li button:nth-of-type(2)').disabled,
   'new-edit-after-retry-produces-new-writing-receipt');
  writing.querySelector('li button:nth-of-type(2)').click();
  assert(writing.querySelector('li').textContent.includes('new document version applied'),
   'writing-step-reports-applied-version-not-provider-persistence');
  writing.querySelector('li:nth-child(2) button:last-of-type').click();
  assert(writing.textContent.includes('document versions (session only): 1')&&
   writing.textContent.includes('skipped: 1'),
   'final-summary-separates-session-writing-from-skips');
  fill('message',writePlan);$('studio-compose-send').click();
  writing.querySelector('li button').click();
  assert(writing.querySelector('li button:nth-of-type(2)').disabled,
   'previous-session-writing-receipt-is-not-replayable-in-new-workflow');
  fill('message','Changed writing task invalidates its old observation');
  assert(writing.hidden,'changed-writing-goal-revokes-unconfirmed-version');
  // Document export is only a user-triggered browser request. Never report
  // arrival on the user's disk. No prior document state or unrelated download
  // may unlock the newly reviewed /export step.
  const exportPlan='/plan\n/export\n/write';
  fill('message',exportPlan);$('studio-compose-send').click();
  const exporting=$('studio-chat-workflow');
  assert(exporting.querySelectorAll('li').length===2&&
   exporting.querySelector('li button:nth-of-type(2)').disabled,
   'document-export-plan-does-not-trigger-a-download');
  exporting.querySelector('li button').click();
  assert(NexusStudioFocus.active()==='canvas-card'&&
   exporting.querySelector('li button:nth-of-type(2)').disabled,
   'opening-export-tool-does-not-prove-delivery');
  const exportCalls={providerCalls,searchCalls,catalogCalls,connectionActions};
  const previousConfirm=window.confirm;
  window.confirm=()=>false;
  $('export-document').click();
  window.confirm=previousConfirm;
  assert(exporting.querySelector('li button:nth-of-type(2)').disabled,
   'declined-plaintext-export-leaves-reviewed-step-incomplete');
  fill('editor',' ');
  $('export-document-word').click();
  assert(exporting.querySelector('li button:nth-of-type(2)').disabled,
   'empty-word-export-cannot-create-a-receipt');
  fill('editor','Updated manuscript after review and deliberate correction.');
  $('language-template').click();
  assert(exporting.querySelector('li button:nth-of-type(2)').disabled,
   'unrelated-template-download-does-not-complete-document-export');
  $('export-document').click();
  assert(!exporting.querySelector('li button:nth-of-type(2)').disabled&&
   exporting.textContent.includes('Browser download requested')&&
   exporting.textContent.includes('saved_version'),
   'explicit-markdown-download-request-emits-only-scoped-receipt');
  const savedVersionCount=NexusStudioUI.snapshot().projects
   .find(p=>p.id===NexusStudioUI.selection().projectId).documents
   .find(d=>d.id===$('documents').value).versions.length;
  exporting.querySelector('li button').click();
  assert(exporting.querySelector('li button:nth-of-type(2)').disabled,
   'reopen-review-revokes-previous-file-request-receipt');
  $('export-document-word').click();
  assert(!exporting.querySelector('li button:nth-of-type(2)').disabled&&
   exporting.textContent.includes('docx')&&
   exporting.textContent.includes('Browser download requested')&&
   JSON.stringify({providerCalls,searchCalls,catalogCalls,connectionActions})===
    JSON.stringify(exportCalls),
   'explicit-docx-request-has-no-implicit-provider-or-research-execution');
  exporting.querySelector('li button:nth-of-type(2)').click();
  assert(exporting.querySelector('li').textContent.includes('delivery unverified'),
   'document-export-checklist-does-not-claim-file-on-disk');
  exporting.querySelector('li:nth-child(2) button:last-of-type').click();
  assert(exporting.textContent.includes('download requests (unverified): 1')&&
   exporting.textContent.includes('skipped: 1'),
   'file-download-request-distinguished-from-version-and-skip');
  assert(NexusStudioUI.snapshot().projects
   .find(p=>p.id===NexusStudioUI.selection().projectId).documents
   .find(d=>d.id===$('documents').value).versions.length===savedVersionCount,
   'exporting-never-mutates-applied-document-versions');
  // Print is a separate browser dialog: PDF is only available if the user
  // chooses Save as PDF and verifies the resulting file. The print-only sheet
  // must never contain Studio chat/history/credentials or executable HTML.
  fill('message',exportPlan);$('studio-compose-send').click();
  exporting.querySelector('li button').click();
  assert(exporting.querySelector('li button:nth-of-type(2)').disabled,
   'old-docx-request-cannot-complete-new-print-workflow');
  const originalPrint=window.print;
  window.print=()=>{throw Error('simulated-print-unavailable')};
  $('export-document-pdf').click();
  assert(exporting.querySelector('li button:nth-of-type(2)').disabled&&
   !$('nexus-print-sheet'),
   'failed-print-call-has-no-receipt-and-removes-private-sheet');
  let printSnapshot=null;
  window.print=()=>{
   const sheet=$('nexus-print-sheet');
   printSnapshot={body:sheet?.querySelector('pre')?.textContent,
    title:sheet?.querySelector('h1')?.textContent,
    style:document.querySelector('style')?.textContent||''};
  };
  $('export-document-pdf').click();
  window.print=originalPrint;
  assert(printSnapshot?.body===$('editor').value&&
   printSnapshot?.title&&printSnapshot.style.includes('body>:not(#nexus-print-sheet){display:none!important}')&&
   !printSnapshot.body.includes('Fake response'),
   'print-dialog-has-a-document-only-private-safe-plain-text-sheet');
  assert(!exporting.querySelector('li button:nth-of-type(2)').disabled&&
   exporting.textContent.includes('Browser print dialog requested'),
   'print-receipt-claims-dialog-only-not-saved-pdf');
  window.dispatchEvent(new Event('afterprint'));
  assert(!$('nexus-print-sheet'),'print-private-sheet-cleared-after-dialog');
  exporting.querySelector('li button:nth-of-type(2)').click();
  exporting.querySelector('li:nth-child(2) button:last-of-type').click();
  assert(exporting.textContent.includes('print dialogs (unverified): 1')&&
   exporting.textContent.includes('download requests (unverified): 0'),
   'pdf-print-dialog-not-mislabeled-as-completed-download');
  fill('message',exportPlan+' modified');
  assert(exporting.hidden,'editing-draft-revokes-file-export-workflow');
  $('lock').click();
  assert(!$('reminder-title').value&&!$('reminder-start').value,'lock-clears-reminder-form');

  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__=='__main__':base.main()
