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

/* Explicit adaptive planning from chat; never dispatch a workflow operation. */
const adaptive=document.createElement('section');adaptive.id='studio-adaptive';adaptive.hidden=true;adaptive.className='studio-compose';
const adaptiveButton=document.createElement('button');adaptiveButton.id='studio-adaptive-open';adaptiveButton.type='button';adaptiveButton.className='secondary';
adaptiveButton.dataset.en='Plan work';adaptiveButton.dataset.fa='برنامه‌ریزی کار';adaptiveButton.setAttribute('aria-controls',adaptive.id);
suggestions.append(adaptiveButton);directory.after(adaptive);
const adaptiveLabels=[];
function adaptiveLabel(element,en,fa){adaptiveLabels.push(()=>{element.textContent=words(en,fa)});return element}
function adaptiveSelect(id,values,en,fa){
 const label=document.createElement('label'),title=document.createElement('span'),field=document.createElement('select');
 field.id=id;label.htmlFor=id;adaptiveLabel(title,en,fa);
 for(const [value,a,b] of values){const opt=document.createElement('option');opt.value=value;adaptiveLabel(opt,a,b);field.append(opt)}
 label.append(title,field);adaptive.append(label);return field;
}
const adaptiveTitle=adaptiveLabel(document.createElement('h3'),'Reviewed work plan','برنامهٔ کار قابل بازبینی');
const adaptiveNotice=adaptiveLabel(document.createElement('p'),
 'Planning sends only your entered goal and settings to the configured Studio gateway, not files or conversation history. No operation or model call runs. Steps are review reminders, not proof of execution.',
 'برنامه‌ریزی فقط هدف واردشده و تنظیمات را به درگاه نکسوس می‌فرستد، نه فایل‌ها یا سابقهٔ گفتگو. هیچ عملیات یا فراخوانی مدل انجام نمی‌شود. گام‌ها یادآور بازبینی‌اند، نه مدرک اجرا.');
