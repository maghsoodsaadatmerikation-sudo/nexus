#!/usr/bin/env node
// Pilot 12: disposable real Chromium, local HTTP origin, then true CDP offline.
// Not a real Android hardware test, no Railway access, no operator data.
import {spawn} from 'node:child_process';
import {readFile, mkdtemp, rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {tmpdir} from 'node:os';
import path from 'node:path';

const PUBLIC_MODE=process.env.NEXUS_PWA_PUBLIC==='true';
if(PUBLIC_MODE && (process.env.GITHUB_ACTIONS!=='true'||
    !/^[0-9]+$/.test(process.env.GITHUB_RUN_ID||'')))
  throw Error('public-origin-test-requires-ephemeral-GitHub-runner');
const ORIGIN=PUBLIC_MODE?
  'https://nexus-offline-pilot.onrender.com/':'http://127.0.0.1:8765/';
const browser=process.env.NEXUS_PWA_CHROME;
if(!browser||typeof WebSocket==='undefined' || process.env.RAILWAY_TOKEN ||
   process.env.NEXUS_API_TOKEN || process.env.RENDER_API_KEY)
  throw Error('disposable-no-credential-chromium-required');
const sha=buf=>createHash('sha256').update(buf).digest('hex');
const sourceHtml=await readFile(new URL('../web/offline-pilot.html',import.meta.url));
const shell=await readFile(new URL('../public/service-worker.js',import.meta.url),'utf8');
const sourceDigest=sha(sourceHtml);
const assert=(x,reason)=>{if(!x)throw Error(reason)};
assert(shell.includes("const EXPECTED_SHA256='"+sourceDigest+"'"),
 'service-worker-pinned-html-mismatch');
const manifest=JSON.parse(await readFile(new URL('../public/manifest.json',import.meta.url),'utf8'));
assert(manifest.start_url==='/'&&manifest.scope==='/'&&manifest.display==='standalone'&&
 manifest.lang===sourceHtml.toString().match(/<html[^>]*lang="([^"]+)"/)[1]&&manifest.icons.length===2,'unsafe-pwa-manifest');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const profile=await mkdtemp(path.join(tmpdir(),'nexus-pwa-private-'));
const child=spawn(browser,[
 '--headless','--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--disable-extensions',
 '--disable-background-networking','--no-first-run','--no-default-browser-check',
 '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
 '--user-data-dir='+profile,'--window-size=500,980','about:blank'
],{stdio:['ignore','ignore','ignore']});
let socket,seq=0,stage='chrome-start',exited=false;
child.on('exit',()=>{exited=true});
const pending=new Map();
const rpc=(method,params={},deadline=10000)=>new Promise((resolve,reject)=>{
 const id=++seq,timeout=setTimeout(()=>{pending.delete(id);reject(Error('local-debugger-timeout'))},deadline);
 pending.set(id,{resolve:r=>{clearTimeout(timeout);resolve(r)},reject:e=>{clearTimeout(timeout);reject(e)}});
 socket.send(JSON.stringify({id,method,params}));
});
async function poll(fn,ms,reason){
 const limit=Date.now()+ms;
 while(Date.now()<limit){
  if(exited)throw Error('chrome-process-exited');
  const value=await fn();if(value)return value;
  await delay(100);
 }
 throw Error(reason);
}
async function js(expression){
 const result=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
 if(result.exceptionDetails)throw Error('javascript-evaluation-rejected');
 return result.result?.value;
}
async function retryJs(expression){
 try{return await js(expression)}catch(e){
  // Reload destroys the current JS execution context. It is safe to
  // retry observation inside the bounded poll, but never failed assertions.
  if(['cdp-failure','javascript-evaluation-rejected'].includes(e.message))return null;
  throw e;
 }
}
const checks=[];
// CDP document-only status records, never request bodies or user data.
const observedDocuments=[];
try{
 const port=await poll(async()=>{
  try{const s=await readFile(path.join(profile,'DevToolsActivePort'),'utf8');
    const n=s.split('\n')[0];return /^\d+$/.test(n)?n:null}
  catch{return null}
 },25000,'private-chrome-port-not-ready');
 const target=await poll(async()=>{
  try{
   const r=await fetch('http://127.0.0.1:'+port+'/json/list',{signal:AbortSignal.timeout(1800)});
   if(!r.ok)return null;
   return (await r.json()).find(x=>x.type==='page'&&x.url==='about:blank');
  }catch(e){if(e?.name==='TimeoutError'||e instanceof TypeError)return null;throw e}
 },15000,'private-chrome-target-not-ready');
 const endpoint=new URL(target.webSocketDebuggerUrl);
 assert(endpoint.hostname==='127.0.0.1'&&endpoint.port===port,'external-debugger-blocked');
 socket=new WebSocket(endpoint);
 await new Promise((res,rej)=>{
  const t=setTimeout(()=>rej(Error('socket-connect-timeout')),5000);
  socket.addEventListener('open',()=>{clearTimeout(t);res()},{once:true});
  socket.addEventListener('error',()=>{clearTimeout(t);rej(Error('socket-connect-error'))},{once:true});
 });
 socket.addEventListener('message',e=>{
  const msg=JSON.parse(e.data),p=pending.get(msg.id);
  if(msg.method==='Network.responseReceived'&&msg.params?.type==='Document'){
    const d=msg.params.response||{};
    observedDocuments.push({public_root:d.url===ORIGIN,
      status:Number(d.status)||0,from_worker:d.fromServiceWorker===true});
  }
  if(!p)return;pending.delete(msg.id);
  msg.error?p.reject(Error('cdp-failure')):p.resolve(msg.result);
 });
 await rpc('Page.enable');await rpc('Network.enable');
 await rpc('Page.addScriptToEvaluateOnNewDocument',{source:"window.addEventListener('DOMContentLoaded',()=>{const el=document.getElementById('ui-language');if(el){el.value='fa';el.dispatchEvent(new Event('change',{bubbles:true}));}},{once:true});"});
 await rpc('Network.setCacheDisabled',{cacheDisabled:true});
 stage='online-bootstrap';
 const initial=await rpc('Page.navigate',{url:ORIGIN});
 assert(!initial.errorText,'local-online-navigation-failed');
 await poll(()=>retryJs("document.readyState==='complete'&&Boolean(document.getElementById('offline-install'))"),12000,'pwa-install-ui-missing');
 checks.push('online-real-chromium-renders-html');
 // The first visit does NOT auto-register a service worker.
 assert(await js("navigator.serviceWorker.getRegistration('/').then(r=>Boolean(r))")===false,
 'auto-registered-worker-without-consent');
 checks.push('no-unconsented-service-worker-registration');
 await js("document.getElementById('offline-install').click();true");
 await poll(()=>retryJs("document.getElementById('offline-install-state')?.textContent.includes('آماده است')"),35000,'opt-in-worker-failed');
 const before=await js("(async()=>{const names=await caches.keys();const reg=await navigator.serviceWorker.getRegistration('/');const cache=await caches.open(names[0]);const keys=await cache.keys();return {names,script:reg?.active?.scriptURL,scope:reg?.scope,controller:Boolean(navigator.serviceWorker.controller),entries:keys.map(k=>k.url),locals:localStorage.length}})()");
 assert(before.names.length===1&&before.names[0].startsWith('nexus-app-shell-v12-')&&
 before.script===ORIGIN+'service-worker.js'&&before.scope===ORIGIN&&
 before.controller===true&&before.entries.length===1&&before.entries[0]===ORIGIN&&
 before.locals===0,'offline-cache-not-code-only-or-active');
 checks.push('opt-in-active-cache-contains-only-public-app-shell');
 const actual=await js("(async()=>{const ns=await caches.keys();const c=await caches.open(ns[0]);const r=await c.match('/');return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await r.arrayBuffer())),x=>x.toString(16).padStart(2,'0')).join('')})()");
 assert(actual===sourceDigest,'cached-shell-differs-from-reviewed-source');
 checks.push('installed-cache-sha256-is-exact-reviewed-html');
 if(process.env.NEXUS_PWA_TAMPER==='true'){
   // Mutate actual Chromium CacheStorage bytes after verified installation.
   // This does not use the VM mock, a network fixture or real user data.
   stage='chromium-cache-tampering';
   const changed=await js("(async()=>{const keys=await caches.keys();const c=await caches.open(keys[0]);const r=await c.match('/');const original=new Uint8Array(await r.arrayBuffer());const modified=original.slice();modified[modified.length-128]^=1;await c.put('/',new Response(modified,{status:200,headers:{'Content-Type':'text/html'}}));const saved=new Uint8Array(await (await c.match('/')).arrayBuffer());return {equal_length:saved.length===original.length,changed_byte:saved[original.length-128]!==original[original.length-128],local_records:localStorage.length}})()");
   assert(changed.equal_length&&changed.changed_byte&&changed.local_records===0,
     'chromium-tampered-cache-mutation-not-persisted');
   checks.push('actual-chromium-cache-storage-tampered-with-no-user-data');
   stage='real-network-offline-corrupt-cache';
   await rpc('Network.emulateNetworkConditions',{offline:true,latency:0,
     downloadThroughput:0,uploadThroughput:0});
   await rpc('Page.reload',{ignoreCache:true});
   const blocked=await poll(async()=>{
     const doc=observedDocuments.findLast(x=>x.public_root&&x.status===503);
     if(!doc)return null;
     const dom=await retryJs("(()=>({complete:document.readyState==='complete',fallback:document.body?.textContent?.includes('NEXUS offline app shell is unavailable.')===true,app_shell:!!document.getElementById('load-demo'),offline:navigator.onLine===false}))()");
     return dom?.complete?{...dom,...doc}:null;
   },20000,'corrupt-cache-did-not-show-verified-503-error-shell');
   assert(blocked.from_worker===true&&blocked.status===503&&blocked.fallback===true&&
     blocked.app_shell===false&&blocked.offline===true,
     'corrupt-offline-app-must-fail-closed-in-real-browser');
   checks.push('real-chromium-offline-navigation-refuses-corrupt-cache-as-503');
   process.stdout.write(JSON.stringify({schema:'nexus.pilot-12.chrome-corrupt-cache.v1',
     status:'PASS',checks,source_sha256:sourceDigest,
     real_chromium:true,public_https_tested:false,real_android_hardware:false,
     cache_corruption_in_disposable_profile:true,
     attempted_runtime_execution_on_bad_shell:false,production_mutation:false,
     private_data_submitted:false,authority:'none'})+'\n');
 } else {
 await js("window.__nexusBeforeOfflineReload=true;true");
 stage='real-network-offline';
 await rpc('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 await rpc('Page.reload',{ignoreCache:true});
 await poll(()=>retryJs("!window.__nexusBeforeOfflineReload&&document.readyState==='complete'&&document.getElementById('offline-install')&&navigator.onLine===false"),15000,'offline-navigation-not-served');
 checks.push('real-chrome-network-offline-reload-served-cached-app');
 const offline=await js("(()=>{document.getElementById('load-demo').click();return {question:document.getElementById('question-view').textContent,claims:document.getElementById('claims').querySelectorAll('.entry').length,options:document.getElementById('alternatives').querySelectorAll('.entry').length,decision:document.getElementById('decision-view').textContent,net:navigator.onLine}})()");
 assert(offline.question.includes('ساختگی')&&offline.claims===2&&offline.options===2&&
 offline.decision.includes('هیچ تصمیم انسانی')&&offline.net===false,
 'offline-content-unavailable-or-created-a-judgment');
 checks.push('real-offline-synthetic-workflow-preserves-human-authority');
 const cached=await js("(async()=>{const ns=await caches.keys();const c=await caches.open(ns[0]);return {keys:(await c.keys()).map(x=>x.url),locals:localStorage.length}})()");
 assert(cached.keys.length===1&&cached.keys[0]===ORIGIN&&cached.locals===0,
 'offline-session-contents-were-persisted-into-cache');
 checks.push('no-synthetic-private-data-in-app-cache');
 stage='restore-network-and-uninstall';
 await rpc('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
 await js("window.confirm=()=>true;document.getElementById('offline-remove').click();true");
 await poll(()=>retryJs("document.getElementById('offline-install-state')?.textContent.includes('حذف شد')"),12000,'explicit-offline-remove-failed');
 const gone=await js("(async()=>({reg:!!(await navigator.serviceWorker.getRegistration('/')),names:await caches.keys(),question:document.getElementById('question-view').textContent}))()");
 assert(!gone.reg&&!gone.names.some(x=>x.startsWith('nexus-app-shell-'))&&gone.question.includes('ساختگی'),
 'uninstall-deleted-workspace-or-left-app-shell');
 checks.push('explicit-uninstall-does-not-change-open-workspace');
 const report={schema:'nexus.pilot-12.offline-install-witness.v1',status:'PASS',
   checks,source_sha256:sourceDigest,source_bytes:sourceHtml.length,
   origin:PUBLIC_MODE?'public-render-pilot':'local-loopback-test-only',
   browser:'headless-chromium',
   actual_offline_navigation:true,real_android_hardware:false,
   private_data_submitted:false,authenticated_rust_tested:false,
   volume_recovery_verified:false,production_mutation:false,authority:'none'};
 process.stdout.write(JSON.stringify(report)+'\n');
 }
}catch(error){
 process.stderr.write(JSON.stringify({event:'pwa-browser-fail-closed',stage,
  reason:String(error?.message||'unknown').replace(/[^A-Za-z0-9-]/g,'').slice(0,90),
  production_verified:false,authority:'none'})+'\n');
 throw error;
}finally{
 if(socket?.readyState===WebSocket.OPEN){
  try{await Promise.race([rpc('Browser.close',{},1200),delay(1400)])}catch{}
  socket.close();
 }
 if(child.pid&&!exited){child.kill('SIGTERM');await delay(250)}
 if(child.pid&&!exited)child.kill('SIGKILL');
 await rm(profile,{recursive:true,force:true});
}
