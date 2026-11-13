#!/usr/bin/env python3
"""Real disposable Chromium smoke tests for optional model chat, no actual provider calls."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location(
    "nexus_browser_fixture",Path(__file__).with_name("test-research-chat-browser.py"))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.WITNESS=r"""
window.addEventListener('load',async()=>{
const e=id=>document.getElementById(id),checks=[],calls=[];
const chk=(v,s)=>{if(!v)throw Error(s);checks.push(s)};
const input=(id,value)=>{e(id).value=value;e(id).dispatchEvent(new Event('input',{bubbles:true}))};
const wait=async fn=>{for(let i=0;i<500;i++){if(fn())return;await new Promise(r=>setTimeout(r,10))}throw Error('timed-out')};
const answer={
 schema:'nexus.model-chat.v1',mode:'generative_unverified_machine_draft',
 authority:'none',judgment_changed:false,verified_facts:false,
 citations:[],actual_cost_known:false,automatic_actions:false,
 provider:'synthetic',model:'unit-model',answer:'<img src=x onerror=alert(1)> Synthetic response'
};
let respond=async()=>({ok:true,json:async()=>answer});
window.fetch=async(url,options)=>{
  calls.push({url,options,payload:JSON.parse(options.body)});
  return respond(options);
};
try{
 chk(calls.length===0&&messages.length===0&&!busy,'no-request-on-open');
 chk(e('consent')&&e('cost')&&!e('consent').checked&&!e('cost').checked,
    'two-consents-default-off');
 chk(document.querySelector('meta[http-equiv="Content-Security-Policy"]')
       .content.includes("connect-src 'self'"),'same-origin-only-csp');
 input('message','Synthetic question');e('send').click();
 chk(calls.length===0,'token-required-before-dispatch');
 input('api-token','SYNTHETIC_SECRET_TOKEN');e('send').click();
 chk(calls.length===0,'approval-required-before-dispatch');
 e('consent').checked=true;e('send').click();
 chk(calls.length===0,'cost-acknowledgement-required');
 e('cost').checked=true;e('send').click();await wait(()=>!busy);
 chk(calls.length===1&&calls[0].url==='/v1/model-chat','one-matched-endpoint');
 chk(calls[0].options.credentials==='omit','no-ambient-cookie-credentials');
 chk(calls[0].options.cache==='no-store','model-request-no-cache');
 chk(calls[0].payload.consent&&calls[0].payload.cost_acknowledged,'two-approvals-on-wire');
 chk(calls[0].payload.messages.length===1&&calls[0].payload.messages[0].content==='Synthetic question',
    'exact-reviewed-message-only');
 chk(!e('consent').checked&&!e('cost').checked,'approvals-consumed');
 chk(e('conversation').querySelectorAll('img').length===0,'machine-output-is-not-html');
 chk(e('conversation').textContent.includes('<img'),'malicious-markup-shown-as-text');
 chk(messages.length===2&&messages[1].role==='assistant','model-draft-retained-in-tab');
 input('message','Followup');e('consent').checked=true;e('cost').checked=true;
 e('send').click();await wait(()=>!busy);
 chk(calls.length===2&&calls[1].payload.messages.length===3,'bounded-multi-turn-context');
 chk(messages.length===4,'second-response-is-visible');
 let resolve;respond=()=>new Promise(fn=>{resolve=fn});
 input('message','Cancel');e('consent').checked=true;e('cost').checked=true;
 e('send').click();await wait(()=>!!resolve);e('cancel').click();
 resolve({ok:true,json:async()=>answer});await new Promise(r=>setTimeout(r,10));
 chk(messages.length===4,'late-answer-discarded-after-cancel');
 chk(!busy,'cancel-releases-client-controls');
 e('clear').click();chk(messages.length===0&&e('message').value==='', 'clear-removes-all-in-tab-context');
 chk(!e('consent').checked&&!e('cost').checked,'clear-removes-prior-approval');
 input('api-token','NEXT_SECRET_TOKEN');chk(messages.length===0,'token-rotation-clears-history');
 e('lang').value='fa';e('lang').dispatchEvent(new Event('change'));
 chk(document.documentElement.dir==='rtl'&&e('send').textContent.includes('ارسال'),'persian-rtl-ui');
 chk(localStorage.length===0&&sessionStorage.length===0,'never-persist-model-or-gateway-tokens');
 chk(messages.every(x=>!x.content.includes('SECRET_TOKEN')),'secret-excluded-from-transcript');
 e('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,provider_requests:0,
 actual_provider_tested:false,mode:'synthetic_browser_only'});
}catch(err){e('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(err?.message||err),checks})}
});
"""
if __name__=="__main__":
    fixture.main("web/model-chat.html")
