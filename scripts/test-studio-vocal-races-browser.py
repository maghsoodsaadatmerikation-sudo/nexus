#!/usr/bin/env python3
"""Chromium regression: late vocal reads and playback cannot reappear after clear or lock."""
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
 const wait=async(fn,n=600)=>{for(let i=0;i<n;i++){if(fn())return;await new Promise(r=>setTimeout(r,30))}throw Error('timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const nativeRead=File.prototype.arrayBuffer,nativePlay=HTMLMediaElement.prototype.play;
 let calls=0,pending=[],plays=[];
 window.fetch=()=>{calls++;throw Error('no-network-allowed')};
 const bytes=new Uint8Array(44+2205*2),v=new DataView(bytes.buffer);
 const put=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i))};
 put(0,'RIFF');v.setUint32(4,36+2205*2,true);put(8,'WAVE');
 put(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);
 v.setUint16(22,1,true);v.setUint32(24,22050,true);
 v.setUint32(28,44100,true);v.setUint16(32,2,true);v.setUint16(34,16,true);
 put(36,'data');v.setUint32(40,2205*2,true);
 for(let i=0;i<2205;i++)v.setInt16(44+2*i,Math.round(1700*Math.sin(i*.12)),true);
 const choose=()=>{
  const transfer=new DataTransfer();
  transfer.items.add(new File([bytes],'private.wav',{type:'audio/wav'}));
  $('orchestra-dry-file').files=transfer.files;
  $('orchestra-dry-file').dispatchEvent(new Event('change',{bubbles:true}));
 };
 const empty=()=>!NexusOrchestraUI.hasOriginalVocal()&&
  !$('orchestra-dry-play').getAttribute('src')&&
  !$('orchestra-dry-report').textContent&&
  $('orchestra-dry-file').value===''&&$('orchestra-dry-download').disabled;
 try{
  File.prototype.arrayBuffer=function(){
   return new Promise((resolve,reject)=>pending.push({resolve,reject}));
  };
  choose();await wait(()=>pending.length===1);
  $('orchestra-dry-clear').click();
  const cleared=$('orchestra-status').textContent;
  pending.shift().resolve(bytes.buffer.slice(0));
  await sleep(100);
  assert(empty(),'manual-clear-rejects-late-successful-file-read');
  assert($('orchestra-status').textContent===cleared,'late-read-may-not-rewrite-clear-status');

  choose();await wait(()=>pending.length===1);
  $('orchestra-dry-clear').click();
  const rejected=$('orchestra-status').textContent;
  pending.shift().reject(Error('synthetic late file failure'));
  await sleep(100);
  assert(empty(),'manual-clear-rejects-late-file-rejection');
  assert($('orchestra-status').textContent===rejected,'late-rejection-may-not-rewrite-clear-status');

  choose();await wait(()=>pending.length===1);
  $('lock').click();
  const locked=$('orchestra-status').textContent;
  pending.shift().resolve(bytes.buffer.slice(0));
  await sleep(100);
  assert(empty()&&!NexusStudioUI.uiStatus().vaultUnlocked,'vault-lock-rejects-late-file-read');
  assert($('orchestra-status').textContent===locked,'late-file-read-may-not-rewrite-locked-page');

  File.prototype.arrayBuffer=nativeRead;
  choose();await wait(()=>NexusOrchestraUI.hasOriginalVocal());
  assert(NexusOrchestraUI.hasOriginalVocal(),'new-vocal-import-still-works-after-cancelled-read');
  assert($('orchestra-dry-report').textContent.includes('Original WAV SHA-256:'),
    'successful-reimport-retains-byte-identity-report');

  $('orchestra-prompt').value='hypnotic airy soprano choir harp flute in D minor 120 bpm 4 bars bird chime';
  $('orchestra-prompt').dispatchEvent(new Event('input',{bubbles:true}));
  $('orchestra-parse').click();$('orchestra-compose').click();
  assert(NexusOrchestraUI.hasScore(),'orchestra-still-composes-after-cancelled-import');
  $('orchestra-render').click();
  await wait(()=>NexusOrchestraUI.hasWav(),1200);
  assert(NexusOrchestraUI.hasWav(),'audio-created-for-delayed-playback-test');
  HTMLMediaElement.prototype.play=function(){return new Promise(resolve=>plays.push(resolve))};
  $('orchestra-together').click();await wait(()=>plays.length===2);
  $('lock').click();
  const noStatusAfterLock=$('orchestra-status').textContent;
  plays.splice(0).forEach(resolve=>resolve());
  await sleep(120);
  assert(!NexusOrchestraUI.hasOriginalVocal()&&!NexusOrchestraUI.hasWav(),
    'lock-clears-audio-while-playback-promise-pending');
  assert($('orchestra-status').textContent===noStatusAfterLock,
    'late-playback-completion-may-not-claim-playing-after-lock');
  assert(calls===0,'no-network-while-protecting-original-vocal');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,network_calls:calls});
 }catch(e){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e?.message).slice(0,170),checks,network_calls:calls});
 }finally{
  File.prototype.arrayBuffer=nativeRead;HTMLMediaElement.prototype.play=nativePlay;
 }
});
"""
if __name__ == "__main__":
    browser.main()
