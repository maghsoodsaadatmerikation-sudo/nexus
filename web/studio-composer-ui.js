/* NEXUS Studio: honest chat composer and explicit archive shortcut.
 * Presentation only. All executions delegate to the existing reviewed actions.
 */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const required=['conversation-card','message','guide','prepare','request-review','consent',
 'send-model','save','vault-card','language','branch-notice'];
if(required.some(id=>!$(id))||!window.NexusStudioUI?.uiStatus)return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const box=document.createElement('section');box.id='studio-compose';box.className='studio-compose';
box.setAttribute('aria-label','Conversation actions');
const mode=document.createElement('details'),heading=document.createElement('summary');heading.id='studio-compose-heading';
const row=document.createElement('div');row.className='studio-compose-row';
const selectLabel=document.createElement('label');selectLabel.htmlFor='studio-compose-mode';
const select=document.createElement('select');select.id='studio-compose-mode';
for(const [value,en,fa] of [
 ['guide','Local reflection guide','راهنمای تأمل محلی'],
 ['model','Connected AI model (requires approval)','مدل متصل (نیازمند تأیید)']
]){const o=document.createElement('option');o.value=value;o.dataset.en=en;o.dataset.fa=fa;select.append(o)}
const send=document.createElement('button');send.type='button';send.id='studio-compose-send';
const save=document.createElement('button');save.type='button';save.id='studio-compose-save';save.className='secondary';
const config=document.createElement('button');config.type='button';config.id='studio-compose-config';config.className='secondary';
const modelStrip=document.createElement('div');modelStrip.id='studio-compose-model-info';modelStrip.className='studio-compose-model-info';modelStrip.hidden=true;
const modelState=document.createElement('p');modelState.id='studio-compose-model-state';modelState.className='help';modelState.setAttribute('role','status');modelState.setAttribute('aria-live','polite');
const modelCheck=document.createElement('button');modelCheck.id='studio-compose-model-check';modelCheck.type='button';modelCheck.className='secondary';
const modelSelectLabel=document.createElement('label');modelSelectLabel.id='studio-compose-choice-label';modelSelectLabel.htmlFor='studio-compose-choice';modelSelectLabel.hidden=true;
const modelSelectTitle=document.createElement('span');modelSelectTitle.textContent=words('Model','مدل');
const modelSelect=document.createElement('select');modelSelect.id='studio-compose-choice';
modelSelectLabel.append(modelSelectTitle,modelSelect);
modelStrip.append(modelState,modelSelectLabel,modelCheck);
const privacy=document.createElement('p');privacy.id='studio-compose-privacy';privacy.className='help';
privacy.setAttribute('role','note');
const storage=document.createElement('p');storage.id='studio-compose-storage';storage.className='help';storage.setAttribute('role','status');storage.setAttribute('aria-live','polite');
selectLabel.append(select);row.append(send,save);
mode.append(heading,selectLabel,config,privacy);
box.append(row,modelStrip,mode,storage);
$('branch-notice').after(box);

/* Discover capability from a typed request; proposal only, never execute. */
const suggestions=document.createElement('div');suggestions.id='nexus-zen-suggestions';
box.prepend(suggestions);
const offer=document.createElement('div');offer.id='nexus-zen-offer';offer.hidden=true;offer.setAttribute('role','status');box.after(offer);
// One reviewed discovery catalog: command, UI destination, languages, prompt field, aliases.
// Listing a capability never proves model or provider availability or grants execution.
const routes=Object.freeze([
 ['orchestra','orchestra-card','Orchestra & vocal','ارکستر و آواز','orchestra-prompt','vocal'],
 ['music','music-card','Music Lab','موسیقی',null,'song'],
 ['research','research-card','Research','پژوهش','research-query','search'],
 ['data','data-card','Data analysis','تحلیل داده',null,'analyze'],
 ['chart','chart-card','Charts','نمودارها',null,''],
 ['code','code-card','Code','کدنویسی',null,''],
 ['remind','reminders-card','Reminders','یادآورها','reminder-title','reminders'],
 ['tasks','tasks-card','Tasks','وظایف',null,'task'],
 ['write','canvas-card','Writing','نوشتن',null,''],
 ['sources','sources-card','Sources','منابع',null,''],
 ['astrology','astrology-card','Astrology','اخترشناسی',null,''],
 ['sky','sky-card','Sky','آسمان',null,''],
 ['memory','profile-card','Memory','حافظه',null,''],
 ['github','studio-connections','GitHub','گیت‌هاب',null,'repo'],
 ['render','studio-connections','Render','رندر',null,'deploy'],
 ['connections','studio-connections','Connections','اتصال‌ها',null,'connect'],
 ['tools','studio-tool-directory','Capabilities','قابلیت‌ها',null,'help capabilities']
].map(row=>Object.freeze(row)));
for(const id of ['music','research','data']){
 const [,panel,en,fa]=routes.find(row=>row[0]===id);
 const b=document.createElement('button');b.type='button';b.className='secondary';b.dataset.en=en;b.dataset.fa=fa;
 b.addEventListener('click',()=>window.NexusStudioFocus?.openPanel(panel));
 suggestions.append(b);
}

