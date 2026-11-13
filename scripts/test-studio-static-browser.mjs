#!/usr/bin/env node
// Disposable real Chromium: static Studio opt-in cache, encrypted reopen and fail-closed integrity.
import {spawn} from 'node:child_process';
import {readFile,mkdtemp,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {tmpdir} from 'node:os';
import path from 'node:path';
const PUBLIC_MODE=process.argv.includes('--public');
const root=new URL('../public/studio/',import.meta.url);
const browser=process.env.NEXUS_PWA_CHROME;
if(!browser||typeof WebSocket==='undefined')throw Error('real-chromium-and-node-required');
const sha=buf=>createHash('sha256').update(buf).digest('hex');
const sourceHtml=await readFile(new URL('index.html',root)),sourceDigest=sha(sourceHtml);
const assert=(v,label)=>{if(!v)throw Error(label)};
const allowed={'/':'index.html','/index.html':'index.html','/service-worker.js':'service-worker.js','/manifest.json':'manifest.json','/icons/nexus-192.png':'icons/nexus-192.png','/icons/nexus-512.png':'icons/nexus-512.png'};
let server;
if(!PUBLIC_MODE){server=createServer(async(req,res)=>{const file=allowed[req.url]||(['device-engine.js','device-worker.js','device-ui.js','model-manifest.json'].some(n=>req.url==='/device/'+n)?req.url.slice(1):null);if(req.method!=='GET'||!file){res.writeHead(404);res.end();return}res.setHeader('content-type',file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.js')?'text/javascript':file.endsWith('.json')?'application/manifest+json':'image/png');res.end(await readFile(new URL(file,root)))});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))}
const ORIGIN=PUBLIC_MODE?'https://nexus-studio-merikation.onrender.com/':`http://127.0.0.1:${server.address().port}/`;
for(const name of ['index.html','service-worker.js','manifest.json']){const response=await fetch(ORIGIN+(name==='index.html'?'':name),{redirect:'error',signal:AbortSignal.timeout(15000)});assert(response.status===200&&sha(Buffer.from(await response.arrayBuffer()))===sha(await readFile(new URL(name,root))),'public-source-identity-'+name)}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const profile=await mkdtemp(path.join(tmpdir(),'nexus-pwa-private-'));
const child=spawn(browser,[
 '--headless','--no-sandbox','--disable-dev-shm-usage','--disable-extensions',
 '--disable-background-networking','--no-first-run','--no-default-browser-check',
 '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0',
 '--user-data-dir='+profile,'--window-size=420,1000','about:blank'
],{stdio:['ignore','ignore','ignore']});
let socket,seq=0,stage='chrome-start',exited=false,lastDocumentStatus=null;
child.on('exit',()=>{exited=true});
const pending=new Map();
const rpc=(method,params={},deadline=10000,sessionId=undefined)=>new Promise((resolve,reject)=>{
 const id=++seq,timeout=setTimeout(()=>{pending.delete(id);reject(Error('local-debugger-timeout'))},deadline);
 pending.set(id,{resolve:r=>{clearTimeout(timeout);resolve(r)},reject:e=>{clearTimeout(timeout);reject(e)}});
 socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
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
const workerSessions=new Map();
async function setOffline(offline){
 const conditions={offline,latency:0,downloadThroughput:offline?0:-1,uploadThroughput:offline?0:-1};
 await rpc('Network.emulateNetworkConditions',conditions);
 const {targetInfos}=await rpc('Target.getTargets');
 const workers=targetInfos.filter(t=>t.type==='service_worker'&&t.url===ORIGIN+'service-worker.js');
 assert(workers.length>0,'active-worker-target-missing');
 for(const worker of workers){
  let session=workerSessions.get(worker.targetId);
  if(!session){session=(await rpc('Target.attachToTarget',{targetId:worker.targetId,flatten:true})).sessionId;workerSessions.set(worker.targetId,session);await rpc('Network.enable',{},10000,session)}
  await rpc('Network.emulateNetworkConditions',conditions,10000,session);
 }
}
const checks=[];
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
  const msg=JSON.parse(e.data);if(!msg.sessionId&&msg.method==='Network.responseReceived'&&msg.params.type==='Document')lastDocumentStatus=msg.params.response.status;const p=pending.get(msg.id);
  if(!p)return;pending.delete(msg.id);
  msg.error?p.reject(Error('cdp-failure')):p.resolve(msg.result);
 });

 await rpc('Page.enable');await rpc('Network.enable');await rpc('Network.setCacheDisabled',{cacheDisabled:true});
 stage='bootstrap';await rpc('Page.navigate',{url:ORIGIN});
 await poll(()=>retryJs("document.readyState==='complete'&&Boolean(window.NexusStudioUI)&&Boolean(document.getElementById('studio-offline'))"),15000,'studio-not-rendered');
 assert(await js("document.documentElement.scrollWidth<=innerWidth+2"),'mobile-overflow');checks.push('responsive-studio-renders');
 assert(await js("navigator.serviceWorker.getRegistration(location.href).then(r=>!r)"),'unapproved-worker');checks.push('no-automatic-worker');
 await js("document.getElementById('check-model').click();true");
 assert(await js("document.getElementById('model-status').textContent.includes('No model hosted here')&&performance.getEntriesByType('resource').every(r=>!r.name.includes('/studio-api/'))"),'static-model-truthfulness');checks.push('no-model-no-api-contact');
 await js("document.getElementById('project-title').value='SYNTHETIC MOBILE PROJECT';document.getElementById('new-project').click();document.getElementById('new-thread').click();document.getElementById('message').value='SYNTHETIC PRIVATE QUESTION';document.getElementById('guide').click();true");
 assert(await js("NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===2"),'guide-failed');checks.push('local-guide-works-without-provider');
 await js("document.getElementById('passphrase').value='synthetic secret phrase 123';document.getElementById('repeat-passphrase').value='synthetic secret phrase 123';document.getElementById('create-vault').click();true");
 await poll(()=>retryJs("!document.getElementById('save').disabled"),12000,'archive-create');
 await js("document.getElementById('save').click();true");await poll(()=>retryJs("document.getElementById('status').textContent.includes('session saved')"),12000,'archive-save');
 assert(await js("new NexusStudio.IndexedStore().read().then(raw=>!!raw&&!raw.includes('SYNTHETIC PRIVATE QUESTION'))"),'plaintext-history');checks.push('encrypted-browser-save');
 stage='opt-in-offline';await js("document.getElementById('studio-offline').click();true");
 await poll(()=>retryJs("document.getElementById('studio-offline-state').textContent.includes('code is ready')"),25000,'offline-prepare');
 const cached=await js("(async()=>{const names=await caches.keys(),cache=await caches.open(names[0]),keys=await cache.keys();const response=await cache.match(location.origin+'/');const bytes=await response.arrayBuffer();return {names,entries:keys.map(k=>k.url),sha:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join(''),private:new TextDecoder().decode(bytes).includes('SYNTHETIC PRIVATE QUESTION')}})()");
 assert(cached.names.length===1&&cached.names[0].startsWith('nexus-studio-shell-v1-')&&cached.entries.length===5&&cached.entries.includes(ORIGIN)&&cached.sha===sourceDigest&&!cached.private,'cache-not-public-code-only');checks.push('opt-in-cache-exact-public-code-only');
 await poll(()=>retryJs("Boolean(navigator.serviceWorker.controller)"),10000,'worker-control');
 await js("window.__beforeOfflineReload=true;true");
 stage='true-offline';await setOffline(true);await rpc('Page.reload',{ignoreCache:true});
 await poll(()=>retryJs("!window.__beforeOfflineReload&&navigator.onLine===false&&document.readyState==='complete'&&Boolean(window.NexusStudioUI)&&Boolean(document.getElementById('studio-offline'))"),15000,'offline-reload');
 assert(await js("NexusStudioUI.snapshot().projects.length===0"),'automatic-private-reopen');checks.push('true-offline-reload-still-locked');
 await js("document.getElementById('passphrase').value='synthetic secret phrase 123';document.getElementById('unlock').click();true");
 await poll(()=>retryJs("NexusStudioUI.snapshot().projects[0]?.title==='SYNTHETIC MOBILE PROJECT'"),12000,'offline-unlock');checks.push('offline-encrypted-reopen');
 await js("document.getElementById('language').value='fa';document.getElementById('language').dispatchEvent(new Event('change'));true");
 assert(await js("document.documentElement.dir==='rtl'&&getComputedStyle(document.querySelector('.studio-en')).display==='none'"),'persian-static-panel');checks.push('persian-rtl-installation-panel');
 stage='remove';await setOffline(false);
 await js("document.getElementById('studio-remove-offline').click();true");await poll(()=>retryJs("document.getElementById('studio-offline-state').textContent.includes('حذف شد')"),12000,'remove-offline');
 assert(await js("(async()=>!(await navigator.serviceWorker.getRegistration(location.href))&&(await caches.keys()).length===0&&NexusStudioUI.snapshot().projects.length===1&&Boolean(await new NexusStudio.IndexedStore().read()))()"),'remove-destroyed-private-state');checks.push('remove-code-retains-open-and-encrypted-work');
 // Reinstall, corrupt only the cached public bytes, then verify true-offline fail-closed.
 await js("document.getElementById('studio-offline').click();true");await poll(()=>retryJs("document.getElementById('studio-offline-state').textContent.includes('آماده است')"),25000,'reinstall');
 await js("(async()=>{const cache=await caches.open((await caches.keys())[0]);await cache.put(location.origin+'/',new Response('CORRUPTED PUBLIC SHELL',{headers:{'content-type':'text/html'}}));return true})()");
 lastDocumentStatus=null;await setOffline(true);await rpc('Page.reload',{ignoreCache:true});
 await poll(async()=>lastDocumentStatus===503,15000,'corrupted-cache-accepted');checks.push('corrupted-offline-shell-rejected');
 process.stdout.write(JSON.stringify({status:'PASS',checks,source_sha256:sourceDigest,origin:ORIGIN,actual_offline_navigation:true,real_android_hardware:false,real_model_tested:false,authority:'none'})+'\n');
}catch(error){
 process.stderr.write(JSON.stringify({event:'pwa-browser-fail-closed',stage,checks,last_document_status:lastDocumentStatus,
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
 if(server)await new Promise(resolve=>server.close(resolve));
}
