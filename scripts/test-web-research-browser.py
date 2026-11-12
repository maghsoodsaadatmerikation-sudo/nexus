#!/usr/bin/env python3
"""Real disposable browser acceptance for consent-gated external web research."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id), checks=[];
 const verify=(good,label)=>{if(!good)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$('web-search-link').dataset.synthetic='true';$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const choose=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 let consent=false,prompts=0,appFetches=0,external=[],downloads=[];
 window.confirm=()=>{prompts++;return consent};
 window.fetch=()=>{appFetches++;throw Error('unexpected-application-network')};
 const nativeUrl=URL.createObjectURL,blobs=new Map();
 URL.createObjectURL=blob=>{const url=nativeUrl(blob);blobs.set(url,blob);return url};
 HTMLAnchorElement.prototype.click=function(){
  if(this.download)downloads.push({name:this.download,blob:blobs.get(this.href)});
  else external.push({href:this.href,target:this.target,rel:this.rel,referrer:this.referrerPolicy});
 };
 const submit=id=>$(id).dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 const snap=async()=>{const n=downloads.length;$('export').click();verify(downloads.length===n+1,'snapshot-export-available');return downloads.at(-1).blob.text()};
 try{
  verify(document.documentElement.lang==='en'&&$('web-research-title').textContent==='Internet research and search','english-first-search-panel');
  verify($('web-search-engine').options.length===16,'fifteen-builtins-plus-custom-provider');
  verify($('web-search-link').children.length===0&&external.length===0,'no-automatic-search-or-navigation');
  const query='فارسی quantum & neuroscience 😀';
  fill('web-search-query',query);
  $('web-search-go').click();
  verify(external.length===0&&prompts===1&&$('web-search-state').textContent.includes('Cancelled'),
    'explicit-cancel-sends-no-search');
  consent=true;$('web-search-go').click();
  verify(external.length===1&&new URL(external[0].href).searchParams.get('q')===query,
    'unicode-query-exactly-encoded-for-google');
  verify(external[0].target==='_blank'&&external[0].rel.includes('noopener')&&
    external[0].rel.includes('noreferrer')&&external[0].referrer==='no-referrer',
    'third-party-handoff-has-no-opener-or-referrer');
  verify($('web-search-link').querySelector('a')?.hostname==='www.google.com',
    'prepared-link-remains-available-if-popup-blocked');
  choose('web-search-engine','duckduckgo');$('web-search-go').click();
  verify(new URL(external.at(-1).href).hostname==='duckduckgo.com'&&
    new URL(external.at(-1).href).searchParams.get('q')===query,
    'second-independent-search-provider');
  choose('web-search-engine','custom');
  verify(!$('web-search-custom-wrap').hidden,'custom-template-controls-visible');
  fill('web-search-custom','https://example.org/find?term={searchTerms}&lang=fa');
  $('web-search-go').click();
  verify(new URL(external.at(-1).href).hostname==='example.org'&&
    new URL(external.at(-1).href).searchParams.get('term')===query&&
    new URL(external.at(-1).href).searchParams.get('lang')==='fa',
    'custom-https-template-replaces-query-only');
  let before=external.length;
  for(const invalid of ['http://example.org/search?q={searchTerms}',
     'https://127.0.0.1/search?q={searchTerms}',
     'https://localhost/search?q={searchTerms}',
     'https://example.org/search?q=x',
     'https://example.org/search/{searchTerms}',
     'https://user:secret@example.org/search?q={searchTerms}',
     'https://example.org/search?q={searchTerms}&x={searchTerms}',
     'javascript://example.org/?q={searchTerms}']){
    fill('web-search-custom',invalid);$('web-search-go').click();
    if(external.length!==before)throw Error('unsafe-custom-provider-was-opened');
  }
  verify(external.length===before,'eight-unsafe-custom-templates-rejected');
  fill('web-search-custom','https://example.org/search?q={searchTerms}');
  fill('web-search-query','a'.repeat(251));$('web-search-go').click();
  verify(external.length===before,'oversized-query-rejected');
  fill('web-search-query','search without workspace secrets');
  $('web-search-go').click();
  verify(external.length===before+1&&!external.at(-1).href.includes('password'),
    'manual-query-only-no-secret-exfiltration');
  before=external.length;
  fill('web-direct-url','javascript:alert(1)');$('web-open-url').click();
  fill('web-direct-url','https://192.168.1.1/');$('web-open-url').click();
  fill('web-direct-url','http://example.org');$('web-open-url').click();
  verify(external.length===before,'unsafe-direct-navigation-rejected');
  fill('web-direct-url','https://example.net/path?x=foo');
  $('web-open-url').click();
  verify(external.length===before+1&&new URL(external.at(-1).href).hostname==='example.net',
    'explicit-public-https-navigation-allowed');
  fill('question','Synthetic question unconnected to search');submit('ask-form');
  const savedBefore=await snap();
  fill('web-source-url','https://localhost/private');fill('web-source-excerpt','Fake text');
  $('web-source-draft').click();
  verify($('claim').value===''&&$('web-source-state').textContent.includes('valid public HTTPS'),
    'private-source-rejected-without-new-claim');
  fill('web-source-url','https://example.org/research?edition=2026');
  const content='Unverified research note <img src=x onerror=alert(1)>';
  fill('web-source-excerpt',content);
  $('web-source-draft').click();
  verify($('claim').value===content&&$('source').value==='https://example.org/research?edition=2026'&&
    $('origin').value==='external_evidence'&&$('uncertainty').value==='unknown',
    'manually-reviewed-text-becomes-unregistered-evidence-draft');
  verify(!$('draft-notice').hidden&&!document.querySelector('#web-source-state img'),
    'untrusted-research-remains-inert-and-unregistered');
  const afterDraft=await snap();
  verify(afterDraft===savedBefore,'research-does-not-change-committed-workspace');
  consent=false;fill('web-search-query','private ?token=& test');
  $('web-search-go').click();
  verify(external.length===before+1,'cancelled-search-does-not-leak-private-query');
  choose('ui-language','fa');
  verify(document.documentElement.dir==='rtl'&&$('web-research-title').textContent==='پژوهش اینترنتی و جست‌وجو',
    'persian-language-search-controls');
  verify($('web-search-query').value==='private ?token=& test'&&
    $('web-search-engine').querySelector('option[value="custom"]').textContent==='موتور HTTPS سفارشی',
    'language-switch-preserves-private-query-and-translates-provider-choice');
  choose('ui-language','en');
  $('web-research-clear').click();
  verify($('web-search-query').value===''&&$('web-source-excerpt').value===''&&
    $('web-search-link').children.length===0,'private-research-fields-can-be-cleared');
  verify($('claim').value===content,'clear-does-not-delete-unregistered-draft');
  verify(await snap()===savedBefore,'clear-does-not-alter-committed-workspace');
  verify(appFetches===0&&localStorage.length===0,'no-background-fetch-or-plaintext-local-storage');
  verify(!document.querySelector('iframe')&&external.every(x=>x.target==='_blank'&&
    x.rel.includes('noopener')&&x.rel.includes('noreferrer')),'no-iframe-or-third-party-opener');
  $('nexus-browser-result').textContent=JSON.stringify({
    status:'PASS',checks,width:innerWidth,network_requests:appFetches,
    external_handoffs:external.length,authority:'none',production_mutation:false,real_web_results_tested:false});
 }catch(error){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',
    reason:String(error.message).replace(/[^a-z0-9-_]/gi,'')});
 }
});
"""

