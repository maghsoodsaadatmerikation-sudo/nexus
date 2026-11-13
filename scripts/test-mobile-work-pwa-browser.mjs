#!/usr/bin/env node
/* Real Chromium mobile PWA acceptance. All content synthetic and disposable.
   An actual Chrome CDP network outage is used; no cloud/production provider. */
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';

const root=path.resolve(process.argv[2]||'build/stage23-mobile');
const browser=process.env.NEXUS_STAGE23_CHROME;
if(!browser||typeof WebSocket==='undefined'||
   process.env.NEXUS_API_TOKEN||process.env.RAILWAY_TOKEN||
   process.env.RAILWAY_API_TOKEN||process.env.RENDER_API_KEY)
  throw Error('real-private-browser-without-provider-secrets-required');

const files=new Map();
for(const name of ['index.html','manifest.json','service-worker.js',
                   'icons/nexus-192.png','icons/nexus-512.png'])
  files.set(name,await readFile(path.join(root,name)));
const mime=name=>name.endsWith('.html')?'text/html; charset=utf-8':
  name.endsWith('.json')?'application/json':
  name.endsWith('.js')?'text/javascript':'image/png';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const assert=(ok,key)=>{if(!ok)throw Error(key)};
const reports=[];
for(const [layout,width,prefix] of [['mobile',500,'/'],['nested',1280,'/nexus-stage23/']]){
 let tamper=false,privateRequest=0;
 const server=createServer((req,res)=>{
   const url=new URL(req.url||'/', 'http://127.0.0.1');
   const relative=url.pathname.startsWith(prefix)?
     url.pathname.slice(prefix.length):null;
   const name=relative===''?'index.html':relative;
   if(req.method!=='GET'||url.search||!files.has(name)){
     if(url.pathname!=='/favicon.ico')privateRequest++;
     res.writeHead(404,{'Content-Type':'text/plain'});res.end('not found');return;
   }
   let data=files.get(name);
   if(tamper&&name==='index.html')
     data=Buffer.from(data.toString().replace('Offline portable Work Mode',
               'INVALID_UNVERIFIED_PUBLIC_HTML'),'utf8');
   res.writeHead(200,{'Content-Type':mime(name),'Cache-Control':'no-store'});
   res.end(data);
 });
 await new Promise((yes,no)=>{server.once('error',no);server.listen(0,'127.0.0.1',yes)});
 const base='http://127.0.0.1:'+server.address().port+prefix;
 const profile=await mkdtemp(path.join(tmpdir(),'nexus-stage23-'+layout+'-'));
 let socket,child,closed=false,serial=0;
 const pending=new Map(),checks=[];
 try{
   child=spawn(browser,['--headless','--no-sandbox','--disable-dev-shm-usage',
     '--disable-background-networking','--disable-extensions','--no-first-run',
     '--no-default-browser-check','--remote-debugging-address=127.0.0.1',
     '--remote-debugging-port=0','--user-data-dir='+profile,
     '--window-size='+width+',980','about:blank'],{stdio:['ignore','ignore','ignore']});
   child.once('exit',()=>{closed=true});
   const until=async(fn,ms,label)=>{
     const deadline=Date.now()+ms;
     while(Date.now()<deadline){
       if(closed)throw Error('headless-chromium-exited');
       try{const value=await fn();if(value)return value}catch(e){
         if(e.message?.includes('browser-evaluation-error'))throw e;
       }
       await delay(80);
     }
     throw Error(label+'-timed-out');
   };
   const active=await until(async()=>{
     try{return (await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]}
     catch{return null}
   },30000,'chrome-port');
   const target=await until(async()=>{
     try{
       const r=await fetch('http://127.0.0.1:'+active+'/json/list',
                           {signal:AbortSignal.timeout(2000)});
       return (await r.json()).find(x=>x.type==='page');
     }catch{return null}
   },15000,'chrome-target');
   const endpoint=new URL(target.webSocketDebuggerUrl);
   assert(endpoint.hostname==='127.0.0.1'&&endpoint.port===active,'loopback-devtools-only');
   socket=new WebSocket(endpoint.href);
   await new Promise((yes,no)=>{
     const timeout=setTimeout(()=>no(Error('cdp-socket-timeout')),5000);
     socket.addEventListener('open',()=>{clearTimeout(timeout);yes()},{once:true});
     socket.addEventListener('error',()=>{clearTimeout(timeout);no(Error('cdp-socket-failed'))},{once:true});
   });
   socket.addEventListener('message',event=>{
     let result;
     try{result=JSON.parse(event.data)}catch{return}
     const item=pending.get(result.id);if(!item)return;
     pending.delete(result.id);clearTimeout(item.timer);
     if(result.error)item.reject(Error('cdp-response-error'));
     else item.resolve(result.result);
   });
   function rpc(method,params={},timeout=10000){
     return new Promise((resolve,reject)=>{
       const id=++serial;
       const timer=setTimeout(()=>{pending.delete(id);reject(Error('cdp-timeout'))},timeout);
       pending.set(id,{resolve,reject,timer});
       socket.send(JSON.stringify({id,method,params}));
     });
   }
   async function evaluate(expression){
     const result=await rpc('Runtime.evaluate',
        {expression,returnByValue:true,awaitPromise:true},15000);
     if(result.exceptionDetails)throw Error('browser-evaluation-error');
     return result.result?.value;
   }
   const poll=(expression,ms,label)=>until(()=>evaluate(expression),ms,label);
   const checked=(condition,label)=>{assert(condition,label);checks.push(label)};
   await rpc('Page.enable');await rpc('Runtime.enable');await rpc('Network.enable');
   await rpc('Page.navigate',{url:base});
   await poll('location.href==='+JSON.stringify(base)+
              "&&document.readyState==='complete'",20000,'initial-navigation');
   let start=await evaluate("(async()=>({reg:!!(await navigator.serviceWorker.getRegistration()),"+
     "vault:typeof vault==='object',stored:(await caches.keys()).filter(x=>x.startsWith('nexus-stage23-shell-')).length,"+
     "canCrypto:!!crypto.subtle,manifest:!!document.querySelector('link[rel=manifest]')}))()");
   checked(!start.reg&&start.stored===0&&start.vault&&start.canCrypto&&start.manifest,
           'no-auto-worker-or-private-vault');
   await evaluate("document.getElementById('mobile-prepare').click();true");
   await poll("(document.getElementById('mobile-state').textContent.includes('prepared'))",
              25000,'explicit-offline-preparation');
   let state=await evaluate("(async()=>{const keys=(await caches.keys()).filter(x=>x.startsWith('nexus-stage23-shell-'));"+
     "const c=await caches.open(keys[0]);return {n:keys.length,paths:(await c.keys()).map(x=>new URL(x.url).pathname),"+
     "registered:!!(await navigator.serviceWorker.getRegistration()),controller:!!navigator.serviceWorker.controller}})()");
   checked(state.n===1&&state.registered&&state.paths.length===4&&
            state.paths.every(p=>p.startsWith(prefix)),'four-public-assets-only');
   checked(state.controller,'same-scope-service-worker-controls-app');
   // Synthetic project: explicit creation, review and encrypted persistence.
   const prepareProject="(()=>{const fill=(id,v)=>{const e=document.getElementById(id);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}))};"+
     "fill('title','STAGE23_PRIVATE_TITLE');fill('goal','STAGE23_PRIVATE_GOAL');"+
     "fill('steps','Review evidence');document.getElementById('create').click();"+
     "return current?.tasks.length===1&&current.tasks[0].status==='todo'})()";
   checked(await evaluate(prepareProject),'human-project-created');
   checked(await evaluate("(()=>{document.getElementById('task-status').value='done';"+
     "document.getElementById('task-status').dispatchEvent(new Event('input'));"+
     "document.getElementById('apply-task').click();return current.tasks[0].status==='todo'})()"),
     'unreviewed-completion-rejected');
   const write="(()=>{let e=document.getElementById('evidence');e.value='STAGE23_PRIVATE_EVIDENCE';"+
     "e.dispatchEvent(new Event('input'));document.getElementById('task-status').value='done';"+
     "document.getElementById('task-status').dispatchEvent(new Event('input'));"+
     "let c=document.getElementById('reviewed');c.checked=true;"+
     "c.dispatchEvent(new Event('input'));document.getElementById('apply-task').click();"+
     "return current.tasks[0].status==='done'})()";
   checked(await evaluate(write),'human-reviewed-completion');
   await evaluate("(()=>{const f=(id,v)=>{document.getElementById(id).value=v};"+
     "f('pass','synthetic-stage23-private-phrase');f('repeat','synthetic-stage23-private-phrase');"+
     "document.getElementById('vault-create').click();return true})()");
   await poll("!busy&&vault.unlocked",25000,'vault-create');
   await evaluate("document.getElementById('save').click();true");
   await poll("!busy&&!dirty&&vault.list().length===1",25000,'encrypted-save');
   const priv=await evaluate("(async()=>{const v=JSON.stringify(await vault.store.read());"+
     "return !v.includes('STAGE23_PRIVATE_TITLE')&&!v.includes('STAGE23_PRIVATE_GOAL')&&"+
     "!v.includes('STAGE23_PRIVATE_EVIDENCE')})()");
   checked(priv,'AES-GCM-no-plaintext-in-indexeddb');
   state=await evaluate("(async()=>{const ks=(await caches.keys()).filter(k=>k.startsWith('nexus-stage23-shell-'));"+
     "const c=await caches.open(ks[0]);let bytes='';for(const req of await c.keys()){const r=await c.match(req);"+
     "if(new URL(req.url).pathname.endsWith('index.html'))bytes+=await r.text()}"+
     "return {keys:(await c.keys()).length,private:bytes.includes('STAGE23_PRIVATE')}})()");
   checked(state.keys===4&&!state.private,'cache-excludes-project-content');
   // Tampered online HTML must never be accepted by the installed worker.
   tamper=true;
   await rpc('Page.reload',{ignoreCache:false});
   await poll("document.readyState==='complete'&&"+
              "document.getElementById('mobile-pwa')!==null",15000,'tampered-online-reload');
   const tampered=await evaluate("document.documentElement.outerHTML.includes('INVALID_UNVERIFIED_PUBLIC_HTML')");
   checked(!tampered,'tampered-online-html-falls-back-to-verified-cache');
   tamper=false;
   // True network outage, not simply mocking window.fetch.
   await rpc('Network.setCacheDisabled',{cacheDisabled:true});
   await rpc('Network.emulateNetworkConditions',
      {offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
   await rpc('Page.reload',{ignoreCache:false});
   await poll("document.readyState==='complete'&&"+
              "document.getElementById('mobile-pwa')!==null",15000,'actual-offline-reload');
   checked(await evaluate("document.getElementById('portable-mode')!==null"),
           'actual-offline-shell-reopens');
   await evaluate("document.getElementById('pass').value='synthetic-stage23-private-phrase';"+
                  "document.getElementById('unlock').click();true");
   await poll("!busy&&vault.unlocked&&vault.list().length===1",
              25000,'offline-vault-unlock');
   checked(await evaluate("vault.list()[0].title==='STAGE23_PRIVATE_TITLE'"),
           'offline-archive-decrypted-after-real-network-outage');
   await rpc('Network.emulateNetworkConditions',
      {offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
   await evaluate("window.confirm=()=>true;document.getElementById('mobile-remove').click();true");
   await poll("document.getElementById('mobile-state').textContent.includes('removed')",
              15000,'offline-shell-remove');
   const cleared=await evaluate("(async()=>({reg:!!(await navigator.serviceWorker.getRegistration()),"+
     "old:(await caches.keys()).filter(x=>x.startsWith('nexus-stage23-shell-')).length,"+
     "vault:vault.unlocked&&vault.list().length===1}))()");
   checked(!cleared.reg&&cleared.old===0&&cleared.vault,
           'uninstall-only-app-shell-preserves-encrypted-project');
   checked(privateRequest===0,'only-allowlisted-public-static-requests');
   reports.push({layout,viewport:width,scope:prefix,checks,
     real_chrome:true,actual_network_outage:true,synthetic_only:true,
     android_hardware:false,public_deployment:false,authority:'human'});
 }finally{
   if(socket?.readyState===WebSocket.OPEN){socket.close()}
   if(child&&!closed){child.kill('SIGTERM');await delay(200);if(!closed)child.kill('SIGKILL')}
   await rm(profile,{recursive:true,force:true});
   await new Promise(done=>server.close(done));
 }
}
assert(reports.length===2&&reports.every(r=>r.checks.length>=11),'two-viewport-witness-required');
process.stdout.write(JSON.stringify({
 schema:'nexus.stage23.mobile-pwa-browser.v1',status:'PASS',
 reports,real_android_tested:false,production_deployed:false,
 original_railway_backup_tested:false,release_seal:false
})+'\n');
