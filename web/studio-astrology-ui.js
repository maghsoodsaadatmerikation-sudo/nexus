'use strict';
(function() {
const A=NexusAstrology;
let epoch=0,abort=null,prepared=null,draft=null,selectedProject=null,importTarget=null;
Object.assign(EN,{astroLocalNatal:'Calculate natal positions offline',astroLocalTransit:'Calculate transit offline',
 astroTitle:'Optional astrology & personal transits',
 astroHelp:'Read tropical, apparent geocentric positions for ten planets from On-line Astrology. Compare a selected transit instant with your natal positions. No houses, Ascendant, MC or sidereal calculations are included. Numerical positions and symbolic interpretations are different kinds of information.',
 astroBirth:'Birth instant: Gregorian ISO date/time with Z or an explicit historical UTC offset',
 astroKnown:'I know this birth time and have checked its UTC offset, including historical daylight saving time.',
 astroTransit:'Transit instant: Gregorian ISO date/time with an explicit UTC offset',astroNow:'Use current UTC instant',
 astroOrb:'Maximum major-aspect orb in degrees (0.25–5)',astroPrepareNatal:'Review natal-data request',astroPrepareTransit:'Review transit-data request',
 astroDisclosure:'Only the displayed instant and fixed planet codes are sent. No name, location, chat, memory or token is sent. The provider sees your IP and may log the requested instant. Retrieval is independent of permission to personalize answers.',
 astroNetworkConsent:'Send this exact request once to On-line Astrology.',astroFetch:'Fetch reviewed data',astroCancel:'Cancel request',
 astroSave:'Apply profile to this project',astroDelete:'Remove astrology profile',astroImportHelp:'Import a raw On-line Astrology API JSON response locally; imports remain marked user-supplied.',astroImportNatal:'Import natal JSON',astroImportTransit:'Import transit JSON',
 astroUse:'Include the applied profile in my next local guide / reviewed model request.',astroHistorical:'Explicitly use this selected past/future instant instead of requiring a transit within 24 hours of now.',
 astroPrivacy:'Off by default. Save the session explicitly for encrypted persistence. Removing a profile stops future use; earlier saved chats/backups may still contain it. Exact birth time is omitted from outgoing model context, but positions remain personal. Change/remove the applied profile before enabling personalization again.',
 astroWorking:'Retrieving the exact reviewed instant…',astroFailed:'No data changed. Check exact time/offset, known birth time, provider availability, file format and numerical limits.',astroRetrieved:'Data received locally. Inspect and apply the profile before using it in answers.',astroDraft:'Unapplied profile preview',astroApplied:'Applied project profile',astroMissing:'No applied astrology profile. Nothing is sent automatically.',astroStale:'The selected transit is outside 24 hours of now. Refresh it, or explicitly choose selected-time mode.',astroNoContacts:'No major contacts within this orb.'
});
Object.assign(FA,{astroLocalNatal:'محاسبهٔ آفلاین چارت تولد',astroLocalTransit:'محاسبهٔ آفلاین ترنزیت',
 astroTitle:'استرولوژی اختیاری و ترنزیت شخصی',
 astroHelp:'موقعیت تروپیکالِ ظاهری و زمین‌مرکزی ده جرم از On-line Astrology دریافت می‌شود و با چارت تولد مقایسه می‌شود. خانه‌ها، طالع، MC و محاسبات سیدریال در این نسخه نیستند. موقعیت عددی و تعبیر نمادین دو نوع اطلاعات متفاوت‌اند.',
 astroBirth:'لحظهٔ تولد: تاریخ میلادی و ساعت ISO با Z یا اختلاف تاریخی UTC',astroKnown:'ساعت تولد را می‌دانم و اختلاف UTC و ساعت تابستانیِ آن تاریخ را بررسی کرده‌ام.',
 astroTransit:'لحظهٔ ترنزیت: تاریخ و ساعت میلادی ISO با اختلاف UTC',astroNow:'استفاده از همین لحظه به UTC',astroOrb:'حداکثر اُرب جنبه‌های اصلی به درجه — ۰٫۲۵ تا ۵',astroPrepareNatal:'بازبینی درخواست چارت تولد',astroPrepareTransit:'بازبینی درخواست ترنزیت',
 astroDisclosure:'فقط لحظهٔ نمایش‌داده‌شده و کد ثابت سیاره‌ها ارسال می‌شوند؛ نام، مکان، گفتگو، حافظه و توکن ارسال نمی‌شوند. ارائه‌دهنده IP را می‌بیند و ممکن است زمان درخواستی را ثبت کند. دریافت داده با اجازهٔ شخصی‌سازی پاسخ جداست.',astroNetworkConsent:'این درخواست دقیق را یک بار به On-line Astrology بفرست.',astroFetch:'دریافت دادهٔ بازبینی‌شده',astroCancel:'لغو درخواست',astroSave:'اعمال پروفایل در همین پروژه',astroDelete:'حذف پروفایل استرولوژی',astroImportHelp:'ورود محلیِ پاسخ خام JSON از API سایت On-line Astrology؛ دادهٔ واردشده با برچسب کاربر باقی می‌ماند.',astroImportNatal:'ورود JSON چارت تولد',astroImportTransit:'ورود JSON ترنزیت',
 astroUse:'پروفایل اعمال‌شده را به راهنمای محلی یا درخواست بازبینی‌شدهٔ بعدی من اضافه کن.',astroHistorical:'این زمان انتخاب‌شدهٔ گذشته/آینده را صریحاً استفاده کن؛ الزام ترنزیت در فاصلهٔ ۲۴ ساعت از اکنون را بردار.',
 astroPrivacy:'پیش‌فرض خاموش است. برای نگهداری رمزگذاری‌شده، نشست را خودت ذخیره کن. حذف پروفایل استفادهٔ بعدی را متوقف می‌کند؛ گفتگوها و پشتیبان‌های قبلی ممکن است هنوز آن را داشته باشند. زمان دقیق تولد از متن ارسالی مدل حذف می‌شود، ولی موقعیت‌ها همچنان دادهٔ شخصی‌اند. پس از تغییر پروفایل، شخصی‌سازی را دوباره انتخاب کن.',
 astroWorking:'در حال دریافت همان لحظهٔ دقیق بازبینی‌شده…',astroFailed:'داده‌ای تغییر نکرد. ساعت و اختلاف UTC، تأیید ساعت تولد، دسترسی سرویس، قالب فایل و محدودیت عددی را بررسی کن.',astroRetrieved:'داده محلی دریافت شد؛ پیش از استفاده در پاسخ، آن را بررسی و پروفایل را اعمال کن.',astroDraft:'پیش‌نمایش پروفایل اعمال‌نشده',astroApplied:'پروفایل اعمال‌شدهٔ پروژه',astroMissing:'پروفایل استرولوژی اعمال نشده؛ چیزی خودکار ارسال نمی‌شود.',astroStale:'ترنزیت انتخاب‌شده بیش از ۲۴ ساعت با اکنون فاصله دارد؛ آن را تازه کن یا استفاده از زمان انتخاب‌شده را صریحاً فعال کن.',astroNoContacts:'در این اُرب، تماس اصلی پیدا نشد.'
});
function current(){return draft||p()?.astrology||null}
function cancel(){epoch++;abort?.abort();abort=null;prepared=null;$('astro-request').hidden=true;$('astro-request-url').textContent='';$('astro-network-consent').checked=false;$('astro-fetch').disabled=false}
function clear(){cancel();draft=null;selectedProject=null;importTarget=null;for(const id of ['astro-birth','astro-transit','astro-summary','astro-status']){if($(id).tagName==='INPUT')$(id).value='';else $(id).textContent=''}$('astro-orb').value='2';for(const id of ['astro-known','use-astrology','astro-historical'])$(id).checked=false}
function display(value){
 if(!value)return t('astroMissing');
 const v=A.profile(value),fa=language==='fa';
 const lines=[t(draft?'astroDraft':'astroApplied'),'tropical · apparent geocentric ecliptic of date','Natal: '+v.natal.provider+' · '+v.natal.at+' · '+v.natal.acquisition+' · retrieved '+v.natal.retrievedAt];
 for(const point of v.natal.positions)lines.push(A.name(point.body,fa)+': '+A.placement(point.longitude));
 if(v.transit){lines.push('\nTransit: '+v.transit.provider+' · '+v.transit.at+' · '+v.transit.acquisition+' · retrieved '+v.transit.retrievedAt);for(const point of v.transit.positions)lines.push(A.name(point.body,fa)+': '+A.placement(point.longitude)+' · '+point.speed.toFixed(6)+'°/day · '+(point.speed<0?'R':'D'));const all=A.contacts(v);lines.push('\nMajor contacts · orb ≤ '+v.orb+'° · '+all.length);for(const c of all)lines.push(A.name(c.transit,fa)+' → '+A.name(c.natal,fa)+' · '+c.aspect+' · '+c.orb.toFixed(4)+'° · '+c.phase);if(!all.length)lines.push(t('astroNoContacts'));if(Math.abs(Date.now()-Date.parse(v.transit.at))>86400000)lines.push(t('astroStale'))}
 return lines.join('\n');
}
function render(){
 if(selectedProject!==projectId){draft=null;selectedProject=projectId;const v=p()?.astrology;$('astro-birth').value=v?.natal.at||'';$('astro-transit').value=v?.transit?.at||'';$('astro-known').checked=!!v;$('astro-orb').value=String(v?.orb||2);$('use-astrology').checked=false;$('astro-historical').checked=false}
 $('astro-summary').textContent=display(current());
 for(const id of ['astro-prepare-natal','astro-prepare-transit','astro-local-natal','astro-local-transit','astro-save','astro-import-natal','astro-import-transit'])$(id).disabled=!p()||busy;
 $('astro-delete').disabled=!p()?.astrology||busy;
 $('use-astrology').disabled=!p()?.astrology?.transit;
}
function changed(){stop();$('use-astrology').checked=false;$('astro-status').textContent=''}
for(const id of ['astro-birth','astro-transit','astro-orb','astro-known'])for(const event of ['input','change'])$(id).addEventListener(event,changed);
$('astro-now').onclick=()=>{$('astro-transit').value=new Date().toISOString().replace(/\.\d{3}Z$/,'Z');changed()};
function prepare(kind){
 if(!p()||busy)return;
 try {
  stop();const at=A.instant($(kind==='natal'?'astro-birth':'astro-transit').value.trim());
  if(kind==='natal'&&!$('astro-known').checked)throw Error('known-time');
  if(kind==='transit'&&(!current()?.natal||Date.parse(at)<Date.parse(current().natal.at)))throw Error('natal-required');
  prepared={kind,at,project:projectId,epoch};$('astro-request-url').textContent=A.request(at);$('astro-request').hidden=false;$('astro-status').textContent='';
 }catch{$('astro-status').textContent=t('astroFailed')}
}
for(const kind of ['natal','transit'])$('astro-local-'+kind).onclick=()=>{if(!p()||busy)return;try{stop();if(kind==='natal'&&!$('astro-known').checked)throw Error('known-time');const at=A.instant($(kind==='natal'?'astro-birth':'astro-transit').value.trim());accept(kind,NexusSky.snapshot(at))}catch{$('astro-status').textContent=t('astroFailed')}};
$('astro-prepare-natal').onclick=()=>prepare('natal');$('astro-prepare-transit').onclick=()=>prepare('transit');
function accept(kind,value){const old=current();draft=A.profile({schema:'nexus.astrology.v1',orb:Number($('astro-orb').value),natal:kind==='natal'?value:old?.natal,transit:kind==='natal'?null:value});$('use-astrology').checked=false;render();$('astro-status').textContent=t('astroRetrieved')}
$('astro-fetch').onclick=async()=>{
 if(!prepared||!$('astro-network-consent').checked||abort||busy)return;
 const task=prepared,scope=epoch,controller=new AbortController();abort=controller;$('astro-network-consent').checked=false;$('astro-fetch').disabled=true;$('astro-status').textContent=t('astroWorking');const timer=setTimeout(()=>controller.abort(),20000);
 try{const value=await A.fetchSnapshot(task.at,{signal:controller.signal});if(scope===epoch&&task.project===projectId)accept(task.kind,value)}catch{if(scope===epoch)$('astro-status').textContent=t('astroFailed')}finally{clearTimeout(timer);if(scope===epoch){cancel()}}
};
$('astro-cancel').onclick=()=>{cancel();$('astro-status').textContent=''};
$('astro-save').onclick=()=>{
 if(!p()||busy)return;
 try{const value=A.profile({...current(),orb:Number($('astro-orb').value)});if(!$('astro-known').checked||A.instant($('astro-birth').value.trim())!==value.natal.at)throw Error('birth-draft');if(value.transit&&A.instant($('astro-transit').value.trim())!==value.transit.at)throw Error('transit-draft');if(mutate(v=>projectIn(v).astrology=value)){draft=null;$('use-astrology').checked=false;render()}}catch{$('astro-status').textContent=t('astroFailed')}
};
$('astro-delete').onclick=()=>{if(!p()?.astrology||!confirm(t('discard')))return;clear();mutate(v=>{delete projectIn(v).astrology});render()};
for(const kind of ['natal','transit'])$('astro-import-'+kind).onclick=()=>{if(!p()||busy)return;importTarget={kind,project:projectId,epoch};$('astro-import-file').click()};
$('astro-import-file').onchange=async event=>{
 const file=event.target.files[0],task=importTarget;event.target.value='';importTarget=null;
 if(!file||!task||!p()||busy)return;
 try{if(file.size>128000)throw Error('file-size');if(task.kind==='natal'&&!$('astro-known').checked)throw Error('known-time');const at=A.instant($(task.kind==='natal'?'astro-birth':'astro-transit').value.trim());const body=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer()));if(task.epoch!==epoch||task.project!==projectId)return;const value=A.parse(body,at,'import');accept(task.kind,value);stop()}catch{if(task.epoch===epoch&&task.project===projectId)$('astro-status').textContent=t('astroFailed')}
};
window.NexusAstrologyUI=Object.freeze({cancel,clear,render,hasDraft:()=>draft!==null});applyLanguage();
})();
