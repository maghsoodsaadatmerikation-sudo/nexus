// Exact PDF UI controller, synthetic DOM, deferred file/module reads and Worker.
export async function checkPdfResourcePolicy(source){
 const checks=[],ok=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
 const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve()};
 const nodes=new Map(),events=new Map(),workers=[],timers=new Map(),staged=[];
 const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',files:[],disabled:false,textContent:'',title:'',addEventListener(type,fn){this[type]=fn}});return nodes.get(id)};
 const document={documentElement:{lang:'en'},getElementById:node,addEventListener(type,fn){if(!events.has(type))events.set(type,[]);events.get(type).push(fn)}};
 const emit=type=>{for(const fn of events.get(type)||[])fn()};
 let owner=null,selection={projectId:'p1',threadId:'t1'},busy=false,archived=false,read,module,loading;
 const gate={audioBusy:()=>owner!==null,acquireAudioJob(){if(owner)return null;const token={};owner=token;emit('nexus-audio-job-state');return ()=>{if(owner===token){owner=null;emit('nexus-audio-job-state')}}}};
 const ui={selection:()=>({...selection}),uiStatus:()=>({busy,archived}),stageChatContext:(...args)=>{staged.push(args);return true}};
 const window={NexusMusicUI:gate,NexusStudioUI:ui,addEventListener(type,fn){this[type]=fn}};
 class Worker{constructor(){workers.push(this)}terminate(){this.terminated=true}}
 const pdf={PDFWorker:class{},getDocument:()=>({promise:loading.promise})};
 const url=class{};
 let serial=0;
 const timer=fn=>{timers.set(++serial,fn);return serial};
 const input=node('studio-pdf-file');
 const transformed=source.replace("import('./pdf.min.mjs')","loadModule()").replaceAll("import.meta.url","'https://fixture.test/pdf/studio-pdf.mjs'");
 new Function('document','window','Worker','URL','setTimeout','clearTimeout','loadModule',transformed)(document,window,Worker,url,timer,id=>timers.delete(id),()=>module.promise);
 function choose(){read=deferred();module=deferred();loading=deferred();input.files=[{name:'fixture.pdf',size:48,arrayBuffer:()=>read.promise}];return input.onchange()}
 const external=gate.acquireAudioJob();ok(input.disabled,'model or audio blocks PDF');
 await choose();ok(workers.length===0&&staged.length===0,'disabled programmatic import rejected');external();ok(!input.disabled,'unblock after external release');
 let job=choose();await flush();ok(gate.audioBusy()&&input.disabled,'PDF read owns lease');
 emit('nexus-studio-private-clear');await flush();ok(gate.audioBusy()&&staged.length===0,'private clear invalidates but retains lease');
 read.resolve(new ArrayBuffer(48));await flush();ok(gate.audioBusy(),'pending module import retains lease');
 module.resolve(pdf);await job;ok(!gate.audioBusy()&&workers.length===0&&staged.length===0,'late read and import cannot start worker or stage');
 job=choose();await flush();read.reject(Error('file-read'));await flush();ok(gate.audioBusy(),'failed read waits for module settlement');
 module.resolve(pdf);await job;ok(!gate.audioBusy()&&staged.length===0,'failed read releases after both settle');
 job=choose();await flush();read.resolve(new ArrayBuffer(48));module.resolve(pdf);await flush();ok(workers.length===1&&gate.audioBusy(),'worker extraction holds lease');
 selection={projectId:'p2',threadId:'t2'};emit('nexus-studio-state');await job;
 ok(workers[0].terminated&&!gate.audioBusy()&&staged.length===0,'switch terminates worker and releases without staging');
 loading.resolve({numPages:1});await flush();ok(staged.length===0,'late worker result ignored');
 job=choose();await flush();read.resolve(new ArrayBuffer(48));module.resolve(pdf);await flush();
 loading.resolve({numPages:1,getPage:async()=>({getTextContent:async()=>({items:[{str:'Synthetic PDF text'}]}),cleanup(){}})});
 await job;ok(staged.length===1&&staged[0][0]==='fixture.pdf'&&staged[0][1].includes('Synthetic PDF text'),'successful reviewed staging');
 ok(workers[1].terminated&&!gate.audioBusy()&&!input.disabled,'success terminates and releases');
 job=choose();await flush();const timeout=[...timers.values()][0];timeout();await flush();ok(gate.audioBusy()&&node('studio-pdf-status').textContent.includes('timed out'),'timeout retains pending read lease');
 read.resolve(new ArrayBuffer(48));module.reject(Error('import failed'));await job;ok(!gate.audioBusy()&&staged.length===1,'timeout cleanup no additional staging');
 return checks;
}
