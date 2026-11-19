#!/usr/bin/env python3
"""Real Chromium: lock and archive erasure revoke all private transient tool state."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nexus_studio_browser", ROOT / "scripts/test-studio-browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)
browser.MIN_CHECKS = 14
browser.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 const wait=async(fn,n=450)=>{for(let i=0;i<n;i++){if(fn())return;await new Promise(r=>setTimeout(r,50))}throw Error('wait-timeout')};
 const password='offline synthetic passphrase 123456';
 let network=0;
 window.confirm=()=>true;
 window.fetch=()=>{network++;throw Error('no-network-expected')};
 const bytes=new Uint8Array(44+2205*2),view=new DataView(bytes.buffer);
 const put=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i))};
 put(0,'RIFF');view.setUint32(4,36+2205*2,true);put(8,'WAVE');
 put(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);
 view.setUint16(22,1,true);view.setUint32(24,22050,true);
 view.setUint32(28,44100,true);view.setUint16(32,2,true);view.setUint16(34,16,true);
 put(36,'data');view.setUint32(40,2205*2,true);
 for(let i=0;i<2205;i++)view.setInt16(44+i*2,Math.round(1500*Math.sin(i*.13)),true);
 const loadVoice=()=>{
   const selected=new DataTransfer();
   selected.items.add(new File([bytes],'private-voice.wav',{type:'audio/wav'}));
   $('orchestra-dry-file').files=selected.files;
   $('orchestra-dry-file').dispatchEvent(new Event('change',{bubbles:true}));
 };
 const build=()=>{
   $('music-build').click();
   assert(NexusMusicUI.hasScore(),'music-score-created');
   $('orchestra-prompt').value='hypnotic airy soprano choir harp flute in D minor 120 bpm 4 bars bird chime';
   $('orchestra-prompt').dispatchEvent(new Event('input',{bubbles:true}));
   $('orchestra-parse').click();$('orchestra-compose').click();
   assert(NexusOrchestraUI.hasScore(),'orchestra-score-created');
 };
 const gone=()=>!NexusMusicUI.hasScore()&&!NexusMusicUI.hasWav()&&!NexusOrchestraUI.hasScore()&&
   !NexusOrchestraUI.hasWav()&&!NexusOrchestraUI.hasOriginalVocal()&&!NexusOrchestraUI.hasMixedWav();
 try{
  assert(NexusStudioUI.schema==='nexus.studio.ui.v1','versioned-studio-interface');
  assert(NexusStudioUI.lifecycle_version==='nexus.studio.tool-lifecycle.v1','versioned-lifecycle-contract');
  assert(Object.isFrozen(NexusStudioUI),'public-studio-api-immutable');
  build();loadVoice();await wait(()=>NexusOrchestraUI.hasOriginalVocal());
  assert($('orchestra-dry-play').src.startsWith('blob:'),'synthetic-private-vocal-loaded');
  $('passphrase').value=password;$('repeat-passphrase').value=password;
  $('create-vault').click();await wait(()=>NexusStudioUI.uiStatus().vaultUnlocked);
  assert(NexusStudioUI.uiStatus().vaultUnlocked,'encrypted-vault-created');
  $('lock').click();
  assert(!NexusStudioUI.uiStatus().vaultUnlocked,'vault-locked');
  assert(gone(),'lock-revokes-audio-scores-and-dry-vocal');
  assert(!$('orchestra-dry-play').getAttribute('src')&&!$('orchestra-play').getAttribute('src'),
    'lock-revokes-blob-audio-urls');
  assert($('orchestra-dry-file').value==='','lock-removes-private-file-selection');
  assert($('gateway-token').value===''&&NexusStudioUI.snapshot().projects.length===0,
    'lock-clears-gateway-and-workspace-state');
  $('passphrase').value=password;$('unlock').click();
  await wait(()=>NexusStudioUI.uiStatus().vaultUnlocked);
  build();loadVoice();await wait(()=>NexusOrchestraUI.hasOriginalVocal());
  $('erase').click();await wait(()=>!NexusStudioUI.uiStatus().vaultUnlocked);
  assert(gone(),'archive-erasure-revokes-private-tool-state');
  assert($('orchestra-dry-file').value===''&&$('gateway-token').value==='',
    'erasure-clears-private-input-and-gateway-token');
  assert(network===0,'no-remote-api-or-provider-call');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,network_requests:network,real_model:false});
 }catch(e){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e?.message).slice(0,180),checks,network_requests:network});
 }
});
"""
if __name__ == "__main__":
    browser.main()
