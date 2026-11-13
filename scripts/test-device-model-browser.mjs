#!/usr/bin/env node
// Actual pinned ONNX weights in a disposable real Chromium WASM Worker.
import {spawn} from 'node:child_process';
import {readFile,mkdtemp,rm} from 'node:fs/promises';
import {createServer} from 'node:http';
import {tmpdir} from 'node:os';
import path from 'node:path';
const PUBLIC_MODE=process.argv.includes('--public');
const browser=process.env.NEXUS_PWA_CHROME;if(!browser)throw Error('real-browser-required');
const root=new URL('../public/studio/device/',import.meta.url);
const manifest=JSON.parse(await readFile(new URL('model-manifest.json',root)));
const allowed=new Set(['device-engine.js','device-worker.js','model-manifest.json',...Object.keys(manifest.vendor).map(x=>'vendor/'+x)]);
let server;
if(!PUBLIC_MODE){server=createServer(async(req,res)=>{const name=req.url?.slice('/device/'.length);if(req.url==='/'){res.setHeader('content-type','text/html');res.end('<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'self\' blob: \'unsafe-inline\' \'wasm-unsafe-eval\'; worker-src \'self\' blob:; connect-src \'self\' https:"><title>Device model acceptance</title>');return}if(!req.url.startsWith('/device/')||!allowed.has(name)){res.writeHead(404);res.end();return}res.setHeader('content-type',name.endsWith('.json')?'application/json':'text/javascript');res.end(await readFile(new URL(name,root)))});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));}
const ORIGIN=PUBLIC_MODE?'https://nexus-studio-merikation.onrender.com/':`http://127.0.0.1:${server.address().port}/`;
const assert=(v,reason)=>{if(!v)throw Error(reason)};
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

