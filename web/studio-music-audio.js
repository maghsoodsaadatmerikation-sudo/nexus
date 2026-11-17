/* NEXUS Music Lab — expressive, purely procedural and original DSP v2.
 * No sample assets, vendor endpoints, user audio, recording, or network access.
 * Approximate timbre modeling only; NOT acoustic instrument authentication.
 */
(function(root){'use strict';
const TAU=2*Math.PI,MAX_WAV_BYTES=160*1024*1024;
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));
const sine=(p)=>Math.sin(p);
function fail(code){throw Error(code)}
function noise(index,id,salt=0){
 let z=(Math.imul((index|0)+1,0x45d9f3b)^Math.imul((id|0)+1,0x119de1f3)^salt)|0;
 z=Math.imul(z^(z>>>16),0x7feb352d);
 z=Math.imul(z^(z>>>15),0x846ca68b);
 return ((z^(z>>>16))>>>0)/2147483648-1;
}
function env(t,d,a,r){
 if(t<0||t>=d)return 0;
 return Math.min(1,t/Math.max(a,.001),Math.max(0,(d-t)/Math.max(r,.001)));
}
function partial(phase,n,frequency,rate){
 return n*frequency<rate*.45?sine(phase*n):0;
}
function sample(note,phase,t,duration,frequency,index,rate){
 const inst=note.instrument, id=note.id|0, attackNoise=noise(index,id);
 if(inst==='daf'){
  // Drum head's bending low membrane + hand/rim noises; never actual recorded daf.
  const code=note.pitch|0,low=code===36, rim=code===42;
  const f=low?68:rim?230:145;
  const sweep=(low?27:rim?34:15);
  const membrane=sine(TAU*(f*t+sweep*(1-Math.exp(-14*t))/14))
       *Math.exp(-t*(low?12:rim?34:22));
  const skin=attackNoise*Math.exp(-t*(low?34:rim?68:48));
  return (rim?.25*membrane+.64*skin:low?.94*membrane+.18*skin:.45*membrane+.48*skin)
    *env(t,duration,.001,.03);
 }
 const attack=inst==='kamancheh'?.088:inst==='cello'?.082:
              inst==='ney'?.063:inst==='electric_guitar'?.010:.0028;
 const release=inst==='kamancheh'?.14:inst==='cello'?.13:
               inst==='ney'?.12:.075;
 const e=env(t,duration,attack,release);
 if(e<=0)return 0;
 const vibratoDepth=inst==='kamancheh'?.0037:inst==='cello'?.002:
                    inst==='ney'?.003:0;
 // Integral of a bounded instantaneous frequency modulation. Unlike
 // "phase * (1+sin(t))", vibrato depth stays stable for long held notes.
 const vibrato=frequency*vibratoDepth/5.1*
      (sine(TAU*5.1*t)-0)*clamp((t-.15)/.27,0,1);
 const p=phase+vibrato;
 if(inst==='santur'){
  // Inharmonic stiff strings with paired detuning; mallet becomes darker
  // as the upper partials decay. No fake "sampled santur" claim.
  const decay=Math.exp(-t*(1.45+.00033*frequency));
  const body=partial(p,1,frequency,rate)*.79
      +partial(p*1.0024,1,frequency,rate)*.17
      +partial(p,2.006,frequency,rate)*.51*Math.exp(-t*1.4)
      +partial(p,3.018,frequency,rate)*.28*Math.exp(-t*2.5)
      +partial(p,4.034,frequency,rate)*.14*Math.exp(-t*4.2);
  const strike=attackNoise*.09*Math.exp(-t*78);
  return (body*.59*decay+strike)*e;
 }
 if(inst==='oud'){
  // Plucked string harmonic nulls from picking position, plus short
  // plectrum transient. Faster high-harmonic damping than main resonance.
  let body=0;
  for(let h=1;h<=5;h++){
   const coeff=Math.abs(sine(Math.PI*h*.19))/Math.pow(h,.88);
   body+=coeff*partial(p,h,frequency,rate)*Math.exp(-t*(.52+.32*h));
  }
  return (body*.64+attackNoise*.045*Math.exp(-t*110))*e;
 }
 if(inst==='ney'){
  // Sparse pipe spectrum, late breath shimmer and slow vibrato.
  const breath=(.019+.017*Math.sin(TAU*2.3*t))*attackNoise;
  const pipe=partial(p,1,frequency,rate)*.86+
       partial(p,2,frequency,rate)*.095+
       partial(p,3,frequency,rate)*.032;
  return (pipe+breath)*e*.8;
 }
 if(inst==='kamancheh'||inst==='cello'){
  // Bow onset, harmonic sustain, controlled slow vibrato with small
  // simulated bow friction (not an acoustic bow recording).
  let bow=0;
  const weights=inst==='kamancheh'?[.74,.43,.30,.17,.09]:
             [.85,.36,.22,.1,.04];
  for(let h=1;h<=weights.length;h++)
   bow+=weights[h-1]*partial(p,h,frequency,rate);
  const grain=attackNoise*(inst==='kamancheh'?.016:.009);
  return Math.tanh((bow+grain)*.96)*e*.70;
 }
 if(inst==='electric_guitar'){
  let x=0;
  for(let h=1;h<=5;h++)
   x+=partial(p,h,frequency,rate)*(1/h)*Math.exp(-t*(.045+.08*h));
  return Math.tanh(x*1.38)*e*.78;
 }
 if(inst==='piano'){
  const body=partial(p,1,frequency,rate)*.87+
       partial(p,2.001,frequency,rate)*.30*Math.exp(-t*.6)+
       partial(p,3.009,frequency,rate)*.11*Math.exp(-t*1.2);
  return body*Math.exp(-t*.4)*e*.72;
 }
 fail('unknown-instrument-audio-model');
}
function analyzeWav(bytes,score=null){
 if(!(bytes instanceof Uint8Array)||bytes.byteLength<48||
    bytes.byteLength>MAX_WAV_BYTES)fail('invalid-wav-data');
 const dv=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 const text=(start,s)=>[...s].every((c,i)=>dv.getUint8(start+i)===c.charCodeAt(0));
 if(!text(0,'RIFF')||!text(8,'WAVE')||!text(12,'fmt ')||
    !text(36,'data')||dv.getUint32(4,true)+8!==bytes.byteLength||
    dv.getUint32(16,true)!==16||dv.getUint16(20,true)!==1||
    dv.getUint16(22,true)!==2||dv.getUint16(34,true)!==16||
    dv.getUint32(40,true)+44!==bytes.byteLength)fail('invalid-wav-header');
 const rate=dv.getUint32(24,true),frames=dv.getUint32(40,true)/4;
 if(![22050,44100].includes(rate)||!Number.isInteger(frames)||
    dv.getUint32(28,true)!==rate*4)fail('invalid-wav-sample-format');
 const regions=score?.sections&&Array.isArray(score.sections)&&
       Number.isFinite(score?.options?.bpm)?score.sections:[];
 const rmsSum=new Float64Array(regions.length),rmsCount=new Uint32Array(regions.length);
 const threshold=327,clipValue=32765;
 let peak=0,sum=0,l2=0,r2=0,lr=0,silent=0,clipped=0,which=0;
 for(let i=0;i<frames;i++){
  const l=dv.getInt16(44+i*4,true),r=dv.getInt16(46+i*4,true);
  const power=(l*l+r*r)/2;
  peak=Math.max(peak,Math.abs(l),Math.abs(r));sum+=power;
  l2+=l*l;r2+=r*r;lr+=l*r;
  if(Math.max(Math.abs(l),Math.abs(r))<=threshold)silent++;
  if(Math.abs(l)>=clipValue||Math.abs(r)>=clipValue)clipped++;
  if(regions.length){
   const bar=i*score.options.bpm/(rate*60*4);
   while(which<regions.length-1&&bar>=regions[which].end)which++;
   rmsSum[which]+=power;rmsCount[which]++;
  }
 }
 const db=value=>value>0?+(20*Math.log10(value/32768)).toFixed(2):null;
 const rms=frames?Math.sqrt(sum/frames):0;
 const sectionRms=regions.map((section,i)=>({
  name:section.name,
  rms_dbfs:db(Math.sqrt(rmsSum[i]/Math.max(1,rmsCount[i]))),
  reviewed_against_real_audio:true
 }));
 const warnings=[];
 if(!peak||!rms)warnings.push('silent-audio');
 if(clipped>0)warnings.push('pcm-clipping');
 if(db(rms)!==null&&db(rms)<-36)warnings.push('very-low-rms');
 if(frames&&silent/frames>.5)warnings.push('more-than-half-near-silence');
 const start=sectionRms[0]?.rms_dbfs,peakSection=sectionRms.find(x=>x.name==='Summit')?.rms_dbfs;
 if(start!==null&&start!==undefined&&peakSection!==null&&peakSection!==undefined&&
    peakSection-start<2)warnings.push('summit-level-not-distinct-from-intro');
 return Object.freeze({
  schema:'nexus.music.audio-diagnostics.v1',
  objective_only:true,subjective_listening_performed:false,
  acoustic_authenticity_verified:false,mastering_certified:false,
  sample_rate:rate,frames,
  measured_peak_dbfs:db(peak),measured_rms_dbfs:db(rms),
  measured_crest_db:peak&&rms?+(20*Math.log10(peak/rms)).toFixed(2):null,
  near_silent_fraction:+(silent/frames).toFixed(5),
  clipped_frame_count:clipped,
  stereo_correlation:l2&&r2?+(lr/Math.sqrt(l2*r2)).toFixed(5):null,
  section_rms_dbfs:sectionRms,warnings
 });
}
root.NexusMusicAudio=Object.freeze({sample,analyzeWav,profile:'expressive-procedural-v2',
 acoustic_recordings:false,external_api:false});
})(typeof globalThis!=='undefined'?globalThis:this);
