/* NEXUS reviewed chat composer; no implicit execution. */
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
 ['model','Review AI model request','بازبینی درخواست مدل هوش مصنوعی']
]){const o=document.createElement('option');o.value=value;o.dataset.en=en;o.dataset.fa=fa;select.append(o)}
const send=document.createElement('button');send.type='button';send.id='studio-compose-send';
const save=document.createElement('button');save.type='button';save.id='studio-compose-save';save.className='secondary';
const config=document.createElement('button');config.type='button';config.id='studio-compose-config';config.className='secondary';
const privacy=document.createElement('p');privacy.id='studio-compose-privacy';privacy.className='help';
privacy.setAttribute('role','note');
const storage=document.createElement('p');storage.id='studio-compose-storage';storage.className='help';storage.setAttribute('role','status');storage.setAttribute('aria-live','polite');
selectLabel.append(select);row.append(send,save);
mode.append(heading,selectLabel,config,privacy);
box.append(row,mode,storage);
$('branch-notice').after(box);

/* Discover capability from a typed request; proposal only, never execute. */
const suggestions=document.createElement('div');suggestions.id='nexus-zen-suggestions';
box.prepend(suggestions);
const offer=document.createElement('div');offer.id='nexus-zen-offer';offer.hidden=true;offer.setAttribute('role','status');box.after(offer);
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
 ['export','canvas-card','Document export','خروجی سند',null,'download'],
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
const planPreview=document.createElement('button');
planPreview.type='button';planPreview.className='secondary';
planPreview.id='studio-assistant-plan-preview';
planPreview.dataset.en='Plan steps';planPreview.dataset.fa='برنامه‌ریزی مراحل';
suggestions.append(planPreview);
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
 if(!/(بساز|ساخت|تولید|طراحی|بنویس|تنظیم|compose|create|make|generate|write|export|download|analy[sz]e|search|find|draw|run|open|launch|list|show|check|اجرا|بررسی|تحلیل|نمایش|نشان\s*بده|وضعیت|باز\s*کن|بازکردن|برو\s+به|جست\s*و\s*جو|خروجی\s*بگیر|دریافت)/i.test(s))return null;
 const kind=/\b(?:export|download)\b|خروجی\s*بگیر|دریافت\s*(?:فایل|سند)/i.test(s)?'export':
  /(github|گیت\s*هاب|گیتهاب|pull requests?|درخواست(?:‌|\s)*ادغام)/i.test(s)?'github':
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
/* Connector suggestions never grant execution authority. */
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

