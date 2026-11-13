/* NEXUS opt-in astrology: numerical source data and symbolic interpretation stay separate. */
(function(root) {
'use strict';
const PROVIDER='on-line-astrology';
const HOME='https://app.on-lineastrology.com/api/';
const CODES=['So','Mo','Me','Ve','Ma','Ju','Sa','Ur','Ne','Pl'];
const NAMES=['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto'];
const FA=['خورشید','ماه','عطارد','زهره','مریخ','مشتری','زحل','اورانوس','نپتون','پلوتو'];
const SIGNS=['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'];
const ASPECTS=[['conjunction',0],['sextile',60],['square',90],['trine',120],['opposition',180]];
const fail=code=>{throw Error(code)};
function instant(value) {
 if(typeof value!=='string')fail('explicit-timezone-required');
 const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
 if(!m)fail('explicit-timezone-required');
 const [year,month,day,hour,minute,second]=m.slice(1,7).map(x=>Number(x||0));
 const days=new Date(Date.UTC(year,month,0)).getUTCDate();
 if(year<1900||year>2050||month<1||month>12||day<1||day>days||hour>23||minute>59||second>59)fail('instant-range');
 if(m[7]!=='Z'){const [h,n]=m[7].slice(1).split(':').map(Number);if(h>14||n>59||(h===14&&n!==0))fail('utc-offset')}
 const date=new Date(value);if(!Number.isFinite(date.getTime())||date.getUTCFullYear()<1900||date.getUTCFullYear()>2050)fail('instant-range');
 return date.toISOString().replace('.000Z','Z');
}
function request(at) {
 const url=new URL('positions.php',HOME);
 url.search=new URLSearchParams({dt:instant(at),bodies:CODES.join(',')});
 return url.href;
}
function positions(items) {
 if(!Array.isArray(items)||items.length!==10)fail('ten-planets-required');
 const seen=new Set();
 const clean=items.map(p=>{
  if(!p||!CODES.includes(p.body)||seen.has(p.body)||typeof p.longitude!=='number'||!Number.isFinite(p.longitude)||p.longitude<0||p.longitude>=360||typeof p.speed!=='number'||!Number.isFinite(p.speed)||Math.abs(p.speed)>100)fail('invalid-position');
  seen.add(p.body);return {body:p.body,longitude:p.longitude,speed:p.speed};
 });
 return CODES.map(body=>clean.find(p=>p.body===body));
}
function snapshot(v) {
 if(!v||v.zodiac!=='tropical'||!((v.provider===PROVIDER&&['live','import'].includes(v.acquisition))||(v.provider==='astronomy-engine-2.1.19'&&v.acquisition==='computed')))fail('snapshot-convention');
 return {provider:v.provider,zodiac:'tropical',at:instant(v.at),retrievedAt:instant(v.retrievedAt),acquisition:v.acquisition,positions:positions(v.positions)};
}
function parse(body,expectedAt,acquisition='live',retrievedAt=new Date().toISOString().replace(/\.\d{3}Z$/,'Z')) {
 const at=instant(expectedAt);
 const coord=body?.record?.coordinate_system;
 if(body?.ok!==true||body?.zodiac?.type!=='tropical'||coord?.frame!=='geocentric'||coord?.zodiac!=='tropical'||coord?.coordinates!=='ecliptic'||coord?.longitude_unit!=='degrees'||coord?.position_type!=='apparent'||instant(body?.input?.datetime_utc)!==at||instant(body?.record?.time_utc)!==at)fail('provider-convention-or-instant');
 const map=body.record.bodies;
 if(!map||typeof map!=='object'||Array.isArray(map))fail('provider-shape');
 return snapshot({provider:PROVIDER,zodiac:'tropical',at,retrievedAt,acquisition,positions:CODES.map(code=>({body:code,longitude:map[code]?.longitude,speed:map[code]?.speed_longitude}))});
}
async function fetchSnapshot(at,{signal,fetcher=root.fetch}={}) {
 const requested=instant(at);
 const response=await fetcher(request(requested),{method:'GET',mode:'cors',credentials:'omit',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',signal});
 if(!response.ok||!response.body)fail('provider-unavailable');
 const reader=response.body.getReader(),chunks=[];let count=0;
 try {
  while(true){const {done,value}=await reader.read();if(done)break;count+=value.length;if(count>128000)fail('provider-size');chunks.push(value)}
  const bytes=new Uint8Array(count);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length}
  return parse(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes)),requested);
 } finally {await reader.cancel().catch(()=>{})}
}
function profile(v) {
 if(!v||v.schema!=='nexus.astrology.v1'||typeof v.orb!=='number'||!Number.isFinite(v.orb)||v.orb<.25||v.orb>5)fail('profile');
 const natal=snapshot(v.natal),transit=v.transit===null?null:snapshot(v.transit);
 if(transit&&Date.parse(transit.at)<Date.parse(natal.at))fail('transit-before-birth');
 return {schema:'nexus.astrology.v1',orb:v.orb,natal,transit};
}
const norm=x=>((x%360)+360)%360;
const separation=(a,b)=>Math.min(norm(a-b),norm(b-a));
function contacts(value) {
 const v=profile(value);if(!v.transit)fail('transit-required');
 const out=[];
 for(const moving of v.transit.positions)for(const natal of v.natal.positions)for(const [aspect,angle] of ASPECTS){
  const distance=separation(moving.longitude,natal.longitude),orb=Math.abs(distance-angle);
  if(orb>v.orb+1e-10)continue;
  const signed=norm(moving.longitude-natal.longitude+180)-180;
  const derivative=Math.sign(signed)*moving.speed;
  const phase=orb<1e-7?'exact-at-snapshot':Math.abs(derivative)<1e-8?'stationary-or-ambiguous':(distance-angle)*derivative<0?'applying':'separating';
  out.push({transit:moving.body,natal:natal.body,aspect,angle,separation:distance,orb,phase});
 }
 return out.sort((a,b)=>a.orb-b.orb||CODES.indexOf(a.transit)-CODES.indexOf(b.transit)||CODES.indexOf(a.natal)-CODES.indexOf(b.natal));
}
function context(value,{historical=false,now=Date.now()}={}) {
 if(typeof historical!=='boolean'||typeof now!=='number'||!Number.isFinite(now))fail('context-options');
 const v=profile(value);if(!v.transit)fail('transit-required');
 if(!historical&&Math.abs(now-Date.parse(v.transit.at))>86400000)fail('refresh-transit-or-review-selected-time');
 const all=contacts(v);
 return {kind:'optional-symbolic-astrology',convention:'apparent geocentric tropical ecliptic longitude of date',provider:v.natal.provider===PROVIDER&&v.transit.provider===PROVIDER?HOME:'local-or-mixed-ephemeris',sources:{natal:v.natal.provider,transit:v.transit.provider},transit_at:v.transit.at,selected_time_mode:historical===true,natal_acquisition:v.natal.acquisition,transit_acquisition:v.transit.acquisition,orb_limit_degrees:v.orb,natal_positions:v.natal.positions,transit_positions:v.transit.positions,contacts:all.slice(0,20),omitted_contacts:Math.max(0,all.length-20),limits:'No houses, Ascendant, MC, sidereal conversion, exact future-event times or causal/diagnostic claims. Imported data are user-supplied, not independently verified. Interpretations are optional symbolic reflection. Answer the actual question; separate numerical source statements, interpretation, uncertainty and values. Do not infer health diagnoses or replace evidence-based decisions. Birth instant, name and location are omitted; positions are still personal data.'};
}
function name(code,fa=false){return (fa?FA:NAMES)[CODES.indexOf(code)]||code}
function placement(longitude){return SIGNS[Math.floor(longitude/30)]+' '+(longitude%30).toFixed(4)+'°'}
function reflection(value,fa=false,options={}) {
 const ctx=context(value,options),list=ctx.contacts.slice(0,3);
 const topics=fa?['بیان خود و جهت‌گیری','احساس و نیاز به امنیت','گفتگو و یادگیری','ارزش‌ها و رابطه','انرژی و مرزبندی','رشد و گسترش','تعهد و محدودیت','تغییر و استقلال','تخیل و ابهام','دگرگونی و قدرت']:['self-expression and direction','feelings and security','communication and learning','values and relationships','energy and boundaries','growth and expansion','commitment and limits','change and independence','imagination and ambiguity','transformation and power'];
 const aspectNames=fa?{conjunction:'مقارنه',sextile:'تسدیس',square:'تربیع',trine:'تثلیث',opposition:'مقابله'}:Object.fromEntries(ASPECTS.map(([x])=>[x,x]));
 const header=fa?'بازتاب شخصی‌سازی‌شدهٔ محلی — تعبیر نمادین، نه پاسخ مدل مولد یا پیش‌بینی قطعی. زمان ترنزیت: ':'Personalized local reflection — symbolic interpretation, not a generative-model answer or a certain prediction. Transit instant: ';
 if(!list.length)return header+ctx.transit_at+(fa?'\nدر اُرب انتخاب‌شده تماس اصلی پیدا نشد؛ این به معنای نبودن رویداد نیست.':'\nNo major contact falls inside the selected orb; this does not imply that nothing will happen.');
 return header+ctx.transit_at+'\n'+list.map(c=>{
  const label=name(c.transit,fa)+' '+aspectNames[c.aspect]+' '+name(c.natal,fa)+' · '+c.orb.toFixed(4)+'° · '+c.phase;
  const topic=topics[CODES.indexOf(c.natal)],moving=topics[CODES.indexOf(c.transit)];
  const themes=fa?{conjunction:'هم‌پوشانی دو موضوع',sextile:'فرصت کوچک برای همکاری',square:'کشمکش و بازبینی اولویت‌ها',trine:'منابع و حمایتِ در دسترس',opposition:'دیدن دو نیاز و ایجاد تعادل'}:{conjunction:'the overlap of two themes',sextile:'a small opening for cooperation',square:'tension and reviewing priorities',trine:'available resources and support',opposition:'holding two needs and seeking balance'};
  return label+'\n'+(fa?'معنای نمادین جنبه: '+themes[c.aspect]+'\n':'Symbolic aspect theme: '+themes[c.aspect]+'\n')+(fa?'برداشت نمادین: موضوع «'+moving+'» را کنار «'+topic+'» بررسی کن. در موقعیت فعلی چه مشاهدهٔ مستقیمی داری و کدام اقدام کوچک با ارزش‌هایت سازگار است؟':'Symbolic prompt: consider “'+moving+'” alongside “'+topic+'”. What do you directly observe in your situation, and which small action fits your values?');
 }).join('\n\n');
}
root.NexusAstrology=Object.freeze({PROVIDER,HOME,CODES:Object.freeze(CODES),instant,request,positions,snapshot,parse,fetchSnapshot,profile,contacts,context,reflection,name,placement,separation});
})(globalThis);
