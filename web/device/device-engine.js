/* Main-thread controller: no prompts in downloads/cache, one bounded Worker. */
export const CACHE='nexus-device-artifacts-v1';
export class DeviceEngine{
 constructor({workerURL,onStatus=()=>{}}){this.workerURL=workerURL;this.onStatus=onStatus;this.worker=null;this.state='idle';this.details=null;this.pending=null;this.serial=0}
 info(){return this.state==='ready'?{ready:true,...this.details}:null}
 unload(){this.worker?.terminate();this.worker=null;this.details=null;this.state='idle';if(this.pending){this.pending.reject(Error('cancelled'));this.pending=null}this.onStatus({type:'idle'})}
 async load({consent=false}={}){
  if(consent!==true)throw Error('explicit-consent-required');
  if(this.state!=='idle')throw Error('model-busy');
  if(!globalThis.Worker||!globalThis.WebAssembly||!globalThis.caches||!globalThis.crypto?.subtle)throw Error('unsupported-device');
  if(navigator.deviceMemory&&navigator.deviceMemory<4)throw Error('insufficient-device-memory');
  this.state='loading';const worker=new Worker(this.workerURL,{type:'module'});this.worker=worker;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{if(this.worker===worker)this.unload()},300000);
   const done=(fn,value)=>{clearTimeout(timer);fn(value)};
   this.pending={reject:error=>done(reject,error)};
   worker.onerror=()=>{if(this.worker===worker)this.unload()};
   worker.onmessage=event=>{
    if(this.worker!==worker)return;const data=event.data;
    if(data.type==='download'||data.type==='phase'){this.onStatus(data);return}
    if(data.type==='ready'){this.state='ready';this.details=data;this.pending=null;done(resolve,this.info());this.onStatus(data)}
    else if(data.type==='error'){this.onStatus(data);this.pending?.reject(Error(data.code));this.pending=null;if(data.phase==='loading')this.unload();else{this.state='ready';this.onStatus(data)}}
    else if(data.type==='result'&&this.pending?.id===data.id){const pending=this.pending;this.pending=null;this.state='ready';pending.resolve(data);this.onStatus({type:'ready',...this.details})}
   };
   worker.postMessage({type:'load',consent:true});
  });
 }
 generate(body,signal){
  if(!this.info()||body?.consent!==true||body.configuration_id!==this.details.configuration_id||signal?.aborted)return Promise.reject(Error('invalid-review'));
  this.state='generating';const id=++this.serial;
  return new Promise((resolve,reject)=>{
   const abort=()=>this.unload(),timer=setTimeout(abort,120000);
   const cleanup=()=>{clearTimeout(timer);signal?.removeEventListener('abort',abort)};
   this.pending={id,resolve:value=>{cleanup();resolve(value)},reject:error=>{cleanup();reject(error)}};
   signal?.addEventListener('abort',abort,{once:true});this.worker.postMessage({type:'generate',id,body});this.onStatus({type:'generating'});
  });
 }
 async erase(){this.unload();await caches.delete(CACHE)}
}
