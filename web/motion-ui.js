/* NEXUS Motion UI — offline browser video workflow, no network/no storage. */
(()=>{'use strict';
const M=globalThis.NexusMotion, $=id=>document.getElementById(id);
if(!M||!$('motion-canvas'))return;
let story=M.DEFAULT(),images={},photoFiles=new Map(),audioFile=null,audioUrl=null;
let running=false,tick=0,startClock=0,position=0,recording=false,cancelRecord=false,recorder=null;
let draftKey=null,draftSalt=null,draftEnabled=false,draftEpoch=0,draftTimer=null;
const canvas=$('motion-canvas'),ctx=canvas.getContext('2d',{alpha:false});
const status=(msg,error=false)=>{const p=$('motion-status');p.textContent=msg;p.style.color=error?'#ffc5b4':'#b6e9de'};
const secs=t=>{const n=Math.floor(Math.max(0,t));return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')};
let budgetKey='';
function updateBudget(){
 const key=[story.width,story.height,story.fps,story.soundtrack?'audio':'mute',
            ...story.scenes.map(s=>s.duration)].join(':');
 if(key===budgetKey)return;
 budgetKey=key;
 const e=M.resourceEstimate(story),gib=x=>(x/1073741824).toFixed(2)+' GiB';
 const output=$('motion-budget');
 if(output)output.textContent=
   story.width+'×'+story.height+' · '+story.fps+' fps · '+
   e.expectedFrames.toLocaleString()+' frames · assumed H.264 '+e.assumedMbps+
   ' Mb/s. Estimated compressed video '+gib(e.estimatedVideoBytes)+
   '; suggested peak temporary disk '+gib(e.estimatedPeakBytes)+
   '. Suggested phone batches: '+e.suggestedBatchScenes+
   ' scene(s). This is NOT measured available space or an output-size guarantee.';
}

function valid(){return M.validate(story)}
function drawable(){
 const factor=Math.min(960/story.width,540/story.height,1);
 canvas.width=Math.max(2,Math.round(story.width*factor/2)*2);
 canvas.height=Math.max(2,Math.round(story.height*factor/2)*2);
}
function draw(t=position){
 try{
  let length=valid();
  position=Math.max(0,Math.min(t,length-.001));
  updateBudget();
  M.frame(ctx,story,position,{images});
  $('motion-seek').value=Math.round(position/length*1000);
  $('motion-time').textContent=secs(position)+' / '+secs(length)+' · '+story.scenes.length+' scenes';
 }catch(e){status(e.message,true);}
}
function halt(){running=false;if(tick)cancelAnimationFrame(tick);tick=0;}
function play(){
 if(recording)return;halt();running=true;startClock=performance.now()-position*1000;
 const step=now=>{if(!running)return;const p=(now-startClock)/1000,total=valid();
  if(p>=total){halt();draw(total-.001);return;}draw(p);tick=requestAnimationFrame(step);};
 tick=requestAnimationFrame(step);
}
const field=(parent,text,kind,value,change,opts)=>{const label=document.createElement('label');label.textContent=text;
 let element=document.createElement(kind==='select'?'select':'input');
 if(kind==='select'){for(const item of opts){const o=document.createElement('option');o.value=item;o.textContent=item;element.append(o);}}
 else{element.type=kind;element.maxLength=kind==='text'?180:undefined;if(kind==='number'){element.min='1';element.max='900';element.step='1';}}
 element.value=value;element.addEventListener('change',()=>{try{change(element.value);draw()}catch(e){element.value=value;status(e.message,true);}});
 label.append(element);parent.append(label);return element;};
function renderScenes(){
 const node=$('motion-scenes');node.replaceChildren();
 story.scenes.forEach((scene,index)=>{
  const card=document.createElement('div');card.className='scene';
  const title=document.createElement('strong');title.textContent='Scene '+(index+1)+' / صحنه '+(index+1);card.append(title);
  const row=document.createElement('div');row.className='row';
  field(row,'Title','text',scene.title,v=>{if(!v||v.length>120)throw Error('Title 1–120 characters');scene.title=v;});
  field(row,'Duration (1–900s)','number',scene.duration,v=>{const n=Number(v);if(!Number.isInteger(n)||n<1||n>900)throw Error('Duration 1–900 seconds');const before=scene.duration;scene.duration=n;try{valid()}catch(e){scene.duration=before;throw e}});
  field(row,'Background','color',scene.background,v=>{scene.background=v});
  field(row,'Accent','color',scene.accent,v=>{scene.accent=v});
  card.append(row);
  const more=document.createElement('div');more.className='row';
  field(more,'Subtitle','text',scene.subtitle||'',v=>{if(v.length>180)throw Error('Subtitle too long');scene.subtitle=v});
  field(more,'Camera motion','select',scene.motion,v=>{scene.motion=v},M.MOTIONS);
  const names=['(procedural / none)',...photoFiles.keys()];
  const photo=field(more,'Original photo (preserve aspect)','select',scene.image||'',v=>{if(v){scene.image=v;}else delete scene.image;},['',...photoFiles.keys()]);
  photo.options[0].textContent='No photo — generated scene';
  card.append(more);node.append(card);
 });
}
function setStory(next){
 M.validate(next);halt();story=JSON.parse(JSON.stringify(next));$('motion-title').value=story.title;
 $('motion-format').value=story.width+'x'+story.height;$('motion-fps').value=story.fps;
 drawable();position=0;renderScenes();draw();status('Storyboard ready. All media stays on this device.');
 queueDraftSave();
}
$('motion-title').addEventListener('change',()=>{const old=story.title;story.title=$('motion-title').value;
 try{valid();draw();}catch(e){story.title=old;$('motion-title').value=old;status(e.message,true)}});
$('motion-format').addEventListener('change',()=>{
 const [w,h]=$('motion-format').value.split('x').map(Number);story.width=w;story.height=h;
 drawable();draw();
});
$('motion-fps').addEventListener('change',()=>{story.fps=Number($('motion-fps').value);draw()});
$('motion-add').onclick=()=>{try{if(recording)return;const existing=story.scenes.at(-1),next={...existing,duration:4,title:'NEW SCENE',subtitle:''};story.scenes.push(next);
 valid();renderScenes();draw();}catch(e){story.scenes.pop();status(e.message,true)}};
$('motion-remove').onclick=()=>{if(recording||story.scenes.length<2)return;story.scenes.pop();renderScenes();draw()};
$('motion-example').onclick=()=>{if(!recording)setStory(M.DEFAULT())};
$('motion-play').onclick=play;
$('motion-pause').onclick=()=>{halt();status('Preview paused.')};
$('motion-seek').oninput=()=>{halt();draw(valid()*Number($('motion-seek').value)/1000)};
$('motion-import').addEventListener('change',async e=>{
 const file=e.target.files[0];e.target.value='';if(!file||recording)return;
 try{
  if(file.size>256000)throw Error('Project JSON exceeds 256 KB');
  setStory(JSON.parse(await file.text()));
  status('Imported storyboard JSON: '+story.scenes.length+
         ' scenes. Reimport the original photos and audio if referenced.');
 }catch(err){status('Import rejected: '+err.message,true)}
});
$('motion-images').addEventListener('change',async e=>{
 const files=[...e.target.files];e.target.value='';if(recording)return;
 const next=new Map(photoFiles),imagesNew={...images};const newUrls=[];
 try{
  if(files.length>16||files.some(f=>f.size>16*1024*1024||f.size===0||
       !/^image\/(png|jpeg|webp)$/.test(f.type)|| !/^[A-Za-z0-9 _().+-]{1,90}\.(png|jpe?g|webp)$/i.test(f.name)))
    throw Error('Maximum 16 PNG/JPEG/WebP images, up to 16 MiB each, simple filenames only');
  for(const file of files){
    const key='assets/'+file.name,url=URL.createObjectURL(file);
    newUrls.push(url);const img=new Image();
    await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;img.src=url;});
    if(img.naturalWidth>12000||img.naturalHeight>12000)throw Error('Image pixel dimensions too large');
    next.set(key,file);imagesNew[key]=img;
  }
  // Retain prior ObjectURLs in same tab for existing scenes. No media auto-save.
  photoFiles=next;images=imagesNew;renderScenes();draw();
  status(photoFiles.size+' images loaded only into this tab. No upload.');
 }catch(err){newUrls.forEach(x=>URL.revokeObjectURL(x));status(err.message,true);}
});
$('motion-sound').addEventListener('change',e=>{
 const file=e.target.files[0];e.target.value='';if(recording)return;
 if(!file)return;if(file.size>128*1024*1024||!file.size||!/^audio\//.test(file.type)
    ||!/^[A-Za-z0-9 _().+-]{1,90}\.(mp3|wav|m4a|flac|ogg|aac)$/i.test(file.name))
  return status('Audio rejected (max 128 MiB; simple filename and supported format).',true);
 if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=URL.createObjectURL(file);
 audioFile=file;story.soundtrack='assets/'+file.name;updateBudget();status('Original audio selected; no voice transformation or remote upload.');
 queueDraftSave();
});
function download(blob,name){
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);
 a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
function sanitized(){return story.title.trim().replace(/[^a-z0-9_-]+/gi,'-').slice(0,45)||'nexus-motion';}
$('motion-export-json').onclick=()=>{try{valid();download(new Blob([JSON.stringify(story,null,2)+'\n'],{type:'application/json'}),sanitized()+'.json');
 status('Project JSON downloaded. Put selected original media in assets/ for FFmpeg rendering.');}catch(e){status(e.message,true)}};
// ZIP STORE writer; exact local files, no network, no compressor dependencies, no ZIP64.
const crcTable=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;crcTable[n]=c>>>0;}
function crc32(bytes){let c=0xffffffff;for(const b of bytes)c=crcTable[(c^b)&255]^(c>>>8);return (c^0xffffffff)>>>0;}
function zipWord(bytes,offset,value,size){let v=value;for(let i=0;i<size;i++){bytes[offset+i]=v&255;v=Math.floor(v/256)}}
async function packageZip(){
 valid();const selected=new Map(),enc=new TextEncoder();
 selected.set('storyboard.json',new Blob([JSON.stringify(story,null,2)+'\n']));
 for(const scene of story.scenes)if(scene.image){
  const file=photoFiles.get(scene.image);if(!file)throw Error('Missing photo for '+scene.image);
  selected.set(scene.image,file);
 }
 if(story.soundtrack){if(!audioFile||story.soundtrack!=='assets/'+audioFile.name)
  throw Error('Attach the soundtrack named by the storyboard before exporting');selected.set(story.soundtrack,audioFile)}
 let size=0;for(const item of selected.values())size+=item.size;
 if(size>96*1024*1024)throw Error('Browser ZIP budget is 96 MiB. Export JSON and transfer larger media separately.');
 let offset=0,entries=[],body=[];
 for(const [name,file] of selected){
  const nameBytes=enc.encode(name),data=new Uint8Array(await file.arrayBuffer()),crc=crc32(data);
  const local=new Uint8Array(30+nameBytes.length);
  zipWord(local,0,0x04034b50,4);zipWord(local,4,20,2);zipWord(local,8,0,2);
  zipWord(local,14,crc,4);zipWord(local,18,data.length,4);zipWord(local,22,data.length,4);
  zipWord(local,26,nameBytes.length,2);local.set(nameBytes,30);
  body.push(local,data);entries.push({nameBytes,crc,length:data.length,offset});
  offset+=local.length+data.length;
 }
 const centralStart=offset;
 for(const x of entries){
  const hdr=new Uint8Array(46+x.nameBytes.length);
  zipWord(hdr,0,0x02014b50,4);zipWord(hdr,4,20,2);zipWord(hdr,6,20,2);
  zipWord(hdr,16,x.crc,4);zipWord(hdr,20,x.length,4);zipWord(hdr,24,x.length,4);
  zipWord(hdr,28,x.nameBytes.length,2);zipWord(hdr,42,x.offset,4);hdr.set(x.nameBytes,46);
  body.push(hdr);offset+=hdr.length;
 }
 const end=new Uint8Array(22);zipWord(end,0,0x06054b50,4);
 zipWord(end,8,entries.length,2);zipWord(end,10,entries.length,2);
 zipWord(end,12,offset-centralStart,4);zipWord(end,16,centralStart,4);
 body.push(end);return new Blob(body,{type:'application/zip'});
}
$('motion-export-zip').onclick=async()=>{if(recording)return;
 $('motion-export-zip').disabled=true;try{const zip=await packageZip();download(zip,sanitized()+'-project.zip');
 status('Project + original media ZIP downloaded. Unzip locally, then run FFmpeg renderer with storyboard.json.');
 }catch(e){status(e.message,true)}finally{$('motion-export-zip').disabled=false}};
