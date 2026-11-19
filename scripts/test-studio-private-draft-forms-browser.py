#!/usr/bin/env python3
"""Disposable Chromium: private music forms are cleared only after confirmed lock/erase."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nexus_studio_browser", ROOT / "scripts/test-studio-browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)
browser.MIN_CHECKS = 21
browser.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,name)=>{if(!v)throw Error(name);checks.push(name)};
 const wait=async(fn,n=350)=>{for(let i=0;i<n;i++){if(fn())return;await new Promise(r=>setTimeout(r,30))}throw Error('wait-timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const leave=()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented};
 let approved=false,confirms=0,network=0;
 window.confirm=()=>{confirms++;return approved};
 window.fetch=()=>{network++;throw Error('remote-call-forbidden')};
 const original={
  musicTitle:$('music-title').value,
  musicSeed:$('music-seed').value,
  musicMode:$('music-mode').value,
  orchestraPrompt:$('orchestra-prompt').value,
  orchestraOffset:$('orchestra-offset').value,
  orchestraDryGain:$('orchestra-dry-gain').value
 };
 const musicChanged=()=>{$('music-title').value='PRIVATE COMPOSITION ALPHA';
  $('music-seed').value='43210';$('music-mode').value='hijaz'};
 const orchestraChanged=()=>{$('orchestra-prompt').value='PRIVATE ORCHESTRA IDEA BETA';
  $('orchestra-prompt').dispatchEvent(new Event('input',{bubbles:true}));
  $('orchestra-offset').value='450';$('orchestra-dry-gain').value='0.7'};
 const clean=()=>!NexusStudioUI.uiStatus().unsavedLocalMedia&&
  !NexusMusicUI.hasTransientWork()&&!NexusOrchestraUI.hasTransientWork()&&
  $('music-title').value===original.musicTitle&&$('music-seed').value===original.musicSeed&&
  $('music-mode').value===original.musicMode&&
  $('orchestra-prompt').value===original.orchestraPrompt&&
  $('orchestra-offset').value===original.orchestraOffset&&
  $('orchestra-dry-gain').value===original.orchestraDryGain;
 try{
  assert(clean(),'initial-defaults-are-not-unsaved-media');
  assert(!leave(),'initial-tab-has-no-loss-warning');
  musicChanged();
  assert(!NexusMusicUI.hasScore()&&NexusMusicUI.hasTransientWork(),'form-only-composition-counts-as-unsaved');
  assert(NexusStudioUI.uiStatus().unsavedLocalMedia,'music-form-only-included-in-studio-status');
  assert(leave(),'unsaved-title-warns-on-tab-exit');
  $('lock').click();
  assert(confirms===1,'lock-prompts-for-music-form-only');
  assert($('music-title').value==='PRIVATE COMPOSITION ALPHA'&&$('music-seed').value==='43210',
   'refused-lock-preserves-music-form-input');
  approved=true;$('lock').click();
  assert($('music-title').value===original.musicTitle,'approved-lock-clears-private-composition-title');
  assert($('music-seed').value===original.musicSeed&&$('music-mode').value===original.musicMode,
   'approved-lock-resets-music-seeds-and-choices');
  assert(clean()&&!leave(),'approved-lock-is-clean-and-exit-safe');

  approved=false;orchestraChanged();
  assert(!NexusOrchestraUI.hasScore()&&NexusOrchestraUI.hasTransientWork(),
   'orchestra-prompt-only-counts-as-unsaved');
  assert(NexusStudioUI.uiStatus().unsavedLocalMedia&&leave(),
   'unsaved-prompt-warns-even-without-a-score');
  $('lock').click();
  assert($('orchestra-prompt').value==='PRIVATE ORCHESTRA IDEA BETA',
   'refused-lock-keeps-private-orchestra-prompt');
  approved=true;$('lock').click();
  assert($('orchestra-prompt').value===original.orchestraPrompt,
   'approved-lock-restores-original-nonprivate-prompt');
  assert($('orchestra-offset').value===original.orchestraOffset&&
   $('orchestra-dry-gain').value===original.orchestraDryGain,
   'approved-lock-resets-orchestra-mix-choices');
  assert(!$('orchestra-report').textContent&&!$('orchestra-mix-report').textContent,
   'approved-lock-removes-orchestra-report-and-mix-output');
  assert(clean()&&!leave(),'orchestra-lock-exit-is-clean');

  musicChanged();orchestraChanged();
  $('music-build').click();
  assert(NexusMusicUI.hasScore(),'actual-score-added-before-discard');
  approved=false;$('lock').click();
  assert(NexusMusicUI.hasScore()&&
   $('orchestra-prompt').value==='PRIVATE ORCHESTRA IDEA BETA',
   'refused-combined-lock-leaves-both-media-and-prompt');
  approved=true;$('lock').click();
  assert(clean()&&!NexusMusicUI.hasScore(),'approved-combined-lock-clears-score-and-inputs');

  $('passphrase').value='synthetic private passphrase 123';
  $('repeat-passphrase').value='synthetic private passphrase 123';
  $('create-vault').click();
  await wait(()=>NexusStudioUI.uiStatus().vaultUnlocked);
  musicChanged();orchestraChanged();
  $('erase').click();
  await wait(()=>!NexusStudioUI.uiStatus().vaultUnlocked&&!NexusStudioUI.uiStatus().unsavedLocalMedia);
  assert(clean()&&!leave(),'confirmed-archive-erasure-clears-private-music-and-orchestra-forms');
  assert(network===0,'no-network-or-provider-request');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,network_requests:network});
 }catch(e){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e?.message).slice(0,190),checks,network_requests:network});
 }
});
"""
if __name__ == "__main__":
    browser.main()
