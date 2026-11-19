#!/usr/bin/env python3
"""Real Chromium: unsaved local audio must not disappear without discard consent."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nexus_studio_browser", ROOT / "scripts/test-studio-browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)
browser.MIN_CHECKS = 20
browser.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 const wait=async(fn,n=300)=>{for(let i=0;i<n;i++){if(fn())return;await new Promise(r=>setTimeout(r,25))}throw Error('wait-timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const leave=()=>{const ev=new Event('beforeunload',{cancelable:true});window.dispatchEvent(ev);return ev.defaultPrevented};
 let confirms=0,allow=false,network=0;
 window.confirm=()=>{confirms++;return allow};
 window.fetch=()=>{network++;throw Error('unexpected-network')};
 const originalRead=File.prototype.arrayBuffer;
 const bytes=new Uint8Array(44+2205*2),v=new DataView(bytes.buffer);
 const put=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i))};
 put(0,'RIFF');v.setUint32(4,36+2205*2,true);put(8,'WAVE');
 put(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);
 v.setUint16(22,1,true);v.setUint32(24,22050,true);
 v.setUint32(28,44100,true);v.setUint16(32,2,true);v.setUint16(34,16,true);
 put(36,'data');v.setUint32(40,2205*2,true);
 const choose=()=>{
  const transfer=new DataTransfer();
  transfer.items.add(new File([bytes],'selected-voice.wav',{type:'audio/wav'}));
  $('orchestra-dry-file').files=transfer.files;
  $('orchestra-dry-file').dispatchEvent(new Event('change',{bubbles:true}));
 };
 try{
  assert(!NexusStudioUI.uiStatus().unsavedLocalMedia,'initially-no-transient-media');
  assert(!leave(),'empty-studio-does-not-warn-on-exit');
  $('music-build').click();
  assert(NexusMusicUI.hasScore()&&NexusMusicUI.hasTransientWork(),'music-score-is-unsaved-work');
  assert(NexusStudioUI.uiStatus().unsavedLocalMedia,'workspace-status-advertises-unsaved-music');
  assert(leave(),'tab-exit-warns-for-music-draft');
  $('lock').click();
  assert(confirms===1,'music-lock-requests-confirmation');
  assert(NexusMusicUI.hasScore(),'declined-lock-retains-music-score');
  assert(NexusStudioUI.uiStatus().unsavedLocalMedia,'declined-lock-retains-unsaved-status');
  allow=true;$('lock').click();
  assert(!NexusMusicUI.hasScore()&&!NexusStudioUI.uiStatus().unsavedLocalMedia,'approved-lock-clears-music');
  assert(!leave(),'no-exit-warning-after-music-cleared');

  $('orchestra-prompt').value='hypnotic airy soprano choir harp flute in D minor 120 bpm 4 bars bird chime';
  $('orchestra-prompt').dispatchEvent(new Event('input',{bubbles:true}));
  $('orchestra-parse').click();
  assert(NexusOrchestraUI.hasTransientWork(),'reviewed-orchestra-plan-is-transient');
  allow=false;$('lock').click();
  assert(NexusOrchestraUI.hasTransientWork(),'declining-lock-preserves-orchestra-plan');
  allow=true;$('lock').click();
  assert(!NexusOrchestraUI.hasTransientWork(),'accepted-lock-releases-orchestra-plan');

  let settle;
  File.prototype.arrayBuffer=()=>new Promise(resolve=>settle=resolve);
  choose();await wait(()=>typeof settle==='function');
  assert(NexusOrchestraUI.hasTransientWork()&&NexusStudioUI.uiStatus().unsavedLocalMedia,
   'pending-private-import-is-visible-as-unsaved');
  assert(leave(),'tab-exit-warns-during-pending-vocal-import');
  allow=false;$('lock').click();
  assert(NexusOrchestraUI.hasTransientWork(),'declined-lock-keeps-pending-import');
  const stale=settle;allow=true;$('lock').click();
  assert(!NexusOrchestraUI.hasTransientWork(),'accepted-lock-invalidates-pending-import');
  stale(bytes.buffer.slice(0));
  await sleep(120);
  assert(!NexusOrchestraUI.hasOriginalVocal()&&!NexusOrchestraUI.hasTransientWork(),
   'late-import-cannot-revive-cleared-private-vocal');
  assert(!leave(),'no-unsaved-warning-after-lock');
  File.prototype.arrayBuffer=originalRead;

  choose();await wait(()=>NexusOrchestraUI.hasOriginalVocal());
  assert(NexusStudioUI.uiStatus().unsavedLocalMedia,'completed-vocal-import-is-unsaved');
  allow=true;$('lock').click();
  assert(!NexusOrchestraUI.hasOriginalVocal(),'approved-lock-releases-complete-vocal');
  assert(network===0,'no-remote-calls-for-media-consent');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,network_requests:network});
 }catch(e){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e?.message).slice(0,180),checks,network_requests:network});
 }finally{File.prototype.arrayBuffer=originalRead}
});
"""
if __name__ == "__main__":
    browser.main()
