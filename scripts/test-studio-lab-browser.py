#!/usr/bin/env python3
"""Real Chromium lab witness. A local sentinel must never receive sandbox traffic."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];const assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};
 const fill=(id,v)=>{$(id).value=v;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async f=>{for(let i=0;i<400;i++){if(f())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const snapshot=()=>NexusStudioUI.snapshot();window.confirm=()=>true;
 const native=window.fetch;let searches=0,late=false,release;
 const fixture={query:{pages:{42:{pageid:42,title:'<img src=x> Source title',extract:'An unverified external excerpt.'}}}};
 window.fetch=async(url,options)=>{if(String(url).startsWith('https://en.wikipedia.org/')){searches++;assert(options.credentials==='omit'&&options.redirect==='error','public-query-omits-credentials-and-redirects');assert(!String(url).includes('TRANSIENT_SECRET'),'query-does-not-copy-gateway-token');const response=()=>new Response(JSON.stringify(fixture));if(late)return new Promise(r=>release=()=>r(response()));return response()}if(String(url).startsWith('https://api.crossref.org/')){searches++;return new Response(JSON.stringify({message:{items:[{DOI:'10.1234/example',title:['Synthetic article'],author:[{given:'A',family:'B'}],published:{'date-parts':[[2020]]},type:'journal-article'}]}}))}return native(url,options)};
 try{
  fill('project-title','PRIVATE LAB PROJECT');$('new-project').click();fill('gateway-token','TRANSIENT_SECRET_NOT_FOR_RESEARCH');
  fill('research-query','explicit public query');$('research-run').click();assert(searches===0,'no-search-without-consent');$('research-consent').checked=true;$('research-run').click();await wait(()=>$('research-cards').children.length===1);
  assert($('research-cards').textContent.includes('unverified external excerpt')&&!$('research-cards').querySelector('img'),'source-text-is-inert');assert($('research-cards').querySelector('a').rel.includes('noreferrer'),'source-links-do-not-share-referrer');
  $('research-cards').querySelector('button').click();assert(snapshot().projects[0].sources[0].text.includes('https://en.wikipedia.org/?curid=42')&&snapshot().projects[0].sources[0].text.includes('Query: explicit public query'),'keeping-source-is-explicit-and-provenanced');
  $('research-consent').checked=true;fill('research-query','new query');assert(!$('research-consent').checked,'query-change-revokes-consent');
  late=true;$('research-consent').checked=true;$('research-run').click();await wait(()=>release);fill('research-query','different query');release();await new Promise(r=>setTimeout(r,40));assert(!$('research-cards').children.length,'late-research-result-discarded');late=false;
  $('research-provider').value='crossref';$('research-provider').dispatchEvent(new Event('change'));$('research-consent').checked=true;$('research-run').click();await wait(()=>$('research-cards').children.length===1);assert($('research-cards').textContent.includes('bibliographic-metadata-only'),'article-metadata-not-claimed-full-text');
  $('code-sample').click();$('code-run').click();assert(!$('code-result').textContent,'no-code-execution-without-consent');$('code-consent').checked=true;$('code-run').click();await wait(()=>$('code-result').textContent.includes('Local calculation'));assert($('code-console').textContent.includes('sum'),'local-code-really-computes');
  $('chart-use').click();$('chart-draw').click();assert(!$('chart').hidden&&$('chart').width===1200,'code-result-renders-chart');const color=$('chart').getContext('2d').getImageData(600,200,1,1).data;assert(color[1]>color[0]&&color[3]===255,'chart-has-rendered-data-pixels');
  const runner=new NexusLab.Sandbox();
  const isolated=JSON.parse(await runner.run("let storage;try{indexedDB.open('nexus-studio-v1');storage='OPEN'}catch(e){storage=e.name}return {document:typeof document,parent:typeof parent,process:typeof process,studio:typeof NexusStudio,storage,origin:self.location.origin};"));
  assert(isolated.document==='undefined'&&isolated.parent==='undefined'&&isolated.process==='undefined'&&isolated.studio==='undefined','worker-cannot-access-page-or-host');assert(isolated.storage==='SecurityError'&&isolated.origin==='null','opaque-origin-blocks-archive-storage');
  const control=await native(location.origin+'/probe');assert(control.ok,'local-sentinel-control-is-reachable');
  const network=await runner.run("try{await fetch(input);return 'LEAK'}catch{return 'BLOCKED'}",location.origin+'/probe');assert(network==='"BLOCKED"','sandbox-network-blocked-by-csp');
  const started=performance.now();let timed=false;try{await runner.run('while(true){}')}catch(e){timed=e.message==='execution-timeout'}assert(timed&&performance.now()-started<6000,'infinite-code-is-terminated');
  let capped=false;try{await runner.run("console.log('x'.repeat(100000));return 'bad'")}catch{capped=true}assert(capped,'oversized-output-is-rejected');
  assert(await runner.run('return 2+2')==='4','sandbox-remains-usable-after-failures');assert(!document.querySelector('iframe'),'sandbox-contexts-removed-after-run');
  fill('chart-json','{"type":"bar","labels":["a"],"values":[1e99]}');$('chart-draw').click();assert($('chart').hidden&&$('chart-status').textContent,'invalid-chart-not-rendered');
  $('lock').click();assert(!$('code').value&&!$('code-input').value&&!$('code-result').textContent&&!$('research-query').value&&!$('research-cards').textContent&&$('chart').width===1,'lock-clears-lab-data-and-pixels');
  assert(snapshot().projects.length===0,'lock-clears-project-state');assert(document.documentElement.scrollWidth<=innerWidth+2,'lab-responsive-without-horizontal-scroll');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,authority:'none',real_model_tested:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""

def main():
 root=Path(__file__).resolve().parents[1]
 browser=next((shutil.which(n) for n in ('google-chrome','chromium') if shutil.which(n)),None)
 if not browser:raise RuntimeError('Chromium required')
 page=(root/'web/studio.html').read_text().replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
 class Handler(BaseHTTPRequestHandler):
  probes=0
  def log_message(self,*args):pass
  def do_GET(self):
   if self.path=='/probe':Handler.probes+=1;raw=b'control'
   elif self.path=='/index.html':raw=page.encode()
   else:self.send_response(404);self.end_headers();return
   self.send_response(200);self.send_header('Content-Type','text/html' if self.path=='/index.html' else 'text/plain');self.send_header('Access-Control-Allow-Origin','*');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  reports=[]
  with tempfile.TemporaryDirectory(prefix='nexus-lab-browser-') as td:
   for label,size in [('narrow','420,1000'),('wide','1280,1000')]:
    before=Handler.probes
    r=subprocess.run(['node',str(root/'scripts/workspace-browser-runner.mjs'),browser,f'http://127.0.0.1:{server.server_port}/index.html',str(Path(td)/label),size,'60000','30000'],capture_output=True,text=True,timeout=130)
    if r.returncode:raise RuntimeError('browser-runner-failed-'+r.stderr[-1000:])
    result=json.loads(r.stdout)
    if result.get('status')!='PASS':raise RuntimeError(json.dumps(result))
    if Handler.probes-before!=1:raise RuntimeError('sandbox-contacted-network-sentinel')
    reports.append({'layout':label,**result,'sandbox_network_requests':0})
  print(json.dumps({'status':'PASS','reports':reports}))
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
if __name__=='__main__':main()
