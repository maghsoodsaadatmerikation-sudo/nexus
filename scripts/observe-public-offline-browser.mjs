#!/usr/bin/env node
// Pilot 10: independent REAL PUBLIC HTTPS browser acceptance.
// Synthetic Chromium interaction only. No operator credentials, backend writes,
// production files, Railway volume access, or user-provided personal data.
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const ORIGIN='https://nexus-offline-pilot.onrender.com/';
const FAVICON='https://nexus-offline-pilot.onrender.com/favicon.ico';
const PUBLIC_APP_ASSETS=new Set([
  ORIGIN,FAVICON,
  ORIGIN+'manifest.json',
  ORIGIN+'icons/nexus-192.png',
  ORIGIN+'icons/nexus-512.png'
]);
const REPORT_MODE=process.env.NEXUS_PUBLIC_REPORT==='true';
const EXPECTED_CHECKS=REPORT_MODE?17:46;
const MIN_DOCUMENTS=REPORT_MODE?1:2;
const REPO_ROOT=new URL('../',import.meta.url);
const sha256=value=>createHash('sha256').update(value).digest('hex');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const assert=(condition,label)=>{if(!condition)throw Error(label)};
const GITHUB_ONLY=process.env.GITHUB_ACTIONS==='true' && /^[0-9]+$/.test(process.env.GITHUB_RUN_ID||'');
const BROWSER=process.env.NEXUS_PUBLIC_CHROME;
if(!GITHUB_ONLY || !BROWSER || typeof WebSocket==='undefined' ||
   process.env.RAILWAY_TOKEN || process.env.RAILWAY_API_TOKEN ||
   process.env.NEXUS_API_TOKEN || process.env.RENDER_API_KEY)
  throw Error('public-witness-requires-ephemeral-github-chromium-and-no-operator-credentials');

const expected=await readFile(new URL('../web/offline-pilot.html',import.meta.url));
assert(expected.length>1000 && expected.length<=300000,'expected-source-size');
const expectedDigest=sha256(expected);
const pythonTest=await readFile(new URL(REPORT_MODE?'./test-decision-report-browser.py':'./test-offline-pilot-browser.py',import.meta.url),'utf8');
const match=pythonTest.match(/WITNESS = r"""([\s\S]*?)"""/);
assert(match && match[1].length>1000 && match[1].includes(REPORT_MODE?'report-user-content-is-inert-text':'real-page-reload-requires-passphrase-and-recovers'),
  'exact-real-browser-witness-unavailable');

