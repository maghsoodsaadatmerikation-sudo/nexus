#!/usr/bin/env python3
"""Pilot 20: disposable real Chromium acceptance for honest guided human dialogue."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const send=v=>{fill('chat-input',v);$('chat-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))};
 const submit=id=>$(id).dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 const labels=()=>Array.from(document.querySelectorAll('#chat-messages .chat-entry')).map(x=>x.textContent);
 let consent=true,prompts=0,downloads=[],network=0,spoken=[],cancelled=0;
 window.confirm=()=>{prompts++;return consent};
 window.fetch=()=>{network++;throw Error('app-network-forbidden')};
 const nativeCreate=URL.createObjectURL,blobs=new Map();
 URL.createObjectURL=b=>{const u=nativeCreate(b);blobs.set(u,b);return u};
 HTMLAnchorElement.prototype.click=function(){if(this.download)downloads.push({blob:blobs.get(this.href),name:this.download})};
 const snap=async()=>{
  const n=downloads.length;$('export').click();if(downloads.length!==n+1)throw Error('snapshot-download-missing');
  return downloads.at(-1).blob.text();
 };
 const synth=new EventTarget(),voices=[
  {name:'remote English',lang:'en-US',localService:false},
  {name:'local English',lang:'en-US',localService:true},
  {name:'local Persian',lang:'fa-IR',localService:true}
 ];
 synth.getVoices=()=>voices;synth.speak=x=>spoken.push(x);synth.cancel=()=>cancelled++;
 Object.defineProperty(window,'speechSynthesis',{configurable:true,value:synth});
 window.SpeechSynthesisUtterance=class{constructor(text){this.text=text}};
 try{
  assert(document.documentElement.lang==='en'&&$('chat-title').textContent==='Talk with NEXUS — guided conversation',
    'english-first-guided-chat-panel-exists');
  assert($('chat-help').textContent.includes('not a generative AI model'),'no-fake-ai-service-claim');
  assert(!$('chat-use-workspace').checked&&$('chat-messages').textContent.includes('Start with a question'),
    'empty-session-with-context-opt-out');
  assert($('chat-as-question').disabled&&$('chat-export').disabled&&$('chat-speak').disabled,
    'no-draft-or-export-or-speech-on-empty-chat');
  $('chat-send').click();assert(labels().length===0,'empty-message-is-rejected');
  send('Could we discuss a community project?');
  assert(labels().length===2&&labels()[0].includes('community project')&&
    labels()[1].includes('desired outcome'),'first-turn-asks-clarifying-question');
  assert(!$('draft-notice').hidden,'private-chat-is-marked-unarchived');
  assert(spoken.length===0&&network===0,'no-automatic-speaker-or-network');
  send('We have only some observations.');
  assert(labels().length===4&&labels().at(-1).includes('direct observations'),
    'second-turn-separates-observations-and-interpretation');
  send('One option is to review this later.');
  assert(labels().length===6&&labels().at(-1).includes('other plausible'),
    'third-turn-explores-alternatives-without-ranking');
  send('Not sure about the consequences.');
  assert(labels().at(-1).includes('remains unknown'),'fourth-turn-asks-about-uncertainty');
  send('We value transparency.');
  assert(labels().at(-1).includes('values and consequences'),
    'fifth-turn-asks-about-human-values');
  send('We need to consider it further.');
  assert(labels().at(-1).includes('Only you can decide'),
    'sixth-turn-preserves-human-decision-authority');
  change('chat-focus','evidence');send('I have a screenshot.');
  assert(labels().at(-1).includes('sources could be checked'),
    'explicit-conversation-focus-overrides-auto-stage');
  const xss='<img src=x onerror=alert(1)> This is an unverified claim.';
  send(xss);
  assert(labels().at(-1).includes('img src')&&
    document.querySelectorAll('#chat-messages img,#chat-messages script').length===0,
    'untrusted-message-is-inert-text');
  const originalHumanCount=labels().length;
  $('chat-as-evidence').click();
  assert($('claim').value===xss&&$('origin').value==='human'&&
    $('uncertainty').value==='unknown'&&$('claims').textContent.includes('No evidence'),
    'manual-message-to-unregistered-human-evidence-draft');
  assert(labels().length===originalHumanCount,'draft-transfer-does-not-inject-new-turn');
  $('chat-as-question').click();
  assert($('question').value===xss&&!$('question-view').textContent.includes(xss),
    'manual-message-to-unregistered-question-draft');
  assert(!$('draft-notice').hidden,'unregistered-chat-and-question-replacement-warn');
  fill('question','A registered question for consented context');
  fill('values','Fairness');
  submit('ask-form');
  assert($('question-view').textContent.includes('A registered question'),
    'human-registers-question-separately');
  const stable=await snap();
  fill('export-passphrase','TOP_SECRET_NOT_FOR_GUIDE');
  send('What do we know so far?');
  assert(!labels().at(-1).includes('A registered question'),
    'no-committed-workspace-read-without-checkbox');
  $('chat-use-workspace').checked=true;
  send('Please revisit the registered question.');
  assert(labels().at(-1).includes('A registered question for consented context')&&
    labels().at(-1).includes('Fairness'),'workspace-context-explicit-opt-in');
  assert(!labels().at(-1).includes('TOP_SECRET')&&!$('chat-messages').textContent.includes('TOP_SECRET'),
    'password-never-in-conversation');
  assert(await snap()===stable,'dialogue-does-not-modify-committed-state-or-audit');
  $('chat-speak').click();
  assert(spoken.length===1&&spoken[0].voice.localService===true&&
    spoken[0].voice.lang==='en-US','only-local-device-voice-speaks-after-click');
  assert(!$('chat-speak-stop').disabled,'local-voice-has-stop-control');
  $('chat-speak-stop').click();
  assert(cancelled>0&&$('chat-speak-stop').disabled,'speech-can-be-stopped');
  voices.splice(1,2);const spoke=spoken.length;
  $('chat-speak').click();
  assert(spoken.length===spoke&&$('chat-state').textContent.includes('No matching on-device voice'),
    'remote-voice-alone-is-refused');
  const n=downloads.length;consent=false;$('chat-export').click();
  assert(downloads.length===n&&$('chat-messages').querySelectorAll('.chat-entry').length>=10,
    'unencrypted-export-requires-explicit-confirmation');
  consent=true;$('chat-export').click();
  const transcript=await downloads.at(-1).blob.text();
  assert(downloads.length===n+1&&downloads.at(-1).name.endsWith('.txt')&&
    transcript.includes('Could we discuss a community project')&&
    transcript.includes('NEXUS guide:')&&!transcript.includes('TOP_SECRET'),
    'export-is-human-readable-session-only-no-password');
  change('ui-language','fa');
  assert(document.documentElement.dir==='rtl'&&$('chat-title').textContent.startsWith('گفت‌وگو با نکسوس')&&
    $('chat-messages').querySelectorAll('.chat-entry').length===labels().length,
    'persian-switch-preserves-conversation-history');
  assert($('chat-messages').textContent.includes('community project'),
    'language-switch-does-not-translate-or-modify-personal-messages');
  change('ui-language','en');
  const old=labels().length;
  consent=false;$('chat-clear').click();
  assert(labels().length===old,'cancelled-clear-retains-only-copy-of-session');
  consent=true;$('chat-clear').click();
  assert(labels().length===0&&$('chat-messages').textContent.includes('Start with a question')&&
    !$('chat-use-workspace').checked,'clear-erases-session-and-sensitive-context-opt-in');
  assert(await snap()===stable,'clearing-chat-leaves-committed-workspace-intact');
  send('A new session after clearing');
  assert(labels().length===2&&labels().at(-1).includes('desired outcome'),
    'new-chat-session-starts-clarification-at-first-step');
  // New workspace operation already has its own guarded confirmation;
  // chat transcript must never follow the replacement.
  $('new').click();
  assert(labels().length===0&&$('chat-state').textContent.includes('workspace was replaced'),
    'new-workspace-clears-chat-on-identity-change');
  assert($('question-view').textContent.includes('No question')&&$('chat-export').disabled,
    'replacement-clears-workspace-and-chat-export-permission');
  fill('chat-input','retained draft');
  assert(!$('draft-notice').hidden,'unsent-chat-input-is-unregistered-draft');
  consent=false;$('new').click();
  assert($('chat-input').value==='retained draft','cancelled-replacement-retains-unsent-chat-draft');
  consent=true;$('new').click();
  assert($('chat-input').value==='','confirmed-replacement-clears-unsent-chat-draft');
  for(let i=0;i<40;i++)send('safe local message '+i);
  assert(labels().length===80,'bounded-forty-exchanges-cap-enforced');
  send('should be rejected');
  assert(labels().length===80&&$('chat-state').textContent.includes('reached its limit'),
    'forty-first-exchange-rejected-without-dropping-history');
  assert(network===0&&localStorage.length===0,
    'conversation-uses-no-app-network-or-plaintext-persistent-storage');
  assert(spoken.length===1,'no-automatic-audio-or-remote-speech');
  $('nexus-browser-result').textContent=JSON.stringify({
    status:'PASS',checks,width:innerWidth,network_requests:network,authority:'none',
    real_person_peer:false,generative_model_used:false,autonomous_judgment:false,production_mutation:false,
    synthetic_local_voice_verified:true});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({
    status:'FAIL',reason:String(e.message).replace(/[^a-z0-9-_]/gi,'')})}
});
"""

