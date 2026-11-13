/* Offline ephemeris and a bounded editorial tone heuristic, not a causal model. */
(function(root){'use strict';
const VERSION='astronomy-engine-2.1.19';
const NAMES=['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto'];
const norm=x=>((x%360)+360)%360;
const signed=x=>norm(x+180)-180;
let cached=null;
function snapshot(at){
 const A=root.NexusAstrology,E=root.Astronomy;
 if(!E?.GeoVector||!E?.Ecliptic)throw Error('offline-ephemeris-unavailable');
 const canonical=A.instant(at),date=new Date(canonical),halfHour=1800000;
 const longitude=(name,time)=>norm(E.Ecliptic(E.GeoVector(name,time,true)).elon);
 const positions=NAMES.map((name,i)=>({body:A.CODES[i],longitude:longitude(name,date),speed:signed(longitude(name,new Date(+date+halfHour))-longitude(name,new Date(+date-halfHour)))*24}));
 return A.snapshot({provider:VERSION,zodiac:'tropical',at:canonical,retrievedAt:new Date().toISOString().replace(/\.\d{3}Z$/,'Z'),acquisition:'computed',positions});
}
function current(now=Date.now()){
 if(typeof now!=='number'||!Number.isFinite(now))throw Error('invalid-clock');
 const at=new Date(Math.floor(now/300000)*300000).toISOString().replace('.000Z','Z');
 if(cached?.at===at)return structuredClone(cached);
 cached=snapshot(at);return structuredClone(cached);
}
function style(value){
 const sky=root.NexusAstrology.snapshot(value),p=Object.fromEntries(sky.positions.map(x=>[x.body,x]));
 const distance=root.NexusAstrology.separation;
 const hard=(a,b)=>[0,90,180].some(angle=>Math.abs(distance(p[a].longitude,p[b].longitude)-angle)<=3);
 const soft=(a,b)=>[0,60,120].some(angle=>Math.abs(distance(p[a].longitude,p[b].longitude)-angle)<=3);
 // These fixed editorial associations are configurable presentation choices,
 // not inferred moods, personality, risk, truth, or advice about the user.
 const element=Math.floor(p.Mo.longitude/30)%4;
 let mode=['encouraging','practical','clear','warm'][element];
 if(hard('Ma','Sa')||hard('Mo','Sa'))mode='calm';
 else if(soft('Ve','Ju'))mode='warm';
 const phrasing={calm:'Use an even, patient tone and manageable short steps.',warm:'Use restrained warmth and considerate wording.',practical:'Use concrete wording and clear, small steps.',clear:'Use plain, organized sentences and concise transitions.',encouraging:'Use measured encouragement and active, accessible wording.'};
 return {mode,phrasing:phrasing[mode],clarity:p.Me.speed<0?'Prefer precise wording; recap an ambiguous detail when useful.':'Keep transitions straightforward.'};
}
function presentation({enabled=true,now=Date.now()}={}){
 if(typeof enabled!=='boolean')throw Error('invalid-tone-setting');
 if(!enabled)return {mode:'neutral',at:null,engine:null,instruction:null};
 try{const sky=current(now),s=style(sky);return {...s,at:sky.at,engine:VERSION,instruction:'Presentation preference only: '+s.phrasing+' '+s.clarity+' Follow the user’s explicit tone, language and format preferences first. Preserve the answer’s facts, meaning, uncertainty, evidence and recommendations. Do not infer anyone’s mood, health, identity, intentions or fate. Do not add a source explanation for this presentation choice unless asked. Be candid about how the style is selected if asked.'}}
 catch{return {mode:'neutral',at:null,engine:null,instruction:null}}
}
function opening(mode,fa=false){
 const en={calm:'We can take this one step at a time.',warm:'Let’s make room for what matters to you.',practical:'Let’s break this into clear, workable steps.',clear:'Let’s separate the key points.',encouraging:'Let’s start with one useful step.'};
 const local={calm:'می‌توانیم آرام و گام‌به‌گام پیش برویم.',warm:'بیاییم برای آنچه برایت مهم است جا باز کنیم.',practical:'بیاییم موضوع را به چند گام روشن و عملی تقسیم کنیم.',clear:'بیاییم نکته‌های اصلی را از هم جدا کنیم.',encouraging:'بیاییم از یک گام مفید شروع کنیم.'};
 return (fa?local:en)[mode]||'';
}
root.NexusSky=Object.freeze({VERSION,snapshot,current,style,presentation,opening});
})(globalThis);
