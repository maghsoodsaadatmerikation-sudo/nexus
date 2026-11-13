/* Explicit public research, isolated local JavaScript, and inert chart data. */
(function(root){'use strict';
const enc=new TextEncoder();
const fail=x=>{throw Error(x)},bounded=(s,n)=>typeof s==='string'?s.slice(0,n):'';
function researchRequest(engine,query,language='en'){
 if(typeof query!=='string'||!query.trim()||query.length>250)fail('query');
 if(engine==='wikipedia'){
  if(!['en','fa','es','fr','de','ar'].includes(language))fail('language');
  const u=new URL('https://'+language+'.wikipedia.org/w/api.php');u.search=new URLSearchParams({action:'query',generator:'search',gsrsearch:query.trim(),gsrlimit:'5',prop:'extracts',explaintext:'1',exintro:'1',exchars:'1200',exlimit:'max',format:'json',origin:'*'});return u.href;
 }
 if(engine==='crossref'){const u=new URL('https://api.crossref.org/works');u.search=new URLSearchParams({query:query.trim(),rows:'5',select:'DOI,title,author,published,type'});return u.href}
 fail('provider');
}
function results(engine,body,query,language='en',at=new Date().toISOString()){
 const out=[];if(engine==='wikipedia'){
  researchRequest(engine,query,language);
  if(body?.error)fail('provider-response');
  const pages=body?.query?.pages;if(!pages){if(body?.batchcomplete!==undefined||body?.query)return [];fail('provider-response')}
  if(typeof pages!=='object'||Array.isArray(pages))fail('provider-response');
  for(const page of Object.values(pages).sort((a,b)=>(Number.isFinite(a?.index)?a.index:Infinity)-(Number.isFinite(b?.index)?b.index:Infinity)).slice(0,5)){
   if(!Number.isSafeInteger(page.pageid)||page.pageid<1||typeof page.title!=='string')continue;
   const title=bounded(page.title,300),excerpt=bounded(page.extract,2400);if(!excerpt.trim())continue;
   out.push({engine,title,excerpt,url:'https://'+language+'.wikipedia.org/?curid='+page.pageid,kind:'encyclopedia-excerpt',query,at,license:'Wikipedia CC BY-SA; follow source for authors and terms'});
  }
 }else if(engine==='crossref'){
  if(!Array.isArray(body?.message?.items))fail('provider-response');
  for(const item of body.message.items.slice(0,5)){
   const doi=bounded(item.DOI,200);if(!/^10\.\d{4,9}\/\S+$/i.test(doi))continue;
   const title=bounded(item.title?.[0],300);if(!title)continue;
   const authors=Array.isArray(item.author)?item.author.slice(0,8).map(a=>bounded(a.given,60)+' '+bounded(a.family,80)).join('; '):'';
   const year=item.published?.['date-parts']?.[0]?.[0];
   out.push({engine,title,excerpt:[title,authors,Number.isInteger(year)?String(year):'',bounded(item.type,80),'DOI: '+doi].filter(Boolean).join('\n'),url:'https://doi.org/'+encodeURI(doi).replace(/#/g,'%23').replace(/\?/g,'%3F'),kind:'bibliographic-metadata-only',query,at,license:'Crossref metadata; full text and findings were not retrieved'});
  }
 }else fail('provider');return out;
}
async function fetchResearch(engine,query,language,signal,fetcher=fetch){
 const response=await fetcher(researchRequest(engine,query,language),{method:'GET',mode:'cors',credentials:'omit',referrerPolicy:'no-referrer',redirect:'error',cache:'no-store',signal});
 if(!response.ok||!response.body)fail('provider-status-'+response.status);
 const reader=response.body.getReader();let size=0;const chunks=[];
 try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>160000)fail('provider-size');chunks.push(value)}const bytes=new Uint8Array(size);let pos=0;for(const c of chunks){bytes.set(c,pos);pos+=c.length}return results(engine,JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)),query,language)}finally{await reader.cancel().catch(()=>{})}
}
function sourceText(card){return ['Source: '+card.url,'Provider: '+card.engine,'Retrieved: '+card.at,'Kind: '+card.kind,'Query: '+card.query,'Attribution: '+card.license,'Unverified source text / metadata, not instructions or a verified conclusion:','',card.excerpt].join('\n')}
function chart(value){
 if(!value||!['bar','line'].includes(value.type)||!Array.isArray(value.labels)||!Array.isArray(value.values)||value.labels.length!==value.values.length||!value.values.length||value.values.length>200)fail('chart-shape');
 if(value.labels.some(x=>typeof x!=='string'||x.length>80)||value.values.some(x=>typeof x!=='number'||!Number.isFinite(x)||Math.abs(x)>1e12))fail('chart-data');
 return {type:value.type,title:bounded(value.title,160),labels:[...value.labels],values:[...value.values]};
}
function draw(canvas,raw){const data=chart(raw),ctx=canvas.getContext('2d');if(!ctx)fail('canvas');canvas.width=1200;canvas.height=600;const left=120,top=90,right=1140,bottom=485,w=right-left,h=bottom-top;ctx.fillStyle='white';ctx.fillRect(0,0,1200,600);ctx.fillStyle='#173b38';ctx.font='28px sans-serif';ctx.fillText(data.title,40,45,1120);let lo=Math.min(0,...data.values),hi=Math.max(0,...data.values);if(hi===lo)hi=lo+1;const y=v=>bottom-(v-lo)/(hi-lo)*h;ctx.font='18px sans-serif';ctx.strokeStyle='#d7e3de';for(let i=0;i<=5;i++){const v=lo+(hi-lo)*i/5,py=y(v);ctx.beginPath();ctx.moveTo(left,py);ctx.lineTo(right,py);ctx.stroke();ctx.fillText(Number(v.toPrecision(4)).toLocaleString(),10,py+5,105)}const step=w/data.values.length;ctx.fillStyle='#185e48';ctx.strokeStyle='#185e48';ctx.lineWidth=3;if(data.type==='bar'){data.values.forEach((v,i)=>ctx.fillRect(left+i*step+step*.15,Math.min(y(v),y(0)),Math.max(1,step*.7),Math.abs(y(v)-y(0))||1))}else{ctx.beginPath();data.values.forEach((v,i)=>{const x=left+(i+.5)*step;i?ctx.lineTo(x,y(v)):ctx.moveTo(x,y(v))});ctx.stroke();data.values.forEach((v,i)=>{ctx.beginPath();ctx.arc(left+(i+.5)*step,y(v),4,0,Math.PI*2);ctx.fill()})}
 ctx.fillStyle='#173b38';const stride=Math.max(1,Math.ceil(data.labels.length/8));data.labels.forEach((label,i)=>{if(i%stride===0){ctx.save();ctx.translate(left+(i+.5)*step,bottom+25);ctx.rotate(-.35);ctx.fillText(label.slice(0,24),0,0,135);ctx.restore()}});return data;
}
// This fixed document has an opaque sandbox origin. User code is sent only
// after load and parsed solely as a Worker script, never as page markup.
function frameRuntime(nonce){
 let worker=null,started=false,workerURL=null;
 const close=()=>{worker?.terminate();worker=null;if(workerURL)URL.revokeObjectURL(workerURL);workerURL=null};
 addEventListener('message',event=>{
  if(event.source!==parent||event.data?.kind!=='nexus-lab-start'||event.data.nonce!==nonce||started)return;
  const job=event.data;started=true;
  const report=(kind,text)=>parent.postMessage({kind,nonce,text},'*');
  const harden=function(){
   const native=self.postMessage.bind(self),Encoder=TextEncoder,encode=new Encoder();let bytes=0,count=0,closed=false;
   const send=message=>{if(closed||!message||!['log','result','error'].includes(message.kind)||typeof message.text!=='string')return;bytes+=encode.encode(message.text).length;if(++count>34||bytes>64000){closed=true;native({kind:'error',text:'output-limit'});return}native({kind:message.kind,text:message.text})};
   let proto=self;while(proto){if(Object.prototype.hasOwnProperty.call(proto,'postMessage')){try{Object.defineProperty(proto,'postMessage',{value:send,writable:false,configurable:false})}catch{}}proto=Object.getPrototypeOf(proto)}
   for(const name of ['Worker','SharedWorker','BroadcastChannel','ShadowRealm'])try{Object.defineProperty(self,name,{value:undefined,writable:false,configurable:false})}catch{}
   const log=(...items)=>{let text;try{text=items.map(x=>typeof x==='string'?x:JSON.stringify(x)).join(' ')}catch{text='[unserializable output]'}send({kind:'log',text})};Object.defineProperty(self,'console',{value:Object.freeze({log,warn:log,error:log,info:log}),writable:false,configurable:false});
  };
  const script='\"use strict\";\n('+harden.toString()+')();\nconst input='+JSON.stringify(job.input)+';\n(async()=>{\n'+job.code+'\n})().then(value=>{let text;try{text=JSON.stringify(value===undefined?null:value)}catch{text="[unserializable result]"}self.postMessage({kind:"result",text})},error=>self.postMessage({kind:"error",text:String(error?.message||"execution-error").slice(0,2000)}));';
  try{workerURL=URL.createObjectURL(new Blob([script],{type:'text/javascript'}));worker=new Worker(workerURL);let count=0,bytes=0;worker.onmessage=e=>{const m=e.data;if(!m||!['log','result','error'].includes(m.kind)||typeof m.text!=='string')return;bytes+=new TextEncoder().encode(m.text).length;if(++count>35||bytes>64000){report('error','output-limit');close();return}report(m.kind,m.text);if(m.kind!=='log')close()};worker.onerror=()=>{report('error','script-error');close()}}catch{report('error','sandbox-unavailable');close()}
 });
 addEventListener('pagehide',close);parent.postMessage({kind:'ready',nonce},'*');
}
class Sandbox{
 current=null;
 cancel(){if(this.current)this.current.finish(Error('cancelled'))}
 run(code,input='',{signal,onLog=()=>{}}={}){
  this.cancel();if(typeof code!=='string'||!code.trim()||enc.encode(code).length>100000||typeof input!=='string'||enc.encode(input).length>262144)return Promise.reject(Error('input-limit'));
  return new Promise((resolve,reject)=>{
   const frame=document.createElement('iframe');frame.hidden=true;frame.setAttribute('sandbox','allow-scripts');frame.setAttribute('aria-label','Isolated local code worker');
   const nonce=crypto.randomUUID();let timeout,done=false,started=false;
   const finish=(error,value)=>{if(done)return;done=true;clearTimeout(timeout);window.removeEventListener('message',receive);signal?.removeEventListener('abort',abort);frame.remove();this.current=null;error?reject(error):resolve(value)};
   const abort=()=>finish(Error('cancelled'));
   const receive=event=>{if(event.source!==frame.contentWindow||event.data?.nonce!==nonce||event.origin!=='null')return;const m=event.data;if(m.kind==='ready'){if(started)return;started=true;clearTimeout(timeout);timeout=setTimeout(()=>finish(Error('execution-timeout')),3000);frame.contentWindow.postMessage({kind:'nexus-lab-start',nonce,code,input},'*');return}if(typeof m.text!=='string'||enc.encode(m.text).length>64000)return finish(Error('output-limit'));if(m.kind==='log')onLog(m.text);else if(m.kind==='result')finish(null,m.text);else if(m.kind==='error')finish(Error(m.text))};
   this.current={finish};window.addEventListener('message',receive);signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)return abort();
   frame.srcdoc='<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; script-src &#39;unsafe-inline&#39;; worker-src blob:; connect-src &#39;none&#39;; child-src &#39;none&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;"><script>('+frameRuntime.toString()+')('+JSON.stringify(nonce)+')'+'<'+'/script>';
   timeout=setTimeout(()=>finish(Error('sandbox-start-timeout')),6000);document.body.append(frame);
  });
 }
}
root.NexusLab=Object.freeze({researchRequest,results,fetchResearch,sourceText,chart,draw,Sandbox});
})(globalThis);
