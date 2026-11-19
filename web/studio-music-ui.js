/* NEXUS Music Lab: offline mobile-first user-controlled composition tools. */
(()=>{'use strict';
const $=id=>document.getElementById(id),Music=globalThis.NexusMusic;
if(!Music||!$('music-card'))return;
const labels={
en:{ready:'Compose a score first.',built:'Original instrumental score ready. No network was used.',
 rendering:'Rendering local stereo WAV',cancelled:'Rendering cancelled.',
 exported:'Downloaded locally. No upload performed.',
 error:'Music Lab could not complete the request.',noAudio:'No rendered WAV yet.',
 browser:'Audio preview may require a browser with WAV support.',
 variation:'Variation prepared. Review and compose again.',keep:'Retained your current motif seed.',
 self:'Structure and measured PCM checks are objective, not proof of acoustic realism or aesthetic quality.',
 resource:'This sample-rate and song-length combination exceeds the offline phone memory budget. Try 22.05 kHz or fewer bars.'},
fa:{ready:'ابتدا قطعه را آهنگ‌سازی کن.',built:'پارتیتور بی‌کلام ساخته شد؛ هیچ اتصالی به اینترنت انجام نشد.',
 rendering:'در حال ساخت فایل WAV استریو در همین دستگاه',
 cancelled:'ساخت موسیقی لغو شد.',exported:'خروجی روی دستگاه ذخیره شد؛ فایلی ارسال نشد.',
 error:'موتور موسیقی نتوانست درخواست را کامل کند.',noAudio:'هنوز WAV ساخته نشده است.',
 browser:'ممکن است پیش‌شنیدن WAV در این مرورگر پشتیبانی نشود.',
 variation:'نسخهٔ متفاوت آماده شد؛ تنظیمات را بررسی و دوباره آهنگ‌سازی کن.',
 keep:'موتیف نسخهٔ پیشین محفوظ ماند.',
 self:'خودنقدی ساختار و سطح سیگنال را می‌سنجد؛ نه اصالت ساز یا زیبایی موسیقی.',
 resource:'این ترکیب طول قطعه و کیفیت صدا از بودجهٔ حافظهٔ گوشی فراتر می‌رود. کیفیت ۲۲ کیلوهرتز یا میزان کمتر را انتخاب کن.'}
};
const fa=()=>document.documentElement.lang==='fa',txt=k=>labels[fa()?'fa':'en'][k];
let score=null,wav=null,revision=0,working=false,objectUrl=null;
function out(status){$('music-status').textContent=status}
function field(name){const node=$('music-'+name);return node.type==='checkbox'?node.checked:node.type==='number'?Number(node.value):node.value}
function inputs(){return {
 title:field('title'),mode:field('mode'),key:field('key'),bpm:field('bpm'),
 bars:Number(field('bars')),lead:field('lead'),story:field('story'),solo:field('solo'),
 santurSolo:field('santur-solo'),guitarSolo:field('guitar-solo'),daf:field('daf'),
 seed:field('seed'),motifSeed:field('motif-seed')
}}
function buttons(){
 $('music-build').disabled=working;$('music-variation').disabled=working;
 $('music-render').disabled=working||!score;$('music-midi').disabled=working||!score;
 $('music-score').disabled=working||!score;$('music-wav').disabled=working||!wav;
 $('music-cancel').disabled=!working;
}
function resetAudio(){
 if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;
 const audio=$('music-preview');audio.pause();audio.removeAttribute('src');audio.load();
 wav=null;$('music-progress').value=0;buttons()
}
function invalidate(){
 revision++;working=false;score=null;resetAudio();$('music-report').textContent='';out(txt('ready'));
}
for(const node of $('music-card').querySelectorAll('select,input')){
 if(['music-quality','music-sound','music-problem','music-lock-motif'].includes(node.id))continue;
 node.addEventListener('change',invalidate);
}
function outputSettingsChanged(){
 revision++;working=false;resetAudio();summary();out(txt('ready'));
}
$('music-quality').addEventListener('change',outputSettingsChanged);
$('music-sound').addEventListener('change',outputSettingsChanged);
function cleanFilename(){return ($('music-title').value.replace(/[^A-Za-z0-9 _-]/g,'').trim()||'nexus-composition').slice(0,56).replace(/\s+/g,'-')}
function download(data,name,type){
 const blob=new Blob([data],{type});
 const url=URL.createObjectURL(blob),a=document.createElement('a');
 a.href=url;a.download=cleanFilename()+'.'+name;a.hidden=true;document.body.append(a);a.click();a.remove();
 setTimeout(()=>URL.revokeObjectURL(url),1000);
 out(txt('exported'));
}
function summary(){
 if(!score)return;
 const energy=score.sections.map(s=>(s.name+': '+s.energy.toFixed(2)+' · '+s.bars+' bars')).join('\n');
 const r=score.review,inst=Object.entries(r.instruments).filter(([,count])=>count).map(([key,count])=>key+': '+count).join(' | ');
 const text=[
  fa()?'مهندسی فرم و خودنقدی عینی':'Form engineering & objective self-check',
  (fa()?'مدت زمان نظری: ':'Planned duration: ')+(score.durationSeconds/60).toFixed(2)+' min',
  'Motif degrees: '+score.motif.join(', '),
  'Intentional breaths: '+r.motif_breath_bars.join(', '),
  'Main solo: '+r.solo_lead,'---',energy,'---',inst,'---',
  'Status: '+r.status,
  'Warnings: '+(r.warnings.join(', ')||'none'),
  'Limit: '+txt('self'),
  'WAV: locally synthesized approximations, not acoustic instrument recordings.',
  'MIDI: note timing/program changes and dedicated half-semitone pitch-bend channels.'
 ];
 $('music-report').textContent=text.join('\n');
}
$('music-build').addEventListener('click',()=>{
 if(working)return;
 try{
  score=Music.compose(inputs());resetAudio();summary();
  $('music-progress').value=0;out(txt('built'));buttons();
 }catch{score=null;resetAudio();out(txt('error'))}
});
$('music-variation').addEventListener('click',()=>{
 if(working)return;
 const seed=$('music-seed'),motif=$('music-motif-seed');
 seed.value=Number(seed.value)>=2147483646?'1':String(Number(seed.value)+1);
 if(!$('music-lock-motif').checked)
  motif.value=Number(motif.value)>=2147483646?'1':String(Number(motif.value)+1);
 invalidate();out(txt('variation')+' '+($('music-lock-motif').checked?txt('keep'):''));
});
$('music-refine').addEventListener('click',()=>{
 if(working)return;
 const issue=field('problem');
 if(issue==='weak-hook'){if(!$('music-lock-motif').checked)$('music-motif-seed').value=String((Number(field('motif-seed'))+97)%2147483646||1)}
 if(issue==='flat'){$('music-story').value='radiance';$('music-bars').value='64'}
 if(issue==='weak-santur'){$('music-lead').value='santur';$('music-solo').value='santur';$('music-santur-solo').checked=true}
 if(issue==='weak-guitar'){$('music-solo').value='electric_guitar';$('music-guitar-solo').checked=true}
 if(issue==='too-short'){$('music-bars').value='64';$('music-bpm').value=String(Math.min(106,Number(field('bpm'))))}
 if(issue==='hard-ending'){$('music-story').value='prayer';$('music-santur-solo').checked=true}
 const seed=$('music-seed');seed.value=String((Number(seed.value)+127)%2147483646||1);
 invalidate();out(txt('variation')+' '+($('music-lock-motif').checked?txt('keep'):''));
});
$('music-midi').addEventListener('click',()=>{
 if(score&&!working)try{download(Music.midi(score),'mid','audio/midi')}catch{out(txt('error'))}
});
$('music-score').addEventListener('click',()=>{
 if(score&&!working)download(JSON.stringify(score,null,2),'json','application/json');
});
$('music-wav').addEventListener('click',()=>{
 if(wav&&!working)download(wav,'wav','audio/wav');
});
$('music-render').addEventListener('click',async()=>{
 if(!score||working)return;
 const start=++revision,active=score;working=true;resetAudio();buttons();
 try{
  const sr=Number($('music-quality').value);
  const data=await Music.renderWav(active,{sampleRate:sr,sound:$('music-sound').value,
   shouldAbort:()=>start!==revision,
   onProgress:p=>{if(start===revision){$('music-progress').value=Math.round(p*100);out(txt('rendering')+': '+Math.round(100*p)+'%')}}
  });
  if(start!==revision)return;
  wav=data;
  const audio=Music.analyzeWav(data,active);
  const a=[
    fa()?'--- تحلیل واقعی سیگنال WAV ---':'--- Measured WAV diagnostics ---',
    'Sound profile: '+$('music-sound').value,
    'Peak dBFS: '+audio.measured_peak_dbfs,
    'RMS dBFS: '+audio.measured_rms_dbfs,
    'Crest dB: '+audio.measured_crest_db,
    'Near-silent fraction: '+audio.near_silent_fraction,
    'Clipped PCM frames: '+audio.clipped_frame_count,
    'Stereo correlation: '+audio.stereo_correlation,
    ...audio.section_rms_dbfs.map(x=>x.name+': '+x.rms_dbfs+' dBFS'),
    'WAV warnings: '+(audio.warnings.join(', ')||'none'),
    'No listening evaluation, acoustic fidelity, or mastering certification.'
  ];
  $('music-report').textContent+='\n'+a.join('\n');
  objectUrl=URL.createObjectURL(new Blob([wav],{type:'audio/wav'}));
  $('music-preview').src=objectUrl;
  out((fa()?'WAV استریو آماده شد.':'Stereo WAV ready.')+' '+txt('browser'));
 }catch(e){if(start===revision)out(e?.message==='render-cancelled'?txt('cancelled'):
    e?.message==='mobile-render-memory-budget'?txt('resource'):txt('error'))}
 finally{if(start===revision){working=false;buttons()}}
});
$('music-cancel').addEventListener('click',()=>{
 if(!working)return;
 revision++;working=false;resetAudio();out(txt('cancelled'));buttons();
});
const sample=Music.DEFAULT;
for(const [key,value] of Object.entries({
 title:sample.title,mode:sample.mode,key:sample.key,bpm:sample.bpm,bars:sample.bars,
 lead:sample.lead,story:sample.story,solo:sample.solo,
 'santur-solo':sample.santurSolo,'guitar-solo':sample.guitarSolo,daf:sample.daf,
 seed:sample.seed,'motif-seed':sample.motifSeed})){
 const node=$('music-'+key);if(node.type==='checkbox')node.checked=value;else node.value=String(value)
}
$('music-lock-motif').checked=true;
// Snapshot only shipped form defaults, never user audio or private draft text.
const baseline=[...$('music-card').querySelectorAll('input,select,textarea')].map(node=>({node,value:node.value,checked:node.checked}));
function isFormChanged(){return baseline.some(({node,value,checked})=>
 (node.type==='checkbox'||node.type==='radio')?node.checked!==checked:node.value!==value)}
function resetPrivateDraft(){
 // Clear locally typed titles, seeds and selections as well as WAV and score.
 for(const {node,value,checked} of baseline){
  if(node.type==='checkbox'||node.type==='radio')node.checked=checked;
  else node.value=value;
 }
 invalidate();
}
document.addEventListener('nexus-music-clear',()=>{invalidate();$('music-title').value='Untitled journey'});
window.addEventListener('pagehide',()=>{revision++;resetAudio()});
out(txt('ready'));buttons();
window.NexusMusicUI=Object.freeze({clear:resetPrivateDraft,hasScore:()=>Boolean(score),hasWav:()=>Boolean(wav),
 hasTransientWork:()=>Boolean(score||wav||working||isFormChanged())});
})();