$('motion-cancel').onclick=()=>{cancelRecord=true;if(recorder&&recorder.state!=='inactive')recorder.stop();status('Recording cancelled; no partial download.')};
$('motion-record').onclick=async()=>{
 if(recording)return;halt();
 const total=valid(),start=Number($('motion-start').value),duration=Number($('motion-clip').value);
 if(!Number.isInteger(start)||start<0||start>=total||!Number.isInteger(duration)||
   duration<1||duration>15||start+duration>total)
  return status('Choose a 1–15 second segment entirely within the timeline.',true);
 if(!canvas.captureStream||typeof MediaRecorder==='undefined')
  return status('This browser cannot capture a Canvas video. Download the project for FFmpeg.',true);
 const mime=['video/mp4;codecs=avc1.42E01E','video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm']
   .find(type=>MediaRecorder.isTypeSupported(type));
 if(!mime)return status('No supported browser video recorder. Use FFmpeg MP4 export.',true);
 recording=true;cancelRecord=false;
 $('motion-record').disabled=true;$('motion-cancel').disabled=false;$('motion-progress').value=0;
 let stream=null,audio=null,audioContext=null,src=null,audioDest=null,raf=0,elapsed=0,bytes=0;
 const w=Math.min(story.width,story.width>story.height?1920:1080);
 const h=Math.round(w*story.height/story.width);
 const oldW=canvas.width,oldH=canvas.height;
 try{
  canvas.width=w;canvas.height=h;
  draw(start);
  stream=canvas.captureStream(Math.min(story.fps,30));
  if(audioFile){
   audio=new Audio(audioUrl);audio.preload='auto';
   audioContext=new (window.AudioContext||window.webkitAudioContext)();
   src=audioContext.createMediaElementSource(audio);
   audioDest=audioContext.createMediaStreamDestination();src.connect(audioDest);
   audioDest.stream.getAudioTracks().forEach(track=>stream.addTrack(track));
  }
  const chunks=[];
  recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:Math.min(16000000,Math.max(4500000,w*h*6))});
  recorder.ondataavailable=e=>{if(e.data&&e.data.size){bytes+=e.data.size;if(bytes>96*1024*1024){cancelRecord=true;recorder.stop();}else chunks.push(e.data)}};
  const done=new Promise((resolve,reject)=>{
   recorder.onerror=e=>reject(Error('MediaRecorder failed'));
   recorder.onstop=()=>resolve();
  });
  if(audio){audio.currentTime=start;await audioContext.resume();await audio.play();}
  recorder.start(900);
  const began=performance.now();
  await new Promise(resolve=>{
   const step=now=>{
    elapsed=Math.min(duration,(now-began)/1000);draw(Math.min(start+elapsed,total-.001));
    $('motion-progress').value=Math.min(100,Math.round(elapsed/duration*100));
    if(cancelRecord||elapsed>=duration){resolve();return;}raf=requestAnimationFrame(step);
   };raf=requestAnimationFrame(step);
  });
  if(recorder.state!=='inactive')recorder.stop();
  await done;
  if(!cancelRecord&&bytes>1000){
   const video=new Blob(chunks,{type:mime}),ext=mime.startsWith('video/mp4')?'mp4':'webm';
   download(video,sanitized()+'-'+String(start).padStart(4,'0')+'.'+ext);
   status('Real local '+ext.toUpperCase()+' segment downloaded ('+(bytes/1048576).toFixed(1)+' MiB). No upload.');
  }else status(cancelRecord?'Recording cancelled.':'Recorder produced no video; use FFmpeg.',!cancelRecord);
 }catch(e){status('Recording failed safely: '+e.message,true)}
 finally{
  if(raf)cancelAnimationFrame(raf);
  if(recorder&&recorder.state!=='inactive')try{recorder.stop()}catch{}
  if(stream)stream.getTracks().forEach(track=>track.stop());
  if(audio){audio.pause();audio.src='';}
  if(audioContext)await audioContext.close().catch(()=>{});
  recorder=null;recording=false;cancelRecord=false;canvas.width=oldW;canvas.height=oldH;
  $('motion-record').disabled=false;$('motion-cancel').disabled=true;draw(position);
 }
};
// A real, local file is compared to the exact Canvas preview at the same
// storyboard time. Nothing is uploaded and the original MP4 is never altered.
let comparisonUrl=null,comparisonBusy=false;
const realVideo=$('motion-final-video'),result=$('motion-compare-result');
const currentButton=$('motion-compare-now'),samplesButton=$('motion-compare-three');
const resetCompare=()=>{
 realVideo.pause();realVideo.removeAttribute('src');realVideo.load();
 if(comparisonUrl){URL.revokeObjectURL(comparisonUrl);comparisonUrl=null;}
 currentButton.disabled=true;samplesButton.disabled=true;
 result.textContent='No local export loaded.';
};
$('motion-compare-clear').onclick=()=>{if(!comparisonBusy)resetCompare()};
$('motion-compare-file').addEventListener('change',async event=>{
 const file=event.target.files[0];event.target.value='';
 if(!file||comparisonBusy)return;
 resetCompare();
 if(file.size<501||file.size>8*1024*1024*1024||!/\.mp4$/i.test(file.name)||
    (file.type&&file.type!=='video/mp4'&&file.type!=='application/octet-stream')){
   result.textContent='Choose a local MP4 from 501 bytes to 8 GiB (streamed by browser, not copied).';
   return;
 }
 comparisonUrl=URL.createObjectURL(file);
 realVideo.src=comparisonUrl;
 try{
  if(realVideo.readyState<1)await new Promise((resolve,reject)=>{
   let timer;
   const clean=()=>{clearTimeout(timer);realVideo.removeEventListener('loadedmetadata',yes);realVideo.removeEventListener('error',no)};
   const yes=()=>{clean();resolve()};
   const no=()=>{clean();reject(Error('Browser cannot read local video metadata'))};
   timer=setTimeout(()=>{clean();reject(Error('MP4 metadata load timed out'))},12000);
   realVideo.addEventListener('loadedmetadata',yes);realVideo.addEventListener('error',no);
  });
  if(!Number.isFinite(realVideo.duration)||realVideo.duration<=0||
     !realVideo.videoWidth||!realVideo.videoHeight)throw Error('Missing video dimensions/duration');
  currentButton.disabled=false;samplesButton.disabled=false;realVideo.pause();
  result.textContent='Local video loaded: '+realVideo.videoWidth+'×'+realVideo.videoHeight+
    ', '+realVideo.duration.toFixed(2)+' s. Compare at a chosen timeline point.';
 }catch(err){resetCompare();result.textContent='Local video rejected: '+err.message;}
});
function videoContract(){
 if(!comparisonUrl||realVideo.readyState<1)throw Error('Load a local final MP4 first');
 const total=valid();
 if(realVideo.videoWidth!==story.width||realVideo.videoHeight!==story.height)
  throw Error('MP4 resolution does not match the selected storyboard.');
 if(!Number.isFinite(realVideo.duration)||
    Math.abs(realVideo.duration-total)>Math.max(.3,2/story.fps))
  throw Error('MP4 duration does not match the selected storyboard.');
 return total;
}
function seekReal(time){
 return new Promise((resolve,reject)=>{
  const t=Math.max(0,Math.min(time,realVideo.duration-1/story.fps*.25));
  if(Math.abs(realVideo.currentTime-t)<.0001&&realVideo.readyState>=2){resolve();return;}
  let timer;
  const clean=()=>{clearTimeout(timer);realVideo.removeEventListener('seeked',yes);
    realVideo.removeEventListener('error',no);};
  const yes=()=>{clean();resolve()};
  const no=()=>{clean();reject(Error('Video decoding/seek failed'))};
  timer=setTimeout(()=>{clean();reject(Error('Local video frame seek timed out'))},12000);
  realVideo.addEventListener('seeked',yes);realVideo.addEventListener('error',no);
  realVideo.currentTime=t;
 });
}
async function compareOne(time,signature){
 if(JSON.stringify(story)!==signature)throw Error('Storyboard changed during comparison');
 await seekReal(time);
 if(JSON.stringify(story)!==signature)throw Error('Storyboard changed during comparison');
 draw(time);
 const width=320,height=Math.max(2,Math.min(600,Math.round(width*story.height/story.width)));
 const left=document.createElement('canvas'),right=document.createElement('canvas');
 left.width=right.width=width;left.height=right.height=height;
 const lctx=left.getContext('2d',{willReadFrequently:true});
 const rctx=right.getContext('2d',{willReadFrequently:true});
 if(!lctx||!rctx)throw Error('Pixel comparison unsupported in browser');
 lctx.drawImage(canvas,0,0,width,height);
 rctx.drawImage(realVideo,0,0,width,height);
 return {second:Math.round(time*1000)/1000,
         ...M.pixelDifference(lctx.getImageData(0,0,width,height).data,
                             rctx.getImageData(0,0,width,height).data)};
}
async function compareSelected(three){
 if(comparisonBusy)return;
 let total;try{total=videoContract()}catch(e){result.textContent=e.message;return;}
 comparisonBusy=true;halt();realVideo.pause();
 currentButton.disabled=true;samplesButton.disabled=true;
 const oldPosition=position,signature=JSON.stringify(story);
 try{
  const times=three?M.sampleTimes(story):[Math.min(position,total-.001)];
  const points=[];
  for(const t of times){
   result.textContent='Comparing local video frame at '+t.toFixed(2)+' seconds…';
   points.push(await compareOne(t,signature));
  }
  const avg=points.reduce((sum,p)=>sum+p.normalizedRgbMae,0)/points.length;
  const worst=Math.max(...points.map(p=>p.normalizedRgbMae));
  const warnings=points.filter(p=>p.reviewSuggested).length;
  result.textContent='Measured '+points.length+' frame pair(s). Mean RGB pixel difference '+
   (avg*100).toFixed(2)+'%, worst '+(worst*100).toFixed(2)+'%. '+
   warnings+' flagged for human review. Frames at '+
   points.map(p=>p.second.toFixed(2)+' s: '+(p.normalizedRgbMae*100).toFixed(1)+'%').join(' | ')+
   '. This is measured image discrepancy, NOT a parity guarantee or a rendering error.';
 }catch(e){result.textContent='Comparison incomplete: '+e.message;}
 finally{comparisonBusy=false;currentButton.disabled=!comparisonUrl;
   samplesButton.disabled=!comparisonUrl;draw(oldPosition);}
}
currentButton.onclick=()=>compareSelected(false);
samplesButton.onclick=()=>compareSelected(true);