function verifyDocument(status,mime,bytes,redirected=false){
  assert(!redirected && status===200,'public-http-not-200-or-redirect');
  assert(/^text\/html(?:\s*;|$)/i.test(mime),'public-content-type');
  assert(Buffer.compare(bytes,expected)===0,'public-html-differs-from-exact-candidate');
  assert(bytes.includes(Buffer.from("connect-src 'none'")),'public-csp-missing');
  assert(bytes.includes(Buffer.from('nexus.offline-pilot.v1')),'public-schema-missing');
  return sha256(bytes);
}
function verifyRequest(url,method){
  assert(method==='GET' && PUBLIC_APP_ASSETS.has(url),
    'unexpected-browser-network-request');
}
async function independentPublicGet(){
  const r=await fetch(ORIGIN,{redirect:'manual',headers:{Accept:'text/html'},
    signal:AbortSignal.timeout(20000)});
  const bytes=Buffer.from(await r.arrayBuffer());
  return verifyDocument(r.status,r.headers.get('content-type')||'',bytes,r.redirected);
}
async function poll(action,ms,label){
  const end=Date.now()+ms;
  while(Date.now()<end){
    const value=await action();
    if(value)return value;
    await delay(80);
  }
  throw Error(label);
}
async function layoutWitness(layout){
  const dimensions=layout==='narrow'?'500,980':'1280,980';
  const root=await mkdtemp(path.join(os.tmpdir(),'nexus-public-witness-'));
  const profile=path.join(root,'chrome-profile');
  const child=spawn(BROWSER,[
    '--headless','--no-sandbox','--disable-dev-shm-usage',
    '--disable-background-networking','--disable-extensions',
    '--no-first-run','--no-default-browser-check',
    '--force-device-scale-factor=1','--hide-scrollbars',
    '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
    '--user-data-dir='+profile,'--window-size='+dimensions,'about:blank'
  ],{stdio:['ignore','ignore','ignore']});
  let socket,serial=0,stage='browser-boot';
  const pending=new Map(),network=[],documents=[];
  let firstError=null;
  child.on('error',()=>{firstError='browser-process-launch'});
  const rpc=(method,params={},timeout=15000)=>new Promise((resolve,reject)=>{
    const id=++serial,timer=setTimeout(()=>{pending.delete(id);reject(Error('cdp-timeout'))},timeout);
    pending.set(id,{resolve:x=>{clearTimeout(timer);resolve(x)},
      reject:x=>{clearTimeout(timer);reject(x)}});
    socket.send(JSON.stringify({id,method,params}));
  });
  try{
    const port=await poll(async()=>{
      if(firstError||child.exitCode!==null)throw Error('chrome-exit-before-debugger');
      try{const text=await readFile(path.join(profile,'DevToolsActivePort'),'utf8');
        const n=text.split('\n')[0];return /^\d+$/.test(n)?n:null}catch{return null}
    },25000,'chrome-no-private-debugger');
    const target=await poll(async()=>{
      try{
        const resp=await fetch('http://127.0.0.1:'+port+'/json/list',
          {signal:AbortSignal.timeout(2000)});
        if(!resp.ok)return null;
        const list=await resp.json();
        return list.find(x=>x.type==='page'&&x.url==='about:blank');
      }catch(error){
        // Chromium can publish DevToolsActivePort before the *local*
        // debugger HTTP server is ready. Retry only transient connection
        // and timeout errors inside the existing bounded 15-second poll;
        // never retry a failed witness, public HTTPS check or data assertion.
        if(error?.name==='TimeoutError'||error instanceof TypeError)return null;
        throw error;
      }
    },15000,'chrome-no-private-target');
    const endpoint=new URL(target.webSocketDebuggerUrl);
    assert(endpoint.hostname==='127.0.0.1'&&endpoint.port===port,'external-debugger-refused');
    stage='browser-witness';
    socket=new WebSocket(endpoint);
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('chrome-debugger-connection-timeout')),5000);
      socket.addEventListener('open',()=>{clearTimeout(timer);resolve()},{once:true});
      socket.addEventListener('error',()=>{clearTimeout(timer);reject(Error('chrome-debugger-connection-failed'))},{once:true});
    });
    socket.addEventListener('message',event=>{
      let data;try{data=JSON.parse(event.data)}catch{return}
      if(data.id!==undefined){
        const req=pending.get(data.id);
        if(req){pending.delete(data.id);data.error?req.reject(Error('cdp-error')):req.resolve(data.result)}
        return;
      }
      if(data.method==='Network.requestWillBeSent'){
        const r=data.params?.request;
        if(r&&/^https?:/.test(r.url))network.push({url:r.url,method:r.method});
      }
      if(data.method==='Network.responseReceived'){
        const r=data.params?.response;
        if(data.params?.type==='Document'&&r?.url===ORIGIN){
          documents.push({requestId:data.params.requestId,status:r.status,mime:r.mimeType});
        }
      }
    });
    socket.addEventListener('close',()=>{for(const x of pending.values())x.reject(Error('cdp-close'));pending.clear()});
    await rpc('Page.enable');
    await rpc('Network.enable',{maxTotalBufferSize:5000000,maxResourceBufferSize:1000000});
    await rpc('Network.setCacheDisabled',{cacheDisabled:true});
    await rpc('Page.setDownloadBehavior',{behavior:'deny'});
    const injection="document.addEventListener('DOMContentLoaded',()=>{"+
      "const n=document.createElement('pre');n.id='nexus-browser-result';"+
      "n.hidden=true;document.body.appendChild(n)},{once:true});\n"+match[1];
    await rpc('Page.addScriptToEvaluateOnNewDocument',{source:injection});
    const navigated=await rpc('Page.navigate',{url:ORIGIN});
    assert(!navigated.errorText,'public-navigation-error');
    const report=await poll(async()=>{
      try{
        const result=await rpc('Runtime.evaluate',{expression:
          "document.getElementById('nexus-browser-result')?.textContent || ''",
          returnByValue:true},10000);
        if(result.exceptionDetails)return null;
        const value=result.result?.value;
        if(!value)return null;
        const parsed=JSON.parse(value);
        if(parsed.status!=='PASS')throw Error('real-public-browser-contract-failed');
        return parsed;
      }catch(error){
        // A Runtime execution context legitimately disappears while the
        // app's encrypted-restore test performs a real page reload.
        if(error.message==='cdp-error'||error.message==='cdp-timeout')return null;
        throw error;
      }
    },180000,'real-public-browser-did-not-complete');
    assert(report.checks?.length===EXPECTED_CHECKS&&report.network_requests===0&&
      report.production_verified===false&&report.authority==='none',
      'live-browser-checks-or-authority-invalid');
    assert((layout==='narrow')===(report.width<=760),'live-browser-viewport-invalid');
    assert(documents.length>=MIN_DOCUMENTS&&network.length>=MIN_DOCUMENTS,'not-two-real-public-document-loads');
    for(const x of network)verifyRequest(x.url,x.method);
    for(const x of documents){
      assert(x.status===200,'public-browser-document-http-status');
      assert(/^text\/html(?:\s*;|$)/i.test(x.mime||''),
        'public-browser-document-content-type');
    }
    const last=documents[documents.length-1];
    const body=await rpc('Network.getResponseBody',{requestId:last.requestId});
    const downloaded=Buffer.from(body.body,body.base64Encoded?'base64':'utf8');
    assert(downloaded.length===expected.length&&sha256(downloaded)===expectedDigest,
      'chrome-rendered-document-bytes-differ-from-source');
    return {layout,width:report.width,checks:report.checks.length,
      real_reload_verified:report.checks.includes('real-page-reload-requires-passphrase-and-recovers'),
      test_fixture_only:true,document_responses:documents.length,
      requested_paths_count:network.length,network_attempts_by_app:report.network_requests,
      browser_document_sha256:sha256(downloaded),status:'PASS'};
  }catch(error){
    // Fixed failure label only, no browser content, credential or workspace.
    process.stderr.write(JSON.stringify({stage,error_type:'PUBLIC_BROWSER_FAIL_CLOSED',layout})+'\n');
    throw error;
  }finally{
    if(socket?.readyState===WebSocket.OPEN){
      try{await Promise.race([rpc('Browser.close',{},1000),delay(1100)])}catch{}
      socket.close();
    }
    if(child.pid&&child.exitCode===null){child.kill('SIGTERM');await delay(250)}
    if(child.pid&&child.exitCode===null)child.kill('SIGKILL');
    await rm(root,{recursive:true,force:true});
  }
}
async function main(){
  assert(verifyDocument(200,'text/html',expected)===expectedDigest,'self-good');
  for(const bad of [404,302]){let failed=false;
    try{verifyDocument(bad,'text/html',expected)}catch{failed=true}
    assert(failed,'negative-status-fixture-not-rejected')}
  for(const bad of [{s:200,m:'application/json',b:expected},
    {s:200,m:'text/html',b:Buffer.concat([expected,Buffer.from('x')])}]){
    let failed=false;try{verifyDocument(bad.s,bad.m,bad.b)}catch{failed=true}
    assert(failed,'negative-byte-or-mime-fixture-not-rejected')}
  for(const [u,method] of [[ORIGIN,'POST'],['https://untrusted.example/','GET']]){
    let failed=false;try{verifyRequest(u,method)}catch{failed=true}
    assert(failed,'network-allowlist-negative-fixture-not-rejected')}
  const getSha=await independentPublicGet();
  const reports=[];
  for(const layout of ['narrow','wide'])reports.push(await layoutWitness(layout));
  process.stdout.write(JSON.stringify({
    schema:REPORT_MODE?'nexus.public-pilot.decision-report-acceptance.v1':'nexus.public-pilot.browser-acceptance.v1',status:'PASS',
    source_sha256:expectedDigest,independent_get_sha256:getSha,
    origin:ORIGIN,checks_per_layout:EXPECTED_CHECKS,negative_local_fixtures:6,
    report:reports,synthetic_only:true,real_human_tested:false,
    authenticated_rust_tested:false,production_restore_tested:false,
    authority:'none',production_mutation:false
  })+'\n');
}
await main();
