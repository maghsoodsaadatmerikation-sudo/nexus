import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import '../web/studio-music.js';
const M=globalThis.NexusMusic;
let checks=0;
const ok=fn=>{fn();checks++};
const opt={...M.DEFAULT};
const score=M.compose(opt);
ok(()=>assert.equal(score.schema,'nexus.music.score.v1'));
ok(()=>assert.equal(score.options.mode,'shur'));
ok(()=>assert.equal(score.sections.length,7));
ok(()=>assert.equal(score.sections[0].start,0));
ok(()=>assert.equal(score.sections.at(-1).end,64));
ok(()=>assert.equal(score.durationSeconds,160));
ok(()=>assert(score.notes.length>300));
ok(()=>assert(score.notes.every(n=>n.start>=0&&n.start+n.duration<=score.durationSeconds+.001)));
ok(()=>assert.equal(score.review.objective_only,true));
ok(()=>assert.equal(score.review.audio_quality_evaluated,false));
ok(()=>assert.equal(score.review.traditional_authenticity_verified,false));
ok(()=>assert(score.sections[5].energy>score.sections[0].energy));
ok(()=>assert(score.sections[6].energy<score.sections[5].energy));
ok(()=>assert(score.review.motif_breath_bars.length>=2));
ok(()=>assert.equal(score.review.solo_lead,'electric_guitar'));
ok(()=>assert.equal(score.review.warnings.length,0));
ok(()=>assert(score.notes.some(n=>n.instrument==='santur')));
ok(()=>assert(score.notes.some(n=>n.instrument==='kamancheh')));
ok(()=>assert(score.notes.some(n=>n.instrument==='electric_guitar')));
ok(()=>assert(score.notes.some(n=>n.instrument==='daf')));
const solo=score.sections.find(s=>s.name==='Instrumental solo');
ok(()=>assert(score.notes.filter(n=>n.role==='motif'&&n.start>=solo.start*2.5&&n.start<solo.end*2.5)
 .every(n=>n.instrument==='electric_guitar')));
const repeated=M.compose(opt);
ok(()=>assert.equal(JSON.stringify(repeated),JSON.stringify(score)));
const alt=M.compose({...opt,seed:opt.seed+1});
ok(()=>assert.deepEqual(alt.motif,score.motif));
ok(()=>assert.notEqual(JSON.stringify(alt.notes),JSON.stringify(score.notes)));
const retuned=M.compose({...opt,mode:'bayati'});
ok(()=>assert(retuned.notes.some(n=>Math.abs(n.pitch-Math.floor(n.pitch)-.5)<.001)));
ok(()=>assert.equal(M.compose({...opt,bars:48}).sections.at(-1).end,48));
ok(()=>assert.equal(M.compose({...opt,bars:32}).sections.at(-1).end,32));
const long=M.compose({...opt,bpm:72,bars:64});
ok(()=>assert(long.durationSeconds>210&&long.durationSeconds<215));
for(const bad of [
 {...opt,bpm:0},{...opt,bars:65},{...opt,seed:0},{...opt,motifSeed:0},
 {...opt,key:'F+0.5'},{...opt,mode:'fake'},{...opt,solo:'random'},
 {...opt,lead:'human-voice'},{...opt,story:'victory'},
 {...opt,title:'x'.repeat(91)},{...opt,hidden:'network'},
 {...opt,daf:'true'},{...opt,seed:Math.PI}
]){ok(()=>assert.throws(()=>M.compose(bad)))}
const midi=M.midi(retuned);
ok(()=>assert.equal(String.fromCharCode(...midi.slice(0,4)),'MThd'));
ok(()=>assert.equal((midi[8]<<8)+midi[9],1));
ok(()=>assert((midi[10]<<8)+midi[11]>5));
ok(()=>assert.equal((midi[12]<<8)+midi[13],480));
ok(()=>assert(midi.length>2000));
ok(()=>assert([...midi].some((b,i)=>b===0xe0+3&&midi[i+1]===0&&midi[i+2]===80))); // pitch bend +50 cents for santur
ok(()=>assert([...midi].some(b=>b===0x99))); // real MIDI percussion
ok(()=>assert.deepEqual(M.midi(retuned),midi));
const short={...score,durationSeconds:1.75,
 notes:score.notes.filter(n=>n.start<1.5).map(n=>({...n,duration:Math.min(n.duration,1.5-n.start)})).filter(n=>n.duration>.02)};
const progress=[];
const wav=await M.renderWav(short,{sampleRate:22050,onProgress:x=>progress.push(x)});
ok(()=>assert.equal(String.fromCharCode(...wav.slice(0,4)),'RIFF'));
ok(()=>assert.equal(String.fromCharCode(...wav.slice(8,12)),'WAVE'));
ok(()=>assert.equal(String.fromCharCode(...wav.slice(36,40)),'data'));
ok(()=>assert.equal(new DataView(wav.buffer).getUint32(24,true),22050));
ok(()=>assert.equal(new DataView(wav.buffer).getUint16(22,true),2));
ok(()=>assert.equal(new DataView(wav.buffer).getUint16(34,true),16));
ok(()=>assert(wav.length>100_000));
ok(()=>assert(wav.some((byte,i)=>i>44&&byte!==0)));
ok(()=>assert.equal(progress.at(-1),1));
const wavAgain=await M.renderWav(short);ok(()=>assert.deepEqual(wavAgain,wav));
await assert.rejects(M.renderWav(short,{sampleRate:22050,shouldAbort:()=>true}));checks++;
await assert.rejects(M.renderWav(short,{sampleRate:12345}));checks++;
const code=await readFile(new URL('../web/studio-music.js',import.meta.url),'utf8');
ok(()=>assert(!/fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|Suno|api\.suno/i.test(code.replace(/Suno/g,''))));
const shell=await readFile(new URL('../web/studio-shell.html',import.meta.url),'utf8');
ok(()=>assert(shell.includes('id="music-card"')&&shell.includes('/*STUDIO_MUSIC*/')&&shell.includes('/*STUDIO_MUSIC_UI*/')));
const focus=await readFile(new URL('../web/studio-focus-ui.js',import.meta.url),'utf8');
ok(()=>assert(focus.includes("['music-card','Music Lab','موسیقی']")));
console.log(JSON.stringify({status:'PASS',checks,engine:'nexus-native-composition',midi_bytes:midi.length,wav_bytes:wav.length,external_model_used:false,acoustic_instruments_recorded:false}));
