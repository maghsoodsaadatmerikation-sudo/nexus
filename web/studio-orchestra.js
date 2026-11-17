/* NEXUS Orchestra Lab v1 — deterministic, original, offline score + sound.
 * Prompt understanding is an inspectable constrained grammar, NOT semantic AI.
 * Generic vowel voices and animal-inspired electronic effects are NOT people,
 * singing understandable words, or field recordings. No external networks.
 */
(function(root){'use strict';
const TAU=2*Math.PI,TPQ=480,BAR=TPQ*4,PART_LIMIT=12;
const GM=Object.freeze({
 grand_piano:{name:'Grand piano',gm:0,family:'keys',pan:-.23},
 violin:{name:'Violin',gm:40,family:'bow',pan:-.19},
 viola:{name:'Viola',gm:41,family:'bow',pan:-.1},
 cello:{name:'Cello',gm:42,family:'bow',pan:-.25},
 double_bass:{name:'Double bass',gm:43,family:'bow',pan:-.45},
 flute:{name:'Flute',gm:73,family:'wind',pan:.18},
 oboe:{name:'Oboe',gm:68,family:'reed',pan:.12},
 clarinet:{name:'Clarinet',gm:71,family:'reed',pan:.24},
 french_horn:{name:'French horn',gm:60,family:'brass',pan:-.35},
 trumpet:{name:'Trumpet',gm:56,family:'brass',pan:.3},
 trombone:{name:'Trombone',gm:57,family:'brass',pan:-.3},
 harp:{name:'Harp',gm:46,family:'pluck',pan:.3},
 pipe_organ:{name:'Pipe organ',gm:19,family:'organ',pan:0},
 acoustic_guitar:{name:'Acoustic guitar',gm:24,family:'pluck',pan:.25},
 drumkit:{name:'Electronic drum kit',gm:0,family:'drum',pan:0},
 synth_pad:{name:'Synthetic pad',gm:89,family:'pad',pan:.3},
 lead_voice:{name:'Generic synthetic vowel (not human)',gm:53,family:'vowel',pan:0},
 choir_high:{name:'Synthetic choir high vowel',gm:52,family:'vowel',pan:-.28},
 choir_mid:{name:'Synthetic choir mid vowel',gm:52,family:'vowel',pan:0},
 choir_low:{name:'Synthetic choir low vowel',gm:52,family:'vowel',pan:.28},
 generic_fx:{name:'Synthetic effect',gm:98,family:'fx',pan:.25},
 animal_fx:{name:'Animal-inspired electronic effect',gm:99,family:'animal',pan:-.28}
});
const DOMAINS=[
 ['grand_piano',/(?:\b(?:grand\s+)?piano\b|پیانو)/iu],
 ['violin',/(?:\bviolin\b|ویولن(?!سل)|ویولون)/iu],
 ['viola',/(?:\bviola\b|ویولا)/iu],
 ['cello',/(?:\bcello\b|ویولنسل)/iu],
 ['double_bass',/(?:\b(?:double bass|contrabass)\b|کنترباس)/iu],
 ['flute',/(?:\bflute\b|فلوت)/iu],
 ['oboe',/(?:\boboe\b|ابوا)/iu],
 ['clarinet',/(?:\bclarinet\b|کلارینت)/iu],
 ['french_horn',/(?:\b(?:french )?horn\b|هورن)/iu],
 ['trumpet',/(?:\btrumpet\b|ترومپت)/iu],
 ['trombone',/(?:\btrombone\b|ترومبون)/iu],
 ['harp',/(?:\bharp\b|چنگ)/iu],
 ['pipe_organ',/(?:\b(?:pipe )?organ\b|ارگ)/iu],
 ['acoustic_guitar',/(?:\b(?:acoustic )?guitar\b|گیتار آکوستیک)/iu],
 ['synth_pad',/(?:\b(?:synth|pad)\b|سینتی)/iu]
];
const STYLES=[
 ['opera',/(?:\b(?:opera|operatic)\b|اپرا|اپرایی)/iu],
 ['rap',/(?:\b(?:rap|hip[\s-]?hop)\b|رپ|هیپ هاپ)/iu],
 ['pop',/(?:\bpop\b|پاپ)/iu],
 ['hypnotic',/(?:\b(?:hypnotic|trance|meditative)\b|هیپنوتیز|خلسه|مدیتیشن)/iu],
 ['chant',/(?:\b(?:chant|prayer)\b|آواز نیایشی|ذکر)/iu]
];
const TONES=[
 ['airy',/(?:\b(?:airy|breathy|whispery)\b|نفس‌دار|نجوا)/iu],
 ['warm',/(?:\b(?:warm|velvety)\b|گرم)/iu],
 ['dark',/(?:\b(?:dark|deep)\b|تیره|بم)/iu],
 ['bright',/(?:\b(?:bright|brilliant)\b|درخشان)/iu],
 ['soft',/(?:\b(?:soft|gentle)\b|آرام|لطیف)/iu],
 ['powerful',/(?:\b(?:powerful|belting|dramatic)\b|پرقدرت|حماسی)/iu]
];
const REGISTERS=[
 ['soprano',/(?:\bsoprano\b|سوپرانو)/iu],
 ['alto',/(?:\balto\b|آلتو)/iu],
 ['tenor',/(?:\btenor\b|تنور)/iu],
 ['baritone',/(?:\bbaritone\b|باریتون)/iu]
];
const ANIMALS=[
 ['bird',/(?:\b(?:bird|birdsong|chirp)\b|پرنده|چهچه)/iu],
 ['crow',/(?:\b(?:crow|raven)\b|کلاغ|زاغ)/iu],
 ['owl',/(?:\bowl\b|جغد)/iu],
 ['whale',/(?:\bwhale\b|نهنگ)/iu],
 ['cat',/(?:\bcat\b|گربه)/iu]
];
const FX=[
 ['riser',/(?:\briser\b|اوج صوتی)/iu],
 ['chime',/(?:\b(?:chime|bell)\b|زنگ)/iu],
 ['pulse',/(?:\bpulse\b|پالس)/iu]
];
function fail(code){throw Error(code)}
function clamp(v,a,b){return Math.max(a,Math.min(b,v))}
function int(n,a,b){return Number.isSafeInteger(n)&&n>=a&&n<=b}
function normalize(s){return s.normalize('NFKC').toLowerCase().replace(/[،؛]/g,' ').trim()}
function discover(source,patterns){return patterns.filter(([,regex])=>regex.test(source)).map(([key])=>key)}
const STOP=/^(?:a|an|the|and|with|in|of|for|make|create|music|song|instrumental|voice|vocals|synthetic|vowel|choir|chorus|no|without|softly|music|instrument|orchestral|original|میخوام|می‌خوام|آهنگ|موسیقی|با|و|به|یک|از|بدون|بساز|آواز|صدای|صدا|ساز|گروه|کر|شکل|آهنگی|پر|ساخت|بکن|خواننده)$/iu;
function parsePrompt(value){
 if(typeof value!=='string'||value.length>480||!value.trim()||/[\x00-\x1f]/u.test(value))fail('invalid-prompt');
 const raw=normalize(value);
 const style=discover(raw,STYLES),tone=discover(raw,TONES),register=discover(raw,REGISTERS);
 const animals=discover(raw,ANIMALS),effects=discover(raw,FX),instruments=discover(raw,DOMAINS);
 let sanitized=raw,recognized=[];
 const all=[...STYLES,...TONES,...REGISTERS,...ANIMALS,...FX,...DOMAINS];
 for(const [name,regex] of all){
  if(regex.test(sanitized)){sanitized=sanitized.replace(new RegExp(regex.source,regex.flags.replace('u','')+'u'),' ');recognized.push(name)}
 }
 const choir=/(?:\bchoir\b|گروه\s*کر|کُر)/iu.test(sanitized);
 if(choir){sanitized=sanitized.replace(/(?:\bchoir\b|گروه\s*کر|کُر)/iu,' ');recognized.push('choir')}
 const noVocal=/(?:\b(?:no|without)\s+(?:vocals?|voice|singers?)\b|\binstrumental\b|بدون\s+(?:وکال|آواز))/iu.test(sanitized);
 if(noVocal){sanitized=sanitized.replace(/(?:\b(?:no|without)\s+(?:vocals?|voice|singers?)\b|\binstrumental\b|بدون\s+(?:وکال|آواز))/iu,' ');recognized.push('no-human-or-synthetic-vocal')}
 const voice=/(?:\b(?:vocal|vocals|singer|voice|singing)\b|آواز|خوانندگی|وکال)/iu.test(sanitized);
 if(voice){sanitized=sanitized.replace(/(?:\b(?:vocal|vocals|singer|voice|singing)\b|آواز|خوانندگی|وکال)/iu,' ');recognized.push('generic-vowel')}
 const forbidDrums=/(?:\b(?:no|without)\s+(?:drums?|percussion)\b|بدون\s+(?:درام|ریتم|پرکاشن))/iu.test(sanitized);
 if(forbidDrums){sanitized=sanitized.replace(/(?:\b(?:no|without)\s+(?:drums?|percussion)\b|بدون\s+(?:درام|ریتم|پرکاشن))/iu,' ');recognized.push('no-drums')}
 const drums=/(?:\b(?:drums?|percussion|beat)\b|درام|پرکاشن)/iu.test(sanitized);
 if(drums){sanitized=sanitized.replace(/(?:\b(?:drums?|percussion|beat)\b|درام|پرکاشن)/iu,' ');recognized.push('drums')}
 const tempo=raw.match(/(?:\b(\d{2,3})\s*bpm\b|\btempo\s*(\d{2,3})\b|تمپو\s*(\d{2,3}))/iu);
 if(tempo){sanitized=sanitized.replace(tempo[0],' ');recognized.push('tempo')}
 const barsMatch=raw.match(/(?:\b(4|8|12|16|24)\s*bars?\b|(4|8|12|16|24)\s*میزان)/iu);
 if(barsMatch){sanitized=sanitized.replace(barsMatch[0],' ');recognized.push('bars')}
 const keysMatch=raw.match(/\b([a-g])\s*(#|♯|b|♭)?\s*(major|minor)\b/iu);
 if(keysMatch){sanitized=sanitized.replace(keysMatch[0],' ');recognized.push('key')}
 const unknown=[...new Set(sanitized.split(/[\s.,!?()[\]{}:;؛،]+/u)
  .filter(Boolean).filter(w=>!STOP.test(w)))].slice(0,12);
 const warnings=[];
 if(style.length>1)warnings.push('ambiguous-vocal-styles');
 if(noVocal&&(voice||choir))warnings.push('conflicting-vocal-instructions');
 if(tone.length>1)warnings.push('multiple-vocal-timbres-use-one');
 if(register.length>1)warnings.push('multiple-registers-use-one');
 if(instruments.length>7)warnings.push('more-than-seven-instruments');
 if(drums&&forbidDrums)warnings.push('conflicting-drum-instructions');
 if(unknown.length)warnings.push('unparsed-terms-require-review');
 const expectedParts=instruments.length+((voice||style.length>0)&&!noVocal?1:0)+(choir?3:0)+
   (animals.length?1:0)+(effects.length?1:0)+(drums&&!forbidDrums?1:0);
 if(expectedParts>PART_LIMIT)warnings.push('part-count-over-local-budget');
 const tempoNumber=tempo?Number(tempo[1]||tempo[2]||tempo[3]):94;
 if(!int(tempoNumber,60,160))warnings.push('tempo-out-of-range');
 let rootMidi=60,mode='minor';
 if(keysMatch){
  const base={c:0,d:2,e:4,f:5,g:7,a:9,b:11}[keysMatch[1].toLowerCase()];
  rootMidi=60+base+(keysMatch[2]==='#'||keysMatch[2]==='♯'?1:keysMatch[2]==='b'||keysMatch[2]==='♭'?-1:0);
  mode=keysMatch[3].toLowerCase();
 }
 const selectedStyle=style[0]||'instrumental';
 const selectedInstruments=instruments.length?instruments.slice(0,7):
  selectedStyle==='opera'?['violin','cello','harp']:
  selectedStyle==='rap'?['grand_piano','synth_pad']:
  selectedStyle==='hypnotic'?['harp','flute','synth_pad']:
  ['grand_piano','violin','cello'];
 return Object.freeze({
  schema:'nexus.music.prompt-plan.v1',prompt:value,
  spec:{style:selectedStyle,tone:tone[0]||'warm',register:register[0]||'soprano',
   instruments:selectedInstruments,choir,voice:(voice||style.length>0)&&!noVocal,
   animal:animals[0]||'none',fx:effects[0]||'none',
   drum:drums&&!forbidDrums,bpm:int(tempoNumber,60,160)?tempoNumber:94,
   bars:barsMatch?Number(barsMatch[1]||barsMatch[2]):8,rootMidi,mode},
  understood:recognized,unparsed:unknown,warnings,
  ready:warnings.length===0,confidence:'strict-keyword-grammar-not-semantic-AI',
  no_external_model:true
 });
}
function xorshift(seed){let x=(seed>>>0)||1;return()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296}}
function validateSpec(p){
 if(!p||typeof p!=='object'||Array.isArray(p))fail('invalid-orchestra-spec');
 const fields=['style','tone','register','instruments','choir','voice','animal','fx','drum','bpm','bars','rootMidi','mode'];
 if(Object.keys(p).sort().join()!==fields.sort().join())fail('invalid-orchestra-spec-fields');
 if(!['instrumental','opera','pop','rap','hypnotic','chant'].includes(p.style)||
    !TONES.some(x=>x[0]===p.tone)||!REGISTERS.some(x=>x[0]===p.register)||
    !Array.isArray(p.instruments)||p.instruments.length>7||
    p.instruments.some(i=>!Object.hasOwn(GM,i)||['vowel','fx','animal'].includes(GM[i].family))||
    new Set(p.instruments).size!==p.instruments.length||typeof p.choir!=='boolean'||
    typeof p.voice!=='boolean'||typeof p.drum!=='boolean'||
    !['none',...ANIMALS.map(x=>x[0])].includes(p.animal)||
    !['none',...FX.map(x=>x[0])].includes(p.fx)||
    !int(p.bpm,60,160)||![4,8,12,16,24].includes(p.bars)||
    !int(p.rootMidi,48,83)||!['minor','major'].includes(p.mode))fail('invalid-orchestra-spec');
 return p;
}
function compose(spec,seed=61234){
 validateSpec(spec);
 if(!int(seed,1,2147483646))fail('invalid-orchestra-seed');
 const r=xorshift(seed),notes=[],scale=spec.mode==='minor'?[0,2,3,5,7,8,10]:[0,2,4,5,7,9,11];
 const b=spec.bars,sections=[
  {name:'Intro',start:0,end:Math.max(1,Math.floor(b/4))},
  {name:'Development',start:Math.max(1,Math.floor(b/4)),end:Math.max(2,Math.floor(3*b/4))},
  {name:'Return',start:Math.max(2,Math.floor(3*b/4)),end:b}
 ];
 let id=0;
 function emit(part,bar,position,duration,pitch,vel,role,vowel='Ah'){
  if(!Object.hasOwn(GM,part)||bar<0||bar>=b||position<0||
     position+duration>BAR||duration<120||position%120||duration%120)fail('invalid-composed-event');
  if(pitch<25||pitch>110)fail('pitch-out-of-bounds');
  notes.push({id:id++,part,startTick:bar*BAR+position,lengthTicks:duration,
    pitch,velocity:clamp(Math.round(vel),20,116),
    pan:GM[part].pan,role,vowel});
 }
 const degree=(d,oct=0)=>spec.rootMidi+scale[((d%7)+7)%7]+12*(Math.floor(d/7)+oct);
 const melodic=spec.style==='rap'?[120,240,120,480,240,240,480]:
  spec.style==='opera'?[960,480,480]:spec.style==='hypnotic'||spec.style==='chant'?[960,960]:
  spec.style==='pop'?[240,480,240,480,480]:[480,480,480,480];
 for(let bar=0;bar<b;bar++){
  const peak=sections[1].start<=bar&&bar<sections[1].end,
   energy=bar<b/4?.32:peak?.78:.40;
  const chord=[0,5,3,4][Math.floor(bar/2)%4];
  for(const [index,part] of spec.instruments.entries()){
   if(part==='grand_piano'||part==='harp'||part==='acoustic_guitar'){
    for(let pos=0;pos<BAR;pos+=480){
     const pitch=degree(chord+((pos/480)%2?4:0),index===0?-1:0);
     emit(part,bar,pos,360,pitch,40+energy*34,'arpeggio');
    }
   }else{
    for(let pos=0;pos<BAR;pos+=960)
     emit(part,bar,pos,960,degree(chord+(index%2?4:0),index===0?0:-1),
       37+energy*43,'orchestra');
   }
  }
  const isVocal=spec.voice;
  if(isVocal){
   let pos=0,i=0;
   while(pos<BAR){
    const d=melodic[i%melodic.length],length=Math.min(d,BAR-pos);
    const gap=bar===0&&pos===0||((bar+1)%8===0&&pos>=1440);
    if(!gap){
     const contour=(bar%4===3&&i%3===0?4:[0,2,4,3,2,1,0][(i+bar)%7])+
       (bar%4===2&&i%3===1&&((seed+bar)%2===0||r()<.07)?1:0);
     let offset=spec.register==='soprano'?12:spec.register==='alto'?7:
                  spec.register==='tenor'?0:-5;
     const pitches=spec.style==='rap'?degree(0,0)+offset+(i%2):
                   degree(contour,0)+offset;
     const vel=spec.style==='opera'?89:spec.style==='hypnotic'?48:
               spec.style==='rap'?73:62;
     emit('lead_voice',bar,pos,length,pitches,vel,'synthetic-vowel', ['Ah','Oo','Ee'][i%3]);
    }
    pos+=length;i++;
   }
  }
  if(spec.choir){
   const voicings=[['choir_high',4,1],['choir_mid',2,0],['choir_low',0,-1]];
   for(const [part,step,oct] of voicings){
    for(let pos=0;pos<BAR;pos+=960){
     emit(part,bar,pos,960,degree(chord+step,oct),
       41+energy*22,'synth-choir',pos===0?'Oo':'Ah');
    }
   }
  }
  if(spec.drum){for(let beat=0;beat<8;beat++){
    const instrument=beat%2===1?42:beat%4===0?36:38;
    emit('drumkit',bar,beat*240,240,instrument,60+energy*20,
      instrument===36?'kick':instrument===38?'snare':'hat');
   }}
  if(spec.fx!=='none'&&bar===Math.max(0,sections[1].start-1))
   emit('generic_fx',bar,960,960,72,64,'generic-'+spec.fx);
  if(spec.animal!=='none'&&(bar===0||bar===b-2)){
   emit('animal_fx',bar,960,480,76,55,'animal-'+spec.animal);
  }
 }
 notes.sort((a,b)=>a.startTick-b.startTick||a.id-b.id);
 const parts=[...new Set(notes.map(x=>x.part))];
 if(parts.length>PART_LIMIT)fail('excessive-orchestra-parts');
 return Object.freeze({schema:'nexus.music.orchestra-score.v1',spec:{...spec},seed,
  ppq:TPQ,bars:b,bpm:spec.bpm,notes,parts,sections,
  durationSeconds:+(b*4*60/spec.bpm).toFixed(4),
  synthetic_vowels_only:true,human_voice_modified:false,
  generated_human_lyrics:false,external_generation:false});
}
function xmlEsc(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]))}
function musicXML(score){
 if(score?.schema!=='nexus.music.orchestra-score.v1')fail('invalid-orchestra-score');
 const name=xmlEsc('NEXUS original orchestral score');
 const steps=['C','C','D','D','E','F','F','G','G','A','A','B'];
 const alterations=[0,1,0,1,0,0,1,0,1,0,1,0];
 const noteType={120:'16th',240:'eighth',360:'eighth',480:'quarter',
  720:'quarter',960:'half',1440:'half',1920:'whole'};
 function nXML(n){
  const pc=((Math.floor(n.pitch)%12)+12)%12,m=Math.floor(n.pitch);
  const altered=alterations[pc]+(n.pitch-m);
  const step=steps[pc],oct=Math.floor(m/12)-1,d=n.lengthTicks;
  const pitchTag=n.part==='drumkit'?'<unpitched><display-step>F</display-step><display-octave>4</display-octave></unpitched>':
    '<pitch><step>'+step+'</step>'+(altered?'<alter>'+altered+'</alter>':'')+
    '<octave>'+oct+'</octave></pitch>';
  const base='<duration>'+d+'</duration><type>'+noteType[d]+'</type>'+([360,720,1440].includes(d)?'<dot/>':'');
  const isVoc=/^(?:lead_voice|choir_)/.test(n.part);
  const lyric=isVoc?'<lyric><syllabic>single</syllabic><text>'+xmlEsc(n.vowel)+'</text></lyric>':'';
  return '<note>'+pitchTag+base+lyric+'</note>';
 }
 const metadata=['<?xml version="1.0" encoding="utf-8"?>',
 '<score-partwise version="4.0"><work><work-title>'+name+'</work-title></work>',
 '<movement-title>'+name+'</movement-title><identification><creator type="composer">NEXUS deterministic local engine</creator></identification>',
 '<defaults><scaling><millimeters>7</millimeters><tenths>40</tenths></scaling></defaults>',
 '<part-list>',...score.parts.map((p,i)=>'<score-part id="P'+(i+1)+'"><part-name>'+xmlEsc(GM[p].name)+'</part-name>'+
   '<part-abbreviation>'+xmlEsc(GM[p].name.slice(0,12))+'</part-abbreviation></score-part>'),'</part-list>'];
 const measures=[];
 for(let pi=0;pi<score.parts.length;pi++){
  const part=score.parts[pi],rows=score.notes.filter(n=>n.part===part).sort((a,b)=>a.startTick-b.startTick);
  measures.push('<part id="P'+(pi+1)+'">');
  for(let bar=0;bar<score.bars;bar++){
   let cursor=bar*BAR;
   const events=rows.filter(n=>Math.floor(n.startTick/BAR)===bar);
   measures.push('<measure number="'+(bar+1)+'">');
   if(bar===0)measures.push('<attributes><divisions>480</divisions><key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type></time><clef><sign>'+ (part==='drumkit'?'percussion':'G') +'</sign>'+ (part==='drumkit'?'':'<line>2</line>') +'</clef></attributes><direction placement="above"><direction-type><words>Original synthetic arrangement</words></direction-type><sound tempo="'+score.bpm+'"/></direction>');
   for(const n of events){
    if(n.startTick<cursor)fail('overlapping-notation-part');
    let rest=n.startTick-cursor;
    if(rest)measures.push('<note><rest/><duration>'+rest+'</duration></note>');
    measures.push(nXML(n));cursor=n.startTick+n.lengthTicks;
   }
   if(cursor<(bar+1)*BAR)measures.push('<note><rest/><duration>'+((bar+1)*BAR-cursor)+'</duration></note>');
   measures.push('</measure>');
  }
  measures.push('</part>');
 }
 return [...metadata,...measures,'</score-partwise>'].join('');
}
function bytes32(n){return [(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255]}
function bytes16(n){return [(n>>>8)&255,n&255]}
function vlq(value){
 if(!int(value,0,0x0fffffff))fail('invalid-midi-delay');
 const a=[value&127];while((value>>=7))a.unshift((value&127)|128);return a;
}
function midi(score){
 if(score?.schema!=='nexus.music.orchestra-score.v1')fail('invalid-orchestra-score');
 const channels=[0,1,2,3,4,5,6,7,8,10,11,12,13,14,15];
 if(score.parts.length>channels.length)fail('too-many-midi-tracks');
 const tracks=[],tempo=Math.round(60_000_000/score.bpm);
 function encode(events){
  events.sort((a,b)=>a.tick-b.tick||a.order-b.order);let previous=0,out=[];
  for(const ev of events){out.push(...vlq(ev.tick-previous),...ev.msg);previous=ev.tick}
  out.push(0,0xff,0x2f,0);
  return [0x4d,0x54,0x72,0x6b,...bytes32(out.length),...out]
 }
 tracks.push(encode([{tick:0,order:0,msg:[0xff,0x51,3,(tempo>>>16)&255,(tempo>>>8)&255,tempo&255]},
  {tick:0,order:1,msg:[0xff,0x58,4,4,2,24,8]}]));
 for(let i=0;i<score.parts.length;i++){
  const name=score.parts[i],channel=name==='drumkit'?9:channels[i],part=GM[name];
  const data=name==='drumkit'?[]:[{tick:0,order:0,msg:[0xc0|channel,part.gm]}];
  for(const n of score.notes.filter(x=>x.part===name)){
   if(!Number.isInteger(n.pitch))fail('unsupported-microtone-midi-channel');
   data.push({tick:n.startTick,order:2,msg:[0x90|channel,n.pitch,n.velocity]});
   data.push({tick:n.startTick+n.lengthTicks,order:1,msg:[0x80|channel,n.pitch,0]});
  }
  tracks.push(encode(data));
 }
 const out=[0x4d,0x54,0x68,0x64,...bytes32(6),0,1,...bytes16(tracks.length),...bytes16(TPQ)];
 for(const t of tracks)out.push(...t);
 return new Uint8Array(out);
}
// Deterministic light synthesis approximating western instruments & vowels.
// Not vocal text-to-speech, not real animal recording, not sampled instruments.
function hashNoise(i,id){let n=Math.imul((i+11)|0,1597334677)^Math.imul((id+3)|0,3812015801);n=Math.imul(n^(n>>>16),2246822519);return ((n^(n>>>13))>>>0)/2147483648-1;}
function voiceSample(note,phase,t,seconds,freq,index,rate,spec){
 const id=note.id,inst=GM[note.part],vowel=note.vowel||'Ah';
 const attack=inst.family==='bow'?.08:inst.family==='vowel'?(spec.style==='rap'?.012:spec.style==='opera'?.08:.045):inst.family==='wind'?.05:
  inst.family==='pad'?.16:inst.family==='organ'?.035:.008;
 const release=inst.family==='bow'?.13:inst.family==='vowel'?.09:.11;
 const env=clamp(t/attack,0,1)*clamp((seconds-t)/release,0,1);
 if(env<=0)return 0;
 const noise=hashNoise(index,id);
 if(inst.family==='drum'){
  const body=note.pitch===36?Math.sin(TAU*(72*t+18*(1-Math.exp(-15*t))/15))*Math.exp(-t*22):0;
  const hit=noise*Math.exp(-t*(note.pitch===42?75:42));
  return (body*.76+hit*(note.pitch===36?.16:.38))*env;
 }
 if(inst.family==='animal'){
  const which=note.role.slice(7);
  const sweep=which==='bird'?1300+340*Math.sin(2*Math.PI*9*t):
   which==='crow'?390-150*t:which==='owl'?470+90*Math.sin(2*Math.PI*2*t):
   which==='whale'?170+180*t:520+110*Math.sin(2*Math.PI*5*t);
  const ratePhase=TAU*(sweep*t+.06*Math.sin(TAU*3*t));
  return (Math.sin(ratePhase)+.2*noise)*env*Math.exp(-t*2.1)*.26;
 }
 if(inst.family==='fx'){
  const kind=note.role.slice(8);
  return (kind==='riser'?Math.sin(phase*(.3+2*t))+noise*.08:
          kind==='chime'?Math.sin(phase*2.32)*Math.exp(-t*4):
          Math.sin(phase*.5)*Math.exp(-t*3))*.3*env;
 }
 const vowels={Ah:[810,1210],Ee:[420,2050],Oo:[460,900]},formants=vowels[vowel]||vowels.Ah;
 const bend=inst.family==='bow'||inst.family==='vowel'?freq*(spec.style==='rap'?.0003:spec.style==='opera'?.0038:.002)/5.3*
  Math.sin(TAU*5.3*t)*clamp((t-.1)/.12,0,1):0;
 const p=phase+bend;
 let sum=0,weight=0;
 for(let h=1;h<=12&&h*freq<rate*.45;h++){
  let c=1/Math.pow(h,inst.family==='brass'?.75:inst.family==='reed'?.92:1.15);
  if(inst.family==='pluck')c*=Math.abs(Math.sin(h*.53))*Math.exp(-t*(.24+.11*h));
  if(inst.family==='bow')c*=h<6?1.12:.55;
  if(inst.family==='wind')c*=h===1?1:.16;
  if(inst.family==='organ')c=h<=4?.8/h:0;
  if(inst.family==='vowel'){
   const frequency=h*freq;
   const resonance=.26+1.6*Math.exp(-Math.pow((frequency-formants[0])/230,2))
      +1.2*Math.exp(-Math.pow((frequency-formants[1])/320,2));
   const brightness={airy:.95,warm:.82,dark:.56,bright:1.35,soft:.7,powerful:1.3}[spec.tone]||1;
   c*=resonance*(h===1?1:brightness);
  }
  if(inst.family==='pad')c*=.42;
  sum+=Math.sin(p*h)*c;weight+=Math.abs(c);
 }
 if(weight)sum/=weight;
 const breath=inst.family==='vowel'&&spec.tone==='airy'?noise*.05:0;
 const tremolo=inst.family==='vowel'&&spec.style==='hypnotic'?.87+.13*Math.sin(TAU*1.6*t):1;
 const instability=inst.family==='reed'?noise*.011:0;
 const percussive=inst.family==='pluck'||inst.family==='keys'?
  Math.exp(-t*60)*noise*.025:0;
 const velocity=note.velocity/127;
 const decay=inst.family==='pluck'||inst.family==='keys'?Math.exp(-t*.7):1;
 const presence=inst.family==='vowel'?({airy:.87,warm:.96,dark:.9,bright:1,soft:.73,powerful:1.18}[spec.tone]||1):1;
 return (sum*.82+breath+instability+percussive)*env*velocity*decay*presence*tremolo;
}
async function render(score,{sampleRate=22050,onProgress=()=>{},shouldAbort=()=>false}={}){
 if(score?.schema!=='nexus.music.orchestra-score.v1'||![22050,44100].includes(sampleRate))fail('invalid-render-input');
 if(score.durationSeconds>120||score.notes.length>1800)fail('render-limit');
 const frames=Math.ceil((score.durationSeconds+.25)*sampleRate);
 if(frames*12>80*1024*1024)fail('render-memory-budget');
 const l=new Float32Array(frames),r=new Float32Array(frames);
 for(let j=0;j<score.notes.length;j++){
  if(shouldAbort())fail('render-cancelled');
  const n=score.notes[j],offset=Math.floor(n.startTick/TPQ*60/score.bpm*sampleRate),
   end=clamp(Math.floor((n.startTick+n.lengthTicks)/TPQ*60/score.bpm*sampleRate),0,frames);
  const length=(end-offset)/sampleRate,frequency=440*2**((n.pitch-69)/12);
  const power=.19,gl=power*Math.sqrt((1-n.pan)/2),gr=power*Math.sqrt((1+n.pan)/2);
  let phase=0,step=TAU*frequency/sampleRate;
  for(let k=offset;k<end;k++){
   const v=voiceSample(n,phase,(k-offset)/sampleRate,length,frequency,k-offset,sampleRate,score.spec);
   l[k]+=v*gl;r[k]+=v*gr;
   phase+=step;if(phase>TAU*2048)phase%=TAU;
  }
  if(j%12===0){onProgress(j/score.notes.length*.7);await new Promise(resolve=>setTimeout(resolve,0))}
 }
 let peak=0;
 for(let k=0;k<frames;k++){if(shouldAbort())fail('render-cancelled');peak=Math.max(peak,Math.abs(l[k]),Math.abs(r[k]))}
 const gain=peak>.88?.88/peak:1,buffer=new ArrayBuffer(44+4*frames),dv=new DataView(buffer);
 function tag(offset,s){for(let i=0;i<s.length;i++)dv.setUint8(offset+i,s.charCodeAt(i))}
 tag(0,'RIFF');dv.setUint32(4,36+4*frames,true);tag(8,'WAVE');tag(12,'fmt ');
 dv.setUint32(16,16,true);dv.setUint16(20,1,true);dv.setUint16(22,2,true);
 dv.setUint32(24,sampleRate,true);dv.setUint32(28,sampleRate*4,true);
 dv.setUint16(32,4,true);dv.setUint16(34,16,true);tag(36,'data');dv.setUint32(40,4*frames,true);
 for(let k=0;k<frames;k++){
  if(shouldAbort())fail('render-cancelled');
  const fade=Math.min(1,k/(sampleRate*.03),(frames-k)/(sampleRate*.25));
  dv.setInt16(44+4*k,Math.round(clamp(l[k]*gain*fade,-1,1)*32767),true);
  dv.setInt16(46+4*k,Math.round(clamp(r[k]*gain*fade,-1,1)*32767),true);
  if(k%262144===0){onProgress(.7+.3*k/frames);await new Promise(resolve=>setTimeout(resolve,0))}
 }
 onProgress(1);return new Uint8Array(buffer);
}
function inspectDryWav(raw){
 const b=raw instanceof Uint8Array?raw:new Uint8Array(raw);
 if(b.byteLength<48||b.byteLength>20*1024*1024)fail('invalid-own-vocal-wav-size');
 const d=new DataView(b.buffer,b.byteOffset,b.byteLength);
 const has=(o,s)=>[...s].every((c,i)=>d.getUint8(o+i)===c.charCodeAt(0));
 if(!has(0,'RIFF')||!has(8,'WAVE')||!has(12,'fmt ')||!has(36,'data')||
   d.getUint32(4,true)+8!==b.byteLength||d.getUint32(16,true)!==16||
   d.getUint16(20,true)!==1||![1,2].includes(d.getUint16(22,true))||
   d.getUint16(34,true)!==16||![22050,44100].includes(d.getUint32(24,true))||
   d.getUint32(40,true)+44!==b.byteLength)fail('unsupported-own-vocal-wav-format');
 const channels=d.getUint16(22,true),rate=d.getUint32(24,true),frames=d.getUint32(40,true)/(2*channels);
 if(!Number.isInteger(frames)||d.getUint32(28,true)!==rate*channels*2||
   d.getUint16(32,true)!==channels*2)fail('invalid-own-vocal-wav-frame');
 return Object.freeze({sampleRate:rate,channels,frames,
  durationSeconds:+(frames/rate).toFixed(3),
  original_bytes_preserved:true,transformed:false,recording_sent:false});
}
root.NexusOrchestra=Object.freeze({GM,TPQ,BAR,parsePrompt,validateSpec,compose,musicXML,midi,render,inspectDryWav,
 syntheticVoices:true,realAnimalRecordings:false,speechSynthesis:false,externalService:false});
})(typeof globalThis!=='undefined'?globalThis:this);
