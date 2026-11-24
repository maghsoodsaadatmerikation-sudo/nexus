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
// Only a literal, fenced JavaScript body is eligible for a local editor handoff.
// Descriptions such as "write code" are never converted into executable code.
function reviewedJavaScript(message){
 const source=/^(?:\/code|(?:please\s+)?run javascript)\s*:?\s*\r?\n```(?:javascript|js)\r?\n([\s\S]*?)\r?\n```\s*$/i.exec(message.trim());
 if(!source||!source[1].trim()||source[1].length>100000)return null;
 return source[1];
}
// A proposal explains permissions before opening any separate tool review.
function toolBoundary(command){
 switch(command){
 case 'code': return words(
  'Local JavaScript worker: a literal fenced snippet may be copied into an empty editor. Execution requires separate exact-code consent. No network or private archive access is granted.',
  'اجرای محلی JavaScript: قطعه‌کد صریح و محصور ممکن است فقط در ویرایشگر خالی کپی شود. اجرا به تأیید جداگانهٔ همان کد نیاز دارد؛ دسترسی به شبکه یا آرشیو خصوصی داده نمی‌شود.');
 case 'research': return words(
  'Public research: the selected query leaves this device only after a separate provider choice and exact-query approval.',
  'پژوهش عمومی: عبارت انتخابی فقط پس از تعیین منبع و تأیید جداگانهٔ متن دقیق از دستگاه خارج می‌شود.');
 case 'github': case 'render': case 'connections': return words(
  'External account: opening connections may fetch an available-action catalog. Account reads or changes require the connector’s separate operation-specific review and permission.',
  'حساب خارجی: بازکردن اتصال‌ها ممکن است فهرست عملیات را دریافت کند. خواندن یا تغییر حساب نیازمند بازبینی و مجوز جداگانهٔ همان عملیات است.');
 case 'remind': return words(
  'Calendar reminder: the tool creates a file to import; it does not schedule a notification by itself.',
  'یادآور تقویمی: ابزار فایلی برای واردکردن به تقویم می‌سازد؛ خودش اعلان زمان‌بندی نمی‌کند.');
 case 'tasks': return words(
  'Local task workers: only a separately reviewed and approved plan can run. No autonomous execution starts here.',
  'کارهای محلی: تنها طرحی که جداگانه بازبینی و تأیید شده اجرا می‌شود؛ اینجا اجرای خودکار شروع نمی‌شود.');
 default: return words(
  'Tool-specific review required. Opening this screen does not approve execution, sharing, saving or a connected-account change.',
  'بازبینی مخصوص ابزار الزامی است. بازکردن این صفحه مجوز اجرا، اشتراک‌گذاری، ذخیره یا تغییر حساب متصل نیست.');
 }
}
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
let workflowState=null;
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
 workflowState=null;workflow.hidden=true;workflow.replaceChildren();
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
 // Open is an editor handoff, never a run. Preserve an already written code draft.
 if(panel==='code-card'){
  // Opening a chat proposal invalidates any old approval, including when an
  // existing editor draft is deliberately preserved instead of replaced.
  if($('code-consent'))$('code-consent').checked=false;
  const snippet=reviewedJavaScript(message),code=$('code');
  if(snippet!==null&&code&&!code.value&&code.maxLength>=snippet.length){
   code.value=snippet;
   code.dispatchEvent(new Event('input',{bubbles:true}));
  }
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

/* WORKFLOW_REVIEW_ENGINE */
function engineInput(draft,steps,planHash){
 const scope={project_id:'tab-local',workflow_id:'chat-review',run_id:'review',plan_sha256:planHash};
 const phase={started:'running',succeeded:'succeeded',failed:'failed',cancelled:'cancelled',partial:'blocked'};
 const plan={goal:'Review explicit chat workflow',steps:steps.map((step,i)=>({
  id:'s'+(i+1),needs:[],effect:step.command==='code'?'local_compute':step.command==='research'?'network_read':'unknown'
 }))};
 const criteria=plan.steps.map(step=>({id:step.id,required:true,evidence_kind:'human_review'}));
 const step_observations=steps.flatMap((step,i)=>phase[step.observed]?[{...scope,id:plan.steps[i].id,status:phase[step.observed]}]:[]);
 return {scope,plan,criteria,step_observations,evidence:[]};
}
async function showEngineReview(button,notice){
 const current=workflowState,state=window.NexusStudioUI.uiStatus();
 if(!validWorkflow()||state.isolated||!current)return;
 const snapshot=()=>JSON.stringify(current.steps.map(s=>({command:s.result.route[0],observed:s.observed||null,acknowledged:s.acknowledged})));
 const captured=snapshot(),draft=current.draft;
 button.disabled=true;
 try{
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(draft))),b=>b.toString(16).padStart(2,'0')).join('');
  if(workflowState!==current||!validWorkflow()||window.NexusStudioUI.uiStatus().isolated||captured!==snapshot()||!notice.isConnected)return;
  const result=reviewAssistantWorkflow(engineInput(draft,JSON.parse(captured),hash),{enabled:true});
  notice.textContent=words('Central review: ','بازبینی مرکزی: ')+({
   review_plan_boundaries:words('review tool boundaries','بازبینی محدودیت ابزار'),
   reconcile_execution_status:words('reconcile execution status','بررسی وضعیت اجرا'),
   review_lost_criteria:words('review lost criteria','بازبینی معیارهای ازدست‌رفته'),
   review_unfinished_steps:words('review unfinished steps','بازبینی مراحل ناتمام'),
   review_plan_findings:words('define success criteria','تعریف معیار موفقیت'),
   review_outcome_evidence:words('review evidence','بازبینی شواهد'),
   manual_final_review:words('manual final review','بازبینی نهایی انسانی')
  })[result.priority]+words(' · No completion verified; no action authorized.',' · تکمیل تأیید نشده؛ هیچ مجوز اجرایی صادر نشده.');
 }catch{if(notice.isConnected)notice.textContent=words('Central review unavailable; no action taken.','بازبینی مرکزی در دسترس نیست؛ اقدامی انجام نشد.')}
 finally{if(button.isConnected)button.disabled=false}
}

