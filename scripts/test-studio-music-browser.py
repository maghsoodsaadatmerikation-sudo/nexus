#!/usr/bin/env python3
"""Disposable real Chromium: original NEXUS Music Lab UI and local WAV playback."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const wait=async(fn,n=650)=>{for(let i=0;i<n;i++){if(fn())return;await new Promise(r=>setTimeout(r,50))}throw Error('music-render-timeout')};
 let net=0,created=[];
 const originalFetch=window.fetch,originalObject=URL.createObjectURL;
 window.fetch=(...args)=>{net++;return Promise.reject(Error('music-engine-should-not-call-network'))};
 URL.createObjectURL=function(blob){created.push({type:blob.type,size:blob.size});return originalObject.call(this,blob)};
 try{
  assert(typeof NexusMusic.compose==='function','engine-wired');
  assert(typeof NexusMusic.renderWav==='function','pcm-wired');
  assert(!$('music-midi').disabled===false,'start-no-midi-before-score');
  assert($('music-card')!==null,'music-panel-visible-in-dom');
  assert(NexusStudioFocus.openPanel('music-card'),'music-mobile-navigation');
  $('music-bars').value='32';$('music-bars').dispatchEvent(new Event('change',{bubbles:true}));
  $('music-bpm').value='140';$('music-bpm').dispatchEvent(new Event('change',{bubbles:true}));
  $('music-build').click();
  assert(NexusMusicUI.hasScore(),'score-is-real');
  assert($('music-report').textContent.includes('Instrumental solo'),'score-has-solo');
  assert(!$('music-midi').disabled,'midi-allowed-after-scoring');
  assert($('music-wav').disabled,'wav-requires-render');
  const old=$('music-report').textContent.match(/Motif degrees: ([^\n]+)/)?.[1];
  $('music-problem').value='weak-hook';$('music-refine').click();
  assert(!NexusMusicUI.hasScore(),'explicit-revision-invalidates-old-score');
  $('music-build').click();
  const revised=$('music-report').textContent.match(/Motif degrees: ([^\n]+)/)?.[1];
  assert(old===revised,'motif-preserved-by-default');
  $('music-midi').click();assert(created.some(x=>x.type==='audio/midi'&&x.size>1000),'native-midi-binary-download');
  $('music-quality').value='22050';$('music-quality').dispatchEvent(new Event('change',{bubbles:true}));
  assert(NexusMusicUI.hasScore()&&!$('music-render').disabled,'changing-output-quality-does-not-delete-score');
  $('music-render').click();assert($('music-cancel').disabled===false,'render-cancel-action-exposed');
  await wait(()=>NexusMusicUI.hasWav(),900);
  assert($('music-preview').src.startsWith('blob:'),'playable-local-audio');
  assert(!$('music-wav').disabled,'wav-export-ready');
  assert($('music-progress').value===100,'render-completed');
  assert($('music-report').textContent.includes('Measured WAV diagnostics'),'post-render-actual-pcm-analysis');
  assert($('music-report').textContent.includes('Clipped PCM frames: 0'),'unclipped-wave-output');
  $('music-wav').click();
  assert(created.some(x=>x.type==='audio/wav'&&x.size>200000),'real-rendered-wave-download');
  $('music-sound').value='classic';$('music-sound').dispatchEvent(new Event('change',{bubbles:true}));
  assert(NexusMusicUI.hasScore()&&!NexusMusicUI.hasWav(),'timbre-ab-preserves-original-score-not-old-audio');
  assert(!$('music-render').disabled,'classic-synth-option-available');
  $('music-sound').value='expressive';$('music-sound').dispatchEvent(new Event('change',{bubbles:true}));
  assert(net===0,'no-suno-or-api-request');
  // Repeat a setup change during the start of a new render: no stuck buttons.
  $('music-render').click();
  $('music-bpm').value='120';$('music-bpm').dispatchEvent(new Event('change',{bubbles:true}));
  await new Promise(r=>setTimeout(r,300));
  assert(!$('music-build').disabled,'changing-settings-never-leaves-render-lock');
  assert(!NexusMusicUI.hasScore()&&!NexusMusicUI.hasWav(),'old-score-and-wav-invalidation');
  assert(net===0,'no-network-on-cancel');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,network_requests:net,actual_wav:true,suno:false,source:'local-synthesis'});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e.message).slice(0,120),checks,network_requests:net})}
 finally{window.fetch=originalFetch;URL.createObjectURL=originalObject}
});
"""

def main():
    browser=next((shutil.which(n) for n in ("google-chrome","chromium") if shutil.which(n)),None)
    if not browser:
        raise RuntimeError("real Chromium browser required")
    html=(ROOT/"web/studio.html").read_text()
    html=html.replace("</body>",
         '<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+"</script></body>")
    with tempfile.TemporaryDirectory(prefix="nexus-original-music-") as directory:
        root=Path(directory)
        page=root/"index.html"
        page.write_text(html)
        result=subprocess.run([
            "node",str(ROOT/"scripts/workspace-browser-runner.mjs"),browser,
            page.as_uri(),str(root/"witness"),"420,900","60000","30000"
        ],capture_output=True,text=True,timeout=170)
        if result.returncode:
            raise RuntimeError("browser-runner-failed: "+result.stderr[-500:])
        report=json.loads(result.stdout)
        if report.get("status")!="PASS":
            raise RuntimeError(json.dumps(report))
        if len(report["checks"])<18:
            raise RuntimeError("missing-browser-checks")
        print(json.dumps(report))

if __name__=="__main__":
    main()
