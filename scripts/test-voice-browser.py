#!/usr/bin/env python3
"""Disposable real-browser acceptance: voice lifecycle with controlled native adapters; not a hardware audio test."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const tick=()=>new Promise(r=>setTimeout(r,25));
 const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await tick()}throw Error('voice-wait-expired')};
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 let consent=true,prompts=0,starts=0,aborts=0,installs=0,available='available',lastRec=null,spoken=[],cancelled=0,blobs=[],network=0,deadline=null;
 window.confirm=()=>{prompts++;return consent};
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 const nativeCreate=URL.createObjectURL;URL.createObjectURL=b=>{blobs.push(b);return nativeCreate(b)};
 HTMLAnchorElement.prototype.click=function(){};
 const snapshot=async()=>{const n=blobs.length;$('export').click();if(blobs.length!==n+1)throw Error('snapshot-missing');return await blobs.at(-1).text()};
 const nativeTimeout=window.setTimeout;window.setTimeout=(fn,ms,...args)=>{if(ms===60000)deadline=fn;return nativeTimeout(fn,ms,...args)};
 class Recognition{
  constructor(){this.processLocally=false;lastRec=this;}
  static async available(){return available}
  static async install(){installs++;return true}
  start(){starts++;this.onstart?.()}
  abort(){aborts++;this.onend?.()}
  emit(text,final=true){const row=[{transcript:text}];row.isFinal=final;this.onresult?.({resultIndex:0,results:[row]})}
 }
 const synth=new EventTarget();synth.getVoices=()=>[
  {name:'Synthetic local English',lang:'en-US',localService:true},
  {name:'Synthetic remote English',lang:'en-US',localService:false},
  {name:'Synthetic local Persian',lang:'fa-IR',localService:true}];
 synth.speak=u=>spoken.push(u);synth.cancel=()=>cancelled++;
 Object.defineProperty(window,'speechSynthesis',{value:synth,configurable:true});
 window.SpeechSynthesisUtterance=class{constructor(text){this.text=text}};
 window.SpeechRecognition=Recognition;
 change('voice-language','en-US');
 try{
  assert(starts===0&&spoken.length===0&&!$('voice-online').checked,'no-automatic-microphone-or-speaker-start');
  assert(Array.from($('voice-target').options).every(o=>!o.value.includes('pass'))&&$('voice-choice').options.length===2,'passwords-excluded-and-remote-voices-hidden-by-default');
  $('voice-read').click();assert(spoken.length===0,'empty-text-is-not-spoken');
  window.SpeechRecognition=null;window.webkitSpeechRecognition=null;$('voice-mic').click();
  assert(starts===0&&$('voice-state').textContent.includes('does not provide'),'unsupported-recognition-is-visible-without-recording');
  window.SpeechRecognition=class{};$('voice-mic').click();await tick();
  assert(starts===0&&$('voice-state').textContent.includes('Local recognition'),'legacy-engine-without-local-guarantee-is-not-silently-started');
  window.SpeechRecognition=Recognition;available='unavailable';$('voice-mic').click();await tick();
  assert(starts===0&&$('voice-state').textContent.includes('Local recognition'),'missing-local-model-never-silently-uses-online');
  available='available';$('voice-mic').click();await wait(()=>starts===1);
  assert(lastRec.processLocally===true&&lastRec.lang==='en-US'&&typeof deadline==='function','explicit-local-dictation-requests-local-processing-and-bounded-session');
  lastRec.onerror();assert($('voice-state').textContent.includes('failed')&&!$('voice-mic').disabled,'recognition-permission-or-engine-error-fails-without-registering-text');
  $('voice-mic').click();await wait(()=>starts===2);
  lastRec.emit('interim',false);assert($('voice-transcript').value==='','interim-results-are-not-inserted');
  lastRec.emit('<img src=x> synthetic question');
  assert($('question').value===''&&$('voice-transcript').value.includes('<img')&&!$('draft-notice').hidden,'final-speech-stays-in-unregistered-inert-preview');
  lastRec.emit('duplicate');assert(!$('voice-transcript').value.includes('duplicate'),'duplicate-final-result-is-not-appended-again');
  const beforeStop=aborts,late=lastRec.onresult;$('voice-stop').click();late({resultIndex:0,results:[Object.assign([{transcript:'late'}],{isFinal:true})]});
  assert(aborts===beforeStop+1&&!$('voice-transcript').value.includes('late')&&!$('voice-mic').disabled,'stop-aborts-and-ignores-late-results');
  const lateStart=aborts;lastRec.onstart();assert(aborts===lateStart+1,'late-permission-start-is-aborted-after-cancellation');
  $('voice-insert').click();
  assert($('question').value==='<img src=x> synthetic question'&&$('question-view').textContent.includes('No question')&&!document.querySelector('#question-view img'),'explicit-insertion-is-a-draft-not-an-event-or-html');
  $('ask-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
  const committed=await snapshot();fill('export-passphrase','never-read-this-password');
  $('voice-read').click();
  assert(spoken.length===1&&spoken[0].voice.localService===true&&!spoken[0].text.includes('never-read'),'explicit-read-uses-selected-local-voice-and-excludes-passwords');
  const oldEnd=spoken[0].onend;$('voice-stop').click();oldEnd();
  assert(cancelled===1&&spoken.length===1,'stop-cancels-reading-and-future-chunks');
  $('voice-read').click();spoken.at(-1).onend();
  assert($('voice-state').textContent.includes('completed'),'read-completion-is-visible');
  $('voice-read').click();spoken.at(-1).onerror();
  assert($('voice-state').textContent.includes('failed')&&$('voice-stop').disabled,'read-error-cleans-active-state');
  const bad=document.createElement('option');bad.value='export-passphrase';$('voice-target').append(bad);change('voice-target','export-passphrase');
  const n=spoken.length;$('voice-read').click();
  assert(spoken.length===n,'tampered-target-cannot-read-password-field');bad.remove();change('voice-target','question');
  $('voice-online').checked=true;$('voice-online').dispatchEvent(new Event('change'));$('voice-choice').value='1';consent=false;
  const remoteBefore=spoken.length;$('voice-read').click();
  assert(spoken.length===remoteBefore,'remote-voice-requires-per-action-confirmation');
  consent=true;$('voice-read').click();
  assert(spoken.at(-1).voice.localService===false,'explicitly-approved-remote-voice-is-distinguished');$('voice-stop').click();
  consent=false;const micBefore=starts;$('voice-mic').click();
  assert(starts===micBefore,'online-dictation-cancellation-does-not-open-microphone');
  consent=true;$('voice-mic').click();await wait(()=>starts===micBefore+1);
  assert(lastRec.processLocally===false,'online-dictation-is-explicit-not-an-automatic-fallback');
  lastRec.emit('new dictation');lastRec.onend();fill('question','typed while dictating');$('voice-insert').click();
  assert($('question').value==='typed while dictating'&&$('voice-state').textContent.includes('changed'),'dictation-never-overwrites-a-changed-target');
  assert(await snapshot()===committed,'speech-and-preview-do-not-mutate-committed-workspace-or-audit');
  change('voice-target','decision');$('voice-mic').click();await wait(()=>!!lastRec.onresult&&!$('voice-stop').disabled);lastRec.emit('I choose a synthetic option');lastRec.onend();$('voice-insert').click();
  assert($('decision').value==='I choose a synthetic option'&&JSON.parse(await snapshot()).workspace.judgment===null,'dictation-into-judgment-still-requires-explicit-human-registration');
  change('voice-target','goal');fill('goal','x'.repeat(999));$('voice-mic').click();await tick();lastRec.emit('more than one character');lastRec.onend();$('voice-insert').click();
  assert($('goal').value.length===999&&$('voice-state').textContent.includes('does not fit'),'field-limits-reject-without-truncation-or-overwrite');
  $('voice-clear').click();$('voice-mic').click();await tick();const stopped=aborts;deadline();
  assert(aborts===stopped+1&&$('voice-stop').disabled,'session-deadline-aborts-microphone-without-restarting');
  consent=false;const installBefore=installs;$('voice-model').click();await tick();
  assert(installs===installBefore,'model-download-requires-explicit-consent');
  consent=true;const startBeforeInstall=starts;$('voice-model').click();await wait(()=>!$('voice-model').disabled);
  assert(installs===installBefore+1&&starts===startBeforeInstall,'model-installation-does-not-start-microphone');
  $('voice-mic').click();await tick();const oldAbort=aborts;change('ui-language','fa');
  assert(aborts===oldAbort+1&&$('voice-mic').textContent==='شروع میکروفن','language-switch-stops-audio-and-localizes-controls');
  change('ui-language','en');$('voice-mic').click();await tick();const onPageHide=aborts;window.dispatchEvent(new Event('pagehide'));
  assert(aborts===onPageHide+1,'leaving-page-stops-active-microphone');
  change('voice-target','question');fill('question','X'+'😀'.repeat(400));const chunkStart=spoken.length;$('voice-read').click();
  for(let i=0;i<10&&!$('voice-stop').disabled;i++)spoken.at(-1).onend();
  const chunks=spoken.slice(chunkStart).map(x=>x.text);
  assert(chunks.join('')===$('question').value&&chunks.every(x=>Array.from(x).every(c=>c.length!==1||c.charCodeAt(0)<0xD800||c.charCodeAt(0)>0xDFFF)),'read-chunks-preserve-unicode-code-points');
  $('voice-mic').click();await tick();lastRec.emit('preview before workspace replacement');const oldResult=lastRec.onresult;$('new').click();oldResult({resultIndex:0,results:[]});
  assert($('voice-transcript').value===''&&$('question').value===''&&$('voice-stop').disabled,'workspace-replacement-clears-context-and-rejects-late-audio');
  assert(network===0&&localStorage.length===0,'adapters-use-no-app-network-or-new-persistent-audio-store');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,network_requests:network,production_verified:false,authority:'none',synthetic_only:true,native_audio_tested:false,engines:'controlled-test-adapters'});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(e.message).replace(/[^a-z-]/g,'')})}
});
"""


def main():
    root = Path(__file__).resolve().parents[1]
    html = (root/'web/offline-pilot.html').read_text()
    assert "connect-src 'none'" in html and '@media print' in html
    browser = next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium') if shutil.which(n)),None)
    if not browser:
        raise RuntimeError('real-browser-required')
    page_html = html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    reports=[]
    with tempfile.TemporaryDirectory(prefix='nexus-voice-') as td:
        page=Path(td)/'index.html';page.write_text(page_html)
        for layout,dimensions in [('narrow','500,980'),('wide','1280,980')]:
            result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,page.as_uri(),str(Path(td)/layout),dimensions,'60000','30000'],capture_output=True,text=True,timeout=130)
            if result.returncode:
                raise RuntimeError('private-browser-did-not-complete')
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))!=35:
                raise RuntimeError('voice-adapter-rejected: '+str(report.get('reason','check-count')))
            assert (layout=='narrow')==(report['width']<=760)
            reports.append({'layout':layout,**report})
    print(json.dumps({'schema':'nexus.pilot-16.voice-adapter-witness.v1','status':'PASS','reports':reports,'authority':'none','real_user_tested':False}))

if __name__=='__main__':
    main()