/* Explicit local checkpoint UI. The file is NOT an encrypted vault backup. */
const restoreButton=document.createElement('button');
restoreButton.id='studio-workflow-restore';restoreButton.type='button';
restoreButton.className='secondary';restoreButton.dataset.en='Restore workflow';
restoreButton.dataset.fa='بازیابی گردش‌کار';suggestions.append(restoreButton);
const restoreFile=document.createElement('input');
restoreFile.type='file';restoreFile.accept='.json,application/json';restoreFile.hidden=true;
restoreFile.id='studio-workflow-restore-file';
restoreFile.setAttribute('aria-label','Choose a NEXUS workflow checkpoint');
const restoreStatus=document.createElement('p');
restoreStatus.id='studio-workflow-restore-status';restoreStatus.className='help';
restoreStatus.setAttribute('role','status');
box.append(restoreFile,restoreStatus);
restoreButton.onclick=()=>{
 const state=window.NexusStudioUI.uiStatus();
 if(state&&!state.busy&&!state.attachmentLoading&&!state.archived)restoreFile.click();
};
const catalog=Object.freeze(routes.filter(row=>row[0]!=='tools').map(
 row=>Object.freeze({command:row[0],en:row[2],fa:row[3],
  kind:row[1]==='studio-connections'?'connection-review':'local-review'})));
const directory=document.createElement('section');directory.id='studio-capability-directory';
directory.hidden=true;directory.setAttribute('aria-label','Available capabilities');
const directoryTitle=document.createElement('strong'),directoryNote=document.createElement('p'),
 directoryItems=document.createElement('div'),directoryClose=document.createElement('button');