/* Every workflow step requires independent human review. */
const workflow=document.createElement('section');
workflow.id='studio-chat-workflow';workflow.className='studio-compose';
workflow.hidden=true;workflow.setAttribute('aria-label','Reviewed workflow');
directory.after(workflow);
let workflowState=null,previewDraft=null,previewController=null;
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
function clearLocalReviewers(){
 window.NexusLabUI?.clearReviewedStep?.();
 window.NexusQualityUI?.clearReviewedStep?.();
 window.NexusMusicUI?.clearReviewedStep?.();
 window.NexusOrchestraUI?.clearReviewedStep?.();
 window.NexusTasksUI?.clearReviewedStep?.();
 window.NexusStudioUI?.clearDocumentReceipt?.();
 window.NexusStudioUI?.clearExportReceipt?.();
}
function clearWorkflow(){
 clearLocalReviewers();
 previewController?.abort();previewController=null;previewDraft=null;
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
function openReviewedSurface(result,message,{readOperation=null,onReadReceipt=null}={}){
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
  if(readOperation){request.operation=readOperation;request.onReadReceipt=onReadReceipt}
  if(!window.NexusStudioConnections?.openFor?.(request)){
   if(readOperation)return false;
   const entry=$('studio-connections-open');
   if(entry&&!entry.disabled)entry.click();
  }
  return $('studio-connections')?.open===true;
 }
 window.NexusStudioFocus?.openPanel(panel);
 return true;
}
/* Receipts distinguish read-only gateway results from self-reports. */
function expectedRead(step){
 const kind=step.result.route[0];
 if(kind==='render')return 'render.deploys';
 if(kind==='github'&&connectionRequest(step.result,step.line).operation==='github.pulls')
  return 'github.pulls';
 return null;
}
function expectedLocal(step){
 const kind=step.result.route[0];
 return ['research','code','data','write','export','music','orchestra','tasks'].includes(kind)?kind:null;
}
function showWorkflow(){
 if(!workflowState)return;
 workflow.hidden=false;workflow.replaceChildren();
 const plan=workflowState;
 const title=document.createElement('strong');
 title.textContent=words('Your reviewed workflow','گردش‌کار قابل بازبینی');
 const info=document.createElement('p');info.className='help';
 info.textContent=words(
  'Opening is not execution. Tools need fresh results; scores do not prove WAV quality. Tasks require every job to succeed. Exports request downloads, not delivery. Save work separately; nothing runs automatically.',
  'بازکردن ابزار اجرا نیست. هر ابزار نتیجهٔ تازه می‌خواهد؛ در وظایف همهٔ کارها باید موفق شوند. پارتیتور تضمین WAV نیست؛ خروجی سند فقط درخواست دانلود است. ذخیره و اجرا نیاز به اقدام جداگانه دارند.');
 const list=document.createElement('ol');
 plan.steps.forEach((step,i)=>{
  const item=document.createElement('li'),span=document.createElement('span');
  const status=i<plan.index?
   step.outcome==='gateway_read'?
    words('gateway read returned · untrusted data','پاسخ خواندن از درگاه دریافت شد · دادهٔ غیرقابل‌اعتماد'):
   step.outcome==='local_observed'?
    words('local tool completed · output untrusted','ابزار محلی اجرا شد · خروجی غیرقابل‌اعتماد'):
   step.outcome==='document_version'?
    words('new document version applied · session only','نسخهٔ جدید سند اعمال شد · فقط نشست جاری'):
   step.outcome==='download_requested'?
    words('file download requested · delivery unverified','درخواست دانلود فایل · دریافت تأییدنشده'):
   step.outcome==='print_requested'?
    words('print dialog requested · Save as PDF unverified','درخواست پنجرهٔ چاپ · ذخیرهٔ PDF تأییدنشده'):
   step.outcome==='skipped'?
    words('skipped by you','با انتخاب شما رد شد'):
    words('confirmed by you · not independently verified','به تأیید شما · بدون راستی‌آزمایی مستقل'):
   i===plan.index?words('current','گام فعلی'):words('not started','شروع‌نشده');
  span.textContent=step.line+' · '+status;
  item.append(span);
  if(i===plan.index){
   const required=expectedRead(step),local=expectedLocal(step);
   const receiptKey=required||local;
   const open=document.createElement('button');open.type='button';open.className='secondary';
   open.textContent=plan.opened?
     words('Review or retry tool (no automatic run)','بازبینی یا تلاش دوباره (بدون اجرای خودکار)'):
     words('Open tool for review','بازکردن ابزار برای بازبینی');
   open.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow())return;
    const receiver=required?(receipt)=>{
     if(workflowState!==plan||!retainedWorkflow()||plan.index!==i||
        !plan.opened||receipt?.source!=='studio-connection-response'||
        receipt?.kind!=='read'||receipt?.operation!==required)return;
     plan.readReceipt={operation:required};showWorkflow();
    }:null;
    const localReceiver=local?(receipt)=>{
     if(workflowState!==plan||!retainedWorkflow()||plan.index!==i||
        !plan.opened||(local!=='export'&&receipt?.completed!==true)||
        receipt?.kind!==local||
        receipt.source!==(local==='data'?'studio-local-analysis':
           local==='write'?'studio-document-version':
           local==='export'?'studio-document-export':
           local==='music'?'studio-local-music':
           local==='orchestra'?'studio-local-orchestra':
           local==='tasks'?'studio-local-tasks':'studio-local-tool')||
        (local==='tasks'&&(receipt.artifact!=='task-report'||
          !Number.isInteger(receipt.succeeded)||receipt.succeeded<1||
          receipt.succeeded>12||receipt.failed!==0||receipt.cancelled!==0))||
        (local==='orchestra'&&(receipt.artifact!=='score'||
          !Number.isInteger(receipt.parts)||receipt.parts<1||receipt.parts>12||
          !Number.isInteger(receipt.notes)||receipt.notes<1||receipt.notes>200000||
          !Number.isFinite(receipt.durationSeconds)||
          receipt.durationSeconds<=0||receipt.durationSeconds>3600))||
        (local==='music'&&(receipt.artifact!=='score'||
          !Number.isInteger(receipt.bars)||receipt.bars<8||receipt.bars>256||
          !Number.isFinite(receipt.durationSeconds)||receipt.durationSeconds<=0||
          receipt.durationSeconds>3600))||
        (local==='data'&&(!/^[a-f0-9]{64}$/.test(receipt.sha256||'')||
          !Number.isInteger(receipt.rows)||receipt.rows<0||
          !Number.isInteger(receipt.columns)||receipt.columns<1))||
        (local==='write'&&(receipt.persistence!=='session_only'||
          typeof receipt.versionId!=='string'||!receipt.versionId||
          !Number.isInteger(receipt.length)||receipt.length<1||receipt.length>100000))||
        (local==='export'&&(
          !['download_requested','print_requested'].includes(receipt.status)||
          receipt.content!=='not_transmitted'||
          !['markdown','docx','print'].includes(receipt.format)||
          (receipt.format==='print')!==(receipt.status==='print_requested')||
          !['draft','saved_version'].includes(receipt.editorVersion)||
          !Number.isInteger(receipt.bytes)||
          (receipt.format==='print'?receipt.bytes!==0:
            receipt.bytes<1||receipt.bytes>1000000)))||
        (local==='research'&&Boolean(step.result.query)&&
          receipt.query!==step.result.query))return;
     plan.readReceipt={operation:local,...(local==='data'?{sha256:receipt.sha256}: {}),
       ...(local==='write'?{versionId:receipt.versionId}: {}),
       ...(local==='export'?{format:receipt.format,bytes:receipt.bytes,
         status:receipt.status,editorVersion:receipt.editorVersion}: {})};
     showWorkflow();
    }:null;
    if(openReviewedSurface(step.result,step.line,
       required?{readOperation:required,onReadReceipt:receiver}:{})){
     clearLocalReviewers();
     const armed=!local||(local==='data'?
       window.NexusQualityUI?.armReviewedStep?.(local,localReceiver):
       local==='write'?window.NexusStudioUI?.armDocumentReceipt?.(local,localReceiver):
       local==='export'?window.NexusStudioUI?.armExportReceipt?.(local,localReceiver):
       local==='music'?window.NexusMusicUI?.armReviewedStep?.(local,localReceiver):
       local==='orchestra'?window.NexusOrchestraUI?.armReviewedStep?.(local,localReceiver):
       local==='tasks'?window.NexusTasksUI?.armReviewedStep?.(local,localReceiver):
       window.NexusLabUI?.armReviewedStep?.(local,localReceiver));
     plan.opened=Boolean(armed);plan.readReceipt=null;showWorkflow();
    }
   };
   const done=document.createElement('button');done.type='button';done.className='secondary';
   done.textContent=required?
     words('Confirm reviewed read','تأیید دریافت پاسخ خواندن'):
     local==='write'?words('Confirm new document version','تأیید نسخهٔ جدید سند'):
     local==='export'?words('Confirm file or print request','تأیید درخواست فایل یا چاپ'):local?
     words('Confirm tool result','تأیید نتیجهٔ ابزار'):
     words('I completed this step','این گام را انجام دادم');
   done.disabled=!plan.opened||(Boolean(receiptKey)&&plan.readReceipt?.operation!==receiptKey);
   done.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow()||!plan.opened||
       (receiptKey&&plan.readReceipt?.operation!==receiptKey))return;
    step.outcome=required?'gateway_read':local==='write'?'document_version':
      local==='export'?plan.readReceipt?.status:local?'local_observed':'self_reported';
    clearLocalReviewers();
    plan.index++;plan.opened=false;plan.readReceipt=null;showWorkflow();
   };
   item.append(open,done);
   if(receiptKey){
    const note=document.createElement('p');note.className='help';
    note.textContent=plan.readReceipt?.operation===receiptKey?
      required?words('Approved read response received; source content remains untrusted.',
        'پاسخ خواندن تأییدشده دریافت شد؛ محتوای منبع همچنان غیرقابل‌اعتماد است.'):
       local==='data'?words('Local dataset analyzed; SHA256 '+plan.readReceipt.sha256.slice(0,12)+
         '… identifies source bytes, not correctness. Review before confirming.',
         'داده محلی تحلیل شد؛ SHA256 '+plan.readReceipt.sha256.slice(0,12)+
         '… فقط هویت بایت‌هاست، نه صحت نتیجه. پیش از تأیید بررسی کن.'):
       local==='tasks'?words('All reviewed local JavaScript jobs finished successfully; outputs remain untrusted.',
        'همهٔ کارهای JavaScript محلی موفق شدند؛ خروجی‌ها هنوز باید بررسی شوند.'):
       local==='orchestra'?words('Synthetic orchestra score built; no WAV, vocal mix or file delivery verified.',
         'پارتیتور ارکستر سنتتیک ساخته شد؛ WAV، میکس و دریافت فایل تأیید نشده‌اند.'):
       local==='music'?words('New original score composed locally. WAV, file download and musical quality remain unverified.',
        'پارتیتور تازه در دستگاه ساخته شد؛ WAV، دانلود فایل و کیفیت موسیقی تأیید نشده‌اند.'):
       local==='write'?words('A changed document version was applied in this tab. Save your encrypted archive separately to keep it.',
         'نسخهٔ تغییرکردهٔ سند در این برگه اعمال شد. برای نگهداری، آرشیو رمزگذاری‌شده را جداگانه ذخیره کن.'):
       local==='export'?plan.readReceipt.status==='print_requested'?
        words('Browser print dialog requested. Select Save as PDF; verify the file yourself. No PDF was automatically generated or confirmed.',
         'پنجرهٔ چاپ مرورگر درخواست شد. گزینهٔ ذخیره به PDF را انتخاب و فایل را خودت بررسی کن؛ ذخیرهٔ فایل تأیید نشده است.'):
        words('Browser download requested ('+plan.readReceipt.format+
         ', '+plan.readReceipt.bytes+' bytes, '+plan.readReceipt.editorVersion+
         '). Verify that the file was saved and opens correctly on your device.',
         'درخواست دانلود مرورگر ثبت شد ('+plan.readReceipt.format+
         '، '+plan.readReceipt.bytes+' بایت). ذخیره و بازشدن فایل را روی دستگاه بررسی کن.'):
       words('A consented local tool run returned a result; review it before confirming.',
        'ابزار محلی با تأیید شما اجرا شد و نتیجه داد؛ پیش از تأیید آن را بررسی کن.'):
      required?words('Waiting for an approved read in the separate connection dialog.',
        'در انتظار خواندن تأییدشده در پنجرهٔ اتصال.'):
       words('Run the tool separately with explicit consent. Failed or canceled attempts do not count.',
        'ابزار را جداگانه و با تأیید اجرا کن؛ تلاش ناموفق یا لغوشده محاسبه نمی‌شود.');
    item.append(note);
   }
   const skip=document.createElement('button');skip.type='button';skip.className='secondary';
   skip.textContent=words('Skip this step','ردکردن این گام');
   skip.onclick=()=>{
    if(!retainedWorkflow()){clearWorkflow();return}
    if(!validWorkflow())return;
    step.outcome='skipped';clearLocalReviewers();
    plan.index++;plan.opened=false;plan.readReceipt=null;showWorkflow();
   };
   item.append(skip);
  }
  list.append(item);
 });
 const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';
 cancel.textContent=words('Discard workflow','حذف گردش‌کار');
 cancel.onclick=()=>{clearWorkflow();$('message').focus()};
 workflow.append(title,info,list);
 if(plan.index===plan.steps.length){
  const note=document.createElement('p');note.setAttribute('role','status');
  const verified=plan.steps.filter(s=>s.outcome==='gateway_read').length;
  const localCount=plan.steps.filter(s=>s.outcome==='local_observed').length;
  const writing=plan.steps.filter(s=>s.outcome==='document_version').length;
  const exports=plan.steps.filter(s=>s.outcome==='download_requested').length;
  const prints=plan.steps.filter(s=>s.outcome==='print_requested').length;
  const reported=plan.steps.filter(s=>s.outcome==='self_reported').length;
  const skipped=plan.steps.filter(s=>s.outcome==='skipped').length;
  note.textContent=words(
   'Checklist finished · gateway reads: '+verified+' · local tool runs: '+localCount+
    ' · document versions (session only): '+writing+' · download requests (unverified): '+exports+
    ' · print dialogs (unverified): '+prints+' · self-reported: '+reported+' · skipped: '+skipped+
    '. Results remain untrusted and are not independently audited.',
   'پایان فهرست · خواندن درگاه: '+verified+' · اجرای ابزار محلی: '+localCount+
    ' · نسخهٔ سند (فقط نشست): '+writing+' · درخواست دانلود (تأییدنشده): '+exports+
    ' · چاپ (تأییدنشده): '+prints+' · گزارش کاربر: '+reported+' · ردشده: '+skipped+
    '. نتایج مستقل راستی‌آزمایی نشده‌اند.');
  workflow.append(note);
 }
 workflow.append(cancel);
}
function reviewWorkflow(message){
 closeDirectory();clearOffer();clearWorkflow();
 const parsed=parseWorkflow(message);
 if(parsed.error){workflowError(parsed.error);return}
 workflowState={draft:message,scope:workflowScope(),steps:parsed.steps,index:0,
  opened:false,readReceipt:null,source:'local'};
 showWorkflow();
}

