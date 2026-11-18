/* NEXUS Motion UI — offline browser video workflow, no network/no storage. */
(()=>{'use strict';
const M=globalThis.NexusMotion, $=id=>document.getElementById(id);
if(!M||!$('motion-canvas'))return;
let story=M.DEFAULT(),images={},photoFiles=new Map(),audioFile=null,audioUrl=null;
let running=false,tick=0,startClock=0,position=0,recording=false,cancelRecord=false,recorder=null;
const canvas=$('motion-canvas'),ctx=canvas.getContext('2d',{alpha:false});
const status=(msg,error=false)=>{const p=$('motion-status');p.textContent=msg;p.style.color=error?'#ffc5b4':'#b6e9de'};
const secs=t=>{const n=Math.floor(Math.max(0,t));return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0')};
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
 try{if(file.size>256000)throw Error('Project JSON exceeds 256 KB');setStory(JSON.parse(await file.text()));}
 catch(err){status('Import rejected: '+err.message,true)}
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
 audioFile=file;story.soundtrack='assets/'+file.name;status('Original audio selected; no voice transformation or remote upload.');
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
setStory(M.DEFAULT());
})();