directoryClose.type='button';directoryClose.className='secondary';
directory.append(directoryTitle,directoryNote,directoryItems,directoryClose);offer.after(directory);
const directoryToggle=document.createElement('button');
directoryToggle.id='studio-open-capability-directory';
directoryToggle.type='button';directoryToggle.className='secondary';
directoryToggle.dataset.en='All tools';directoryToggle.dataset.fa='همهٔ ابزارها';
directoryToggle.setAttribute('aria-controls',directory.id);
suggestions.append(directoryToggle);
function closeDirectory(){
 directory.hidden=true;directoryItems.replaceChildren();
 directoryToggle.setAttribute('aria-expanded','false');
}
closeDirectory();
directoryToggle.onclick=()=>{
 if(directory.hidden){clearOffer();showDirectory()}
 else closeDirectory();
};
directoryClose.onclick=()=>{closeDirectory();directoryToggle.focus()};
function showDirectory(){
 closeDirectory();directory.hidden=false;
 directoryToggle.setAttribute('aria-expanded','true');
 directory.setAttribute('aria-label',words('Available capabilities','قابلیت‌های در دسترس'));
 directoryTitle.textContent=words('NEXUS capabilities','قابلیت‌های نکسوس');
 directoryNote.textContent=words('Choose a command to fill the chat. Nothing runs until you review and approve it.',
  'یک فرمان را برای درج در گفتگو انتخاب کن. تا بازبینی و تأیید، هیچ کاری اجرا نمی‌شود.');
 directoryClose.textContent=words('Close','بستن');
 for(const item of catalog){
  const b=document.createElement('button');b.type='button';b.className='secondary';
  b.textContent='/'+item.command+' · '+words(item.en,item.fa)+' · '+
   (item.kind==='connection-review'?words('Connection review','بازبینی اتصال'):words('Tool review','بازبینی ابزار'));
  b.onclick=()=>{
   const draft=$('message').value.trim();
   if(draft&&!/^\/(tools|help|capabilities)$/i.test(draft)&&
      !confirm(words('Replace your unsent message with this command?','این فرمان جایگزین پیام ارسال‌نشده شود؟')))return;
   $('message').value='/'+item.command+' ';
   $('message').dispatchEvent(new Event('input',{bubbles:true}));
   closeDirectory();$('message').focus();
  };
  directoryItems.append(b);
 }
 directoryItems.firstElementChild.focus();
}
const explicitResearch=/^(?:search\s+(?:the\s+web\s+)?for|جست[\s\u200c]*و[\s\u200c]*جو\s+کن)\s+(.+)$/is;
function intent(value){
 const message=value.trim();
 const slash=/^\/([a-z-]+)(?:\s|$)/i.exec(message);
 if(slash){
  const command=slash[1].toLowerCase();
  const route=routes.find(x=>x[0]===command||(x[5]||'').split(' ').includes(command));
  return route?{route,query:message.slice(slash[0].length).trim()}:null;
 }
 const search=explicitResearch.exec(message);
 if(search)return {route:routes.find(row=>row[0]==='research'),query:search[1]};
 const reminder=/^(?:remind me (?:to )?|set (?:a )?reminder(?: for)?\s+|یادآوری کن\s+)(.+)$/i.exec(message);
 if(reminder)return {route:routes.find(row=>row[0]==='remind'),query:reminder[1]};
 if(window.NexusStudio.asksForChoice(message))return null;
 const s=message.slice(0,340).toLocaleLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/\u200c/g,' ');
 if(!/(بساز|ساخت|تولید|طراحی|بنویس|تنظیم|compose|create|make|generate|write|analy[sz]e|search|find|draw|run|open|launch|list|show|check|اجرا|بررسی|تحلیل|نمایش|نشان\s*بده|وضعیت|باز\s*کن|بازکردن|برو\s+به|جست\s*و\s*جو)/i.test(s))return null;
 const kind=/(github|گیت\s*هاب|گیتهاب|pull requests?|درخواست(?:‌|\s)*ادغام)/i.test(s)?'github':
  /(render|رندر|deployment|deploy)/i.test(s)?'render':
  /(ارکستر|گروه کر|وکال|orchestra|choir|vocal)/i.test(s)?'orchestra':
  /(آهنگ|اهنگ|موسیقی|ملودی|music|song|melody)/i.test(s)?'music':
  /(چارت تولد|طالع|astrology|transit)/i.test(s)?'astrology':
  /(نمودار|chart|graph)/i.test(s)?'chart':
  /(کدنویسی|برنامه نویسی|code|javascript|python)/i.test(s)?'code':
  /(csv|tsv|json|داده|فایل|dataset|spreadsheet|data\s+analysis)/i.test(s)?'data':
  /(پژوهش|منبع علمی|research|wikipedia|crossref)/i.test(s)?'research':
  /(داستان|متن بنویس|essay|story|draft|writing\s+canvas|ویرایشگر\s+متن)/i.test(s)?'write':
  /(وظایف|task|workflow)/i.test(s)?'tasks':
  /(یادآور|reminders?)/i.test(s)?'remind':
  /(اتصال(?:ات)?|connections?)/i.test(s)?'connections':
  /(منابع|sources)/i.test(s)?'sources':
  /(حافظه|memory)/i.test(s)?'memory':
  /(آسمان|\bsky\b)/i.test(s)?'sky':null;
 const route=routes.find(x=>x[0]===kind);
 const prefix=kind==='research'?/^find\s+/i.exec(message):null;
 const query=kind==='research'||kind==='orchestra'?message.slice(prefix?.[0].length||0):'';
 return route?{route,query}:null;
}
/* Advisory mapping only; no operation is executed from text classification.
 * The connection dialog verifies actual provider permissions after a separate
 * user-triggered catalog load and requires explicit review before each action.
 */
function connectionRequest(result,message){
 const kind=result.route[0];
 if(kind==='connections')return {};
 if(kind==='render')return {provider:'render',operation:'render.deploys'};
 if(kind!=='github')return null;
 const text=message.replace(/^\/[a-z-]+\s*/i,'').slice(0,340).toLocaleLowerCase();
 const operation=/(?:edit|commit|ویرایش|اصلاح\s+فایل|تغییر\s+فایل)/i.test(text)?'github.edit':
  /(?:branch|شاخه)/i.test(text)?'github.branch':
  /(?:file|readme|فایل)/i.test(text)?'github.file':
  /(?:pull\s*requests?|\bpr\b|درخواست(?:‌|\s)*ادغام)/i.test(text)?'github.pulls':null;
 return {provider:'github',operation};
}

/* Review-only multi-step chat checklist. This is not autonomous planning:
 * each step is a reviewed slash command supplied by the human. No work runs
 * from parsing, opening, or marking a step; tools enforce their own consent.
 */
