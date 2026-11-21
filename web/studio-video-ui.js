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
const timingLabel=node('label');timingLabel.className='inline';
const individual=node('input','studio-video-individual-timing');individual.type='checkbox';
const timingText=node('span');timingLabel.append(individual,timingText);
const fadeLabel=node('label');fadeLabel.className='inline';
const fade=node('input','studio-video-fade');fade.type='checkbox';fade.checked=true;
const fadeText=node('span');fadeLabel.append(fade,fadeText);
const transitionLabel=node('label');transitionLabel.className='inline';
const crossfade=node('input','studio-video-crossfade');crossfade.type='checkbox';crossfade.checked=true;
const crossfadeText=node('span');transitionLabel.append(crossfade,crossfadeText);
const transitionLengthLabel=node('label'),transitionLength=node('select','studio-video-transition-length');
for(const value of ['0.15','0.35','0.65']){
 const o=node('option');o.value=value;o.textContent=value+' s';transitionLength.append(o)
}
transitionLength.value='0.35';transitionLengthLabel.append(transitionLength);
controls.append(aspectLabel,durationLabel,timingLabel,fadeLabel,transitionLabel,transitionLengthLabel);
const sceneList=node('div','studio-video-scenes');
sceneList.setAttribute('role','list');
sceneList.style.cssText='display:grid;gap:6px;margin:10px 0';
const timingInfo=node('output','studio-video-total');timingInfo.setAttribute('aria-live','polite');
timingInfo.style.cssText='display:block;margin:8px 0';
const audioMix=node('div');audioMix.className='row';
const volumeLabel=node('label'),volume=node('input','studio-video-volume');
volume.type='range';volume.min='0';volume.max='100';volume.step='5';volume.value='70';
const volumeText=node('span');volumeLabel.append(volumeText,volume);
const audioFadeLabel=node('label');audioFadeLabel.className='inline';
const audioFade=node('input','studio-video-audio-fade');
audioFade.type='checkbox';audioFade.checked=true;
const audioFadeText=node('span');audioFadeLabel.append(audioFade,audioFadeText);

const audioDelayLabel=node('label'),audioDelay=node('select','studio-video-audio-delay');
const audioSkipLabel=node('label'),audioSkip=node('select','studio-video-audio-skip');
for(const [value,label] of [['0','0 s'],['0.25','0.25 s'],['0.5','0.5 s'],['1','1 s']]){
 const o=node('option');o.value=value;o.textContent=label;audioDelay.append(o)
}
for(const [value,label] of [['0','0 s'],['0.5','0.5 s'],['1','1 s'],['2','2 s']]){
 const o=node('option');o.value=value;o.textContent=label;audioSkip.append(o)
}
audioDelayLabel.append(audioDelay);audioSkipLabel.append(audioSkip);
audioMix.append(volumeLabel,audioFadeLabel,audioDelayLabel,audioSkipLabel);
const canvas=node('canvas','studio-video-canvas');canvas.width=640;canvas.height=360;
canvas.hidden=true;canvas.setAttribute('role','img');
canvas.style.cssText='display:block;max-width:100%;max-height:340px;margin:12px auto;border-radius:12px;background:#101618';
const scrubLabel=node('label'),scrub=node('input','studio-video-scrub');
scrub.type='range';scrub.min='0';scrub.max='6';scrub.step='0.05';scrub.value='0';
scrub.setAttribute('aria-label','Storyboard preview position');
const scrubText=node('span');scrubLabel.append(scrubText,scrub);
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
box.append(heading,help,imageLabel,generated,sceneList,timingInfo,audioLabel,audioMix,controls,canvas,scrubLabel,commands,meter,output,info);
const insertAfter=$('studio-local-image-panel')||$('studio-imagegen-panel')||$('studio-compose');
insertAfter.after(box);$('nexus-zen-suggestions').append(shortcut);

