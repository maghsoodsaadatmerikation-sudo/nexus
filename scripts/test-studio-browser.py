#!/usr/bin/env python3
"""Disposable real Chromium: Studio UX, encryption, branching and consent races."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

MIN_CHECKS=48

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const snapshot=()=>NexusStudioUI.snapshot();
 const current=()=>snapshot().projects.find(p=>p.id===$('projects').value);
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let network=0,posted=null,delayResponse=null,late=false;
 const formattedReply=[
  '# Synthetic answer',
  'Read **carefully** with `sample()` and *context*; ~~obsolete~~ detail.',
  '- First item','- Second item','','- [ ] Open task','- [x] Finished task','','---',
  '3. Third step','4. Fourth step',
  '> An attributed quote',
  '```text','<div>literal code</div>','```',
  '| Term | Meaning |','| --- | --- |','| مثال | Example |',
  '[Source](https://example.org/reference) [Blocked](javascript:blocked) ![image](https://example.org/image.png)',
  '<img src=x onerror="invalid()">'
 ].join('\n');
 window.confirm=()=>true;window.prompt=()=> 'Renamed conversation';
 window.fetch=async(url,options={})=>{network++;if(String(url).endsWith('/status'))return new Response(JSON.stringify({configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'synthetic.invalid'}));posted=JSON.parse(options.body);const response=()=>new Response(JSON.stringify({text:formattedReply,origin:'model',model:'synthetic-model',authority:'none'}));if(late)return new Promise(resolve=>delayResponse=()=>resolve(response()));return response()};
 try{
  assert(document.documentElement.lang==='en'&&document.documentElement.dir==='ltr'&&
   $('language').value==='en'&&$('language').options[0].defaultSelected,'english-first');
  assert(!snapshot().projects.length&&!$('use-memory').checked,'empty-temporary-session-memory-off');
  const offer=$('nexus-zen-offer'),compose=$('studio-compose-send');
  $('nexus-zen-suggestions').querySelector('button').click();
  assert(NexusStudioFocus.active()==='music-card'&&!$('message').value&&snapshot().projects.length===0,
   'empty-chat-chip-opens-tool-in-one-step');
  assert(!$('conversation-card').hidden&&!$('music-card').hidden&&
   document.documentElement.scrollWidth<=innerWidth+2,'opening-a-tool-keeps-chat-visible-without-overflow');
  $('music-card').querySelector('.studio-return-to-message').click();
  assert(NexusStudioFocus.active()==='conversation-card'&&$('music-card').hidden&&
   document.activeElement===$('message'),'return-to-message-closes-only-tool-and-focuses-composer');
  change('studio-compose-mode','model');fill('message','/research Explicit tool');
  assert(compose.textContent==='Review Research','explicit-tool-discoverable-in-model-mode');
  compose.click();
  assert(!offer.hidden&&$('request-review').hidden&&network===0,'explicit-tool-does-not-start-model-review');
  fill('message','Search the web for sleep studies');
  assert(compose.textContent==='Review Research','explicit-natural-search-is-reviewable-in-model-mode');
  compose.click();
  assert(!offer.hidden&&$('request-review').hidden&&network===0,'explicit-natural-search-does-not-send-model-request');
  const exactCode='Run JavaScript:\n```javascript\nreturn 7 * 6;\n```';
  fill('message',exactCode);
  assert(compose.textContent==='Review Code','explicit-fenced-js-is-discovered-as-code');
  compose.click();
  assert(!offer.hidden&&offer.textContent.includes('separate exact-code consent')&&
   !$('code').value&&!$('code-consent').checked&&network===0,
   'code-offer-discloses-sandbox-and-does-not-copy-or-execute');
  offer.querySelector('button').click();
  assert(NexusStudioFocus.active()==='code-card'&&$('code').value==='return 7 * 6;'&&
   !$('code-consent').checked&&$('message').value===exactCode&&network===0,
   'opening-fenced-js-only-fills-empty-local-editor-without-execution');
  $('code-card').querySelector('.studio-return-to-message').click();
  fill('code','return "already here";');
  $('code-consent').checked=true;
  fill('message','/code\n```js\nreturn 2;\n```');
  compose.click();offer.querySelector('button').click();
  assert($('code').value==='return "already here";'&&!$('code-consent').checked&&network===0,
   'code-handoff-never-overwrites-existing-editor');
  $('code-card').querySelector('.studio-return-to-message').click();
  fill('code','');
  fill('message','Run JavaScript:\n```javascript\nreturn 11;\n```');
  compose.click();fill('message','Changed before approval');
  assert(offer.hidden&&!$('code').value&&network===0,
   'editing-a-proposed-code-request-revokes-the-unopened-handoff');
  change('studio-compose-mode','guide');
  fill('message','تحليل فايل CSV');
  assert(compose.textContent==='Review Data analysis','persian-intent-shows-tool-before-submit');
  fill('message','/research Old question');compose.click();
  assert(!offer.hidden,'tool-offer-opens-after-explicit-action');
  fill('message','Revised question');
  assert(offer.hidden&&offer.childElementCount===0,'editing-drops-stale-tool-offer');
  fill('research-query','Preserve existing research draft');
  fill('message','/research Replacement query');compose.click();offer.querySelector('button').click();
  assert(NexusStudioFocus.active()==='research-card'&&$('research-query').value==='Preserve existing research draft'&&
   $('message').value==='/research Replacement query'&&!$('conversation-card').hidden,'tool-navigation-preserves-both-drafts');
  $('research-card').querySelector('.studio-return-to-message').click();
  assert($('research-query').value==='Preserve existing research draft'&&
   $('message').value==='/research Replacement query'&&network===0,'closing-tool-preserves-both-drafts-and-does-not-send');
  fill('research-query','');$('nexus-zen-home').click();
  fill('message','جست‌وجو کن دربارهٔ پژوهش خواب');compose.click();offer.querySelector('button').click();
  assert($('research-query').value==='دربارهٔ پژوهش خواب'&&network===0,
   'natural-language-research-query-prefills-for-review');
  fill('research-query','');$('nexus-zen-home').click();
  fill('message','/research Exact query');compose.click();offer.querySelector('button').click();
  assert($('research-query').value==='Exact query','empty-tool-field-receives-reviewed-query');
  fill('research-query','');$('nexus-zen-home').click();
  fill('message','/research Guide fallback');compose.click();
  assert(offer.querySelectorAll('button').length===3&&
   offer.querySelectorAll('button')[1].textContent.includes('Continue with local guide'),
   'tool-fallback-continues-with-local-guide-action');
  offer.querySelectorAll('button')[1].click();
  if(!current()?.threads?.[0]?.nodes?.length)
   throw Error('guide-fallback-state:'+JSON.stringify({
    status:$('status').textContent,sendDisabled:compose.disabled,
    draftPresent:Boolean($('message').value),draftMatchesExpected:$('message').value==='/research Guide fallback',
    mode:$('studio-compose-mode').value,
    guideDisabled:$('guide').disabled,offerHidden:offer.hidden,
    projectCount:snapshot().projects.length,ui:NexusStudioUI.uiStatus(),
    activePanel:NexusStudioFocus.active()
   }));
  assert(offer.hidden&&current().threads[0].nodes.length===2&&network===0,
   'declining-tool-can-continue-with-local-guide');
  change('studio-compose-mode','model');$('studio-compose-config').click();
  assert($('nexus-zen-more').getAttribute('aria-expanded')==='true'&&$('studio-model-settings').open,
   'model-settings-shortcut-expands-chat-options');
  $('nexus-zen-more').click();
  assert($('nexus-zen-more').getAttribute('aria-expanded')==='false','chat-options-can-collapse-after-shortcut');
  change('studio-compose-mode','guide');

  fill('message','/research Synthetic private offer');compose.click();
  $('nexus-zen-menu').click();fill('nexus-zen-find','Synthetic private search');$('nexus-zen-archived').click();
  window.confirm=()=>false;$('lock').click();
  assert(!offer.hidden&&$('nexus-zen-find').value==='Synthetic private search','declined-lock-keeps-chat-and-search');
  window.confirm=()=>true;$('lock').click();
  assert(offer.hidden&&offer.childElementCount===0&&$('nexus-zen-drawer').hidden&&
   !$('nexus-zen-find').value&&!$('nexus-zen-archived').checked&&!$('nexus-zen-history').childElementCount,
   'accepted-lock-clears-private-chat-overlays');
  fill('project-title','PRIVATE PROJECT');$('new-project').click();$('new-thread').click();
  fill('message','ORIGINAL QUESTION');$('guide').click();
  assert(current().threads[0].nodes.length===2,'local-guide-multi-turn');
  assert($('messages').textContent.includes('not a generative model'),'guide-origin-honest');
  assert(network===0,'local-guide-does-not-connect');
  const firstHead=current().threads[0].head;
  $('messages').querySelector('button').click();fill('message','BRANCHED QUESTION');$('guide').click();
  assert(current().threads[0].nodes.length===4&&$('branch').options.length===2,'editing-preserves-two-branches');
  change('branch',firstHead);assert($('messages').textContent.includes('ORIGINAL QUESTION')&&!$('messages').textContent.includes('BRANCHED QUESTION'),'branch-selector-restores-original');
  fill('message','KEEP THIS DRAFT');window.confirm=()=>false;change('branch',current().threads[0].nodes.at(-1).id);assert($('branch').value===firstHead&&current().threads[0].head===firstHead&&$('message').value==='KEEP THIS DRAFT','declined-branch-change-restores-selection-and-draft');window.confirm=()=>true;fill('message','');
  $('messages').querySelector('button').click();
  assert($('request-review').hidden&&$('storage-center').dataset.unsaved==='true'&&$('branch-notice').textContent===EN.branching,'edit-branch-refreshes-draft-status');
  change('branch',current().threads[0].nodes.at(-1).id);
  assert(!$('message').value&&!$('branch-notice').textContent&&$('storage-chat-state').textContent===EN.storageChatNone,'accepted-branch-switch-clears-draft-before-render');
  change('branch',firstHead);
  $('rename-thread').click();assert(current().threads[0].title==='Renamed conversation','rename-chat');
  fill('search','BRANCHED');assert($('history').children.length===1,'search-includes-other-branches');
  fill('search','');$('archive-thread').click();assert($('history').children.length===0,'archive-hides-thread');
  $('archived').checked=true;$('archived').dispatchEvent(new Event('change'));assert($('history').children.length===1,'include-archived-search');$('archive-thread').click();
  fill('instructions','CUSTOM PREFERENCE');fill('memories','REVIEWED SECRET MEMORY');$('apply-profile').click();
  assert(current().memories[0]==='REVIEWED SECRET MEMORY','explicit-project-memory');
  const transfer=new DataTransfer();transfer.items.add(new File(['The orchard has green trees.\nA source is not a verified fact.'],'notes.txt',{type:'text/plain'}));$('source-file').files=transfer.files;$('source-file').dispatchEvent(new Event('change'));
  await wait(()=>current().sources.length===1);fill('source-query','orchard');$('search-sources').click();assert($('source-results').textContent.includes('notes.txt:1'),'local-source-name-and-line');
  fill('document-title','PRIVATE DOC');$('new-document').click();fill('editor','version one');$('save-version').click();fill('editor','version two');$('save-version').click();assert(current().documents[0].versions.length===2,'append-only-document-versions');
  change('versions',current().documents[0].versions[0].id);assert($('version-diff').textContent.includes('version one')&&$('version-diff').textContent.includes('version two'),'version-diff');$('load-version').click();assert($('editor').value==='version one','load-old-version-into-draft');$('save-version').click();
  const injection='<img src=x onerror=alert(1)>';fill('message',injection);$('guide').click();assert($('messages').textContent.includes(injection)&&!$('messages').querySelector('img'),'untrusted-message-is-inert');
  fill('gateway','https://synthetic.invalid');fill('gateway-token','TRANSIENT ACCESS TOKEN');$('check-model').click();await wait(()=>$('model-status').textContent.includes('synthetic-model'));
  assert($('studio-compose-model-info').hidden&&$('studio-compose-mode').value==='guide',
   'local-guide-is-default-and-no-model-availability-is-implied');
  change('studio-compose-mode','model');
  const available=NexusStudioUI.modelAvailability();
  assert(!$('studio-compose-model-info').hidden&&
   available.checked&&available.configured&&available.model==='synthetic-model'&&
   $('studio-compose-model-state').textContent.includes('synthetic-model')&&
   $('studio-compose-model-state').textContent.includes('not verified')&&network===1,
   'chat-model-choice-shows-only-checked-config-not-fake-live-access');
  assert($('studio-compose-model-check').type==='button',
   'checking-model-settings-is-manual-and-separate-from-billable-model-sends');
  change('studio-compose-mode','guide');
  assert($('studio-compose-model-info').hidden&&network===1,
   'switching-to-local-guide-does-not-contact-provider');
  const studyMode=$('study-mode');
  studyMode.click();fill('message','Fractions');$('guide').click();
  assert($('messages').textContent.includes('Local study guide')&&network===1,'study-guide-is-local');
  fill('message','orchard trees');$('prepare').click();
  const studyReview=JSON.parse($('request-context').textContent);
  assert(studyReview.response_style==='study'&&studyReview.messages[0].content.includes('User-selected Study mode')&&
   !$('consent').checked&&network===1,'study-uses-reviewed-model-context');
  change('studio-compose-mode','model');
  assert($('request-review').hidden&&!$('consent').checked&&
   !NexusStudioUI.uiStatus().pendingReview,'switching-response-mode-revokes-reviewed-request');
  $('prepare').click();assert(!$('request-review').hidden,'request-can-be-reviewed-again-after-mode-change');
  change('studio-compose-mode','guide');
  assert($('request-review').hidden&&!$('consent').checked&&network===1,
   'return-to-local-mode-revokes-model-consent-without-provider-call');
  $('prepare').click();
  studyMode.click();
  assert($('request-review').hidden&&!$('consent').checked,'changing-study-mode-revokes-review');
  assert(!$('decision-mode')&&!$('decision-mode-help'),'decision-guidance-has-no-separate-control');
  fill('message','Should I make music now or wait for feedback?');
  assert(compose.textContent==='Use local guide'&&offer.hidden,'asking-about-a-tool-keeps-the-turn-in-chat');
  compose.click();
  assert($('messages').textContent.includes('reversible next step')&&
   current().threads[0].nodes.at(-1).origin==='guide'&&network===1,'choice-uses-local-judgment-guidance-automatically');
  fill('message','orchard trees');$('prepare').click();
  const chatReview=JSON.parse($('request-context').textContent);
  assert(chatReview.response_style==='standard'&&
   chatReview.messages[0].content.includes('NEXUS response guidance: Handle the request directly')&&
   chatReview.messages.at(-1).content==='orchard trees'&&
   !$('consent').checked&&network===1,'normal-chat-discloses-built-in-model-guidance');
  assert(!$('request-context').textContent.includes('REVIEWED SECRET MEMORY'),'memory-not-sent-by-default');
  $('use-memory').checked=true;$('use-memory').dispatchEvent(new Event('input'));assert($('request-review').hidden,'context-change-invalidates-approval');$('use-sources').checked=true;$('prepare').click();assert($('request-context').textContent.includes('REVIEWED SECRET MEMORY')&&$('request-context').textContent.includes('notes.txt'),'exact-selected-context-visible');
  const count=network;$('send-model').click();assert(network===count,'unapproved-send-does-not-connect');$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();await wait(()=>current().threads[0].nodes.at(-1)?.origin==='model');assert(posted.consent===true&&posted.configuration_id==='a'.repeat(64),'approved-request-binds-configuration');assert(!JSON.stringify(posted).includes('TRANSIENT ACCESS TOKEN'),'gateway-token-excluded-from-context');
  assert(posted.messages[0].content.includes('NEXUS response guidance'),'approved-standard-request-includes-judgment-guidance');
  const formatted=$('messages').querySelector('.reply-format');
  assert(formatted.querySelector('h3').textContent==='Synthetic answer'&&formatted.querySelector('p strong').textContent==='carefully'&&
   formatted.querySelector('p code').textContent==='sample()'&&formatted.querySelector('p em').textContent==='context',
   'finished-reply-displays-headings-and-inline-formatting');
  assert(formatted.querySelector('ul').querySelectorAll(':scope > li').length===2&&formatted.querySelector('ol').start===3&&
   formatted.querySelector('blockquote').textContent==='An attributed quote','finished-reply-displays-lists-and-quotations');
  assert(formatted.querySelector('p del')?.textContent==='obsolete'&&
   formatted.querySelectorAll('ul input[type="checkbox"]').length===2&&
   [...formatted.querySelectorAll('ul input[type="checkbox"]')].every(node=>node.disabled)&&
   !formatted.querySelectorAll('ul input[type="checkbox"]')[0].checked&&
   formatted.querySelectorAll('ul input[type="checkbox"]')[1].checked&&
   formatted.querySelector('hr')&&!formatted.querySelector('script'),
   'finished-reply-uses-inert-tasks-strike-and-thematic-break');
  assert(formatted.querySelector('pre code')?.dataset.language==='text'&&
   formatted.querySelector('button.reply-copy-code')?.type==='button',
   'code-action-is-visible-only-in-live-reply');
  assert(formatted.querySelector('pre code').textContent==='<div>literal code</div>'&&
   formatted.querySelector('table tbody td').textContent==='مثال','code-and-table-render-as-structured-text');
  const links=formatted.querySelectorAll('a');
  assert(links.length===1&&links[0].href==='https://example.org/reference'&&links[0].rel.includes('noreferrer')&&
   !formatted.querySelector('img')&&formatted.textContent.includes('[Blocked](javascript:blocked)'),
   'plain-html-and-unsafe-links-cannot-become-interactive-elements');
  let copiedReply;
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{copiedReply=text}}});
  formatted.querySelector('.reply-copy-code').click();
  await wait(()=>copiedReply==='<div>literal code</div>');
  assert(formatted.querySelector('.reply-copy-code').textContent==='Copied',
   'copy-code-is-explicit-and-preserves-literal-snippet');
  copiedReply=undefined;
  formatted.parentElement.querySelector('[data-chat-copy]').click();
  await wait(()=>copiedReply!==undefined);
  assert(copiedReply===formattedReply&&current().threads[0].nodes.at(-1).text===formattedReply,'copy-and-history-keep-original-markdown');
  const exportAnswer=formatted.parentElement.querySelector('[data-chat-export]');
  const previousCreate=URL.createObjectURL,previousClick=HTMLAnchorElement.prototype.click,previousConfirm=window.confirm;
  const beforeExport=JSON.stringify(snapshot()),beforeExportCalls=network;
  let exportedBlob,exportName;
  URL.createObjectURL=blob=>{exportedBlob=blob;return previousCreate.call(URL,blob)};
  HTMLAnchorElement.prototype.click=function(){exportName=this.download};
  try{
   window.confirm=()=>false;exportAnswer.click();
   assert(!exportedBlob&&!exportName,'declining-export-does-not-produce-a-file');
   window.confirm=()=>true;exportAnswer.click();
  }finally{
   URL.createObjectURL=previousCreate;HTMLAnchorElement.prototype.click=previousClick;window.confirm=previousConfirm;
  }
  assert(exportName==='nexus-answer.html'&&exportedBlob.type.startsWith('text/html'),'answer-exports-as-portable-html');
  const exportedHtml=await exportedBlob.text();
  const exported=new DOMParser().parseFromString(exportedHtml,'text/html');
  assert(exported.documentElement.lang==='en'&&exported.querySelector('main h3')?.textContent==='Synthetic answer'&&
   exported.querySelector('table td')?.textContent==='مثال'&&exported.querySelector('pre code')?.textContent==='<div>literal code</div>',
   'standalone-answer-keeps-structured-markdown-and-unicode');
  assert(!exported.querySelector('.reply-copy-code')&&
   exported.querySelectorAll('ul input[type="checkbox"]:disabled').length===2&&
   exported.querySelector('hr')&&exported.querySelector('del')?.textContent==='obsolete',
   'offline-export-retains-readable-structure-without-clipboard-controls');
  assert(!exported.querySelector('script,img,iframe,base,link,form')&&exported.querySelectorAll('a').length===1&&
   exported.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("default-src 'none'"),
   'exported-html-keeps-unsupported-markup-inert');
  assert(!exportedHtml.includes('orchard trees')&&!exportedHtml.includes('REVIEWED SECRET MEMORY')&&
   !exportedHtml.includes('TRANSIENT ACCESS TOKEN')&&JSON.stringify(snapshot())===beforeExport&&network===beforeExportCalls,
   'answer-export-excludes-conversation-context-and-stays-local');
  let branchBlob,branchName;
  URL.createObjectURL=blob=>{branchBlob=blob;return previousCreate.call(URL,blob)};
  HTMLAnchorElement.prototype.click=function(){branchName=this.download};
  try{
   window.confirm=()=>false;$('export-thread-html').click();
   assert(!branchBlob,'declining-full-conversation-export-does-not-download');
   window.confirm=()=>true;$('export-thread-html').click();
  }finally{
   URL.createObjectURL=previousCreate;HTMLAnchorElement.prototype.click=previousClick;window.confirm=previousConfirm;
  }
  const branchHtml=await branchBlob.text(),branchDoc=new DOMParser().parseFromString(branchHtml,'text/html');
  assert(branchName==='nexus-conversation.html'&&branchDoc.querySelectorAll('main > section').length===NexusStudio.path(current().threads[0]).length&&
   branchDoc.querySelector('main h3').textContent==='Synthetic answer'&&branchDoc.body.textContent.includes('orchard trees'),
   'conversation-html-preserves-active-turns-and-answer-formatting');
  assert(!branchHtml.includes('BRANCHED QUESTION')&&!branchHtml.includes('REVIEWED SECRET MEMORY')&&
   !branchHtml.includes('TRANSIENT ACCESS TOKEN')&&!branchDoc.querySelector('script,img,iframe,form')&&network===beforeExportCalls,
   'conversation-html-excludes-other-branches-and-context-stays-local');
  const wordButton=formatted.parentElement.querySelector('[data-chat-word]');
  const canvasEditor=$('editor'),originalCanvasText=canvasEditor.value;
  let answerWord,canvasWord,wordName;
  HTMLAnchorElement.prototype.click=function(){wordName=this.download};
  try{
   URL.createObjectURL=blob=>{answerWord=blob;return previousCreate.call(URL,blob)};
   window.confirm=()=>false;wordButton.click();
   assert(!answerWord,'declining-word-download-produces-no-file');
   window.confirm=()=>true;wordButton.click();
   assert(wordName==='nexus-answer.docx'&&answerWord.type==='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'answer-downloads-as-editable-word');
   URL.createObjectURL=blob=>{canvasWord=blob;return previousCreate.call(URL,blob)};
   canvasEditor.value='پیش‌نویس\n\n<draft> &\tfinal';
   $('export-document-word').click();
   assert(wordName==='nexus-document.docx'&&canvasWord,'canvas-downloads-as-editable-word');
  }finally{
   canvasEditor.value=originalCanvasText;
   URL.createObjectURL=previousCreate;HTMLAnchorElement.prototype.click=previousClick;window.confirm=previousConfirm;
  }
  assert((await NexusOfficeZip.readDocx(answerWord))==='NEXUS answer\n'+formattedReply.trim(),
   'word-answer-roundtrip-preserves-answer-only-including-code-and-persian');
  assert((await NexusOfficeZip.readDocx(canvasWord))==='PRIVATE DOC\nپیش‌نویس\n\n<draft> &\tfinal'&&
   JSON.stringify(snapshot())===beforeExport&&network===beforeExportCalls,
   'word-canvas-includes-unsaved-text-and-stays-local');
  const spoken=[];
  let pauses=0,resumes=0,cancellations=0,paused=false;
  const localEnglish={name:'Local English',lang:'en-US',localService:true};
  const localPersian={name:'Local Persian',lang:'fa-IR',localService:true};
  const remoteVoice={name:'Cloud voice',lang:'en-GB',localService:false};
  let voices=[remoteVoice,localPersian,localEnglish];
  Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{
   getVoices:()=>voices, speak:utterance=>spoken.push(utterance),
   pause(){paused=true;pauses++},resume(){paused=false;resumes++},
   cancel(){cancellations++},get paused(){return paused}
  }});
  Object.defineProperty(window,'SpeechSynthesisUtterance',{configurable:true,value:class{constructor(text){this.text=text}}});
  const speak=formatted.parentElement.querySelector('[data-chat-speak]');
  const playback=$('studio-playback'),playPause=$('studio-playback-pause'),voiceChoice=$('studio-playback-voice');
  speak.click();
  assert(!playback.hidden&&spoken[0].voice===localEnglish&&voiceChoice.options.length===2&&
   spoken[0].text.includes('Synthetic answer')&&!spoken[0].text.includes('**carefully**'),'playback-uses-local-voice-and-readable-answer-text');
  playPause.click();assert(pauses===1&&playPause.textContent==='Resume','pause-keeps-playback-controls');
  playPause.click();assert(resumes===1&&playPause.textContent==='Pause','resume-continues-the-current-answer');
  const oldVoice=spoken[0];
  change('studio-playback-voice','0');
  assert(spoken.at(-1).voice===localPersian&&spoken.at(-1).text===oldVoice.text,'changing-local-voice-restarts-answer');
  const beforeLateVoice=spoken.length;oldVoice.onend();
  assert(spoken.length===beforeLateVoice,'abandoned-utterance-does-not-queue-more-audio');
  $('studio-playback-stop').click();
  assert(playback.hidden&&document.activeElement===speak,'stop-restores-focus-to-the-answer');
  voices=[remoteVoice];speak.click();
  assert(!playback.hidden&&spoken.length===beforeLateVoice&&$('studio-playback-status').textContent.includes('No local'),
   'remote-only-browser-shows-unavailable-without-starting-audio');
  $('studio-playback-stop').click();voices=[remoteVoice,localPersian,localEnglish];
  const longSpeech='الف'+'🌙'.repeat(3500);
  const chunkStart=spoken.length;
  NexusSpeechPlayback.start(longSpeech);
  for(let i=0;i<100&&!playPause.disabled;i++)spoken.at(-1).onend();
  const chunks=spoken.slice(chunkStart);
  assert(playPause.disabled&&chunks.map(chunk=>chunk.text).join('')===longSpeech&&
   chunks.every(chunk=>chunk.text.length<=240&&!/[\uD800-\uDBFF]$/.test(chunk.text)),
   'chunked-playback-reads-beyond-old-limit-without-splitting-surrogates');
  $('studio-playback-stop').click();
  assert(JSON.stringify(snapshot())===beforeExport&&network===beforeExportCalls,'playback-leaves-archive-and-network-untouched');
  const regenerate=$('regenerate');
  assert(!regenerate.hidden&&!regenerate.disabled&&getComputedStyle(regenerate).display!=='none','retry-is-visible-in-chat');
  fill('message','Keep this unsent follow-up');
  regenerate.click();
  assert(regenerate.disabled&&$('request-review').hidden&&$('message').value==='Keep this unsent follow-up','retry-protects-unsent-draft');
  fill('message','');
  regenerate.click();assert(!$('request-review').hidden,'regenerate-prepares-another-branch');$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click();await wait(()=>$('request-review').hidden);assert($('branch').options.length>=3,'regenerate-keeps-original-answer');
  late=true;fill('message','STALE REQUEST');$('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));const before=current().threads[0].nodes.length;$('send-model').click();await wait(()=>delayResponse!==null);$('stop').click();delayResponse();await sleep(50);assert(current().threads[0].nodes.length===before,'stop-discards-late-model-answer');fill('message','');late=false;
  const historyButton=title=>[...$('history').children].find(b=>b.textContent.endsWith(' · '+title));
  const canvasId=$('documents').value;
  fill('editor','Preserve the current canvas draft');
  fill('task-plan','Preserve the project task draft');
  let confirmations=0;
  window.confirm=()=>{confirmations++;return false};
  $('new-thread').click();
  assert(confirmations===0&&current().threads.length===2&&$('editor').value==='Preserve the current canvas draft',
   'new-chat-keeps-unrelated-draft-without-confirmation');
  assert(!$('use-memory').checked&&!$('use-sources').checked,'new-chat-resets-context-opt-ins');
  fill('message','Keep the composer draft on the active chat');
  $('use-memory').checked=true;$('use-sources').checked=true;
  const draftFiles=new DataTransfer();draftFiles.items.add(new File(['draft text'],'switch.txt'));
  $('chat-file').files=draftFiles.files;$('chat-file').dispatchEvent(new Event('change'));
  await wait(()=>$('chat-attachment-tray').textContent.includes('switch.txt'));
  $('prepare').click();$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));
  historyButton(EN.newChat).click();
  assert(confirmations===0&&!$('request-review').hidden&&$('consent').checked,'reselecting-active-chat-keeps-draft-and-review');
  historyButton('Renamed conversation').click();
  assert(confirmations===1&&!$('request-review').hidden&&$('message').value.includes('Keep the composer'),
   'declining-chat-switch-keeps-review-and-draft');
  window.confirm=()=>{confirmations++;return true};
  historyButton('Renamed conversation').click();
  assert(confirmations===2&&$('request-review').hidden&&!$('request-context').textContent&&!$('consent').checked&&
   !$('message').value&&!$('use-memory').checked&&!$('use-sources').checked&&$('chat-attachment-tray').textContent.includes(EN.chatNoFiles),
   'accepted-chat-switch-clears-only-chat-context-and-review');
  assert($('documents').value===canvasId&&$('editor').value==='Preserve the current canvas draft'&&
   $('task-plan').value==='Preserve the project task draft'&&$('source-results').textContent.includes('notes.txt:1'),
   'same-project-chat-switch-keeps-canvas-tools-and-search-results');
  fill('instructions','Preserve unapplied project preferences');
  confirmations=0;window.confirm=()=>{confirmations++;return false};
  historyButton(EN.newChat).click();historyButton('Renamed conversation').click();
  assert(confirmations===0&&$('instructions').value==='Preserve unapplied project preferences'&&NexusStudioUI.storageStatus().drafts.preferences,
   'same-project-history-preserves-unapplied-preferences-without-warning');
  window.confirm=()=>true;$('apply-profile').click();$('save-version').click();
  fill('passphrase','long private password 123');fill('repeat-passphrase','long private password 123');$('create-vault').click();await wait(()=>!$('save').disabled);$('save').click();await wait(()=>$('status').textContent.includes('session saved'));
  const store=new NexusStudio.IndexedStore(),raw=await store.read();assert(raw&&!raw.includes('PRIVATE PROJECT')&&!raw.includes('REVIEWED SECRET MEMORY'),'indexeddb-contains-ciphertext-only');assert(!raw.includes('TRANSIENT ACCESS TOKEN'),'credentials-not-in-encrypted-state');
  fill('editor','UNSAVED CANVAS');fill('instructions','CHANGED PREFERENCE');$('apply-profile').click();$('save').click();assert($('status').textContent.includes('save document versions'),'profile-apply-does-not-hide-canvas-draft');$('save-version').click();$('save').click();await wait(()=>$('status').textContent.includes('session saved'));
  const projectId=current().id;$('lock').click();assert(snapshot().projects.length===0&&$('gateway-token').value===''&&$('editor').value==='','lock-clears-working-data-and-credential');
  fill('passphrase','wrong password 123');$('unlock').click();await wait(()=>$('status').textContent.includes('Operation failed'));assert(snapshot().projects.length===0,'wrong-password-does-not-open');
  fill('passphrase','long private password 123');$('unlock').click();await wait(()=>snapshot().projects.length===1);assert(current().id===projectId&&current().documents[0].versions.at(-1).text==='UNSAVED CANVAS','encrypted-reopen-restores-chats-memory-and-canvas');
  const unchangedDraftState=JSON.stringify(snapshot());fill('message','UNSENT PRIVATE DRAFT');fill('passphrase','long private password 123');window.confirm=()=>false;$('unlock').click();await sleep(30);assert($('message').value==='UNSENT PRIVATE DRAFT'&&JSON.stringify(snapshot())===unchangedDraftState&&$('passphrase').value==='long private password 123','unlock-requires-confirmation-for-unsent-draft');window.confirm=()=>true;fill('message','');fill('passphrase','');
  const oldId=current().id;fill('project-title','SECOND PROJECT');$('new-project').click();$('new-thread').click();assert(current().id!==oldId&&current().memories.length===0&&!$('use-memory').checked,'new-project-isolates-memory-and-context');
  fill('task-plan','Second project only');
  fill('instructions','Unapplied second-project preferences');
  const secondId=current().id;
  window.confirm=()=>false;historyButton('Renamed conversation').click();
  assert(current().id===secondId&&$('task-plan').value==='Second project only','declined-cross-project-history-keeps-current-work');
  window.confirm=()=>true;historyButton('Renamed conversation').click();
  assert(current().id===oldId&&!$('task-plan').value&&$('instructions').value==='CHANGED PREFERENCE',
   'accepted-cross-project-history-clears-project-scoped-work');
  change('language','fa');assert(document.documentElement.dir==='rtl'&&$('guide').textContent.includes('محلی'),'persian-rtl-interface');
  const unchanged=JSON.stringify(snapshot());
  const labels={};document.querySelectorAll('[data-t]').forEach(n=>labels[n.dataset.t]=n.textContent);
  // The template includes status/action labels not currently rendered in the page.
  Object.assign(labels,EN);
  const languageTransfer=new DataTransfer();languageTransfer.items.add(new File([JSON.stringify({schema:'nexus.studio.locale.v1',code:'es',dir:'ltr',messages:{...labels,conversation:'Conversación'}})],'spanish-labels.json',{type:'application/json'}));$('language-file').files=languageTransfer.files;$('language-file').dispatchEvent(new Event('change'));
  await wait(()=>document.documentElement.lang==='es');assert($('conversation-card').textContent.includes('Conversación'),'complete-local-language-pack');assert(JSON.stringify(snapshot())===unchanged,'language-import-does-not-touch-projects');
  const nativeBuffer=File.prototype.arrayBuffer;let rejectFile;File.prototype.arrayBuffer=()=>new Promise((_,reject)=>rejectFile=reject);const pendingFile=new DataTransfer();pendingFile.items.add(new File(['pending'],'late.txt'));$('source-file').files=pendingFile.files;$('source-file').dispatchEvent(new Event('change'));await wait(()=>rejectFile);$('lock').click();const lockedFileStatus=$('status').textContent;rejectFile(Error('late file failure'));await sleep(40);File.prototype.arrayBuffer=nativeBuffer;assert($('status').textContent===lockedFileStatus&&snapshot().projects.length===0,'late-file-failure-cannot-change-locked-session-status');
  let rejectStatus;window.fetch=()=>new Promise((_,reject)=>rejectStatus=reject);$('check-model').click();await wait(()=>rejectStatus);$('lock').click();const lockedStatus=$('status').textContent;rejectStatus(Error('late network failure'));await sleep(40);assert($('status').textContent===lockedStatus&&snapshot().projects.length===0,'late-failure-cannot-change-locked-session-status');
  const transcript=$('messages');
  for(let i=0;i<3;i++){
   fill('message',('Long local turn '+i+' ').repeat(170));compose.click();
  }
  await wait(()=>transcript.scrollHeight>transcript.clientHeight&&
   transcript.scrollHeight-transcript.scrollTop-transcript.clientHeight<2);
  assert(transcript.scrollTop>0,'new-replies-reveal-latest-turn-in-long-transcript');
  transcript.scrollTop=0;fill('search','Long local turn');await sleep(40);
  assert(transcript.scrollTop===0,'unrelated-search-keeps-reader-position');
  const requests=[];
  window.fetch=async(url,options)=>{
   requests.push({url,options});
   const body=options.body?JSON.parse(options.body):null;
   if(!body)return new Response(JSON.stringify({connections:[{provider:'github',target:'example/nexus',configuration_id:'b'.repeat(64),branch_creation:true,file_commit:true}]}));
   if(url.includes('/github/file-')){
    const result={target:'example/nexus',branch:'nexus/studio-'+body.slug,path:body.path,base_sha:'a'.repeat(40)};
    if(url.endsWith('/file-base'))result.text='Before\n';
    if(url.endsWith('/file-preview'))Object.assign(result,{diff:'-Before\n+'+body.text,review_id:'c'.repeat(64),expires_at:2000000000});
    if(url.endsWith('/file-commit'))result.commit='d'.repeat(40);
    return new Response(JSON.stringify(result));
   }
   if(url.endsWith('/github/branch-preview'))return new Response(JSON.stringify({target:'example/nexus',
    branch:'nexus/studio-'+body.slug,base_sha:'a'.repeat(40),expires_at:2000000000,review_id:'c'.repeat(64)}));
   if(url.endsWith('/github/branch'))return new Response(JSON.stringify({target:'example/nexus',
    branch:'nexus/studio-'+body.slug,base_sha:body.base_sha,status:'created'}));
   return new Response(JSON.stringify({provider:'github',target:'example/nexus',operation:body.operation,
    provenance:'external-untrusted',result:{path:body.path,blob_sha:'a'.repeat(40),text:'Synthetic repository source'}}));
  };
  fill('gateway','https://synthetic-gateway.example');fill('gateway-token','synthetic-operator-token');
  const draft='Keep this draft while reading the repository';fill('message',draft);
  assert($('studio-connections-open').textContent==='Connections','connections-shortcut-keeps-its-label');
  $('studio-connections-open').click();
  assert($('studio-connections').open&&requests.length===0,'opening-connections-does-not-contact-gateway');
  $('studio-connections-load').click();
  const actions=$('studio-connections').querySelector('select');
  await wait(()=>actions.options.length===4);
  actions.value='github.file';actions.dispatchEvent(new Event('change',{bubbles:true}));
  const filePath=$('studio-connection-path');
  filePath.value='README.md';filePath.dispatchEvent(new Event('input',{bubbles:true}));
  assert($('studio-connections').textContent.includes('example/nexus / README.md')&&requests.length===1,
   'connection-target-and-path-visible-before-approved-read');
  $('studio-connections-read').click();
  await wait(()=>!$('studio-connections-use').hidden);
  assert(requests.length===2&&JSON.parse(requests[1].options.body).consent===true&&
   $('studio-connections').textContent.includes('Synthetic repository source'),'reviewed-result-is-visible');
  $('studio-connections-use').click();
  assert(!$('studio-connections').open&&$('message').value===draft&&
   $('chat-attachment-tray').textContent.includes('README.md')&&!NexusStudioUI.uiStatus().pendingReview&&requests.length===2,
   'selected-file-attachment-preserves-draft-and-does-not-call-model');
  await sleep(40);
  $('studio-connections-open').click();$('studio-connections-load').click();
  await wait(()=>actions.options.length===4);
  actions.value='github.branch';actions.dispatchEvent(new Event('change',{bubbles:true}));
  filePath.value='example-change';filePath.dispatchEvent(new Event('input',{bubbles:true}));
  const create=$('studio-connections-create');
  assert(create.hidden,'branch-write-hidden-until-preview');
  $('studio-connections-read').click();await wait(()=>!create.hidden);
  assert(requests.every(x=>!x.url.endsWith('/github/branch'))&&
   $('studio-connections').textContent.includes('main @ '+'a'.repeat(40)),
   'branch-preview-shows-exact-main-with-no-write');
  filePath.value='other-change';filePath.dispatchEvent(new Event('input',{bubbles:true}));
  assert(create.hidden,'changing-branch-name-clears-approval');
  $('studio-connections-read').click();await wait(()=>!create.hidden);
  create.click();await wait(()=>$('studio-connections').textContent.includes('Branch created'));
  const writes=requests.filter(x=>x.url.endsWith('/github/branch')).map(x=>JSON.parse(x.options.body));
  assert(writes.length===1&&writes[0].slug==='other-change'&&writes[0].base_sha==='a'.repeat(40)&&
   writes[0].consent===true&&$('message').value===draft,'separate-approval-creates-only-reviewed-branch');
  actions.value='github.edit';actions.dispatchEvent(new Event('change',{bubbles:true}));
  fill('studio-file-topic','other-change');fill('studio-connection-path','docs/intro.md');
  $('studio-connections-read').click();
  const editor=$('studio-file-editor');
  await wait(()=>!editor.hidden);
  assert(editor.value==='Before\n'&&create.hidden,'file-editor-loads-original-without-write');
  fill('studio-file-editor','After\n');
  window.confirm=()=>false;$('studio-connections-close').click();
  assert($('studio-connections').open&&editor.value==='After\n','declining-close-keeps-source-edit');
  window.confirm=()=>true;
  $('studio-file-preview').click();await wait(()=>!create.hidden);
  assert($('studio-connections').textContent.includes('-Before\n+After')&&
   requests.every(x=>!x.url.endsWith('/github/file-commit')),'review-shows-diff-before-commit');
  fill('studio-file-editor','Final edit\n');
  assert(create.hidden,'editing-text-invalidates-the-reviewed-diff');
  $('studio-file-preview').click();await wait(()=>!create.hidden);
  create.click();await wait(()=>$('studio-connections').textContent.includes('Commit created'));
  const writesToFile=requests.filter(x=>x.url.endsWith('/file-commit')).map(x=>JSON.parse(x.options.body));
  assert(writesToFile.length===1&&writesToFile[0].base_sha==='a'.repeat(40)&&
   writesToFile[0].consent===true&&writesToFile[0].text==='Final edit\n'&&$('message').value===draft,
   'file-commit-only-sends-the-independently-approved-text');
  $('studio-connections-close').click();

  let stream,streamSignal,streamCalls=0;
  const encoder=new TextEncoder();
  const frame=(value)=>stream.enqueue(encoder.encode(JSON.stringify(value)+'\n'));
  const complete={type:'done',origin:'model',model:'synthetic-stream',authority:'none',
   truncated:false,model_slot:'primary',configuration_id:'d'.repeat(64)};
  window.fetch=async(url,options={})=>{
   if(String(url).endsWith('/studio-api/status'))return Response.json({
    configured:true,configuration_id:'d'.repeat(64),model:'synthetic-stream',provider_host:'synthetic.invalid',
    streaming:true,reply_receipt_version:1
   });
   assert(String(url).endsWith('/studio-api/respond-stream'),'streaming-does-not-resend-to-buffered-route');
   assert(JSON.parse(options.body).configuration_id==='d'.repeat(64),'stream-send-is-bound-to-reviewed-configuration');
   streamCalls++;streamSignal=options.signal;
   return new Response(new ReadableStream({start(controller){stream=controller}}),
    {headers:{'content-type':'application/x-ndjson'}});
  };
  fill('gateway','https://streaming.example');fill('gateway-token','STREAM-ACCESS');
  $('check-model').click();await wait(()=>$('model-status').textContent.includes('synthetic-stream'));
  fill('message','Stream a draft step by step');
  const beforeStream=JSON.stringify(snapshot());
  $('prepare').click();
  assert(JSON.parse($('request-context').textContent).response_delivery==='streaming','review-identifies-streaming-delivery');
  $('send-model').click();assert(streamCalls===0,'streaming-still-requires-explicit-approval');
  const sendStream=()=>{$('consent').checked=true;$('consent').dispatchEvent(new Event('change'));$('send-model').click()};
  sendStream();await wait(()=>streamCalls===1&&stream);
  const chunk=encoder.encode(JSON.stringify({type:'delta',text:'پیش‌نویس 🌙 <b>'})+'\n');
  stream.enqueue(chunk.slice(0,-8));stream.enqueue(chunk.slice(-8));
  await wait(()=>$('model-stream-text').textContent.includes('🌙'));
  assert(!$('model-stream-preview').hidden&&!$('model-stream-text').querySelector('b')&&JSON.stringify(snapshot())===beforeStream,
   'partial-answer-is-visible-inert-and-uncommitted');
  frame({type:'delta',text:' finished'});frame(complete);stream.close();
  await wait(()=>$('messages').textContent.includes('پیش‌نویس 🌙 <b> finished'));
  assert($('model-stream-preview').hidden&&!$('model-stream-text').textContent,
   'validated-completion-commits-one-answer-and-clears-preview');

  const committedStream=JSON.stringify(snapshot());
  fill('message','Retryable draft');$('prepare').click();sendStream();await wait(()=>streamCalls===2);
  frame({type:'delta',text:'Only one fragment'});stream.close();
  await wait(()=>$('request-review').hidden);
  assert($('message').value==='Retryable draft'&&$('model-stream-preview').hidden&&JSON.stringify(snapshot())===committedStream&&
   $('status').textContent===EN.gatewayMalformedReply,'interrupted-stream-preserves-draft-and-discards-fragments');
  $('prepare').click();sendStream();await wait(()=>streamCalls===3);
  frame({type:'delta',text:'Stop this preview'});await wait(()=>!$('model-stream-preview').hidden);
  $('stop').click();
  frame({type:'delta',text:'Late content'});frame(complete);stream.close();await sleep(40);
  assert(streamSignal.aborted&&$('model-stream-preview').hidden&&$('message').value==='Retryable draft'&&
   JSON.stringify(snapshot())===committedStream,'stop-aborts-preview-without-saving-late-content');
  // A syntactically completed stream with a wrong route must still be
  // rejected after the last delta and before committing a chat message.
  $('prepare').click();sendStream();await wait(()=>streamCalls===4);
  frame({type:'delta',text:'Spoofed completed answer'});
  frame({...complete,model_slot:'secondary'});stream.close();
  await wait(()=>$('request-review').hidden);
  assert(JSON.stringify(snapshot())===committedStream&&
   $('message').value==='Retryable draft'&&$('model-stream-preview').hidden,
   'completed-stream-wrong-route-is-rejected-before-persisting');

  fill('message','');
  const playbackOrigin=NexusStudioUI.selection();
  $('new-thread').click();
  const playbackDestination=NexusStudioUI.selection();
  assert(playbackDestination.threadId!==playbackOrigin.threadId&&
   NexusStudioUI.openConversation(playbackOrigin.projectId,playbackOrigin.threadId),'setup-playback-navigation');
  $('messages').querySelector('[data-chat-speak]').click();
  assert(!playback.hidden,'playback-starts-in-prior-chat');
  const beforeSwitch=cancellations,abandonedSpeech=spoken.at(-1),beforeSwitchCount=spoken.length;
  assert(NexusStudioUI.openConversation(playbackDestination.projectId,playbackDestination.threadId),'switch-chat-during-playback');
  abandonedSpeech.onend();
  assert(playback.hidden&&cancellations===beforeSwitch+1&&spoken.length===beforeSwitchCount,'chat-switch-stops-playback-and-ignores-late-events');

  $('new-thread').click();fill('message','orchard trees RECALL TEST');$('guide').click();
  const priorThread=NexusStudioUI.selection();
  $('new-thread').click();fill('message','orchard trees');$('prepare').click();
  const plainReview=JSON.parse($('request-context').textContent);
  assert(plainReview.related_chat_passages.length===0,'other-project-chats-are-opt-in');
  $('use-related-chats').checked=true;$('use-related-chats').dispatchEvent(new Event('input'));
  assert($('request-review').hidden,'changing-project-context-invalidates-review');
  $('prepare').click();
  const recallReview=JSON.parse($('request-context').textContent);
  assert(recallReview.related_chat_passages.some(p=>p.thread===priorThread.threadId&&p.turn===1)&&
   recallReview.messages[0].content.includes('orchard trees RECALL TEST')&&!$('consent').checked,
   'matching-user-excerpt-in-exact-request-review');
  fill('message','/temporary');compose.click();
  const isolatedSelection=NexusStudioUI.selection();
  const isolated=current().threads.find(t=>t.id===isolatedSelection.threadId);
  assert(isolated?.temporary&&isolated.isolated&&!$('isolated-chat-note').hidden&&
   !$('message').value&&$('request-review').hidden&&$('use-related-chats').disabled&&$('use-memory').disabled,
   'temporary-chat-command-starts-tab-only-thread-without-project-context');
  fill('message','orchard trees');$('prepare').click();
  const isolatedReview=JSON.parse($('request-context').textContent);
  assert(!JSON.stringify(isolatedReview).includes('orchard trees RECALL TEST')&&
   !JSON.stringify(isolatedReview).includes('CUSTOM PREFERENCE')&&!$('consent').checked,
   'temporary-model-review-excludes-project-content');

  fill('message','');
  $('new-thread').click();
  const audioCount=spoken.length;
  assert(!$('auto-speak').checked,'automatic-playback-stays-off-by-default');
  $('auto-speak').click();
  fill('message','Local test for automatic read aloud');$('message').focus();$('guide').click();
  assert(spoken.length===audioCount+1&&!playback.hidden&&spoken.at(-1).voice.localService&&
   document.activeElement===$('message'),'opt-in-automatic-read-aloud-uses-local-voice-without-taking-focus');
  $('auto-speak').click();
  assert(playback.hidden,'turning-off-auto-speak-stops-playback');
  window.confirm=()=>true;
  fill('project-title','Fresh canvas project');$('new-project').click();$('new-thread').click();
  fill('message','Give me a draft about an orchard');$('guide').click();
  const canvasReply=current().threads[0].nodes.at(-1).text;
  $('messages').querySelector('[data-chat-canvas]').click();
  assert(NexusStudioFocus.active()==='canvas-card'&&!$('conversation-card').hidden&&
   $('editor').value===canvasReply&&document.activeElement===$('editor')&&!current().documents.length,
   'answer-opens-editable-canvas-alongside-chat-without-saving');
  window.confirm=()=>false;
  fill('document-title','First canvas document');$('new-document').click();
  assert($('editor').value===canvasReply&&current().documents[0].versions.length===0,
   'creating-first-document-preserves-answer-draft');
  $('save-version').click();
  assert(current().documents[0].versions[0].text===canvasReply,'draft-saves-as-first-document-version-on-request');
  const beforeCanvasSend=network,headBeforeCanvasSend=NexusStudioUI.selection().head;
  fill('editor','Orchard canvas details still in draft.');
  fill('message','Summarize orchard canvas details');
  $('canvas-chat').click();
  assert(NexusStudioFocus.active()==='conversation-card'&&$('canvas-card').hidden&&
   $('message').value==='Summarize orchard canvas details'&&$('chat-attachment-tray').textContent.includes('First canvas document')&&
   $('editor').value==='Orchard canvas details still in draft.'&&NexusStudioCompose.mode()==='model'&&
   NexusStudioUI.selection().head===headBeforeCanvasSend&&network===beforeCanvasSend&&
   $('request-review').hidden&&current().documents[0].versions.length===1,
   'canvas-draft-returns-to-same-chat-for-one-turn-review-without-sending-or-saving');
  assert(document.documentElement.scrollWidth<=innerWidth+2,'no-horizontal-overflow');

  // Model catalog is discovered explicitly, never inferred from a name or
  // treated as proof of provider access. No real provider is contacted here.
  window.confirm=()=>true;
  $('clear-chat-files').click();$('new-thread').click();
  const beforeMulti=network,slotReply='Reviewed secondary answer',slotId='b'.repeat(64);
  window.fetch=async(url,options={})=>{
   network++;
   if(String(url).endsWith('/status'))return new Response(JSON.stringify({
    configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',
    provider_host:'primary.example',authority:'none',models:[
     {slot:'primary',configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'primary.example'},
     {slot:'secondary',configuration_id:slotId,model:'secondary-model',provider_host:'secondary.example'}
    ]
   }));
   posted=JSON.parse(options.body);
   return new Response(JSON.stringify({
    text:slotReply,origin:'model',model:'secondary-model',authority:'none',truncated:false
   }));
  };
  fill('gateway','https://private-test-multimodel.invalid');
  change('studio-compose-mode','model');
  assert(NexusStudioUI.availableModelOptions().length===0,
   'changing-gateway-invalidates-previous-provider-catalog');
  $('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.availableModelOptions().length===2);
  assert(network===beforeMulti+1&&!$('studio-compose-choice-label').hidden&&
   $('studio-compose-choice').options.length===2&&
   NexusStudioUI.modelAvailability().model==='synthetic-model',
   'model-check-lists-only-two-real-configured-synthetic-slots');
  fill('message','Please provide a reviewed synthetic answer');
  $('prepare').click();assert(!$('request-review').hidden,
   'first-provider-exact-context-review-exists');
  const approvedPrimary=JSON.parse($('request-context').textContent);
  assert(approvedPrimary.model_slot==='primary'&&
   !$('consent').checked,'default-selection-is-primary-without-consent');
  change('studio-compose-choice','secondary');
  assert(NexusStudioUI.modelAvailability().model==='secondary-model'&&
   $('request-review').hidden&&!$('consent').checked&&network===beforeMulti+1,
   'switching-model-revokes-stale-approval-without-provider-call');
  $('prepare').click();
  const exact=JSON.parse($('request-context').textContent);
  assert(exact.model_slot==='secondary'&&exact.model==='secondary-model'&&
   !$('consent').checked,'secondary-exact-context-review-shows-actual-model');
  const proposed=NexusStudioUI.uiStatus();
  assert(proposed.pendingReview,'secondary-review-needs-independent-approval');
  $('consent').click();$('send-model').click();
  await wait(()=>$('request-review').hidden);
  assert(posted.model_slot==='secondary'&&posted.configuration_id===slotId&&
   !JSON.stringify(posted).includes('TRANSIENT ACCESS TOKEN')&&
   $('messages').textContent.includes(slotReply)&&network===beforeMulti+2,
   'selected-secondary-request-uses-only-reviewed-slot-and-config');
  fill('message','Another draft for the primary model');$('prepare').click();
  assert(!$('request-review').hidden,'new-secondary-review-opened');
  change('studio-compose-choice','primary');
  assert($('request-review').hidden&&!$('consent').checked&&
   $('message').value==='Another draft for the primary model'&&
   network===beforeMulti+2,'changing-back-to-primary-preserves-draft-and-revokes-consent');
  assert(document.documentElement.scrollWidth<=innerWidth+2,
   'multi-model-selector-stays-in-viewport');

  // Opt-in operator diagnostics are read-only. They disclose only the local
  // attempt budget, never claim live provider readiness or spend model tokens.
  const localToken='synthetic-studio-operator-token-0123456789';
  let diagnosticRequests=0,forbiddenProviderRequests=0;
  window.fetch=async(url,options={})=>{
   const address=String(url);
   if(address.endsWith('/studio-api/status'))return Response.json({
    configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',
    provider_host:'primary.example',authority:'none',models:[
     {slot:'primary',configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'primary.example'},
     {slot:'secondary',configuration_id:slotId,model:'secondary-model',provider_host:'secondary.example'}
    ]
   });
   if(address.includes('/studio-api/operator-readiness?model_slot=')){
    diagnosticRequests++;
    assert(options.headers?.authorization==='Bearer '+localToken&&
     options.credentials==='omit'&&options.redirect==='error'&&
     options.cache==='no-store','operator-readiness-uses-explicit-token-without-cookies');
    const slot=address.split('model_slot=')[1];
    const secondary=slot==='secondary';
    return Response.json({
     model_slot:slot,model:secondary?'secondary-model':'synthetic-model',
     provider_host:secondary?'secondary.example':'primary.example',
     provider_contact_attempted:false,provider_live_verification:'NOT_RECORDED',
     readiness:secondary?'READY_TO_TEST':'LOCAL_BUDGET_EXHAUSTED',
     local_request_budget:{limit:2,attempted:secondary?0:2,remaining:secondary?2:0}
    });
   }
   forbiddenProviderRequests++;throw Error('unexpected paid provider request');
  };
  fill('gateway-token',localToken);
  change('studio-compose-choice','secondary');
  assert(!NexusStudioUI.modelAvailability().localReadiness,
   'changing-model-clears-previous-diagnostic');
  $('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().localReadiness==='READY_TO_TEST');
  assert(NexusStudioUI.modelAvailability().remainingRequests===2&&
   $('studio-compose-model-state').textContent.includes('2 local attempt(s) remain')&&
   $('studio-compose-model-state').textContent.includes('provider access, billing and quality unverified'),
   'secondary-readiness-shows-local-budget-without-provider-attestation');
  assert(diagnosticRequests===1&&forbiddenProviderRequests===0&&
   !$('studio-compose-model-state').textContent.includes(localToken),
   'readiness-does-not-call-provider-or-render-secret');
  change('studio-compose-choice','primary');
  assert(!NexusStudioUI.modelAvailability().localReadiness,
   'model-switch-invalidates-diagnostic-and-existing-review');
  $('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().localReadiness==='LOCAL_BUDGET_EXHAUSTED');
  assert($('studio-compose-model-state').textContent.includes('Local request budget exhausted')&&
   diagnosticRequests===2&&forbiddenProviderRequests===0,
   'exhausted-operator-budget-is-clear-and-fail-closed');
  fill('gateway-token','rotated-token');
  assert(!NexusStudioUI.modelAvailability().localReadiness,
   'changing-gateway-token-invalidates-readiness');

  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,real_model_tested:false,authority:'none'});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""

def main():
 root=Path(__file__).resolve().parents[1]
 browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
 if not browser:raise RuntimeError('real Chromium required')
 html=(root/'web/studio.html').read_text().replace('</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 reports=[]
 with tempfile.TemporaryDirectory(prefix='nexus-studio-browser-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  for label,size in [('narrow','420,1000'),('wide','1280,1000')]:
   r=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/label),size,'60000','30000'],capture_output=True,text=True,timeout=130)
   if r.returncode:raise RuntimeError('browser-runner-failed-'+r.stderr[-1000:])
   report=json.loads(r.stdout)
   if report.get('status')!='PASS':raise RuntimeError(json.dumps(report))
   if len(report['checks'])<MIN_CHECKS:raise RuntimeError('missing-witness-checks')
   reports.append({'layout':label,**report})
 print(json.dumps({'status':'PASS','reports':reports}))
if __name__=='__main__':main()