const workflow=document.createElement('section');
workflow.id='studio-chat-workflow';workflow.className='studio-compose';
workflow.hidden=true;workflow.setAttribute('aria-label','Reviewed workflow');
directory.after(workflow);
let workflowState=null,workflowImportEpoch=0;
const WORKFLOW_SCHEMA='nexus.studio.workflow-checkpoint.v1';
function workflowScope(){
 const selection=window.NexusStudioUI.selection?.()||{};
 return JSON.stringify([selection.projectId||null,selection.threadId||null]);
}
function isWorkflowRequest(message){return /^\/plan(?:\s|$)/i.test(message.trimStart())}
function parseWorkflow(message){
 const lines=message.replace(/\r\n?/g,'\n').split('\n');
 if(lines[0].trim().toLowerCase()!=='/plan'||lines.length<3||lines.length>7||
    message.length>1900)return {error:'Use /plan on its own line, then 2–6 tool commands on separate lines.'};
 const steps=[];
 for(const raw of lines.slice(1)){
  const line=raw.trim();
  if(!line||line.length>260||/[\x00-\x1f\x7f]/.test(line)||
     !/^\/[a-z-]+(?:[ \t]+\S.*)?$/i.test(line))
   return {error:'Every step must be a short /tool command; empty or unrecognized steps are rejected.'};
  const result=intent(line);
  if(!result||result.route[0]==='tools')
   return {error:'Unknown workflow tool. Use All tools to choose a supported /command.'};
  steps.push({line,result});
 }
 return {steps};
}
function clearWorkflow(){
 workflowImportEpoch++;workflowState=null;workflow.hidden=true;workflow.replaceChildren();
}
function retainedWorkflow(){
 const state=window.NexusStudioUI.uiStatus();
 return Boolean(workflowState&&state&&!state.archived&&
  $('message').value===workflowState.draft&&workflowScope()===workflowState.scope);
}
function validWorkflow(){
 const state=window.NexusStudioUI.uiStatus();
 return Boolean(retainedWorkflow()&&state&&!state.busy&&!state.attachmentLoading);
}
function workflowError(reason){
 clearWorkflow();workflow.hidden=false;
 const p=document.createElement('p');p.textContent=words(reason,reason);
 const close=document.createElement('button');close.type='button';close.className='secondary';
 close.textContent=words('Close','بستن');close.onclick=()=>{clearWorkflow();$('message').focus()};
 workflow.append(p,close);
}
function openReviewedSurface(result,message){
 const state=window.NexusStudioUI.uiStatus();
 if(!state||state.busy||state.attachmentLoading||state.archived)return false;
 const [,panel,,,field]=result.route;
 const input=field?$(field):null;
 if(input&&!input.value&&result.query){
  const limit=field==='research-query'?250:input.maxLength;
  input.value=result.query.slice(0,limit>0?limit:480);
  input.dispatchEvent(new Event('input',{bubbles:true}));
 }
 if(panel==='studio-connections'){
  const request=connectionRequest(result,message);
  if(!window.NexusStudioConnections?.openFor?.(request)){
   const entry=$('studio-connections-open');
   if(entry&&!entry.disabled)entry.click();
  }
 }else window.NexusStudioFocus?.openPanel(panel);
 return true;
}
function showWorkflow(){
 if(!workflowState)return;
 workflow.hidden=false;workflow.replaceChildren();
 const title=document.createElement('strong');
 title.textContent=words('Your reviewed workflow','گردش‌کار قابل بازبینی');
 const info=document.createElement('p');info.className='help';
 info.textContent=words(
  'Temporary checklist only. Opening a step does not run it. Mark each step done yourself after completing it in the separate tool.',
  'فهرست موقت است. بازکردن هر گام آن را اجرا نمی‌کند. پس از انجام کار در ابزار مربوطه، گام را خودت تکمیل‌شده علامت بزن.');
 const list=document.createElement('ol');
 workflowState.steps.forEach((step,i)=>{
  const item=document.createElement('li'),span=document.createElement('span');
  span.textContent=step.line+' · '+(i<workflowState.index?
   words('confirmed by you','به تأیید شما'):
   i===workflowState.index?words('current','گام فعلی'):words('not started','شروع‌نشده'));
  item.append(span);
  if(i===workflowState.index){
   const open=document.createElement('button');open.type='button';open.className='secondary';
   open.textContent=words('Open tool for review','بازکردن ابزار برای بازبینی');
   open.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow())return;
    if(openReviewedSurface(step.result,step.line)){
     workflowState.opened=true;showWorkflow();
    }
   };
   const done=document.createElement('button');done.type='button';done.className='secondary';
   done.textContent=words('I completed this step','این گام را انجام دادم');
   done.disabled=!workflowState.opened;
   done.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow()||!workflowState.opened)return;
    workflowState.index++;workflowState.opened=false;showWorkflow();
   };
   item.append(open,done);
  }
  list.append(item);
 });
 const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';
 cancel.textContent=words('Discard workflow','حذف گردش‌کار');
 cancel.onclick=()=>{clearWorkflow();$('message').focus()};
 workflow.append(title,info,list);
 if(workflowState.index===workflowState.steps.length){
  const note=document.createElement('p');note.setAttribute('role','status');
  note.textContent=words('All steps marked done by you; NEXUS has not verified external results.',
   'همهٔ گام‌ها به تأیید شما رسیدند؛ نکسوس نتیجهٔ خارجی را راستی‌آزمایی نکرده است.');
  workflow.append(note);
 }
 const exportButton=document.createElement('button');
 exportButton.id='studio-workflow-export';exportButton.type='button';
 exportButton.className='secondary';
 exportButton.textContent=words('Download checkpoint (plain JSON)','دریافت پیشرفت (JSON بدون رمزگذاری)');
 exportButton.onclick=downloadWorkflow;
 workflow.append(exportButton,cancel);
}

