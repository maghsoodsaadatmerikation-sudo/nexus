'use strict';
const S=NexusStudio,$=id=>document.getElementById(id),vault=new S.Vault(),undoSlot=new S.UndoSlot(),localePacks=new NexusLocales.Registry();
let data=S.empty(),projectId=null,threadId=null,documentId=null,dirty=false,profileDirty=false,editorDirty=false,revision=0,branchBase=undefined,pending=null,controller=null,busy=false,language='en',modelInfo=null,languageImport=0,sourceViewStamp='';
let chatAttachments=[],attachmentEpoch=0;
const EN={subtitle:'Your conversations, sources and drafts — under your control.',projects:'Projects',projectName:'New project name',createProject:'Create project',deleteProject:'Delete project',history:'Conversation history',search:'Search all conversations',showArchived:'Include archived',newChat:'New conversation',archive:'Private archive',archiveHelp:'Saving is explicit and encrypted in this browser. Keep an encrypted backup and its passphrase separately.',pass:'Passphrase: at least 12 characters',repeat:'Repeat for a new archive or backup',createVault:'Create archive',unlock:'Unlock',lock:'Lock & clear',save:'Save session',backup:'Encrypted backup',restore:'Open encrypted file',erase:'Erase archive',conversation:'Conversation',rename:'Rename',archiveChat:'Archive / reopen',deleteChat:'Delete chat',exportChat:'Export transcript',temporary:'Until you explicitly save, this session exists only in this tab. Closing it can lose your work.',message:'Your message',useMemory:"Include this project's reviewed memory",useSources:'Include relevant project source excerpts',guide:'Use local reflection guide',prepare:'Prepare model request',regenerate:'Prepare another answer',stop:'Stop',modelSettings:'Optional generative model connection',modelHelp:'An operator must configure a model gateway. A ChatGPT subscription is not an API credential. Provider keys stay on the gateway; only its access token is entered here, for this tab.',checkModel:'Check configured model',requestReview:'Exact context to send',consent:'Send this exact context to the configured provider once.',send:'Send approved request',profile:'Project assistant & memory',instructions:'Custom instructions (preferences, not authority)',memories:'Reviewed memory — one item per line, up to 30',applyProfile:'Apply project preferences',memoryHelp:'Nothing is learned automatically. Memory is isolated to this project and sent only when selected. Removing memory does not remove earlier transcript text.',sources:'Local source search',sourceHelp:'Select UTF-8 TXT, Markdown, CSV, TSV or JSON files together, up to 256 KiB each and 12 per project. A batch is added only if every file is valid. Excerpts are local lexical search results, not verified facts. Files are never executed.',sourceQuery:'Words to find in project sources',searchSources:'Search sources',canvas:'Versioned writing canvas',documentTitle:'Document title',newDocument:'New document',saveVersion:'Save new version',exportDocument:'Export Markdown',deleteDocument:'Delete document',loadVersion:'Load version into editor',canvasHelp:'Every saved version remains available, up to 30 per document. Text and code are edited as inert text and never executed.',boundary:'NEXUS assists judgment. It cannot make a human decision or take external actions from a conversation.',unsaved:'Temporary session / unsaved changes',saved:'Applied session saved as encrypted data. Unapplied form text is excluded.',failed:'Operation failed. Check input, capacity, passphrase or archive conflicts. Work has not been silently overwritten.',discard:'Replace or delete this work? Unsaved work and form text can be lost.',plain:'Export unencrypted text? It may include private information.',needApply:'Apply preferences / astrology profiles and save document versions before saving/exporting the session.',branching:'Your next message creates a new branch; the original remains available.',local:'Guide — not a generative model',human:'You',model:'Model draft',edit:'Edit into a new branch',toCanvas:'Copy to canvas',speak:'Read aloud (device voice)',empty:'Create a project, then choose New conversation.',noModel:'No model configured. Local guide remains available.',configured:'Configured model',apply:'Applied locally. Save explicitly to retain this change.'};
Object.assign(EN,{languagePacks:'Interface language packs',languageHelp:'Up to eight complete translation packs can be kept in this tab. They contain labels only, not your projects.',languageTemplate:'Download English label template',gatewayOrigin:'Model gateway origin',gatewayAccess:'Gateway access token (not the provider API key)'});
const FA={subtitle:'گفتگو، منابع و نوشته‌هایت — در اختیار خودت.',projects:'پروژه‌ها',projectName:'نام پروژهٔ جدید',createProject:'ساخت پروژه',deleteProject:'حذف پروژه',history:'تاریخچهٔ گفتگو',search:'جست‌وجو در همهٔ گفتگوها',showArchived:'نمایش بایگانی‌شده‌ها',newChat:'گفتگوی جدید',archive:'آرشیو خصوصی',archiveHelp:'ذخیره‌سازی دستی و رمزگذاری‌شده در همین مرورگر است. پشتیبان رمزگذاری‌شده و گذرواژه را جدا نگه دار.',pass:'گذرواژه: حداقل ۱۲ نویسه',repeat:'تکرار برای آرشیو یا پشتیبان جدید',createVault:'ساخت آرشیو',unlock:'بازکردن قفل',lock:'قفل و پاک‌کردن صفحه',save:'ذخیرهٔ نشست',backup:'پشتیبان رمزگذاری‌شده',restore:'بازکردن فایل رمزگذاری‌شده',erase:'حذف آرشیو',conversation:'گفتگو',rename:'تغییر نام',archiveChat:'بایگانی / بازگردانی',deleteChat:'حذف گفتگو',exportChat:'خروجی گفتگو',temporary:'تا وقتی خودت ذخیره نکنی، این نشست فقط در همین برگه است. بستن آن ممکن است کار را از بین ببرد.',message:'پیام تو',useMemory:'حافظهٔ بازبینی‌شدهٔ همین پروژه را اضافه کن',useSources:'بخش‌های مرتبط منابع پروژه را اضافه کن',guide:'استفاده از راهنمای تأمل محلی',prepare:'آماده‌سازی درخواست مدل',regenerate:'آماده‌سازی پاسخ دیگر',stop:'توقف',modelSettings:'اتصال اختیاری مدل مولد',modelHelp:'مدیر سرور باید درگاه مدل را پیکربندی کند. اشتراک ChatGPT کلید API نیست. کلید مدل روی سرور می‌ماند؛ فقط توکن دسترسی درگاه در همین برگه وارد می‌شود.',checkModel:'بررسی مدل پیکربندی‌شده',requestReview:'متن دقیق ارسالی',consent:'این متن دقیق را یک بار به ارائه‌دهندهٔ پیکربندی‌شده بفرست.',send:'ارسال درخواست تأییدشده',profile:'دستیار و حافظهٔ پروژه',instructions:'دستورهای سفارشی — ترجیح، نه اختیار',memories:'حافظهٔ بازبینی‌شده — هر مورد یک خط، حداکثر ۳۰ مورد',applyProfile:'اعمال ترجیحات پروژه',memoryHelp:'یادگیری خودکار انجام نمی‌شود. حافظه فقط به همین پروژه تعلق دارد و با انتخاب تو ارسال می‌شود. حذف حافظه متن گفتگوهای قبلی را حذف نمی‌کند.',sources:'جست‌وجوی منابع محلی',sourceHelp:'فایل‌های متنی UTF-8 با قالب TXT، Markdown، CSV، TSV و JSON را گروهی انتخاب کن؛ هر فایل تا ۲۵۶ کیبی‌بایت و حداکثر ۱۲ فایل در پروژه. گروه فقط وقتی وارد می‌شود که همهٔ فایل‌ها معتبر باشند. نتیجهٔ جست‌وجوی واژگانی تأیید حقیقت نیست. فایل‌ها اجرا نمی‌شوند.',sourceQuery:'عبارت جست‌وجو در منابع پروژه',searchSources:'جست‌وجوی منابع',canvas:'ویرایشگر نسخه‌دار نوشته',documentTitle:'عنوان سند',newDocument:'سند جدید',saveVersion:'ذخیرهٔ نسخهٔ جدید',exportDocument:'خروجی Markdown',deleteDocument:'حذف سند',loadVersion:'بازکردن نسخه در ویرایشگر',canvasHelp:'هر نسخهٔ ذخیره‌شده تا سقف ۳۰ نسخه حفظ می‌شود. متن و کد اجرا نمی‌شوند.',boundary:'نکسوس به قضاوت کمک می‌کند؛ از داخل گفتگو تصمیم انسانی نمی‌گیرد و اقدام خارجی انجام نمی‌دهد.',unsaved:'نشست موقت / تغییرات ذخیره‌نشده',saved:'نشست اعمال‌شده رمزگذاری و ذخیره شد. متن فرم‌های اعمال‌نشده ذخیره نمی‌شود.',failed:'عملیات ناموفق بود. ورودی، ظرفیت، گذرواژه یا تداخل آرشیو را بررسی کن. کار بدون اطلاع بازنویسی نشده است.',discard:'این کار جایگزین یا حذف شود؟ تغییرات ذخیره‌نشده ممکن است از دست بروند.',plain:'خروجی متن بدون رمزگذاری تهیه شود؟ ممکن است شامل اطلاعات خصوصی باشد.',needApply:'پیش از ذخیره یا خروجی نشست، پروفایل‌ها و ترجیحات را اعمال و نسخهٔ سند را ذخیره کن.',branching:'پیام بعدی شاخهٔ تازه می‌سازد؛ شاخهٔ اصلی باقی می‌ماند.',local:'راهنما — پاسخ مدل مولد نیست',human:'تو',model:'پیش‌نویس مدل',edit:'ویرایش در شاخهٔ تازه',toCanvas:'کپی به ویرایشگر',speak:'خواندن با صدای دستگاه',empty:'یک پروژه بساز، سپس گفتگوی جدید را انتخاب کن.',noModel:'مدل پیکربندی نشده؛ راهنمای محلی در دسترس است.',configured:'مدل پیکربندی‌شده',apply:'محلی اعمال شد. برای نگهداری، خودت ذخیره کن.'};
Object.assign(FA,{languagePacks:'بسته‌های زبان رابط',languageHelp:'تا هشت بستهٔ ترجمهٔ کامل در همین برگه نگه داشته می‌شوند. فقط برچسب‌ها را شامل می‌شوند، نه پروژه‌هایت.',languageTemplate:'دانلود الگوی برچسب‌های انگلیسی',gatewayOrigin:'آدرس درگاه مدل',gatewayAccess:'توکن درگاه — کلید API ارائه‌دهنده نیست'});
Object.assign(EN,{archiveDamaged:'The browser archive is damaged or unsupported. It was not replaced; your open session remains available for encrypted backup.'});
Object.assign(FA,{archiveDamaged:'آرشیو مرورگر آسیب‌دیده یا ناسازگار است؛ جایگزین نشد. نشست باز برای تهیهٔ پشتیبان رمزگذاری‌شده در دسترس است.'});
Object.assign(EN,{chatAttachments:'Attach text files to this message',chatAttachmentsHelp:'Up to four TXT, Markdown, CSV, TSV or JSON files, 128 KiB each. Only short, clearly marked excerpts enter the exact reviewed model request. This is not image/PDF understanding. The original files are not stored in chat or archive; filenames are retained with your turn. Nothing is sent until you explicitly approve the model request.',chatAttachedDocument:'Include latest saved writing document as a temporary excerpt',chatClearAttachments:'Clear attachments',chatNoFiles:'No text files attached',chatAttachmentAdded:'Local files added to next reviewed model request.',chatAttachmentInvalid:'Could not read text files; check size, format and capacity.',chatAttachmentRequiresModel:'Attached file excerpts require a configured model request; the local guide cannot read them.',chatAttachedUsed:'One-turn excerpts supplied (not verified):',chatRegenRequiresFiles:'A response grounded in temporary files cannot be regenerated from the filenames alone. Edit the user message to a new branch and attach the files again.',chatFilesNotSaved:'Files are held only in this tab and their bytes are never saved to the chat archive.'});
Object.assign(FA,{chatAttachments:'پیوست فایل متنی برای همین پیام',chatAttachmentsHelp:'حداکثر چهار فایل TXT، Markdown، CSV، TSV یا JSON، هرکدام تا ۱۲۸ کیبی‌بایت. فقط گزیده‌های کوتاه و مشخص وارد درخواست مدل پس از بازبینی می‌شوند. تصویر و PDF تحلیل نمی‌شوند. محتوای فایل‌ها در تاریخچه یا آرشیو ذخیره نمی‌شود؛ فقط نامشان کنار پیام می‌ماند. تا تأیید صریح شما چیزی فرستاده نمی‌شود.',chatAttachedDocument:'افزودن گزیده‌ای از آخرین نسخهٔ ذخیره‌شدهٔ سند',chatClearAttachments:'پاک‌کردن پیوست‌ها',chatNoFiles:'فایل متنی پیوست نشده است',chatAttachmentAdded:'فایل‌های محلی به درخواست بعدی اضافه شدند؛ قبل از ارسال بازبینی می‌شوند.',chatAttachmentInvalid:'خواندن فایل‌های متنی انجام نشد؛ اندازه، قالب یا ظرفیت را بررسی کن.',chatAttachmentRequiresModel:'گزیدهٔ فایل‌ها فقط در درخواست مدل پیکربندی‌شده استفاده می‌شود؛ راهنمای محلی فایل را نمی‌خواند.',chatAttachedUsed:'گزیده‌های موقت ارائه‌شده (تأییدنشده):',chatRegenRequiresFiles:'پاسخ مبتنی بر فایل موقت را نمی‌توان فقط از نام فایل بازتولید کرد. پیام را در شاخهٔ تازه ویرایش کن و فایل‌ها را دوباره اضافه کن.',chatFilesNotSaved:'محتوای فایل‌ها فقط در همین برگه است و در آرشیو گفتگو ذخیره نمی‌شود.'});
Object.assign(EN,{
 storageCenter:'Storage & unsaved work',storageHelp:'Only applied conversations, projects and document versions enter an explicitly saved encrypted browser archive. Draft text, temporary tool work and Music/Orchestra output remain in this tab. Export audio and keep an encrypted backup separately.',
 storageArchive:'Projects and applied conversations',storageChat:'Unsent chat and attachments',storageWriting:'Writing and preferences',storageMedia:'Music and original vocals',
 storageTools:'Research, code, tasks and data',storageToolsDraft:'Temporary tool inputs or results in this tab',storageToolsNone:'No temporary tool work',
 storageCurrent:'Encrypted browser archive up to date',storageChanged:'Applied changes not yet saved',storageLocked:'No unlocked archive; current work is tab-only',
 storageChatDraft:'Unsent message, attachment or pending request in this tab',storageChatNone:'No unsent chat draft',
 storageWritingDraft:'Unapplied document or preference changes in this tab',storageWritingNone:'No unapplied writing or preference draft',
 storageMediaDraft:'Temporary score, prompt, WAV or original vocal — export separately',storageMediaNone:'No unsaved Music or Orchestra work',
 storageRisk:'Leaving or locking now may discard unsaved work',storageSafe:'No unsaved work detected in this tab',
 storageSummaryRisk:'Unsaved work needs attention',storageSummarySafe:'No unsaved changes detected'
});
Object.assign(FA,{
 storageCenter:'وضعیت ذخیره‌سازی و کارهای ناتمام',storageHelp:'فقط گفتگوها، پروژه‌ها و نسخه‌های اعمال‌شدهٔ سند با ذخیرهٔ صریح وارد آرشیو رمزگذاری‌شدهٔ مرورگر می‌شوند. پیش‌نویس‌ها، کار موقت ابزارها و خروجی موسیقی یا ارکستر در همین برگه می‌مانند. صوت را جداگانه خروجی بگیر و از آرشیو پشتیبان رمزگذاری‌شده نگه دار.',
 storageArchive:'پروژه‌ها و گفتگوهای اعمال‌شده',storageChat:'پیام و پیوست ارسال‌نشده',storageWriting:'نوشته‌ها و ترجیحات',storageMedia:'موسیقی و وکال اصلی',
 storageTools:'پژوهش، کد، کارها و داده',storageToolsDraft:'ورودی یا نتیجهٔ موقت ابزارها در این برگه',storageToolsNone:'کار موقتی در ابزارها وجود ندارد',
 storageCurrent:'آرشیو رمزگذاری‌شدهٔ مرورگر به‌روز است',storageChanged:'تغییرات اعمال‌شده هنوز ذخیره نشده‌اند',storageLocked:'آرشیو باز نیست؛ کار فعلی فقط در این برگه است',
 storageChatDraft:'پیام، پیوست یا درخواست در انتظار فقط در این برگه است',storageChatNone:'پیش‌نویس ارسال‌نشدهٔ گفتگو وجود ندارد',
 storageWritingDraft:'سند یا ترجیحات اعمال‌نشده فقط در این برگه است',storageWritingNone:'پیش‌نویس اعمال‌نشدهٔ نوشته یا ترجیحات وجود ندارد',
 storageMediaDraft:'نت، پرامپت، فایل WAV یا وکال موقت؛ خروجی جداگانه بگیر',storageMediaNone:'کار ذخیره‌نشده در موسیقی یا ارکستر وجود ندارد',
 storageRisk:'خروج یا قفل اکنون ممکن است کار ذخیره‌نشده را از بین ببرد',storageSafe:'کار ذخیره‌نشده‌ای در این برگه شناسایی نشد',
 storageSummaryRisk:'کار ذخیره‌نشده نیاز به توجه دارد',storageSummarySafe:'تغییر ذخیره‌نشده‌ای شناسایی نشد'
});
const forms=()=>profileDirty||editorDirty||window.NexusAstrologyUI?.hasDraft()===true;
const t=k=>(localePacks.get(language)?.messages||(language==='fa'?FA:EN))[k]||EN[k]||k,el=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n},p=()=>data.projects.find(x=>x.id===projectId),chat=()=>p()?.threads.find(x=>x.id===threadId),doc=()=>p()?.documents.find(x=>x.id===documentId);
Object.assign(EN,{studyMode:'Study mode',modelMode:'Provider execution mode (requires a supporting gateway)',modeDefault:'Provider default',modeThinking:'Thinking',modeFast:'Non-thinking',modelBudget:'Maximum generated tokens (1–8192; existing response and time limits still apply)'});
Object.assign(FA,{studyMode:'حالت مطالعه',modelMode:'حالت اجرای مدل — نیازمند درگاه پشتیبان',modeDefault:'پیش‌فرض ارائه‌دهنده',modeThinking:'تفکر',modeFast:'بدون تفکر',modelBudget:'حداکثر توکن تولیدی — ۱ تا ۸۱۹۲؛ محدودیت زمان و حجم پاسخ همچنان برقرار است'});
function status(k){$('status').textContent=t(k)}
function selectedAttachments(){
 const saved=$('attach-document').checked&&doc()?.versions.at(-1)?.text?.trim();
 const version=saved?doc().versions.at(-1):null;
 return [...chatAttachments,...(version?[{id:doc().id,name:'Document: '+doc().title+' ('+version.id.slice(0,8)+')',text:version.text}]:[])];
}
function stageChatContext(label,material){
 if(busy||chat()?.archived||typeof label!=='string'||!label.trim()||
    label.length>160||typeof material!=='string'||!material.trim()||material.length>131072||
    chatAttachments.length>=4||chatAttachments.length+1+($('attach-document').checked?1:0)>S.MAX_CHAT_ATTACHMENTS){
  status('chatAttachmentInvalid');return false;
 }
 if(!chat()&&!startConversation())return false;
 chatAttachments.push({id:S.uid(),name:label,text:material});
 stop();renderChatAttachments();status('chatAttachmentAdded');
 document.dispatchEvent(new CustomEvent('nexus-studio-open-chat'));
 $('conversation-card').scrollIntoView({block:'start',behavior:'smooth'});
 return true;
}
function clearChatAttachments(){attachmentEpoch++;chatAttachments=[];$('chat-file').value='';$('attach-document').checked=false;renderChatAttachments()}
function renderChatAttachments(){
 const tray=$('chat-attachment-tray');tray.replaceChildren();
 if(!chatAttachments.length)tray.append(el('span',t('chatNoFiles')));
 for(const file of chatAttachments){
  const item=el('span',file.name+' · '+file.text.length+' chars ');
  const remove=el('button','×');remove.className='secondary';remove.setAttribute('aria-label',file.name+' · remove');
  remove.disabled=busy;remove.onclick=()=>{if(busy)return;chatAttachments=chatAttachments.filter(x=>x.id!==file.id);stop();renderChatAttachments()};
  item.append(remove);tray.append(item);
 }
 const latest=doc()?.versions.at(-1);
 $('attach-document').disabled=busy||!latest?.text?.trim()||chatAttachments.length>=S.MAX_CHAT_ATTACHMENTS;
 if(!latest?.text?.trim()||chatAttachments.length>=S.MAX_CHAT_ATTACHMENTS)$('attach-document').checked=false;
 $('clear-chat-files').disabled=busy||(!chatAttachments.length&&!$('attach-document').checked);
}
// v1 lifecycle contract: workspace tools are separate from private tab-only audio.
const TOOL_LIFECYCLE=Object.freeze({
 version:'nexus.studio.tool-lifecycle.v1',
 cancel:Object.freeze([['NexusQualityUI','cancel'],['NexusAstrologyUI','cancel'],['NexusLabUI','cancel']]),
 project:Object.freeze([['NexusTasksUI','clear'],['NexusQualityUI','clear'],['NexusAstrologyUI','clear'],['NexusLabUI','clear']]),
 private:Object.freeze([['NexusDevice','unload'],['NexusTasksUI','clear'],['NexusQualityUI','clear'],
  ['NexusAstrologyUI','clear'],['NexusLabUI','clear'],['NexusMusicUI','clear'],['NexusOrchestraUI','clear']])
});
function unsavedLocalMedia(){
 // Preview buffers, unsaved scores and selected original vocals live outside the vault.
 return window.NexusMusicUI?.hasTransientWork?.()===true||
  window.NexusOrchestraUI?.hasTransientWork?.()===true;
}
function hasToolWork(){
 return window.NexusLabUI?.hasTransientWork?.()===true||
  window.NexusTasksUI?.hasTransientWork?.()===true||
  window.NexusQualityUI?.hasTransientWork?.()===true;
}
// Single read-only source for the visible storage center and loss-of-work guards.
// It deliberately exposes flags only, never prompt text, original vocal bytes or keys.
function storageSnapshot(){
 const drafts=Object.freeze({
  chat:hasChatDraft()||Boolean(pending),
  writing:Boolean(editorDirty),
  preferences:Boolean(profileDirty||window.NexusAstrologyUI?.hasDraft?.()===true),
  tools:hasToolWork(),
  music:window.NexusMusicUI?.hasTransientWork?.()===true,
  orchestra:window.NexusOrchestraUI?.hasTransientWork?.()===true
 });
 const risk=dirty||Object.values(drafts).some(Boolean);
 return Object.freeze({
  schema:'nexus.studio.storage-status.v1',
  archive:!vault.unlocked?'tab-only':dirty?'applied-unsaved':'encrypted-current',
  appliedUnsaved:dirty,
  drafts,
  lossRisk:risk
 });
}
function renderStorage(){
 const state=storageSnapshot();
 $('storage-summary').textContent=t(state.lossRisk?'storageSummaryRisk':'storageSummarySafe');
 $('storage-archive-state').textContent=t(state.archive==='tab-only'?'storageLocked':state.archive==='applied-unsaved'?'storageChanged':'storageCurrent');
 $('storage-chat-state').textContent=t(state.drafts.chat?'storageChatDraft':'storageChatNone');
 $('storage-writing-state').textContent=t(state.drafts.writing||state.drafts.preferences?'storageWritingDraft':'storageWritingNone');
 $('storage-tools-state').textContent=t(state.drafts.tools?'storageToolsDraft':'storageToolsNone');
 $('storage-media-state').textContent=t(state.drafts.music||state.drafts.orchestra?'storageMediaDraft':'storageMediaNone');
 $('storage-risk').textContent=t(state.lossRisk?'storageRisk':'storageSafe');
 $('storage-center').dataset.unsaved=String(state.lossRisk);
 return state;
}
function toolLifecycle(phase){
 let complete=true;
 for(const [name,method] of TOOL_LIFECYCLE[phase]){
  const api=window[name];
  if(api==null)continue; // An optional device API may not be loaded.
  try{if(typeof api[method]!=='function')throw Error('unsupported-lifecycle');api[method]()}
  catch{complete=false} // Continue clearing independent tools even if one fails.
 }
 if(phase==='private'){
  $('study-mode').checked=false;
  document.dispatchEvent(new Event('nexus-studio-private-clear'));
 }
 return complete;
}
function clearModelReview(){
 pending=null;$('request-review').hidden=true;$('request-context').textContent='';$('consent').checked=false;
}
function stop({refresh=true}={}){
 languageImport++;toolLifecycle('cancel');revision++;controller?.abort();controller=null;busy=false;
 clearModelReview();try{speechSynthesis.cancel()}catch{}if(refresh)controls();
}
function controls(){
 $('study-mode').disabled=busy||Boolean(chat()?.archived);
 for(const id of ['new-project','delete-project','new-thread','rename-thread','archive-thread','delete-thread','guide','prepare','regenerate','apply-profile','new-document','save-version','delete-document','projects','branch','documents','create-vault','unlock','save','backup','restore','erase','language-file'])$(id).disabled=busy;
 $('chat-file').disabled=busy||!chat()||chat().archived;
 $('clear-chat-files').disabled=busy||(!chatAttachments.length&&!$('attach-document').checked);
 $('attach-document').disabled=busy||!chat()||chat().archived||!doc()?.versions.at(-1)?.text?.trim()||chatAttachments.length>=S.MAX_CHAT_ATTACHMENTS;for(const id of ['delete-project','new-thread','apply-profile','new-document','source-file'])$(id).disabled=busy||!p();for(const id of ['rename-thread','archive-thread','delete-thread','export-thread'])$(id).disabled=busy||!chat();for(const id of ['guide','prepare','regenerate'])$(id).disabled=busy||!chat()||chat().archived;for(const id of ['save-version','export-document','delete-document','load-version'])$(id).disabled=busy||!doc();$('send-model').disabled=busy||!pending||!$('consent').checked;$('undo-removal').disabled=busy||!undoSlot.available;$('stop').disabled=!busy;$('save').disabled=busy||!vault.unlocked;$('erase').disabled=busy||!vault.unlocked;$('retention').textContent=t(storageSnapshot().lossRisk?'unsaved':(vault.unlocked?'saved':'temporary'));renderStorage();window.NexusQualityUI?.refreshStatus();document.dispatchEvent(new Event('nexus-studio-state'))}
