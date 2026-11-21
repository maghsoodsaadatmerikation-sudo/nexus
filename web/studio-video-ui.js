/* NEXUS Studio: bounded local image-to-video, optional user-selected audio.
 * No provider, network request, model, automatic publishing, or persisted media.
 * The entire source image remains visible (contain fit, no crop).
 */
(()=>{'use strict';
const $=id=>document.getElementById(id);
if(!window.NexusStudioUI?.selection||!$('studio-compose')||!$('nexus-zen-suggestions'))return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const node=(tag,id)=>{const element=document.createElement(tag);if(id)element.id=id;return element};
const box=node('details','studio-video-panel');box.className='studio-vision-panel';
const heading=node('summary'),help=node('p');help.className='help';
const imageLabel=node('label'),photo=node('input','studio-video-photo');
photo.type='file';photo.multiple=true;photo.accept='.png,.jpg,.jpeg,image/png,image/jpeg';imageLabel.append(photo);
const generated=node('button','studio-video-from-generated');
generated.className='secondary';generated.type='button';
const audioLabel=node('label'),audio=node('input','studio-video-audio');
audio.type='file';audio.accept='.wav,.mp3,.ogg,.m4a,audio/wav,audio/mpeg,audio/ogg,audio/mp4';audioLabel.append(audio);
const controls=node('div');controls.className='row';
const aspectLabel=node('label'),aspect=node('select','studio-video-aspect');
for(const [value,title] of [['landscape','Landscape · 16:9'],['portrait','Portrait · 9:16']]){
 const o=node('option');o.value=value;o.textContent=title;aspect.append(o)
}aspectLabel.append(aspect);
const durationLabel=node('label'),duration=node('select','studio-video-duration');
for(const sec of [3,6,10,12]){const o=node('option');o.value=String(sec);o.textContent=sec+' s';duration.append(o)}
duration.value='6';durationLabel.append(duration);
const fadeLabel=node('label');fadeLabel.className='inline';
const fade=node('input','studio-video-fade');fade.type='checkbox';fade.checked=true;
const fadeText=node('span');fadeLabel.append(fade,fadeText);
const transitionLabel=node('label');transitionLabel.className='inline';
const crossfade=node('input','studio-video-crossfade');crossfade.type='checkbox';crossfade.checked=true;
const crossfadeText=node('span');transitionLabel.append(crossfade,crossfadeText);
controls.append(aspectLabel,durationLabel,fadeLabel,transitionLabel);
const sceneList=node('div','studio-video-scenes');
sceneList.setAttribute('role','list');
sceneList.style.cssText='display:grid;gap:6px;margin:10px 0';
const canvas=node('canvas','studio-video-canvas');canvas.width=640;canvas.height=360;
canvas.hidden=true;canvas.setAttribute('role','img');
canvas.style.cssText='display:block;max-width:100%;max-height:340px;margin:12px auto;border-radius:12px;background:#101618';
const commands=node('div');commands.className='row';
const start=node('button','studio-video-start'),cancel=node('button','studio-video-cancel');
const clear=node('button','studio-video-clear'),download=node('button','studio-video-download');
const shortcut=node('button','studio-video-open');
for(const b of [start,cancel,clear,download,shortcut]){b.type='button';b.className='secondary'}
commands.append(start,cancel,clear,download);
const meter=node('progress','studio-video-progress');meter.max=100;meter.value=0;meter.style.width='100%';
const output=node('video','studio-video-preview');output.controls=true;output.playsInline=true;
output.preload='metadata';output.hidden=true;
output.style.cssText='display:block;max-width:100%;max-height:440px;margin:12px auto';
const info=node('p','studio-video-status');info.className='help';info.setAttribute('role','status');
info.setAttribute('aria-live','polite');
box.append(heading,help,imageLabel,generated,sceneList,audioLabel,controls,canvas,commands,meter,output,info);
const insertAfter=$('studio-local-image-panel')||$('studio-imagegen-panel')||$('studio-compose');
insertAfter.after(box);$('nexus-zen-suggestions').append(shortcut);

const MAX_IMAGE=6_000_000,MAX_AUDIO=8_000_000,MAX_PIXELS=8_000_000,MAX_OUTPUT=32_000_000;
const MAX_SCENES=4,MAX_TOTAL_IMAGE_BYTES=16_000_000,MAX_TOTAL_PIXELS=16_000_000;
let image=null,scenes=[],music=null,recording=null,videoURL=null,format=null,epoch=0,loading=false,preparing=false;
let selected=selection();
function selection(){
 const s=window.NexusStudioUI.selection?.()||{};
 return JSON.stringify([s.projectId||null,s.threadId||null,s.head||null,s.revision||null,s.branchBase||null]);
}
const message=(en,fa)=>{info.textContent=words(en,fa)};
const mimeType=()=>{
 if(typeof MediaRecorder==='undefined'||typeof HTMLCanvasElement.prototype.captureStream!=='function')return '';
 return ['video/webm;codecs=vp8,opus','video/webm;codecs=vp9,opus','video/webm','video/mp4']
   .find(t=>MediaRecorder.isTypeSupported(t))||'';
};
function previewClear(){
 output.pause();output.removeAttribute('src');output.load();output.hidden=true;
 if(videoURL)URL.revokeObjectURL(videoURL);
 videoURL=format=null;download.disabled=true;
}
function drawBitmap(ctx,bitmap,opacity){
 if(!bitmap||opacity<=0)return;
 const scale=Math.min(canvas.width/bitmap.width,canvas.height/bitmap.height);
 const w=bitmap.width*scale,h=bitmap.height*scale;
 ctx.globalAlpha=opacity;
 ctx.drawImage(bitmap,(canvas.width-w)/2,(canvas.height-h)/2,w,h);
 ctx.globalAlpha=1;
}
function draw(t=0,seconds=6){
 const ctx=canvas.getContext('2d',{alpha:false});
 if(!ctx||!scenes.length)return;
 ctx.fillStyle='#101618';ctx.fillRect(0,0,canvas.width,canvas.height);
 const count=scenes.length,segment=seconds/count;
 const elapsed=Math.max(0,Math.min(seconds,t));
 const idx=Math.min(count-1,Math.floor(elapsed/segment));
 const windowStart=(idx+1)*segment;
 const transition=Math.min(0.35,segment*0.2);
 const blend=(crossfade.checked&&idx<count-1&&elapsed>windowStart-transition)?
  Math.max(0,Math.min(1,(elapsed-windowStart+transition)/transition)):0;
 const outer=fade.checked?Math.max(0,Math.min(1,elapsed/0.4,(seconds-elapsed)/0.4)):1;
 drawBitmap(ctx,scenes[idx].bitmap,outer*(1-blend));
 if(blend>0)drawBitmap(ctx,scenes[idx+1].bitmap,outer*blend);
}
function freeScenes(){
 for(const scene of scenes)scene.bitmap.close?.();
 scenes=[];image=null;sceneList.replaceChildren();
 canvas.width=canvas.height=0; // discard raw preview pixels before the next decode
}
function listScenes(){
 sceneList.replaceChildren();
 scenes.forEach((scene,index)=>{
  const row=node('div');row.setAttribute('role','listitem');row.className='row';
  const label=node('span');label.style.cssText='flex:2;min-width:120px;overflow-wrap:anywhere';
  label.textContent=(index+1)+'. '+scene.label;
  row.append(label);
  for(const [action,textEN,textFA] of [
   ['preview','Preview','پیش‌نمایش'],['up','Move up','انتقال به بالا'],
   ['down','Move down','انتقال به پایین'],['remove','Remove','حذف']]){
   const button=node('button');button.type='button';button.className='secondary';
   button.textContent=words(textEN,textFA);
   button.setAttribute('aria-label',words(textEN,textFA)+' '+(index+1));
   button.dataset.sceneAction=action;
   button.disabled=Boolean(recording||preparing||loading)||
    (action==='up'&&index===0)||(action==='down'&&index===scenes.length-1);
   button.addEventListener('click',()=>{
    if(recording||preparing||loading)return;
    if(action==='preview'){
     const sec=Number(duration.value)||6;draw((index+0.5)*sec/scenes.length,sec);return;
    }
    if(action==='remove'){
     const removed=scenes.splice(index,1)[0];removed.bitmap.close?.();
    }else{
     const other=index+(action==='up'?-1:1);
     if(other<0||other>=scenes.length)return;
     [scenes[index],scenes[other]]=[scenes[other],scenes[index]];
    }
    image=scenes[0]?.bitmap||null;
    photo.value=''; // no hidden references to removed/reordered original File objects
    previewClear();layout();listScenes();refresh();
   });
   row.append(button);
  }
  sceneList.append(row);
 });
}
function layout(){
 if(recording)return;
 if(aspect.value==='portrait'){canvas.width=360;canvas.height=640}
 else{canvas.width=640;canvas.height=360}
 draw(1,6); // Preview the full frame, not the first fade-to-black frame.
}
function stopJob(discard=true){
 const job=recording;
 if(!job)return;
 job.discard ||= discard;
 if(job.frame)cancelAnimationFrame(job.frame);
 if(job.watchdog)clearTimeout(job.watchdog);
 try{if(job.recorder?.state==='recording')job.recorder.stop();else{job.discard=true;releaseJob(job)}}
 catch{job.discard=true;releaseJob(job)}
}
function releaseJob(job){
 if(job.frame)cancelAnimationFrame(job.frame);
 if(job.watchdog)clearTimeout(job.watchdog);
 for(const track of job.stream?.getTracks()||[])track.stop();
 try{job.audioSource?.stop()}catch{}
 job.audioContext?.close().catch(()=>{});
 if(recording===job)recording=null;
 refresh();
}
function wipe(){
 epoch++;
 stopJob(true);
 freeScenes();
 music=null;photo.value='';audio.value='';loading=false;preparing=false;
 previewClear();canvas.width=0;canvas.height=0;canvas.hidden=true;meter.value=0;message('','');refresh();
}
function refresh(){
 const running=Boolean(recording),blocked=running||loading||preparing,unavailable=!mimeType();
 photo.disabled=audio.disabled=generated.disabled=aspect.disabled=duration.disabled=fade.disabled=crossfade.disabled=blocked;
 for(const button of sceneList.querySelectorAll('button'))button.disabled=blocked||
  (button.dataset.sceneAction==='up'&&button.closest('[role=listitem]')===sceneList.firstChild)||
  (button.dataset.sceneAction==='down'&&button.closest('[role=listitem]')===sceneList.lastChild);
 start.disabled=blocked||!image||unavailable;
 cancel.disabled=!running&&!preparing;
 clear.disabled=loading;
 download.disabled=!videoURL;
 canvas.hidden=!image;
}
async function acceptImages(files){
 if(recording||preparing||loading)return;
 const ticket=++epoch,selectedFiles=Array.from(files||[]);
 freeScenes();previewClear();refresh();
 if(!selectedFiles.length){photo.value='';return}
 if(selectedFiles.length>MAX_SCENES||
    selectedFiles.some(f=>!['image/png','image/jpeg'].includes(f.type)||
      f.size<=0||f.size>MAX_IMAGE)||
    selectedFiles.reduce((n,f)=>n+f.size,0)>MAX_TOTAL_IMAGE_BYTES){
  photo.value='';message('Select up to 4 PNG/JPEG photos (6 MB each, 16 MB total).',
   'حداکثر ۴ تصویر PNG/JPEG انتخاب کن (هرکدام ۶ و مجموعاً ۱۶ مگابایت).');
  return;
 }
 loading=true;refresh();
 const decoded=[];let pixels=0;
 try{
  for(const f of selectedFiles){
   const bitmap=await createImageBitmap(f,{imageOrientation:'from-image'});
   if(ticket!==epoch){bitmap.close?.();throw Error('stale')}
   if(!bitmap.width||!bitmap.height||bitmap.width>4096||bitmap.height>4096||
      bitmap.width*bitmap.height>MAX_PIXELS){
    bitmap.close?.();throw Error('dimensions');
   }
   pixels+=bitmap.width*bitmap.height;
   if(pixels>MAX_TOTAL_PIXELS){bitmap.close?.();throw Error('total-pixels')}
   decoded.push({bitmap,label:f.name.slice(0,100)});
  }
  if(ticket!==epoch)throw Error('stale');
  scenes=decoded;image=scenes[0].bitmap;photo.value='';layout();listScenes();
  message('Storyboard loaded locally. Use Preview or move scenes to set order.',
   'داستان تصویری روی دستگاه آماده شد؛ ترتیب صحنه‌ها را بررسی و جابه‌جا کن.');
 }catch{
  for(const scene of decoded)scene.bitmap.close?.();
  if(ticket===epoch){photo.value='';message('Photos exceeded safe limits or could not be decoded.',
    'تصویرها خارج از محدودیت ایمن‌اند یا بازخوانی نشدند.')}
 }finally{if(ticket===epoch){loading=false;refresh()}}
}
photo.addEventListener('change',()=>{if(recording||preparing)return;acceptImages(photo.files)});
generated.addEventListener('click',async()=>{
 const preview=$('studio-imagegen-preview');
 const src=preview?.getAttribute('src')||'';
 if(!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/.test(src)||src.length>8_000_150){
  message('No usable generated image exists in this tab.',
          'تصویر تولیدشدهٔ قابل استفاده در این برگه موجود نیست.');return;
 }
 const ticket=++epoch;
 freeScenes();previewClear();loading=true;refresh();
 let candidate;
 try{
  await preview.decode();
  candidate=await createImageBitmap(preview);
  if(ticket!==epoch){candidate?.close?.();return}
  if(!candidate.width||!candidate.height||candidate.width>4096||candidate.height>4096||
     candidate.width*candidate.height>MAX_PIXELS)throw Error('dimensions');
  scenes=[{bitmap:candidate,label:words('Generated image','تصویر ساخته‌شده')}];image=candidate;
  photo.value='';layout();listScenes();
  message('Generated preview copied locally; no new provider call.',
          'پیش‌نمایش ساخته‌شده روی دستگاه کپی شد؛ درخواست جدیدی ارسال نشد.');
 }catch{
  candidate?.close?.();
  if(ticket===epoch)message('Could not use the generated image.','استفاده از تصویر ساخته‌شده ممکن نیست.');
 }finally{if(ticket===epoch){loading=false;refresh()}}
});
audio.addEventListener('change',()=>{
 if(recording)return;
 const f=audio.files?.[0];
 if(!f){music=null;return}
 if(!['audio/wav','audio/x-wav','audio/mpeg','audio/mp3','audio/ogg','audio/mp4'].includes(f.type)||
     f.size<=0||f.size>MAX_AUDIO){
  music=null;audio.value='';
  message('Audio must be a supported WAV, MP3, OGG or M4A under 8 MB.',
          'صوت باید WAV، MP3، OGG یا M4A پشتیبانی‌شده و کمتر از ۸ مگابایت باشد.');
  return;
 }
 music=f;message('Audio selected locally. It is not uploaded.','صوت روی دستگاه انتخاب شد و ارسال نمی‌شود.');
});
for(const control of [aspect,duration,fade,crossfade])
 control.addEventListener('change',()=>{if(!recording){previewClear();layout();refresh()}});
async function startRecording(){
 if(recording||loading||preparing||!image||!mimeType())return;
 const current=++epoch,scope=selection(),seconds=Number(duration.value);
 if(![3,6,10,12].includes(seconds)){message('Choose a supported duration.','مدت مجاز را انتخاب کن.');return}
 preparing=true;previewClear();meter.value=0;layout();refresh();
 let ctx=null,audioBuffer=null,stream=null,recorder=null,audioSource=null,ownJob=null;
 try{
  // Construct/resume the audio context directly from the user's click.
  if(music){
   const AudioCtor=window.AudioContext||window.webkitAudioContext;
   if(!AudioCtor)throw Error('audio-api-unavailable');
   ctx=new AudioCtor();
   await ctx.resume();
   if(music.size>MAX_AUDIO)throw Error('audio-size');
   audioBuffer=await ctx.decodeAudioData(await music.arrayBuffer());
   if(!audioBuffer||!Number.isFinite(audioBuffer.duration)||audioBuffer.duration<=0||
      audioBuffer.duration>30)throw Error('audio-duration');
  }
  if(current!==epoch||scope!==selection())throw Error('context-changed');
  draw(0,seconds);
  stream=canvas.captureStream(20);
  if(!stream.getVideoTracks().length)throw Error('video-track-unavailable');
  if(ctx&&audioBuffer){
   const destination=ctx.createMediaStreamDestination();
   audioSource=ctx.createBufferSource();audioSource.buffer=audioBuffer;
   const gain=ctx.createGain();gain.gain.value=0.7;
   audioSource.connect(gain);gain.connect(destination);
   for(const track of destination.stream.getAudioTracks())stream.addTrack(track);
  }
  const selectedMime=mimeType();
  recorder=new MediaRecorder(stream,{
   mimeType:selectedMime,videoBitsPerSecond:950000,audioBitsPerSecond:96000});
  const job={recorder,stream,audioContext:ctx,audioSource,frame:0,watchdog:0,
   parts:[],size:0,discard:false,type:recorder.mimeType||selectedMime,finished:false};
  ownJob=job;recording=job;preparing=false;refresh();
  recorder.addEventListener('dataavailable',event=>{
   if(job.discard||!event.data?.size)return;
   job.size+=event.data.size;
   if(job.size>MAX_OUTPUT){job.discard=true;stopJob(true);return}
   job.parts.push(event.data);
  });
  recorder.addEventListener('error',()=>{job.discard=true;stopJob(true)});
  recorder.addEventListener('stop',()=>{
   if(job.finished)return;
   job.finished=true;
   const valid=!job.discard&&current===epoch&&scope===selection()&&
     job.size>0&&job.size<=MAX_OUTPUT;
   releaseJob(job);
   if(valid){
    const blob=new Blob(job.parts,{type:job.type});
    if(blob.size&&blob.size<=MAX_OUTPUT){
     videoURL=URL.createObjectURL(blob);format=blob.type.includes('mp4')?'mp4':'webm';
     output.src=videoURL;output.hidden=false;meter.value=100;
     message('Video is ready in this tab. Download to keep it.',
             'ویدیو در این برگه آماده است. برای نگه‌داری دانلود کن.');
    }
   }else message('Video stopped or was not recorded successfully.',
                 'ضبط ویدیو لغو شد یا با موفقیت انجام نشد.');
   refresh();
  },{once:true});
  recorder.start(250);
  if(audioSource){
   audioSource.start();
   audioSource.stop(ctx.currentTime+Math.min(seconds,audioBuffer.duration));
  }
  const startTime=performance.now();
  const step=now=>{
   if(recording!==job||job.discard)return;
   const passed=Math.min(seconds,(now-startTime)/1000);
   draw(passed,seconds);
   meter.value=Math.min(99,Math.floor(passed/seconds*100));
   if(passed>=seconds){stopJob(false);return}
   job.frame=requestAnimationFrame(step);
  };
  job.frame=requestAnimationFrame(step);
  job.watchdog=setTimeout(()=>{if(recording===job)stopJob(false)},(seconds+2)*1000);
  message('Recording locally; keep this tab open.','ضبط روی دستگاه در حال اجراست؛ این برگه را باز نگه دار.');
 }catch{
  if(ownJob&&recording===ownJob){stopJob(true)}
  else{
   for(const track of stream?.getTracks()||[])track.stop();
   try{audioSource?.stop()}catch{}
   ctx?.close().catch(()=>{});
  }
  if(current===epoch){preparing=false;message(
   'Video recording unavailable. Check browser MediaRecorder/audio support and file limits.',
   'ضبط ویدیو در دسترس نیست؛ پشتیبانی مرورگر و محدودیت فایل‌ها را بررسی کن.');}
  refresh();
 }
}
start.addEventListener('click',startRecording);
cancel.addEventListener('click',()=>{if(recording)stopJob(true);else if(preparing){epoch++;preparing=false;message('Preparation cancelled.','آماده‌سازی لغو شد.');refresh()}});
clear.addEventListener('click',wipe);
download.addEventListener('click',()=>{
 if(!videoURL)return;
 const anchor=node('a');anchor.href=videoURL;anchor.download='NEXUS-local-clip.'+(format||'webm');
 document.body.append(anchor);anchor.click();anchor.remove();
});
shortcut.addEventListener('click',()=>{box.open=true;photo.focus({preventScroll:true})});
function labels(){
 heading.textContent=words('Create a video locally (free)','ساخت ویدیوی محلی (رایگان)');
 help.textContent=words(
  'Make a 3–12 second storyboard with 1–4 uncropped photos, optional crossfades and your audio. Arrange scenes before recording. This browser-only tool does not use generative AI.',
  'از یک تا چهار تصویر بدون برش، یک کلیپ ۳ تا ۱۲ ثانیه‌ای با گذار نرم و صوت اختیاری بساز. پیش از ضبط ترتیب صحنه‌ها را مشخص کن؛ این ابزار هوش مصنوعی مولد نیست.');
 const labelText=(parent,child,en,fa)=>{
  if(parent.firstChild?.nodeType===3)parent.firstChild.remove();
  parent.insertBefore(document.createTextNode(words(en,fa)),child)
 };
 labelText(imageLabel,photo,'Photos: 1–4 PNG/JPEG (6 MB each, 16 MB total)','۱ تا ۴ تصویر PNG/JPEG (هرکدام ۶ و مجموعاً ۱۶ مگابایت)');
 generated.textContent=words('Use generated image from this tab','استفاده از تصویر ساخته‌شده در این برگه');
 labelText(audioLabel,audio,'Optional audio (≤ 8 MB, ≤ 30 s)','صوت اختیاری (تا ۸ مگابایت و ۳۰ ثانیه)');
 labelText(aspectLabel,aspect,'Frame','قالب تصویر');
 labelText(durationLabel,duration,'Duration','مدت');
 fadeText.textContent=words('Fade in/out','محوشدن آغاز و پایان');
 crossfadeText.textContent=words('Crossfade scenes','گذار نرم بین صحنه‌ها');
 listScenes();
 start.textContent=words('Record locally','شروع ضبط محلی');
 cancel.textContent=words('Stop and discard','توقف و حذف ضبط');
 clear.textContent=words('Clear media','پاک‌سازی فایل‌ها');
 download.textContent=words('Download clip','دانلود ویدیو');
 shortcut.textContent=words('Make video','ساخت ویدیو');
 canvas.setAttribute('aria-label',words('Uncropped storyboard canvas','پیش‌نمایش بدون برش تصاویر'));
 if(!mimeType())message(
  'This browser cannot record a local video in a supported format.',
  'این مرورگر از ضبط ویدیوی محلی با فرمت پشتیبانی‌شده برخوردار نیست.');
 refresh();
}
document.addEventListener('nexus-studio-state',()=>{
 const next=selection();if(next!==selected){selected=next;wipe()}else refresh();
});
document.addEventListener('nexus-studio-private-clear',wipe);
$('language')?.addEventListener('change',()=>queueMicrotask(labels));
labels();refresh();
})();