adaptiveNotice.className='help';adaptive.append(adaptiveTitle,adaptiveNotice);
const adaptiveGoal=document.createElement('textarea');adaptiveGoal.id='studio-adaptive-goal';adaptiveGoal.maxLength=1000;adaptiveGoal.dir='auto';
const goalLabel=document.createElement('label');goalLabel.htmlFor=adaptiveGoal.id;
goalLabel.append(adaptiveLabel(document.createElement('span'),'Goal (do not include private data)','هدف (اطلاعات خصوصی وارد نکنید)'),adaptiveGoal);adaptive.append(goalLabel);
const adaptiveTask=adaptiveSelect('studio-adaptive-task',[
 ['document_answer','Answer from documents','پاسخ بر اساس اسناد'],['document_privacy','DOCX privacy review','حریم خصوصی Word'],
 ['manuscript_review','Manuscript review','بازبینی مقاله'],['research_synthesis','Research synthesis','ترکیب پژوهش'],
 ['paired_statistics','Paired statistics','آمار زوجی'],['general_chat','General chat','گفتگوی عمومی']
],'Task','نوع کار');
const adaptivePrivacy=adaptiveSelect('studio-adaptive-privacy',[
 ['studio_only','Studio gateway only','فقط درگاه نکسوس'],['device_only','Device only — no network','فقط دستگاه — بدون شبکه'],
 ['provider_allowed','Provider steps may be proposed','پیشنهاد مراحل مدل خارجی مجاز باشد']
],'Privacy','حریم خصوصی');
const adaptiveQuality=adaptiveSelect('studio-adaptive-quality',[
 ['extractive','Exact excerpts','قطعات دقیق متن'],['draft','Model draft','پیش‌نویس مدل'],
 ['critique','Draft and critique','پیش‌نویس و نقد'],['comparative','Compare two critiques','مقایسهٔ دو نقد']
],'Depth','عمق پردازش');
const adaptiveCount=adaptiveSelect('studio-adaptive-count',[['1','1','۱'],['2','2','۲'],['3','3','۳']],'Document count','تعداد اسناد');
const adaptiveSlot=adaptiveSelect('studio-adaptive-slot',[
 ['primary','Primary','اصلی'],['secondary','Secondary','دوم'],['tertiary','Tertiary','سوم']
],'Preferred model slot','مسیر مدل ترجیحی');
const adaptiveActions=document.createElement('div');adaptiveActions.className='row';
const adaptiveReview=adaptiveLabel(document.createElement('button'),'Review plan on gateway','بازبینی برنامه در درگاه');
adaptiveReview.id='studio-adaptive-review';adaptiveReview.type='button';
const adaptiveClose=adaptiveLabel(document.createElement('button'),'Discard plan','کنارگذاشتن برنامه');
adaptiveClose.id='studio-adaptive-close';adaptiveClose.type='button';adaptiveClose.className='secondary';
adaptiveActions.append(adaptiveReview,adaptiveClose);
const adaptiveStatus=document.createElement('p');adaptiveStatus.id='studio-adaptive-status';adaptiveStatus.setAttribute('role','status');adaptiveStatus.className='help';
const adaptiveList=document.createElement('div');adaptiveList.id='studio-adaptive-steps';
adaptive.append(adaptiveActions,adaptiveStatus,adaptiveList);
let adaptiveState=null,adaptiveAbort=null,adaptiveEpoch=0,adaptiveScope=null;
const adaptiveFields=[adaptiveGoal,adaptiveTask,adaptivePrivacy,adaptiveQuality,adaptiveCount,adaptiveSlot];
function adaptiveReset(close=false){
 adaptiveEpoch++;adaptiveAbort?.abort();adaptiveAbort=null;adaptiveState=null;
 adaptiveList.replaceChildren();adaptiveStatus.textContent='';
 if(close){adaptive.hidden=true;adaptiveGoal.value='';adaptiveScope=null;adaptiveButton.setAttribute('aria-expanded','false')}
 adaptiveRefresh();
}
function adaptiveRefresh(){
 adaptiveLabels.forEach(fn=>fn());
 const documentTask=adaptiveTask.value==='document_answer'||adaptiveTask.value==='document_privacy';
 adaptiveCount.parentElement.hidden=!documentTask;
 adaptiveCount.disabled=adaptiveTask.value==='document_privacy'||Boolean(adaptiveAbort);
 if(adaptiveTask.value==='document_privacy')adaptiveCount.value='1';
 adaptiveQuality.parentElement.hidden=adaptiveTask.value!=='document_answer';
 if(adaptiveTask.value!=='document_answer')adaptiveQuality.value='extractive';
 adaptiveSlot.parentElement.hidden=adaptivePrivacy.value!=='provider_allowed';
 adaptiveReview.disabled=Boolean(adaptiveAbort)||!adaptiveGoal.value.trim();
}
function adaptiveInput(){
 return {task:adaptiveTask.value,goal:adaptiveGoal.value.trim(),privacy:adaptivePrivacy.value,
  quality:adaptiveTask.value==='document_answer'?adaptiveQuality.value:'extractive',
  preferred_slot:adaptiveSlot.value,
  document_count:['document_answer','document_privacy'].includes(adaptiveTask.value)?Number(adaptiveCount.value):0};
}
function adaptiveOrigin(){
 const raw=$('gateway').value.trim(),u=new URL(raw||location.origin);
 if((u.protocol!=='https:'&&!(u.protocol==='http:'&&['127.0.0.1','[::1]'].includes(u.hostname)))||
    u.username||u.password||u.search||u.hash||!['','/'].includes(u.pathname))throw Error('gateway');
 return u.origin;
}
function adaptivePrivate(){
 const scope=window.NexusStudioUI.selection?.()||{};
 if(!scope.threadId)return false;
 const project=window.NexusStudioUI.snapshot().projects.find(p=>p.id===scope.projectId);
 return Boolean(project?.threads.find(t=>t.id===scope.threadId)?.isolated);
}
async function adaptiveRequest(path,body,origin,token){
 const epoch=++adaptiveEpoch,controller=new AbortController();adaptiveAbort=controller;adaptiveRefresh();
 const timeout=setTimeout(()=>controller.abort(),15000);
 try{
  const response=await fetch(origin+path,{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',
   redirect:'error',referrerPolicy:'no-referrer',headers:{'content-type':'application/json','authorization':'Bearer '+token},
   body:JSON.stringify(body),signal:controller.signal});
  if(!response.ok)throw Error('review-failed');
  const raw=await response.text();if(raw.length>64000)throw Error('oversize');
  const result=JSON.parse(raw);
  if(epoch!==adaptiveEpoch||adaptive.hidden||adaptiveScope!==workflowScope()||adaptivePrivate())return null;
  if(result.execution_authorized!==false||result.automatic_dispatch!==false)throw Error('invalid-authority');
  return result;
 }catch{
  if(epoch===adaptiveEpoch)adaptiveStatus.textContent=words('Review unavailable or changed. Review the plan again.','بازبینی در دسترس نیست یا تغییر کرده است؛ برنامه را دوباره بازبینی کنید.');
  return null;
 }finally{
  clearTimeout(timeout);if(epoch===adaptiveEpoch){adaptiveAbort=null;adaptiveRefresh()}
 }
}
function adaptiveRender(){
 adaptiveList.replaceChildren();if(!adaptiveState)return;
 const {plan,acknowledged}=adaptiveState;
 const list=document.createElement('ol');
 for(const step of plan.workflow.plan.steps){
  const li=document.createElement('li'),handoff=plan.handoffs.find(h=>h.step_id===step.id);
  const detail=document.createElement('span');
  detail.textContent=step.description+' · '+(handoff.model_slot||handoff.boundary);
  li.append(detail);
  if(acknowledged.includes(step.id))li.append(document.createTextNode(' · '+words('Acknowledged, not verified','بازبینی اعلام شده، نه اجرای تأییدشده')));
  else if(step.depends_on.every(id=>acknowledged.includes(id))){
   const button=document.createElement('button');button.type='button';button.className='secondary';
   button.textContent=words('Mark reviewed','علامت بازبینی');
   button.onclick=()=>adaptiveAdvance(step.id);li.append(button);
  }
  list.append(li);
 }
 adaptiveList.append(list);
 if(plan.blockers.length){
  const p=document.createElement('p');p.textContent=words('Requested route blocked: ','مسیر درخواستی مسدود است: ')+plan.blockers.join(', ');adaptiveList.append(p);
 }
 if(acknowledged.length===plan.workflow.plan.steps.length){
  const p=document.createElement('p');p.textContent=words('All reminders acknowledged; task execution is not verified.','همهٔ یادآورها بازبینی شدند؛ اجرای کار تأیید نشده است.');adaptiveList.append(p);
 }
}
function validAdaptivePlan(out,input){
 const steps=out?.workflow?.plan?.steps,hs=out?.handoffs;
 if(!/^[a-f0-9]{64}$/.test(out?.route_sha256)||JSON.stringify(out.request)!==JSON.stringify(input)||
    !Array.isArray(steps)||!steps.length||steps.length>12||!Array.isArray(hs)||hs.length!==steps.length||
    !Array.isArray(out.blockers)||out.blockers.some(b=>typeof b!=='string')||
    new Set(steps.map(s=>s.id)).size!==steps.length)return false;
 return steps.every((s,i)=>typeof s.id==='string'&&typeof s.description==='string'&&Array.isArray(s.depends_on)&&
  s.depends_on.every(id=>steps.slice(0,i).some(previous=>previous.id===id))&&
  hs[i]?.step_id===s.id&&hs[i].automatic_dispatch===false&&['studio','provider','human'].includes(hs[i].boundary)&&
  (input.privacy==='provider_allowed'||hs[i].boundary!=='provider'));
}
adaptiveButton.onclick=()=>{
 if(!adaptive.hidden){adaptiveReset(true);return}
 if(adaptivePrivate())return;
 adaptive.hidden=false;adaptiveScope=workflowScope();adaptiveButton.setAttribute('aria-expanded','true');
 adaptiveGoal.value='';adaptiveRefresh();adaptiveGoal.focus();
};
adaptiveClose.onclick=()=>adaptiveReset(true);
adaptiveFields.forEach(field=>field.addEventListener('input',()=>adaptiveReset()));
for(const id of ['gateway','gateway-token'])$(id).addEventListener('input',()=>adaptiveReset());
adaptiveReview.onclick=async()=>{
 if(adaptiveAbort||adaptivePrivate()||adaptiveScope!==workflowScope())return;
 const input=adaptiveInput();adaptiveReset();
 if(!input.goal)return;
 if(input.privacy==='device_only'){
  adaptiveStatus.textContent=words('Device-only selected. No data sent; use local tools.','فقط دستگاه انتخاب شد. داده‌ای ارسال نشد؛ از ابزارهای محلی استفاده کنید.');return;
 }
 let origin;try{origin=adaptiveOrigin()}catch{adaptiveStatus.textContent=words('Configure a valid gateway.','درگاه معتبر تنظیم کنید.');return}
 const token=$('gateway-token').value.trim();
 if(token.length<32){adaptiveStatus.textContent=words('Enter the Studio gateway access token in model settings.','توکن دسترسی درگاه را در تنظیمات مدل وارد کنید.');return}
 if(!confirm(words('Send this goal and settings to '+origin+' for planning only?','فقط برای برنامه‌ریزی، هدف و تنظیمات به '+origin+' ارسال شود؟')))return;
 const out=await adaptiveRequest('/studio/api/workflow/adaptive/review',input,origin,token);
 if(!out)return;
 if(!validAdaptivePlan(out,input)){adaptiveStatus.textContent=words('Invalid plan response.','پاسخ برنامه نامعتبر است.');return}
 adaptiveState={plan:out,input,origin,acknowledged:[]};adaptiveStatus.textContent=words('Review reminders only. No operations have run.','فقط یادآور بازبینی؛ هیچ عملیاتی اجرا نشده است.');adaptiveRender();
};
async function adaptiveAdvance(id){
 if(adaptiveAbort||!adaptiveState||adaptivePrivate()||adaptiveScope!==workflowScope())return;
 const state=adaptiveState,step=state.plan.workflow.plan.steps.find(s=>s.id===id);
 if(!step||state.acknowledged.includes(id)||!step.depends_on.every(d=>state.acknowledged.includes(d)))return;
 const acknowledged=[...state.acknowledged,id];
 const token=$('gateway-token').value.trim();if(token.length<32||adaptiveOrigin()!==state.origin){adaptiveReset();return}
 const out=await adaptiveRequest('/studio/api/workflow/adaptive/progress',
  {request:state.input,route_sha256:state.plan.route_sha256,acknowledged,cancelled:false},state.origin,token);
 if(!out)return;
 if(out.route_sha256!==state.plan.route_sha256||out.requested_task_completion_verified!==false||
    out.progress?.evidence!=='caller_reported_only'||JSON.stringify(out.progress.acknowledged)!==JSON.stringify(acknowledged)){
  adaptiveReset();adaptiveStatus.textContent=words('Progress response invalid; review again.','پاسخ پیشرفت نامعتبر است؛ دوباره بازبینی کنید.');return;
 }
 state.acknowledged=acknowledged;adaptiveRender();
}
document.addEventListener('nexus-studio-private-clear',()=>adaptiveReset(true));
document.addEventListener('nexus-studio-state',()=>{
 if(!adaptive.hidden&&(adaptiveScope!==workflowScope()||adaptivePrivate()))adaptiveReset(true);
});
$('language').addEventListener('change',()=>queueMicrotask(()=>{adaptiveRefresh();adaptiveRender()}));
adaptiveRefresh();