def main():
    root=Path(__file__).resolve().parents[1]
    html=(root/'web/offline-pilot.html').read_text(encoding='utf8')
    assert 'NEXUS_GUIDED_CHAT_BEGIN' in html and "connect-src 'none'" in html
    browser=next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium')
                  if shutil.which(n)),None)
    if not browser:raise RuntimeError('real-browser-required')
    page=html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    reports=[]
    with tempfile.TemporaryDirectory(prefix='nexus-guided-chat-') as td:
        source=Path(td)/'index.html';source.write_text(page,encoding='utf8')
        for name,size in [('narrow','500,980'),('wide','1280,980')]:
            result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),
                browser,source.as_uri(),str(Path(td)/name),size,'60000','30000'],
                capture_output=True,text=True,timeout=130)
            if result.returncode:raise RuntimeError('real-browser-runner-failed')
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))<36:
                raise RuntimeError('guided-chat-rejected-'+str(report.get('reason','check-count')))
            assert (name=='narrow')==(report['width']<=760)
            assert report['network_requests']==0 and report['authority']=='none'
            reports.append({'layout':name,**report})
    print(json.dumps({'schema':'nexus.pilot-20.guided-human-dialogue-witness.v1',
                      'status':'PASS','reports':reports,'authority':'none'}))

if __name__=='__main__':main()