function parseCheckpoint(raw){
 if(!raw||typeof raw!=='object'||Array.isArray(raw)||
    Object.keys(raw).sort().join('|')!=='authority|completed|plan|schema|verified'||
    raw.schema!==WORKFLOW_SCHEMA||raw.authority!=='none'||raw.verified!==false||
    typeof raw.plan!=='string'||!Number.isInteger(raw.completed)||raw.completed<0)
  throw Error('invalid-checkpoint');
 const validated=parseWorkflow(raw.plan);
 if(validated.error||raw.completed>validated.steps.length)throw Error('invalid-checkpoint');
 return {plan:raw.plan,completed:raw.completed,steps:validated.steps};
}
function downloadWorkflow(){
 if(!validWorkflow())return;
 if(!confirm(words(
  'Download PLAIN-TEXT JSON with your full tool commands and self-reported progress? This file is unencrypted and does not verify external results.',
  'فایل JSON بدون رمزگذاری شامل فرمان‌های کامل و پیشرفت اعلام‌شدهٔ شماست. نتیجهٔ خارجی راستی‌آزمایی نمی‌شود. دریافت می‌کنی؟')))return;
 const payload={schema:WORKFLOW_SCHEMA,authority:'none',verified:false,
  plan:workflowState.draft,completed:workflowState.index};
 const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),link=document.createElement('a');
 link.href=url;link.download='nexus-workflow-checkpoint.json';
 link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
restoreFile.addEventListener('change',async()=>{
 const file=restoreFile.files?.[0];restoreFile.value='';
 if(!file)return;
 const epoch=++workflowImportEpoch,scope=workflowScope(),draft=$('message').value;
 const current=()=>{
  const state=window.NexusStudioUI.uiStatus();
  return epoch===workflowImportEpoch&&scope===workflowScope()&&
   $('message').value===draft&&state&&!state.busy&&!state.attachmentLoading&&!state.archived;
 };
 if(!current())return;
 try{
  if(!/\.json$/i.test(file.name)||file.size<1||file.size>4096)throw Error('bad-file');
  const raw=await file.text();if(!current())return;
  if(new TextEncoder().encode(raw).length>4096)throw Error('bad-size');
  const data=parseCheckpoint(JSON.parse(raw));
  if(!confirm(words(
   'Restore this UNTRUSTED review-only workflow and replace your unsent message? Completed steps are user reports, not verified, and no tool will execute.',
   'این گردش‌کار غیرقابل‌اعتماد فقط برای بازبینی بازیابی شود و جای پیام ارسال‌نشده را بگیرد؟ گام‌های انجام‌شده راستی‌آزمایی نشده‌اند و هیچ ابزاری اجرا نخواهد شد.')))return;
  if(!current())return;
  restoreStatus.textContent='';
  $('message').value=data.plan;
  $('message').dispatchEvent(new Event('input',{bubbles:true}));
  workflowState={draft:data.plan,scope:workflowScope(),steps:data.steps,index:data.completed,opened:false};
  showWorkflow();refresh();
 }catch{
  if(current())restoreStatus.textContent=words(
   'Invalid checkpoint. Nothing was changed.','فایل نامعتبر است؛ تغییری انجام نشد.');
 }
});

