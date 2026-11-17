#!/usr/bin/env node
// Disposable real-Chromium browser witness for the local Android reporting FORM.
// Not a phone test, not the real published Pilot 12, no network or user data.
import {spawn} from 'node:child_process';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const chrome=process.env.NEXUS_ANDROID_FORM_CHROME;
if(!chrome||typeof WebSocket==='undefined'||
   process.env.RAILWAY_TOKEN||process.env.RENDER_API_KEY||
   process.env.NEXUS_API_TOKEN)throw Error('disposable-local-chrome-without-operator-credentials-required');
const targetUrl=pathToFileURL(fileURLToPath(new URL('../web/pilot12-android-field-witness.html',import.meta.url))).href;
const tmp=await mkdtemp(path.join(tmpdir(),'nexus-android-form-'));
const profile=path.join(tmp,'profile');
const processChrome=spawn(chrome,[
 '--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
 '--disable-background-networking','--disable-extensions','--no-first-run',
 '--no-default-browser-check','--remote-debugging-address=127.0.0.1',
 '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'
],{stdio:['ignore','ignore','ignore']});
let socket,sequence=0,stage='boot',exited=false;
const pending=new Map();
processChrome.on('exit',()=>{exited=true});
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const assert=(value,label)=>{if(!value)throw Error(label)};
async function poll(action,timeout,label){
 const end=Date.now()+timeout;
 while(Date.now()<end){
  assert(!exited,'chromium-exited');
  const result=await action();
  if(result)return result;
  await delay(80);
 }
 throw Error(label);
}
function rpc(method,params={},timeout=15000){
 return new Promise((resolve,reject)=>{
  const id=++sequence;
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('cdp-timeout'))},timeout);
  pending.set(id,{resolve:value=>{clearTimeout(timer);resolve(value)},
                  reject:err=>{clearTimeout(timer);reject(err)}});
  socket.send(JSON.stringify({id,method,params}));
 });
}
async function js(expression){
 const reply=await rpc('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
 if(reply.exceptionDetails)throw Error('form-js-exception');
 return reply.result?.value;
}
let httpAttempts=0;
try{
 const port=await poll(async()=>{
  try{
   const s=await readFile(path.join(profile,'DevToolsActivePort'),'utf8');
   const p=s.split('\n')[0];return /^\d+$/.test(p)?p:null;
  }catch{return null}
 },25000,'chromium-debugger-port-unavailable');
 const target=await poll(async()=>{
  try{
   const response=await fetch('http://127.0.0.1:'+port+'/json/list',
     {signal:AbortSignal.timeout(2000)});
   if(!response.ok)return null;
   const tabs=await response.json();
   return tabs.find(x=>x.type==='page'&&x.url==='about:blank');
  }catch{return null}
 },10000,'chromium-no-disposable-page');
 const address=new URL(target.webSocketDebuggerUrl);
 assert(address.hostname==='127.0.0.1'&&address.port===port,'external-debugger');
 socket=new WebSocket(address.href);
 await new Promise((resolve,reject)=>{
  const t=setTimeout(()=>reject(Error('chromium-debugger-connection-timeout')),5000);
  socket.addEventListener('open',()=>{clearTimeout(t);resolve()},{once:true});
  socket.addEventListener('error',()=>{clearTimeout(t);reject(Error('chromium-debugger-connection-error'))},{once:true});
 });
 socket.addEventListener('message',evt=>{
  let msg;try{msg=JSON.parse(evt.data)}catch{return}
  if(msg.method==='Network.requestWillBeSent'&&
     /^https?:/.test(msg.params?.request?.url||''))httpAttempts++;
  const call=pending.get(msg.id);
  if(call){
   pending.delete(msg.id);
   msg.error?call.reject(Error('cdp-error')):call.resolve(msg.result);
  }
 });
 await rpc('Page.enable');await rpc('Network.enable');
 await rpc('Page.setDownloadBehavior',{behavior:'deny'});
 stage='form-load';
 const nav=await rpc('Page.navigate',{url:targetUrl});
 assert(!nav.errorText,'local-html-navigation-failed');
 const ready=await poll(async()=>{
  try{return await js("document.readyState==='complete'&&document.querySelectorAll('#stages select').length===10&&!!document.getElementById('generate')")}
  catch{return false}
 },15000,'mobile-field-form-not-ready');
 assert(ready,'form-not-ready');
 assert(httpAttempts===0,'field-form-made-network-request');
 stage='default-incomplete';
 const initial=await js("(()=>{document.getElementById('generate').click();return JSON.parse(document.getElementById('output').value)})()");
 assert(initial.status==='INCOMPLETE_OR_FAILED'&&
   initial.independent_hardware_verified===false&&
   initial.device_sha256_measured===false&&
   initial.production_release_authorized===false&&initial.transmission==='none',
   'default-form-must-fail-closed');
 stage='all-reported-pass';
 const reported=await js("(()=>{for(const select of document.querySelectorAll('#stages select'))select.value='pass';document.getElementById('android').checked=true;document.getElementById('fictional').checked=true;document.getElementById('browser').value='chrome';document.getElementById('generate').click();return JSON.parse(document.getElementById('output').value)})()");
 assert(reported.status==='USER_REPORTED_PASS_UNVERIFIED'&&
   reported.self_attested_physical_android===true&&
   Object.keys(reported.stages).length===10&&
   Object.values(reported.stages).every(x=>x==='pass')&&
   reported.independent_hardware_verified===false&&
   reported.production_release_authorized===false,
   'reported-success-must-not-become-hardware-verification');
 stage='negative-ui-regression';
 const failure=await js("(()=>{document.getElementById('stage-reopen_two').value='fail';document.getElementById('generate').click();const r=JSON.parse(document.getElementById('output').value);return {status:r.status,revoked:r.production_release_authorized,network:r.transmission}})()");
 assert(failure.status==='INCOMPLETE_OR_FAILED'&&
   failure.revoked===false&&failure.network==='none'&&httpAttempts===0,
   'failed-step-must-revoke-self-report-completion');
 const storage=await js("(()=>{try{return {ls:localStorage.length,ss:sessionStorage.length}}catch{return {ls:0,ss:0}}})()");
 assert(storage.ls===0&&storage.ss===0,'browser-storage-not-empty');
 process.stdout.write(JSON.stringify({schema:'nexus.pilot12.android-form-chromium.v1',
   status:'PASS',checks:4,network_requests_from_page:httpAttempts,
   using_file_scheme:true,real_android_hardware:false,
   independent_device_verified:false,production_mutation:false,authority:'none'})+'\n');
}catch(error){
 process.stderr.write(JSON.stringify({event:'android-form-browser-failed',
   stage,reason:String(error?.message||'unknown').replace(/[^A-Za-z0-9-]/g,'').slice(0,70),
   content_logged:false,real_android_verified:false,authority:'none'})+'\n');
 throw error;
}finally{
 if(socket?.readyState===WebSocket.OPEN){
  try{await Promise.race([rpc('Browser.close',{},1000),delay(1150)])}catch{}
  socket.close();
 }
 if(processChrome.pid&&!exited){processChrome.kill('SIGTERM');await delay(250)}
 if(processChrome.pid&&!exited)processChrome.kill('SIGKILL');
 await rm(tmp,{recursive:true,force:true});
}
