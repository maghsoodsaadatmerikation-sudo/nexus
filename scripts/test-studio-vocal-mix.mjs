import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import '../web/studio-vocal-mix.js';
import '../web/studio-orchestra.js';
const V=globalThis.NexusVocalMix,O=globalThis.NexusOrchestra;
let checks=0;
function ok(fn){fn();checks++}
function fail(fn,code){ok(()=>assert.throws(fn,e=>e.message===code))}
function PCM(rate=22050,channels=1,length=33075,amplitude=2500){
 const buf=new ArrayBuffer(44+length*channels*2),dv=new DataView(buf);
 const tag=(at,s)=>[...s].forEach((c,i)=>dv.setUint8(at+i,c.charCodeAt(0)));
 tag(0,'RIFF');dv.setUint32(4,36+length*channels*2,true);
 tag(8,'WAVE');tag(12,'fmt ');dv.setUint32(16,16,true);
 dv.setUint16(20,1,true);dv.setUint16(22,channels,true);
 dv.setUint32(24,rate,true);dv.setUint32(28,rate*channels*2,true);
 dv.setUint16(32,channels*2,true);dv.setUint16(34,16,true);
 tag(36,'data');dv.setUint32(40,length*channels*2,true);
 for(let j=0;j<length;j++)for(let c=0;c<channels;c++)
  dv.setInt16(44+(j*channels+c)*2,Math.round(amplitude*Math.sin(j*.067+(c*.11))),true);
 return new Uint8Array(buf);
}
ok(()=>assert.equal(V.version,'offline-nondestructive-v1'));
const dry=PCM(),backing=PCM(22050,2,22050,1000);
const original=dry.slice(),originalBacking=backing.slice();
const parsed=V.parse(dry,backing);
ok(()=>assert.equal(parsed.dry.channels,1));
ok(()=>assert.equal(parsed.backing.channels,2));
ok(()=>assert.equal(parsed.dry.frames,33075));
ok(()=>assert.equal(parsed.dry.sampleRate,22050));
ok(()=>assert.equal(parsed.backing.frames,22050));
const p=V.plan(dry,backing,{offsetMs:500});
ok(()=>assert.equal(p.schema,'nexus.music.vocal-mix-plan.v1'));
ok(()=>assert.equal(p.dryStartFrames,11025));
ok(()=>assert.equal(p.backingStartFrames,0));
ok(()=>assert.equal(p.outputFrames,44100));
ok(()=>assert.equal(p.appliedOffsetMs,500));
ok(()=>assert(p.dryOriginalPreserved&&p.sourceReencoded===false));
const n=V.plan(dry,backing,{offsetMs:-500});
ok(()=>assert.equal(n.dryStartFrames,0));
ok(()=>assert.equal(n.backingStartFrames,11025));
ok(()=>assert.equal(n.outputFrames,33075));
ok(()=>assert.equal(n.appliedOffsetMs,-500));
ok(()=>assert.equal(V.plan(dry,backing,{offsetMs:1}).appliedOffsetMs,
  +(Math.round(22.05)/22050*1000).toFixed(4)));