def main():
    root=Path(__file__).resolve().parents[1]
    html=(root/'web/offline-pilot.html').read_text(encoding='utf8')
    assert "connect-src 'none'" in html and 'NEXUS_WEB_RESEARCH_BEGIN' in html
    browser=next((shutil.which(x) for x in ('google-chrome','google-chrome-stable','chromium')
                  if shutil.which(x)),None)
    if not browser:raise RuntimeError('real-browser-required')
    page=html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    reports=[]
    with tempfile.TemporaryDirectory(prefix='nexus-web-research-') as td:
        source=Path(td)/'index.html';source.write_text(page,encoding='utf-8')
        for name,size in [('narrow','500,980'),('wide','1280,980')]:
            run=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),
                 browser,source.as_uri(),str(Path(td)/name),size,'60000','30000'],
                 capture_output=True,text=True,timeout=120)
            if run.returncode:raise RuntimeError('real-browser-runner-failed')
            report=json.loads(run.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))<25:
                raise RuntimeError('web-research-rejected-'+str(report.get('reason','check-count')))
            assert (name=='narrow')==(report['width']<=760)
            assert report['network_requests']==0 and report['authority']=='none'
            reports.append({'layout':name,**report})
    print(json.dumps({'schema':'nexus.pilot-19.web-research-witness.v1',
                      'status':'PASS','reports':reports,'authority':'none'}))

if __name__=='__main__':main()
