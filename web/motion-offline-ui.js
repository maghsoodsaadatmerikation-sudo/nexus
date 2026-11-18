/* NEXUS Motion: explicitly opted-in verified public shell offline cache. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const setup=$('motion-offline-prepare'),remove=$('motion-offline-remove'),
  status=$('motion-offline-status');
if(!setup||!remove||!status)return;
const BASE=new URL('./', location.href);
const PREFIX='nexus-motion-shell-v1-';
let busy=false;
const notice=(msg)=>{status.textContent=msg};
async function perform(action){
 if(busy)return;busy=true;setup.disabled=remove.disabled=true;
 try{
  if(!isSecureContext||!('serviceWorker' in navigator)||!('caches' in window))
   throw Error('A secure-context browser with service workers is needed.');
  if(action==='prepare'){
   const registration=await navigator.serviceWorker.register(
     new URL('offline-worker.js',BASE),{scope:BASE.href,updateViaCache:'none'});
   const deadline=Date.now()+18000;
   while(!registration.active||registration.active.state!=='activated'){
    if(Date.now()>deadline)throw Error('Motion offline worker activation timed out');
    await new Promise(r=>setTimeout(r,100));
   }
   await new Promise((resolve,reject)=>{
    const channel=new MessageChannel();
    const timer=setTimeout(()=>{channel.port1.close();reject(Error('Motion cache refresh timed out'))},12000);
    channel.port1.onmessage=evt=>{
     clearTimeout(timer);channel.port1.close();
     evt.data?.ok ? resolve() : reject(Error('Motion public file integrity check failed'));
    };
    registration.active.postMessage({type:'refresh-motion-shell'},[channel.port2]);
   });
   const available=(await caches.keys()).filter(x=>x.startsWith(PREFIX));
   let ready=false;
   for(const name of available){
    const cache=await caches.open(name);
    if(await cache.match(new URL('index.html',BASE).href)&&
       await cache.match(new URL('motion-core.js',BASE).href)&&
       await cache.match(new URL('motion-ui.js',BASE).href))ready=true;
   }
   if(!ready)throw Error('Offline public files are incomplete');
   notice('Motion public code prepared for offline opening. Your videos and projects are NOT cached; export them separately.');
  } else {
   const reg=await navigator.serviceWorker.getRegistration(BASE.href);
   if(reg&&reg.scope===BASE.href)await reg.unregister();
   await Promise.all((await caches.keys()).filter(k=>k.startsWith(PREFIX)).map(k=>caches.delete(k)));
   notice('Motion offline copy removed. Your current editor tab and exported files are unchanged.');
  }
 }catch(e){notice('Offline setup not completed: '+e.message);}
 finally{busy=false;setup.disabled=remove.disabled=false;}
}
setup.onclick=()=>perform('prepare');
remove.onclick=()=>perform('remove');
})();
