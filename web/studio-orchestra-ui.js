/* NEXUS Orchestra Lab UI — local, inspectable, and consent-based.
 * Original dry vocal import is never transmitted, retuned, cloned or saved
 * in project memory or offline application cache. No microphone access.
 */
(()=>{'use strict';
const O=globalThis.NexusOrchestra,$=id=>document.getElementById(id);
if(!O||!$('orchestra-card'))return;
const fa=()=>document.documentElement.lang==='fa';
const say=(en,faText)=>fa()?faText:en;
let plan=null,score=null,wav=null,rendering=false,ticket=0;
let wavUrl=null,dryUrl=null,dryBytes=null,dryInfo=null;
function status(en,faText){$('orchestra-status').textContent=say(en,faText)}
function buttons(){
 $('orchestra-compose').disabled=rendering||!plan?.ready;
 $('orchestra-render').disabled=rendering||!score;
 $('orchestra-xml').disabled=rendering||!score;
 $('orchestra-midi').disabled=rendering||!score;
 $('orchestra-score').disabled=rendering||!score;
 $('orchestra-wav').disabled=rendering||!wav;
 $('orchestra-cancel').disabled=!rendering;
 $('orchestra-dry-file').disabled=rendering;
 $('orchestra-dry-download').disabled=!dryBytes;
 $('orchestra-together').disabled=!wav||!dryBytes||rendering;
}
function clearWav(){
 if(wavUrl)URL.revokeObjectURL(wavUrl);
 wavUrl=null;wav=null;
 const audio=$('orchestra-play');audio.pause();audio.removeAttribute('src');audio.load();
 $('orchestra-progress').value=0;buttons();
}
function invalidate(){
 ticket++;rendering=false;plan=null;score=null;clearWav();
 $('orchestra-report').textContent='';
 buttons();
}
function download(data,extension,type){
 const title='nexus-orchestra-'+extension,blob=new Blob([data],{type});
 const url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download=title;a.hidden=true;document.body.append(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function fail(error){
 status('Could not complete the local operation. Check the score and format.',
       'عملیات آفلاین انجام نشد؛ پارتیتور و قالب فایل را بررسی کن.');
}
$('orchestra-prompt').addEventListener('input',invalidate);
$('orchestra-parse').addEventListener('click',()=>{
 invalidate();
 try{
  plan=O.parsePrompt($('orchestra-prompt').value);
  const p=plan.spec;
  $('orchestra-report').textContent=[
   say('Recognized prompt instructions','دستورهای شناسایی‌شده')+': '+(plan.understood.join(', ')||'none'),
   'Style: '+p.style+' | Register: '+p.register+' | Tone: '+p.tone,
   'Instruments: '+p.instruments.join(', '),
   'Choir: '+p.choir+' | Generic vowel voice: '+p.voice,
   'Animal-inspired effect: '+p.animal+' | FX: '+p.fx,
   'Tempo: '+p.bpm+' BPM | Bars: '+p.bars+' | Mode: '+p.mode,
   'Unparsed: '+(plan.unparsed.join(', ')||'none'),
   'Warnings: '+(plan.warnings.join(', ')||'none'),
   'Parser: strict limited grammar, not understanding arbitrary prose.',
   'No human voice imitation, intelligible rap lyrics or actual animal recordings.'
  ].join('\n');
  if(plan.ready)status('Plan ready; review before composing.','طرح آماده است؛ پیش از ساخت آن را بازبینی کن.');
  else status('Unrecognized or conflicting instructions. Edit the prompt to continue.',
              'برخی دستورها شناخته نشده یا متناقض‌اند؛ پرامپت را اصلاح کن.');
 }catch{fail()}
 buttons();
});
$('orchestra-compose').addEventListener('click',()=>{
 if(rendering||!plan?.ready)return;
 try{
  score=O.compose(plan.spec,61234);
  clearWav();
  $('orchestra-report').textContent+='\n'+say('Original score created','پارتیتور مستقل ساخته شد')+
    ': '+score.notes.length+' notes; '+score.parts.length+' parts; '+score.durationSeconds+' sec';
  status('Score ready. MusicXML, MIDI and local WAV are available.',
         'پارتیتور آماده است؛ خروجی نت MusicXML، MIDI و WAV در دسترس است.');
 }catch{score=null;clearWav();fail()}
 buttons();
});
$('orchestra-xml').addEventListener('click',()=>{
 if(score&&!rendering)try{download(O.musicXML(score),'score.musicxml','application/vnd.recordare.musicxml+xml')}catch{fail()}
});
$('orchestra-midi').addEventListener('click',()=>{
 if(score&&!rendering)try{download(O.midi(score),'score.mid','audio/midi')}catch{fail()}
});
$('orchestra-score').addEventListener('click',()=>{
 if(score&&!rendering)download(JSON.stringify(score,null,2),'score.json','application/json');
});
$('orchestra-wav').addEventListener('click',()=>{
 if(wav&&!rendering)download(wav,'backing.wav','audio/wav');
});
$('orchestra-render').addEventListener('click',async()=>{
 if(!score||rendering)return;
 const id=++ticket,source=score;
 rendering=true;clearWav();buttons();
 status('Synthesizing the original score on this device...',
        'در حال تولید صدای مستقل و آفلاین روی همین دستگاه...');
 try{
  const data=await O.render(source,{sampleRate:22050,shouldAbort:()=>id!==ticket,
   onProgress:x=>{if(id===ticket)$('orchestra-progress').value=Math.round(x*100)}});
  if(id!==ticket)return;
  wav=data;
  wavUrl=URL.createObjectURL(new Blob([data],{type:'audio/wav'}));
  $('orchestra-play').src=wavUrl;
  status('Synthetic audio ready; listen before judging quality.',
        'صدای سنتزی آماده است؛ پیش از داوری دربارهٔ کیفیت آن را گوش کن.');
 }catch(e){if(id===ticket)status(e?.message==='render-cancelled'?'Cancelled.':'Render failed.',
     e?.message==='render-cancelled'?'لغو شد.':'ساخت صدا ناموفق بود.')}
 finally{if(id===ticket){rendering=false;buttons()}}
});
$('orchestra-cancel').addEventListener('click',()=>{
 if(!rendering)return;
 ticket++;rendering=false;clearWav();
 status('Rendering cancelled; your score remains.','ساخت صدا لغو شد؛ پارتیتور محفوظ است.');
 buttons();
});
function clearDry(){
 $('orchestra-play').pause();$('orchestra-dry-play').pause();
 if(dryUrl)URL.revokeObjectURL(dryUrl);dryUrl=null;dryBytes=null;dryInfo=null;
 $('orchestra-dry-play').removeAttribute('src');$('orchestra-dry-play').load();
 $('orchestra-dry-report').textContent='';$('orchestra-dry-file').value='';
 buttons();
}
$('orchestra-dry-clear').addEventListener('click',()=>{
 clearDry();status('Local original vocal released from the tab.',
                  'وکال اصلی از حافظهٔ این برگه آزاد شد.');
});
$('orchestra-dry-file').addEventListener('change',async()=>{
 if(rendering)return;
 const file=$('orchestra-dry-file').files[0];clearDry();
 if(!file)return;
 const id=++ticket;
 try{
  if(file.size>20*1024*1024||file.size<48)throw Error('file-size');
  const bytes=new Uint8Array(await file.arrayBuffer());
  if(id!==ticket)return;
  const result=O.inspectDryWav(bytes);
  if(!globalThis.crypto?.subtle)throw Error('browser-crypto-unavailable');
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),
    n=>n.toString(16).padStart(2,'0')).join('');
  if(id!==ticket)return;
  dryBytes=bytes;dryInfo=result;
  dryUrl=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));
  $('orchestra-dry-play').src=dryUrl;
  $('orchestra-dry-play').playbackRate=1;
  $('orchestra-dry-report').textContent=[
   'Original WAV SHA-256: '+digest,
   'PCM: '+result.sampleRate+' Hz, '+result.channels+' channel(s)',
   'Duration: '+result.durationSeconds+' s',
   'Dry bytes are unchanged and downloadable bit for bit.',
   'No pitch shifting, formant conversion, tempo stretch, voice cloning or network upload.',
   'The synthetic backing track is separate: simultaneous playback is approximate, not sample-accurate alignment.'
  ].join('\n');
  status('Your original vocal was loaded locally, byte-for-byte.',
         'وکال اصلی بدون هیچ دستکاری در همین دستگاه بارگذاری شد.');
 }catch{status('Dry vocal rejected: use a local PCM 16-bit WAV (22.05/44.1 kHz; 20 MiB max).',
     'فایل وکال پذیرفته نشد؛ WAV خام ۱۶ بیتی با نرخ ۲۲ یا ۴۴ کیلوهرتز، حداکثر ۲۰ مگابایت لازم است.')}
 buttons();
});
$('orchestra-dry-download').addEventListener('click',()=>{
 if(dryBytes)download(dryBytes,'original-voice-unchanged.wav','audio/wav');
});
$('orchestra-together').addEventListener('click',async()=>{
 if(!wav||!dryBytes||rendering)return;
 const backing=$('orchestra-play'),original=$('orchestra-dry-play');
 backing.pause();original.pause();backing.currentTime=0;original.currentTime=0;
 backing.playbackRate=1;original.playbackRate=1;
 try{
  await Promise.all([backing.play(),original.play()]);
  status('Playing original vocal and synthesized backing at normal speed. Timing is approximate.',
   'وکال اصلی و موسیقی همراه با سرعت طبیعی پخش می‌شوند؛ همگام‌سازی تقریبی است.');
 }catch{fail()}
});
window.addEventListener('pagehide',()=>{ticket++;clearWav();clearDry()});
window.NexusOrchestraUI=Object.freeze({
 hasScore:()=>Boolean(score),hasWav:()=>Boolean(wav),
 hasOriginalVocal:()=>Boolean(dryBytes),clear:()=>{invalidate();clearDry()}
});
status('Enter a supported prompt and preview the parsed plan.',
  'دستور موسیقی را بنویس و طرح شناسایی‌شده را بازبینی کن.');
buttons();
})();