/* Gateway preview requires separate user approval; no tool execution. */
const planTools=new Set(['research','data','write','export','code','music','orchestra','tasks','remind','github','render']);
function planGateway(){
 const raw=$('gateway')?.value.trim()||location.origin;
 const url=new URL(raw);
 if((url.protocol!=='https:'&&!(url.protocol==='http:'&&
     ['127.0.0.1','[::1]'].includes(url.hostname)))||
    url.username||url.password||url.search||url.hash||!['','/'].includes(url.pathname))throw Error('gateway');
 return url.origin;
}
async function planResponse(response){
 if(!response.ok||response.headers.get('content-type')?.split(';')[0].trim().toLowerCase()!=='application/json'||!response.body)
  throw Error('gateway-response');
 const reader=response.body.getReader(),chunks=[];let size=0;
 try{
  while(true){
   const {done,value}=await reader.read();if(done)break;
   size+=value.byteLength;if(size>16000)throw Error('gateway-response');
   chunks.push(value);
  }
  const bytes=new Uint8Array(size);let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength}
  return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
 }finally{await reader.cancel().catch(()=>{})}
}
function checkedPlan(result,draft){
 if(result?.kind!=='review_only'||result?.authority!=='none'||
    result.execution!=='not_started'||result.provider_requests!==0||
    result.tools_executed!==0||!Array.isArray(result.steps)||
    result.steps.length<2||result.steps.length>6)throw Error('untrusted-plan');
 return result.steps.map((item,i)=>{
  if(!item||item.number!==i+1||item.status!=='not_started'||
     item.requires_separate_user_review!==true||!planTools.has(item.tool)||
     item.command!=='/'+item.tool||typeof item.instruction!=='string'||
     !item.instruction.trim()||item.instruction.length>260||
     !draft.includes(item.instruction))throw Error('untrusted-plan');
  const route=routes.find(row=>row[0]===item.tool);
  if(!route)throw Error('untrusted-plan');
  const query=item.tool==='research'?item.instruction.replace(
   /^(?:\/research\b|research\b|search\s+(?:the\s+web\s+)?(?:for\s+)?|پژوهش\b|جست\s*[‌ ]*و\s*[‌ ]*جو(?:\s+کن)?\b)/i,'').trim():'';
  return {line:item.instruction,result:{route,query}};
 });
}
/* Local preview is an offline, non-executing allowlist parser. */
function localNaturalPlan(draft){
 if(typeof draft!=='string'||draft.length>1800||
    /[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]/u.test(draft))
  throw Error('local-plan-invalid');
 let lines=draft.replace(/\r\n?/g,'\n').trim().split('\n').map(s=>s.trim());
 if(['/plan','plan:','برنامه:','برنامه'].includes(lines[0].toLowerCase()))lines.shift();
 if(lines.some(s=>!s))throw Error('local-plan-empty');
 const entries=lines.flatMap(s=>s.split(/\s+(?:and\s+then|then|و\s+سپس|سپس|بعد\s+از\s+آن)\s+/iu));
 if(entries.length<2||entries.length>6)throw Error('local-plan-count');
 const detectors=[
  ['research',/^(?:\/research(?:\s|$)|research(?:\s|$)|search\s+(?:the\s+web\s+)?(?:for\s+)?|پژوهش(?:\s|$)|جست[\s‌]*و[\s‌]*جو(?:\s+کن)?(?:\s|$))/iu],
  ['data',/^(?:\/data(?:\s|$)|analy[sz]e(?:\s|$)|تحلیل\s*(?:داده|فایل|csv)(?:[‌\s]|$))/iu],
  ['write',/^(?:\/write(?:\s|$)|draft(?:\s|$)|write(?:\s|$)|بنویس(?:\s|$)|نوشتن(?:\s|$)|پیش\s*نویس(?:\s|$))/iu],
  ['export',/^(?:\/export(?:$|\s+(?:document|draft|report|file|markdown|docx|word|pdf)\b)|(?:export|download)\s+(?:(?:the|this)\s+)?(?:document|draft|report|file|markdown|docx|word|pdf)\b|خروجی\s*(?:سند|فایل|گزارش)(?:\s|$)|(?:دانلود|دریافت)\s*(?:سند|فایل|گزارش)(?:\s|$))/iu],
  ['code',/^(?:\/code(?:\s|$)|run\s+(?:this\s+)?(?:javascript|js)\b|کدنویسی(?:\s|$)|اجرا\s*ی?\s*کد(?:\s|$))/iu],
  ['music',/^(?:\/music(?:\s|$)|compose(?:\s|$)|آهنگ\s+بساز(?:\s|$)|موسیقی\s+بساز(?:\s|$))/iu],
  ['orchestra',/^(?:\/orchestra(?:\s|$)|orchestra(?:\s|$)|orchestrate(?:\s|$)|arrange\s+(?:an?\s+)?orchestra\b|ارکستر\s+بساز(?:\s|$))/iu],
  ['tasks',/^(?:\/tasks(?:\s|$)|run\s+(?:reviewed\s+)?(?:local\s+)?javascript\s+tasks\b|وظایف\s+محلی(?:\s|$))/iu],
  ['remind',/^(?:\/remind(?:\s|$)|remind\s+me(?:\s|$)|set\s+(?:a\s+)?reminder(?:\s|$)|یادآوری\s+کن(?:\s|$))/iu],
  ['github',/^(?:\/github(?:\s+(?:pulls|prs))?$|(?:review|list|show|check)\s+github\s+(?:pull\s+requests|prs)\b)/iu],
  ['render',/^(?:\/render(?:\s+deploys)?$|(?:check|list|show)\s+render\s+deploy(?:ment)?s\b)/iu]
 ];
 const steps=entries.map((raw,i)=>{
  const instruction=raw.replace(/^(?:[0-9۰-۹]{1,2}[.)]|[-*])\s+/u,'').trim();
  if(!instruction||instruction.length>260||
     /[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]/u.test(instruction)||
     /\bpython\b|پایتون/iu.test(instruction)||
     (/\s+(?:and|&)\s+(?:research|search|analy[sz]e|write|draft|export|download|run|compose|orchestrate|arrange|remind|list|check)\b/iu.test(instruction))||
     (/\s+و\s+(?:پژوهش|تحلیل|بنویس|نوشتن|کدنویسی|خروجی|دانلود|دریافت)(?:\s|$)/u.test(instruction)))
   throw Error('local-plan-compound');
  const found=detectors.filter(([,pattern])=>pattern.test(instruction));
  if(found.length!==1)throw Error('local-plan-unknown');
  const tool=found[0][0];
  if(instruction.startsWith('/')&&!new RegExp('^/'+tool+'(?:\\s|$)','i').test(instruction))
   throw Error('local-plan-command');
  return {number:i+1,tool,command:'/'+tool,instruction,status:'not_started',
   requires_separate_user_review:true};
 });
 return {kind:'review_only',authority:'none',execution:'not_started',
  provider_requests:0,tools_executed:0,steps};
}
function stageAssistantPlan(){
 const state=window.NexusStudioUI.uiStatus(),draft=$('message').value;
 if(!state||state.busy||state.attachmentLoading||state.archived||
    draft.trim().length<8||draft.length>1800)return;
 closeDirectory();clearOffer();clearWorkflow();
 const staged={draft,scope:workflowScope()};previewDraft=staged;
 workflow.hidden=false;
 const title=document.createElement('strong');
 title.textContent=words('Preview an assistant workflow','پیش‌نمایش برنامهٔ دستیار');
 const description=document.createElement('p');
 description.className='help';description.textContent=words(
  'Review the exact text. Preview locally with no network or approve a single request to your configured NEXUS gateway. Neither option runs tools; review each step separately.',
  'متن دقیق را بررسی کن. پیش‌نمایش محلی بدون اینترنت انجام می‌شود؛ یا یک درخواست به درگاه پیکربندی‌شدهٔ نکسوس را تأیید کن. هیچ‌کدام ابزارها را اجرا نمی‌کنند.');
 const exact=document.createElement('pre');exact.dir='auto';exact.textContent=draft.trim();
 const status=document.createElement('p');status.setAttribute('role','status');
 const approve=document.createElement('button');approve.type='button';
 approve.textContent=words('Approve gateway-only preview','تأیید پیش‌نمایش در درگاه');
 const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';
 cancel.textContent=words('Cancel','لغو');cancel.onclick=()=>{clearWorkflow();$('message').focus()};
 approve.onclick=async()=>{
  if(previewDraft!==staged||$('message').value!==draft||workflowScope()!==staged.scope||
     window.NexusStudioUI.uiStatus().busy)return;
  const token=$('gateway-token')?.value.trim()||'';
  let origin;
  try{origin=planGateway();if(token.length<32)throw Error('token')}
  catch{status.textContent=words('Configure the NEXUS gateway and Studio access token in model settings first.',
   'ابتدا درگاه نکسوس و توکن دسترسی استودیو را در تنظیمات مدل وارد کن.');return}
  const controller=new AbortController();previewController=controller;
  approve.disabled=true;
  status.textContent=words('Requesting a gateway-only preview…','در حال دریافت پیش‌نمایش از درگاه…');
  const timeout=setTimeout(()=>controller.abort(),15000);
  try{
   const response=await fetch(origin+'/studio-api/assistant/plan-preview',{
    method:'POST',headers:{'content-type':'application/json','authorization':'Bearer '+token},
    body:JSON.stringify({consent:true,goal:draft.trim()}),cache:'no-store',
    redirect:'error',signal:controller.signal
   });
   const parsed=await planResponse(response);
   if(previewDraft!==staged||$('message').value!==draft||workflowScope()!==staged.scope||
      window.NexusStudioUI.uiStatus().busy||window.NexusStudioUI.uiStatus().archived)return;
   const steps=checkedPlan(parsed,draft);
   workflowState={draft,scope:staged.scope,steps,index:0,opened:false,
    readReceipt:null,source:'gateway'};
   previewDraft=null;previewController=null;showWorkflow();
  }catch{
   if(previewDraft===staged&&!controller.signal.aborted){
    status.textContent=words('Preview unavailable or invalid. Your draft is unchanged; no tools were run.',
     'پیش‌نمایش در دسترس نیست یا معتبر نبود. پیش‌نویس تغییر نکرده و ابزاری اجرا نشده است.');
   }else if(previewDraft===staged){
    status.textContent=words('Preview canceled or timed out. No tools were run.',
     'پیش‌نمایش لغو شد یا زمان آن به پایان رسید. ابزاری اجرا نشده است.');
   }
  }finally{
   clearTimeout(timeout);
   if(previewController===controller)previewController=null;
   if(previewDraft===staged)approve.disabled=false;
  }
 };
 const local=document.createElement('button');local.type='button';
 local.className='secondary';local.id='studio-assistant-local-preview';
 local.textContent=words('Preview locally (no network)','پیش‌نمایش محلی (بدون اینترنت)');
 local.onclick=()=>{
  const state=window.NexusStudioUI.uiStatus();
  if(previewDraft!==staged||!state||state.busy||state.attachmentLoading||
     state.archived||$('message').value!==draft||workflowScope()!==staged.scope)return;
  try{
   const steps=checkedPlan(localNaturalPlan(draft.trim()),draft);
   workflowState={draft,scope:staged.scope,steps,index:0,opened:false,
    readReceipt:null,source:'local-natural'};
   previewDraft=null;previewController?.abort();previewController=null;
   showWorkflow();
  }catch{
   status.textContent=words(
    'Local plan not recognized. Use 2–6 explicit, separately ordered supported actions. No request was sent.',
    'برنامهٔ محلی شناسایی نشد. از ۲ تا ۶ دستور مشخص و جداگانه استفاده کن. هیچ درخواستی ارسال نشد.');
  }
 };
 workflow.append(title,description,exact,approve,local,cancel,status);
}
let offeredDraft=null;
function clearOffer(){
 offeredDraft=null;offer.hidden=true;offer.replaceChildren();
}
/* Tool suggestions require separate review; model replies are inert. */
function explicitToolRequest(message){
 const value=message.trim();
 return value.startsWith('/')||explicitResearch.test(value)||
  /^(?:remind me(?: to)?|set (?:a )?reminder(?: for)?|یادآوری کن)\s+/i.test(value)||
  /^(?:please\s+)?(?:open|launch)\s+/i.test(value)||
  /^(?:لطفاً\s+)?(?:باز\s*کن|برو\s+به)\s+/u.test(value)||
  /^(?:please\s+)?analy[sz]e\s+(?:this\s+|the\s+)?(?:csv|tsv|json|dataset|spreadsheet)\b/i.test(value)||
  /^(?:please\s+)?run\s+(?:this\s+)?javascript\b/i.test(value)||
  /^(?:please\s+)?(?:export|download)\s+/i.test(value)||
  /^(?:لطفاً\s+)?(?:خروجی\s*بگیر|دریافت\s+فایل)/u.test(value);
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
  const current=$('message').value===message;
  clearOffer();
  const state=window.NexusStudioUI.uiStatus();
  if(!current||state.busy||state.archived)return;
  if(!state.threadReady&&!window.NexusStudioUI.startConversation()){
   refresh();return;
  }
  if(select.value==='guide'){$('guide').click();refresh();return}
  refresh();run({routeTools:false});
 });
 offer.append(p,open,proceed,dismiss);
}