function reviewWorkflow(message){
 closeDirectory();clearOffer();
 const parsed=parseWorkflow(message);
 if(parsed.error){workflowError(parsed.error);return}
 workflowState={draft:message,scope:workflowScope(),steps:parsed.steps,index:0,opened:false};
 showWorkflow();
}

let offeredDraft=null;
function clearOffer(){
 offeredDraft=null;offer.hidden=true;offer.replaceChildren();
}
/* Model replies are text-only and cannot operate tools. Honor explicit user
 * requests to open a tool, but never infer permission from a generic question.
 * A suggestion only opens a separate local/connection review surface.
 */
function explicitToolRequest(message){
 const value=message.trim();
 return value.startsWith('/')||explicitResearch.test(value)||
  /^(?:remind me(?: to)?|set (?:a )?reminder(?: for)?|یادآوری کن)\s+/i.test(value)||
  /^(?:please\s+)?(?:open|launch)\s+/i.test(value)||
  /^(?:لطفاً\s+)?(?:باز\s*کن|برو\s+به)\s+/u.test(value)||
  /^(?:please\s+)?analy[sz]e\s+(?:this\s+|the\s+)?(?:csv|tsv|json|dataset|spreadsheet)\b/i.test(value)||
  /^(?:please\s+)?run\s+(?:this\s+)?javascript\b/i.test(value);
}
function suggestion(message){
 if(!window.NexusStudioFocus?.isFocused()||
    (select.value==='model'&&!explicitToolRequest(message)))return null;
 return intent(message);
}
function offerTool(message,result){
 const [,panel,en,fa,field]=result.route;
 clearOffer();offeredDraft=message;offer.hidden=false;
 const p=document.createElement('p');
 p.textContent=words('Open '+en+' to review its inputs.','برای بازبینی ورودی‌ها، '+fa+' را باز کن.');
 const open=document.createElement('button');open.type='button';open.textContent=words('Open '+en,'بازکردن '+fa);
 open.addEventListener('click',()=>{
  if($('message').value!==offeredDraft||window.NexusStudioUI.uiStatus().busy){clearOffer();return}
  clearOffer();
  openReviewedSurface(result,message);
 });
 const dismiss=document.createElement('button');dismiss.type='button';dismiss.className='secondary';
 dismiss.textContent=words('Keep typing','ادامهٔ نوشتن');dismiss.addEventListener('click',()=>{clearOffer();$('message').focus()});
 const proceed=document.createElement('button');proceed.type='button';proceed.className='secondary';
 proceed.textContent=select.value==='model'?words('Review as model message','بازبینی برای ارسال به مدل'):
  words('Continue with local guide','ادامه با راهنمای محلی');
 proceed.addEventListener('click',()=>{
  // Bind continuation to this exact reviewed proposal, not a mutable
  // suggestion slot that may have been invalidated by unrelated UI updates.
  const current=$('message').value===message;
  clearOffer();
  const state=window.NexusStudioUI.uiStatus();
  if(!current||state.busy||state.archived)return;
  // The local guide is an existing consent-checked action and requires
  // a thread. Start it explicitly; never infer permission for a model.
  if(!state.threadReady&&!window.NexusStudioUI.startConversation()){
   refresh();return;
  }
  if(select.value==='guide'){$('guide').click();refresh();return}
  refresh();run({routeTools:false});
 });
 offer.append(p,open,proceed,dismiss);
}