const MAX_IMAGE=6_000_000,MAX_AUDIO=8_000_000,MAX_PIXELS=8_000_000,MAX_OUTPUT=32_000_000;
const MAX_SCENES=4,MAX_TOTAL_IMAGE_BYTES=16_000_000,MAX_TOTAL_PIXELS=16_000_000,MAX_DURATION=24;
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
/* Camera transforms are strictly contained inside the output canvas.
 * Frame factor never exceeds 1: no content is cropped or invented.
 */
function drawBitmap(ctx,bitmap,opacity,progress=0,motion='still'){
 if(!bitmap||opacity<=0)return;
 const p=Math.max(0,Math.min(1,progress));
 const smooth=p*p*(3-2*p);
 const scale=Math.min(canvas.width/bitmap.width,canvas.height/bitmap.height);
 const factor=motion==='push'?0.90+0.10*smooth:
  motion==='pull'?1-0.10*smooth:
  motion==='left'||motion==='right'?0.94:1;
 const w=bitmap.width*scale*factor,h=bitmap.height*scale*factor;
 const freeX=(canvas.width-w)/2,freeY=(canvas.height-h)/2;
 const travel=(motion==='left'||motion==='right')?
  Math.min(20,Math.max(0,freeX)):0;
 const dx=motion==='left'?travel*(1-2*smooth):
  motion==='right'?travel*(2*smooth-1):0;
 ctx.globalAlpha=opacity;
 ctx.drawImage(bitmap,freeX+dx,freeY,w,h);
 ctx.globalAlpha=1;
}
function timeline(override){
 if(!scenes.length)return null;
 const raw=Number(override===undefined?duration.value:override);
 if(!individual.checked&&![3,6,10,12].includes(raw))return null;
 const times=individual.checked?scenes.map(scene=>Number(scene.seconds)) :
  scenes.map(()=>raw/scenes.length);
 const total=times.reduce((sum,sec)=>sum+sec,0);
 if(!Number.isFinite(total)||total>MAX_DURATION||total<=0||
    times.some(sec=>!Number.isFinite(sec)||sec<0.5||sec>12))return null;
 return {times,total};
}
function previewTime(t,full){
 const spec=timeline(full);
 if(!spec)return;
 scrub.max=String(spec.total);
 scrub.value=String(Math.max(0,Math.min(spec.total,t)));
 draw(Number(scrub.value),spec.total);
}
function draw(t=0,seconds){
 const ctx=canvas.getContext('2d',{alpha:false});
 if(!ctx||!scenes.length)return;
 const plan=timeline(seconds);
 if(!plan)return;
 ctx.fillStyle='#101618';ctx.fillRect(0,0,canvas.width,canvas.height);
 const elapsed=Math.max(0,Math.min(plan.total,t));
 let idx=0,sceneStart=0;
 while(idx<plan.times.length-1&&elapsed>=sceneStart+plan.times[idx]){
  sceneStart+=plan.times[idx];idx++;
 }
 const local=elapsed-sceneStart,sceneSeconds=plan.times[idx];
 const nextSeconds=plan.times[idx+1]||0;
 const transition=Math.min(Number(transitionLength.value)||0,sceneSeconds/2,nextSeconds/2);
 const blend=(crossfade.checked&&idx<plan.times.length-1&&transition>0&&
   local>sceneSeconds-transition)?
  Math.max(0,Math.min(1,(local-(sceneSeconds-transition))/transition)):0;
 const outer=fade.checked?Math.max(0,Math.min(1,elapsed/0.4,(plan.total-elapsed)/0.4)):1;
 drawBitmap(ctx,scenes[idx].bitmap,outer*(1-blend),
   sceneSeconds?local/sceneSeconds:0,scenes[idx].motion);
 if(blend>0)drawBitmap(ctx,scenes[idx+1].bitmap,outer*blend,
   0,scenes[idx+1].motion);
}
function freeScenes(){
 for(const scene of scenes)scene.bitmap.close?.();
 scenes=[];image=null;sceneList.replaceChildren();
 canvas.width=canvas.height=0; // discard raw preview pixels before the next decode
}
const splitParts=seconds=>{
 const start=Math.floor(seconds/2);
 return [start,seconds-start];
};
function canSplit(scene){
 const px=scene.bitmap.width*scene.bitmap.height;
 const all=scenes.reduce((sum,part)=>sum+part.bitmap.width*part.bitmap.height,0);
 const [a,b]=splitParts(scene.seconds);
 return individual.checked&&scenes.length<MAX_SCENES&&
  [1,2,3,4,6,8,12].includes(a)&&[1,2,3,4,6,8,12].includes(b)&&
  all+px<=MAX_TOTAL_PIXELS;
}
async function splitScene(scene,index){
 if(recording||preparing||loading||scenes[index]!==scene||!canSplit(scene))return;
 const token=epoch,scope=selection();
 preparing=true;refresh();
 let clone=null;
 try{
  clone=await createImageBitmap(scene.bitmap);
  if(token!==epoch||scope!==selection()||scenes[index]!==scene||!canSplit(scene)){
   clone.close?.();return;
  }
  const [first,second]=splitParts(scene.seconds);
  scene.seconds=first;
  scenes.splice(index+1,0,{
   bitmap:clone,label:scene.label,seconds:second,motion:scene.motion
  });
  image=scenes[0].bitmap;
  previewClear();layout();listScenes();
  message('Scene split into two independently editable segments.',
          'صحنه به دو بخش مستقل و قابل ویرایش تقسیم شد.');
 }catch{
  clone?.close?.();
  if(token===epoch)message('Could not split this scene within memory limits.',
       'تقسیم صحنه در محدودیت حافظه ممکن نشد.');
 }finally{if(token===epoch){preparing=false;refresh()}}
}
function listScenes(){
 sceneList.replaceChildren();
 scenes.forEach((scene,index)=>{
  const row=node('div');row.setAttribute('role','listitem');row.className='row';
  const label=node('span');label.style.cssText='flex:2;min-width:120px;overflow-wrap:anywhere';
  label.textContent=(index+1)+'. '+scene.label;
  row.append(label);
  const sceneTiming=node('select');sceneTiming.dataset.sceneSeconds=String(index);
  sceneTiming.setAttribute('aria-label',words('Scene duration seconds','مدت صحنه به ثانیه')+' '+(index+1));
  for(const sec of [1,2,3,4,6,8,12]){
   const option=node('option');option.value=String(sec);option.textContent=sec+' s';
   sceneTiming.append(option);
  }
  sceneTiming.value=String(scene.seconds||3);
  sceneTiming.disabled=!individual.checked||recording||preparing||loading;
  sceneTiming.addEventListener('change',()=>{
   if(recording||preparing||loading)return;
   scene.seconds=Number(sceneTiming.value);
   previewClear();layout();refresh();
  });
  row.append(sceneTiming);
  const motionChoice=node('select');motionChoice.dataset.sceneMotion=String(index);
  motionChoice.setAttribute('aria-label',words('Scene motion','حرکت تصویر صحنه')+' '+(index+1));
  for(const [mode,en,fa] of [
    ['still','Still','ثابت'],['push','Gentle push','نزدیک‌شدن ملایم'],
    ['pull','Gentle pullback','دورشدن ملایم'],
    ['left','Drift left','حرکت آرام به چپ'],
    ['right','Drift right','حرکت آرام به راست']]){
   const o=node('option');o.value=mode;o.textContent=words(en,fa);motionChoice.append(o)
  }
  motionChoice.value=scene.motion||'still';
  motionChoice.disabled=Boolean(recording||preparing||loading);
  motionChoice.addEventListener('change',()=>{
   if(recording||preparing||loading)return;
   scene.motion=motionChoice.value;
   previewClear();layout();refresh();
  });
  row.append(motionChoice);
  for(const [action,textEN,textFA] of [
   ['preview','Preview','پیش‌نمایش'],['up','Move up','انتقال به بالا'],
   ['down','Move down','انتقال به پایین'],['split','Split scene','تقسیم صحنه'],['remove','Remove','حذف']]){
   const button=node('button');button.type='button';button.className='secondary';
   button.textContent=words(textEN,textFA);
   button.setAttribute('aria-label',words(textEN,textFA)+' '+(index+1));
   button.dataset.sceneAction=action;
   button.disabled=Boolean(recording||preparing||loading)||
    (action==='up'&&index===0)||(action==='down'&&index===scenes.length-1)||
    (action==='split'&&!canSplit(scene));
   button.addEventListener('click',()=>{
    if(recording||preparing||loading)return;
    if(action==='preview'){
     const plan=timeline();
     if(!plan)return;
     const before=plan.times.slice(0,index).reduce((sum,sec)=>sum+sec,0);
     previewTime(before+plan.times[index]/2,plan.total);return;
    }
    if(action==='split'){splitScene(scene,index);return}
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
 const plan=timeline();
 if(plan)previewTime(plan.times[0]/2,plan.total); // Show first full scene, never an all-black fade frame.
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
 const plan=timeline();
 photo.disabled=audio.disabled=generated.disabled=aspect.disabled=fade.disabled=crossfade.disabled=individual.disabled=transitionLength.disabled=volume.disabled=audioFade.disabled=audioDelay.disabled=audioSkip.disabled=blocked;
 duration.disabled=blocked||individual.checked;
 scrub.disabled=blocked||!plan;
 timingInfo.textContent=plan?
  words('Total clip duration: ','مدت کل کلیپ: ')+plan.total.toFixed(2)+' s':
  scenes.length?words('Duration exceeds 24 seconds; shorten individual scenes.','مدت بیش از ۲۴ ثانیه است؛ زمان صحنه‌ها را کم کن.'):'';
 for(const field of sceneList.querySelectorAll('[data-scene-seconds]'))
  field.disabled=blocked||!individual.checked;
 for(const field of sceneList.querySelectorAll('[data-scene-motion]'))
  field.disabled=blocked;
 for(const button of sceneList.querySelectorAll('button'))button.disabled=blocked||
  (button.dataset.sceneAction==='up'&&button.closest('[role=listitem]')===sceneList.firstChild)||
  (button.dataset.sceneAction==='down'&&button.closest('[role=listitem]')===sceneList.lastChild)||
  (button.dataset.sceneAction==='split'&&!canSplit(scenes[Array.from(sceneList.children).indexOf(button.closest('[role=listitem]'))]));
 start.disabled=blocked||!image||unavailable||!plan;
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
   decoded.push({bitmap,label:f.name.slice(0,100),seconds:3,motion:'still'});
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
  scenes=[{bitmap:candidate,label:words('Generated image','تصویر ساخته‌شده'),seconds:3,motion:'still'}];image=candidate;
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
for(const control of [aspect,duration,fade,crossfade,transitionLength,individual])
 control.addEventListener('change',()=>{
  if(!recording&&!preparing){
   previewClear();if(control===individual)listScenes();layout();refresh();
  }
 });
scrub.addEventListener('input',()=>{
 if(recording||preparing||loading||!timeline())return;
 previewClear();draw(Number(scrub.value),timeline().total);
});
async function startRecording(){
 if(recording||loading||preparing||!image||!mimeType())return;
 const chosen=timeline(),current=++epoch,scope=selection(),seconds=chosen?.total;
 if(!chosen){message('Choose a valid duration of at most 24 seconds.','مدت معتبر تا سقف ۲۴ ثانیه انتخاب کن.');return}
 preparing=true;previewClear();meter.value=0;layout();refresh();
 let ctx=null,audioBuffer=null,stream=null,recorder=null,audioSource=null,ownJob=null;
 let gain=null,playable=0,skipSeconds=0,delaySeconds=0;
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
   skipSeconds=Number(audioSkip.value);delaySeconds=Number(audioDelay.value);
   if(![0,0.5,1,2].includes(skipSeconds)||![0,0.25,0.5,1].includes(delaySeconds))
    throw Error('audio-offset-invalid');
   playable=Math.min(seconds-delaySeconds,audioBuffer.duration-skipSeconds);
   if(!Number.isFinite(playable)||playable<=0.05)throw Error('audio-window-empty');
   gain=ctx.createGain();
   gain.gain.value=0; // initialized silently until explicitly scheduled
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
  const startTime=performance.now();
  if(audioSource){
   // Both gain automation and sample offset share an AudioContext clock.
   // An intentional delay is relative to the beginning of this recording,
   // not a guarantee of frame-accurate device-specific synchronization.
   const at=ctx.currentTime+0.10+delaySeconds;
   const level=Number(volume.value)/100;
   const ramp=Math.min(0.5,playable/3);
   if(audioFade.checked&&level>0&&ramp>0){
    gain.gain.setValueAtTime(0,at);
    gain.gain.linearRampToValueAtTime(level,at+ramp);
    gain.gain.setValueAtTime(level,at+Math.max(ramp,playable-ramp));
    gain.gain.linearRampToValueAtTime(0,at+playable);
   }else gain.gain.setValueAtTime(level,at);
   audioSource.start(at,skipSeconds,playable);
  }
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
  'Arrange up to 4 uncropped scenes. Split an eligible scene in independent-timing mode, set contained camera motion, and adjust audio offset/start delay. Local recorder; no generative AI or original-file modification.',
  'تا ۴ صحنهٔ بدون برش تنظیم کن. در حالت زمان مستقل، صحنهٔ مجاز را دو بخش کن؛ حرکت دوربین، نقطهٔ آغاز صوت و تأخیر صدا را تغییر بده. ضبط محلی است و فایل اصلی تغییر نمی‌کند.');
 const labelText=(parent,child,en,fa)=>{
  if(parent.firstChild?.nodeType===3)parent.firstChild.remove();
  parent.insertBefore(document.createTextNode(words(en,fa)),child)
 };
 labelText(imageLabel,photo,'Photos: 1–4 PNG/JPEG (6 MB each, 16 MB total)','۱ تا ۴ تصویر PNG/JPEG (هرکدام ۶ و مجموعاً ۱۶ مگابایت)');
 generated.textContent=words('Use generated image from this tab','استفاده از تصویر ساخته‌شده در این برگه');
 labelText(audioLabel,audio,'Optional audio (≤ 8 MB, ≤ 30 s)','صوت اختیاری (تا ۸ مگابایت و ۳۰ ثانیه)');
 labelText(aspectLabel,aspect,'Frame','قالب تصویر');
 labelText(durationLabel,duration,'Total-duration preset','مدت آمادهٔ کل');
 timingText.textContent=words('Set durations per scene','زمان مستقل برای هر صحنه');
 labelText(transitionLengthLabel,transitionLength,'Crossfade length','طول گذار نرم');
 volumeText.textContent=words('Audio volume ('+volume.value+'%)','شدت صدا ('+volume.value+'٪)');
 audioFadeText.textContent=words('Audio fade in/out','محوشدن ابتدا و انتهای صدا');
 labelText(audioDelayLabel,audioDelay,'Audio start delay','تأخیر شروع صدا');
 labelText(audioSkipLabel,audioSkip,'Skip audio opening','حذف ابتدای صوت از پخش');
 scrubText.textContent=words('Preview timeline','پیش‌نمایش خط زمانی');
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
volume.addEventListener('input',()=>{
 volumeText.textContent=words('Audio volume ('+volume.value+'%)','شدت صدا ('+volume.value+'٪)');
 if(!recording)previewClear();
});
audioFade.addEventListener('change',()=>{if(!recording)previewClear()});
for(const control of [audioDelay,audioSkip])
 control.addEventListener('change',()=>{if(!recording&&!preparing)previewClear()});
$('language')?.addEventListener('change',()=>queueMicrotask(labels));
labels();refresh();
})();
