#!/usr/bin/env python3
"""Real narrow Chromium: Orchestra input parsing, notes, WAV and dry vocal safety."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],objects=[];
 const assert=(condition,name)=>{if(!condition)throw Error(name);checks.push(name)};
 const wait=async(fn,attempts=500)=>{for(let i=0;i<attempts;i++){if(fn())return;await new Promise(r=>setTimeout(r,65))}throw Error('wait-timeout')};
 const oldFetch=window.fetch,oldObject=URL.createObjectURL;
 let networkCalls=0;
 window.fetch=()=>{networkCalls++;return Promise.reject(Error('network-unexpected'))};
 URL.createObjectURL=function(blob){objects.push(blob);return oldObject.call(this,blob)};
 try{
  assert(typeof NexusOrchestra.parsePrompt==='function','orchestra-bundle-loaded');
  assert(typeof NexusOrchestra.render==='function','orchestra-wav-engine-loaded');
  assert($('orchestra-card')!==null,'orchestra-panel-present');
  assert(NexusStudioFocus.openPanel('orchestra-card'),'mobile-tool-navigation');
  assert($('orchestra-compose').disabled,'must-review-prompt-before-compose');
  $('orchestra-prompt').value='hypnotic airy soprano choir harp flute in D minor 120 bpm 4 bars bird chime';
  $('orchestra-prompt').dispatchEvent(new Event('input',{bubbles:true}));
  $('orchestra-parse').click();
  assert(!$('orchestra-compose').disabled,'recognized-keyword-grammar-available');
  assert($('orchestra-report').textContent.includes('synthetic-vowel')||
    $('orchestra-report').textContent.includes('Generic vowel voice: true'),'plan-labels-what-is-synthetic');
  $('orchestra-compose').click();
  assert(NexusOrchestraUI.hasScore(),'orchestra-score-created');
  assert(!$('orchestra-midi').disabled&&!$('orchestra-xml').disabled,'notation-export-ready');
  $('orchestra-xml').click();
  assert(objects.some(b=>b.type==='application/vnd.recordare.musicxml+xml'),'musicxml-download-content');
  $('orchestra-midi').click();
  assert(objects.some(b=>b.type==='audio/midi'&&b.size>100),'true-midi-download');
  $('orchestra-render').click();
  assert(!$('orchestra-cancel').disabled,'render-is-cancellable');
  await wait(()=>NexusOrchestraUI.hasWav(),900);
  assert($('orchestra-play').src.startsWith('blob:'),'synth-audio-in-browser');
  $('orchestra-wav').click();
  assert(objects.some(b=>b.type==='audio/wav'&&b.size>100000),'wav-download');
  // Original 16-bit mono WAV with 22050 Hz and exactly valid RIFF bytes.
  const frames=2205,bytes=new Uint8Array(44+frames*2),v=new DataView(bytes.buffer);
  const put=(off,text)=>{for(let i=0;i<text.length;i++)v.setUint8(off+i,text.charCodeAt(i))};
  put(0,'RIFF');v.setUint32(4,36+frames*2,true);put(8,'WAVE');
  put(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);
  v.setUint16(22,1,true);v.setUint32(24,22050,true);
  v.setUint32(28,44100,true);v.setUint16(32,2,true);
  v.setUint16(34,16,true);put(36,'data');v.setUint32(40,frames*2,true);
  for(let i=0;i<frames;i++)v.setInt16(44+i*2,Math.round(2300*Math.sin(i*.12)),true);
  const transfer=new DataTransfer();
  transfer.items.add(new File([bytes],'my-own-voice.wav',{type:'audio/wav'}));
  $('orchestra-dry-file').files=transfer.files;
  $('orchestra-dry-file').dispatchEvent(new Event('change',{bubbles:true}));
  await wait(()=>NexusOrchestraUI.hasOriginalVocal());
  assert($('orchestra-dry-play').src.startsWith('blob:'),'user-own-voice-local-only');
  assert($('orchestra-dry-play').playbackRate===1,'dry-original-playback-normal-rate');
  assert($('orchestra-dry-report').textContent.includes('Original WAV SHA-256:'),'local-only-fingerprint');
  $('orchestra-dry-download').click();
  const raw=objects.at(-1);
  const same=new Uint8Array(await raw.arrayBuffer());
  assert(same.length===bytes.length&&same.every((x,i)=>x===bytes[i]),
    'original-dry-vocal-downloaded-byte-for-byte');
  assert($('orchestra-together').disabled===false,'optional-voice-and-backing-audition-available');
  assert(networkCalls===0,'no-provider-or-music-api-network');
  $('orchestra-dry-clear').click();
  assert(!NexusOrchestraUI.hasOriginalVocal(),'clear-removes-voice-from-tab');
  assert($('orchestra-dry-download').disabled,'no-private-voice-export-after-clear');
  $('orchestra-prompt').value='opera rap impossible word';
  $('orchestra-prompt').dispatchEvent(new Event('input',{bubbles:true}));
  $('orchestra-parse').click();
  assert($('orchestra-compose').disabled,'unsupported-instructions-are-not-silently-guessed');
  assert(!NexusOrchestraUI.hasScore(),'editing-prompt-revokes-old-score');
  assert(networkCalls===0,'all-actions-offline');
  $('nexus-browser-result').textContent=JSON.stringify({
   status:'PASS',checks,networkCalls,dry_file_untouched:true,source:'offline-orchestra'});
 }catch(error){
  $('nexus-browser-result').textContent=JSON.stringify({
   status:'FAIL',reason:String(error.message).slice(0,160),checks,networkCalls});
 }finally{window.fetch=oldFetch;URL.createObjectURL=oldObject}
});
"""

def main():
    chrome=next((shutil.which(n) for n in ("chromium","google-chrome") if shutil.which(n)),None)
    if not chrome:
        raise RuntimeError("real Chromium required")
    html=(ROOT/"web/studio.html").read_text()
    html=html.replace("</body>",'<pre hidden id="nexus-browser-result"></pre><script>'+
        WITNESS+"</script></body>")
    with tempfile.TemporaryDirectory(prefix="nexus-orchestra-browser-") as td:
        root=Path(td)
        page=root/"index.html"
        page.write_text(html)
        result=subprocess.run([
            "node",str(ROOT/"scripts/workspace-browser-runner.mjs"),chrome,
            page.as_uri(),str(root/"profile"),"420,900","60000","30000"
        ],capture_output=True,text=True,timeout=140)
        if result.returncode:
            raise RuntimeError("browser-launch-failed: "+result.stderr[-600:])
        report=json.loads(result.stdout)
        if report.get("status")!="PASS":
            raise RuntimeError(json.dumps(report))
        if len(report["checks"])<20:
            raise RuntimeError("insufficient-browser-witnesses")
        print(json.dumps(report))
if __name__=="__main__":
    main()