let running=false,temporaryModel=false,lastModelChoices='';
function refresh(){
 const state=window.NexusStudioUI.uiStatus();
 if(!state)return;
 if(temporaryModel&&!state.hasChatAttachments){select.value='guide';temporaryModel=false}
 if(offeredDraft!==null&&($('message').value!==offeredDraft||state.archived))clearOffer();
 if(workflowState&&!retainedWorkflow())clearWorkflow();
 const model=select.value==='model',ready=!state.busy&&!state.attachmentLoading&&(!state.threadReady||!state.archived);
 $('message').placeholder=words('Ask NEXUS anything…','هرچه می‌خواهی از نکسوس بپرس…');
 heading.textContent=model?words('AI model options','گزینه‌های مدل هوش مصنوعی'):words('Local guide · change mode','راهنمای محلی · تغییر حالت');
 box.setAttribute('aria-label',words('Conversation actions','گزینه‌های گفتگو'));
 selectLabel.setAttribute('aria-label',words('Choose how to respond','روش پاسخ را انتخاب کن'));
 for(const b of suggestions.children)b.textContent=words(b.dataset.en,b.dataset.fa);
 for(const opt of select.options)opt.textContent=words(opt.dataset.en,opt.dataset.fa);
 const privateChat=/^\/temporary$/i.test($('message').value.trim());
 const tool=suggestion($('message').value);
 const planning=isWorkflowRequest($('message').value);
 send.textContent=planning?words('Review workflow','بازبینی گردش‌کار'):privateChat?words('Start temporary chat','شروع گفتگوی موقت'):tool?words('Review '+tool.route[2],'بازبینی '+tool.route[3]):model?words('Review before sending','بازبینی پیش از ارسال'):words('Use local guide','استفاده از راهنمای محلی');
 send.disabled=!ready||!$('message').value.trim();
 restoreButton.disabled=state.busy||state.attachmentLoading||state.archived;
 send.setAttribute('aria-label',send.textContent);
 select.disabled=state.busy;
 const availability=window.NexusStudioUI.modelAvailability?.()||{kind:'gateway',checked:false,configured:false};
 const available=window.NexusStudioUI.availableModelOptions?.()||[];
 const signature=JSON.stringify(available);
 if(signature!==lastModelChoices){
  lastModelChoices=signature;
  modelSelect.replaceChildren(...available.map(item=>{
   const opt=document.createElement('option');opt.value=item.slot;
   opt.textContent=item.model+' · '+item.providerHost;return opt;
  }));
 }
 modelSelectLabel.hidden=!model||available.length<2;
 modelSelectTitle.textContent=words('Model','مدل');
 modelSelect.value=availability.slot||'primary';
 modelSelect.disabled=state.busy||state.attachmentLoading;
 modelStrip.hidden=!model;
 modelCheck.disabled=state.busy||state.attachmentLoading;
 modelCheck.textContent=availability.kind==='device'?
  words('Check local model','بررسی مدل روی دستگاه'):
  words('Check gateway settings','بررسی تنظیمات درگاه');
 modelState.textContent=!model?'':availability.kind==='device'?
  (availability.configured?words('On-device · '+availability.model+' · small model, limited accuracy; no provider request yet.',
   'روی دستگاه · '+availability.model+' · مدل کوچک با دقت محدود؛ هنوز درخواستی به ارائه‌دهنده ارسال نشده است.'):
   words('On-device model not ready; load it separately before reviewing a request.',
    'مدل روی دستگاه آماده نیست؛ پیش از بازبینی درخواست، آن را جداگانه بارگذاری کن.')):
  !availability.checked?words('Gateway model not checked. Check settings before requesting an AI reply.',
    'مدل درگاه هنوز بررسی نشده است. پیش از درخواست پاسخ، تنظیمات را بررسی کن.'):
  !availability.configured?words('No model configured at this gateway. Local guide is still available.',
    'در این درگاه مدلی پیکربندی نشده است؛ راهنمای محلی همچنان در دسترس است.'):
  words(availability.model+' · '+availability.providerHost+' · configured only; real access and quality are not verified.',
    availability.model+' · '+availability.providerHost+' · فقط پیکربندی تأیید شده؛ دسترسی و کیفیت واقعی هنوز بررسی نشده‌اند.');
 save.textContent=state.vaultUnlocked?words('Save encrypted session','ذخیرهٔ رمزگذاری‌شدهٔ نشست'):words('Set up private archive','تنظیم آرشیو خصوصی');
 // Never bypass the existing noForms() gate, including unread chat drafts.
 const pendingDraft=Boolean($('message').value.trim());
 save.disabled=state.busy||(state.vaultUnlocked&&(state.unsavedForms||pendingDraft));
 config.hidden=!model;
 config.disabled=state.busy;
 config.textContent=words('Model settings','تنظیمات مدل');
 privacy.textContent=model?
  words('Only operator-configured models appear. Review exact context and approve each send; provider charges may apply.',
        'فقط مدل‌های تنظیم‌شده در سرور نمایش داده می‌شوند. متن دقیق و هر ارسال را تأیید کن؛ ممکن است هزینه داشته باشد.'):
  words('Local guide only — not generative AI. It cannot read attached files or contact a provider.',
        'فقط راهنمای محلی است، نه هوش مصنوعی مولد؛ فایل پیوست نمی‌خواند یا با ارائه‌دهنده تماس نمی‌گیرد.');
 storage.textContent=state.vaultUnlocked?
  state.dirty||state.unsavedForms||pendingDraft?
   words('Work is not fully saved. Finish or clear draft fields, then save explicitly.',
         'همهٔ تغییرات ذخیره نشده‌اند. پیش‌نویس‌ها را تکمیل یا پاک کن و سپس صریحاً ذخیره کن.'):
   words('Encrypted archive unlocked. Use Save to retain changes; keep a separate encrypted backup.',
         'آرشیو رمزگذاری‌شده باز است. برای نگهداری تغییرات ذخیره کن و پشتیبان رمزگذاری‌شدهٔ جدا داشته باش.'):
  words('No encrypted archive is unlocked. This work can be lost if the tab closes.',
        'آرشیو رمزگذاری‌شده‌ای باز نیست. با بسته‌شدن برگه ممکن است کار از بین برود.');
}
function run({routeTools=true}={}){
 // The send button can briefly lag a newly created first conversation.
 // Authoritative UI state and the draft, not a stale disabled flag, gate work.
 const state=window.NexusStudioUI.uiStatus();
 if(running||!state||state.busy||state.attachmentLoading||(state.threadReady&&state.archived)||
    !$('message').value.trim())return;
 const message=$('message').value;
 if(isWorkflowRequest(message)){reviewWorkflow(message);return}
 if(/^\/temporary$/i.test(message.trim())){
  if(window.NexusStudioUI.startConversation(true,{isolated:true}))$('message').focus();
  return;
 }
 const tool=routeTools&&suggestion(message);
 if(tool?.route[0]==='tools'){clearOffer();showDirectory();return}
 if(tool){closeDirectory();offerTool(message,tool);return}
 if(!window.NexusStudioUI.uiStatus().threadReady&&!window.NexusStudioUI.startConversation()){
  refresh();return;
 }
 running=true;
 try{
  if(select.value==='model'){
   $('prepare').click(); // Existing model-info, context, consent and safety checks.
   if(!$('request-review').hidden){
    const reviewHeading=$('request-review').querySelector('h3');
    if(reviewHeading){reviewHeading.tabIndex=-1;reviewHeading.focus({preventScroll:true})}
    $('request-review').scrollIntoView({block:'nearest'});
   }else mode.open=true;
  }else{
   $('guide').click(); // Existing source/attachment validation; never a network call.
  }
 }finally{running=false;refresh()}
}
send.addEventListener('click',()=>run());
save.addEventListener('click',()=>{
 const state=window.NexusStudioUI.uiStatus();
 if(!state||state.busy||save.disabled)return;
 if(!state.vaultUnlocked){window.NexusStudioFocus?.openPanel('vault-card');$('passphrase').focus({preventScroll:true});return}
 $('save').click(); // Existing noForms() gate, vault encryption and user feedback.
 refresh();
});
config.addEventListener('click',()=>{
 document.dispatchEvent(new Event('nexus-studio-show-chat-options'));
 const settings=$('studio-model-settings');if(!settings)return;
 settings.open=true;
 settings.scrollIntoView({block:'nearest'});
 settings.querySelector('summary')?.focus({preventScroll:true});
});
modelCheck.addEventListener('click',()=>{if(!modelCheck.disabled)$('check-model').click()});
modelSelect.addEventListener('change',()=>{
 if(!window.NexusStudioUI.selectModelSlot?.(modelSelect.value))refresh();
 else {clearOffer();closeDirectory();refresh()}
});
select.addEventListener('change',()=>{
 temporaryModel=false;clearOffer();closeDirectory();
 window.NexusStudioUI.revokeModelReview?.();
 refresh();
});
document.addEventListener('nexus-studio-private-clear',()=>{clearOffer();closeDirectory();clearWorkflow();restoreStatus.textContent=''});
$('message').addEventListener('input',refresh);
$('message').addEventListener('keydown',event=>{
 if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&!event.isComposing&&
    document.documentElement.classList.contains('studio-focus-mode')){
  event.preventDefault();
  // Studio's older window-level shortcut would otherwise also dispatch a
  // local guide when no model was configured. Stop this duplicate event ONLY
  // in focused mode; full-view shortcuts retain their previous behavior.
  event.stopPropagation();
  run(); // In model mode only opens the consent review.
 }
});
$('language').addEventListener('change',()=>queueMicrotask(()=>{if(!directory.hidden)showDirectory();refresh()}));
document.addEventListener('nexus-studio-state',refresh);
document.addEventListener('nexus-studio-chat-layout',refresh);
document.addEventListener('nexus-studio-open-chat',()=>{
 clearOffer();closeDirectory();
 if(select.value==='guide'){temporaryModel=true;select.value='model'}
 $('chat-file-panel').open=true;refresh();
 $('message').focus({preventScroll:true});
});
window.NexusStudioCompose={refresh,mode:()=>select.value,catalog:()=>catalog};
refresh();
})();
