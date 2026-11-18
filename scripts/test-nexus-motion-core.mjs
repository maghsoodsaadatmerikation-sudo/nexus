import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import '../web/motion-core.js';
const M=globalThis.NexusMotion;
let count=0;
const check=fn=>{fn();count++};
const sample=M.DEFAULT();
check(()=>assert.equal(sample.schema,M.SCHEMA));
check(()=>assert.equal(M.validate(sample),13));
check(()=>assert.equal(M.locate(sample,0).index,0));
check(()=>assert.equal(M.locate(sample,4).index,1));
check(()=>assert.equal(M.locate(sample,9).index,2));
check(()=>assert.equal(M.locate(sample,500).index,2));
check(()=>assert.equal(M.locate(sample,5).local,1));
check(()=>assert.equal(M.FPS.includes(60),true));
check(()=>assert(M.PRESETS['4K'][0]===3840));
check(()=>assert(M.PRESETS['Vertical 4K'][1]===3840));
check(()=>assert(M.validate({...sample,width:3840,height:2160,fps:60})===13));
check(()=>assert(M.validate({...sample,width:2160,height:3840})===13));
const bad=fn=>{assert.throws(fn);count++};
bad(()=>M.validate({...sample,secretToken:'n'}));
bad(()=>M.validate({...sample,fps:120}));
bad(()=>M.validate({...sample,width:9999}));
bad(()=>M.validate({...sample,scenes:[]}));
bad(()=>M.validate({...sample,scenes:sample.scenes.repeat}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],duration:0}]}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],duration:true}]}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],motion:'arbitrary'}]}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],background:'#xyz'}]}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],title:'<'.repeat(121)}]}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],image:'../secret.png'}]}));
bad(()=>M.validate({...sample,scenes:[{...sample.scenes[0],image:'https://bad.test/a.png'}]}));
bad(()=>M.validate({...sample,soundtrack:'../../key.mp3'}));
const tooMany=[...sample.scenes,...Array.from({length:118},()=>({...sample.scenes[0]}))];
bad(()=>M.validate({...sample,scenes:tooMany}));
const accepted={...sample,scenes:[{...sample.scenes[0],image:'assets/My Film 2.png'}],soundtrack:'assets/voice.wav'};
check(()=>assert.equal(M.validate(accepted),4));
const timeline={...sample,scenes:[{...sample.scenes[0],duration:900},...Array.from({length:7},()=>({...sample.scenes[1],duration:900}))]};
check(()=>assert.equal(M.validate(timeline),7200));
bad(()=>M.validate({...timeline,scenes:[...timeline.scenes,{...sample.scenes[0]}]}));
function fakeCtx(){
 const calls=[];return {canvas:{width:960,height:540},calls,
  createLinearGradient(){return {addColorStop(){}}},createRadialGradient(){return {addColorStop(){}}},
  save(){},restore(){},fillRect(){calls.push('rect')},clearRect(){},
  beginPath(){},arc(){},ellipse(){},fill(){},stroke(){},translate(){},rotate(){},scale(){},
  fillText(text){calls.push(text)},measureText(text){return {width:text.length*10}},
  set fillStyle(v){},set globalAlpha(v){},set strokeStyle(v){},set lineWidth(v){},
  set textAlign(v){},set textBaseline(v){},set shadowColor(v){},set shadowBlur(v){},set font(v){}
 };
}
let ctx=fakeCtx();
check(()=>assert.equal(M.frame(ctx,sample,0).index,0));
check(()=>assert(ctx.calls.includes('BEFORE THE LIGHT')));
const again=fakeCtx();M.frame(again,sample,0);
check(()=>assert.deepEqual(ctx.calls,again.calls));
const budget=M.resourceEstimate(sample);
check(()=>assert.equal(budget.expectedFrames,390));
check(()=>assert(budget.estimatedPeakBytes>budget.estimatedVideoBytes));
check(()=>assert.equal(budget.hardUpperBound,false));
check(()=>assert.equal(budget.knownAvailableDiskBytes,null));
check(()=>assert.equal(M.resourceEstimate({...sample,width:3840,height:2160,fps:60}).suggestedBatchScenes,1));
check(()=>assert(M.resourceEstimate({...sample,width:3840,height:2160,fps:60}).estimatedPeakBytes>budget.estimatedPeakBytes));
check(()=>assert.equal(M.resourceEstimate({...sample,soundtrack:'assets/voice.wav'}).estimatedPeakBytes>budget.estimatedPeakBytes,true));
const source=await readFile(new URL('../web/motion-core.js',import.meta.url),'utf8');
const ui=await readFile(new URL('../web/motion-ui.js',import.meta.url),'utf8');
const page=await readFile(new URL('../web/motion.html',import.meta.url),'utf8');
check(()=>assert(!/fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|api\.suno|cloud-video/i.test(source+ui)));
check(()=>assert(page.includes("connect-src 'none'")));
check(()=>assert(page.includes('id="motion-record"')&&page.includes('id="motion-export-zip"')));
const rust=await readFile(new URL('../artifact-05/src/lib.rs',import.meta.url),'utf8');
check(()=>assert(rust.includes('.route("/motion", get(motion_workspace))')));
check(()=>assert(rust.includes('include_str!("../../web/motion.html")')));
console.log(JSON.stringify({status:'PASS',checks:count,local_only:true,ai_video_model_used:false}));