const checks=[];
try{
 const port=await poll(async()=>{try{const s=await readFile(path.join(profile,'DevToolsActivePort'),'utf8');return s.split('\n')[0]}catch{return null}},25000,'browser-port');
 const targets=await fetch('http://127.0.0.1:'+port+'/json/list').then(r=>r.json()),target=targets.find(t=>t.type==='page');
 socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})});
 socket.addEventListener('message',e=>{const msg=JSON.parse(e.data),p=pending.get(msg.id);if(!p)return;pending.delete(msg.id);msg.error?p.reject(Error('cdp-failure')):p.resolve(msg.result)});
 await rpc('Page.enable');await rpc('Network.enable');await rpc('Page.navigate',{url:ORIGIN});
 await poll(()=>retryJs("document.readyState==='complete'"),10000,'page-load');
 stage='consent';await js("(async()=>{const {DeviceEngine}=await import('/device/device-engine.js');window.engine=new DeviceEngine({workerURL:new URL('/device/device-worker.js',location.href),onStatus:s=>{window.lastModelStatus=s;if(s.type==='phase')window.lastModelPhase=s.stage;if(s.type==='error')window.lastModelError=s}});try{await engine.load({consent:false})}catch(e){window.refused=e.message}return true})()");
 assert(await js("window.refused==='explicit-consent-required'&&engine.state==='idle'"),'unapproved-model-download');checks.push('no-download-without-explicit-consent');
 stage='real-weights';await js("window.loadFailure=null;window.loaded=false;engine.load({consent:true}).then(()=>window.loaded=true).catch(e=>window.loadFailure=e.message);true");
 let lastArtifact=null;await poll(async()=>{const state=await retryJs("({ready:window.loaded,error:window.loadFailure,status:window.lastModelStatus,phase:window.lastModelPhase,errorDetail:window.lastModelError})");if(state?.phase&&state.phase!==lastArtifact&&state.status?.type==='phase'){lastArtifact=state.phase;process.stderr.write(JSON.stringify({event:'model-load-phase',phase:state.phase})+'\n')}if(state?.status?.file&&state.status.file!==lastArtifact){lastArtifact=state.status.file;process.stderr.write(JSON.stringify({event:'public-artifact-progress',...state.status})+'\n')}if(state?.error)throw Error('model-load-'+state.error);return state?.ready},300000,'real-weights-timeout');checks.push('real-pinned-q8-weights-loaded-in-wasm');
 const info=await js("engine.info()");assert(info.model===manifest.model&&info.max_input_tokens===768,'model-fingerprint');
 stage='offline-inference';
 await rpc('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 const {targetInfos:workerTargets}=await rpc('Target.getTargets');
 for(const target of workerTargets.filter(t=>t.type==='worker'&&t.url===ORIGIN+'device/device-worker.js')){const {sessionId}=await rpc('Target.attachToTarget',{targetId:target.targetId,flatten:true});await rpc('Network.enable',{},10000,sessionId);await rpc('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0},10000,sessionId)}
 checks.push('browser-network-offline-before-inference');
 await js("window.answer=null;window.generationFailure=null;engine.generate({consent:true,configuration_id:engine.info().configuration_id,messages:[{role:'user',content:'Answer in one word: What color is grass?'}],max_output_tokens:16},new AbortController().signal).then(r=>window.answer=r).catch(e=>window.generationFailure=e.message);true");
 await poll(async()=>{const state=await retryJs("({answer:window.answer,error:window.generationFailure})");if(state?.error)throw Error('generation-'+state.error);return state?.answer},120000,'generation-timeout');
 const answer=await js('window.answer');assert(/green/i.test(answer.text)&&answer.origin==='model'&&answer.authority==='none'&&answer.input_tokens<=768,'actual-model-smoke-answer');checks.push('actual-model-generates-correct-simple-english-smoke-answer');
 stage='bounds';await js("window.boundFailure=null;engine.generate({consent:true,configuration_id:engine.info().configuration_id,messages:[{role:'user',content:'x'.repeat(7000)}],max_output_tokens:16}).catch(e=>window.boundFailure=e.message);true");await poll(()=>retryJs("window.boundFailure==='context-too-large'"),10000,'oversized-context-not-rejected');checks.push('oversized-context-rejected-without-truncation');
 await js("window.boundFailure=null;engine.generate({consent:true,configuration_id:engine.info().configuration_id,messages:[{role:'user',content:'word '.repeat(900)}],max_output_tokens:16}).catch(e=>window.boundFailure=e.message);true");await poll(()=>retryJs("window.boundFailure==='context-too-large'"),10000,'token-context-cap-not-enforced');checks.push('actual-tokenizer-limit-enforced-below-character-limit');
 stage='cancel';await js("window.cancelled=null;const abort=new AbortController();engine.generate({consent:true,configuration_id:engine.info().configuration_id,messages:[{role:'user',content:'Write a long story.'}],max_output_tokens:64},abort.signal).catch(e=>window.cancelled=e.message);abort.abort();true");assert(await js("engine.state==='idle'&&engine.worker===null"),'cancel-did-not-destroy-worker');checks.push('cancel-terminates-real-inference-worker');
 stage='erase';await js("(async()=>{await caches.open('unrelated-cache-sentinel');await engine.erase();return true})()");assert(await js("caches.keys().then(keys=>keys.includes('unrelated-cache-sentinel')&&!keys.includes('nexus-device-artifacts-v1'))"),'erase-touched-unrelated-storage');checks.push('model-cache-erasure-is-scoped');
 process.stdout.write(JSON.stringify({status:'PASS',checks,real_model_tested:true,origin:ORIGIN,model:manifest.model,revision:manifest.revision,runtime:manifest.runtime,download_bytes:manifest.download_bytes,output:answer.text,real_android_hardware:false,authority:'none'})+'\n');
}catch(error){
 let detail=null;try{if(stage==='real-weights')detail=await js('({status:window.lastModelStatus,phase:window.lastModelPhase,errorDetail:window.lastModelError})');else if(stage==='offline-inference')detail=await js('window.answer')}catch{}
 process.stderr.write(JSON.stringify({event:'pwa-browser-fail-closed',stage,checks,detail,
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
