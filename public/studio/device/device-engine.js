/* Main-thread controller: no prompts in downloads/cache, one bounded Worker. */
export const CACHE='nexus-device-artifacts-v1';
export function assessReadiness(input){
 const missing=['secure','worker','wasm','cache','crypto'].filter(key=>input[key]!==true);
 const memory=Number.isFinite(input.memoryGiB)?input.memoryGiB:null;
 const free=Number.isFinite(input.quota)&&Number.isFinite(input.usage)?Math.max(0,input.quota-input.usage):null;
 const required=Math.ceil(input.downloadBytes*3);
 const issues=[...missing.map(key=>'missing-'+key)];
 if(memory!==null&&memory<4)issues.push('insufficient-device-memory');
 if(memory===null)issues.push('memory-unknown');
 if(free===null)issues.push('storage-unknown');else if(free<required)issues.push('storage-low');
 return {schema:'nexus.device-readiness.v1',status:missing.length||(memory!==null&&memory<4)?'blocked':issues.length?'advisory':'basic-checks-pass',issues,memory_gib:memory,storage_available_bytes:free,storage_headroom_bytes:required,model_execution_verified:false};
}
export async function inspectReadiness(downloadBytes){
 let storage={};try{storage=await navigator.storage?.estimate()||{}}catch{}
 return assessReadiness({secure:globalThis.isSecureContext===true,worker:typeof Worker==='function',wasm:typeof WebAssembly==='object',cache:typeof caches==='object',crypto:!!globalThis.crypto?.subtle,memoryGiB:navigator.deviceMemory,quota:storage.quota,usage:storage.usage,downloadBytes});
}
export class DeviceEngine{
 constructor({workerURL,onStatus=()=>{}}){this.workerURL=workerURL;this.onStatus=onStatus;this.worker=null;this.state='idle';this.details=null;this.pending=null;this.serial=0;this.evidence={}}
 info(){return this.state==='ready'?{ready:true,...this.details}:null}
 report(){
  return {schema:'nexus.device-runtime-report.v1',scope:'local-runtime-observation',state:this.state,model:this.details?.model||null,configuration_id:this.details?.configuration_id||null,model_loaded:!!this.details,generation_observed:this.evidence.generated===true,input_tokens:this.evidence.inputTokens??null,max_output_tokens:this.evidence.budget??null,elapsed_ms:this.evidence.elapsed??null,quality_evaluated:false,physical_android_verified:false,authority:'none'};
 }
 unload(reason='cancelled'){this.worker?.terminate();this.worker=null;this.details=null;this.state='idle';this.evidence={};if(this.pending){this.pending.reject(Error(reason));this.pending=null}this.onStatus({type:'idle',reason})}
 async load({consent=false}={}){
  if(consent!==true)throw Error('explicit-consent-required');
  if(this.state!=='idle')throw Error('model-busy');
  if(!globalThis.Worker||!globalThis.WebAssembly||!globalThis.caches||!globalThis.crypto?.subtle)throw Error('unsupported-device');
  if(navigator.deviceMemory&&navigator.deviceMemory<4)throw Error('insufficient-device-memory');
  this.state='loading';let worker;try{worker=new Worker(this.workerURL,{type:'module'})}catch{this.state='idle';throw Error('worker-start-failed')}this.worker=worker;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{if(this.worker===worker)this.unload('load-timeout')},300000);
   const done=(fn,value)=>{clearTimeout(timer);fn(value)};
   this.pending={reject:error=>done(reject,error)};
   worker.onerror=()=>{if(this.worker===worker)this.unload('worker-failed')};
   worker.onmessage=event=>{
    if(this.worker!==worker)return;const data=event.data;
    if(data.type==='download'||data.type==='phase'){this.onStatus(data);return}
    if(data.type==='ready'){this.state='ready';this.details=data;this.pending=null;done(resolve,this.info());this.onStatus(data)}
    else if(data.type==='error'){this.onStatus(data);this.pending?.reject(Error(data.code));this.pending=null;if(data.phase==='loading')this.unload();else{this.state='ready';this.onStatus(data)}}
    else if(data.type==='result'&&this.pending?.id===data.id){const pending=this.pending;this.pending=null;this.state='ready';this.evidence={generated:true,inputTokens:Number.isSafeInteger(data.input_tokens)?data.input_tokens:null,budget:this.evidence.budget,elapsed:Math.max(0,Math.round(performance.now()-this.evidence.started))};pending.resolve(data);this.onStatus({type:'ready',...this.details})}
   };
   worker.postMessage({type:'load',consent:true});
  });
 }
 generate(body,signal){
  if(!this.info()||body?.consent!==true||body.configuration_id!==this.details.configuration_id||signal?.aborted)return Promise.reject(Error('invalid-review'));
  this.state='generating';this.evidence={started:performance.now(),budget:body.max_output_tokens??64};const id=++this.serial;
  return new Promise((resolve,reject)=>{
   const abort=()=>this.unload(),timer=setTimeout(()=>this.unload('generation-timeout'),120000);
   const cleanup=()=>{clearTimeout(timer);signal?.removeEventListener('abort',abort)};
   this.pending={id,resolve:value=>{cleanup();resolve(value)},reject:error=>{cleanup();reject(error)}};
   signal?.addEventListener('abort',abort,{once:true});this.worker.postMessage({type:'generate',id,body});this.onStatus({type:'generating'});
  });
 }
 async erase(){this.unload();await caches.delete(CACHE)}
}
