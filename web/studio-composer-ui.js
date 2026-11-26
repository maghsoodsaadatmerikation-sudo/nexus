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
 resetChatCorrectionPanel();resetChatCorrectionPanel=()=>{};workflowState=null;workflow.hidden=true;workflow.replaceChildren();
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

const {reviewAssistantWorkflow,buildChatExperienceReport}=experienceImportEngine;
function humanCriterion(step){
 const criterion=typeof step.criterion==='string'?step.criterion.trim():'';
 const valid=criterion.length>0&&criterion.length<=260;
 const verdict=valid&&step.opened===true&&step.observed!=='started'&&
  ['pass','fail','inconclusive'].includes(step.verdict)?step.verdict:null;
 return {criterion:valid?criterion:'',verdict};
}
function engineInput(draft,steps,planHash,round=1){
 if(!Number.isSafeInteger(round)||round<1)throw Error('invalid-review-round');
 const scope={project_id:'tab-local',workflow_id:'chat-review',run_id:'review-'+round,plan_sha256:planHash};
 const phase={started:'running',succeeded:'succeeded',failed:'failed',cancelled:'cancelled',partial:'blocked'};
 const plan={goal:'Review explicit chat workflow',steps:steps.map((step,i)=>({
  id:'s'+(i+1),needs:[],effect:step.command==='code'?'local_compute':step.command==='research'?'network_read':'unknown',
  ...(humanCriterion(step).criterion?{success_criteria:humanCriterion(step).criterion}:{})
 }))};
 const criteria=plan.steps.map(step=>({id:step.id,required:true,evidence_kind:'human_review'}));
 const step_observations=steps.flatMap((step,i)=>phase[step.observed]?[{...scope,id:plan.steps[i].id,status:phase[step.observed]}]:[]);
 const evidence=steps.flatMap((step,i)=>{const {verdict}=humanCriterion(step);return verdict?[{...scope,criterion_id:plan.steps[i].id,evidence_id:scope.run_id+'-human-'+(i+1),kind:'human_review',result:verdict}]:[]});
 return {scope,plan,criteria,step_observations,evidence};
}
function reviewSnapshot(current){
 return current.steps.map(s=>({command:s.result.route[0],observed:s.observed||null,acknowledged:s.acknowledged,opened:s.opened,criterion:s.criterion||'',verdict:s.verdict||null}));
}
function canCompareRound(current){
 return current.index===current.steps.length&&current.steps.every(s=>humanCriterion(s).verdict!==null);
}
function restartReviewedRound(current){
 if(!canCompareRound(current)||current.round>=100)throw Error('review-round-unavailable');
 const prior={round:current.round,steps:reviewSnapshot(current)};
 return {...current,round:current.round+1,epoch:0,baseline:prior,history:[...(current.history||[]),prior].slice(-30),index:0,opened:false,
  steps:current.steps.map(s=>({...s,opened:false,acknowledged:false,runId:null,observed:null,verdict:null}))};
}
// Forget only retained prior rounds; preserve the current review and invalidate in-flight results.
function forgetReviewedHistory(current){
 return {...current,epoch:current.epoch+1,baseline:null,history:[]};
}
// Retain only comparable, completed rounds in the current workflow tab.
function comparableFailureHistory(current,hash,snapshot){
 const signature=steps=>JSON.stringify(steps.map(s=>[s.command,humanCriterion(s).criterion]));
 const expected=signature(snapshot);
 return (current.history||[]).filter(r=>r.round<current.round&&signature(r.steps)===expected&&r.steps.every(s=>humanCriterion(s).verdict!==null)).map(r=>{
  const previous=engineInput(current.draft,r.steps,hash,r.round);
  return {scope:previous.scope,observations:previous.evidence};
 });
}
// A proposed review graph only. Never mutate or execute the current workflow.
function adaptiveChatDraft(input,result){
 const recurrent=new Set((result.failure_patterns?.patterns||[]).filter(p=>p.historical_reported_failure>=2).map(p=>p.criterion_id));
 if(!recurrent.size)return null;
 const steps=[],checkpoints=[];
 for(const step of input.plan.steps){
  const copy={...step,needs:[...step.needs]};
  if(recurrent.has(step.id)){
   const check='pre-'+step.id;
   steps.push({id:check,needs:[...step.needs],effect:'human_review',success_criteria:'Before starting, review the prior failure and agree on a verification method: '+step.success_criteria});
   copy.needs.push(check);
   checkpoints.push({criterion_id:step.id,check_step_id:check,protected_step_ids:[step.id]});
  }
  steps.push(copy);
 }
 if(steps.length>12)return null;
 return {plan:{goal:'Draft preventive review of next chat workflow',steps},checkpoints};
}
function completeReportRounds(current){
 if(!canCompareRound(current)||current.round<4||current.round>24||current.round%2||
    !Array.isArray(current.history)||current.history.length!==current.round-1||
    current.history.some((r,i)=>r.round!==i+1))return null;
 return [...current.history,{round:current.round,steps:reviewSnapshot(current)}];
}
function reviewQueueText(result,words){
 const labels={declared_plan_boundary_findings:words('plan boundaries','مرزهای برنامه'),uncertain_or_inconsistent_step_status:words('uncertain step status','وضعیت نامشخص گام‌ها'),required_evidence_reconciliation:words('required evidence conflicts','تعارض شواهد ضروری'),reported_pass_lost:words('reported passes lost','موفقیت‌های ازدست‌رفته'),other_unfinished_steps:words('unfinished steps','گام‌های ناتمام'),other_plan_findings:words('other plan findings','سایر نواقص برنامه'),other_required_evidence_actions:words('required evidence review','بازبینی شواهد ضروری'),optional_evidence_actions:words('optional evidence review','بازبینی شواهد تکمیلی')};
 const queue=result.review_readiness.queue;
 return queue.length?words(' · Outstanding review: ',' · موارد نیازمند بازبینی: ')+queue.map(q=>labels[q.reason]+': '+q.count).join('; '):words(' · Manual final review still required.',' · بازبینی نهایی انسانی همچنان لازم است.');
}
async function showEngineReview(button,notice){
 const current=workflowState,state=window.NexusStudioUI.uiStatus();
 if(!validWorkflow()||state.isolated||!current)return;
 const snapshot=()=>JSON.stringify(reviewSnapshot(current));
 const captured=snapshot(),draft=current.draft,epoch=current.epoch;
 button.disabled=true;
 try{
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([draft,JSON.parse(captured).map(s=>s.criterion)])))),b=>b.toString(16).padStart(2,'0')).join('');
  if(workflowState!==current||!validWorkflow()||window.NexusStudioUI.uiStatus().isolated||epoch!==current.epoch||captured!==snapshot()||!notice.isConnected)return;
  const input=engineInput(draft,JSON.parse(captured),hash,current.round);
  const baseline=current.baseline;
  if(baseline&&canCompareRound(current)){
   const previous=engineInput(draft,baseline.steps,hash,baseline.round);
   input.prior_run={scope:previous.scope,observations:previous.evidence};
  }
  const history=comparableFailureHistory(current,hash,JSON.parse(captured));
  if(history.length)input.failure_history=history;
  let result=reviewAssistantWorkflow(input,{enabled:true,experienceEnabled:history.length>0});
  const proposal=adaptiveChatDraft(input,result);
  if(proposal){
   const proposalHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(proposal.plan)))),b=>b.toString(16).padStart(2,'0')).join('');
   if(workflowState!==current||!validWorkflow()||window.NexusStudioUI.uiStatus().isolated||epoch!==current.epoch||captured!==snapshot()||!notice.isConnected)return;
   input.adaptive_plan={scope:{...input.scope,run_id:'draft-'+current.round,plan_sha256:proposalHash},...proposal};
   result=reviewAssistantWorkflow(input,{enabled:true,experienceEnabled:true});
  }
  const preventive=result.adaptive_plan?.findings.filter(f=>f.status==='declared_checkpoint_present').map(f=>f.criterion_id)||[];
  const recurrent=result.failure_patterns?.patterns.filter(p=>p.historical_reported_failure>=2).map(p=>p.criterion_id)||[];
  const reviewed=result.outcome.items.filter(i=>i.disposition==='reported_pass').length;
  const failed=result.outcome.items.filter(i=>i.disposition==='reported_failure').length;
  notice.textContent=words('Central review: ','بازبینی مرکزی: ')+({
   review_plan_boundaries:words('review tool boundaries','بازبینی محدودیت ابزار'),
   reconcile_execution_status:words('reconcile execution status','بررسی وضعیت اجرا'),
   review_lost_criteria:words('review lost criteria','بازبینی معیارهای ازدست‌رفته'),
   review_unfinished_steps:words('review unfinished steps','بازبینی مراحل ناتمام'),
   review_plan_findings:words('define success criteria','تعریف معیار موفقیت'),
   review_outcome_evidence:words('review evidence','بازبینی شواهد'),
   manual_final_review:words('manual final review','بازبینی نهایی انسانی')
  })[result.priority]+words(' · Human-reported pass / fail: ',' · موفق / ناموفق به گزارش کاربر: ')+reviewed+'/'+failed+(result.revision?words(' · Reported gains / losses: ',' · پیشرفت / پسرفت گزارش‌شده: ')+result.revision.gained_count+'/'+result.revision.lost_count:'')+(history.length?words(' · Comparable previous rounds: ',' · دورهای قابل‌مقایسهٔ پیشین: ')+history.length+words(' · Repeated prior failures: ',' · شکست‌های مکرر پیشین: ')+(recurrent.join(', ')||'0'):'')+(preventive.length?words(' · Suggested for next round: before steps ',' · پیشنهاد برای دور بعد: پیش از گام‌های ')+preventive.map(id=>id.slice(1)).join(', ')+words(', review prior failures and agree on a verification method. Draft only; not applied.','، شکست‌های پیشین و روش اعتبارسنجی را بازبینی کنید. فقط پیش‌نویس؛ اعمال نشده.'):'' )+reviewQueueText(result,words)+words(' · No completion verified; no action authorized.',' · تکمیل تأیید نشده؛ هیچ مجوز اجرایی صادر نشده.');
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
// Explicit local export only. Never send to a model or save to the vault here.
function appendExperienceReportControls(){
 const current=workflowState,selection=window.NexusStudioUI.selection?.();
 if(!selection?.projectId||!selection.threadId||current.round<4||current.round>24||current.round%2||
    current.history.length!==current.round-1)return;
 const details=document.createElement('details'),summary=document.createElement('summary');
 summary.textContent=words('Export correction experience report','دریافت گزارش تجربهٔ اصلاح');
 details.append(summary);
 const help=document.createElement('p');help.className='help';
 help.textContent=words('Pairs are consecutive rounds (1–2, 3–4, …). Include all relevant attempts. Human reports are not independent proof. The unencrypted file contains project identifiers and verdicts.','جفت‌ها دورهای متوالی هستند (۱–۲، ۳–۴ و ...). همهٔ تلاش‌های مرتبط را لحاظ کنید. گزارش انسانی مدرک مستقل نیست. فایل بدون رمزگذاری شامل شناسهٔ پروژه و ارزیابی‌هاست.');
 details.append(help);
 const field=(text,node)=>{const label=document.createElement('label');label.textContent=text;label.append(node);details.append(label)};
 const code=document.createElement('input');code.type='text';code.maxLength=80;code.placeholder='correction-code';
 field(words('Non-sensitive correction code','شناسهٔ غیرحساس اصلاح'),code);
 const criterion=document.createElement('select');
 current.steps.forEach((_,i)=>{const o=document.createElement('option');o.value='s'+(i+1);o.textContent=words('Step ','گام ')+(i+1);criterion.append(o)});
 field(words('Improved criterion','معیار بهبودیافته'),criterion);
 const kind=document.createElement('select');
 for(const [v,en,fa] of [['accept','New experience','تجربهٔ تازه'],['refresh','Refresh existing experience','بازبینی تجربهٔ موجود']]){const o=document.createElement('option');o.value=v;o.textContent=words(en,fa);kind.append(o)}
 field(words('Operation','عملیات'),kind);
 const button=document.createElement('button');button.type='button';button.className='secondary';button.dataset.experienceReport='true';
 button.textContent=words('Review and download report','بازبینی و دریافت گزارش');button.disabled=!completeReportRounds(current);
 const notice=document.createElement('p');notice.setAttribute('role','status');const apply=document.createElement('button');apply.type='button';apply.className='secondary';apply.dataset.experienceApply='true';
 apply.textContent=words('Review and retain in session','بازبینی و ثبت در نشست');
 apply.disabled=!completeReportRounds(current)||!canApplyChatExperience();
 details.append(button,apply,notice);
 const submit=async(direct)=>{
  const rounds=completeReportRounds(current),selected=window.NexusStudioUI.selection?.(),epoch=current.epoch;
  if(!rounds||!validWorkflow()||window.NexusStudioUI.uiStatus().isolated||workflowState!==current||!button.isConnected||!selected?.projectId||!selected.threadId||(direct&&!canApplyChatExperience()))return;
  const captured=JSON.stringify(rounds),fields=[code.value.trim(),criterion.value,kind.value];
  if(!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(fields[0])){notice.textContent=words('Enter a valid non-sensitive correction code.','شناسهٔ معتبر و غیرحساس اصلاح را وارد کنید.');return}
  if(!confirm(words('Did you apply the same named correction between each before/after pair, and include all relevant attempts, including failures? This is your report, not verified evidence.','آیا در هر جفت قبل و بعد همان اصلاح نام‌گذاری‌شده را انجام داده‌اید و همهٔ تلاش‌های مرتبط، از جمله شکست‌ها، را لحاظ کرده‌اید؟ این گزارش شماست، نه مدرک تأییدشده.')))return;
  button.disabled=apply.disabled=true;
  const stillCurrent=()=>{const now=window.NexusStudioUI.selection?.();return workflowState===current&&validWorkflow()&&!window.NexusStudioUI.uiStatus().isolated&&button.isConnected&&current.epoch===epoch&&now?.projectId===selected.projectId&&now?.threadId===selected.threadId&&now?.revision===selected.revision&&JSON.stringify(completeReportRounds(current))===captured&&JSON.stringify([code.value.trim(),criterion.value,kind.value])===JSON.stringify(fields)};
  try{
   if(!current.reportSessionId)current.reportSessionId=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([current.draft,rounds[0].steps.map(s=>s.criterion.trim())])))),b=>b.toString(16).padStart(2,'0')).join('');
   if(!stillCurrent())return;
   const result=buildChatExperienceReport(rounds,{project_id:selected.projectId,plan_sha256:hash,session_id:current.reportSessionId,correction_code:fields[0],criterion_id:fields[1],kind:fields[2],same_correction_reported:true,complete_relevant_history_reported:true},{enabled:true});
   if(!result.report){notice.textContent=words('Insufficient reported support; no report exported.','پشتیبانی گزارش‌شده کافی نیست؛ گزارشی دریافت نشد.');return}
   if(direct){
    const status=applyChatExperienceReport(result.report,selected);
    if(notice.isConnected)notice.textContent=({applied:words('Experience retained in session. Clear the workflow draft before Save session.','تجربه در نشست ثبت شد. پیش از ذخیره، پیش‌نویس گردش‌کار را پاک کنید.'),declined:words('Not retained.','ثبت نشد.'),unavailable:words('Archive or session unavailable.','آرشیو یا نشست در دسترس نیست.'),rejected:words('Report rejected; no experience changed.','گزارش رد شد؛ تجربه‌ای تغییر نکرد.')})[status];
    return;
   }
   if(!confirm(words('Download unencrypted report? Supporting pairs: ','گزارش بدون رمزگذاری دریافت شود؟ جفت‌های پشتیبان: ')+result.supporting_pair_count+' · '+fields.join(' / '))||!stillCurrent())return;
   download(JSON.stringify(result.report,null,2),'nexus-correction-experience.json','application/json');
   notice.textContent=words('Report prepared for local import. No experience saved.','گزارش برای ورود محلی آماده شد. تجربه‌ای ذخیره نشد.');
  }catch{if(stillCurrent())notice.textContent=words('Report unavailable; no action taken.','گزارش در دسترس نیست؛ اقدامی انجام نشد.')}
  finally{if(button.isConnected){button.disabled=!completeReportRounds(current);apply.disabled=button.disabled||!canApplyChatExperience()}}
 };
 button.onclick=()=>submit(false);apply.onclick=()=>submit(true);
 workflow.append(details);
}
// Explicit local report selection; results are ephemeral.
let chatRecallGeneration=0;
function clearChatRecallResult(){
 resetChatCorrectionPanel();chatRecallGeneration++;
 const notice=workflow.querySelector('[data-chat-recall-result]');
 if(notice)notice.textContent='';
}
function canRecallCurrent(current){
 return !!current&&workflowState===current&&validWorkflow()&&canCompareRound(current)&&!!chatArchiveRecallContext()&&current.steps.some(s=>humanCriterion(s).verdict==='fail');
}
function appendChatRecallControls(){
 const current=workflowState;
 const details=document.createElement('details'),summary=document.createElement('summary');
 summary.textContent=words('Review a previous correction','بازبینی اصلاح پیشین');details.append(summary);
 const help=document.createElement('p');help.className='help';help.textContent=words('Choose a previously exported correction report for the same workflow after a complete round with a reported failure. Local review only; nothing sent, saved or applied.','پس از یک دور کامل با شکست گزارش‌شده، گزارش اصلاح پیشین همان گردش‌کار را انتخاب کنید. فقط بازبینی محلی؛ بدون ارسال، ذخیره یا اعمال خودکار.');details.append(help);
 const label=document.createElement('label');label.textContent=words('Previous correction report (.json)','گزارش اصلاح پیشین (.json)');
 const input=document.createElement('input');input.type='file';input.accept='.json,application/json';input.dataset.chatRecallFile='true';input.disabled=!canRecallCurrent(current);label.append(input);details.append(label);
 const notice=document.createElement('p');notice.dataset.chatRecallResult='true';notice.setAttribute('role','status');details.append(notice);
 input.onchange=async()=>{
  const file=input.files?.[0];input.value='';clearChatRecallResult();
  if(!file||!input.isConnected||!canRecallCurrent(current))return;
  if(file.size<1||file.size>65536||!/\.json$/i.test(file.name)){notice.textContent=words('Invalid report file.','فایل گزارش نامعتبر است.');return}
  if(!confirm(words('Read this local report and compare it with the current failure? The report is not independently verified. No data will be sent or saved.','این گزارش محلی خوانده و با شکست فعلی مقایسه شود؟ گزارش مستقلاً تأیید نشده و داده‌ای ارسال یا ذخیره نمی‌شود.')))return;
  const expected=chatArchiveRecallContext(),epoch=current.epoch,generation=chatRecallGeneration,steps=reviewSnapshot(current),captured=JSON.stringify(steps);
  const live=()=>input.isConnected&&canRecallCurrent(current)&&epoch===current.epoch&&generation===chatRecallGeneration&&JSON.stringify(chatArchiveRecallContext())===JSON.stringify(expected)&&JSON.stringify(reviewSnapshot(current))===captured;
  input.disabled=true;
  try{
   const raw=await file.text();if(!live())return;
   const planHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([current.draft,steps.map(s=>s.criterion.trim())])))),b=>b.toString(16).padStart(2,'0')).join('');
   if(!live())return;
   if(!current.reportSessionId)current.reportSessionId=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
   const result=recallChatExperienceReport(raw,expected,{sessionId:current.reportSessionId,round:current.round,planHash,steps});
   if(!live())return;
   if(result.matches.length)notice.textContent=words('Previous reported correction(s) for review: ','اصلاح‌های پیشین گزارش‌شده برای بازبینی: ')+result.matches.map(m=>m.criterion_id+' / '+m.correction_code+' ('+m.supporting_pair_count+')').join(' · ')+words(' · Associations, not proof. Nothing applied.',' · همبستگی، نه مدرک اثربخشی. هیچ اصلاحی اعمال نشده.');
   else notice.textContent=words('No matching active correction with rechecked reported support. Nothing applied.','اصلاح فعال مطابق با پشتیبانی بازبینی‌شده یافت نشد. هیچ اصلاحی اعمال نشده.');
  }catch{if(live())notice.textContent=words('Recall unavailable or report rejected. Nothing applied.','بازیابی در دسترس نیست یا گزارش رد شد. هیچ اصلاحی اعمال نشده.')}
  finally{if(input.isConnected&&generation===chatRecallGeneration)input.disabled=!canRecallCurrent(current)}
 };
 workflow.append(details);
}
// Local report set and estimates are ephemeral; the central engine makes
// no decision or execution grant. A scope change discards the whole form.
let resetChatCorrectionPanel=()=>{};
function appendChatCorrectionControls(){
 const current=workflowState,details=document.createElement('details'),summary=document.createElement('summary');
 summary.textContent=words('Compare previous corrections','مقایسه اصلاح‌های پیشین');details.append(summary);
 const help=document.createElement('p');help.className='help';
 help.textContent=words('Choose 2–5 exported reports for distinct corrections of the same failed criterion. Both archive support and local tool status must pass review. Enter your own estimates; this is not prediction or execution.','۲ تا ۵ گزارش اصلاح متمایز برای یک معیار ناموفق انتخاب کنید. پشتیبانی آرشیو و وضعیت ابزار باید بازبینی شود. برآوردها را خودتان وارد کنید؛ این پیش‌بینی یا اجرا نیست.');details.append(help);
 const label=document.createElement('label');label.textContent=words('Previous reports (.json)','گزارش‌های پیشین (.json)');
 const files=document.createElement('input');files.type='file';files.multiple=true;files.accept='.json,application/json';files.dataset.chatCompareFiles='true';label.append(files);details.append(label);
 const form=document.createElement('div'),notice=document.createElement('div');notice.dataset.chatCompareResult='true';notice.setAttribute('role','status');details.append(form,notice);
 let generation=0,reports=null;
 const reset=()=>{generation++;reports=null;files.value='';form.replaceChildren();notice.textContent='';files.disabled=!canRecallCurrent(current)};
 resetChatCorrectionPanel=reset;reset();
 details.ontoggle=()=>{if(!details.open)reset()};
 const make=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
 const field=(parent,title,control)=>{const l=make('label',title);l.append(control);parent.append(l);return control};
 const num=(parent,title,max)=>{const n=make('input');n.type='number';n.min='0';n.max=String(max);n.step='1';n.inputMode='numeric';return field(parent,title,n)};
 const select=(parent,title,choices)=>{const n=make('select');for(const [v,en,fa] of choices){const o=make('option',words(en,fa));o.value=v;n.append(o)}return field(parent,title,n)};
 const integer=(n,optional=false)=>{if(!n.value&&optional)return null;if(!/^\d+$/.test(n.value)||!Number.isSafeInteger(Number(n.value))||Number(n.value)>Number(n.max))throw Error('invalid-estimate');return Number(n.value)};
 files.onchange=async()=>{
  const selected=Array.from(files.files||[]);reset();
  if(!files.isConnected||!canRecallCurrent(current)||!selected.length)return;
  if(selected.length<2||selected.length>5||selected.some(f=>f.size<1||f.size>65536||!/\.json$/i.test(f.name))||selected.reduce((n,f)=>n+f.size,0)>196608){notice.textContent=words('Select 2–5 valid JSON reports within the size limits.','۲ تا ۵ گزارش JSON معتبر در محدوده حجم انتخاب کنید.');return}
  if(!confirm(words('Read these local reports for comparison? No files will be sent or saved.','این گزارش‌های محلی برای مقایسه خوانده شوند؟ هیچ فایلی ارسال یا ذخیره نمی‌شود.')))return;
  const version=generation,expected=chatArchiveRecallContext(),epoch=current.epoch,steps=reviewSnapshot(current),captured=JSON.stringify(steps);
  const live=()=>files.isConnected&&version===generation&&canRecallCurrent(current)&&epoch===current.epoch&&JSON.stringify(expected)===JSON.stringify(chatArchiveRecallContext())&&captured===JSON.stringify(reviewSnapshot(current));
  files.disabled=true;
  try{
   const raw=await Promise.all(selected.map(f=>f.text()));if(!live())return;
   const planHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([current.draft,steps.map(s=>s.criterion.trim())])))),b=>b.toString(16).padStart(2,'0')).join('');
   if(!live())return;
   if(!current.reportSessionId)current.reportSessionId=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
   const context={sessionId:current.reportSessionId,round:current.round,planHash,steps},ops=raw.map(text=>{experienceImportEngine.prepareChatArchiveRecall(text,{...context,projectId:expected.projectId,threadId:expected.threadId,sessionRevision:expected.revision});return JSON.parse(text).operation});
   if(new Set(ops.map(o=>o.criterion_id)).size!==1||new Set(ops.map(o=>o.correction_code)).size!==ops.length||steps[Number(ops[0].criterion_id.slice(1))-1]?.verdict!=='fail')throw Error('incomparable-reports');
   reports=raw;
   const budget=num(form,words('Maximum cost (USD cents)','حداکثر هزینه (سنت دلار)'),100000000),time=num(form,words('Maximum effort (minutes)','حداکثر زمان (دقیقه)'),525600);
   form.append(make('p',words('Blank cost, effort, risk or reversibility means unknown. Scenario fields are optional unless enabled.','هزینه، زمان، ریسک یا بازگشت‌پذیری خالی یعنی نامشخص. تکمیل سناریو در صورت فعال‌سازی لازم است.')));
   const rows=ops.map(op=>{
    const group=make('fieldset');group.append(make('legend',op.correction_code+' / '+op.criterion_id));form.append(group);
    const cost=num(group,words('Expected cost (cents)','هزینه مورد انتظار (سنت)'),100000000),effort=num(group,words('Expected minutes','دقایق مورد انتظار'),525600);
    const risk=select(group,words('Risk','ریسک'),[['','Unknown','نامشخص'],['low','Low','کم'],['medium','Medium','متوسط'],['high','High','زیاد']]);
    const reversible=select(group,words('Reversible?','بازگشت‌پذیر؟'),[['','Unknown','نامشخص'],['yes','Yes','بله'],['no','No','خیر']]);
    const scenario=make('details');scenario.append(make('summary',words('Optional scenario estimates','برآورد اختیاری سناریو')));group.append(scenario);
    const check=make('input');check.type='checkbox';field(scenario,words('Include scenario','بررسی سناریو'),check);
    const bestCost=num(scenario,words('Best cost (cents)','بهترین هزینه (سنت)'),100000000),worstCost=num(scenario,words('Worst cost (cents)','بدترین هزینه (سنت)'),100000000);
    const bestTime=num(scenario,words('Best minutes','کمترین زمان (دقیقه)'),525600),worstTime=num(scenario,words('Worst minutes','بیشترین زمان (دقیقه)'),525600);
    const rb=make('input');rb.type='checkbox';field(scenario,words('Declare rollback contingency','تعریف برنامه بازگشت'),rb);
    const rc=num(scenario,words('Rollback cost (cents)','هزینه بازگشت (سنت)'),100000000),rt=num(scenario,words('Rollback minutes','زمان بازگشت (دقیقه)'),525600);
    const phrase=(title)=>{const n=make('input');n.type='text';n.maxLength=300;return field(scenario,title,n)};
    const trigger=phrase(words('Rollback trigger','شرط بازگشت')),restore=phrase(words('Restoration check','آزمون بازیابی'));
    return {op,cost,effort,risk,reversible,check,bestCost,worstCost,bestTime,worstTime,rb,rc,rt,trigger,restore};
   });
   const button=make('button',words('Review comparison','بازبینی مقایسه'));button.type='button';button.className='secondary';button.dataset.chatCompareRun='true';form.append(button);
   form.oninput=()=>{notice.textContent=''};form.onchange=form.oninput;
   button.onclick=()=>{
    if(!live()||!reports)return;
    notice.textContent='';
    try{
     const criterion_id=ops[0].criterion_id,comparison={criterion_id,max_cost_usd_cents:integer(budget),max_effort_minutes:integer(time),options:rows.map(x=>({correction_code:x.op.correction_code,cost_usd_cents:integer(x.cost,true),effort_minutes:integer(x.effort,true),risk:x.risk.value||null,reversible:x.reversible.value?x.reversible.value==='yes':null}))};
     const options=rows.filter(x=>x.check.checked).map(x=>({correction_code:x.op.correction_code,cost_usd_cents:{best:integer(x.bestCost),expected:integer(x.cost),worst:integer(x.worstCost)},effort_minutes:{best:integer(x.bestTime),expected:integer(x.effort),worst:integer(x.worstTime)},rollback:x.rb.checked?{cost_usd_cents:integer(x.rc),effort_minutes:integer(x.rt),trigger:x.trigger.value,restore_check:x.restore.value}:null}));
     const result=compareChatExperienceReports(reports,expected,context,comparison,options.length?{criterion_id,options}:undefined);
     if(!live())return;
     if(result.status!=='review_only'){notice.textContent=words('Comparison withheld: current review or recalled support is incomplete.','مقایسه متوقف شد: بازبینی فعلی یا پشتیبانی تجربه کافی نیست.');return}
     const labels={tradeoff_candidate:words('Trade-off candidate','گزینه قابل بررسی'),dominated_estimates:words('Less favorable estimates','برآورد نامطلوب‌تر'),outside_limits:words('Outside limits','خارج از محدودیت'),missing_estimates:words('Missing estimates','برآورد ناقص'),no_recalled_support:words('No recalled support','بدون پشتیبانی'),worst_case_outside_limits:words('Worst case exceeds limits','بدترین حالت خارج از محدودیت'),rollback_reserve_outside_limits:words('Rollback reserve exceeds limits','ذخیره بازگشت خارج از محدودیت'),rollback_details_missing:words('Rollback details missing','جزئیات بازگشت ناقص'),irreversible_review_required:words('Irreversible: review required','برگشت‌ناپذیر: نیازمند بازبینی'),within_declared_limits_review_required:words('Within declared limits: review required','در محدوده اعلامی: نیازمند بازبینی'),not_eligible_for_scenario_review:words('Scenario not eligible','سناریو قابل بررسی نیست')};
     const lines=make('ul');
     for(const o of result.comparison.options){const s=result.scenarios?.options.find(x=>x.correction_code===o.correction_code);lines.append(make('li',o.correction_code+' · '+(labels[o.status]||o.status)+(s?' · '+(labels[s.status]||s.status):'')+(s?.worst_with_rollback?words(' · Worst + rollback (cents / min): ',' · بدترین حالت + بازگشت (سنت / دقیقه): ')+s.worst_with_rollback.cost_usd_cents+' / '+s.worst_with_rollback.effort_minutes:'')))}
     notice.append(lines,make('p',words('Supplied estimates, not verified predictions. No option selected or applied.','برآوردهای واردشده، نه پیش‌بینی تأییدشده. هیچ گزینه‌ای انتخاب یا اعمال نشده.')));
    }catch{if(live())notice.textContent=words('Invalid or incomplete estimates/reports. No action taken.','برآوردها یا گزارش‌ها نامعتبر یا ناقص‌اند. اقدامی انجام نشد.')}
   };
  }catch{if(live()){reports=null;form.replaceChildren();notice.textContent=words('Reports rejected or incompatible.','گزارش‌ها رد شدند یا قابل مقایسه نیستند.')}}
  finally{if(files.isConnected&&version===generation)files.disabled=!canRecallCurrent(current)}
 };
 workflow.append(details);
}
function showWorkflow(){
 if(!workflowState)return;
 resetChatCorrectionPanel();resetChatCorrectionPanel=()=>{};workflow.hidden=false;workflow.replaceChildren();
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
  if(!window.NexusStudioUI.uiStatus().isolated){
   const criterionLabel=document.createElement('label'),criterion=document.createElement('input');
   criterionLabel.textContent=words('Success criterion (optional definition)','معیار موفقیت (تعریف اختیاری)');
   criterion.type='text';criterion.maxLength=260;criterion.value=step.criterion||'';
   criterion.dataset.centralCriterion=String(i);criterionLabel.append(criterion);
   const verdictLabel=document.createElement('label'),verdict=document.createElement('select');
   verdictLabel.textContent=words('Your result assessment (not independent proof)','ارزیابی شما از نتیجه (نه مدرک مستقل)');
   verdict.dataset.centralVerdict=String(i);
   for(const [value,en,fa] of [['','Not assessed','ارزیابی نشده'],['pass','Reported pass','موفق به گزارش شما'],['fail','Reported failure','ناموفق به گزارش شما'],['inconclusive','Inconclusive','نامشخص']]){
    const option=document.createElement('option');option.value=value;option.textContent=words(en,fa);verdict.append(option);
   }
   const invalidate=()=>{workflowState.epoch++;clearChatRecallResult();const recall=workflow.querySelector('[data-chat-recall-file]');if(recall)recall.disabled=!canRecallCurrent(workflowState);const n=workflow.querySelector('[data-central-result]');if(n)n.textContent='';const retry=workflow.querySelector('[data-central-restart]');if(retry)retry.disabled=!canCompareRound(workflowState)||workflowState.round>=100;const exp=workflow.querySelector('[data-experience-report]');if(exp)exp.disabled=!completeReportRounds(workflowState);const apply=workflow.querySelector('[data-experience-apply]');if(apply)apply.disabled=!completeReportRounds(workflowState)||!canApplyChatExperience();};
   const canAssess=()=>validWorkflow()&&!window.NexusStudioUI.uiStatus().isolated&&step.opened&&step.observed!=='started'&&!!humanCriterion(step).criterion;
   verdict.value=humanCriterion(step).verdict||'';verdict.disabled=!canAssess();
   criterion.oninput=()=>{
    if(!retainedWorkflow()||!criterion.isConnected||window.NexusStudioUI.uiStatus().isolated)return;
    workflowState.baseline=null;workflowState.history=[];step.criterion=criterion.value.slice(0,260);step.verdict=null;verdict.value='';verdict.disabled=!canAssess();invalidate();
   };
   verdict.onchange=()=>{
    if(!verdict.isConnected||!canAssess()){verdict.value='';return}
    step.verdict=['pass','fail','inconclusive'].includes(verdict.value)?verdict.value:null;invalidate();
   };
   verdictLabel.append(verdict);item.append(criterionLabel,verdictLabel);
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
 if(!window.NexusStudioUI.uiStatus().isolated){
  const restart=document.createElement('button');restart.type='button';restart.className='secondary';restart.dataset.centralRestart='true';
  restart.textContent=words('Review another round · compare results','بازبینی دور جدید و مقایسهٔ نتایج');
  restart.disabled=!canCompareRound(workflowState)||workflowState.round>=100;
  restart.onclick=()=>{
   if(!restart.isConnected||!validWorkflow()||window.NexusStudioUI.uiStatus().isolated||!canCompareRound(workflowState)||workflowState.round>=100)return;
   if(!confirm(words('Keep this assessment in up to 30 comparable review rounds in this tab only, to identify repeated failures? Changing criteria clears history. No tool runs automatically.','این ارزیابی در تاریخچهٔ حداکثر ۳۰ دور قابل‌مقایسه، فقط در همین برگه، برای تشخیص شکست‌های مکرر بماند؟ تغییر معیارها تاریخچه را پاک می‌کند. هیچ ابزاری خودکار اجرا نمی‌شود.')))return;
   workflowState=restartReviewedRound(workflowState);showWorkflow();
  };
  workflow.append(restart);
  appendExperienceReportControls();
  appendChatRecallControls();
  appendChatCorrectionControls();
  if(workflowState.history.length){
   const forget=document.createElement('button');forget.type='button';forget.className='secondary';forget.dataset.centralForget='true';
   forget.textContent=words('Clear previous review rounds','پاک‌کردن دورهای بازبینی پیشین');
   forget.onclick=()=>{
    if(!forget.isConnected||!retainedWorkflow()||window.NexusStudioUI.uiStatus().isolated)return;
    workflowState=forgetReviewedHistory(workflowState);showWorkflow();
   };
   workflow.append(forget);
  }
 }
}
function reviewWorkflow(message){
 closeDirectory();clearOffer();
 const parsed=parseWorkflow(message);
 if(parsed.error){workflowError(parsed.error);return}
 workflowState={draft:message,scope:workflowScope(),round:1,epoch:0,baseline:null,history:[],steps:parsed.steps.map(step=>({
  ...step,opened:false,acknowledged:false,runId:null,observed:null,criterion:'',verdict:null
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
 if(detail.phase==='started'){step.runId=detail.runId;step.observed='started';step.verdict=null}
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
document.addEventListener('nexus-studio-state',()=>{clearChatRecallResult();refresh();const recall=workflow.querySelector('[data-chat-recall-file]');if(recall)recall.disabled=!canRecallCurrent(workflowState)});
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
