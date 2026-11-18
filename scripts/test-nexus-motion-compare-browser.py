#!/usr/bin/env python3
"""Actual isolated Chromium: local MP4-vs-Canvas comparison; no external API."""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id), checks=[];
 const check=(truth,msg)=>{if(!truth)throw Error(msg);checks.push(msg)};
 let calls=0;
 const originalFetch=window.fetch;
 window.fetch=()=>{calls++;return Promise.reject(Error('network is forbidden'))};
 const pause=ms=>new Promise(r=>setTimeout(r,ms));
 const until=async(fn,deadline=14000)=>{
   for(let t=0;t<deadline;t+=50){if(fn())return;await pause(50);}
   throw Error('local UI assertion timed out');
 };
 const media=(base64,type,name)=>{
   const raw=atob(base64),bytes=new Uint8Array(raw.length);
   for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
   return new File([bytes],name,{type});
 };
 const upload=(id,file)=>{
   const data=new DataTransfer();data.items.add(file);
   $(id).files=data.files;$(id).dispatchEvent(new Event('change',{bubbles:true}));
 };
 try{
  check(typeof NexusMotion.pixelDifference==='function','pixel-difference-loaded');
  check($('motion-final-video') instanceof HTMLVideoElement,'html-video-preview-present');
  check($('motion-compare-now').disabled,'no-file-comparison-disabled');
  const sample={
    schema:'nexus.motion.storyboard.v1',title:'NEXUS COMPARISON WITNESS',
    width:1280,height:720,fps:24,
    scenes:[
      {duration:1,background:'#07112b',accent:'#88caba',
       title:'DARK SCENE',motion:'still'},
      {duration:1,background:'#1c2240',accent:'#ffffff',
       title:'NEXT SCENE',motion:'still'}
    ]};
  upload('motion-import',new File([JSON.stringify(sample)],'project.json',{type:'application/json'}));
  await until(()=>$('motion-title').value==='NEXUS COMPARISON WITNESS');
  check(NexusMotion.validate(sample)===2,'two-second-storyboard-loaded');
  upload('motion-compare-file',media('__WHITE_MP4__','video/mp4','white.mp4'));
  await until(()=>$('motion-compare-now').disabled===false);
  check($('motion-final-video').videoWidth===1280,'local-mp4-width-decoded');
  check(Math.abs($('motion-final-video').duration-2)<.1,'local-mp4-duration-decoded');
  $('motion-compare-now').click();
  await until(()=>$('motion-compare-result').textContent.startsWith('Measured 1 frame'));
  check($('motion-compare-result').textContent.includes('human review'),
        'actual-decoded-frame-difference-reported');
  check($('motion-compare-result').textContent.includes('1 flagged'),
        'dark-canvas-versus-white-mp4-flags-difference');
  $('motion-compare-three').click();
  await until(()=>$('motion-compare-result').textContent.startsWith('Measured 2 frame'));
  check($('motion-compare-result').textContent.includes('worst'),
        'independent-two-frame-comparison-done');
  check(calls===0,'no-network-api-or-user-media-upload');
  upload('motion-compare-file',media('__WRONG_MP4__','video/mp4','wrong.mp4'));
  await until(()=>$('motion-compare-now').disabled===false);
  $('motion-compare-now').click();
  await until(()=>$('motion-compare-result').textContent.includes('resolution does not match'));
  check(true,'wrong-resolution-video-fails-closed');
  $('motion-compare-clear').click();
  check($('motion-compare-now').disabled,'clearing-releases-video');
  check(calls===0,'no-network-after-clear');
  $('nexus-browser-result').textContent=JSON.stringify({
    status:'PASS',checks,network_requests:calls,real_mp4_decode:true,
    pixel_parity_proven:false,cloud_upload:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({
    status:'FAIL',reason:String(e.message),checks,network_requests:calls});}
 finally{window.fetch=originalFetch}
});
"""


def make_video(path: Path, dimensions: str):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=white:s={dimensions}:r=24:d=2",
        "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", str(path)
    ], check=True, capture_output=True, timeout=50)
    assert path.stat().st_size > 500


def main():
    browser=next((shutil.which(k) for k in ('google-chrome','chromium') if shutil.which(k)),None)
    if not browser:
        raise RuntimeError("Real Chromium required")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg required")
    with tempfile.TemporaryDirectory(prefix="nexus-motion-compare-test-") as tmp:
        folder=Path(tmp)
        for name in ("motion.html","motion-core.js","motion-ui.js"):
            shutil.copy2(ROOT/"web"/name, folder/name)
        white=folder/"white.mp4";wrong=folder/"wrong.mp4"
        make_video(white,"1280x720")
        make_video(wrong,"320x180")
        html=(folder/"motion.html").read_text(encoding="utf-8")
        html=html.replace("</body>",'<pre hidden id="nexus-browser-result"></pre><script src="./witness.js"></script></body>')
        (folder/"motion.html").write_text(html,encoding="utf-8")
        code=WITNESS.replace('__WHITE_MP4__',base64.b64encode(white.read_bytes()).decode())
        code=code.replace('__WRONG_MP4__',base64.b64encode(wrong.read_bytes()).decode())
        (folder/"witness.js").write_text(code,encoding="utf-8")
        attempt=subprocess.run([
            "node",str(ROOT/"scripts/workspace-browser-runner.mjs"),
            browser,(folder/"motion.html").as_uri(),str(folder/"private-browser"),
            "420,900","60000","30000",
        ], capture_output=True,text=True,timeout=145)
        if attempt.returncode:
            raise RuntimeError("private browser failed: "+attempt.stderr[-900:])
        report=json.loads(attempt.stdout)
        if report.get("status")!="PASS" or len(report.get("checks",[]))<10:
            raise RuntimeError("local MP4 comparison failed: "+json.dumps(report))
        print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