/* Explicit document retrieval in chat. Full files go only to the reviewed gateway. */
const docPanel=document.createElement('section');docPanel.id='studio-document-workflow';docPanel.hidden=true;docPanel.className='studio-compose';
const docOpen=document.createElement('button');docOpen.id='studio-document-open';docOpen.type='button';docOpen.className='secondary';
docOpen.dataset.en='Ask documents';docOpen.dataset.fa='پرسش از اسناد';docOpen.setAttribute('aria-controls',docPanel.id);docOpen.setAttribute('aria-expanded','false');
suggestions.append(docOpen);adaptive.after(docPanel);
const docLabels=[];
function docLabel(el,en,fa){docLabels.push(()=>{el.textContent=words(en,fa)});return el}
const docTitle=docLabel(document.createElement('h3'),'Find evidence in documents','یافتن شواهد در اسناد');
const docNotice=docLabel(document.createElement('p'),'Select up to 3 TXT or DOCX files (2 MiB total). This sends entire selected files to your configured Studio gateway only after you approve. It does not send conversation history or call a language model. Results are exact extracted excerpts, not a synthesized answer.','حداکثر ۳ فایل متنی یا Word (مجموعاً ۲ مگابایت) انتخاب کنید. فقط پس از تأیید شما، تمام فایل‌های منتخب به درگاه تنظیم‌شدهٔ نکسوس ارسال می‌شوند. سابقهٔ گفتگو ارسال نمی‌شود و مدل زبانی فراخوانی نمی‌شود. نتیجه قطعهٔ متن استخراج‌شده است، نه پاسخ ترکیبی.');
docNotice.className='help';
const docFiles=document.createElement('input');docFiles.id='studio-document-files';docFiles.type='file';docFiles.multiple=true;docFiles.accept='.txt,.docx';
const docFileLabel=document.createElement('label');docFileLabel.htmlFor=docFiles.id;docFileLabel.append(docLabel(document.createElement('span'),'Documents','اسناد'),docFiles);
const docQuery=document.createElement('input');docQuery.id='studio-document-query';docQuery.maxLength=250;docQuery.dir='auto';
const docQueryLabel=document.createElement('label');docQueryLabel.htmlFor=docQuery.id;docQueryLabel.append(docLabel(document.createElement('span'),'Search words (1–16 distinct words)','واژه‌های جست‌وجو (۱ تا ۱۶ واژهٔ متفاوت)'),docQuery);
const docMatch=document.createElement('select');docMatch.id='studio-document-match';
for(const [v,en,fa] of [['all','All words','همهٔ واژه‌ها'],['any','Any word','هر یک از واژه‌ها']]){const opt=document.createElement('option');opt.value=v;docMatch.append(docLabel(opt,en,fa))}
const docMatchLabel=document.createElement('label');docMatchLabel.htmlFor=docMatch.id;docMatchLabel.append(docLabel(document.createElement('span'),'Match','تطبیق'),docMatch);
const docTables=document.createElement('input');docTables.type='checkbox';docTables.id='studio-document-tables';
const docTableLabel=document.createElement('label');docTableLabel.className='inline';docTableLabel.append(docTables,docLabel(document.createElement('span'),'Include direct Word table cells','شامل سلول‌های مستقیم جدول Word'));
const docActions=document.createElement('div');docActions.className='row';
function docButton(id,en,fa){const b=docLabel(document.createElement('button'),en,fa);b.id=id;b.type='button';return b}
const docReview=docButton('studio-document-review','Review files on gateway','بازبینی فایل‌ها در درگاه');
const docRun=docButton('studio-document-run','Approve retrieval','تأیید بازیابی');docRun.hidden=true;
const docClose=docButton('studio-document-close','Discard files and results','کنارگذاشتن فایل‌ها و نتایج');docClose.className='secondary';
docActions.append(docReview,docRun,docClose);
const docStatus=document.createElement('p');docStatus.id='studio-document-status';docStatus.className='help';docStatus.setAttribute('role','status');
const docResults=document.createElement('div');docResults.id='studio-document-results';
docPanel.append(docTitle,docNotice,docFileLabel,docQueryLabel,docMatchLabel,docTableLabel,docActions,docStatus,docResults);
let docEpoch=0,docAbort=null,docState=null,docScope=null;
const docHash=s=>typeof s==='string'&&/^[a-f0-9]{64}$/.test(s);
function docRefresh(){
 docLabels.forEach(fn=>fn());
 docReview.disabled=Boolean(docAbort)||!docFiles.files.length||!docQuery.value.trim();
 docRun.disabled=Boolean(docAbort)||!docState;docRun.hidden=!docState;
}
function docReset(close=false){
 docEpoch++;docAbort?.abort();docAbort=null;docState=null;docResults.replaceChildren();docStatus.textContent='';
 if(close){docFiles.value='';docQuery.value='';docTables.checked=false;docMatch.value='all';docScope=null;docPanel.hidden=true;docOpen.setAttribute('aria-expanded','false')}
 docRefresh();
}
function docCurrent(epoch){return epoch===docEpoch&&!docPanel.hidden&&docScope===workflowScope()&&!adaptivePrivate()}
function docDestination(){
 if(!$('gateway').value.trim())throw Error('gateway');
 const origin=adaptiveOrigin(),token=$('gateway-token').value.trim();
 if(token.length<32)throw Error('token');
 return {origin,token};
}
function docError(){docStatus.textContent=words('Document request failed or changed. Review again.','درخواست سند ناموفق بود یا تغییر کرد؛ دوباره بازبینی کنید.')}
async function docPost(path,body,destination,controller){
 const response=await fetch(destination.origin+path,{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',
  headers:{'content-type':'application/json','authorization':'Bearer '+destination.token},body:JSON.stringify(body),signal:controller.signal});
 if(!response.ok||!response.body)throw Error('request');
 const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let total=0,raw='';
 try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>262144)throw Error('response-size');raw+=decoder.decode(value,{stream:true})}raw+=decoder.decode()}
 finally{await reader.cancel().catch(()=>{});reader.releaseLock()}
 const out=JSON.parse(raw);
 if(out.execution_authorized!==false||out.provider_contact_attempted!==false||out.provider_disclosure_authorized!==false)throw Error('authority');
 return out;
}
function docBase64(bytes){
 let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
 return btoa(binary);
}
function docReviewValid(out,plan){
 return out.status==='review_only'&&docHash(out.review_sha256)&&docHash(out.search_review_sha256)&&Array.isArray(out.documents)&&
  out.documents.length===plan.documents.length&&out.documents.every((d,i)=>d.document_id===plan.documents[i].id&&docHash(d.input_sha256)&&docHash(d.extraction_review_sha256)&&Number.isInteger(d.block_count)&&d.block_count>0);
}
docOpen.onclick=()=>{
 if(!docPanel.hidden){docReset(true);return}
 if(adaptivePrivate())return;
 docScope=workflowScope();docPanel.hidden=false;docOpen.setAttribute('aria-expanded','true');docRefresh();docFiles.focus();
};
docClose.onclick=()=>docReset(true);
docFiles.addEventListener('change',()=>docReset());
for(const f of [docQuery,docMatch,docTables,$('gateway'),$('gateway-token')])f.addEventListener('input',()=>docReset());
document.addEventListener('nexus-studio-private-clear',()=>docReset(true));
document.addEventListener('nexus-studio-state',()=>{if(!docPanel.hidden&&(docScope!==workflowScope()||adaptivePrivate()))docReset(true)});
$('language').addEventListener('change',()=>queueMicrotask(docRefresh));
docReview.onclick=async()=>{
 if(docAbort||docPanel.hidden||adaptivePrivate()||docScope!==workflowScope())return;
 const files=Array.from(docFiles.files),query=docQuery.value.trim(),match=docMatch.value,tables=docTables.checked;
 docReset();
 let destination;
 try{destination=docDestination()}catch{docStatus.textContent=words('Configure a Studio gateway and access token first.','ابتدا درگاه نکسوس و توکن دسترسی را تنظیم کنید.');return}
 if(!query||files.length<1||files.length>3||files.some(f=>!/\.(txt|docx)$/i.test(f.name)||f.size===0)||files.reduce((n,f)=>n+f.size,0)>2097152||
    files.reduce((n,f)=>n+4*Math.ceil(f.size/3),0)>2796204){
  docStatus.textContent=words('Choose 1–3 supported files within the total size limit.','۱ تا ۳ فایل پشتیبانی‌شده در محدودهٔ حجم مجاز انتخاب کنید.');return;
 }
 if(!confirm(words('Send the entire selected files and search words to '+destination.origin+' for review? No model call.','تمام فایل‌های منتخب و واژه‌های جست‌وجو برای بازبینی به '+destination.origin+' ارسال شوند؟ مدل فراخوانی نمی‌شود.')))return;
 const epoch=++docEpoch,controller=new AbortController();docAbort=controller;docRefresh();
 const timer=setTimeout(()=>controller.abort(),20000);
 try{
  const documents=[];
  for(const [i,f] of files.entries()){
   const format=f.name.toLowerCase().endsWith('.docx')?'docx':'txt';
   const bytes=new Uint8Array(await f.arrayBuffer());if(!docCurrent(epoch)||controller.signal.aborted)return;
   if(bytes.length!==f.size)throw Error('file-size');
   documents.push({id:'doc-'+(i+1),extraction:{format,content_base64:docBase64(bytes),include_table_cells:format==='docx'&&tables}});
  }
  const plan={documents,query,match,limit:8};
  const out=await docPost('/studio/api/documents/workflow/review',plan,destination,controller);
  if(!docCurrent(epoch)||controller.signal.aborted)return;
  if(!docReviewValid(out,plan))throw Error('invalid-review');
  docState={plan,review:out,origin:destination.origin,names:files.map(f=>f.name)};
  docStatus.textContent=words('Review ready. Approve separately to retrieve excerpts.','بازبینی آماده است. برای بازیابی قطعات متن جداگانه تأیید کنید.');
  for(const [i,d] of out.documents.entries()){
   const line=document.createElement('p');line.textContent=docState.names[i]+' · '+d.block_count+' '+words('blocks','بلوک');
   const flags=Object.keys(d.skipped_counts||{}).length+Object.keys(d.package_privacy_findings||{}).filter(k=>d.package_privacy_findings[k]>0).length;
   if(flags)line.textContent+=' · '+words('Omissions/privacy indicators require review','نشانه‌های حذف یا حریم خصوصی نیازمند بررسی‌اند');
   docResults.append(line);
  }
 }catch{if(docCurrent(epoch))docError()}
 finally{clearTimeout(timer);if(epoch===docEpoch){docAbort=null;docRefresh()}}
};
docRun.onclick=async()=>{
 if(docAbort||!docState||!docCurrent(docEpoch))return;
 const state=docState;let destination;
 try{destination=docDestination()}catch{docReset();docError();return}
 if(destination.origin!==state.origin){docReset();docError();return}
 if(!confirm(words('Resend these same files to retrieve exact excerpts from '+destination.origin+'?','همین فایل‌ها برای بازیابی قطعات دقیق متن به '+destination.origin+' دوباره ارسال شوند؟')))return;
 const epoch=++docEpoch,controller=new AbortController();docAbort=controller;docRefresh();
 const timer=setTimeout(()=>controller.abort(),20000);
 try{
  const out=await docPost('/studio/api/documents/workflow/run',{plan:state.plan,review_sha256:state.review.review_sha256,consent:true},destination,controller);
  if(!docCurrent(epoch)||controller.signal.aborted)return;
  const bundle=out.evidence;
  if(out.review_sha256!==state.review.review_sha256||out.semantic_verification!==false||bundle?.model_called!==false||
     bundle.search_review_sha256!==state.review.search_review_sha256||!docHash(bundle.evidence_sha256)||!Array.isArray(bundle.sources)||
     bundle.sources.length>8||bundle.source_count!==bundle.sources.length||
     out.status!==(bundle.sources.length?'extractive_evidence_available':'no_lexical_match'))throw Error('result');
  const fragment=document.createDocumentFragment();
  for(const row of bundle.sources){
   const index=state.review.documents.findIndex(d=>d.document_id===row.document_id&&d.input_sha256===row.input_sha256);
   if(index<0||typeof row.excerpt!=='string'||row.excerpt.length<1||row.excerpt.length>800||
      typeof row.evidence_id!=='string'||!/^e-[a-f0-9]{64}$/.test(row.evidence_id)||!docHash(row.block_sha256)||!docHash(row.excerpt_sha256)||
      !Number.isInteger(row.block_index)||row.block_index<0||row.block_index>=state.review.documents[index].block_count||
      !Number.isInteger(row.excerpt_start)||row.excerpt_start<0||!Number.isInteger(row.excerpt_end)||
      row.excerpt_end-row.excerpt_start!==Array.from(row.excerpt).length||row.content_trust!=='untrusted_document_text')throw Error('source');
   const article=document.createElement('article'),heading=document.createElement('strong'),body=document.createElement('p');
   heading.textContent=state.names[index]+' · '+words('Block','بلوک')+' '+(row.block_index+1)+' · '+row.excerpt_start+'–'+row.excerpt_end;
   body.dir='auto';body.style.whiteSpace='pre-wrap';body.textContent=row.excerpt;
   article.append(heading,body);fragment.append(article);
  }
  docResults.replaceChildren(fragment);
  docStatus.textContent=bundle.sources.length?words('Exact excerpts; relevance and truth are not verified.','قطعات دقیق متن؛ ارتباط و صحت آن‌ها تأیید نشده است.'):words('No lexical match. This does not prove absence.','تطابق واژگانی یافت نشد؛ این به معنای نبود اطلاعات نیست.');
  if(bundle.truncated===true)docStatus.textContent+=' '+words('More matching blocks exist.','بلوک‌های منطبق بیشتری وجود دارد.');
  docState=null;docFiles.value='';
 }catch{if(docCurrent(epoch)){docState=null;docResults.replaceChildren();docError()}}
 finally{clearTimeout(timer);if(epoch===docEpoch){docAbort=null;docRefresh()}}
};
docRefresh();

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
