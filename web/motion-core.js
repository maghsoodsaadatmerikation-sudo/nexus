/* NEXUS Motion v1: pure local storyboard validation and procedural Canvas renderer.
   No external API, storage, network, WebGL shaders, facial alteration or paid model. */
'use strict';
globalThis.NexusMotion = (() => {
  const SCHEMA='nexus.motion.storyboard.v1';
  const PRESETS=Object.freeze({'HD':[1280,720], 'Full HD':[1920,1080], '4K':[3840,2160], 'Vertical HD':[1080,1920], 'Vertical 4K':[2160,3840]});
  const FPS=[24,25,30,60];
  const MOTIONS=['still','push','pull','pan-left','pan-right'];
  const DEFAULT=()=>({
    schema:SCHEMA,title:'NEXUS — A Journey',width:1920,height:1080,fps:30,
    scenes:[
      {duration:4,background:'#061125',accent:'#67d2c3',title:'BEFORE THE LIGHT',subtitle:'A story in motion',motion:'push'},
      {duration:5,background:'#10203d',accent:'#f0c584',title:'THE TURNING POINT',subtitle:'Silence becomes movement',motion:'pan-right'},
      {duration:4,background:'#17223a',accent:'#c4b6fa',title:'AFTER THE ECHO',subtitle:'And the story continues',motion:'pull'}
    ]
  });
  const allowed=new Set(['duration','background','accent','title','subtitle','motion','image']);
  const color=/^#[0-9a-fA-F]{6}$/;
  const media=/^[A-Za-z0-9 _().+\/@-]{1,180}$/;
  const cleanName=x=>typeof x==='string'&&media.test(x)&&!x.startsWith('/')&&!x.includes('\\')&&
    x.split('/').every(s=>s!=='.'&&s!=='..');
  const int=(v,a,b)=>Number.isInteger(v)&&v>=a&&v<=b;
  const words=(v,max,optional=false)=>typeof v==='string'&&
    (optional?v.length>=0:v.length>0)&&v.length<=max&&
    [...v].every(ch=>ch==='\n'||ch.charCodeAt(0)>=32)&&!v.includes('\r');
  function validate(value){
    if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Storyboard must be an object');
    if(Object.keys(value).some(k=>!['schema','title','width','height','fps','scenes','soundtrack'].includes(k))||
      value.schema!==SCHEMA)throw Error('Unsupported storyboard schema/keys');
    if(!words(value.title,100))throw Error('Title must be 1–100 characters');
    if(!Object.values(PRESETS).some(([w,h])=>value.width===w&&value.height===h))
      throw Error('Choose a supported HD, 4K or vertical resolution');
    if(!FPS.includes(value.fps))throw Error('Unsupported frame rate');
    if(!Array.isArray(value.scenes)||value.scenes.length<1||value.scenes.length>120)
      throw Error('Need 1–120 scenes');
    let duration=0;
    for(const s of value.scenes){
      if(!s||typeof s!=='object'||Array.isArray(s)||
         Object.keys(s).some(k=>!allowed.has(k)))throw Error('Unsupported scene');
      if(!int(s.duration,1,900)||!color.test(s.background)||!color.test(s.accent)||
         !words(s.title,120)||!words(s.subtitle||'',180,true)||
         !MOTIONS.includes(s.motion))throw Error('Invalid scene timing, color or typography');
      if(s.image!==undefined&&s.image!==''&&(!cleanName(s.image)||
         !/\.(png|jpe?g|webp)$/i.test(s.image)))throw Error('Invalid local image path');
      duration+=s.duration;
    }
    if(duration>7200)throw Error('Two-hour maximum: split larger projects');
    if(value.soundtrack!==undefined&&value.soundtrack!==''&&
       (!cleanName(value.soundtrack)||!(/\.(mp3|wav|m4a|flac|ogg|aac)$/i).test(value.soundtrack)))
      throw Error('Invalid local soundtrack');
    return duration;
  }
  function resourceEstimate(story){
    // Browser has no reliable authority to know actual available filesystem
    // capacity. This matches the *assumptions* of the Python CLI planner,
    // not a measured output size or a guarantee.
    const duration=validate(story);
    const {width,height,fps}=story;
    const rate=Math.ceil(12000000*width*height*fps/(1920*1080*30));
    const video=Math.ceil(rate*duration/8);
    const audio=story.soundtrack?32000*duration:0;
    const reserve=512*1048576+Math.min(2*1073741824,Math.floor(video/4));
    const peak=(story.soundtrack?3:2)*video+audio+reserve;
    return Object.freeze({
      durationSeconds:duration,
      expectedFrames:duration*fps,
      estimatedVideoBytes:video,
      estimatedPeakBytes:peak,
      rawRgbaFrameBytes:width*height*4,
      assumedMbps:Math.round(rate/10000)/100,
      suggestedBatchScenes:width*height>=3840*2160?1:width*height>=1920*1080?3:5,
      knownAvailableDiskBytes:null,
      hardUpperBound:false,
      androidThermalBenchmarked:false
    });
  }
  function sampleTimes(story){
    validate(story);
    // One mid-scene timestamp per selected scene: avoids deliberately
    // black fade edges and limits seek/decode on mobile devices.
    const n=story.scenes.length;
    const indexes=[0,Math.floor((n-1)/2),n-1].filter((x,i,a)=>a.indexOf(x)===i);
    let offset=0;
    const starts=story.scenes.map(s=>{const v=offset;offset+=s.duration;return v;});
    return indexes.map(i=>Math.min(offset-.001,starts[i]+story.scenes[i].duration/2));
  }
  function pixelDifference(a,b){
    if(!(a instanceof Uint8ClampedArray||a instanceof Uint8Array)||
       !(b instanceof Uint8ClampedArray||b instanceof Uint8Array)||
       a.length!==b.length||a.length<4||a.length%4!==0||
       a.length>640*480*4)throw Error('Invalid bounded RGBA frame pair');
    let absolute=0,squared=0,high=0;
    const total=a.length/4;
    for(let i=0;i<a.length;i+=4){
      let pixel=0;
      for(let channel=0;channel<3;channel++){
        const d=Math.abs(a[i+channel]-b[i+channel]);
        absolute+=d;squared+=d*d;pixel+=d;
      }
      if(pixel/(3*255)>=.25)high++;
    }
    const mae=absolute/(total*3*255);
    return Object.freeze({
      normalizedRgbMae:Math.round(mae*1000000)/1000000,
      normalizedRgbRmse:Math.round(Math.sqrt(squared/(total*3))/255*1000000)/1000000,
      pixelsCompared:total,
      highDifferencePixelFraction:Math.round(high/total*1000000)/1000000,
      reviewSuggested:mae>=.08,
      pixelParityProven:false,
      artisticQualityAssessed:false,
      onlyOneFrameCompared:true
    });
  }
  function locate(story,time){
    const total=validate(story);const t=Math.min(Math.max(0,Number(time)||0),Math.max(0,total-1e-6));
    let offset=0;
    for(let i=0;i<story.scenes.length;i++){
      let s=story.scenes[i];
      if(t<offset+s.duration)return {scene:s,index:i,local:t-offset,elapsed:t,total,progress:(t-offset)/s.duration};
      offset+=s.duration;
    }
    throw Error('Invalid timeline');
  }
  function hash(seed){seed=Math.imul(seed^seed>>>16,0x45d9f3b);seed=Math.imul(seed^seed>>>16,0x45d9f3b);return ((seed^seed>>>16)>>>0)/4294967296}
  function wrap(ctx,text,maxWidth,maxLines){
    const out=[];for(const paragraph of String(text).split('\n')){
      let line='';for(const word of paragraph.split(/\s+/).filter(Boolean)){
        const n=line?line+' '+word:word;
        if(ctx.measureText(n).width>maxWidth&&line){out.push(line);line=word;}else line=n;
        if(out.length>=maxLines)break;
      }
      if(out.length>=maxLines)break;if(line)out.push(line);
    }
    return out.slice(0,maxLines);
  }
  function frame(ctx,story,time,{images={}}={}){
    const at=locate(story,time),{scene,progress,index,local}=at;
    const W=ctx.canvas.width,H=ctx.canvas.height,unit=W/1920;
    ctx.save();ctx.globalAlpha=1;ctx.clearRect(0,0,W,H);
    // Gradient/vignette and layered geometric shapes are ORIGINAL procedural art.
    const grad=ctx.createLinearGradient(0,0,W,H);
    grad.addColorStop(0,scene.background);
    grad.addColorStop(1,'#02050d');ctx.fillStyle=grad;ctx.fillRect(0,0,W,H);
    const glow=ctx.createRadialGradient(W*(.26+progress*.25),H*.32,W*.03,W*.52,H*.48,W*.8);
    glow.addColorStop(0,scene.accent+'88');glow.addColorStop(.35,scene.accent+'30');
    glow.addColorStop(1,'#00000000');ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);

    // Fully locally loaded stills; default contain preserves the original frame/face.
    const img=scene.image&&images[scene.image];
    if(img&&img.complete&&img.naturalWidth&&img.naturalHeight){
      const scale=Math.min(W/img.naturalWidth,H/img.naturalHeight),dw=img.naturalWidth*scale,dh=img.naturalHeight*scale;
      const zoom=scene.motion==='push'?1+.06*progress:scene.motion==='pull'?1.06-.06*progress:
                 scene.motion==='still'?1:1.035;
      const dx=scene.motion==='pan-left'?-progress*.03*W:scene.motion==='pan-right'?progress*.03*W:0;
      ctx.save();ctx.globalAlpha=.78;ctx.translate(W/2+dx,H/2);ctx.scale(zoom,zoom);
      ctx.drawImage(img,-dw/2,-dh/2,dw,dh);ctx.restore();
      ctx.fillStyle='rgba(0,0,0,.28)';ctx.fillRect(0,0,W,H);
    }else{
      // Fixed-seed parallax motion, deterministic per requested timestamp.
      for(let i=0;i<70;i++){
        const seed=i+index*197,layer=1+(i%4),x=(hash(seed*71)*W+time*layer*W*.0009)%W;
        const y=(hash(seed*43)*H+Math.sin(time*.4+seed)*H*.012+H)%H;
        const radius=Math.max(.75,unit*(.8+hash(seed*19)*2.8));
        ctx.beginPath();ctx.arc(x,y,radius,0,2*Math.PI);
        ctx.fillStyle=scene.accent;ctx.globalAlpha=.08+hash(seed*11)*.42;ctx.fill();
      }
      ctx.globalAlpha=.14;ctx.strokeStyle=scene.accent;ctx.lineWidth=Math.max(1,unit*3);
      ctx.save();ctx.translate(W*.5,H*.51);ctx.rotate(time*.018);
      for(let n=0;n<3;n++){ctx.beginPath();ctx.ellipse(0,0,W*(.15+n*.1),H*(.17+n*.09),n*.35,0,Math.PI*2);ctx.stroke();}
      ctx.restore();ctx.globalAlpha=1;
    }
    const fade=Math.min(1,local/.42,(scene.duration-local)/.42);ctx.globalAlpha=Math.max(0,fade);
    const titleSize=Math.max(21,Math.round(W*.052));
    ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowColor='rgba(0,0,0,.8)';ctx.shadowBlur=W*.01;
    ctx.fillStyle='#ffffff';ctx.font='600 '+titleSize+'px system-ui, sans-serif';
    const lines=wrap(ctx,scene.title,W*.82,3);
    let top=H*.44-(lines.length-1)*titleSize*.61;
    for(const line of lines){ctx.fillText(line,W*.5,top,W*.86);top+=titleSize*1.22;}
    if(scene.subtitle){
      ctx.font='400 '+Math.max(15,Math.round(W*.024))+'px system-ui,sans-serif';
      ctx.fillStyle=scene.accent;
      for(const [i,line] of wrap(ctx,scene.subtitle,W*.8,2).entries())
        ctx.fillText(line,W*.5,H*.67+i*Math.max(22,W*.034),W*.85);
    }
    ctx.globalAlpha=1;ctx.fillStyle=scene.accent;
    ctx.fillRect(W*.12,H*.83,W*.76*(at.elapsed/at.total),Math.max(2,W*.002));
    ctx.restore();return at;
  }
  return Object.freeze({SCHEMA,PRESETS,FPS,MOTIONS,DEFAULT,validate,resourceEstimate,sampleTimes,pixelDifference,locate,frame});
})();
