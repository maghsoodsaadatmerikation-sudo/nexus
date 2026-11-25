// Exact Studio UI handlers, synthetic DOM and delayed audio engines.
import {readFileSync} from 'node:fs';
export async function testAudioJobGate(musicSource,orchestraSource){
 const checks=[],ok=(x,label)=>{if(!x)throw Error(label);checks.push(label)};
 const nodes=new Map(),listeners=new Map(),jobs=[],reads=[];
 const node=id=>{if(!nodes.has(id))nodes.set(id,{id,value:'',checked:false,disabled:false,textContent:'',type:'text',files:[],
  handlers:new Map(),addEventListener(type,fn){this.handlers.set(type,fn)},querySelectorAll:()=>[],pause(){},load(){},removeAttribute(){}});return nodes.get(id)};
 const document={documentElement:{lang:'en'},getElementById:node,addEventListener(type,fn){if(!listeners.has(type))listeners.set(type,[]);listeners.get(type).push(fn)},dispatchEvent(e){for(const fn of listeners.get(e.type)||[])fn(e)}};
 const Event=class{constructor(type){this.type=type}};
 const pending=(kind,opts)=>new Promise((resolve,reject)=>jobs.push({kind,opts,resolve,reject}));
 const root={addEventListener(){},NexusMusic:{DEFAULT:{},compose:()=>({sections:[],durationSeconds:1,motif:[],review:{instruments:{},motif_breath_bars:[],warnings:[]}}),renderWav:(s,o)=>pending('music',o)},
 NexusOrchestra:{parsePrompt:()=>({ready:true,spec:{instruments:[]},understood:[],unparsed:[],warnings:[]}),compose:()=>({notes:[],parts:[],durationSeconds:1}),render:(s,o)=>pending('orchestra',o),inspectDryWav:()=>({sampleRate:22050,channels:1,durationSeconds:1})},NexusVocalMix:{mix:(dry,backing,o)=>pending('mix',o)}};
 const crypto={subtle:{digest:async()=>new Uint8Array(32).buffer}};root.crypto=crypto;
 const URL={createObjectURL:()=>'blob:synthetic',revokeObjectURL(){}};
 const Blob=class{};
 for(const text of [musicSource,orchestraSource])new Function('globalThis','window','document','Event','crypto','URL','Blob',text)(root,root,document,Event,crypto,URL,Blob);
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
 // Drive the actual import and mix handlers rather than only the gate API.
 click('orchestra-parse');click('orchestra-compose');
 const third=click('orchestra-render');
 const wav=new Uint8Array(48);new DataView(wav.buffer).setUint32(24,22050,true);
 jobs[2].resolve(wav);await third;
 ok(root.NexusOrchestraUI.hasWav()&&!gate.audioBusy(),'backing ready');
 const file=node('orchestra-dry-file');
 file.files=[{size:wav.length,arrayBuffer:()=>new Promise((resolve,reject)=>reads.push({resolve,reject}))}];
 const choose=()=>file.handlers.get('change')();
 const read=choose();ok(reads.length===1&&gate.audioBusy(),'vocal read owns lease');
 ok(file.disabled&&node('music-render').disabled,'other operations disabled during file read');
 await click('music-render');await click('orchestra-render');await choose();
 ok(jobs.length===3&&reads.length===1,'overlapping work refused during file read');
 click('orchestra-dry-clear');ok(gate.audioBusy()&&!root.NexusOrchestraUI.hasOriginalVocal(),'cleared read retains lease');
 reads[0].resolve(wav.buffer);await read;
 ok(!gate.audioBusy()&&!root.NexusOrchestraUI.hasOriginalVocal(),'late read cannot restore original');
 const reread=choose();reads[1].resolve(wav.buffer);await reread;
 ok(root.NexusOrchestraUI.hasOriginalVocal()&&!gate.audioBusy(),'reimport succeeds');
 const mix=click('orchestra-mix');
 ok(jobs.length===4&&jobs[3].kind==='mix'&&gate.audioBusy(),'mix owns lease');
 await click('music-render');await click('orchestra-render');await choose();
 ok(jobs.length===4&&reads.length===2,'mix excludes render and import');
 click('orchestra-cancel');ok(jobs[3].opts.shouldAbort()&&gate.audioBusy(),'mix cancellation retains lease');
 jobs[3].reject(Error('mix-cancelled'));await mix;
 ok(!gate.audioBusy()&&root.NexusOrchestraUI.hasOriginalVocal()&&!root.NexusOrchestraUI.hasMixedWav(),'mix cancel preserves original and releases');
 const badRead=choose();reads[2].reject(Error('synthetic file error'));await badRead;
 ok(!gate.audioBusy()&&!root.NexusOrchestraUI.hasOriginalVocal(),'rejected read releases lease');
 const release=gate.acquireAudioJob();ok(typeof release==='function'&&gate.acquireAudioJob()===null,'exclusive token');
 release();const next=gate.acquireAudioJob();release();ok(gate.audioBusy(),'stale release cannot unlock newer job');next();ok(!gate.audioBusy(),'final release');
 return checks;
}
if(typeof process!=='undefined'){
 const checks=await testAudioJobGate(readFileSync(new URL('../web/studio-music-ui.js',import.meta.url),'utf8'),readFileSync(new URL('../web/studio-orchestra-ui.js',import.meta.url),'utf8'));
 console.log('AUDIO JOB GATE: PASS ('+checks.length+' checks)');
}