const events=[];
const a=await V.mix(dry,backing,{offsetMs:500,dryGain:1,backingGain:.35,onProgress:p=>events.push(p)});
ok(()=>assert.equal(a.report.schema,'nexus.music.vocal-mix-report.v1'));
ok(()=>assert.equal(a.wav.length,44+p.outputFrames*4));
ok(()=>assert.equal(String.fromCharCode(...a.wav.slice(0,4)),'RIFF'));
ok(()=>assert.equal(new DataView(a.wav.buffer).getUint16(22,true),2));
ok(()=>assert.equal(new DataView(a.wav.buffer).getUint32(24,true),22050));
ok(()=>assert.equal(new DataView(a.wav.buffer).getUint32(40,true),p.outputFrames*4));
ok(()=>assert.equal(a.report.clippedSamplesAfterGain,0));
ok(()=>assert(a.report.originalVoicePitchChanged===false&&a.report.originalVoiceFormantsChanged===false));
ok(()=>assert(a.report.sourceDryBytesUntouched&&a.report.sourceDryFramesNotTrimmed));
ok(()=>assert.deepEqual(dry,original));
ok(()=>assert.deepEqual(backing,originalBacking));
ok(()=>assert.equal(events.at(-1),1));
ok(()=>assert(events.every(v=>v>=0&&v<=1)));
const repeated=await V.mix(dry,backing,{offsetMs:500,dryGain:1,backingGain:.35});
ok(()=>assert.deepEqual(a.wav,repeated.wav));
const mute=await V.mix(dry,backing,{offsetMs:500,dryGain:1,backingGain:0});
const v=new DataView(mute.wav.buffer),d=new DataView(dry.buffer);
ok(()=>assert.equal(v.getInt16(44,true),0));
ok(()=>assert.equal(v.getInt16(44+4*11025,true),d.getInt16(44,true)));
ok(()=>assert.equal(v.getInt16(44+4*(11025+100),true),d.getInt16(44+2*100,true)));
ok(()=>assert.equal(v.getInt16(44+4*(11025+100)+2,true),d.getInt16(44+2*100,true)));
const minus=await V.mix(dry,backing,{offsetMs:-500,dryGain:1,backingGain:0});
ok(()=>assert.equal(new DataView(minus.wav.buffer).getInt16(44+4*100,true),d.getInt16(44+2*100,true)));
const maximum=await V.mix(PCM(22050,1,250,32000),PCM(22050,2,250,32000),{dryGain:1,backingGain:1});
ok(()=>assert(maximum.report.mixedOutputGainDb<0));
ok(()=>assert.equal(maximum.report.clippedSamplesAfterGain,0));
ok(()=>assert.deepEqual(dry,original));
const stereo=await V.mix(PCM(44100,2,441,1000),PCM(44100,1,441,1000));
ok(()=>assert.equal(stereo.report.outputSampleRate,44100));
ok(()=>assert.equal(stereo.report.outputFrames,441));
fail(()=>V.plan(dry,PCM(44100,1,2205)),'sample-rate-mismatch-re-render-backing');
for(const t of [-3001,3001,1.5,Infinity,NaN,'12'])fail(
 ()=>V.plan(dry,backing,{offsetMs:t}),'invalid-alignment');
for(const [dryGain,backingGain] of [[-1,.3],[1,NaN],[Infinity,.3],[0,0],[.7,1.2]])
 fail(()=>V.plan(dry,backing,{dryGain,backingGain}),'invalid-gain-settings');
for(const edit of [
 v=>v[0]=0,v=>v[8]=0,v=>v[12]=0,v=>v[20]=0,
 v=>v[22]=0,v=>v[24]=0,v=>v[28]=0,v=>v[32]=0,
 v=>v[34]=0,v=>v[36]=0,v=>v[40]=0,v=>v[4]=0
]){
 const corrupted=dry.slice();edit(corrupted);
 ok(()=>assert.throws(()=>V.parse(corrupted,backing)));
}
fail(()=>V.parse(new Uint8Array(47),backing),'invalid-raw-wave-size');
fail(()=>V.parse(new Uint8Array(21*1024*1024),backing),'invalid-raw-wave-size');
const huge=PCM(44100,2,10);
let corrupted=huge.slice();corrupted[22]=3;
ok(()=>assert.throws(()=>V.inspect?.(corrupted)||V.parse(corrupted,huge)));
await assert.rejects(V.mix(dry,backing,{shouldAbort:()=>true}),e=>e.message==='mix-cancelled');checks++;
await assert.rejects(V.mix(dry,backing,{offsetMs:3005}),e=>e.message==='invalid-alignment');checks++;
const musical=O.compose(O.parsePrompt('operatic warm soprano choir harp flute in D minor 120 bpm 4 bars').spec,61234);
const withLead=await O.render(musical,{sampleRate:22050,excludeSyntheticLead:false});
const withoutLead=await O.render(musical,{sampleRate:22050,excludeSyntheticLead:true});
ok(()=>assert.notDeepEqual(withLead,withoutLead));
const repeatedWithoutLead=await O.render(musical,{sampleRate:22050,excludeSyntheticLead:true});
ok(()=>assert.deepEqual(repeatedWithoutLead,withoutLead));
ok(()=>assert.equal(V.parse(dry,withoutLead).backing.sampleRate,22050));
await assert.rejects(O.render(musical,{excludeSyntheticLead:'yes'}),e=>e.message==='invalid-lead-voice-flag');checks++;
const sources=['web/studio-vocal-mix.js','web/studio-orchestra-ui.js'];
for(const source of sources) {
 const code=readFileSync(new URL('../'+source,import.meta.url),'utf8');
 ok(()=>assert(!/fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|mediaDevices|api\.suno/i.test(code)));
}
const shell=readFileSync(new URL('../web/studio-shell.html',import.meta.url),'utf8');
ok(()=>assert(shell.includes('id="orchestra-mix"')&&shell.includes('/*STUDIO_VOCAL_MIX*/')));
console.log(JSON.stringify({status:'PASS',checks,bytes_mixed:a.wav.length,
 mono_stereo_supported:true,exact_integer_pcm_alignment:true,
 no_pitch_or_formant_change:true,dry_source_bit_identical:true,offline:true}));
