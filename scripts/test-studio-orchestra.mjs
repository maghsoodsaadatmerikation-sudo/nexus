import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import '../web/studio-orchestra.js';
const O=globalThis.NexusOrchestra;
let checks=0;const ok=fn=>{fn();checks++},bad=fn=>ok(()=>assert.throws(fn));
const MAIN='hypnotic airy soprano choir harp flute in D minor 92 bpm 8 bars bird chime';
const parsed=O.parsePrompt(MAIN);
ok(()=>assert.equal(parsed.ready,true));
ok(()=>assert.equal(parsed.spec.style,'hypnotic'));
ok(()=>assert.equal(parsed.spec.tone,'airy'));
ok(()=>assert.equal(parsed.spec.register,'soprano'));
ok(()=>assert.equal(parsed.spec.choir,true));
ok(()=>assert.equal(parsed.spec.voice,true));
ok(()=>assert.equal(parsed.spec.rootMidi,62));
ok(()=>assert.equal(parsed.spec.mode,'minor'));
ok(()=>assert.equal(parsed.spec.bpm,92));
ok(()=>assert.equal(parsed.spec.bars,8));
ok(()=>assert.equal(parsed.spec.animal,'bird'));
ok(()=>assert.equal(parsed.spec.fx,'chime'));
ok(()=>assert.deepEqual(parsed.spec.instruments,['flute','harp']));
ok(()=>assert(parsed.understood.includes('choir')));
ok(()=>assert.equal(parsed.unparsed.length,0));
ok(()=>assert.equal(parsed.warnings.length,0));
ok(()=>assert.equal(parsed.no_external_model,true));
const opera=O.parsePrompt('operatic powerful soprano choir violin cello harp in C minor 84 bpm 8 bars');
ok(()=>assert(opera.ready&&opera.spec.style==='opera'&&opera.spec.register==='soprano'));
const rap=O.parsePrompt('rap bright tenor piano synth 110 bpm 8 bars pulse drums');
ok(()=>assert(rap.ready&&rap.spec.style==='rap'&&rap.spec.drum));
const pop=O.parsePrompt('pop warm alto acoustic guitar flute 100 bpm 8 bars');
ok(()=>assert(pop.ready&&pop.spec.style==='pop'));
const persian=O.parsePrompt('اپرا سوپرانو گروه کر ویولن ویولنسل چنگ تمپو 84');
ok(()=>assert(persian.ready&&persian.spec.choir&&persian.spec.voice));
for(const prompt of ['opera rap soprano violin','hypnotic mysterious quantum cosmos',
                     'rap no drums percussion', 'opera soprano violin 199 bpm',
                     'pop warm dark bright violin', ' ']){
 const p=prompt.trim()?O.parsePrompt(prompt):null;
 if(p)ok(()=>assert.equal(p.ready,false));
 else bad(()=>O.parsePrompt(prompt));
}
for(const value of [null,{},[],'a'.repeat(481),'\x00'])bad(()=>O.parsePrompt(value));
const s=O.compose(parsed.spec,61234);
ok(()=>assert.equal(s.schema,'nexus.music.orchestra-score.v1'));
ok(()=>assert.equal(s.bars,8));
ok(()=>assert.equal(s.ppq,480));
ok(()=>assert.equal(s.durationSeconds,+(8*4*60/92).toFixed(4)));
ok(()=>assert(s.notes.length>50));
ok(()=>assert(s.parts.includes('lead_voice')));
ok(()=>assert(s.parts.includes('choir_high')&&s.parts.includes('choir_mid')&&s.parts.includes('choir_low')));
ok(()=>assert(s.parts.includes('animal_fx')&&s.parts.includes('generic_fx')));
ok(()=>assert(s.parts.includes('flute')&&s.parts.includes('harp')));
ok(()=>assert(s.notes.every(n=>Number.isInteger(n.pitch)&&n.startTick%120===0&&n.lengthTicks%120===0)));
ok(()=>assert(s.notes.every(n=>n.startTick+n.lengthTicks<=s.bars*O.BAR)));
ok(()=>assert.deepEqual(O.compose(parsed.spec,61234),s));
const changed=O.compose(parsed.spec,61235);
ok(()=>assert.notDeepEqual(changed.notes,s.notes));
const short=O.compose({...parsed.spec,bars:4},61234);
ok(()=>assert(short.notes.length<s.notes.length));
const sr=O.compose(rap.spec,61234);
ok(()=>assert(sr.parts.includes('drumkit')));
ok(()=>assert(sr.notes.some(n=>n.role==='kick')&&sr.notes.some(n=>n.role==='snare')));
const so=O.compose(opera.spec,61234);
ok(()=>assert(so.parts.includes('choir_high')));
ok(()=>assert(so.notes.filter(n=>n.part==='lead_voice').some(n=>n.lengthTicks===960)));
const rapNotes=sr.notes.filter(n=>n.part==='lead_voice');
ok(()=>assert(rapNotes.some(n=>n.lengthTicks===120)));
const xml=O.musicXML(s);
ok(()=>assert(xml.startsWith('<?xml version="1.0"')));
ok(()=>assert(xml.includes('<score-partwise version="4.0">')));
ok(()=>assert(xml.includes('<divisions>480</divisions>')));
ok(()=>assert(xml.includes('<sound tempo="92"/>')));
ok(()=>assert(xml.includes('<type>eighth</type><dot/>')));
ok(()=>assert(xml.includes('<lyric>')));
ok(()=>assert(xml.includes('<part-list>')));
ok(()=>assert(!xml.includes('http://')&&!xml.includes('<!DOCTYPE')));
const xmlDrums=O.musicXML(sr);
ok(()=>assert(xmlDrums.includes('<sign>percussion</sign>')));
ok(()=>assert(xmlDrums.includes('<unpitched>')));
const py=[
 'import sys,xml.etree.ElementTree as E',
 'root=E.fromstring(sys.stdin.read())',
 "assert root.tag=='score-partwise'",
 "parts=root.findall('part')",
 'assert len(parts)>=4',
 'for part in parts:',
 " for measure in part.findall('measure'):",
 "  assert sum(int(n.findtext('duration')) for n in measure.findall('note'))==1920",
 'print(len(parts))'
].join('\n');
const check=spawnSync('python3',['-c',py],{input:xml,encoding:'utf8'});
ok(()=>assert.equal(check.status,0,check.stderr));
ok(()=>assert(Number(check.stdout.trim())===s.parts.length));
const bytes=O.midi(s);
ok(()=>assert.equal(String.fromCharCode(...bytes.subarray(0,4)),'MThd'));
ok(()=>assert.equal((bytes[8]<<8|bytes[9]),1));
ok(()=>assert.equal((bytes[12]<<8|bytes[13]),480));
ok(()=>assert(bytes.length>1000));
ok(()=>assert.deepEqual(O.midi(s),bytes));
const drm=O.midi(sr);
ok(()=>assert(drm.includes(0x99)));
const wav=await O.render(short,{sampleRate:22050});
ok(()=>assert.equal(String.fromCharCode(...wav.subarray(0,4)),'RIFF'));
ok(()=>assert.equal(new DataView(wav.buffer).getUint32(24,true),22050));
ok(()=>assert.equal(new DataView(wav.buffer).getUint16(22,true),2));
ok(()=>assert(wav.length>100000));
ok(()=>assert(wav.subarray(10000).some(c=>c!==0)));
const repeated=await O.render(short,{sampleRate:22050});
ok(()=>assert.deepEqual(repeated,wav));
const info=O.inspectDryWav(wav);
ok(()=>assert(info.original_bytes_preserved&&info.transformed===false&&info.recording_sent===false));
ok(()=>assert.equal(info.sampleRate,22050));
ok(()=>assert.equal(info.channels,2));
ok(()=>assert.equal(info.frames,(wav.byteLength-44)/4));
ok(()=>assert.deepEqual(wav.slice(),wav));
for(const edit of [x=>x[0]=0,x=>x[8]=0,x=>x[22]=0,x=>x[24]=0,x=>x[40]=0,x=>x[4]=0]){
 let mutated=wav.slice();edit(mutated);bad(()=>O.inspectDryWav(mutated));
}
bad(()=>O.inspectDryWav(new Uint8Array(44)));
bad(()=>O.inspectDryWav(new Uint8Array(20*1024*1024+1)));
bad(()=>O.compose({...parsed.spec,bars:7}));
bad(()=>O.compose({...parsed.spec,voice:'yes'}));
bad(()=>O.compose({...parsed.spec,instruments:['imposter']}));
bad(()=>O.compose({...parsed.spec,tempo:130}));
bad(()=>O.compose(parsed.spec,0));
await assert.rejects(O.render({...s,durationSeconds:121}));checks++;
await assert.rejects(O.render(short,{sampleRate:12345}));checks++;
await assert.rejects(O.render(short,{shouldAbort:()=>true}));checks++;
// Cancellation at the normalization scan must not enter PCM encoding.
const progress=[];
await assert.rejects(O.render(short,{onProgress:p=>progress.push(p),shouldAbort:()=>progress.some(p=>p>.7&&p<=.74)}),e=>e.message==='render-cancelled');checks++;
ok(()=>assert(progress.some(p=>p>.7&&p<=.74)&&!progress.some(p=>p>.74)));
const completeProgress=[];
const unchanged=await O.render(short,{onProgress:p=>completeProgress.push(p)});
ok(()=>assert.deepEqual(unchanged,wav));
ok(()=>assert(completeProgress.every((p,i)=>p>=0&&p<=1&&(i===0||p>=completeProgress[i-1]))));
ok(()=>assert.equal(completeProgress.at(-1),1));
const generated=readFileSync(new URL('../web/studio-orchestra.js',import.meta.url),'utf8');
ok(()=>assert(!/fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|api\.suno/i.test(generated)));
const ui=readFileSync(new URL('../web/studio-orchestra-ui.js',import.meta.url),'utf8');
ok(()=>assert(!/fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|mediaDevices|recordAudio/.test(ui)));
ok(()=>assert(ui.includes("new Blob([bytes],{type:'audio/wav'})")));
ok(()=>assert(ui.includes("original.playbackRate=1")));
const shell=readFileSync(new URL('../web/studio-shell.html',import.meta.url),'utf8');
ok(()=>assert(shell.includes('id="orchestra-card"')&&shell.includes('/*STUDIO_ORCHESTRA*/')));
console.log(JSON.stringify({status:'PASS',checks,synthesized_wav_bytes:wav.length,
 musicxml_measures:s.bars,voices:'generic-vowels-only',synthetic_choir:true,
 spoken_lyrics:false,real_animal_recordings:false,voice_modification:false,
 external_network_calls:0}));
