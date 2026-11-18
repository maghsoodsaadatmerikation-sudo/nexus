/* NEXUS Original Vocal Mix v1 — offline, explicit, non-destructive.
 * A mixed WAV necessarily differs from the original dry recording.
 * The raw user-supplied recording stays byte-for-byte intact and separate.
 * No network, source recording edit, voice conversion or audio libraries.
 */
(function(root){'use strict';
const MAX_SOURCE_BYTES=84*1024*1024,MAX_DRY_BYTES=20*1024*1024,MAX_MIX_BYTES=64*1024*1024;
function fail(s){throw Error(s)}
function bounded(value,min,max){return Number.isFinite(value)&&value>=min&&value<=max}
function inspect(bytes,maxBytes){
 if(!(bytes instanceof Uint8Array)||bytes.byteLength<48||bytes.byteLength>maxBytes)fail('invalid-raw-wave-size');
 const d=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 const match=(at,tag)=>[...tag].every((c,i)=>d.getUint8(at+i)===c.charCodeAt(0));
 if(!match(0,'RIFF')||!match(8,'WAVE')||!match(12,'fmt ')||!match(36,'data')||
    d.getUint32(4,true)+8!==bytes.byteLength||d.getUint32(16,true)!==16||
    d.getUint16(20,true)!==1||d.getUint16(34,true)!==16||
    d.getUint32(40,true)+44!==bytes.byteLength)fail('unsupported-wave-layout');
 const channels=d.getUint16(22,true),rate=d.getUint32(24,true),
       payload=d.getUint32(40,true),align=d.getUint16(32,true);
 if(![1,2].includes(channels)||![22050,44100].includes(rate)||
    align!==2*channels||d.getUint32(28,true)!==rate*align||
    payload===0||payload%align!==0)fail('unsupported-wave-format');
 const frames=payload/align;
 return Object.freeze({channels,sampleRate:rate,frames,durationSeconds:frames/rate,view:d});
}
function parse(dry,backing){
 const a=inspect(dry,MAX_DRY_BYTES),b=inspect(backing,MAX_SOURCE_BYTES);
 if(a.sampleRate!==b.sampleRate)fail('sample-rate-mismatch-re-render-backing');
 return {dry:a,backing:b};
}
function formatWavHeader(view,frames,rate){
 function put(offset,tag){for(let i=0;i<tag.length;i++)view.setUint8(offset+i,tag.charCodeAt(i))}
 put(0,'RIFF');view.setUint32(4,36+frames*4,true);
 put(8,'WAVE');put(12,'fmt ');view.setUint32(16,16,true);
 view.setUint16(20,1,true);view.setUint16(22,2,true);
 view.setUint32(24,rate,true);view.setUint32(28,rate*4,true);
 view.setUint16(32,4,true);view.setUint16(34,16,true);
 put(36,'data');view.setUint32(40,frames*4,true);
}
function numberSample(source,index,channel){
 if(index<0||index>=source.frames)return 0;
 const v=source.view;
 // Mono input is positioned into the stereo mix equally, not resampled.
 return v.getInt16(44+(index*source.channels+Math.min(channel,source.channels-1))*2,true);
}
function plan(original,backing,{offsetMs=0,dryGain=1,backingGain=.35}={}){
 const parsed=parse(original,backing);
 if(!Number.isSafeInteger(offsetMs)||offsetMs < -3000||offsetMs >3000)fail('invalid-alignment');
 if(!bounded(dryGain,0,1)||!bounded(backingGain,0,1)||
    (dryGain===0&&backingGain===0))fail('invalid-gain-settings');
 const frameOffset=Math.round(Math.abs(offsetMs)*parsed.dry.sampleRate/1000);
 // For negative offset, move *backing* later, never trim user vocal.
 const dryStart=offsetMs>=0?frameOffset:0;
 const backingStart=offsetMs<0?frameOffset:0;
 const frames=Math.max(parsed.dry.frames+dryStart,parsed.backing.frames+backingStart);
 const bytes=44+frames*4;
 if(bytes>MAX_MIX_BYTES)fail('mobile-mix-memory-budget');
 return Object.freeze({
   schema:'nexus.music.vocal-mix-plan.v1',
   outputSampleRate:parsed.dry.sampleRate,outputChannels:2,outputFrames:frames,
   outputBytes:bytes,dryStartFrames:dryStart,backingStartFrames:backingStart,
   requestedOffsetMs:offsetMs,
   appliedOffsetMs:+((dryStart-backingStart)*1000/parsed.dry.sampleRate).toFixed(4),
   dryGain,backingGain,
   sourceDryFrames:parsed.dry.frames,sourceBackingFrames:parsed.backing.frames,
   dryOriginalPreserved:true,sourceReencoded:false,
   syntheticBackingMixedIntoACopy:true,externalNetwork:false
 });
}
const yieldLoop=()=>new Promise(resolve=>setTimeout(resolve,0));
async function mix(dry,backing,opts={}){
 if(!opts||typeof opts!=='object')fail('invalid-mixer-options');
 const p=plan(dry,backing,opts),a=inspect(dry,MAX_DRY_BYTES),b=inspect(backing,MAX_SOURCE_BYTES);
 const onProgress=typeof opts.onProgress==='function'?opts.onProgress:()=>{};
 const shouldAbort=typeof opts.shouldAbort==='function'?opts.shouldAbort:()=>false;
 const CHUNK=32768;
 let peak=0,peakAt=0;
 // First pass: find the exact linear-mix peak. Normalize ONLY the mixed output,
 // while the original dry file remains an unmodified, separately exportable blob.
 for(let pos=0;pos<p.outputFrames;pos+=CHUNK){
  if(shouldAbort())fail('mix-cancelled');
  const end=Math.min(p.outputFrames,pos+CHUNK);
  for(let i=pos;i<end;i++){
   const d=i-p.dryStartFrames,t=i-p.backingStartFrames;
   for(let ch=0;ch<2;ch++){
    const v=numberSample(a,d,ch)*p.dryGain+numberSample(b,t,ch)*p.backingGain;
    if(!Number.isFinite(v))fail('invalid-mix-sample');
    if(Math.abs(v)>peak){peak=Math.abs(v);peakAt=i}
   }
  }
  onProgress(.48*end/p.outputFrames);
  await yieldLoop();
 }
 const factor=peak>32767*.95?32767*.95/peak:1;
 const buffer=new ArrayBuffer(p.outputBytes),view=new DataView(buffer);
 formatWavHeader(view,p.outputFrames,p.outputSampleRate);
 let clipped=0;
 for(let pos=0;pos<p.outputFrames;pos+=CHUNK){
  if(shouldAbort())fail('mix-cancelled');
  const end=Math.min(p.outputFrames,pos+CHUNK);
  for(let i=pos;i<end;i++){
   const d=i-p.dryStartFrames,t=i-p.backingStartFrames;
   for(let ch=0;ch<2;ch++){
    const sample=(numberSample(a,d,ch)*p.dryGain+numberSample(b,t,ch)*p.backingGain)*factor;
    const rounded=Math.round(sample);
    if(Math.abs(rounded)>32767)clipped++;
    view.setInt16(44+(i*2+ch)*2,Math.max(-32768,Math.min(32767,rounded)),true);
   }
  }
  onProgress(.48+.52*end/p.outputFrames);
  await yieldLoop();
 }
 if(shouldAbort())fail('mix-cancelled');
 const report=Object.freeze({
  ...p,
  schema:'nexus.music.vocal-mix-report.v1',
  peakBeforeGainDbfs:peak?+(20*Math.log10(peak/32768)).toFixed(3):null,
  outputPeakAtSeconds:+(peakAt/p.outputSampleRate).toFixed(4),
  mixedOutputGainDb:factor<1?+(20*Math.log10(factor)).toFixed(3):0,
  clippedSamplesAfterGain:clipped,
  sourceDryBytesUntouched:true,originalVoicePitchChanged:false,
  originalVoiceFormantsChanged:false,originalVoiceTimeStretched:false,
  sourceDryFramesNotTrimmed:true,
  note:'Only the mix copy is summed/level-adjusted. Keep the unmodified dry WAV independently.'
 });
 onProgress(1);
 return Object.freeze({wav:new Uint8Array(buffer),report});
}
root.NexusVocalMix=Object.freeze({inspect,parse,plan,mix,version:'offline-nondestructive-v1'});
})(typeof globalThis!=='undefined'?globalThis:this);
