#!/usr/bin/env node
// Real Chromium, exact extracted ZIP, same-origin scoped PWA, shut down
// the ACTUAL loopback Python process, then reopen Motion from verified cache.
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {createServer} from 'node:net';
import {tmpdir} from 'node:os';
import path from 'node:path';

const HOME=process.env.NEXUS_MOBILE_PACKAGE_DIR;
const BROWSER=process.env.NEXUS_PWA_CHROME;
if(!HOME||!BROWSER||typeof WebSocket==='undefined')
  throw Error('Extracted NEXUS mobile ZIP, real Chromium and Node WebSocket are required');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const assert=(value,message)=>{if(!value)throw Error(message)};
const profile=await mkdtemp(path.join(tmpdir(),'nexus-motion-offline-chrome-'));
const lease=createServer();
await new Promise((resolve,reject)=>lease.once('error',reject).listen(0,'127.0.0.1',resolve));
const port=lease.address().port;
await new Promise(resolve=>lease.close(resolve));
const ORIGIN='http://127.0.0.1:'+port+'/';
const launcher=spawn('python3',[path.join(HOME,'run-nexus.py'),'--port',String(port)],{
  cwd:HOME,stdio:['ignore','ignore','pipe']
});
let liveServer=true,chromeExited=false,ws=null,seq=0,chrome=null,stage='bootstrap';
const calls=new Map();
let errorText='';
launcher.stderr.on('data',chunk=>{errorText+=chunk.toString().slice(0,300)});
const poll=async(fn,timeout=20000,label='poll timeout')=>{
  const end=Date.now()+timeout;
  while(Date.now()<end){const value=await fn();if(value)return value;await wait(120)}
  throw Error(stage+': '+label);
};
function rpc(method,params={},timeout=10000){
 return new Promise((resolve,reject)=>{
  const id=++seq;
  const timer=setTimeout(()=>{calls.delete(id);reject(Error('CDP response timeout: '+method))},timeout);
  calls.set(id,{resolve:v=>{clearTimeout(timer);resolve(v)},reject:e=>{clearTimeout(timer);reject(e)}});
  ws.send(JSON.stringify({id,method,params}));
 });
}
async function js(expression){
 const data=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},12000);
 if(data.exceptionDetails)throw Error('browser evaluation failed: '+expression.slice(0,110));
 return data.result?.value;
}
async function retryJs(expression){
 try{return await js(expression)}catch(e){
  if(e.message.startsWith('browser evaluation failed')||
     e.message.includes('CDP response timeout'))return null;
  throw e;
 }
}
async function serverReady(){
 return await poll(async()=>{
  try{
   const response=await fetch(ORIGIN+'motion/',{signal:AbortSignal.timeout(900)});
   return response.status===200;
  }catch{return false}
 },15000,'Python loopback did not start');
}
async function stopServer(){
 if(!liveServer)return;
 liveServer=false;
 launcher.kill('SIGTERM');
 const waitForExit=()=>new Promise(resolve=>{
   if(launcher.exitCode!==null||launcher.signalCode!==null)return resolve();
   launcher.once('exit',resolve);
 });
 await Promise.race([waitForExit(),wait(2500)]);
 if(launcher.exitCode===null&&launcher.signalCode===null)launcher.kill('SIGKILL');
 await poll(async()=>{
  try{
   const response=await fetch(ORIGIN+'motion/',{signal:AbortSignal.timeout(400)});
   return false;
  }catch{return true}
 },8000,'server still serves after shutdown');
}
const checks=[];
try{
 stage='real-Python-loopback-start';
 await serverReady();
 const manifest=await fetch(ORIGIN+'motion/manifest.json',{signal:AbortSignal.timeout(4000)});
 assert(manifest.ok,'Motion PWA manifest not served');
 const contents=await manifest.json();
 assert(contents.display==='standalone'&&contents.start_url==='./'&&
   contents.icons?.length===2,'installable Motion manifest invalid');
 checks.push('actual-reviewed-PWA-manifest-over-Python-HTTP');

 chrome=spawn(BROWSER,[
  '--headless','--disable-gpu','--no-sandbox','--disable-dev-shm-usage',
  '--disable-extensions','--disable-background-networking','--no-first-run',
  '--no-default-browser-check','--remote-debugging-address=127.0.0.1',
  '--remote-debugging-port=0','--user-data-dir='+profile,
  '--window-size=420,900','about:blank'
 ],{stdio:['ignore','ignore','ignore']});
 chrome.on('exit',()=>{chromeExited=true});
 const debuggerPort=await poll(async()=>{
  if(chromeExited)throw Error('Chromium stopped unexpectedly');
  try{
   const content=await readFile(path.join(profile,'DevToolsActivePort'),'utf8');
   const found=content.split('\n')[0];
   return /^\d+$/.test(found)?found:null;
  }catch{return null}
 },30000,'DevToolsActivePort absent');
 const target=await poll(async()=>{
  try{
   const response=await fetch('http://127.0.0.1:'+debuggerPort+'/json/list',{
     signal:AbortSignal.timeout(1400)});
   if(!response.ok)return null;
   return (await response.json()).find(t=>t.type==='page'&&t.url==='about:blank');
  }catch{return null}
 },12000,'private Chromium page target not found');
 const endpoint=new URL(target.webSocketDebuggerUrl);
 assert(endpoint.hostname==='127.0.0.1'&&endpoint.port===debuggerPort,
   'external debugger URL rejected');
 ws=new WebSocket(endpoint);
 await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('WebSocket connection timed out')),5000);
  ws.addEventListener('open',()=>{clearTimeout(timer);resolve()},{once:true});
  ws.addEventListener('error',()=>{clearTimeout(timer);reject(Error('CDP connection failed'))},{once:true});
 });
 ws.addEventListener('message',event=>{
  const message=JSON.parse(event.data),pending=calls.get(message.id);
  if(!pending)return;
  calls.delete(message.id);
  message.error?pending.reject(Error('CDP request failed')):pending.resolve(message.result);
 });
 await rpc('Page.enable');await rpc('Network.enable');
 await rpc('Network.setCacheDisabled',{cacheDisabled:true});
 stage='initial-Motion-no-worker';
 await rpc('Page.navigate',{url:ORIGIN+'motion/'});
 await poll(()=>retryJs("document.readyState==='complete'&&Boolean(window.NexusMotion)&&Boolean(document.getElementById('motion-offline-prepare'))"),
   15000,'Motion editor did not load');
 assert(await js("document.documentElement.scrollWidth<=innerWidth+3"),
   'Mobile Motion layout overflows viewport');
 assert(await js("navigator.serviceWorker.getRegistration(location.href).then(r=>!r)"),
   'Service Worker auto-registered without explicit consent');
 checks.push('narrow-screen-Motion-editor-no-implicit-offline-install');
 stage='opt-in-encrypted-storyboard-draft';
 const slot='nexus.motion.encrypted.storyboard.v1';
 assert(await js("localStorage.getItem('nexus.motion.encrypted.storyboard.v1')===null"),
  'Motion created private persistent storage before user consent');
 await js("document.getElementById('motion-draft-pass').value='synthetic-private-passphrase-2030';"+
  "document.getElementById('motion-draft-confirm').value='synthetic-private-passphrase-2030';"+
  "document.getElementById('motion-draft-enable').click();true");
 await poll(()=>retryJs("document.getElementById('motion-draft-status').textContent.includes('Encrypted storyboard saved')"),
   20000,'first PBKDF2/AES-GCM checkpoint not saved');
 const encryptedBefore=await js("localStorage.getItem('nexus.motion.encrypted.storyboard.v1')");
 assert(encryptedBefore&&encryptedBefore.length>200&&!encryptedBefore.includes('BEFORE THE LIGHT')&&
  !encryptedBefore.includes('synthetic-private-passphrase'),
  'Autosave leaked plaintext or did not create ciphertext');
 await js("document.getElementById('motion-add').click();true");
 await poll(()=>retryJs("localStorage.getItem('nexus.motion.encrypted.storyboard.v1')!=="+
  JSON.stringify(encryptedBefore)),20000,'edited storyboard not auto-encrypted');
 assert(await js("document.querySelectorAll('#motion-scenes .scene').length")===4,
   'synthetic edit not reflected in Motion editor');
 await js("document.getElementById('motion-draft-enable').click();true");
 await rpc('Page.reload',{ignoreCache:true});
 await poll(()=>retryJs("document.readyState==='complete'&&Boolean(window.NexusMotion)&&"+
  "document.querySelectorAll('#motion-scenes .scene').length===3"),15000,
  'fresh Motion page did not reset unsaved memory');
 assert(await js("document.getElementById('motion-draft-status').textContent.includes('Encrypted draft found')"),
  'encrypted recovery prompt not displayed after restart');
 await js("window.confirm=()=>true;document.getElementById('motion-draft-pass').value='wrong-private-password';"+
  "document.getElementById('motion-draft-restore').click();true");
 await poll(()=>retryJs("document.getElementById('motion-draft-status').textContent.includes('Restore rejected')"),
  18000,'wrong passphrase did not fail closed');
 assert(await js("document.querySelectorAll('#motion-scenes .scene').length")===3,
  'wrong passphrase modified the storyboard');
 await js("document.getElementById('motion-draft-pass').value='synthetic-private-passphrase-2030';"+
  "document.getElementById('motion-draft-restore').click();true");
 await poll(()=>retryJs("document.getElementById('motion-draft-status').textContent.includes('Restored encrypted storyboard')"),
  20000,'valid passphrase did not restore storyboard');
 assert(await js("document.querySelectorAll('#motion-scenes .scene').length")===4,
  'encrypted checkpoint did not recover exact scene count');
 checks.push('explicit-aes-gcm-autosave-no-plaintext-wrong-passphrase-fails-reload-restore');
 stage='user-initiated-install';
 await js("document.getElementById('motion-offline-prepare').click();true");
 await poll(()=>retryJs("document.getElementById('motion-offline-status').textContent.includes('prepared for offline opening')"),
   30000,'verified Motion public shell not installed');
 assert(await js("navigator.serviceWorker.getRegistration(location.href).then(r=>Boolean(r?.active&&r.scope.endsWith('/motion/')))"),
   'separately scoped Motion worker not activated');
 const cached=await js(`(async()=>{const keys=(await caches.keys()).filter(k=>k.startsWith('nexus-motion-shell-v1-'));
 const found=[];
 for(const k of keys){const cache=await caches.open(k);const requests=await cache.keys();
 for(const req of requests)found.push(new URL(req.url).pathname);}
 return found.sort();})()`);
 assert(cached.length===7,'Expected exactly seven verified public Motion cache files: '+JSON.stringify(cached));
 assert(cached.includes('/motion/index.html')&&cached.includes('/motion/motion-ui.js')
   &&cached.includes('/motion/manifest.json'),'Essential Motion offline files are absent');
 assert(cached.every(p=>p.startsWith('/motion/')&&!p.includes('user-media')),
   'A private or foreign path was cached');
 checks.push('explicit-install-seven-hash-checked-public-files-only');
 stage='real-Python-service-stopped';
 await stopServer();
 checks.push('actual-Termux-equivalent-loopback-process-stopped');
 stage='reopen-offline-Motion';
 await rpc('Page.navigate',{url:ORIGIN+'motion/'});
 await poll(()=>retryJs("document.readyState==='complete'&&Boolean(window.NexusMotion)&&Boolean(document.getElementById('motion-add'))"),
   20000,'Motion did not reopen after real Python shutdown');
 assert(await js("navigator.serviceWorker.controller?.scriptURL.endsWith('/motion/offline-worker.js')"),
   'Offline Motion page is not controlled by dedicated worker');
 checks.push('real-Chromium-reloaded-Motion-after-server-shutdown');
 assert(await js("document.getElementById('motion-draft-status').textContent.includes('Encrypted draft found')"),
  'encrypted draft unavailable in actual offline reopened editor');
 await js("window.confirm=()=>true;document.getElementById('motion-draft-pass').value='synthetic-private-passphrase-2030';"+
  "document.getElementById('motion-draft-restore').click();true");
 await poll(()=>retryJs("document.getElementById('motion-draft-status').textContent.includes('Restored encrypted storyboard')"),
   20000,'offline recovery could not decrypt local checkpoint');
 assert(await js("document.querySelectorAll('#motion-scenes .scene').length")===4,
  'offline restored scene count differs from last saved draft');
 checks.push('encrypted-draft-survives-server-shutdown-and-offline-worker-reopen');
 const before=await js("document.querySelectorAll('#motion-scenes .scene').length");
 await js("document.getElementById('motion-add').click();true");
 const after=await js("document.querySelectorAll('#motion-scenes .scene').length");
 assert(after===before+1,'Cached offline Motion editor cannot edit local scene');
 checks.push('interactive-offline-scene-edit-after-disconnection');
 await js("window.confirm=()=>true;document.getElementById('motion-draft-clear').click();true");
 assert(await js("localStorage.getItem('nexus.motion.encrypted.storyboard.v1')===null"),
  'explicit delete did not remove the encrypted checkpoint');
 await js("document.getElementById('motion-add').click();true");
 await wait(950);
 assert(await js("localStorage.getItem('nexus.motion.encrypted.storyboard.v1')===null"),
  'draft recreated itself after user explicitly disabled and cleared storage');
 checks.push('explicit-erase-and-no-silent-resave');
 stage='user-clears-offline-cache';
 await js("document.getElementById('motion-offline-remove').click();true");
 await poll(()=>retryJs("document.getElementById('motion-offline-status').textContent.includes('offline copy removed')"),
  10000,'Offline public-code removal failed');
 assert(await js("caches.keys().then(names=>names.every(x=>!x.startsWith('nexus-motion-shell-v1-')))"),
   'Motion public offline cache not removed');
 checks.push('explicit-uninstall-removes-only-Motion-public-cache');
 console.log(JSON.stringify({status:'PASS',checks,chromium:true,
   python_loopback_really_stopped:true,actual_android_hardware_tested:false,
   media_uploaded:false,offline_public_code_only:true,apk_created:false}));
}catch(e){throw Error(stage+': '+e.message+' | '+errorText.slice(-200));}
finally{
 try{ws?.close()}catch{}
 for(const call of calls.values())call.reject(Error('browser test closing'));
 if(chrome?.exitCode===null){chrome.kill('SIGTERM');await wait(250);if(chrome.exitCode===null)chrome.kill('SIGKILL')}
 if(liveServer){launcher.kill('SIGTERM');await wait(200);if(launcher.exitCode===null)launcher.kill('SIGKILL')}
 await rm(profile,{recursive:true,force:true});
}