let running=false,temporaryModel=false;
function refresh(){
 const state=window.NexusStudioUI.uiStatus();
 if(!state)return;
 if(temporaryModel&&!state.hasChatAttachments){select.value='guide';temporaryModel=false}
 if(offeredDraft!==null&&($('message').value!==offeredDraft||state.archived))clearOffer();
 if(workflowState&&!retainedWorkflow())clearWorkflow();
 if(previewDraft&&($('message').value!==previewDraft.draft||workflowScope()!==previewDraft.scope||
    state.archived||state.busy))clearWorkflow();
 planPreview.textContent=words('Plan steps','برنامه‌ریزی مراحل');
 planPreview.disabled=state.busy||state.attachmentLoading||state.archived||
  $('message').value.trim().length<8||$('message').value.length>1800;
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
 send.setAttribute('aria-label',send.textContent);
 save.textContent=state.vaultUnlocked?words('Save encrypted session','ذخیرهٔ رمزگذاری‌شدهٔ نشست'):words('Set up private archive','تنظیم آرشیو خصوصی');
 const pendingDraft=Boolean($('message').value.trim());
 save.disabled=state.busy||(state.vaultUnlocked&&(state.unsavedForms||pendingDraft));
 config.hidden=!model;
 config.disabled=state.busy;
 config.textContent=words('Model settings','تنظیمات مدل');
 privacy.textContent=model?
  words('Choose a model, review the message and approve sending.',
        'مدل را انتخاب کن، پیام را بازبینی کن و ارسال را تأیید کن.'):
  words('Local guide only — not generative AI. It cannot read attached files.',
        'فقط راهنمای محلی، نه هوش مصنوعی مولد؛ فایل‌های پیوست را نمی‌خواند.');
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
planPreview.addEventListener('click',stageAssistantPlan);
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
select.addEventListener('change',()=>{temporaryModel=false;clearOffer();closeDirectory();refresh()});
document.addEventListener('nexus-studio-private-clear',()=>{clearOffer();closeDirectory();clearWorkflow()});
$('message').addEventListener('input',refresh);
$('message').addEventListener('keydown',event=>{
 if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&!event.isComposing&&
    document.documentElement.classList.contains('studio-focus-mode')){
  event.preventDefault();
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
