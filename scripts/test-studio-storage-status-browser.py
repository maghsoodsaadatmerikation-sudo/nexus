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
  $('save-version').click();$('save').click();
  await wait(()=>!NexusStudioUI.uiStatus().dirty);
  assert(!snapshot().drafts.writing&&!snapshot().lossRisk,'applied-version-and-save-remove-risk');

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
  assert($('storage-media-state').textContent.includes('No unsaved'),'creative-state-cleared-on-lock');

  $('language').value='fa';$('language').dispatchEvent(new Event('change',{bubbles:true}));
  assert($('storage-center').textContent.includes('وضعیت ذخیره'),'storage-heading-localized-to-persian');
  assert($('storage-archive-state').textContent.includes('آرشیو'),'storage-detail-localized-to-persian');
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
