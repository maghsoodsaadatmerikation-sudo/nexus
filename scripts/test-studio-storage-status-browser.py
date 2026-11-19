#!/usr/bin/env python3
"""Real Chromium: visible and read-only storage state matches archive and tab-only work."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nexus_studio_browser", ROOT / "scripts/test-studio-browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)
browser.MIN_CHECKS = 22
browser.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(value,name)=>{if(!value)throw Error(name);checks.push(name)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async(fn,n=350)=>{for(let i=0;i<n;i++){if(fn())return;await new Promise(r=>setTimeout(r,25))}throw Error('wait-timeout')};
 const leave=()=>{const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);return event.defaultPrevented};
 const snapshot=()=>NexusStudioUI.storageStatus();
 const display=()=>[...$('storage-center').querySelectorAll('summary,dt,dd,p')].map(x=>x.textContent).join(' ');
 const password='synthetic password for private test';
 let allow=false,confirmCount=0,network=0;
 window.confirm=()=>{confirmCount++;return allow};
 window.fetch=()=>{network++;throw Error('network-should-not-run')};
 try{
  assert(snapshot().schema==='nexus.studio.storage-status.v1','versioned-storage-schema');
  assert(Object.isFrozen(snapshot())&&Object.isFrozen(snapshot().drafts),'read-only-storage-snapshot');
  assert(snapshot().archive==='tab-only'&&!snapshot().lossRisk,'empty-session-does-not-claim-saved');
  assert($('storage-summary').textContent.includes('No unsaved'),'initial-summary-is-visible');
  assert($('storage-archive-state').textContent.includes('tab-only'),'archive-locked-labelled-as-tab-only');
  assert(!leave(),'no-exit-warning-on-empty-session');

  fill('message','PRIVATE UNSENT CHAT TOKEN');
  assert(snapshot().drafts.chat&&snapshot().lossRisk,'unsent-chat-risk-is-central');
  assert($('storage-chat-state').textContent.includes('Unsent'),'unsent-chat-visible');
  assert($('storage-center').dataset.unsaved==='true','unsaved-state-marked-for-appearance');
  assert(leave(),'central-risk-drives-beforeunload');
  assert(!display().includes('PRIVATE UNSENT CHAT TOKEN'),'status-does-not-leak-chat-content');

  $('lock').click();
  assert(confirmCount===1&&$('message').value==='PRIVATE UNSENT CHAT TOKEN','declined-lock-keeps-message');
  allow=true;$('lock').click();
  assert(!snapshot().lossRisk&&!$('message').value,'approved-lock-clears-chat-and-risk');

  fill('project-title','Synthetic project');
  $('new-project').click();
  assert(snapshot().appliedUnsaved&&snapshot().archive==='tab-only','project-changes-are-tab-only');
  fill('passphrase',password);fill('repeat-passphrase',password);
  $('create-vault').click();await wait(()=>NexusStudioUI.uiStatus().vaultUnlocked);
  assert(snapshot().archive==='applied-unsaved','creating-archive-does-not-save-existing-project');
  $('save').click();await wait(()=>!NexusStudioUI.uiStatus().dirty);
  assert(snapshot().archive==='encrypted-current'&&!snapshot().lossRisk,'explicit-save-updates-applied-state');
  assert($('storage-archive-state').textContent.includes('up to date'),'saved-archive-label-is-truthful');

  fill('document-title','Draft document');$('new-document').click();
  fill('editor','PRIVATE UNSAVED DOCUMENT TEXT');
  assert(snapshot().drafts.writing&&snapshot().appliedUnsaved,'writing-and-applied-delta-are-distinct');
  assert($('storage-writing-state').textContent.includes('Unapplied'),'writing-draft-visible');
  assert(!display().includes('PRIVATE UNSAVED DOCUMENT TEXT'),'status-does-not-leak-document');
  $('save-version').click();
  assert(!snapshot().drafts.writing&&$('storage-writing-state').textContent===EN.storageWritingNone,
    'saving-a-version-refreshes-visible-draft-status-immediately');
  fill('instructions','x'.repeat(2001));$('apply-profile').click();
  assert(snapshot().drafts.preferences&&$('instructions').value.length===2001,
    'rejected-preferences-remain-editable');
  fill('instructions','Applied preferences');$('apply-profile').click();
  assert(!snapshot().drafts.preferences&&$('storage-writing-state').textContent===EN.storageWritingNone,
    'applying-preferences-refreshes-visible-draft-status-immediately');
  $('save').click();
  await wait(()=>!NexusStudioUI.uiStatus().dirty);
  assert(!snapshot().drafts.writing&&!snapshot().lossRisk,'applied-version-and-save-remove-risk');

  for(const id of ['research-query','code','code-input','chart-json','task-plan']){
   fill(id,'PRIVATE TOOL DRAFT');
   assert(snapshot().drafts.tools&&snapshot().lossRisk&&leave()&&
     $('storage-tools-state').textContent===EN.storageToolsDraft,'tool-input-is-protected-'+id);
   assert(!display().includes('PRIVATE TOOL DRAFT'),'storage-hides-tool-input-'+id);
   fill(id,'');
   assert(!snapshot().drafts.tools&&!leave(),'clearing-last-input-removes-warning-'+id);
  }
  $('task-sample').click();
  assert(snapshot().drafts.tools&&$('storage-tools-state').textContent===EN.storageToolsDraft,
    'programmatic-task-sample-refreshes-storage');
  fill('task-plan','');
  $('code-sample').click();
  assert(snapshot().drafts.tools&&$('storage-tools-state').textContent===EN.storageToolsDraft,
    'programmatic-code-sample-refreshes-storage');
  fill('code','');fill('code-input','');

  const dataset=new DataTransfer();
  dataset.items.add(new File(['value\n1\n2'],'private-dataset.csv'));
  $('data-file').files=dataset.files;$('data-file').dispatchEvent(new Event('change',{bubbles:false}));
  assert(snapshot().drafts.tools&&leave()&&$('storage-tools-state').textContent===EN.storageToolsDraft&&
    !display().includes('private-dataset.csv'),'temporary-file-warning-does-not-need-a-bubbling-event');
  const beforeUnlock=confirmCount;allow=false;$('unlock').click();
  assert(confirmCount===beforeUnlock+1&&snapshot().drafts.tools&&snapshot().archive==='encrypted-current',
    'declined-archive-reopen-preserves-temporary-tool-work');
  fill('project-title','Second project');const beforeProject=confirmCount;$('new-project').click();
  assert(confirmCount===beforeProject+1&&NexusStudioUI.snapshot().projects.length===1&&snapshot().drafts.tools,
    'declined-project-change-preserves-temporary-tool-work');
  allow=true;$('new-project').click();
  assert(NexusStudioUI.snapshot().projects.length===2&&!snapshot().drafts.tools,
    'approved-project-change-clears-project-tool-work');
  $('save').click();await wait(()=>!NexusStudioUI.uiStatus().dirty);

  fill('task-plan','PRIVATE TEMPORARY PLAN');
  fill('music-title','PRIVATE MUSIC TITLE');
  assert(snapshot().drafts.music&&!snapshot().drafts.orchestra,'music-draft-appears-independently');
  assert($('storage-media-state').textContent.includes('Temporary'),'creative-work-labelled-tab-only');
  fill('orchestra-prompt','PRIVATE ORCHESTRA PROMPT');
  assert(snapshot().drafts.music&&snapshot().drafts.orchestra,'both-media-tool-drafts-visible');
  assert(!display().includes('PRIVATE MUSIC TITLE')&&!display().includes('PRIVATE ORCHESTRA PROMPT'),
    'storage-center-never-displays-private-media-text');
  const before=confirmCount;allow=false;$('lock').click();
  assert(confirmCount===before+1&&snapshot().lossRisk,'unified-risk-prevents-unapproved-lock');
  assert($('music-title').value==='PRIVATE MUSIC TITLE','declined-lock-keeps-music-draft');
  allow=true;$('lock').click();
  assert(!snapshot().lossRisk&&snapshot().archive==='tab-only','approved-lock-clears-unified-state');
  assert(!$('task-plan').value&&!snapshot().drafts.tools&&$('storage-tools-state').textContent===EN.storageToolsNone,
   'approved-lock-clears-tool-work-and-status');
  assert($('storage-media-state').textContent.includes('No unsaved'),'creative-state-cleared-on-lock');

  $('language').value='fa';$('language').dispatchEvent(new Event('change',{bubbles:true}));
  assert($('storage-center').textContent.includes('وضعیت ذخیره'),'storage-heading-localized-to-persian');
  assert($('storage-archive-state').textContent.includes('آرشیو'),'storage-detail-localized-to-persian');
  assert($('storage-tools-state').textContent===FA.storageToolsNone,'tool-status-localized-to-persian');
  assert(document.documentElement.dir==='rtl','central-status-supports-rtl');
  assert(document.documentElement.scrollWidth<=innerWidth+2,'central-status-mobile-without-overflow');
  assert(network===0,'status-and-lock-never-call-network');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,network_requests:network});
 }catch(e){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e?.message).slice(0,200),checks,network_requests:network});
 }
});
"""
if __name__ == "__main__":
    browser.main()
