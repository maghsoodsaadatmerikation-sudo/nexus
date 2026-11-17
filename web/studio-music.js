/* NEXUS Music Lab v1: original deterministic composition and DSP.
 * Entirely local; no AI model, Suno, sampling, network, or recorded instruments.
 * Modes are artistically stylized approximations; not a claim of canonical intonation.
 */
(function(root){'use strict';
const TAU=2*Math.PI,PPQ=480,SAMPLE_RATES=[22050,44100];
const MODES=Object.freeze({
 hijaz:Object.freeze([0,100,400,500,700,800,1000]),
 bayati:Object.freeze([0,150,300,500,700,800,1000]),
 shur:Object.freeze([0,150,300,500,700,850,1000]),
 nahawand:Object.freeze([0,200,300,500,700,800,1100]),
 kurd:Object.freeze([0,100,300,500,700,800,1000])
});
const KEYS=Object.freeze({C:48,'C#':49,D:50,'D#':51,E:52,F:53,'F#':54,G:55,'G#':56,A:57,'A#':58,B:59});
const INSTRUMENTS=Object.freeze({
 piano:Object.freeze({name:'Felt piano',program:0,channels:[0,1],pan:-0.25}),
 santur:Object.freeze({name:'Santur (synth)',program:15,channels:[2,3],pan:0.32}),
 oud:Object.freeze({name:'Oud (synth)',program:24,channels:[4,5],pan:-0.35}),
 ney:Object.freeze({name:'Ney (synth)',program:73,channels:[6,7],pan:0.25}),
 kamancheh:Object.freeze({name:'Kamancheh (synth)',program:40,channels:[8,10],pan:-0.2}),
 cello:Object.freeze({name:'Cello (synth)',program:42,channels:[11,12],pan:0.06}),
 electric_guitar:Object.freeze({name:'Electric guitar (synth)',program:27,channels:[13,14],pan:0.4}),
 daf:Object.freeze({name:'Daf (synth)',program:0,channels:[9],pan:0})
});
const DEFAULT=Object.freeze({title:'Untitled journey',mode:'shur',key:'D',bpm:96,bars:64,
 lead:'kamancheh',story:'longing',solo:'electric_guitar',santurSolo:true,
 guitarSolo:true,daf:true,seed:271828,motifSeed:31415});
const STORIES=Object.freeze({
 longing:Object.freeze([0.12,0.35,0.44,0.53,0.72,0.93,0.27]),
 exile:Object.freeze([0.1,0.22,0.34,0.43,0.7,0.83,0.18]),
 radiance:Object.freeze([0.25,0.46,0.58,0.78,0.84,1,0.48]),
 prayer:Object.freeze([0.11,0.24,0.31,0.45,0.59,0.78,0.22])
});
const FORM=[
 {name:'Threshold',weight:8},{name:'Motif',weight:8},
 {name:'Dialogue',weight:8},{name:'Ascent',weight:12},
 {name:'Instrumental solo',weight:8},{name:'Summit',weight:12},
 {name:'Return',weight:8}
];
function fail(code){throw Error(code)}
function integer(n,min,max){return Number.isSafeInteger(n)&&n>=min&&n<=max}
function validate(value={}){
 if(!value||typeof value!=='object'||Array.isArray(value))fail('invalid-options');
 const v={...DEFAULT,...value};
 if(Object.keys(v).some(k=>!Object.hasOwn(DEFAULT,k)))fail('unknown-option');
 if(typeof v.title!=='string'||!v.title.trim()||v.title.length>90||/[\x00-\x1f]/.test(v.title))fail('invalid-title');
 if(!Object.hasOwn(MODES,v.mode)||!Object.hasOwn(KEYS,v.key)||!Object.hasOwn(STORIES,v.story))fail('invalid-mode-key-story');
 if(!integer(v.bpm,72,140)||![32,48,64,96].includes(v.bars))fail('invalid-tempo-length');
 if(!['santur','oud','ney','kamancheh','electric_guitar'].includes(v.lead)||!['santur','oud','ney','kamancheh','electric_guitar'].includes(v.solo))fail('invalid-lead-solo');
 if(!integer(v.seed,1,2147483646)||!integer(v.motifSeed,1,2147483646))fail('invalid-seed');
 for(const key of ['santurSolo','guitarSolo','daf'])if(typeof v[key]!=='boolean')fail('invalid-arrangement-boolean');
 return Object.freeze(v);
}
function rng(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296}}
function clamp(v,a,b){return Math.min(b,Math.max(a,v))}
function pitch(v,degree,octave=0){
 const n=Math.floor(degree/7),d=((degree%7)+7)%7;
 return KEYS[v.key]+12*(n+octave)+MODES[v.mode][d]/100;
}
function sectionMap(bars,story){
 // Allocate full bars deterministically, preserve distinct solo and final resolution.
 const assigned=FORM.map(f=>Math.floor(bars*f.weight/64));
 let left=bars-assigned.reduce((a,b)=>a+b,0);
 for(const j of [5,3,4,2,1,0,6])if(left-->0)assigned[j]++;
 let at=0;
 return FORM.map((section,i)=>{const start=at;at+=assigned[i];return Object.freeze({
 name:section.name,start,end:at,bars:assigned[i],energy:STORIES[story][i]
 })});
}
function compose(options={}){
 const v=validate(options),random=rng(v.seed),motifRandom=rng(v.motifSeed),sections=sectionMap(v.bars,v.story);
 const beat=60/v.bpm,barSeconds=beat*4,notes=[],phrases=[];
 const motif=[0,2,1,4,3,2,1,0].map((n,i)=>n+((i===3||i===6)&&motifRandom()<0.34?1:0));
 let serial=0;
 function add(inst,bar,bpos,length,degree,octave,vel,role,energy,noteOverride){
  if(inst==='daf'&&!v.daf)return;
  const start=(bar*4+bpos)*beat,nominal=length*beat;
  const duration=Math.min(nominal,(v.bars*4*beat)-start-.02);
  if(duration<=0)return;
  const hzMidi=noteOverride!==undefined?noteOverride:pitch(v,degree,octave);
  notes.push({id:serial++,instrument:inst,start:+start.toFixed(6),
   duration:+duration.toFixed(6),pitch:+hzMidi.toFixed(3),
   velocity:Math.round(clamp(vel*(.75+.25*random()),18,115)),
   pan:INSTRUMENTS[inst].pan,role,energy:+energy.toFixed(3),bar});
 }
 for(let bar=0;bar<v.bars;bar++){
  const section=sections.find(s=>bar>=s.start&&bar<s.end),energy=section.energy;
  const within=bar-section.start,last=bar>=v.bars-4;
  const phrase=Math.floor(bar/2),measure=bar%2;
  const transition=bar===section.start&&bar>0;
  const harmony=[0,5,3,4][Math.floor(bar/4)%4];
  const gap=(within===0&&bar>0)||((bar+1)%16===0&&!last);
  let voice=v.lead;
  if(section.name==='Threshold')voice='ney';
  if(section.name==='Dialogue')voice=bar%4<2?'kamancheh':'oud';
  if(section.name==='Instrumental solo')voice=v.solo;
  if(section.name==='Summit')voice=bar%4<2?'electric_guitar':'santur';
  if(section.name==='Return')voice='ney';
  // Preserve the melody as a recognizable two-bar motif with a varied second half.
  if(!gap){
   for(let i=0;i<4;i++){
    const ix=measure*4+i,base=motif[ix];
    const variation=phrase>3&&(phrase%4===2)&&i===2?1:0;
    const lift=section.name==='Summit'&&i===3?2:0;
    const ornament=section.name==='Instrumental solo'&&i===1&&random()<.6;
    const degree=base+variation+lift,oct=section.name==='Summit'?2:1;
    const place=[0,1,1.75,3][i],dur=[.82,.67,1.13,.85][i];
    add(voice,bar,place,dur,degree,oct,49+energy*40,'motif',energy);
    if(ornament&&place+.45<4)add(voice,bar,place+.48,.24,degree+1,oct,42+energy*25,'ornament',energy);
   }
  }
  phrases.push({bar,section:section.name,lead:voice,motif:!gap,energy});
  // Sparse chord support: low root and fifth, no machine-autonomous harmony "judgment".
  if(bar%2===0) {
   add('piano',bar,0,3.7,harmony,0,32+energy*40,'harmony',energy);
   if(energy>.4)add('piano',bar,0,3.2,harmony+4,0,22+energy*27,'harmony',energy);
  }
  // Anchor drones without filling the rests; cello gives recurring gravity.
  if(bar%2===0&&!gap) add('cello',bar,0,7.4,harmony,-1,38+energy*30,'drone',energy);
  // Santur is a playable pitched instrument, not a synonym for every oriental texture.
  // The "dialogue" role is placed between the lead phrases.
  if(bar%4===2&&energy>.30&&voice!=='santur') {
   add('santur',bar,2.5,.41,harmony+2,2,35+energy*32,'answer',energy);
   add('santur',bar,3.08,.46,harmony+3,2,35+energy*29,'answer',energy);
  }
  // Oud picking supplies rhythmic impetus; solo bars leave the lead exposed.
  if(energy>.38&&section.name!=='Instrumental solo'&&!gap){
   for(const p of [0.5,2.5]) add('oud',bar,p,.42,harmony,1,26+energy*32,'pulse',energy);
  }
  if(v.guitarSolo&&section.name==='Ascent'&&bar%4===3&&!gap){
   add('electric_guitar',bar,2.75,1.12,harmony+4,1,52+energy*32,'solo-foreshadow',energy);
  }
  if(v.santurSolo&&section.name==='Return'&&bar%2===0){
   add('santur',bar,1.25,.8,0,2,30,'final-santur-echo',energy);
  }
  // Daf patterns breathe: almost absent at first, supportive then active at peak.
  if(v.daf&&energy>.39&&!gap){
   add('daf',bar,0,.24,0,0,35+energy*50,'pulse',energy,36);
   if(energy>.65)add('daf',bar,2,.18,0,0,35+energy*44,'backbeat',energy,47);
   if(energy>.8){for(const t of [1.5,3.5])add('daf',bar,t,.15,0,0,30+energy*35,'rim',energy,42);}
  }
  if(transition) { /* intentional one-bar melodic breath */ }
 }
 notes.sort((a,b)=>a.start-b.start||a.id-b.id);
 const score={schema:'nexus.music.score.v1',options:v,
  durationSeconds:+(v.bars*barSeconds).toFixed(3),sections,notes,phrases,
  motif:Object.freeze(motif),engine:'deterministic-local-composition-v1',
  actual_instrument_recordings:false,external_model_or_api:false};
 score.review=review(score);
 return score;
}
function review(score){
 if(score?.schema!=='nexus.music.score.v1')fail('invalid-score');
 const stats={},events=score.notes;
 for(const inst of Object.keys(INSTRUMENTS))stats[inst]=events.filter(n=>n.instrument===inst).length;
 const gaps=score.phrases.filter(p=>!p.motif).map(p=>p.bar);
 const solo=score.sections.find(s=>s.name==='Instrumental solo');
 const soloLead=events.filter(n=>n.role==='motif'&&n.start>=solo.start*4*60/score.options.bpm&&n.start<solo.end*4*60/score.options.bpm);
 const warnings=[];
 if(score.durationSeconds<125)warnings.push('shorter-than-target-story-arc');
 if(!stats.santur)warnings.push('no-santur-voice');
 if(!stats.electric_guitar)warnings.push('no-electric-guitar-voice');
 if(!stats.daf&&score.options.daf)warnings.push('daf-unexpectedly-absent');
 if(!gaps.length)warnings.push('no-intentional-melodic-breath');
 if(!soloLead.length||soloLead.some(n=>n.instrument!==score.options.solo))warnings.push('solo-handoff-not-isolated');
 if(events.length>2500)warnings.push('dense-arrangement');
 return Object.freeze({status:warnings.length?'REVIEW_REQUIRED':'STRUCTURAL_CHECKS_OK',
  objective_only:true,audio_quality_evaluated:false,traditional_authenticity_verified:false,
  duration_seconds:score.durationSeconds,note_count:events.length,
  instruments:stats,motif_breath_bars:gaps,solo_lead:score.options.solo,
  warnings:Object.freeze(warnings)});
}
function writeVLQ(n){if(!integer(n,0,0x0fffffff))fail('invalid-midi-delta');let a=[n&127];while((n>>=7)>0)a.unshift((n&127)|128);return a}
function bytes16(n){return [(n>>>8)&255,n&255]}
function bytes32(n){return [(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255]}
function utf8(s){return [...new TextEncoder().encode(s)]}
function midi(score){
 if(score?.schema!=='nexus.music.score.v1')fail('invalid-score');
 const bpm=score.options.bpm,tracks=[];
 const tempo=Math.round(60000000/bpm),meta=[
   {t:0,pri:0,data:[0xff,0x51,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255]},
   {t:0,pri:0,data:[0xff,0x58,4,4,2,24,8]},
   {t:0,pri:0,data:[0xff,0x03,...writeVLQ(utf8(score.options.title).length),...utf8(score.options.title)]}
 ];
 function track(items){
  items.sort((a,b)=>a.t-b.t||a.pri-b.pri);
  const out=[];let previous=0;
  for(const e of items){const delta=e.t-previous;out.push(...writeVLQ(delta),...e.data);previous=e.t}
  out.push(0,0xff,0x2f,0);
  tracks.push([0x4d,0x54,0x72,0x6b,...bytes32(out.length),...out]);
 }
 track(meta);
 for(const [key,spec] of Object.entries(INSTRUMENTS)){
  const part=score.notes.filter(n=>n.instrument===key);
  if(!part.length)continue;
  const data=[];
  const channels=key==='daf'?[9]:spec.channels;
  for(const channel of channels){
   if(key!=='daf')data.push({t:0,pri:0,data:[0xc0|channel,spec.program]});
   if(key!=='daf') {
    // Default pitch bend range +/- 2 semitones; +0.5 semitone = 10240.
    const v=channel===channels[1]?10240:8192;
    data.push({t:0,pri:1,data:[0xe0|channel,v&127,v>>7]});
   }
  }
  for(const note of part){
   const base=Math.floor(note.pitch+.0001),frac=note.pitch-base;
   if(key!=='daf'&&Math.abs(frac)>.001&&Math.abs(frac-.5)>.001)fail('unsupported-midi-tuning');
   const ch=key==='daf'?9:channels[frac>.25?1:0];
   const tick=Math.round(note.start*bpm*PPQ/60);
   const end=Math.max(tick+1,Math.round((note.start+note.duration)*bpm*PPQ/60));
   data.push({t:tick,pri:2,data:[0x90|ch,clamp(base,0,127),note.velocity]});
   data.push({t:end,pri:1,data:[0x80|ch,clamp(base,0,127),0]});
  }
  track(data);
 }
 const out=[0x4d,0x54,0x68,0x64,...bytes32(6),0,1,...bytes16(tracks.length),...bytes16(PPQ)];
 for(const tr of tracks)out.push(...tr);
 return new Uint8Array(out);
}
// Approximate synthetic timbre, not sampled oud/santur/ney/kamancheh.
const PARTIALS={
 piano:[1,.42,.19,.09],santur:[1,.75,.48,.22,.12],
 oud:[1,.38,.16,.08],ney:[1,.09,.025],
 kamancheh:[1,.53,.31,.17,.09],cello:[1,.5,.28,.12],
 electric_guitar:[1,.45,.20,.10]
};
function synthWave(note,phase,t,seconds){
 const inst=note.instrument;
 if(inst==='daf'){
  const p=note.pitch;let noise=Math.sin((t+note.id*.01)*15413.9)*43758.5453;
  noise=2*(noise-Math.floor(noise))-1;
  const decay=Math.exp(-t*(p===36?15:28));
  const low=Math.sin(TAU*(p===36?72:185)*t)*Math.exp(-t*16);
  return (p===36?low*.9+noise*.14:noise*.5+low*.25)*decay;
 }
 const attack=inst==='kamancheh'||inst==='cello'?0.095:inst==='ney'?0.065:0.005;
 const release=inst==='kamancheh'||inst==='cello'?0.25:0.13;
 const envelope=Math.min(1,t/attack)*Math.min(1,Math.max(0,(seconds-t)/release));
 const decay=inst==='santur'?Math.exp(-t*2.5):inst==='oud'?Math.exp(-t*1.55):
             inst==='piano'?Math.exp(-t*.55):inst==='electric_guitar'?Math.exp(-t*.22):1;
 const vibrato=['kamancheh','cello','ney'].includes(inst)?(1+0.003*Math.sin(TAU*5.2*t)):1;
 const coefficients=PARTIALS[inst];
 let value=0,div=0;
 for(let i=0;i<coefficients.length;i++){value+=coefficients[i]*Math.sin(phase*vibrato*(i+1));div+=coefficients[i]}
 value/=div;
 if(inst==='santur')value+=.14*Math.sin(phase*2.004)*Math.exp(-t*3);
 if(inst==='ney')value+=.036*Math.sin(phase*13.07)*Math.exp(-t*.9);
 if(inst==='electric_guitar')value=Math.tanh(value*2.2)*.77;
 return value*envelope*decay;
}
function delayTick(){return new Promise(resolve=>setTimeout(resolve,0))}
async function renderWav(score,{sampleRate=22050,sound='expressive',onProgress=()=>{},shouldAbort=()=>false}={}){
 if(score?.schema!=='nexus.music.score.v1'||!SAMPLE_RATES.includes(sampleRate))fail('invalid-render-request');
 if(score.durationSeconds>350)fail('duration-over-budget');
 if(!['expressive','classic'].includes(sound))fail('unknown-sound-profile');
 if(sound==='expressive'&&!root.NexusMusicAudio)fail('missing-expressive-audio-engine');
 if(!Array.isArray(score.notes)||score.notes.length>5000)fail('invalid-render-note-list');
 for(const n of score.notes){if(!Object.hasOwn(INSTRUMENTS,n.instrument)||
  !Number.isFinite(n.start)||!Number.isFinite(n.duration)||
  !Number.isFinite(n.pitch)||!Number.isFinite(n.pan)||
  !Number.isFinite(n.velocity)||n.start<0||n.duration<=0||n.pitch<20||n.pitch>115||
  n.velocity<1||n.velocity>127||Math.abs(n.pan)>1||
  n.start+n.duration>score.durationSeconds+.002)fail('invalid-render-note');}
 const frames=Math.ceil((score.durationSeconds+.8)*sampleRate);
 // Two float32 buffers plus PCM WAV; reject expensive combinations before
 // allocating or running DSP. Long, low-rate exports remain available.
 if(frames*12>128*1024*1024)fail('mobile-render-memory-budget');
 const left=new Float32Array(frames),right=new Float32Array(frames);
 const notes=score.notes;
 for(let n=0;n<notes.length;n++){
  if(shouldAbort())fail('render-cancelled');
  const note=notes[n],start=Math.max(0,Math.floor(note.start*sampleRate));
  const total=Math.max(0,Math.min(frames-start,Math.ceil((note.duration+.14)*sampleRate)));
  const freq=440*Math.pow(2,(note.pitch-69)/12),increment=TAU*freq/sampleRate;
  // Saturate total gain gently; an occasional solo note must stay audible.
  const amp=(note.velocity/127)*(note.instrument==='daf'?.22:.17);
  const lg=Math.sqrt((1-note.pan)*.5)*amp,rg=Math.sqrt((1+note.pan)*.5)*amp;
  let phase=0;
  for(let i=0;i<total;i++){
   const t=i/sampleRate;
   const v=sound==='expressive'
    ?root.NexusMusicAudio.sample(note,phase,t,note.duration,freq,i,sampleRate)
    :synthWave(note,phase,t,note.duration);
   const index=start+i;
   left[index]+=v*lg;right[index]+=v*rg;
   phase+=increment;if(phase>TAU*5000)phase%=TAU;
  }
  if(n%16===0){onProgress(n/notes.length);await delayTick()}
 }
 // Quiet single-tap echoes after mixing; gentle tail gives space, not an
 // arbitrary algorithmic "authentic" eastern room response.
 const tap=Math.round(sampleRate*.217);
 for(let i=tap;i<frames;i++){
  left[i]+=right[i-tap]*.055;
  right[i]+=left[i-tap]*.055;
  if(i%262144===0){if(shouldAbort())fail('render-cancelled');await delayTick()}
 }
 let peak=0;
 for(let i=0;i<frames;i++)peak=Math.max(peak,Math.abs(left[i]),Math.abs(right[i]));
 const gain=peak>.9?.9/peak:1;
 const buf=new ArrayBuffer(44+frames*4),view=new DataView(buf);
 function str(offset,text){for(let i=0;i<text.length;i++)view.setUint8(offset+i,text.charCodeAt(i))}
 str(0,'RIFF');view.setUint32(4,36+frames*4,true);str(8,'WAVE');
 str(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);
 view.setUint16(22,2,true);view.setUint32(24,sampleRate,true);
 view.setUint32(28,sampleRate*4,true);view.setUint16(32,4,true);view.setUint16(34,16,true);
 str(36,'data');view.setUint32(40,frames*4,true);
 for(let i=0;i<frames;i++){
  if(shouldAbort())fail('render-cancelled');
  const fade=Math.min(1,i/(sampleRate*.25),(frames-i)/(sampleRate*.8));
  const l=clamp(left[i]*gain*fade,-1,1),r=clamp(right[i]*gain*fade,-1,1);
  view.setInt16(44+i*4,Math.round(l*32767),true);
  view.setInt16(46+i*4,Math.round(r*32767),true);
  if(i%262144===0){onProgress(.84+.16*i/frames);await delayTick()}
 }
 onProgress(1);
 return new Uint8Array(buf);
}
root.NexusMusic=Object.freeze({MODES,INSTRUMENTS,DEFAULT,validate,compose,review,midi,renderWav,
 analyzeWav:(...args)=>{if(!root.NexusMusicAudio)fail('missing-expressive-audio-engine');return root.NexusMusicAudio.analyzeWav(...args)},
 sounds:Object.freeze(['expressive','classic']),source_tree:'none'});
})(typeof globalThis!=='undefined'?globalThis:this);