function mutate(fn,{undoable=false,afterCommit}={}){
 if(busy)return false;
 const before=data,next=S.copy(data),selection={projectId,threadId,documentId};
 try{
  fn(next);
  const validated=S.state(next);
  if(undoable)undoSlot.record(before,validated,selection);else undoSlot.clear();
  data=validated;
 }catch{status('failed');return false}
 dirty=true;
 afterCommit?.();
 stop({refresh:false});render();status('apply');return true;
}
function projectIn(v){return v.projects.find(x=>x.id===projectId)}
function option(value,label){const o=el('option',label);o.value=value;return o}
function fillProfile(){$('instructions').value=p()?.instructions||'';$('memories').value=p()?.memories.join('\n')||''}
function fillDoc(){$('editor').value=doc()?.versions.at(-1)?.text||'';renderVersions()}
function renderVersions(){const d=doc();$('versions').replaceChildren(...(d?.versions||[]).map((v,i)=>option(v.id,(i+1)+' · '+v.at)));$('versions').value=d?.versions.at(-1)?.id||'';$('version-diff').textContent=''}
let lastChatView;
function render(){
 $('projects').replaceChildren(...data.projects.map(x=>option(x.id,x.title)));$('projects').value=projectId||'';
 $('history').replaceChildren();
 for(const h of S.search(data,$('search').value,$('archived').checked)){
  const b=el('button',h.project_title+' · '+h.title+(h.archived?' ◇':''));
  b.className=h.project===projectId&&h.thread===threadId?'active':'secondary';
  b.disabled=busy;b.onclick=()=>openHistoryThread(h);$('history').append(b);
 }
 const stamp=projectId+':'+(p()?.sources||[]).map(s=>s.id).join(',');if(stamp!==sourceViewStamp){$('source-results').textContent='';sourceViewStamp=stamp}
 const c=chat();$('messages').replaceChildren();if(c){for(const n of S.path(c)){const item=el('article','');item.className='message '+n.role;item.append(el('strong',t(n.origin==='human'?'human':n.origin==='model'?'model':'local')));const body=el('div',n.text);body.className='body';body.dir='auto';item.append(body);if(n.role==='user'){if(n.attached_files?.length){const info=el('small',t('chatAttachedUsed')+' '+n.attached_files.join(', ')+' · '+t('chatFilesNotSaved'));item.append(info)}const edit=el('button',t('edit'));edit.disabled=busy;edit.onclick=()=>{if(!mayReplaceChat())return;clearChatDraft();branchBase=n.parent;$('message').value=n.text;$('branch-notice').textContent=t('branching');stop()};item.append(edit)}else{const canvas=el('button',t('toCanvas'));canvas.disabled=busy;canvas.onclick=()=>{if($('editor').value&&!confirm(t('discard')))return;$('editor').value=n.text;editorDirty=true;stop()};const speak=el('button',t('speak'));speak.onclick=()=>readAloud(n.text);item.append(canvas,speak)}$('messages').append(item)}}else $('messages').append(el('p',t('empty')));
 const chatView=[projectId,threadId,c?.head].join(':');
 if(chatView!==lastChatView){
  lastChatView=chatView;
  requestAnimationFrame(()=>{const messages=$('messages');messages.scrollTop=messages.scrollHeight});
 }
 const parents=new Set(c?.nodes.map(n=>n.parent));const leaves=c?.nodes.filter(n=>!parents.has(n.id))||[];$('branch').replaceChildren(...leaves.map((n,i)=>option(n.id,(i+1)+' · '+n.text.slice(0,60))));$('branch').value=c?.head||'';
 $('source-list').replaceChildren();for(const s of p()?.sources||[]){const row=el('div',s.name+' · '+s.text.length);const b=el('button','×');b.disabled=busy;b.setAttribute('aria-label',language==='fa'?'حذف منبع':'Remove source');b.onclick=()=>mutate(v=>{const q=projectIn(v);q.sources=q.sources.filter(x=>x.id!==s.id)},{undoable:true});row.append(b);$('source-list').append(row)}
 $('documents').replaceChildren(...(p()?.documents||[]).map(d=>option(d.id,d.title)));$('documents').value=documentId||'';window.NexusLabUI?.render();window.NexusAstrologyUI?.render();window.NexusQualityUI?.render();renderChatAttachments();controls();
}
function hasChatDraft(){return Boolean($('message').value||chatAttachments.length||$('attach-document').checked)}
function mayReplaceChat(){return !hasChatDraft()||confirm(t('discard'))}
function mayReplace(){return (!forms()&&!hasChatDraft()&&!hasToolWork())||confirm(t('discard'))}
function clearChatDraft(){
 clearChatAttachments();$('message').value='';branchBase=undefined;$('branch-notice').textContent='';
}
function selectDocument(id){
 documentId=id;editorDirty=false;$('attach-document').checked=false;fillDoc();
}
function resetConversation(id){
 threadId=id;clearChatDraft();
 for(const key of ['use-memory','use-sources','use-astrology','astro-historical','study-mode'])$(key).checked=false;
}
function resetProject(id){
 toolLifecycle('project');
 projectId=id;selectDocument(p()?.documents[0]?.id||null);
 resetConversation(p()?.threads.find(x=>!x.archived)?.id||null);
 profileDirty=false;$('source-results').textContent='';fillProfile();
}
function selectProject(id){resetProject(id);stop({refresh:false})}
function openHistoryThread(entry){
 if(busy)return;
 if(entry.project===projectId){
  if(entry.thread===threadId||!mayReplaceChat())return;
  resetConversation(entry.thread);
  clearModelReview();
 }else{
  if(!mayReplace())return;
  selectProject(entry.project);threadId=entry.thread;
 }
 render();
}
function openConversation(project,thread){
 // Reuse the existing unsaved-work confirmation. Never switch on cancellation.
 if(busy||typeof project!=='string'||typeof thread!=='string')return false;
 const target=data.projects.find(x=>x.id===project);
 if(!target?.threads.some(x=>x.id===thread))return false;
 if(projectId===project&&threadId===thread)return true;
 openHistoryThread({project,thread});
 return projectId===project&&threadId===thread;
}
function applyLanguage(){document.documentElement.lang=language;document.documentElement.dir=localePacks.get(language)?.dir||(language==='fa'?'rtl':'ltr');document.querySelectorAll('[data-t]').forEach(n=>n.textContent=t(n.dataset.t));document.querySelectorAll('[data-placeholder]').forEach(n=>n.placeholder=t(n.dataset.placeholder));render();if(branchBase!==undefined)$('branch-notice').textContent=t('branching')}
function download(text,name,type='text/plain'){const u=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
async function operation(fn,success='apply'){
 if(busy)return;languageImport++;const rev=revision,abort=new AbortController();controller=abort;busy=true;controls();
 try{await fn(rev,abort);if(rev===revision)status(success)}catch(error){if(rev===revision)status(error?.message==='archive-damaged'?'archiveDamaged':'failed')}
 finally{if(controller===abort)controller=null;if(rev===revision)busy=false;controls()}
}
// Create a local first conversation on the user's explicit action, retaining the typed draft.
// No model request, archive write, or network activity happens here.
function startConversation(fresh=false){
 if(busy)return false;
 const current=chat();
 if(current&&!current.archived){
  if(!fresh)return true;
  const before=threadId;
  $('new-thread').click(); // Existing draft-discard confirmation remains authoritative.
  return Boolean(chat()&&threadId!==before);
 }
 const draft=$('message').value,study=$('study-mode').checked;
 // First-chat setup keeps workspace tools already used in this tab.
 if(!p()&&forms()){status('needApply');return false}
 try{
  let ok=false;
  if(!p()){
   const project=S.project(language==='fa'?'گفتگوهای من':'My conversations');
   const thread=S.thread(t('newChat'));
   ok=mutate(v=>{project.threads.push(thread);v.projects.push(project)},{
    afterCommit:()=>{projectId=project.id;resetConversation(thread.id);$('study-mode').checked=study;$('message').value=draft}
   });
  }else{
   const thread=S.thread(t('newChat'));
   ok=mutate(v=>projectIn(v).threads.push(thread),{
    afterCommit:()=>{resetConversation(thread.id);$('study-mode').checked=study;$('message').value=draft}
   });
  }
  if(ok)$('message').dispatchEvent(new Event('input',{bubbles:true}));
  return Boolean(ok&&chat()&&!chat().archived);
 }catch{status('failed');return false}
}
function noForms(){if(forms()||hasChatDraft()){status('needApply');return false}return true}
function candidate(regenerate=false,materials=[]){const c=chat();if(!c||!p()||c.archived)throw Error('select-chat');if(regenerate){const path=S.path(c),last=path.at(-1);if(last?.role!=='assistant')throw Error('no-answer');if(path.at(-2)?.attached_files?.length)throw Error('reattach-required');return {...S.copy(c),head:last.parent}}return S.append(c,'user',$('message').value.trim(),'human',branchBase===undefined?c.head:branchBase,materials.map(x=>x.name))}
function installThread(next){
 return mutate(v=>{const q=projectIn(v);q.threads[q.threads.findIndex(x=>x.id===next.id)]=next},{afterCommit:clearChatDraft});
}
function selectedModelEngine(){return document.getElementById('model-engine')?.value==='device'?'device':'gateway'}
function prepare(regenerate=false){if(profileDirty||($('use-astrology').checked&&window.NexusAstrologyUI?.hasDraft()))return status('needApply');try{const destination=selectedModelEngine();if(destination==='device'){const info=window.NexusDevice?.info();if(!info?.ready)return status('noModel');modelInfo={...info,configured:true,gateway:'device',provider_host:'this device'}}if(!modelInfo?.configured||modelInfo.gateway!==(destination==='device'?'device':gateway()))return status('noModel');stop();const mode=$('model-mode').value,budget=Number($('model-budget').value);if(!Number.isInteger(budget)||budget<1||budget>(destination==='device'?64:8192)||(mode!=='standard'&&(destination==='device'||!modelInfo.modes?.includes(mode))))throw Error('unsupported-mode');const materials=selectedAttachments(),c=candidate(regenerate,materials),ctx=S.context(p(),c,{attachments:materials,memory:$('use-memory').checked,sources:$('use-sources').checked,astrology:$('use-astrology').checked,astroHistorical:$('astro-historical').checked,skyTone:$('sky-tone').checked,study:$('study-mode').checked});if($('study-mode').checked&&!ctx.study)throw Error('study-context-capacity');if(destination==='device'&&JSON.stringify(ctx.messages).length>6000)throw Error('device-context-too-large');pending={destination,thread:c,body:{consent:true,configuration_id:modelInfo.configuration_id,messages:ctx.messages,...(mode!=='standard'||budget!==2048?{mode,max_output_tokens:budget}:{})},revision,projectId,threadId};$('request-context').textContent=JSON.stringify({destination,gateway:destination==='device'?'on-device; no prompt transmission':gateway(),...(destination==='device'?{fixed_policy:modelInfo.policy,max_input_tokens:modelInfo.max_input_tokens}:{}),model:modelInfo.model,provider_host:modelInfo.provider_host,mode,max_output_tokens:budget,response_style:ctx.study?'study':'standard',omitted_earlier_messages:ctx.omitted_messages,optional_context_truncated:ctx.optional_context_truncated,presentation:ctx.presentation,messages:ctx.messages,source_passages_supplied:ctx.citations,source_search_truncated:ctx.retrieval_truncated,temporary_attachment_passages:ctx.attachments_supplied,temporary_attachments_partial:ctx.attachments_truncated},null,2);$('request-review').hidden=false;controls()}catch(error){status(error?.message==='reattach-required'?'chatRegenRequiresFiles':'failed')}}
function gateway(){const value=$('gateway').value.trim();const u=new URL(value||location.origin);if((u.protocol!=='https:'&&!(u.protocol==='http:'&&['127.0.0.1','[::1]'].includes(u.hostname)))||u.username||u.password||u.search||u.hash||!['','/'].includes(u.pathname))throw Error('gateway-url');return u.origin}
async function boundedJson(response,max=128000){if(!response.ok)throw Error('gateway-status-'+response.status);if(!response.body)throw Error('empty-response');const reader=response.body.getReader(),chunks=[];let size=0;try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>max)throw Error('response-capacity');chunks.push(value)}const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length}return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes))}finally{await reader.cancel().catch(()=>{})}}
$('undo-removal').onclick=()=>{if(busy||!undoSlot.available||!mayReplace())return;try{const restored=undoSlot.take(data);data=restored.data;dirty=true;selectProject(restored.selection.projectId);threadId=p()?.threads.some(x=>x.id===restored.selection.threadId)?restored.selection.threadId:threadId;documentId=p()?.documents.some(x=>x.id===restored.selection.documentId)?restored.selection.documentId:documentId;fillDoc();render();status('undoDone')}catch{status('failed')}};
$('new-project').onclick=()=>{
 const name=$('project-title').value.trim();
 if(!name||!mayReplace())return;
 try{
  const q=S.project(name);
  mutate(v=>v.projects.push(q),{afterCommit:()=>{resetProject(q.id);$('project-title').value=''}});
 }catch{status('failed')}
};
$('projects').onchange=()=>{
 const id=$('projects').value;
 if(id===projectId)return;
 if(!mayReplace()){$('projects').value=projectId||'';return}
 selectProject(id);render();
};
$('delete-project').onclick=()=>{
 if(!p()||!confirm(t('discard')))return;
 mutate(v=>v.projects=v.projects.filter(x=>x.id!==projectId),
  {undoable:true,afterCommit:()=>resetProject(data.projects[0]?.id||null)});
};
$('new-thread').onclick=()=>{
 if(!p()||!mayReplaceChat())return;
 const c=S.thread(t('newChat'));
 mutate(v=>projectIn(v).threads.push(c),{afterCommit:()=>resetConversation(c.id)});
};
$('rename-thread').onclick=()=>{if(!chat())return;const name=prompt(t('rename'),chat().title);if(name?.trim())mutate(v=>projectIn(v).threads.find(x=>x.id===threadId).title=name.trim())};
$('archive-thread').onclick=()=>{if(!chat())return;mutate(v=>{const c=projectIn(v).threads.find(x=>x.id===threadId);c.archived=!c.archived})};
$('delete-thread').onclick=()=>{
 if(!chat()||!confirm(t('discard')))return;
 mutate(v=>{const q=projectIn(v);q.threads=q.threads.filter(x=>x.id!==threadId)},
  {undoable:true,afterCommit:()=>resetConversation(null)});
};
$('search').oninput=render;$('archived').onchange=render;
$('branch').onchange=()=>{
 const current=chat();
 if(!current)return;
 const head=$('branch').value;
 if(head===current.head)return;
 if(!mayReplaceChat()){$('branch').value=current.head||'';return}
 if(!mutate(v=>projectIn(v).threads.find(x=>x.id===threadId).head=head,{afterCommit:clearChatDraft}))render();
};
$('guide').onclick=()=>{if(chatAttachments.length||$('attach-document').checked)return status('chatAttachmentRequiresModel');if($('use-astrology').checked&&window.NexusAstrologyUI?.hasDraft())return status('needApply');try{const c=candidate();installThread(S.append(c,'assistant',S.guide(S.path(c).at(-1).text,language==='fa',{skyTone:$('sky-tone').checked,study:$('study-mode').checked})+($('use-astrology').checked?'\n\n'+NexusAstrology.reflection(p().astrology,language==='fa',{historical:$('astro-historical').checked}):''),'guide'))}catch{status('failed')}};
$('prepare').onclick=()=>prepare();$('regenerate').onclick=()=>prepare(true);$('consent').onchange=controls;$('stop').onclick=()=>{stop({refresh:false});render()};
$('chat-file').onchange=async event=>{
 const files=Array.from(event.target.files);event.target.value='';
 if(!files.length||busy||!p()||!chat())return;
 if(files.length>4||chatAttachments.length+files.length+($('attach-document').checked?1:0)>S.MAX_CHAT_ATTACHMENTS||
    files.some(file=>file.size>131072||file.size<1)){status('chatAttachmentInvalid');return}
 const epoch=++attachmentEpoch,pid=projectId,tid=threadId;
 try{
  const incoming=await S.readSources(files);
  if(epoch!==attachmentEpoch||pid!==projectId||tid!==threadId||busy)return;
  chatAttachments.push(...incoming);stop();renderChatAttachments();status('chatAttachmentAdded');
 }catch{if(epoch===attachmentEpoch)status('chatAttachmentInvalid')}
};
$('attach-document').onchange=()=>{stop();renderChatAttachments()};
$('clear-chat-files').onclick=()=>{if(busy)return;clearChatAttachments();stop()};
for(const id of ['message','gateway','gateway-token','use-memory','use-sources','use-astrology','astro-historical','sky-tone','study-mode'])$(id).addEventListener('input',stop);
$('send-model').onclick=async()=>{if(!pending||!$('consent').checked||busy)return;languageImport++;const request=pending,rev=revision;const abort=new AbortController();controller=abort;const timer=setTimeout(()=>abort.abort(),request.destination==='device'?120000:50000);busy=true;controls();try{let out;if(request.destination==='device'){out=await window.NexusDevice.generate(request.body,abort.signal)}else{const response=await fetch(gateway()+'/studio-api/respond',{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',redirect:'error',headers:{'content-type':'application/json','authorization':'Bearer '+$('gateway-token').value},body:JSON.stringify(request.body),signal:abort.signal});out=await boundedJson(response)}if(rev!==revision||request.projectId!==projectId||request.threadId!==threadId)return;if(out.origin!=='model'||out.authority!=='none'||typeof out.text!=='string'||out.model!==modelInfo?.model)throw Error('model-response');busy=false;const installed=installThread(S.append(request.thread,'assistant',(request.destination==='device'?'[On-device draft · SmolLM2-135M · English / limited]\n\n':'')+out.text,'model'));if(installed&&out.truncated)$('status').textContent=language==='fa'?'پاسخ به سقف طول رسیده است.':'The response reached its length limit.'}catch{if(rev===revision)status('failed')}finally{clearTimeout(timer);if(rev===revision){busy=false;clearModelReview();controller=null;controls()}}};
$('check-model').onclick=()=>operation(async(rev,abort)=>{if(selectedModelEngine()==='device'){const info=window.NexusDevice?.info();modelInfo=info?{...info,configured:true,gateway:'device',provider_host:'this device'}:null;$('model-status').textContent=info?info.model+' · on-device · max 64 output tokens':t('noModel');return}const timer=setTimeout(()=>abort.abort(),10000);try{const out=await boundedJson(await fetch(gateway()+'/studio-api/status',{credentials:'omit',cache:'no-store',redirect:'error',signal:abort.signal}),8000);if(rev===revision){if(out.configured&&(typeof out.model!=='string'||typeof out.provider_host!=='string'||! /^[a-f0-9]{64}$/.test(out.configuration_id)))throw Error('configuration');modelInfo={...out,gateway:gateway()};$('model-status').textContent=out.configured?t('configured')+': '+out.model+' · '+out.provider_host:t('noModel')} }finally{clearTimeout(timer)}});
$('apply-profile').onclick=()=>{if(!p())return;const instructions=$('instructions').value,memories=$('memories').value.split('\n').map(x=>x.trim()).filter(Boolean);mutate(v=>Object.assign(projectIn(v),{instructions,memories}),{afterCommit:()=>{profileDirty=false}})};
for(const id of ['instructions','memories'])$(id).addEventListener('input',()=>{profileDirty=true;stop()});$('editor').addEventListener('input',()=>{editorDirty=true;stop()});
$('source-file').onchange=event=>{
 const files=Array.from(event.target.files);event.target.value='';if(!files.length||!p()||busy)return;
 if(p().sources.length+files.length>S.MAX_SOURCES)return status('failed');const pid=projectId;
 return operation(async(rev,abort)=>{
  const sources=await S.readSources(files,{signal:abort.signal});if(rev!==revision||pid!==projectId)return;
  busy=false;if(!mutate(v=>projectIn(v).sources.push(...sources)))throw Error('source-import');
 });
};
$('search-sources').onclick=()=>{if(!p())return;const hits=S.retrieve(p(),$('source-query').value);$('source-results').textContent=(hits.length?hits.map(h=>h.name+':'+h.line+':'+h.offset+'\n'+h.text).join('\n\n'):t('sourceNoMatch'))+(hits.truncated?'\n'+t('sourceLimited'):'')};
$('new-document').onclick=()=>{
 const title=$('document-title').value.trim();
 if(!p()||!title||(editorDirty&&!confirm(t('discard'))))return;
 const d={id:S.uid(),title,versions:[]};
 mutate(v=>projectIn(v).documents.push(d),{afterCommit:()=>{selectDocument(d.id);$('document-title').value=''}});
};
$('documents').onchange=()=>{
 const id=$('documents').value;
 if(id===documentId)return;
 if(editorDirty&&!confirm(t('discard'))){$('documents').value=documentId||'';return}
 selectDocument(id);stop({refresh:false});render();
};
$('save-version').onclick=()=>{
 if(!doc())return;
 const text=$('editor').value,at=new Date().toISOString();
 mutate(v=>projectIn(v).documents.find(d=>d.id===documentId).versions.push({id:S.uid(),text,at}),
  {afterCommit:()=>{editorDirty=false;renderVersions()}});
};
$('delete-document').onclick=()=>{
 if(!doc()||!confirm(t('discard')))return;
 mutate(v=>{const q=projectIn(v);q.documents=q.documents.filter(d=>d.id!==documentId)},
  {undoable:true,afterCommit:()=>selectDocument(null)});
};
$('versions').onchange=()=>{const a=doc()?.versions.find(x=>x.id===$('versions').value)?.text||'',b=doc()?.versions.at(-1)?.text||'';const left=a.split('\n'),right=b.split('\n');$('version-diff').textContent=Array.from({length:Math.max(left.length,right.length)},(_,i)=>left[i]===right[i]?null:(i+1)+':\n− '+(left[i]??'')+'\n+ '+(right[i]??'')).filter(Boolean).slice(0,200).join('\n')};
$('load-version').onclick=()=>{if(forms()&&!confirm(t('discard')))return;const v=doc()?.versions.find(x=>x.id===$('versions').value);if(v){$('editor').value=v.text;editorDirty=true;stop()}};
$('export-document').onclick=()=>{if(doc()&&confirm(t('plain')))download($('editor').value,'nexus-document.md','text/markdown')};
$('export-thread').onclick=()=>{if(chat()&&confirm(t('plain')))download('# '+chat().title+'\n\n'+S.path(chat()).map(n=>'## '+t(n.origin==='human'?'human':n.origin==='model'?'model':'local')+'\n\n'+n.text+(n.attached_files?.length?'\n\n'+t('chatAttachedUsed')+' '+n.attached_files.join(', ')+' — '+t('chatFilesNotSaved'):'')).join('\n\n'),'nexus-conversation.md','text/markdown')};
$('create-vault').onclick=()=>{const pass=$('passphrase').value;if(pass!==$('repeat-passphrase').value)return status('failed');$('passphrase').value='';$('repeat-passphrase').value='';operation((rev,abort)=>vault.create(pass,{signal:abort.signal}))};
$('unlock').onclick=()=>{if((dirty||forms()||hasChatDraft()||hasToolWork())&&!confirm(t('discard')))return;const pass=$('passphrase').value;$('passphrase').value='';$('repeat-passphrase').value='';operation(async(rev,abort)=>{const next=await vault.unlock(pass,{signal:abort.signal});if(rev!==revision)return;undoSlot.clear();data=next;dirty=false;selectProject(data.projects[0]?.id||null);render()})};
$('save').onclick=()=>{if(!noForms())return;const snapshot=S.state(data);operation(async(rev,abort)=>{await vault.save(snapshot,{signal:abort.signal});if(rev===revision)dirty=false},'saved')};
$('lock').onclick=()=>{if(storageSnapshot().lossRisk&&!confirm(t('discard')))return;const clean=toolLifecycle('private');undoSlot.clear();stop({refresh:false});clearChatDraft();modelInfo=null;vault.lock();data=S.empty();projectId=threadId=documentId=null;dirty=profileDirty=editorDirty=false;for(const id of ['passphrase','repeat-passphrase','gateway-token','project-title','document-title','instructions','memories','editor','source-query','search'])$(id).value='';$('model-status').textContent='';$('source-results').textContent='';renderVersions();render();if(!clean)location.reload()};
$('backup').onclick=()=>{if(!noForms())return;const pass=$('passphrase').value;if(pass!==$('repeat-passphrase').value)return status('failed');$('passphrase').value='';$('repeat-passphrase').value='';operation(async(rev,abort)=>{const raw=await vault.export(data,pass,{signal:abort.signal});if(rev===revision)download(raw,'nexus-studio.encrypted.json','application/json')})};
$('restore').onclick=()=>$('restore-file').click();$('restore-file').onchange=event=>{const f=event.target.files[0];event.target.value='';if(!f||f.size>6*1024*1024||!confirm(t('discard')))return;const pass=$('passphrase').value;$('passphrase').value='';$('repeat-passphrase').value='';operation(async(rev,abort)=>{const raw=await f.text();if(rev!==revision||abort.signal.aborted)return;const opened=await S.decrypt(raw,pass,{signal:abort.signal});if(rev!==revision)return;undoSlot.clear();data=opened.data;dirty=true;selectProject(data.projects[0]?.id||null);render()})};
$('erase').onclick=()=>{if(confirm(t('discard')))operation(async(rev,abort)=>{
  window.NexusDevice?.unload();await vault.erase({signal:abort.signal});
  if(rev!==revision){if(!vault.unlocked&&data.projects.length)dirty=true;return}
  const clean=toolLifecycle('private');undoSlot.clear();modelInfo=null;for(const id of ['gateway-token','source-query','search','project-title','document-title'])$(id).value='';data=S.empty();selectProject(null);dirty=false;render();if(!clean)location.reload();
})};
function readAloud(text){try{speechSynthesis.cancel();const voices=speechSynthesis.getVoices().filter(v=>v.localService&&v.lang.startsWith(language));if(!voices.length)return status('failed');const u=new SpeechSynthesisUtterance(text.slice(0,6000));u.voice=voices[0];speechSynthesis.speak(u)}catch{status('failed')}}
$('language-template').onclick=()=>download(JSON.stringify({schema:'nexus.studio.locale.v1',code:'en',dir:'ltr',messages:EN},null,2),'nexus-studio-english-labels.json','application/json');
$('language-file').onchange=async event=>{
 const f=event.target.files[0],task=++languageImport,rev=revision;event.target.value='';
 if(!f||busy)return;if(f.size>NexusLocales.MAX_BYTES)return status('failed');
 const current=()=>task===languageImport&&rev===revision&&!busy;
 try{
  const raw=await f.text();if(!current())return;const pack=localePacks.install(raw,EN,{optionalKeys:['storageTools','storageToolsDraft','storageToolsNone','studyMode']});
  if(!$('language').querySelector('option[value="'+pack.code+'"]'))$('language').append(option(pack.code,pack.code));
  language=pack.code;$('language').value=pack.code;stop();applyLanguage();
 }catch{if(current())status('failed')}
};
$('language').onchange=()=>{stop();language=$('language').value;applyLanguage()};
window.addEventListener('beforeunload',e=>{if(storageSnapshot().lossRisk){e.preventDefault();e.returnValue=''}});
// Reflect DOM-only drafts as they are typed and async media completions after they settle.
document.addEventListener('input',renderStorage);
document.addEventListener('change',renderStorage);
document.addEventListener('nexus-studio-media-state',renderStorage);
window.NexusStudioUI=Object.freeze({schema:'nexus.studio.ui.v1',startConversation,openConversation,selection:()=>({projectId,threadId}),lifecycle_version:TOOL_LIFECYCLE.version,storageStatus:storageSnapshot,snapshot:()=>S.copy(data),stageChatContext,uiStatus:()=>({vaultUnlocked:vault.unlocked,dirty,busy,unsavedForms:forms()||chatAttachments.length>0||$('attach-document').checked,unsavedLocalMedia:unsavedLocalMedia(),lossRisk:storageSnapshot().lossRisk,threadReady:!!chat(),archived:!!chat()?.archived,pendingReview:!!pending,hasChatAttachments:chatAttachments.length>0||$('attach-document').checked}),resetModel:()=>{stop();modelInfo=null;$('model-status').textContent='';render()}});$('language').value=language;applyLanguage();

for(const id of ['model-mode','model-budget'])$(id).addEventListener('input',stop);
