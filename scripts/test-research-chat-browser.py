#!/usr/bin/env python3
"""Synthetic browser acceptance: private source-grounded dialogue, no provider calls."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WITNESS = r"""
window.addEventListener('load',async()=>{
const $=id=>document.getElementById(id),checks=[],calls=[];
const assert=(yes,key)=>{if(!yes)throw Error(key);checks.push(key)};
const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
const change=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
const send=()=> $('chat-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
const wait=async test=>{for(let i=0;i<100;i++){if(test())return;await new Promise(r=>setTimeout(r,10))}throw Error('waiting-timeout')};
const fixture=()=>({schema:'nexus.research-chat.v1',mode:'retrieval_assisted_extractive',authority:'none',judgment_changed:false,
 answer:'“Synthetic alpha has seven units.” [S1]',context:null,answer_status:'source_excerpts_available',
 claims:[{text:'Synthetic alpha has seven units.',citation_ids:['S1'],origin:'user_supplied_excerpt',uncertainty:'not_independently_verified'}],
 sources:[{id:'S1',title:'<img src=x onerror=alert(1)>',url:'https://example.org/alpha',excerpt:'Synthetic alpha has seven units.',origin:'user_supplied_excerpt',provider:'manual_review',retrieved_at_unix:null}],
 providers:[],unknowns:['Synthetic evidence is not independent verification.'],next_question:'Which primary source should we check?'});
let reply=async()=>({ok:true,json:async()=>fixture()}),exported=[];
window.confirm=()=>true;
window.fetch=async(url,options)=>{assert(url==='/v1/research-chat','single-same-origin-endpoint');calls.push({url,options,payload:JSON.parse(options.body)});return reply(options)};
const create=URL.createObjectURL,blobs=new Map();URL.createObjectURL=b=>{const u=create(b);blobs.set(u,b);return u};
HTMLAnchorElement.prototype.click=function(){if(this.download)exported.push(blobs.get(this.href))};
try{
 assert(document.documentElement.lang==='en'&&!$('search').checked&&!$('consent').checked&&calls.length===0,'no-automatic-retrieval');
 assert(document.querySelector('meta[http-equiv="Content-Security-Policy"]').content.includes("connect-src 'self'"),'browser-only-connects-to-own-server');
 fill('message','Private initial question');send();assert(calls.length===0,'missing-token-does-not-send');
 fill('token','SYNTHETIC_PRIVATE_TOKEN');fill('message','What is alpha?');
 $('search').checked=true;$('search').dispatchEvent(new Event('change'));fill('query','public alpha');send();assert(calls.length===0,'missing-per-query-consent-does-not-send');
 $('consent').checked=true;fill('query','changed public alpha');assert(!$('consent').checked,'query-edit-revokes-consent');
 $('search').checked=false;$('search').dispatchEvent(new Event('change'));
 fill('source-title','Synthetic primary review');fill('source-url','https://example.org/alpha');fill('source-text','Synthetic alpha has seven units.');
 send();await wait(()=>!$('send').disabled);
 assert(calls.length===1&&calls[0].payload.search===false,'manual-evidence-needs-no-provider-request');
 assert(calls[0].options.credentials==='omit'&&calls[0].options.cache==='no-store','private-request-has-no-cookies-or-cache');
 assert($('conversation').children.length===2&&$('conversation').textContent.includes('[S1]'),'cited-answer-is-visible');
 assert($('conversation').querySelectorAll('img').length===0&&$('conversation').textContent.includes('<img'),'source-markup-is-text-not-instructions');
 const a=$('conversation').querySelector('a');assert(a.rel.includes('noreferrer')&&a.href==='https://example.org/alpha','source-link-is-inspectable-with-no-referrer');
 for(const id of ['source-title','source-url','source-text'])fill(id,'');
 fill('message','And its capacity?');send();await wait(()=>!$('send').disabled);
 assert(calls.at(-1).payload.context_sources[0].excerpt==='Synthetic alpha has seven units.','followup-reuses-explicit-source-context');
 assert(calls.at(-1).payload.messages[0].content==='What is alpha?','followup-retains-human-conversation-context');
 $('search').checked=true;$('search').dispatchEvent(new Event('change'));fill('query','only approved public query');$('consent').checked=true;fill('message','Private followup');send();assert(!$('consent').checked,'consent-is-consumed-at-dispatch');await wait(()=>!$('send').disabled);
 assert(calls.at(-1).payload.query==='only approved public query'&&calls.at(-1).payload.consent===true,'exact-query-is-explicitly-approved');
 assert(!$('consent').checked,'consent-is-reset-after-each-search');
 $('export').click();const transcript=await exported.at(-1).text();assert(transcript.includes('https://example.org/alpha')&&!transcript.includes('SYNTHETIC_PRIVATE_TOKEN'),'transcript-keeps-citations-not-token');
 let release;reply=()=>new Promise(r=>release=r);$('search').checked=false;$('search').dispatchEvent(new Event('change'));fill('message','Sent draft');send();await wait(()=>!!release);fill('message','New unsent draft');release({ok:true,json:async()=>fixture()});await wait(()=>!$('send').disabled);
 assert($('message').value==='New unsent draft','late-answer-does-not-erase-new-typing');
 release=null;send();await wait(()=>!!release);$('clear').click();release({ok:true,json:async()=>fixture()});await new Promise(r=>setTimeout(r,30));
 assert($('conversation').children.length===0&&!$('send').disabled,'clear-discards-late-reply-and-sensitive-context');
 change('language','fa');assert(document.documentElement.dir==='rtl'&&$('send').textContent==='ارسال','persian-interface-and-reading-direction');
 reply=async()=>{const r=fixture();r.answer='نمونه '.repeat(250);r.sources[0].excerpt='زمینه '.repeat(300);return {ok:true,json:async()=>r}};
 for(let i=0;i<10;i++){fill('message','پرسش '.repeat(280));send();await wait(()=>!$('send').disabled)}
 assert(new TextEncoder().encode(JSON.stringify(calls.at(-1).payload)).length<=60000,'long-persian-context-respects-byte-budget');
 assert(calls.at(-1).payload.messages.at(-1).content==='پرسش '.repeat(280).trim(),'byte-budget-keeps-latest-human-message');
 assert(localStorage.length===0&&sessionStorage.length===0,'no-persistent-chat-or-token-storage');
 $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,provider_requests:0,authority:'none'});
}catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message)})}
});
"""

def main():
    root=Path(__file__).resolve().parents[1]
    html=(root/'web/research-chat.html').read_text()
    page=html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>').encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200);self.send_header('content-type','text/html;charset=utf-8');self.end_headers();self.wfile.write(page)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    browser=next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium') if shutil.which(n)),None)
    if not browser:raise RuntimeError('real-browser-required')
    reports=[]
    try:
        with tempfile.TemporaryDirectory(prefix='nexus-research-browser-') as td:
            for name,dimensions in [('narrow','500,980'),('wide','1280,980')]:
                result=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,
                    f'http://127.0.0.1:{server.server_port}/',str(Path(td)/name),dimensions,'30000','30000'],
                    capture_output=True,text=True,timeout=75)
                if result.returncode:raise RuntimeError('browser-runner-failed-'+result.stderr[-1200:])
                report=json.loads(result.stdout)
                if report.get('status')!='PASS':raise RuntimeError('research-chat-browser-'+str(report.get('reason')))
                assert len(report['checks'])>=20 and report['provider_requests']==0
                reports.append(report)
    finally:server.shutdown();server.server_close()
    print(json.dumps({'status':'PASS','schema':'nexus.research-chat.browser.v1','reports':reports}))
if __name__=='__main__':main()
