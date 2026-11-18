#!/usr/bin/env python3
"""Real disposable Chromium smoke test: NEXUS Motion canvas + local video export."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],created=[];
 const test=(condition,message)=>{if(!condition)throw Error(message);checks.push(message)};
 const originalFetch=window.fetch,originalURL=URL.createObjectURL;
 let external=0;
 window.fetch=(...args)=>{external++;return Promise.reject(Error('network not allowed'))};
 URL.createObjectURL=function(blob){created.push({size:blob.size,type:blob.type});return originalURL.call(this,blob)};
 try{
  test(typeof NexusMotion.frame==='function','motion-core-loaded');
  test($('motion-canvas').width>0,'canvas-present');
  test($('motion-scenes').children.length===3,'three-editable-scenes');
  test(NexusMotion.validate(NexusMotion.DEFAULT())===13,'timeline-correct');
  $('motion-play').click();await new Promise(r=>setTimeout(r,180));
  test(Number($('motion-seek').value)>0,'real-animation-playhead');
  $('motion-pause').click();
  $('motion-add').click();test($('motion-scenes').children.length===4,'scene-editing');
  $('motion-remove').click();test($('motion-scenes').children.length===3,'scene-removal');
  $('motion-export-json').click();
  test(created.some(x=>x.type==='application/json'&&x.size>100),'json-export');
  $('motion-export-zip').click();
  await new Promise(r=>setTimeout(r,250));
  test(created.some(x=>x.type==='application/zip'&&x.size>400),'local-project-zip');
  test(external===0,'no-network');
  test(!$('motion-record').disabled,'record-button-live');
  $('motion-clip').value='1';
  $('motion-record').click();
  await new Promise((resolve,reject)=>{
   let ticks=0;const timer=setInterval(()=>{
    ticks++;
    if(!$('motion-record').disabled){clearInterval(timer);resolve();}
    if(ticks>80){clearInterval(timer);reject(Error('recording timed out'));}
   },125);
  });
  const supported=typeof MediaRecorder!=='undefined'&&!!['video/mp4;codecs=avc1.42E01E','video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(x=>MediaRecorder.isTypeSupported(x));
  if(supported)test(created.some(x=>x.type.startsWith('video/')&&x.size>1000),'real-local-video-recorded');
  test(external===0,'zero-network-after-export');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,created,network_requests:external});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e.message),checks,created,network_requests:external})}
 finally{window.fetch=originalFetch;URL.createObjectURL=originalURL}
});
"""


def main():
    browser=next((shutil.which(k) for k in ("google-chrome","chromium") if shutil.which(k)),None)
    if not browser:raise RuntimeError("Chromium is required, not a synthetic DOM")
    with tempfile.TemporaryDirectory(prefix="nexus-motion-browser-") as d:
        folder=Path(d)
        for name in ("motion.html","motion-core.js","motion-ui.js"):
            shutil.copy2(ROOT/"web"/name, folder/name)
        page=folder/"motion.html"
        html=page.read_text(encoding="utf-8")
        html=html.replace("</body>",'<pre hidden id="nexus-browser-result"></pre><script src="./witness.js"></script></body>')
        page.write_text(html,encoding="utf-8")
        (folder/"witness.js").write_text(WITNESS,encoding="utf-8")
        result=subprocess.run(["node",str(ROOT/"scripts/workspace-browser-runner.mjs"),
                               browser,page.as_uri(),str(folder/"witness"),"420,900","60000","30000"],
                              capture_output=True,text=True,timeout=145)
        if result.returncode:
            raise RuntimeError("real browser failed: "+result.stderr[-900:])
        report=json.loads(result.stdout)
        if report.get("status")!="PASS" or len(report.get("checks",[]))<10:
            raise RuntimeError("Motion browser acceptance failed: "+json.dumps(report))
        print(json.dumps(report))


if __name__=="__main__":
    main()