// Opt-in, encrypted STORYBOARD-only checkpoints. Neither media nor passphrase
// enters storage; the derived AES key exists only until this page is closed.
const DRAFT_SLOT='nexus.motion.encrypted.storyboard.v1',DRAFT_MAX=240000;
const dStatus=(value,error=false)=>{const n=$('motion-draft-status');
 n.textContent=value;n.style.color=error?'#ffc5b4':'#b6e9de';};
function b64(bytes){let s='';for(let i=0;i<bytes.length;i+=8192)
 s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);}
function unb64(value,max){
 if(typeof value!=='string'||value.length>max*2||!/^[A-Za-z0-9+/]+={0,2}$/.test(value))
  throw Error('Invalid draft encoding');
 const bytes=Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 if(!bytes.length||bytes.length>max)throw Error('Invalid draft size');
 return bytes;
}
function readDraft(){
 const value=localStorage.getItem(DRAFT_SLOT);
 if(value===null)return null;
 if(value.length>400000)throw Error('Draft size exceeds safe limit');
 const obj=JSON.parse(value);
 if(!obj||obj.v!==1||Object.keys(obj).sort().join(',')!=='data,iv,salt,v')
  throw Error('Unsupported draft format');
 const salt=unb64(obj.salt,16),iv=unb64(obj.iv,12),data=unb64(obj.data,DRAFT_MAX+32);
 if(salt.length!==16||iv.length!==12)throw Error('Invalid encryption parameters');
 return {salt,iv,data};
}
function cryptoReady(){
 if(!globalThis.crypto?.subtle||typeof globalThis.crypto.getRandomValues!=='function')
  throw Error('Secure on-device cryptography unavailable');
}
async function deriveDraft(pass,salt){
 cryptoReady();
 if(pass.length<12||pass.length>128)throw Error('Passphrase must be 12–128 characters');
 const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),
                                      'PBKDF2',false,['deriveKey']);
 return crypto.subtle.deriveKey(
  {name:'PBKDF2',salt,hash:'SHA-256',iterations:240000},key,
  {name:'AES-GCM',length:256},false,['encrypt','decrypt']);
}
function stopDraft(){
 draftEnabled=false;draftKey=null;draftSalt=null;draftEpoch++;
 if(draftTimer!==null)clearTimeout(draftTimer);
 draftTimer=null;$('motion-draft-enable').textContent='Enable encrypted autosave';
}
async function saveDraft(ticket){
 if(!draftEnabled||!draftKey)return;
 try{
  M.validate(story);
  const payload=new TextEncoder().encode(JSON.stringify(story));
  if(payload.length>DRAFT_MAX)throw Error('Storyboard exceeds draft limit');
  cryptoReady();
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const data=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},draftKey,payload));
  if(!draftEnabled||ticket!==draftEpoch)return;
  localStorage.setItem(DRAFT_SLOT,JSON.stringify({v:1,
   salt:b64(draftSalt),iv:b64(iv),data:b64(data)}));
  dStatus('Encrypted storyboard saved locally. Original media is NOT included.');
 }catch(e){
  stopDraft();dStatus('Autosave stopped: '+e.message+'. Export project + media ZIP.',true);
 }
}
function queueDraftSave(){
 if(!draftEnabled)return;
 if(draftTimer!==null)clearTimeout(draftTimer);
 const ticket=++draftEpoch;
 draftTimer=setTimeout(()=>{draftTimer=null;void saveDraft(ticket);},750);
}
$('motion-draft-enable').addEventListener('click',async()=>{
 const button=$('motion-draft-enable'),input=$('motion-draft-pass'),confirm=$('motion-draft-confirm');
 if(draftEnabled){stopDraft();dStatus('Autosave paused; last encrypted checkpoint remains.');return;}
 button.disabled=true;
 try{
  if(readDraft())throw Error('Draft already exists. Restore or delete it first');
  if(input.value!==confirm.value)throw Error('Passphrases do not match');
  cryptoReady();
  const salt=crypto.getRandomValues(new Uint8Array(16));
  const key=await deriveDraft(input.value,salt);
  draftKey=key;draftSalt=salt;draftEnabled=true;
  button.textContent='Pause encrypted autosave';
  await saveDraft(++draftEpoch);
 }catch(e){stopDraft();dStatus('Autosave not enabled: '+e.message,true);}
 finally{input.value='';confirm.value='';button.disabled=false;}
});
$('motion-draft-restore').addEventListener('click',async()=>{
 const input=$('motion-draft-pass'),confirm=$('motion-draft-confirm'),
  button=$('motion-draft-restore');
 button.disabled=true;
 try{
  if(draftEnabled)throw Error('Pause autosave before restoring');
  const record=readDraft();
  if(!record)throw Error('No encrypted draft found in this origin');
  if(!$('motion-draft-ack').checked)throw Error('Check the explicit Restore/Delete confirmation first');
  $('motion-draft-ack').checked=false;
  const key=await deriveDraft(input.value,record.salt);
  let plain;
  try{plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:record.iv},key,record.data);}
  catch{throw Error('Wrong passphrase or corrupted encrypted draft');}
  if(plain.byteLength>DRAFT_MAX)throw Error('Restored draft too large');
  const recovered=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(plain));
  M.validate(recovered);
  for(const image of Object.values(images))
   if(image?.src?.startsWith('blob:'))URL.revokeObjectURL(image.src);
  if(audioUrl)URL.revokeObjectURL(audioUrl);
  photoFiles.clear();images={};audioFile=null;audioUrl=null;
  setStory(recovered);
  draftKey=key;draftSalt=record.salt;draftEnabled=true;draftEpoch++;
  $('motion-draft-enable').textContent='Pause encrypted autosave';
  dStatus('Restored encrypted storyboard. Autosave resumed. Re-import original photos and audio.');
 }catch(e){dStatus('Restore rejected: '+e.message,true);}
 finally{input.value='';confirm.value='';button.disabled=false;}
});
$('motion-draft-clear').addEventListener('click',()=>{
 if(!$('motion-draft-ack').checked){
  dStatus('Check the explicit Restore/Delete confirmation before deleting.',true);return;
 }
 $('motion-draft-ack').checked=false;
 try{localStorage.removeItem(DRAFT_SLOT);stopDraft();
  dStatus('Encrypted local draft deleted; current storyboard remains in memory.');
 }catch(e){dStatus('Could not delete draft: '+e.message,true);}
});
$('motion-scenes').addEventListener('change',queueDraftSave);
for(const id of ['motion-title','motion-format','motion-fps'])
 $(id).addEventListener('change',queueDraftSave);
for(const id of ['motion-add','motion-remove','motion-example'])
 $(id).addEventListener('click',queueDraftSave);
try{dStatus(readDraft()?'Encrypted draft found. Enter passphrase and Restore & resume autosave.':
 'Autosave off. Enable with passphrase or export project + media ZIP.');}
catch(e){dStatus('Stored draft unavailable: '+e.message+'; delete explicitly if needed.',true);}

setStory(M.DEFAULT());
})();
