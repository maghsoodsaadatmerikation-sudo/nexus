// Exercise exact generated service-worker routing using synthetic cache/network.
// Native caller provides actual artifact bytes and SHA-256, not a live browser.
export async function checkStudioCachePolicy({worker,html,orchestra,sha256,URLClass=URL,ResponseClass=Response}){
 const origin='https://studio.test/',moduleUrl=origin+'studio-orchestra.js';
 const checks=[],assert=(ok,label)=>{if(!ok)throw Error('cache-policy-'+label);checks.push(label)};
 const response=(bytes,mime,extra={})=>({status:200,type:'basic',redirected:false,headers:{get:()=>mime},
  clone(){return this},async arrayBuffer(){return Uint8Array.from(bytes).buffer},...extra});
 const moduleResponse=response(orchestra,'text/javascript'),htmlResponse=response(html,'text/html');
 const corrupt=Uint8Array.from(orchestra);corrupt[0]^=1;
 const corruptModule=response(corrupt,'text/javascript');
 const wrongMime=response(orchestra,'text/html');
 const broken=Error('synthetic-cache-or-network-error');
 function host(cached,network){
  const listeners={},trace=[];
  const self={location:{href:origin+'service-worker.js'},addEventListener:(type,fn)=>listeners[type]=fn};
  const caches={open:async()=>{trace.push('cache');if(cached===broken)throw broken;return {match:async()=>cached}}};
  const fetch=async()=>{trace.push('network');if(network===broken)throw broken;return network};
  const crypto={subtle:{digest:async(algorithm,bytes)=>{if(algorithm!=='SHA-256')throw Error('algorithm');return sha256(new Uint8Array(bytes))}}};
  new Function('self','caches','fetch','crypto','Response','URL',worker)(self,caches,fetch,crypto,ResponseClass,URLClass);
  return {trace,async request(url=moduleUrl,method='GET',mode='cors'){
   let result;listeners.fetch({request:{url,method,mode},respondWith:p=>{result=p}});return await result;
  }};
 }
 const order=(h,expected,label)=>assert(h.trace.join(',')===expected,label);
 let h=host(moduleResponse,broken);
 assert(await h.request()===moduleResponse,'valid-module-cache');order(h,'cache','valid-cache-zero-network');
 h=host(corruptModule,moduleResponse);
 assert(await h.request()===moduleResponse,'corrupt-cache-valid-network');order(h,'cache,network','corrupt-cache-fallback-order');
 h=host(undefined,moduleResponse);
 assert(await h.request()===moduleResponse,'missing-cache-valid-network');order(h,'cache,network','missing-cache-fallback-order');
 h=host(broken,moduleResponse);
 assert(await h.request()===moduleResponse,'cache-error-valid-network');order(h,'cache,network','cache-error-fallback-order');
 h=host(wrongMime,moduleResponse);
 assert(await h.request()===moduleResponse,'wrong-mime-cache-rejected');order(h,'cache,network','mime-fallback-order');
 h=host(corruptModule,corruptModule);
 assert((await h.request()).status===503,'both-digests-invalid');order(h,'cache,network','invalid-digests-fallback-order');
 h=host(broken,broken);
 assert((await h.request()).status===503,'both-sources-error');order(h,'cache,network','both-sources-error-order');
 h=host(htmlResponse,htmlResponse);
 assert(await h.request(origin,'GET','navigate')===htmlResponse,'html-valid-network');order(h,'network','navigation-network-first');
 h=host(htmlResponse,broken);
 assert(await h.request(origin+'index.html','GET','navigate')===htmlResponse,'html-offline-fallback');order(h,'network,cache','navigation-fallback-order');
 h=host(undefined,broken);
 assert((await h.request(origin,'GET','navigate')).status===503,'html-both-unavailable');order(h,'network,cache','navigation-unavailable-order');
 h=host(moduleResponse,moduleResponse);
 for(const [url,method,mode] of [[moduleUrl+'?q=1','GET','cors'],[moduleUrl,'POST','cors'],[origin+'unknown.js','GET','cors'],['https://other.test/studio-orchestra.js','GET','cors'],[origin,'GET','cors']]){
  assert(await h.request(url,method,mode)===undefined,'unreviewed-request-not-intercepted');
 }
 order(h,'','unreviewed-requests-no-cache-or-network');
 return checks;
}
