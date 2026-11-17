import assert from 'node:assert/strict';
import '../web/studio-music-audio.js';
import '../web/studio-music.js';
const M=globalThis.NexusMusic, A=globalThis.NexusMusicAudio;
let checks=0;
function ok(fn){fn();checks++}
const note=(instrument,id=1,pitch=69)=>({
 id,instrument,pitch,start:0.10,duration:0.65,velocity:86,pan:0,role:'solo',energy:.65,bar:0
});
function score(inst,pitch){
 return {schema:'nexus.music.score.v1',options:M.DEFAULT,durationSeconds:1.15,
  notes:[note(inst,2,pitch)],sections:[],phrases:[],motif:[]};
}
ok(()=>assert.equal(A.profile,'expressive-procedural-v2'));
ok(()=>assert.deepEqual(M.sounds,['expressive','classic']));
ok(()=>assert.equal(A.external_api,false));
ok(()=>assert.equal(A.acoustic_recordings,false));
const instrumentPitches={piano:60,santur:78,oud:64,ney:74,kamancheh:68,
 cello:50,electric_guitar:70,daf:36};
const signatures=new Set();
for(const [instrument,pitch] of Object.entries(instrumentPitches)){
 const n=note(instrument,87,pitch),f=440*2**((pitch-69)/12);
 const samples=[0.006,.020,.045,.12,.21,.42].map(t=>
  A.sample(n,Math.PI*2*f*t,t,.7,f,Math.floor(t*22050),22050));
 ok(()=>assert(samples.every(Number.isFinite)));
 ok(()=>assert(samples.some(x=>Math.abs(x)>.00001)));
 ok(()=>assert.deepEqual(samples,
   [0.006,.020,.045,.12,.21,.42].map(t=>
    A.sample(n,Math.PI*2*f*t,t,.7,f,Math.floor(t*22050),22050))));
 const expressive=await M.renderWav(score(instrument,pitch),{sampleRate:22050,sound:'expressive'});
 const classic=await M.renderWav(score(instrument,pitch),{sampleRate:22050,sound:'classic'});
 ok(()=>assert.notDeepEqual(expressive,classic));
 const report=M.analyzeWav(expressive);
 ok(()=>assert(report.measured_peak_dbfs!==null&&report.measured_rms_dbfs!==null));
 ok(()=>assert.equal(report.clipped_frame_count,0));
 ok(()=>assert.equal(report.subjective_listening_performed,false));
 ok(()=>assert.equal(report.acoustic_authenticity_verified,false));
 ok(()=>assert.equal(report.mastering_certified,false));
 signatures.add(expressive.subarray(100,1200).reduce((sum,b,i)=>(sum+((i+3)*b))>>>0,0));
}
ok(()=>assert(signatures.size>=5));
const original=M.compose(M.DEFAULT);
ok(()=>assert.equal(original.sections.length,7));
ok(()=>assert.equal(original.review.audio_quality_evaluated,false));
const short={...original,durationSeconds:2.0,
 notes:original.notes.filter(n=>n.start<1.65)
  .map(n=>({...n,duration:Math.min(n.duration,1.65-n.start)}))
  .filter(n=>n.duration>.015)};
const wav=await M.renderWav(short,{sampleRate:22050,sound:'expressive'});
const report=M.analyzeWav(wav,original);
ok(()=>assert.equal(report.schema,'nexus.music.audio-diagnostics.v1'));
ok(()=>assert.equal(report.sample_rate,22050));
ok(()=>assert(report.measured_peak_dbfs<0));
ok(()=>assert(report.measured_rms_dbfs<=report.measured_peak_dbfs));
ok(()=>assert(report.measured_crest_db>=0));
ok(()=>assert(report.near_silent_fraction>=0&&report.near_silent_fraction<=1));
ok(()=>assert.equal(report.clipped_frame_count,0));
ok(()=>assert(report.section_rms_dbfs.length===7));
ok(()=>assert(report.section_rms_dbfs.some(s=>s.reviewed_against_real_audio)));
ok(()=>assert.equal(report.objective_only,true));
ok(()=>assert.equal(report.subjective_listening_performed,false));
const repeated=await M.renderWav(short,{sampleRate:22050,sound:'expressive'});
ok(()=>assert.deepEqual(wav,repeated));
for(const edit of [
  b=>b[0]=0, b=>b[8]=0, b=>b[22]=0, b=>b[24]=0,
  b=>b[40]=0, b=>b[4]=0
]){
 const mutated=wav.slice();edit(mutated);
 ok(()=>assert.throws(()=>M.analyzeWav(mutated)));
}
for(const bad of [
 {...short,durationSeconds:351},
 {...short,notes:[{...note('ney'),velocity:NaN}]},
 {...short,notes:[{...note('kamancheh'),duration:Infinity}]},
 {...short,notes:[{...note('kamancheh'),pitch:300}]},
 {...short,notes:[{...note('fake')}]}
]){await assert.rejects(M.renderWav(bad,{sound:'expressive'}));checks++}
await assert.rejects(M.renderWav(short,{sound:'external-provider'}));checks++;
const extended=M.compose({...M.DEFAULT,bars:96,bpm:72});
ok(()=>assert.equal(extended.sections.at(-1).end,96));
ok(()=>assert.equal(extended.durationSeconds,320));
ok(()=>assert(extended.notes.length>original.notes.length));
await assert.rejects(M.renderWav(extended,{sampleRate:44100,sound:'expressive'}),
 err=>err.message==='mobile-render-memory-budget');checks++;
await assert.rejects(M.renderWav(short,{sampleRate:22050,sound:'expressive',shouldAbort:()=>true}));checks++;
console.log(JSON.stringify({status:'PASS',checks,sample_models:Object.keys(instrumentPitches).length,
 pcm_analysis:true,eastern_instrument_recordings:false,
 actual_human_listening:false,cloud_calls:0,extended_duration_minutes:extended.durationSeconds/60}));