function workflowAction(p){return p==='started'?'wait':p==='succeeded'?'verify':p?'reconcile':'inspect'}
function workflowOutcomes(){
 const counts={succeeded:0,incomplete:0,running:0,unobserved:0,verified:false};
 for(const {observed} of workflowState.steps)counts[observed==='succeeded'?'succeeded':observed==='started'?'running':observed?'incomplete':'unobserved']++;
 return counts;
}
function workflowReport(){
 if(!retainedWorkflow())return null;
 return {
  schema:'nexus.workflow-review.v1',authority:'none',
  evidence:'tab-local-ui-and-human-acknowledgment-not-independent-proof',
  complete:workflowState.index===workflowState.steps.length,
  outcome_review:workflowOutcomes(),
  steps:workflowState.steps.map(step=>({
   command:step.result.route[0],request:step.line,
   opened:step.opened===true,acknowledged_by_user:step.acknowledged===true,
   local_ui_outcome:step.observed||null,next_review:workflowAction(step.observed)
  }))
 };
}
function showWorkflow(){
 if(!workflowState)return;
 workflow.hidden=false;workflow.replaceChildren();
 const title=document.createElement('strong');
 title.textContent=words('Your reviewed workflow','گردش‌کار قابل بازبینی');
 const info=document.createElement('p');info.className='help';
 info.textContent=words(
  'Opening a step does not run it. Local code and research can show a tab-observed outcome, not independent proof. Progress still requires your acknowledgment.',
  'بازکردن گام آن را اجرا نمی‌کند. نتیجهٔ اجرای کد و پژوهش فقط در همین برگه مشاهده می‌شود، نه به‌عنوان مدرک مستقل. پیشرفت همچنان به تأیید شما نیاز دارد.');
 const list=document.createElement('ol');
 workflowState.steps.forEach((step,i)=>{
  const item=document.createElement('li'),span=document.createElement('span');
  span.textContent=step.line+' · '+(i<workflowState.index?
   words('confirmed by you','به تأیید شما'):
   i===workflowState.index?words('current','گام فعلی'):words('not started','شروع‌نشده'));
  if(step.opened)span.textContent+=' · '+words('Review: '+workflowAction(step.observed),'بازبینی: '+({wait:'انتظار',verify:'راستی‌آزمایی',reconcile:'رفع نقص',inspect:'بررسی'})[workflowAction(step.observed)]);
  item.append(span);
  const boundary=document.createElement('small');boundary.className='help';
  boundary.textContent=' · '+toolBoundary(step.result.route[0]);
  item.append(boundary);
  if(step.observed){
   const observation=document.createElement('small');observation.className='help';
   const phase=step.observed;
   observation.textContent=' · '+(phase==='started'?
    words('Local tool started (awaiting result)','ابزار محلی شروع شد (در انتظار نتیجه)'):
    phase==='succeeded'?
    words('Local UI reported success · not independent proof','رابط محلی موفقیت را گزارش کرد؛ مدرک مستقل نیست'):
    phase==='partial'?
    words('Local UI reported partial result · not verified','رابط محلی نتیجهٔ ناقص گزارش کرد؛ راستی‌آزمایی نشده'):
    phase==='cancelled'?
    words('Local execution cancelled · no result','اجرای محلی لغو شد؛ نتیجه‌ای ثبت نشد'):
    words('Local UI reported failure · do not treat as success','رابط محلی شکست را گزارش کرد؛ موفقیت محسوب نمی‌شود'));
   item.append(observation);
  }
  if(i===workflowState.index){
   const open=document.createElement('button');open.type='button';open.className='secondary';
   open.textContent=words('Open tool for review','بازکردن ابزار برای بازبینی');
   open.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow())return;
    if(openReviewedSurface(step.result,step.line)){
     workflowState.opened=true;step.opened=true;showWorkflow();
    }
   };
   const done=document.createElement('button');done.type='button';done.className='secondary';
   done.textContent=['failed','cancelled','partial'].includes(step.observed)?
    words('Acknowledge incomplete result · continue','ثبت نتیجهٔ ناقص یا ناموفق و ادامه'):
    words('I reviewed this step · continue','این گام را بازبینی کردم؛ ادامه');
   done.disabled=!workflowState.opened||step.observed==='started';
   done.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow()||!workflowState.opened||step.observed==='started')return;
    step.acknowledged=true;workflowState.index++;workflowState.opened=false;showWorkflow();
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
  const {succeeded,incomplete,unobserved}=workflowOutcomes();
  note.textContent=words('Review complete; execution not verified. Local success / incomplete / unobserved: ','بازبینی پایان یافت؛ اجرا تأیید نشده. موفق محلی / ناقص / مشاهده‌نشده: ')+[succeeded,incomplete,unobserved].join(' / ');
  workflow.append(note);
 }
 workflow.append(cancel);
 const exportButton=document.createElement('button');exportButton.type='button';
 exportButton.className='secondary';exportButton.dataset.workflowReport='true';
 exportButton.textContent=words('Download review report','دریافت گزارش بازبینی');
 exportButton.onclick=()=>{
  const record=workflowReport();
  if(!record||!confirm(words(
   'Download an unencrypted report containing your workflow commands and local status? This is not verified execution evidence.',
   'گزارش بدون رمزگذاری شامل فرمان‌های گردش‌کار و وضعیت محلی دریافت شود؟ این مدرک اجرای تأییدشده نیست.')))return;
  download(JSON.stringify(record,null,2),'nexus-workflow-review.json','application/json');
 };
 workflow.append(exportButton);
 const central=document.createElement('button');central.type='button';central.className='secondary';central.dataset.centralReview='true';
 central.textContent=words('Review with central engine','بازبینی با موتور مرکزی');
 central.disabled=Boolean(window.NexusStudioUI.uiStatus().isolated);
 const reviewNotice=document.createElement('p');reviewNotice.dataset.centralResult='true';reviewNotice.setAttribute('role','status');
 central.onclick=()=>showEngineReview(central,reviewNotice);
 workflow.append(central,reviewNotice);
}
function reviewWorkflow(message){
 closeDirectory();clearOffer();
 const parsed=parseWorkflow(message);
 if(parsed.error){workflowError(parsed.error);return}
 workflowState={draft:message,scope:workflowScope(),steps:parsed.steps.map(step=>({
  ...step,opened:false,acknowledged:false,runId:null,observed:null
 })),index:0,opened:false};
 showWorkflow();
}
// These UI events come from local tool controllers after an explicitly
// consented action; they are not authorization tokens or signed attestations.
document.addEventListener('nexus-studio-local-tool-lifecycle',event=>{
 if(!retainedWorkflow()||!workflowState.opened)return;
 const detail=event.detail;
 if(!detail||!['code','research'].includes(detail.tool)||
    !Number.isSafeInteger(detail.runId)||detail.runId<1||
    !['started','succeeded','partial','failed','cancelled'].includes(detail.phase))return;
 const step=workflowState.steps[workflowState.index];
 if(!step||step.result.route[0]!==detail.tool)return;
 if(detail.phase==='started'){step.runId=detail.runId;step.observed='started'}
 else if(step.runId===detail.runId&&step.observed==='started')step.observed=detail.phase;
 else return;
 showWorkflow();
});

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
 const boundary=document.createElement('p');boundary.className='help';
 boundary.textContent=toolBoundary(result.route[0]);
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
 offer.append(p,boundary,open,proceed,dismiss);
}

