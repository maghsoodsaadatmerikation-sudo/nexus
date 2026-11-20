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
function intent(value){
 const message=value.trim();
 const slash=/^\/([a-z-]+)(?:\s|$)/i.exec(message);
 if(slash){
  const command=slash[1].toLowerCase();
  const route=routes.find(x=>x[0]===command||(x[5]||'').split(' ').includes(command));
  return route?{route,query:message.slice(slash[0].length).trim()}:null;
 }
 const search=/^(?:search\s+(?:the\s+web\s+)?for|جست[\s\u200c]*و[\s\u200c]*جو\s+کن)\s+(.+)$/is.exec(message);
 if(search)return {route:routes.find(row=>row[0]==='research'),query:search[1]};
 const reminder=/^(?:remind me (?:to )?|set (?:a )?reminder(?: for)?\s+|یادآوری کن\s+)(.+)$/i.exec(message);
 if(reminder)return {route:routes.find(row=>row[0]==='remind'),query:reminder[1]};
 if(window.NexusStudio.asksForChoice(message))return null;
 const s=message.slice(0,340).toLocaleLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/\u200c/g,' ');
 if(!/(بساز|ساخت|تولید|طراحی|بنویس|تنظیم|compose|create|make|generate|write|analy[sz]e|search|find|draw|run|open|list|show|check|اجرا|بررسی|تحلیل|نمایش|نشان\s*بده|وضعیت|جست\s*و\s*جو)/i.test(s))return null;
 const kind=/(github|گیت\s*هاب|گیتهاب|pull requests?|درخواست(?:‌|\s)*ادغام)/i.test(s)?'github':
  /(render|رندر|deployment|deploy)/i.test(s)?'render':
  /(ارکستر|گروه کر|وکال|orchestra|choir|vocal)/i.test(s)?'orchestra':
  /(آهنگ|اهنگ|موسیقی|ملودی|music|song|melody)/i.test(s)?'music':
  /(چارت تولد|طالع|astrology|transit)/i.test(s)?'astrology':
  /(نمودار|chart|graph)/i.test(s)?'chart':
  /(کدنویسی|برنامه نویسی|code|javascript|python)/i.test(s)?'code':
  /(csv|json|داده|فایل|dataset|spreadsheet)/i.test(s)?'data':
  /(پژوهش|منبع علمی|research|wikipedia|crossref)/i.test(s)?'research':
  /(داستان|متن بنویس|essay|story|draft)/i.test(s)?'write':
  /(وظایف|task|workflow)/i.test(s)?'tasks':null;
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
let offeredDraft=null;
function clearOffer(){
 offeredDraft=null;offer.hidden=true;offer.replaceChildren();
}
function suggestion(message){
 if(!window.NexusStudioFocus?.isFocused()||(select.value==='model'&&!message.trimStart().startsWith('/')))return null;
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
  const input=field?$(field):null;
  if(input&&!input.value&&result.query){
   const limit=field==='research-query'?250:input.maxLength;
   input.value=result.query.slice(0,limit>0?limit:480);
   input.dispatchEvent(new Event('input',{bubbles:true}));
  }
  if(panel==='studio-connections'){
   // Opening a chosen review surface never fetches or grants permission.
   const request=connectionRequest(result,message);
   if(!window.NexusStudioConnections?.openFor?.(request)){
    const entry=$('studio-connections-open');
    if(entry&&!entry.disabled)entry.click();
   }
  }else window.NexusStudioFocus?.openPanel(panel);
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

let running=false,temporaryModel=false;
function refresh(){
 const state=window.NexusStudioUI.uiStatus();
 if(!state)return;
 if(temporaryModel&&!state.hasChatAttachments){select.value='guide';temporaryModel=false}
 if(offeredDraft!==null&&($('message').value!==offeredDraft||state.archived))clearOffer();
 const model=select.value==='model',ready=!state.busy&&(!state.threadReady||!state.archived);
 $('message').placeholder=words('Ask NEXUS anything…','هرچه می‌خواهی از نکسوس بپرس…');
 heading.textContent=model?words('AI model options','گزینه‌های مدل هوش مصنوعی'):words('Local guide · change mode','راهنمای محلی · تغییر حالت');
 box.setAttribute('aria-label',words('Conversation actions','گزینه‌های گفتگو'));
 selectLabel.setAttribute('aria-label',words('Choose how to respond','روش پاسخ را انتخاب کن'));
 for(const b of suggestions.children)b.textContent=words(b.dataset.en,b.dataset.fa);
 for(const opt of select.options)opt.textContent=words(opt.dataset.en,opt.dataset.fa);
 const privateChat=/^\/temporary$/i.test($('message').value.trim());
 const tool=suggestion($('message').value);
 send.textContent=privateChat?words('Start temporary chat','شروع گفتگوی موقت'):tool?words('Review '+tool.route[2],'بازبینی '+tool.route[3]):model?words('Review before sending','بازبینی پیش از ارسال'):words('Use local guide','استفاده از راهنمای محلی');
 send.disabled=!ready||!$('message').value.trim();
 send.setAttribute('aria-label',send.textContent);
 save.textContent=state.vaultUnlocked?words('Save encrypted session','ذخیرهٔ رمزگذاری‌شدهٔ نشست'):words('Set up private archive','تنظیم آرشیو خصوصی');
 // Never bypass the existing noForms() gate, including unread chat drafts.
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
 // The send button can briefly lag a newly created first conversation.
 // Authoritative UI state and the draft, not a stale disabled flag, gate work.
 const state=window.NexusStudioUI.uiStatus();
 if(running||!state||state.busy||(state.threadReady&&state.archived)||
    !$('message').value.trim())return;
 const message=$('message').value;
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
select.addEventListener('change',()=>{temporaryModel=false;clearOffer();closeDirectory();refresh()});
document.addEventListener('nexus-studio-private-clear',()=>{clearOffer();closeDirectory()});
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
