// Exact Studio UI handlers, synthetic DOM and delayed audio engines.
import {readFileSync} from 'node:fs';
export async function testAudioJobGate(musicSource,orchestraSource){
 const checks=[],ok=(x,label)=>{if(!x)throw Error(label);checks.push(label)};
 const nodes=new Map(),listeners=new Map(),jobs=[];
 const node=id=>{if(!nodes.has(id))nodes.set(id,{id,value:'',checked:false,disabled:false,textContent:'',type:'text',files:[],
  handlers:new Map(),addEventListener(type,fn){this.handlers.set(type,fn)},querySelectorAll:()=>[],pause(){},load(){},removeAttribute(){}});return nodes.get(id)};
 const document={documentElement:{lang:'en'},getElementById:node,addEventListener(type,fn){if(!listeners.has(type))listeners.set(type,[]);listeners.get(type).push(fn)},dispatchEvent(e){for(const fn of listeners.get(e.type)||[])fn(e)}};
 const Event=class{constructor(type){this.type=type}};
 const pending=(kind,opts)=>new Promise((resolve,reject)=>jobs.push({kind,opts,resolve,reject}));
 const root={addEventListener(){},NexusMusic:{DEFAULT:{},compose:()=>({sections:[],durationSeconds:1,motif:[],review:{instruments:{},motif_breath_bars:[],warnings:[]}}),renderWav:(s,o)=>pending('music',o)},
 NexusOrchestra:{parsePrompt:()=>({ready:true,spec:{instruments:[]},understood:[],unparsed:[],warnings:[]}),compose:()=>({notes:[],parts:[],durationSeconds:1}),render:(s,o)=>pending('orchestra',o)}};
 for(const text of [musicSource,orchestraSource])new Function('globalThis','window','document','Event',text)(root,root,document,Event);
 const click=id=>node(id).handlers.get('click')();
 click('music-build');click('orchestra-parse');click('orchestra-compose');
 const gate=root.NexusMusicUI;
 ok(!gate.audioBusy(),'idle');
 const first=click('music-render');
 ok(jobs.length===1&&jobs[0].kind==='music'&&gate.audioBusy(),'music acquired');
 ok(node('orchestra-render').disabled,'orchestra disabled');
 await click('orchestra-render');ok(jobs.length===1,'cross-tool programmatic start refused');
 click('music-cancel');ok(jobs[0].opts.shouldAbort()&&gate.audioBusy(),'cancel retains lease until unwind');
 await click('music-render');await click('orchestra-render');ok(jobs.length===1,'no restart while unwinding');
 jobs[0].reject(Error('render-cancelled'));await first;
 ok(!gate.audioBusy()&&!node('orchestra-render').disabled,'release after unwind');
 const second=click('orchestra-render');ok(jobs.length===2&&jobs[1].kind==='orchestra','orchestra acquired');
 await click('music-render');ok(jobs.length===2&&node('music-render').disabled,'music blocked');
 root.NexusOrchestraUI.clear();ok(gate.audioBusy()&&jobs[1].opts.shouldAbort(),'private clear invalidates not releases');
 jobs[1].reject(Error('render-cancelled'));await second;ok(!gate.audioBusy(),'clear unwinds safely');
 const release=gate.acquireAudioJob();ok(typeof release==='function'&&gate.acquireAudioJob()===null,'exclusive token');
 release();const next=gate.acquireAudioJob();release();ok(gate.audioBusy(),'stale release cannot unlock newer job');next();ok(!gate.audioBusy(),'final release');
 return checks;
}
if(typeof process!=='undefined'){
 const checks=await testAudioJobGate(readFileSync(new URL('../web/studio-music-ui.js',import.meta.url),'utf8'),readFileSync(new URL('../web/studio-orchestra-ui.js',import.meta.url),'utf8'));
 console.log('AUDIO JOB GATE: PASS ('+checks.length+' checks)');
}
