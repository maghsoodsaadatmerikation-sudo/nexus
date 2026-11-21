#!/usr/bin/env node
// Disposable real Chromium: static Studio opt-in cache, encrypted reopen and fail-closed integrity.
import {spawn} from 'node:child_process';
import {readFile,mkdtemp,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const PUBLIC_MODE=process.argv.includes('--public');
// CI can inspect the exact extracted public-only phone ZIP, not merely its
// build sources. The origin remains a fresh local loopback server.
const packageRoot=process.env.NEXUS_STUDIO_PACKAGE_DIR;
const root=packageRoot?pathToFileURL(path.resolve(packageRoot)+path.sep):new URL('../public/studio/',import.meta.url);
const browser=process.env.NEXUS_PWA_CHROME;
if(!browser||typeof WebSocket==='undefined')throw Error('real-chromium-and-node-required');
const sha=buf=>createHash('sha256').update(buf).digest('hex');
const sourceHtml=await readFile(new URL('index.html',root)),sourceDigest=sha(sourceHtml);
const assert=(v,label)=>{if(!v)throw Error(label)};
const pdfModules=['pdf/studio-pdf.mjs','pdf/pdf.min.mjs','pdf/pdf.worker.min.mjs'];
const allowed={...Object.fromEntries(pdfModules.map(name=>['/'+name,name])),'/':'index.html','/index.html':'index.html','/service-worker.js':'service-worker.js','/manifest.json':'manifest.json','/icons/nexus-192.png':'icons/nexus-192.png','/icons/nexus-512.png':'icons/nexus-512.png',...(packageRoot?{'/device-check.html':'device-check.html'}:{})};
let server;
if(!PUBLIC_MODE){server=createServer(async(req,res)=>{const file=allowed[req.url]||(['device-engine.js','device-worker.js','device-ui.js','model-manifest.json'].some(n=>req.url==='/device/'+n)?req.url.slice(1):null);if(req.method!=='GET'||!file){res.writeHead(404);res.end();return}res.setHeader('content-type',file.endsWith('.html')?'text/html; charset=utf-8':/\.m?js$/.test(file)?'text/javascript':file.endsWith('.json')?'application/manifest+json':'image/png');res.end(await readFile(new URL(file,root)))});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))}
// Small ASCII fixture with exact xref offsets and one selectable text line.
function samplePdf(){
 const stream='BT /F1 12 Tf 20 720 Td (NEXUS SYNTHETIC PDF TEST) Tj ET';
 const objects=[
  '<< /Type /Catalog /Pages 2 0 R >>',
  '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
  '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
  '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  '<< /Length '+stream.length+' >>\nstream\n'+stream+'\nendstream'
 ];
 let pdf='%PDF-1.4\n';
 const positions=objects.map((object,i)=>{const offset=pdf.length;pdf+=(i+1)+' 0 obj\n'+object+'\nendobj\n';return offset});
 const xref=pdf.length;
 const rows=positions.map(offset=>String(offset).padStart(10,'0')+' 00000 n \n').join('');
 return pdf+'xref\n0 6\n0000000000 65535 f \n'+rows+'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';
}
const ORIGIN=PUBLIC_MODE?'https://nexus-studio-merikation.onrender.com/':`http://127.0.0.1:${server.address().port}/`;
for(const name of ['index.html','service-worker.js','manifest.json',...pdfModules]){const response=await fetch(ORIGIN+(name==='index.html'?'':name),{redirect:'error',signal:AbortSignal.timeout(15000)});assert(response.status===200&&sha(Buffer.from(await response.arrayBuffer()))===sha(await readFile(new URL(name,root))),'public-source-identity-'+name)}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const profile=await mkdtemp(path.join(tmpdir(),'nexus-pwa-private-'));
const child=spawn(browser,[
 '--headless','--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--disable-extensions',
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

 if(packageRoot){
  stage='phone-fieldcheck-from-extracted-zip';
  await rpc('Page.navigate',{url:ORIGIN+'device-check.html'});
  await poll(()=>retryJs("document.readyState==='complete'&&Boolean(window.NexusPhoneCheck)&&Boolean(document.getElementById('run'))"),10000,'fieldcheck-page-not-ready');
  await js("NexusPhoneCheck.run()");
  const report=await js("NexusPhoneCheck.report()");
  assert(report?.schema==='nexus.studio.owner-phone-field.v1'&&
    report?.source_sha256===sourceDigest&&
    report?.personal_data_collected===false&&report?.telemetry_sent===false&&
    report?.app_content_uploaded===false&&report?.actual_android_hardware_independently_verified===false&&
    report?.real_disconnected_reload_automatically_verified===false&&report?.result==='NOT_PREPARED'&&
    report.checks?.length===8&&
    report.checks.filter(c=>c.state==='PASS').length===6&&
    report.checks.filter(c=>c.state==='NOT_PREPARED').length===2&&
    report.owner_reported?.disconnected_reopen===false,
    'fieldcheck-honesty-or-public-asset-hash-invalid');
  assert(await js("localStorage.length===0&&Boolean(document.querySelector('#checks .item'))"),'fieldcheck-should-not-touch-private-storage');
  await js("document.getElementById('manual-offline').click();true");
  const self=await js("NexusPhoneCheck.report()");
  assert(self.owner_reported.disconnected_reopen===true&&
    self.actual_android_hardware_independently_verified===false,
    'self-report-must-never-be-treated-as-independent-proof');
  checks.push('fieldcheck-real-chromium-no-data-and-self-report-distinction');
  stage='bootstrap-after-fieldcheck';
  await rpc('Page.navigate',{url:ORIGIN});
  await poll(()=>retryJs("document.readyState==='complete'&&Boolean(window.NexusStudioUI)&&Boolean(document.getElementById('studio-offline'))"),15000,'studio-after-fieldcheck-not-rendered');
 }
 assert(await js("document.documentElement.scrollWidth<=innerWidth+2"),'mobile-overflow');checks.push('responsive-studio-renders');
 stage='static-branding';
 await poll(()=>retryJs(`(()=>{
   const brand=document.querySelector('.studio-mark');
   return brand?.complete&&brand.naturalWidth===64&&
    document.querySelector('link[rel=icon]')?.getAttribute('href')==='./icons/nexus-192.png'&&
    document.querySelector('link[rel=apple-touch-icon]')?.getAttribute('href')==='./icons/nexus-192.png';
 })()`),5000,'approved-brand-did-not-render');
 checks.push('approved-brand-renders-with-mobile-and-browser-icons');
 stage='static-tool-bootstrap';
 assert(await js("Boolean(window.NexusLabUI)&&document.querySelector('#research-card h2').textContent==='Live research desk'"),'static-research-labels-not-loaded');
 await js(`(()=>{
   const code=document.getElementById('code');
   code.value='return 6 * 7;';
   code.dispatchEvent(new Event('input',{bubbles:true}));
   document.getElementById('code-consent').checked=true;
   document.getElementById('code-run').click();
   return true;
 })()`);
 await poll(()=>retryJs("document.getElementById('code-result').textContent==='42'"),8000,'static-isolated-code-result-missing');
 await js("(()=>{const code=document.getElementById('code');code.value='';code.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 checks.push('static-tools-bootstrap-and-isolated-code');
 stage='web-app-install';
 const installCheck=await js(`(async()=>{
   const install=document.getElementById('studio-install');
   const privacy=document.querySelector('a[href="#studio-privacy"]');
   if(!install||!privacy||!document.getElementById('studio-privacy'))return 'missing-controls';
   const panel=document.getElementById('studio-install-card');
   if(!panel||getComputedStyle(panel).display==='none'||panel.open)return 'install-panel-hidden-or-expanded';
   panel.querySelector('summary').click();
   if(!panel.open||getComputedStyle(document.getElementById('studio-offline')).display==='none')return 'offline-action-not-reachable';
   panel.querySelector('summary').click();
   const origin='https://nexus-studio-merikation.onrender.com/';
   if(document.querySelector('link[rel="canonical"]')?.href!==origin||
      document.querySelector('meta[property="og:url"]')?.content!==origin||
      document.querySelector('meta[property="og:title"]')?.content!=='NEXUS Studio'||
      !document.querySelector('meta[property="og:description"]')?.content||
      document.querySelector('meta[property="og:image"]')?.content!==origin+'icons/nexus-512.png')return 'share-metadata-missing';
   let prompted=0;
   const event=new Event('beforeinstallprompt',{cancelable:true});
   event.prompt=async()=>{prompted++};
   event.userChoice=Promise.resolve({outcome:'accepted'});
   if(window.dispatchEvent(event)||install.hidden)return 'prompt-not-captured';
   install.click();
   install.click();
   await event.userChoice;
   window.dispatchEvent(new Event('appinstalled'));
   if(prompted!==1)return 'prompt-not-single-use';
   return install.hidden&&document.getElementById('studio-install-state').textContent.includes('installed')?'pass':'install-state-missing';
 })()`);
 assert(installCheck==='pass','install-flow-'+installCheck);
 checks.push('install-prompt-single-use-and-privacy-link');
 assert(await js("NexusStudioFocus.isFocused()&&NexusStudioFocus.active()==='conversation-card'&&!document.getElementById('conversation-card').hidden&&document.getElementById('projects-card').hidden&&!document.getElementById('studio-focus-onboarding').hidden&&document.getElementById('studio-focus-nav').getAttribute('aria-label')==='Primary Studio navigation'"),'mobile-default-chat-not-focused');checks.push('chat-first-first-project-guidance');
 assert(await js("Boolean(window.NexusStudioCompose)&&NexusStudioCompose.mode()==='guide'&&document.getElementById('studio-compose-send').disabled&&document.getElementById('studio-compose-privacy').textContent.includes('not generative AI')&&document.getElementById('studio-compose-storage').textContent.includes('No encrypted archive')"),'initial-honest-composer');
 assert(await js("(()=>{const h=document.getElementById('studio-compose-heading'),d=h.parentElement;const closed=!d.open;h.click();const opened=d.open;h.click();return closed&&opened&&!d.open&&h.textContent.includes('Local guide')})()"),'response-mode-default-disclosure');
 checks.push('composer-local-mode-honesty-before-project');
 assert(await js("typeof NexusStudioUI.startConversation==='function'&&NexusStudioUI.snapshot().projects.length===0"),'one-step-start-api-missing');
 assert(await js("getComputedStyle(document.getElementById('messages')).display==='none'&&getComputedStyle(document.getElementById('branch')).display==='none'&&document.getElementById('studio-focus-onboarding').textContent.includes('No account needed')"),'first-visit-layout-not-compact');
 checks.push('one-step-onboarding-available-with-no-project');
 assert(await js("navigator.serviceWorker.getRegistration(location.href).then(r=>!r)"),'unapproved-worker');checks.push('no-automatic-worker');
 await poll(()=>retryJs('Boolean(window.NexusDevice)'),10000,'device-controls-not-ready');await js("document.getElementById('device-check').click();true");await poll(()=>retryJs("document.getElementById('device-readiness').textContent.includes('not been verified')"),10000,'readiness-not-rendered');assert(await js("NexusDevice.worker===null&&NexusDevice.report().generation_observed===false"),'readiness-started-model');checks.push('readiness-does-not-load-model-or-claim-execution');
 await js("document.getElementById('check-model').click();true");
 assert(await js("document.getElementById('model-status').textContent.includes('No model hosted here')&&performance.getEntriesByType('resource').every(r=>!r.name.includes('/studio-api/'))"),'static-model-truthfulness');checks.push('no-model-no-api-contact');
 await js("(()=>{const m=document.getElementById('message');m.value='SYNTHETIC FIRST DRAFT';m.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 assert(await js("!document.getElementById('studio-compose-send').disabled&&NexusStudioUI.snapshot().projects.length===0"),'message-first-must-enable-composer');
 await js("document.getElementById('studio-focus-onboarding').querySelector('button').click();true");
 assert(await js("NexusStudioFocus.active()==='conversation-card'&&document.activeElement.id==='message'&&document.getElementById('studio-focus-onboarding').hidden&&NexusStudioUI.snapshot().projects[0].threads.length===1&&NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===0&&document.getElementById('message').value==='SYNTHETIC FIRST DRAFT'"),'one-click-first-chat-must-preserve-draft');
 await js("(()=>{const m=document.getElementById('message');m.value='';m.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 checks.push('first-chat-creates-local-project-and-thread-without-sending-or-losing-draft');

 // Image generation is a separate reviewed, transient model request. Mock the
 // provider boundary; do not claim this proves real image model quality.
 stage='mock-image-generation-consent';
 assert(await js("Boolean(document.getElementById('studio-imagegen-open'))&&Boolean(document.getElementById('studio-imagegen-panel'))"),'image-generation-not-in-chat');
 await js("(()=>{window.__imageRequests=[];window.__imageFetchOriginal=window.fetch;window.fetch=async function(input,init={}){const url=String(input);if(url.endsWith('/studio-api/image-generation-status')){window.__imageRequests.push({kind:'status'});return new Response(JSON.stringify({configured:true,configuration_id:'a'.repeat(64),model:'mock-image-provider',provider_host:'example.test',authority:'none'}),{status:200,headers:{'content-type':'application/json'}})}if(url.endsWith('/studio-api/generate-image')){window.__imageRequests.push({kind:'generate',method:init.method,credentialMode:init.credentials,body:JSON.parse(init.body)});return new Response(JSON.stringify({authority:'none',model:'mock-image-provider',mime_type:'image/png',image_base64:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGMQMgkDAAD4AJ3MaiF4AAAAAElFTkSuQmCC'}),{status:200,headers:{'content-type':'application/json'}})}return window.__imageFetchOriginal.call(this,input,init)};const m=document.getElementById('message');m.value='SYNTHETIC GREEN AND PURPLE LANDSCAPE';m.dispatchEvent(new Event('input'));document.getElementById('studio-imagegen-open').click();document.getElementById('studio-imagegen-use-draft').click();return true})()");
 assert(await js("document.getElementById('studio-imagegen-panel').open&&document.getElementById('studio-imagegen-prompt').value==='SYNTHETIC GREEN AND PURPLE LANDSCAPE'&&document.getElementById('message').value==='SYNTHETIC GREEN AND PURPLE LANDSCAPE'&&!window.__imageRequests.length"),'image-draft-sent-or-lost');
 await js("document.getElementById('studio-imagegen-check').click();true");
 await poll(()=>retryJs("document.getElementById('studio-imagegen-status').textContent.includes('mock-image-provider')"),3500,'image-status-check');
 assert(await js("window.__imageRequests.length===1&&window.__imageRequests[0].kind==='status'&&document.getElementById('studio-imagegen-approval').hidden"),'image-check-must-not-generate');
 await js("document.getElementById('studio-imagegen-review').click();true");
 await poll(()=>retryJs("!document.getElementById('studio-imagegen-approval').hidden"),3500,'image-request-review');
 assert(await js("window.__imageRequests.every(x=>x.kind==='status')&&document.getElementById('studio-imagegen-exact').textContent.includes('SYNTHETIC GREEN AND PURPLE LANDSCAPE')&&document.getElementById('studio-imagegen-submit').disabled"),'image-review-not-a-send');
 await js("(()=>{const p=document.getElementById('studio-imagegen-prompt');document.getElementById('studio-imagegen-consent').checked=true;p.value='CHANGED IMAGE PROMPT';p.dispatchEvent(new Event('input'));return true})()");
 assert(await js("document.getElementById('studio-imagegen-approval').hidden&&document.getElementById('studio-imagegen-submit').disabled"),'image-modification-must-invalidate-review');
 await js("document.getElementById('studio-imagegen-review').click();true");
 await poll(()=>retryJs("!document.getElementById('studio-imagegen-approval').hidden"),3500,'image-rereview');
 await js("document.getElementById('studio-imagegen-consent').click();document.getElementById('studio-imagegen-submit').click();true");
 await poll(()=>retryJs("!document.getElementById('studio-imagegen-output').hidden"),3500,'mock-image-request');
 assert(await js("(()=>{const made=window.__imageRequests.filter(x=>x.kind==='generate');const body=made[0]?.body;return made.length===1&&made[0].method==='POST'&&made[0].credentialMode==='omit'&&body?.consent===true&&body.prompt==='CHANGED IMAGE PROMPT'&&body.configuration_id==='a'.repeat(64)&&body.size==='1024x1024'&&document.getElementById('studio-imagegen-preview').getAttribute('src').startsWith('data:image/png;base64,')&&!JSON.stringify(NexusStudioUI.snapshot()).includes('CHANGED IMAGE PROMPT')})()"),'image-not-reviewed-or-private-result-saved');
 await js("(()=>{document.getElementById('studio-imagegen-clear').click();window.fetch=window.__imageFetchOriginal;const m=document.getElementById('message');m.value='';m.dispatchEvent(new Event('input'));return true})()");
 assert(await js("document.getElementById('studio-imagegen-output').hidden&&!document.getElementById('studio-imagegen-preview').hasAttribute('src')"),'image-result-not-erased');
 checks.push('image-generation-requires-exact-review-and-explicit-consent');

 // Real local canvas editing: no model, network, crop or archived image bytes.
 stage='offline-image-editing';
 assert(await js("Boolean(document.getElementById('studio-local-image-open'))&&Boolean(document.getElementById('studio-local-image-file'))"),'local-image-editor-missing');
 await js("(async()=>{const source=document.createElement('canvas');source.width=2;source.height=2;const ctx=source.getContext('2d');ctx.fillStyle='rgb(80,40,20)';ctx.fillRect(0,0,2,2);const b=await new Promise(resolve=>source.toBlob(resolve,'image/png'));const input=document.getElementById('studio-local-image-file'),dt=new DataTransfer();dt.items.add(new File([b],'synthetic.png',{type:'image/png'}));input.files=dt.files;document.getElementById('studio-local-image-open').click();input.dispatchEvent(new Event('change'));return true})()");
 await poll(()=>retryJs("document.getElementById('studio-local-image-canvas').width===2&&!document.getElementById('studio-local-image-canvas').hidden&&!document.getElementById('studio-local-image-download').disabled"),5000,'offline-image-load');
 const edit=await js("(()=>{const canvas=document.getElementById('studio-local-image-canvas'),ctx=canvas.getContext('2d'),before=[...ctx.getImageData(0,0,1,1).data],slider=document.getElementById('studio-local-image-brightness');slider.value='140';slider.dispatchEvent(new Event('input'));const after=[...ctx.getImageData(0,0,1,1).data];document.getElementById('studio-local-image-reset').click();const reset=[...ctx.getImageData(0,0,1,1).data];return {before,after,reset,sliders:[...document.querySelectorAll('#studio-local-image-controls input')].map(n=>n.value),status:document.getElementById('studio-local-image-status').textContent}})()");
 assert(edit.after[0]>edit.before[0]&&edit.reset.join(',')===edit.before.join(',')&&edit.sliders.join(',')==='100,100,100','offline-filters-must-work-and-reset-'+JSON.stringify(edit));
 assert(await js("!JSON.stringify(NexusStudioUI.snapshot()).includes('synthetic.png')"),'local-image-in-encrypted-archive-state');
 await js("document.getElementById('studio-local-image-download').click();true");
 await poll(()=>retryJs("document.getElementById('studio-local-image-status').textContent.includes('Edited copy downloaded')"),3500,'offline-image-export');
 await js("document.getElementById('studio-local-image-clear').click();true");
 assert(await js("document.getElementById('studio-local-image-canvas').hidden&&document.getElementById('studio-local-image-canvas').width===0&&document.getElementById('studio-local-image-file').value===''"),'offline-image-not-erased');
 checks.push('real-offline-image-editing-full-frame-reset-download-and-clear');

 stage='video-chat-tool-and-local-privacy';
 assert(await js("Boolean(document.getElementById('studio-video-open'))&&Boolean(document.getElementById('studio-video-panel'))&&document.getElementById('studio-video-start').disabled"),'video-must-be-chat-linked-but-disabled-without-photo');
 await js("document.getElementById('studio-video-open').click();true");
 assert(await js("document.getElementById('studio-video-panel').open"),'video-panel-did-not-open');
 const videoSupported=await js("typeof MediaRecorder!=='undefined'&&typeof HTMLCanvasElement.prototype.captureStream==='function'&&['video/webm;codecs=vp8,opus','video/webm;codecs=vp9,opus','video/webm','video/mp4'].some(x=>MediaRecorder.isTypeSupported(x))");
 await js("(async()=>{const source=document.createElement('canvas');source.width=8;source.height=6;const c=source.getContext('2d');c.fillStyle='#823456';c.fillRect(0,0,8,6);const b=await new Promise(resolve=>source.toBlob(resolve,'image/png'));const picker=document.getElementById('studio-video-photo'),dt=new DataTransfer();dt.items.add(new File([b],'PRIVATE-VIDEO-FIXTURE.png',{type:'image/png'}));picker.files=dt.files;picker.dispatchEvent(new Event('change'));return true})()");
 await poll(()=>retryJs("!document.getElementById('studio-video-canvas').hidden&&document.getElementById('studio-video-canvas').width===640"),5000,'video-local-photo-decode');
 assert(await js("!JSON.stringify(NexusStudioUI.snapshot()).includes('PRIVATE-VIDEO-FIXTURE')"),'video-input-was-persisted');
 if(videoSupported){
  await js("(()=>{document.getElementById('studio-video-aspect').value='portrait';document.getElementById('studio-video-aspect').dispatchEvent(new Event('change'));document.getElementById('studio-video-duration').value='3';return true})()");
  assert(await js("document.getElementById('studio-video-canvas').width===360&&document.getElementById('studio-video-canvas').height===640&&!document.getElementById('studio-video-start').disabled"),'video-portrait-and-duration');
  await js("document.getElementById('studio-video-start').click();true");
  assert(await js("document.getElementById('studio-video-download').disabled"),'video-was-downloaded-before-user-action');
  await poll(()=>retryJs("!document.getElementById('studio-video-preview').hidden&&!!document.getElementById('studio-video-preview').src"),11000,'video-local-render');
  const videoProof=await js("(async()=>{const player=document.getElementById('studio-video-preview'),r=await fetch(player.src),buffer=await r.arrayBuffer(),bytes=new Uint8Array(buffer.slice(0,12));return {length:buffer.byteLength,mime:r.headers.get('content-type'),prefix:[...bytes],status:document.getElementById('studio-video-status').textContent,downloadDisabled:document.getElementById('studio-video-download').disabled}})()");
  const isWebm=videoProof.prefix.slice(0,4).join(',')==='26,69,223,163';
  const isMp4=String.fromCharCode(...videoProof.prefix.slice(4,8))==='ftyp';
  assert(videoProof.length>1000&&videoProof.length<=32000000&&(isWebm||isMp4)&&!videoProof.downloadDisabled,'local-video-file-invalid-'+JSON.stringify(videoProof));
  assert(await js("!JSON.stringify(NexusStudioUI.snapshot()).includes('PRIVATE-VIDEO-FIXTURE')&&performance.getEntriesByType('resource').every(x=>!x.name.includes('/studio-api/generate-video'))"),'video-must-not-upload-or-archive');
  await js("document.getElementById('studio-video-clear').click();true");
  assert(await js("document.getElementById('studio-video-preview').hidden&&document.getElementById('studio-video-photo').value===''&&document.getElementById('studio-video-download').disabled"),'video-private-clear-failed');
  checks.push('real-local-image-to-video-output-uncropped-portrait-and-private');
 }else{
  assert(await js("document.getElementById('studio-video-start').disabled"),'unsupported-video-must-fail-closed');
  await js("document.getElementById('studio-video-clear').click();true");
  checks.push('unsupported-video-recorder-fails-closed');
 }




  assert(await js("Boolean(document.getElementById('nexus-zen-menu'))&&Boolean(document.getElementById('nexus-zen-home'))&&getComputedStyle(document.getElementById('studio-focus-nav')).display==='none'"),'zen-home-has-no-tab-clutter');
  await js("document.getElementById('nexus-zen-menu').click();true");
  assert(await js("!document.getElementById('nexus-zen-drawer').hidden&&document.activeElement.id==='nexus-zen-find'"),'zen-menu-not-accessible');
  await js("document.getElementById('nexus-zen-close').click();true");
  assert(await js("document.getElementById('nexus-zen-drawer').hidden"),'zen-menu-not-dismissible');
  checks.push('zen-default-and-collapsible-history');
  await js("(()=>{const m=document.getElementById('message');m.value='/music cinematic instrumental';m.dispatchEvent(new Event('input'));document.getElementById('studio-compose-send').click();return true})()");
  assert(await js("!document.getElementById('nexus-zen-offer').hidden&&NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===0"),'chat-routing-must-be-consent-first');
  await js("document.querySelector('#nexus-zen-offer button').click();true");
  assert(await js("NexusStudioFocus.active()==='music-card'&&!document.getElementById('music-card').hidden&&NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===0"),'chat-request-must-open-reviewed-tool-only');
  await js("document.getElementById('nexus-zen-home').click();document.getElementById('message').value='';document.getElementById('message').dispatchEvent(new Event('input'));true");
  assert(await js("NexusStudioFocus.active()==='conversation-card'&&!document.getElementById('conversation-card').hidden"),'one-tap-back-to-chat');
  checks.push('text-to-tool-is-non-executing-and-reversible');
  await js("(()=>{const m=document.getElementById('message');m.value='SYNTHETIC KEEP THIS PRIVATE DRAFT';m.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#nexus-zen-suggestions button').click();return true})()");
  assert(await js("NexusStudioFocus.active()==='music-card'&&document.getElementById('message').value==='SYNTHETIC KEEP THIS PRIVATE DRAFT'"),'quick-capability-chip-must-not-overwrite-draft');
  await js("document.getElementById('nexus-zen-home').click();document.getElementById('message').value='';document.getElementById('message').dispatchEvent(new Event('input',{bubbles:true}));true");
  checks.push('quick-capability-navigation-preserves-private-draft');

 await js("(()=>{const m=document.getElementById('message');m.value='SYNTHETIC UNSENT MODEL CONTEXT';m.dispatchEvent(new Event('input'));document.getElementById('studio-compose-mode').value='model';document.getElementById('studio-compose-mode').dispatchEvent(new Event('change'));document.getElementById('studio-compose-send').click();return true})()");
 assert(await js("document.getElementById('request-review').hidden&&!document.getElementById('consent').checked&&document.getElementById('message').value==='SYNTHETIC UNSENT MODEL CONTEXT'&&NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===0&&performance.getEntriesByType('resource').every(r=>!r.name.includes('/studio-api/respond'))"),'no-model-quick-action-must-not-send');
 await js("(()=>{const m=document.getElementById('message');m.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true}));return true})()");
 const quickKey=await js("({reviewHidden:document.getElementById('request-review').hidden,consent:document.getElementById('consent').checked,mode:document.getElementById('studio-compose-mode').value,threadNodes:NexusStudioUI.snapshot().projects[0].threads[0].nodes.length,pending:NexusStudioUI.uiStatus().pendingReview,status:document.getElementById('status').textContent})");
 assert(quickKey.reviewHidden&&!quickKey.consent&&quickKey.threadNodes===0,'ctrl-enter-must-not-bypass-consent-'+JSON.stringify(quickKey));
 await js("(()=>{const m=document.getElementById('message');m.value='';m.dispatchEvent(new Event('input'));document.getElementById('studio-compose-mode').value='guide';document.getElementById('studio-compose-mode').dispatchEvent(new Event('change'));return true})()");
 checks.push('model-review-not-send-even-on-ctrl-enter');
 await js("document.querySelector('#studio-focus-nav button[data-panel=tools]').click();true");
 assert(await js("NexusStudioFocus.active()==='tools'&&!document.getElementById('studio-focus-tools').hidden&&document.getElementById('conversation-card').hidden"),'tool-chooser-not-focused');
 assert(await js(`(()=>{
   const search=document.getElementById('studio-tool-search');
   const tray=document.getElementById('studio-focus-tools');
   const choices=()=>[...tray.querySelectorAll('button[data-panel]:not([hidden])')].map(button=>button.dataset.panel);
   const query=text=>{search.value=text;search.dispatchEvent(new Event('input'))};
   query('CSV');if(choices().join()!=='data-card')return false;
   query('ميكس');if(choices().join()!=='orchestra-card')return false;
   query('Reminders');if(choices().join()!=='reminders-card')return false;
   query('xyz-no-such-tool');if(choices().length||tray.querySelector('[role=status]').hidden)return false;
   query('');return choices().length===13&&tray.querySelector('[role=status]').hidden;
 })()`),'tool-catalog-search-and-empty-state');
 await js("document.querySelector('#studio-focus-tools button[data-panel=data-card]').click();true");
 assert(await js("NexusStudioFocus.active()==='data-card'&&!document.getElementById('data-card').hidden&&!document.getElementById('conversation-card').hidden"),'data-panel-route-keeps-the-conversation');
 await js("NexusStudioUI.stageChatContext('SYNTHETIC ANALYSIS','SYNTHETIC HANDOFF')"); 
 assert(await js("NexusStudioFocus.active()==='conversation-card'&&document.getElementById('chat-attachment-tray').textContent.includes('SYNTHETIC ANALYSIS')"),'handoff-should-return-to-chat');
 await js("document.getElementById('clear-chat-files').click();document.querySelector('#studio-focus-nav button[data-panel=vault-card]').click();true");
 assert(await js("NexusStudioFocus.active()==='vault-card'&&!document.getElementById('vault-card').hidden"),'save-tab-not-accessible');
 await js("(()=>{document.querySelector('#studio-focus-nav button[data-panel=conversation-card]').click();const m=document.getElementById('message');m.value='SYNTHETIC PRIVATE QUESTION';m.dispatchEvent(new Event('input'));document.getElementById('studio-compose-send').click();return true})()");
 assert(await js("document.getElementById('request-review').hidden&&!document.getElementById('consent').checked"),'local-guide-must-not-stage-or-send-provider-content');
 checks.push('focused-tools-save-and-reviewed-handoff');
 assert(await js("NexusStudioUI.snapshot().projects[0].threads[0].nodes.length===2"),'guide-failed');checks.push('local-guide-works-without-provider');
 assert(await js("document.getElementById('nexus-zen-storage-indicator').textContent.includes('Unsaved changes')"),'temporary-work-must-be-labeled-unsaved');
 await js("(()=>{window.__zenOriginal=NexusStudioUI.snapshot().projects[0].threads[0].id;NexusStudioUI.startConversation(true);const search=document.getElementById('search');search.value='NO_LEGACY_MATCH';search.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('nexus-zen-menu').click();const find=document.getElementById('nexus-zen-find');find.value='SYNTHETIC PRIVATE QUESTION';find.dispatchEvent(new Event('input',{bubbles:true}));return true})()");
 assert(await js("document.getElementById('history').querySelectorAll('button').length===0&&document.querySelectorAll('#nexus-zen-history button').length===1&&document.querySelector('#nexus-zen-history button').textContent.includes('SYNTHETIC PRIVATE QUESTION')"),'drawer-history-must-ignore-legacy-filter');
 await js("document.querySelector('#nexus-zen-history button').click();true");
 assert(await js("NexusStudioUI.selection().threadId===window.__zenOriginal&&document.getElementById('nexus-zen-drawer').hidden&&document.getElementById('messages').textContent.includes('SYNTHETIC PRIVATE QUESTION')"),'direct-session-history-routing-missing');
 await js("document.getElementById('archive-thread').click();document.getElementById('nexus-zen-menu').click();true");
 assert(await js("document.querySelectorAll('#nexus-zen-history button').length===0"),'archived-chats-should-be-hidden-by-default');
 await js("document.getElementById('nexus-zen-archived').click();true");
 assert(await js("document.querySelectorAll('#nexus-zen-history button').length===1&&document.querySelector('#nexus-zen-history button').textContent.includes('Archived')"),'archived-conversation-search-not-discoverable');
 await js("document.querySelector('#nexus-zen-history button').click();document.getElementById('archive-thread').click();document.getElementById('search').value='';document.getElementById('search').dispatchEvent(new Event('input',{bubbles:true}));true");
 assert(await js("!NexusStudioUI.snapshot().projects[0].threads[0].archived&&document.getElementById('nexus-zen-drawer').hidden"),'archive-restore-not-preserved');
 checks.push('full-session-search-and-archived-toggle-independent-of-legacy-pane');
 await js("document.getElementById('studio-focus-toggle').click();true");
 assert(await js("!NexusStudioFocus.isFocused()&&document.querySelectorAll('section.card[hidden]').length===0&&document.getElementById('studio-focus-nav').hidden"),'full-view-not-restored');
 await js("document.getElementById('studio-tools-toggle').click();true");
 assert(await js("NexusStudioFocus.active()==='tools'&&!document.getElementById('studio-focus-tools').hidden&&!document.getElementById('conversation-card').hidden"),'wide-catalog-preserves-workspace');
 await js("document.querySelector('#studio-focus-tools button[data-panel=canvas-card]').click();true");
 assert(await js("NexusStudioFocus.active()==='canvas-card'&&document.getElementById('studio-focus-tools').hidden&&document.activeElement.closest('#canvas-card')"),'wide-catalog-focuses-result');
 checks.push('bilingual-tool-search-and-wide-routing');
 await js("NexusStudioFocus.openPanel('conversation-card');document.getElementById('studio-focus-toggle').click();document.getElementById('message').focus();true");
 await poll(()=>retryJs("NexusStudioFocus.isFocused()&&getComputedStyle(document.getElementById('studio-focus-nav')).display==='none'"),2200,'mobile-keyboard-dock-focus-timing');
 const keyboard=await js("({focused:NexusStudioFocus.isFocused(),typing:document.documentElement.classList.contains('studio-focus-typing'),active:document.activeElement.id,dock:getComputedStyle(document.getElementById('studio-focus-nav')).display})");
 assert(keyboard.focused&&keyboard.dock==='none','mobile-keyboard-should-not-be-obscured-'+JSON.stringify(keyboard));
 await js("document.getElementById('message').blur();true");
 checks.push('reversible-focus-keeps-content-and-keyboard-clear');
 await js("document.getElementById('studio-compose-save').click();true");
 assert(await js("NexusStudioFocus.active()==='vault-card'&&document.getElementById('passphrase')===document.activeElement&&document.getElementById('save').disabled"),'save-shortcut-did-not-route-to-locked-vault');
 await js("document.getElementById('passphrase').value='synthetic secret phrase 123';document.getElementById('repeat-passphrase').value='synthetic secret phrase 123';document.getElementById('create-vault').click();true");
 await poll(()=>retryJs("!document.getElementById('save').disabled"),12000,'archive-create');
 await js("document.querySelector('#studio-focus-nav button[data-panel=conversation-card]').click();document.getElementById('studio-compose-save').click();true");await poll(()=>retryJs("document.getElementById('status').textContent.includes('session saved')"),12000,'archive-save');
 assert(await js("document.getElementById('nexus-zen-storage-indicator').textContent.includes('Archive unlocked')"),'post-save-status-must-not-show-unsaved');checks.push('truthful-header-save-state-before-and-after-explicit-encryption');
 await js("(()=>{const m=document.getElementById('message');m.value='SYNTHETIC UNSAVED DRAFT';m.dispatchEvent(new Event('input'));return true})()");
 assert(await js("document.getElementById('studio-compose-save').disabled&&document.getElementById('studio-compose-storage').textContent.includes('not fully saved')"),'draft-save-blocked-no-false-success');
 await js("(()=>{const m=document.getElementById('message');m.value='';m.dispatchEvent(new Event('input'));return true})()");
 checks.push('archive-quick-save-delegates-encryption-and-blocks-drafts');
 assert(await js("new NexusStudio.IndexedStore().read().then(raw=>!!raw&&!raw.includes('SYNTHETIC PRIVATE QUESTION'))"),'plaintext-history');checks.push('encrypted-browser-save');
 stage='opt-in-offline';await js("document.getElementById('studio-offline').click();true");
 await poll(()=>retryJs("document.getElementById('studio-offline-state').textContent.includes('code is ready')"),25000,'offline-prepare');
 const cached=await js("(async()=>{const names=await caches.keys(),cache=await caches.open(names[0]),keys=await cache.keys();const response=await cache.match(location.origin+'/');const bytes=await response.arrayBuffer();return {names,entries:keys.map(k=>k.url),sha:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join(''),private:new TextDecoder().decode(bytes).includes('SYNTHETIC PRIVATE QUESTION')}})()");
 assert(cached.names.length===1&&cached.names[0].startsWith('nexus-studio-shell-v1-')&&cached.entries.length===5+pdfModules.length&&pdfModules.every(name=>cached.entries.includes(ORIGIN+name))&&cached.entries.includes(ORIGIN)&&cached.sha===sourceDigest&&!cached.private,'cache-not-public-code-only');checks.push('opt-in-cache-exact-public-code-only');
 await poll(()=>retryJs("Boolean(navigator.serviceWorker.controller)"),10000,'worker-control');
 await js("window.__beforeOfflineReload=true;true");
 stage='true-offline';await setOffline(true);await rpc('Page.reload',{ignoreCache:true});
 await poll(()=>retryJs("!window.__beforeOfflineReload&&navigator.onLine===false&&document.readyState==='complete'&&Boolean(window.NexusStudioUI)&&Boolean(document.getElementById('studio-offline'))"),15000,'offline-reload');
 assert(await js("NexusStudioUI.snapshot().projects.length===0"),'automatic-private-reopen');checks.push('true-offline-reload-still-locked');
 await js("document.getElementById('passphrase').value='synthetic secret phrase 123';document.getElementById('unlock').click();true");
 await poll(()=>retryJs("NexusStudioUI.snapshot().projects[0]?.title==='My conversations'"),12000,'offline-unlock');checks.push('offline-encrypted-reopen');
 stage='offline-pdf';
 await js(`(()=>{const file=document.getElementById('studio-pdf-file'),transfer=new DataTransfer();
  transfer.items.add(new File([${JSON.stringify(samplePdf())}],'fixture.pdf',{type:'application/pdf'}));
  file.files=transfer.files;file.dispatchEvent(new Event('change'));return true})()`);
 await poll(()=>retryJs("document.getElementById('studio-pdf-status').textContent.includes('ready for review')"),20000,'offline-pdf-extract');
 assert(await js("document.getElementById('chat-attachment-tray').textContent.includes('fixture.pdf')&&!JSON.stringify(NexusStudioUI.snapshot()).includes('NEXUS SYNTHETIC PDF TEST')"),'pdf-attaches-temporarily');
 checks.push('pdf-text-extracted-in-offline-worker');
 await js("document.getElementById('clear-chat-files').click();true");

 await js("document.getElementById('language').value='fa';document.getElementById('language').dispatchEvent(new Event('change'));true");
 assert(await js("document.documentElement.dir==='rtl'&&getComputedStyle(document.querySelector('.studio-en')).display==='none'&&document.querySelector('#studio-focus-nav button[data-panel=conversation-card] .studio-control-label').textContent==='گفتگو'&&document.getElementById('studio-compose-send').textContent==='استفاده از راهنمای محلی'"),'persian-static-panel');checks.push('persian-rtl-navigation-and-installation-panel');
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