let running=false,temporaryModel=false,lastModelChoices='';
function memoryCommand(value){
 const edit=/^(?:\/replace-memory(?:\s+|$)|اصلاح حافظه\s*[:：]\s*)/i.exec(value.trim());
 if(edit){
  const parts=value.trim().slice(edit[0].length).split('=>');
  return {edit:true,remove:false,note:parts.length===2?parts[0].trim():'',replacement:parts.length===2?parts[1].trim():''};
 }
 const remove=/^(?:\/forget(?:\s+|$)|فراموش کن\s*[:：]\s*)/i.exec(value.trim());
 const match=remove||/^(?:\/remember(?:\s+|$)|به خاطر بسپار\s*[:：]\s*)/i.exec(value.trim());
 return match?{remove:!!remove,note:value.trim().slice(match[0].length).trim()}:null;
}
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
 const memory=memoryCommand($('message').value);
 send.textContent=memory?memory.edit?words('Review memory correction','بازبینی اصلاح حافظه'):memory.remove?words('Review memory removal','بازبینی حذف یادداشت'):words('Review memory note','بازبینی یادداشت حافظه'):planning?words('Review workflow','بازبینی گردش‌کار'):privateChat?words('Start temporary chat','شروع گفتگوی موقت'):tool?words('Review '+tool.route[2],'بازبینی '+tool.route[3]):model?words('Review before sending','بازبینی پیش از ارسال'):words('Use local guide','استفاده از راهنمای محلی');
 send.disabled=!ready||!$('message').value.trim();
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
  availability.localReadiness==='LOCAL_BUDGET_UNAVAILABLE'?
  words('Local request budget storage unavailable. Model requests are blocked; provider access unverified.',
    'ذخیرهٔ سهمیهٔ محلی در دسترس نیست. درخواست مدل مسدود است؛ اتصال ارائه‌دهنده تأیید نشده است.'):
  availability.localReadiness==='LOCAL_BUDGET_EXHAUSTED'?
  words('Local request budget exhausted. Model requests are blocked; provider access unverified.',
    'سهمیهٔ محلی تمام شده است. درخواست مدل مسدود است؛ اتصال ارائه‌دهنده تأیید نشده است.'):
  availability.localReadiness==='READY_TO_TEST'?
  words(availability.model+' · '+availability.providerHost+' · '+availability.remainingRequests+' local attempt(s) remain. Ready to test configuration only; provider access, billing and quality unverified.',
    availability.model+' · '+availability.providerHost+' · '+availability.remainingRequests+' درخواست محلی باقی مانده است. فقط پیکربندی برای آزمایش آماده است؛ اتصال، هزینه و کیفیت تأیید نشده‌اند.'):
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
 const note=memoryCommand(message);
 if(note!==null){
  clearOffer();closeDirectory();
  if(window.NexusStudioUI.stageMemoryNote?.(note.note,note.remove,note.replacement??null)){
   window.NexusStudioFocus?.openPanel('profile-card');
   $('status').textContent=words('Memory draft only. Review and Apply preferences; save separately.','فقط پیش‌نویس حافظه است. بازبینی و اعمال ترجیحات؛ ذخیره جداگانه.');
  }else $('status').textContent=note.edit?words('Use /replace-memory exact old note => new note. One unique match is required.','اصلاح حافظه: متن دقیق قدیمی => متن جدید. یک تطابق یکتا لازم است.'):note.remove?words('Removal unavailable. Use one exact, unique saved note in a regular project with no pending draft.','حذف ممکن نیست. متن دقیق یک یادداشت یکتا را در پروژه عادی و بدون پیش‌نویس وارد کن.'):words('Memory draft unavailable. Select a regular project, finish existing drafts, and use one line (1–500 characters).','پیش‌نویس حافظه ممکن نیست. پروژه عادی را انتخاب کن، پیش‌نویس‌های قبلی را تکمیل کن و یک خط (۱ تا ۵۰۰ نویسه) بنویس.');
  refresh();return;
 }
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
document.addEventListener('nexus-studio-private-clear',()=>{clearOffer();closeDirectory();clearWorkflow()});
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
