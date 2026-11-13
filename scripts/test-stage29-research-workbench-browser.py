#!/usr/bin/env python3
"""Real Chromium test: a consent-controlled multi-query evidence ledger."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location("nexus_browser_fixture",
    Path(__file__).with_name("test-research-chat-browser.py"))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
fixture.WITNESS=r"""
window.addEventListener('load',async()=>{
const e=id=>document.getElementById(id),checks=[],requests=[];
const check=(yes,key)=>{if(!yes)throw Error(key);checks.push(key)};
const input=(id,value)=>{e(id).value=value;e(id).dispatchEvent(new Event('input',{bubbles:true}))};
const wait=async f=>{for(let i=0;i<500;i++){if(f())return;await new Promise(r=>setTimeout(r,10))}throw Error('timeout')};
const response=()=>({schema:'nexus.research-chat.v1',authority:'none',judgment_changed:false,
 sources:[{id:'S1',title:'<img src=x onerror=alert(1)> Synthetic source',
 url:'https://example.org/synthetic',excerpt:'Test finding with no verified inference.',
 origin:'public_web_excerpt',provider:'wikipedia',retrieved_at_unix:1734000000},
 {id:'S2',title:'Untrusted bad link',url:'javascript:alert(1)',excerpt:'should not be adopted',origin:'synthetic',provider:'test'},
 {id:'S3',title:'Different source',url:'https://source.test.org/nexus',excerpt:'Dissenting finding',origin:'public_web_excerpt',provider:'duckduckgo',retrieved_at_unix:null}],
 providers:[{provider:'wikipedia',status:'ok'}],unknowns:['Verification needed']});
let remote=async()=>({ok:true,json:async()=>response()});
window.fetch=async(url,options)=>{requests.push({url,options,payload:JSON.parse(options.body)});return remote(options)};
window.confirm=()=>true;
const oldCreate=URL.createObjectURL,files=[];
URL.createObjectURL=b=>{files.push(b);return oldCreate(b)};
HTMLAnchorElement.prototype.click=function(){};
try{
 check(requests.length===0&&!record.length,'no-automatic-research');
 check(!e('consent').checked,'no-borrowed-query-consent');
 check(!e('export').disabled===false,'export-blocked-before-evidence');
 input('token','SYNTHETIC_GATEWAY_SECRET');input('question','My unverified research question');input('query','my first public query');
 e('search').click();check(requests.length===0,'query-needs-approval');
 e('consent').checked=true;e('search').click();await wait(()=>!busy);
 check(requests.length===1&&requests[0].url==='/v1/research-chat','one-approved-same-origin-call');
 check(requests[0].options.credentials==='omit'&&requests[0].options.cache==='no-store',
    'no-ambient-credentials-or-caching');
 check(requests[0].payload.search===true&&requests[0].payload.consent===true&&
       requests[0].payload.query==='my first public query','only-exact-allowed-query');
 check(requests[0].payload.reviewed_sources.length===0&&requests[0].payload.context_sources.length===0,
   'no-implicit-history-or-source-sharing');
 check(requests[0].payload.messages.length===1&&requests[0].payload.messages[0].content==='My unverified research question',
   'top-level-question-only-to-own-gateway');
 check(record.length===1&&record[0].sources.length===2,'hostile-javascript-source-link-rejected');
 check(e('sources').querySelectorAll('img').length===0&&e('sources').textContent.includes('<img'),
    'malicious-source-title-displayed-as-inert-text');
 check(e('sources').querySelectorAll('a[href^=javascript]').length===0,'no-dangerous-resource-links');
 check(e('sources').querySelector('a').rel.includes('noreferrer'),
   'safe-source-referrer-boundary');
 check(e('sources').textContent.includes('Verification needed')&&
       e('sources').textContent.includes('2024-12-12'),
   'uncertainty-and-retrieval-timestamp-not-hidden');
 check(!e('consent').checked,'consent-consumed-once');
 e('search').click();check(requests.length===1,'second-search-needs-separate-consent');
 input('query','second query');e('consent').checked=true;e('search').click();await wait(()=>!busy);
 check(record.length===2&&requests.length===2,'second-query-independently-approved');
 check(markdown().includes('Source-by-source')===false&&markdown().includes('URL: https://example.org/synthetic'),
   'dossier-has-original-verifiable-source-urls');
 check(markdown().includes('Verification needed')&&markdown().includes('No verified factual conclusion'),
   'report-does-not-fake-corroboration');
 check(!markdown().includes('SYNTHETIC_GATEWAY_SECRET'),'report-excludes-authentication-token');
 input('notes','My private notes');e('export').click();
 check(files.length===1,'plaintext-export-requires-user-action');
 check((await files[0].text()).includes('My private notes'),'human-notes-explicitly-exported');
 let resolve;remote=()=>new Promise(fn=>{resolve=fn});
 input('query','cancelled query');e('consent').checked=true;e('search').click();
 await wait(()=>!!resolve);e('stop').click();resolve({ok:true,json:async()=>response()});
 await new Promise(r=>setTimeout(r,20));
 check(record.length===2,'late-search-result-discarded-after-cancellation');
 input('question','Different question');input('query','unapproved');e('consent').checked=true;e('search').click();
 check(requests.length===3,'changed-question-refuses-new-search-without-reset');
 e('clear').click();check(record.length===0&&e('notes').value==='','clear-removes-dossier-and-notes');
 input('token','CHANGED_GATEWAY_SECRET');check(record.length===0,'token-rotation-clears-data');
 e('language').value='fa';e('language').dispatchEvent(new Event('change'));
 check(document.documentElement.dir==='rtl'&&e('search').textContent.includes('جست'),'persian-rtl-ui');
 check(localStorage.length===0&&sessionStorage.length===0,'no-plaintext-persistence');
 e('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,provider_requests:0,
 mode:'synthetic_approved_research_sources_only',actual_provider_checked:false});
}catch(err){e('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(err?.message||err),checks})}
});
"""
if __name__=="__main__":
    fixture.main("web/research-workbench.html")
