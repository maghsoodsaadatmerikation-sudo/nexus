'use strict';
const S=NexusStudio,$=id=>document.getElementById(id),vault=new S.Vault(),undoSlot=new S.UndoSlot(),localePacks=new NexusLocales.Registry();
let data=S.empty(),projectId=null,threadId=null,documentId=null,dirty=false,profileDirty=false,editorDirty=false,revision=0,branchBase=undefined,pending=null,controller=null,busy=false,language='en',modelInfo=null,modelChoices=[],selectedModelSlot='primary',modelReadiness=null,languageImport=0,sourceViewStamp='';
let chatAttachments=[],attachmentEpoch=0,attachmentLoading=false,trainingReview=null;
const EN={subtitle:'An AI assistant built to support human judgment.',projects:'Projects',projectName:'New project name',createProject:'Create project',deleteProject:'Delete project',history:'Conversation history',search:'Search all conversations',showArchived:'Include archived',newChat:'New conversation',archive:'Private archive',archiveHelp:'Saving is explicit and encrypted in this browser. Keep an encrypted backup and its passphrase separately.',pass:'Passphrase: at least 12 characters',repeat:'Repeat for a new archive or backup',createVault:'Create archive',unlock:'Unlock',lock:'Lock & clear',save:'Save session',backup:'Encrypted backup',restore:'Open encrypted file',erase:'Erase archive',conversation:'Conversation',rename:'Rename',archiveChat:'Archive / reopen',deleteChat:'Delete chat',exportChat:'Export transcript',temporary:'Until you explicitly save, this session exists only in this tab. Closing it can lose your work.',message:'Your message',useMemory:"Include this project's reviewed memory",useSources:'Include relevant project source excerpts',guide:'Use local reflection guide',prepare:'Prepare model request',regenerate:'Prepare another answer',stop:'Stop',modelSettings:'Optional generative model connection',modelHelp:'An operator must configure a model gateway. A ChatGPT subscription is not an API credential. Provider keys stay on the gateway; only its access token is entered here, for this tab.',checkModel:'Check configured model',requestReview:'Exact context to send',consent:'Send this exact context to the configured provider once.',send:'Send approved request',profile:'Project assistant & memory',instructions:'Custom instructions (preferences, not authority)',memories:'Reviewed memory — one item per line, up to 30',applyProfile:'Apply project preferences',memoryHelp:'Nothing is learned automatically. Memory is isolated to this project and sent only when selected. Removing memory does not remove earlier transcript text.',sources:'Local source search',sourceHelp:'Select UTF-8 TXT, Markdown, CSV, TSV or JSON files together, up to 256 KiB each and 12 per project. A batch is added only if every file is valid. Excerpts are local lexical search results, not verified facts. Files are never executed.',sourceQuery:'Words to find in project sources',searchSources:'Search sources',canvas:'Versioned writing canvas',documentTitle:'Document title',newDocument:'New document',saveVersion:'Save new version',exportDocument:'Export Markdown',deleteDocument:'Delete document',loadVersion:'Load version into editor',canvasHelp:'Every saved version remains available, up to 30 per document. Text and code are edited as inert text and never executed.',boundary:'NEXUS assists judgment. It cannot make a human decision or take external actions from a conversation.',unsaved:'Temporary session / unsaved changes',saved:'Applied session saved as encrypted data. Unapplied form text is excluded.',failed:'Operation failed. Check input, capacity, passphrase or archive conflicts. Work has not been silently overwritten.',discard:'Replace or delete this work? Unsaved work and form text can be lost.',plain:'Export unencrypted text? It may include private information.',needApply:'Apply preferences / astrology profiles and save document versions before saving/exporting the session.',branching:'Your next message creates a new branch; the original remains available.',local:'Guide — not a generative model',human:'You',model:'Model draft',edit:'Edit into a new branch',toCanvas:'Copy to canvas',speak:'Read aloud (device voice)',empty:'Create a project, then choose New conversation.',noModel:'No model configured. Local guide remains available.',configured:'Configured model',apply:'Applied locally. Save explicitly to retain this change.'};
Object.assign(EN,{languagePacks:'Interface language packs',languageHelp:'Up to eight complete translation packs can be kept in this tab. They contain labels only, not your projects.',languageTemplate:'Download English label template',gatewayOrigin:'Model gateway origin',gatewayAccess:'Gateway access token (not the provider API key)'});
const FA={subtitle:'دستیار هوش مصنوعی برای کمک به قضاوت انسانی.',projects:'پروژه‌ها',projectName:'نام پروژهٔ جدید',createProject:'ساخت پروژه',deleteProject:'حذف پروژه',history:'تاریخچهٔ گفتگو',search:'جست‌وجو در همهٔ گفتگوها',showArchived:'نمایش بایگانی‌شده‌ها',newChat:'گفتگوی جدید',archive:'آرشیو خصوصی',archiveHelp:'ذخیره‌سازی دستی و رمزگذاری‌شده در همین مرورگر است. پشتیبان رمزگذاری‌شده و گذرواژه را جدا نگه دار.',pass:'گذرواژه: حداقل ۱۲ نویسه',repeat:'تکرار برای آرشیو یا پشتیبان جدید',createVault:'ساخت آرشیو',unlock:'بازکردن قفل',lock:'قفل و پاک‌کردن صفحه',save:'ذخیرهٔ نشست',backup:'پشتیبان رمزگذاری‌شده',restore:'بازکردن فایل رمزگذاری‌شده',erase:'حذف آرشیو',conversation:'گفتگو',rename:'تغییر نام',archiveChat:'بایگانی / بازگردانی',deleteChat:'حذف گفتگو',exportChat:'خروجی گفتگو',temporary:'تا وقتی خودت ذخیره نکنی، این نشست فقط در همین برگه است. بستن آن ممکن است کار را از بین ببرد.',message:'پیام تو',useMemory:'حافظهٔ بازبینی‌شدهٔ همین پروژه را اضافه کن',useSources:'بخش‌های مرتبط منابع پروژه را اضافه کن',guide:'استفاده از راهنمای تأمل محلی',prepare:'آماده‌سازی درخواست مدل',regenerate:'آماده‌سازی پاسخ دیگر',stop:'توقف',modelSettings:'اتصال اختیاری مدل مولد',modelHelp:'مدیر سرور باید درگاه مدل را پیکربندی کند. اشتراک ChatGPT کلید API نیست. کلید مدل روی سرور می‌ماند؛ فقط توکن دسترسی درگاه در همین برگه وارد می‌شود.',checkModel:'بررسی مدل پیکربندی‌شده',requestReview:'متن دقیق ارسالی',consent:'این متن دقیق را یک بار به ارائه‌دهندهٔ پیکربندی‌شده بفرست.',send:'ارسال درخواست تأییدشده',profile:'دستیار و حافظهٔ پروژه',instructions:'دستورهای سفارشی — ترجیح، نه اختیار',memories:'حافظهٔ بازبینی‌شده — هر مورد یک خط، حداکثر ۳۰ مورد',applyProfile:'اعمال ترجیحات پروژه',memoryHelp:'یادگیری خودکار انجام نمی‌شود. حافظه فقط به همین پروژه تعلق دارد و با انتخاب تو ارسال می‌شود. حذف حافظه متن گفتگوهای قبلی را حذف نمی‌کند.',sources:'جست‌وجوی منابع محلی',sourceHelp:'فایل‌های متنی UTF-8 با قالب TXT، Markdown، CSV، TSV و JSON را گروهی انتخاب کن؛ هر فایل تا ۲۵۶ کیبی‌بایت و حداکثر ۱۲ فایل در پروژه. گروه فقط وقتی وارد می‌شود که همهٔ فایل‌ها معتبر باشند. نتیجهٔ جست‌وجوی واژگانی تأیید حقیقت نیست. فایل‌ها اجرا نمی‌شوند.',sourceQuery:'عبارت جست‌وجو در منابع پروژه',searchSources:'جست‌وجوی منابع',canvas:'ویرایشگر نسخه‌دار نوشته',documentTitle:'عنوان سند',newDocument:'سند جدید',saveVersion:'ذخیرهٔ نسخهٔ جدید',exportDocument:'خروجی Markdown',deleteDocument:'حذف سند',loadVersion:'بازکردن نسخه در ویرایشگر',canvasHelp:'هر نسخهٔ ذخیره‌شده تا سقف ۳۰ نسخه حفظ می‌شود. متن و کد اجرا نمی‌شوند.',boundary:'نکسوس به قضاوت کمک می‌کند؛ از داخل گفتگو تصمیم انسانی نمی‌گیرد و اقدام خارجی انجام نمی‌دهد.',unsaved:'نشست موقت / تغییرات ذخیره‌نشده',saved:'نشست اعمال‌شده رمزگذاری و ذخیره شد. متن فرم‌های اعمال‌نشده ذخیره نمی‌شود.',failed:'عملیات ناموفق بود. ورودی، ظرفیت، گذرواژه یا تداخل آرشیو را بررسی کن. کار بدون اطلاع بازنویسی نشده است.',discard:'این کار جایگزین یا حذف شود؟ تغییرات ذخیره‌نشده ممکن است از دست بروند.',plain:'خروجی متن بدون رمزگذاری تهیه شود؟ ممکن است شامل اطلاعات خصوصی باشد.',needApply:'پیش از ذخیره یا خروجی نشست، پروفایل‌ها و ترجیحات را اعمال و نسخهٔ سند را ذخیره کن.',branching:'پیام بعدی شاخهٔ تازه می‌سازد؛ شاخهٔ اصلی باقی می‌ماند.',local:'راهنما — پاسخ مدل مولد نیست',human:'تو',model:'پیش‌نویس مدل',edit:'ویرایش در شاخهٔ تازه',toCanvas:'کپی به ویرایشگر',speak:'خواندن با صدای دستگاه',empty:'یک پروژه بساز، سپس گفتگوی جدید را انتخاب کن.',noModel:'مدل پیکربندی نشده؛ راهنمای محلی در دسترس است.',configured:'مدل پیکربندی‌شده',apply:'محلی اعمال شد. برای نگهداری، خودت ذخیره کن.'};
Object.assign(FA,{languagePacks:'بسته‌های زبان رابط',languageHelp:'تا هشت بستهٔ ترجمهٔ کامل در همین برگه نگه داشته می‌شوند. فقط برچسب‌ها را شامل می‌شوند، نه پروژه‌هایت.',languageTemplate:'دانلود الگوی برچسب‌های انگلیسی',gatewayOrigin:'آدرس درگاه مدل',gatewayAccess:'توکن درگاه — کلید API ارائه‌دهنده نیست'});
Object.assign(EN,{archiveDamaged:'The browser archive is damaged or unsupported. It was not replaced; your open session remains available for encrypted backup.'});
Object.assign(FA,{archiveDamaged:'آرشیو مرورگر آسیب‌دیده یا ناسازگار است؛ جایگزین نشد. نشست باز برای تهیهٔ پشتیبان رمزگذاری‌شده در دسترس است.'});
Object.assign(EN,{routeMismatch:'The gateway reply did not match the model or configuration you approved. Nothing was added to the conversation. Check the gateway and review the request again.'});
Object.assign(FA,{routeMismatch:'پاسخ درگاه با مدل یا تنظیماتی که تأیید کرده‌اید مطابقت نداشت. چیزی به گفتگو اضافه نشد. اتصال درگاه را بررسی کنید و درخواست را دوباره بازبینی کنید.'});
Object.assign(EN,{
 gatewayUnauthorized:'Gateway access denied (401/403). Check its token and permissions. Nothing was saved.',
 gatewayConfigurationChanged:'Gateway model changed (409). Check settings and review a fresh request. No answer was saved.',
 gatewayInvalidRequest:'Gateway rejected the request (415/422). Review the model, mode and context. No answer was saved.',
 gatewayBusy:'Gateway busy or local request budget exhausted (429). Check readiness; no automatic retry.',
 gatewayUnavailable:'Gateway or provider unavailable (503). Check its status; the attempt may have reached the provider.',
 gatewayUpstreamFailure:'Gateway/provider error (408/500/502/504). No answer saved; check usage before manually retrying.',
 gatewayRejected:'Gateway rejected the request. No answer was saved; check its status.',
 gatewayNetwork:'Gateway connection failed. Check URL, network and CORS. The attempt may have reached the server.',
 gatewayTimeout:'Model request timed out. No answer saved; check usage before manually retrying.',
 gatewayMalformedReply:'Incomplete or invalid model reply was not saved. Check gateway health before retrying.'
});
Object.assign(FA,{
 gatewayUnauthorized:'دسترسی به درگاه رد شد (401/403). توکن و مجوز را بررسی کنید. چیزی ذخیره نشد.',
 gatewayConfigurationChanged:'مدل درگاه تغییر کرد (409). تنظیمات را بررسی و درخواست تازه‌ای را تأیید کنید. پاسخی ذخیره نشد.',
 gatewayInvalidRequest:'درگاه درخواست را نپذیرفت (415/422). مدل، حالت و زمینه را بررسی کنید. پاسخی ذخیره نشد.',
 gatewayBusy:'درگاه مشغول یا سهمیهٔ محلی تمام است (429). وضعیت را بررسی کنید؛ تکرار خودکار انجام نشد.',
 gatewayUnavailable:'درگاه یا ارائه‌دهنده در دسترس نیست (503). وضعیت را بررسی کنید؛ شاید درخواست به ارائه‌دهنده رسیده باشد.',
 gatewayUpstreamFailure:'خطای درگاه یا مدل (408/500/502/504). پاسخی ذخیره نشد؛ پیش از تکرار دستی، مصرف را بررسی کنید.',
 gatewayRejected:'درگاه درخواست را نپذیرفت. پاسخی ذخیره نشد؛ وضعیت درگاه را بررسی کنید.',
 gatewayNetwork:'اتصال درگاه برقرار نشد. نشانی، شبکه و CORS را بررسی کنید؛ شاید درخواست به سرور رسیده باشد.',
 gatewayTimeout:'مهلت پاسخ مدل تمام شد. پاسخی ذخیره نشد؛ پیش از تلاش مجدد، مصرف را بررسی کنید.',
 gatewayMalformedReply:'پاسخ مدل ناقص یا نامعتبر بود و ذخیره نشد. پیش از تکرار، وضعیت درگاه را بررسی کنید.'
});
Object.assign(EN,{chatAttachments:'Attach files to this message',chatAttachmentsHelp:'Up to four files. Text formats are limited to 128 KiB per file. Word (.docx) and PowerPoint (.pptx) files are limited to 2 MiB. Up to 20 slides are supported. Only text is extracted. Only short, clearly marked excerpts enter the exact reviewed model request. This is not image/PDF understanding. The original files are not stored in chat or archive; filenames are retained with your turn. Nothing is sent until you explicitly approve the model request.',chatAttachedDocument:'Include latest saved writing document as a temporary excerpt',chatClearAttachments:'Clear attachments',chatNoFiles:'No text files attached',chatAttachmentAdded:'Local files added to next reviewed model request.',chatAttachmentInvalid:'Could not read text files; check size, format and capacity.',chatAttachmentRequiresModel:'Attached file excerpts require a configured model request; the local guide cannot read them.',chatAttachedUsed:'One-turn excerpts supplied (not verified):',chatRegenRequiresFiles:'A response grounded in temporary files cannot be regenerated from the filenames alone. Edit the user message to a new branch and attach the files again.',chatFilesNotSaved:'Files are held only in this tab and their bytes are never saved to the chat archive.'});
Object.assign(FA,{chatAttachments:'پیوست فایل برای همین پیام',chatAttachmentsHelp:'حداکثر چهار فایل. سقف هر فایل متنی ۱۲۸ کیبی‌بایت است. فایل‌های Word و PowerPoint تا ۲ مِبی‌بایت و ارائه‌ها تا ۲۰ اسلاید پذیرفته می‌شوند. فقط متن استخراج می‌شود. فقط گزیده‌های کوتاه و مشخص وارد درخواست مدل پس از بازبینی می‌شوند. تصویر و PDF تحلیل نمی‌شوند. محتوای فایل‌ها در تاریخچه یا آرشیو ذخیره نمی‌شود؛ فقط نامشان کنار پیام می‌ماند. تا تأیید صریح شما چیزی فرستاده نمی‌شود.',chatAttachedDocument:'افزودن گزیده‌ای از آخرین نسخهٔ ذخیره‌شدهٔ سند',chatClearAttachments:'پاک‌کردن پیوست‌ها',chatNoFiles:'فایل متنی پیوست نشده است',chatAttachmentAdded:'فایل‌های محلی به درخواست بعدی اضافه شدند؛ قبل از ارسال بازبینی می‌شوند.',chatAttachmentInvalid:'خواندن فایل‌های متنی انجام نشد؛ اندازه، قالب یا ظرفیت را بررسی کن.',chatAttachmentRequiresModel:'گزیدهٔ فایل‌ها فقط در درخواست مدل پیکربندی‌شده استفاده می‌شود؛ راهنمای محلی فایل را نمی‌خواند.',chatAttachedUsed:'گزیده‌های موقت ارائه‌شده (تأییدنشده):',chatRegenRequiresFiles:'پاسخ مبتنی بر فایل موقت را نمی‌توان فقط از نام فایل بازتولید کرد. پیام را در شاخهٔ تازه ویرایش کن و فایل‌ها را دوباره اضافه کن.',chatFilesNotSaved:'محتوای فایل‌ها فقط در همین برگه است و در آرشیو گفتگو ذخیره نمی‌شود.'});
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
Object.assign(EN,{
 reminderTitle:'Reminders',reminderHelp:'Download an .ics file and import it into your calendar. The receiving calendar interprets the local time and manages alerts.',
 reminderName:'Reminder',reminderStart:'Local date and time',reminderRepeat:'Repeat',reminderOnce:'Once',reminderDaily:'Daily',reminderWeekly:'Weekly',
 reminderAlert:'Alert',reminderAtStart:'At the event time',reminderFive:'5 minutes before',reminderFifteen:'15 minutes before',reminderHour:'1 hour before',
 reminderExport:'Download calendar file',reminderDownloaded:'Calendar file ready. Import it into your calendar and check its alert.',reminderInvalid:'Enter a reminder and a valid local date and time.'
});
Object.assign(FA,{
 reminderTitle:'یادآورها',reminderHelp:'فایل .ics را بگیر و در تقویمت وارد کن. تقویم مقصد ساعت محلی را تفسیر می‌کند و اعلان‌ها را مدیریت می‌کند.',
 reminderName:'یادآور',reminderStart:'تاریخ و ساعت محلی',reminderRepeat:'تکرار',reminderOnce:'یک‌بار',reminderDaily:'روزانه',reminderWeekly:'هفتگی',
 reminderAlert:'اعلان',reminderAtStart:'در زمان رویداد',reminderFive:'۵ دقیقه قبل',reminderFifteen:'۱۵ دقیقه قبل',reminderHour:'یک ساعت قبل',
 reminderExport:'دریافت فایل تقویم',reminderDownloaded:'فایل آماده است. آن را در تقویمت وارد و اعلان را بررسی کن.',reminderInvalid:'عنوان یادآور و تاریخ و ساعت معتبر وارد کن.'
});
function status(k){$('status').textContent=t(k)}
Object.assign(EN,{streamPreview:'Answer in progress',streamFailed:'The answer did not finish. Your draft is still available.'});
Object.assign(FA,{streamPreview:'پاسخ در حال تولید',streamFailed:'پاسخ کامل نشد. پیش‌نویس هنوز در دسترس است.'});
Object.assign(EN,{
 chatCopy:'Copy answer',chatCopyDone:'Answer copied to the clipboard.',
 chatCopyFailed:'Clipboard access is unavailable. Select the answer text to copy it.',
 chatExportThread:'Download active branch as HTML',chatExport:'Download answer',chatExportTitle:'NEXUS answer',
 chatExportWord:'Download Word (.docx)',chatExportWordDone:'Word download requested.',chatExportWordFailed:'Word export needs text within the supported size.',
 chatExportConfirm:'Download this answer as an unencrypted HTML file?',chatExportDone:'HTML download requested.',
 chatPasteName:'Pasted text',chatPasteAdded:'Long paste attached locally. Add a question and review the excerpts before sending.',
 chatPasteLimit:'The draft was kept. Paste less text or remove an attachment to make room.'
});
Object.assign(FA,{
 chatCopy:'کپی پاسخ',chatCopyDone:'پاسخ در کلیپ‌بورد کپی شد.',
 chatCopyFailed:'دسترسی به کلیپ‌بورد ممکن نیست. متن پاسخ را انتخاب و کپی کن.',
 chatExportThread:'دریافت شاخهٔ فعال به‌صورت HTML',chatExport:'دریافت فایل پاسخ',chatExportTitle:'پاسخ نکسوس',
 chatExportWord:'دریافت Word (.docx)',chatExportWordDone:'درخواست دانلود Word ثبت شد.',chatExportWordFailed:'برای دریافت Word، متن باید در محدودهٔ حجم مجاز باشد.',
 chatExportConfirm:'همین پاسخ را به‌صورت فایل HTML بدون رمزگذاری دانلود می‌کنی؟',chatExportDone:'درخواست دانلود HTML ثبت شد.',
 chatPasteName:'متن چسبانده‌شده',chatPasteAdded:'متن بلند به‌صورت محلی پیوست شد. پرسشت را بنویس و گزیده‌ها را پیش از ارسال بازبینی کن.',
 chatPasteLimit:'پیش‌نویس حفظ شد. متن کوتاه‌تری بچسبان یا یکی از پیوست‌ها را بردار.'
});
const PRIVACY_EN={
 privacySettings:'Privacy settings',historyDays:'Keep chat history',historyManual:'Until I delete it',
 historyOff:'Off — this tab only',history30:'30 days',history90:'90 days',history365:'365 days',
 historyHelp:'Save the encrypted session to apply. Expired chats are removed on save or unlock, based on their last message. Previously downloaded copies are separate.',
 historyConfirm:'Turn history off? This keeps chats in this tab only and removes them from the browser archive at the next save.',
 temporaryChats:'Temporary conversations are only in this tab',
 trainingOptIn:'Allow me to prepare a conversation for AI training',
 trainingHelp:'Off by default and resets when you lock. NEXUS training is not connected. You can review one branch and download a local copy. Files and audio are excluded. Online providers apply their own policies.',
 trainingReview:'Review conversation for training',trainingDownload:'Download reviewed text',trainingConfirm:'Download the reviewed text as an unencrypted file for training?'
};
Object.assign(EN,PRIVACY_EN);
Object.assign(FA,{
 privacySettings:'تنظیمات حریم خصوصی',historyDays:'نگهداری تاریخچهٔ گفتگو',historyManual:'تا زمانی که خودم پاک کنم',
 historyOff:'خاموش — فقط در همین برگه',history30:'۳۰ روز',history90:'۹۰ روز',history365:'۳۶۵ روز',
 historyHelp:'برای اعمال، نشست رمزگذاری‌شده را ذخیره کن. گفتگوهای منقضی بر اساس زمان آخرین پیام، هنگام ذخیره یا بازکردن آرشیو پاک می‌شوند. نسخه‌هایی که قبلاً دانلود کرده‌ای جدا هستند.',
 historyConfirm:'تاریخچه خاموش شود؟ گفتگوها فقط در همین برگه می‌مانند و با ذخیرهٔ بعدی از آرشیو مرورگر حذف می‌شوند.',
 temporaryChats:'گفتگوهای موقت فقط در همین برگه‌اند',
 trainingOptIn:'اجازهٔ آماده‌سازی گفتگو برای آموزش هوش مصنوعی',
 trainingHelp:'پیش‌فرض خاموش است و هنگام قفل‌کردن دوباره خاموش می‌شود. سامانهٔ آموزش نکسوس متصل نیست. می‌توانی یک شاخه از گفتگو را بازبینی کنی و نسخهٔ محلی آن را دانلود کنی. فایل و صدا در خروجی نیستند. ارائه‌دهندگان آنلاین سیاست خودشان را دارند.',
 trainingReview:'بازبینی گفتگو برای آموزش',trainingDownload:'دانلود متن بازبینی‌شده',trainingConfirm:'متن بازبینی‌شده برای آموزش به‌صورت فایل بدون رمزگذاری دانلود شود؟'
});
const CHAT_CONTEXT_EN={
 temporaryAttachments:'Remove staged attachments before starting a temporary chat.',
 chatFilesReading:'Reading attachments on this device…',
 canvasChat:'Use this draft in chat',canvasDraft:'Canvas draft',
 autoSpeak:'Read completed replies aloud with a local voice',
 useRelatedChats:'Review related excerpts from other chats in this project',
 isolatedChat:'Temporary chat',isolatedChatNote:'This chat stays in this tab. Project context is off. Online model requests still require approval.'
};
Object.assign(EN,CHAT_CONTEXT_EN);
Object.assign(FA,{
 temporaryAttachments:'برای شروع گفتگوی موقت، پیوست‌های آماده‌شده را بردار.',
 chatFilesReading:'در حال خواندن پیوست‌ها روی همین دستگاه…',
 canvasChat:'استفاده از این پیش‌نویس در گفتگو',canvasDraft:'پیش‌نویس بوم',
 autoSpeak:'خواندن خودکار پاسخ‌های کامل با صدای محلی',
 useRelatedChats:'بازبینی بخش‌های مرتبط از گفتگوهای دیگر همین پروژه',
 isolatedChat:'گفتگوی موقت',isolatedChatNote:'این گفتگو فقط در همین برگه می‌ماند. زمینهٔ پروژه خاموش است. ارسال به مدل آنلاین همچنان به تأیید تو نیاز دارد.'
});
function selectedAttachments(){
 const saved=!chat()?.isolated&&$('attach-document').checked&&doc()?.versions.at(-1)?.text?.trim();
 const version=saved?doc().versions.at(-1):null;
 return [...chatAttachments,...(version?[{id:doc().id,name:'Document: '+doc().title+' ('+version.id.slice(0,8)+')',text:version.text}]:[])];
}
function stageChatContext(label,material){
 if(typeof label!=='string'||!label.trim()||label.length>160||
    typeof material!=='string'||!material.trim()||material.length>131072){
  status('chatAttachmentInvalid');return false;
 }
 return stageChatAttachments([{id:S.uid(),name:label,text:material}]);
}
function canStageAttachments(count){
 return !busy&&!chat()?.archived&&chatAttachments.length+count<=4&&
  chatAttachments.length+count+Number($('attach-document').checked)<=S.MAX_CHAT_ATTACHMENTS;
}
function stageChatAttachments(incoming){
 if(attachmentLoading||!canStageAttachments(incoming.length)){
  status('chatAttachmentInvalid');return false;
 }
 if(!chat()&&!startConversation())return false;
 chatAttachments.push(...incoming);
 stop();renderChatAttachments();status('chatAttachmentAdded');
 document.dispatchEvent(new Event('nexus-studio-open-chat'));
 return true;
}
function clearChatAttachments(){
 attachmentEpoch++;attachmentLoading=false;chatAttachments=[];$('chat-file').value='';
 $('attach-document').checked=false;renderChatAttachments();
}
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
 $('attach-document').disabled=busy||Boolean(chat()?.isolated)||!latest?.text?.trim()||chatAttachments.length>=S.MAX_CHAT_ATTACHMENTS;
 if(!latest?.text?.trim()||chatAttachments.length>=S.MAX_CHAT_ATTACHMENTS)$('attach-document').checked=false;
 $('clear-chat-files').disabled=busy||(!attachmentLoading&&!chatAttachments.length&&!$('attach-document').checked);
}
// v1 lifecycle contract: workspace tools are separate from private tab-only audio.
const TOOL_LIFECYCLE=Object.freeze({
 version:'nexus.studio.tool-lifecycle.v1',
 cancel:Object.freeze([['NexusStudioVision','cancel'],['NexusQualityUI','cancel'],['NexusAstrologyUI','cancel'],['NexusLabUI','cancel']]),
 project:Object.freeze([['NexusStudioVision','clear'],['NexusCalendar','clear'],['NexusTasksUI','clear'],['NexusQualityUI','clear'],['NexusAstrologyUI','clear'],['NexusLabUI','clear']]),
 private:Object.freeze([['NexusStudioVision','clear'],['NexusDevice','unload'],['NexusCalendar','clear'],['NexusTasksUI','clear'],['NexusQualityUI','clear'],
  ['NexusAstrologyUI','clear'],['NexusLabUI','clear'],['NexusMusicUI','clear'],['NexusOrchestraUI','clear']])
});
function unsavedLocalMedia(){
 // Preview buffers, unsaved scores and selected original vocals live outside the vault.
 return window.NexusStudioVision?.hasTransientWork?.()===true||
   window.NexusMusicUI?.hasTransientWork?.()===true||
  window.NexusOrchestraUI?.hasTransientWork?.()===true;
}
function hasToolWork(){
 return window.NexusStudioVision?.hasTransientWork?.()===true||
   window.NexusCalendar?.hasTransientWork?.()===true||
  window.NexusLabUI?.hasTransientWork?.()===true||
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
 const temporary=data.projects.some(p=>p.threads.some(c=>c.nodes.length&&(c.temporary||data.history_days===0)));
 const risk=dirty||temporary||Object.values(drafts).some(Boolean);
 return Object.freeze({
  schema:'nexus.studio.storage-status.v1',
  archive:!vault.unlocked?'tab-only':dirty?'applied-unsaved':'encrypted-current',
  appliedUnsaved:dirty,temporaryChats:temporary,
  drafts,
  lossRisk:risk
 });
}
function renderStorage(){
 const state=storageSnapshot();
 $('storage-summary').textContent=t(state.lossRisk?'storageSummaryRisk':'storageSummarySafe');
 $('storage-archive-state').textContent=t(state.archive==='tab-only'?'storageLocked':state.archive==='applied-unsaved'?'storageChanged':'storageCurrent');
 $('storage-chat-state').textContent=t(state.drafts.chat?'storageChatDraft':state.temporaryChats?'temporaryChats':'storageChatNone');
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
  $('auto-speak').checked=false;
  $('training-opt-in').checked=false;clearTrainingReview();
  document.dispatchEvent(new Event('nexus-studio-private-clear'));
 }
 return complete;
}
/* Local, non-exhaustive credential warning; matched values are not shown. */
const privacyPanel=el('div',''),privacyDetails=el('p',''),privacyLabel=el('label',''),
 privacyAck=el('input',''),privacyLabelText=el('span','');
let privacyKinds=[];
privacyPanel.className='notice';privacyPanel.id='studio-credential-preflight';privacyPanel.hidden=true;
privacyDetails.id='studio-credential-warning';privacyDetails.setAttribute('role','alert');
privacyAck.id='studio-credential-override';privacyAck.type='checkbox';
privacyLabel.className='inline';privacyLabel.append(privacyAck,privacyLabelText);
privacyPanel.append(privacyDetails,privacyLabel);
$('request-context').before(privacyPanel);
function refreshPrivacyWarning(){
 privacyPanel.hidden=!privacyKinds.length;
 if(privacyPanel.hidden)return;
 privacyDetails.textContent=(language==='fa'
  ?'احتمال وجود اطلاعات ورود محرمانه در متن ارسالی: '
  :'Possible credential patterns in this request: ')+privacyKinds.join(', ')+
  (language==='fa'?'. این بررسی ناقص است. متن کامل درخواست را بازبینی و در صورت نیاز اطلاعات محرمانه را حذف کن.':
   '. This scan is incomplete. Review the full request below; remove secrets before sending.');
 privacyLabelText.textContent=language==='fa'
  ?'با وجود این هشدار، ارسال همین متن به سرویس خارجی را جداگانه تأیید می‌کنم.'
  :'I separately approve sending this exact request to the external provider despite the warning.';
}
function showPrivacy(audit){
 privacyKinds=[...audit.categories];privacyAck.checked=false;refreshPrivacyWarning();
}
privacyAck.addEventListener('change',controls);
function clearModelReview(){
 pending=null;$('request-review').hidden=true;$('request-context').textContent='';$('consent').checked=false;privacyKinds=[];privacyAck.checked=false;refreshPrivacyWarning();
 $('model-stream-preview').hidden=true;$('model-stream-text').textContent='';
}
function stop({refresh=true}={}){
 languageImport++;toolLifecycle('cancel');revision++;controller?.abort();controller=null;busy=false;
 clearModelReview();window.NexusSpeechPlayback?.stop();if(refresh)controls();
}
function clearTrainingReview(){
 trainingReview=null;
 $('training-preview').textContent='';$('training-preview').hidden=true;$('training-download').hidden=true;
}
function controls(){
 $('history-days').value=String(data.history_days??'');
 $('history-days').disabled=busy;
 $('training-opt-in').disabled=busy;
 $('training-review').disabled=busy||!$('training-opt-in').checked||!chat()?.head||chat()?.isolated;
 if(trainingReview&&(trainingReview.thread!==threadId||trainingReview.head!==chat()?.head||!$('training-opt-in').checked))clearTrainingReview();
 $('training-download').disabled=busy;

 $('study-mode').disabled=busy||Boolean(chat()?.archived);
 $('canvas-chat').disabled=busy||!p()||Boolean(chat()?.archived||chat()?.isolated)||!$('editor').value.trim();
 for(const id of ['new-project','delete-project','new-thread','rename-thread','archive-thread','delete-thread','guide','prepare','apply-profile','new-document','save-version','delete-document','projects','branch','documents','create-vault','unlock','save','backup','restore','erase','language-file'])$(id).disabled=busy;
 $('chat-file').disabled=busy||attachmentLoading||Boolean(chat()?.archived);
 $('clear-chat-files').disabled=busy||(!attachmentLoading&&!chatAttachments.length&&!$('attach-document').checked);
 const thread=chat();
 $('isolated-chat-note').hidden=!thread?.isolated;
 $('new-temporary-chat').disabled=busy;
 for(const id of ['use-memory','use-sources','astro-historical'])$(id).disabled=busy||Boolean(thread?.isolated);
 $('use-related-chats').disabled=busy||!thread||thread.temporary||thread.isolated;
 $('export-thread-html').disabled=busy||!thread?.head;
 const regenerate=$('regenerate');
 regenerate.hidden=thread?.nodes.find(node=>node.id===thread.head)?.role!=='assistant';
 regenerate.disabled=regenerate.hidden||busy||thread.archived||branchBase!==undefined||hasChatDraft();
 $('attach-document').disabled=busy||!chat()||chat().archived||chat().isolated||!doc()?.versions.at(-1)?.text?.trim()||chatAttachments.length>=S.MAX_CHAT_ATTACHMENTS;for(const id of ['delete-project','new-thread','apply-profile','new-document','source-file'])$(id).disabled=busy||!p();for(const id of ['rename-thread','archive-thread','delete-thread','export-thread'])$(id).disabled=busy||!chat();for(const id of ['guide','prepare'])$(id).disabled=busy||attachmentLoading||!chat()||chat().archived;for(const id of ['save-version','export-document','export-document-word','delete-document','load-version'])$(id).disabled=busy||!doc();$('send-model').disabled=busy||attachmentLoading||!pending||!$('consent').checked||(!privacyPanel.hidden&&!privacyAck.checked);$('undo-removal').disabled=busy||!undoSlot.available;$('stop').disabled=!busy;$('save').disabled=busy||!vault.unlocked;$('erase').disabled=busy||!vault.unlocked;$('retention').textContent=t(storageSnapshot().lossRisk?'unsaved':(vault.unlocked?'saved':'temporary'));renderStorage();window.NexusQualityUI?.refreshStatus();document.dispatchEvent(new Event('nexus-studio-state'))}
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
function messageOriginLabel(n){
 const ordinary=t(n.origin==='human'?'human':n.origin==='model'?'model':'local');
 // Only receipts accepted from the reviewed gateway route are attributed.
 return n.origin==='model'&&n.model_receipt?
  ordinary+' · '+n.model_receipt.model+' ('+n.model_receipt.model_slot+')':ordinary;
}
function renderMessage(n){
 const item=el('article','');
 item.className='message '+n.role;
 const heading=el('strong',messageOriginLabel(n));
 if(n.model_receipt)heading.title=language==='fa'?
  'مسیر ثبت‌شدهٔ درگاه؛ هویت ارائه‌دهندهٔ بیرونی مستقل تأیید نشده است.':
  'Gateway-selected route; external provider identity is not independently verified.';
 item.append(heading);
 const body=el('div',n.origin==='model'?'':n.text);
 body.className='body';body.dir='auto';
 if(n.origin==='model')NexusReplyFormat.render(body,n.text);
 item.append(body);
 if(n.role==='user'){
  if(n.attached_files?.length)item.append(el('small',t('chatAttachedUsed')+' '+n.attached_files.join(', ')+' · '+t('chatFilesNotSaved')));
  const edit=el('button',t('edit'));
  edit.disabled=busy;
  edit.onclick=()=>{if(!mayReplaceChat())return;clearChatDraft();branchBase=n.parent;$('message').value=n.text;$('branch-notice').textContent=t('branching');stop()};
  item.append(edit);
 }else{
  const copy=el('button',t('chatCopy'));
  copy.type='button';copy.className='secondary';copy.dataset.chatCopy='';
  copy.onclick=async()=>{
   let result='chatCopyDone';
   try{await navigator.clipboard.writeText(n.text)}catch{result='chatCopyFailed'}
   if(copy.isConnected)status(result);
  };
  const exportAnswer=el('button',t('chatExport'));
  exportAnswer.type='button';exportAnswer.className='secondary';exportAnswer.dataset.chatExport='';
  exportAnswer.onclick=()=>{
   if(!confirm(t('chatExportConfirm')))return;
   const html=NexusReplyFormat.exportHtml(document,n.text,{title:t('chatExportTitle'),format:n.origin==='model'});
   download(html,'nexus-answer.html','text/html;charset=utf-8');
   status('chatExportDone');
  };
  const exportWord=el('button',t('chatExportWord'));
  exportWord.type='button';exportWord.className='secondary';exportWord.dataset.chatWord='';
  exportWord.onclick=()=>downloadWord(t('chatExportTitle'),n.text,'nexus-answer.docx');
  const canvas=el('button',t('toCanvas'));
  canvas.disabled=busy;canvas.dataset.chatCanvas='';
  canvas.onclick=()=>{
   if(busy||($('editor').value&&$('editor').value!==n.text&&!confirm(t('discard'))))return;
   $('editor').value=n.text;editorDirty=true;stop();
   document.dispatchEvent(new Event('nexus-studio-open-canvas'));
  };
  const speak=el('button',t('speak'));
  speak.type='button';speak.dataset.chatSpeak='';
  speak.onclick=()=>window.NexusSpeechPlayback?.start(body.innerText||n.text,speak);
  item.append(copy,exportAnswer,exportWord,canvas,speak);
 }
 return item;
}
function render(){
 $('projects').replaceChildren(...data.projects.map(x=>option(x.id,x.title)));$('projects').value=projectId||'';
 $('history').replaceChildren();
 for(const h of S.search(data,$('search').value,$('archived').checked)){
  const b=el('button',h.project_title+' · '+h.title+(h.archived?' ◇':''));
  b.className=h.project===projectId&&h.thread===threadId?'active':'secondary';
  b.disabled=busy;b.onclick=()=>openHistoryThread(h);$('history').append(b);
 }
 const stamp=projectId+':'+(p()?.sources||[]).map(s=>s.id).join(',');if(stamp!==sourceViewStamp){$('source-results').textContent='';sourceViewStamp=stamp}
 const c=chat();$('messages').replaceChildren(...(c?S.path(c).map(renderMessage):[el('p',t('empty'))]));
 const chatView=[projectId,threadId,c?.head].join(':');
 if(chatView!==lastChatView){
  lastChatView=chatView;
  requestAnimationFrame(()=>{const messages=$('messages');messages.scrollTop=messages.scrollHeight});
 }
 const parents=new Set(c?.nodes.map(n=>n.parent));const leaves=c?.nodes.filter(n=>!parents.has(n.id))||[];$('branch').replaceChildren(...leaves.map((n,i)=>option(n.id,(i+1)+' · '+n.text.slice(0,60))));$('branch').value=c?.head||'';
 $('source-list').replaceChildren();for(const s of p()?.sources||[]){const row=el('div',s.name+' · '+s.text.length);const b=el('button','×');b.disabled=busy;b.setAttribute('aria-label',language==='fa'?'حذف منبع':'Remove source');b.onclick=()=>mutate(v=>{const q=projectIn(v);q.sources=q.sources.filter(x=>x.id!==s.id)},{undoable:true});row.append(b);$('source-list').append(row)}
 $('documents').replaceChildren(...(p()?.documents||[]).map(d=>option(d.id,d.title)));$('documents').value=documentId||'';window.NexusLabUI?.render();window.NexusAstrologyUI?.render();window.NexusQualityUI?.render();renderChatAttachments();controls();
}
function hasChatDraft(){return Boolean($('message').value||attachmentLoading||chatAttachments.length||$('attach-document').checked||window.NexusStudioVision?.hasTransientWork?.()===true)}
function mayReplaceChat(){return !hasChatDraft()||confirm(t('discard'))}
function mayReplace(){return (!forms()&&!hasChatDraft()&&!hasToolWork())||confirm(t('discard'))}
function clearChatDraft(){
 clearChatAttachments();$('message').value='';branchBase=undefined;$('branch-notice').textContent='';
}
function selectDocument(id){
 documentId=id;editorDirty=false;$('attach-document').checked=false;fillDoc();
}
function resetConversation(id){
 clearTrainingReview();
 window.NexusSpeechPlayback?.stop();
 // Private image input belongs to the thread where it was selected.
 // Only first-chat setup may preserve a selected image when there is no prior thread.
 if(threadId!==null&&threadId!==id)window.NexusStudioVision?.clear?.();
 threadId=id;clearChatDraft();
 for(const key of ['use-memory','use-sources','use-related-chats','use-astrology','astro-historical','study-mode','auto-speak'])$(key).checked=false;
}
function resetProject(id){
 toolLifecycle('project');
 projectId=id;selectDocument(p()?.documents[0]?.id||null);
 resetConversation(p()?.threads.find(x=>!x.archived&&!x.isolated)?.id||null);
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
function applyLanguage(){document.documentElement.lang=language;document.documentElement.dir=localePacks.get(language)?.dir||(language==='fa'?'rtl':'ltr');document.querySelectorAll('[data-t]').forEach(n=>n.textContent=t(n.dataset.t));document.querySelectorAll('[data-placeholder]').forEach(n=>n.placeholder=t(n.dataset.placeholder));refreshPrivacyWarning();render();if(branchBase!==undefined)$('branch-notice').textContent=t('branching')}
function download(text,name,type='text/plain'){const u=URL.createObjectURL(text instanceof Blob?text:new Blob([text],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
function downloadWord(title,text,filename){
 if(!text.trim())return status('chatExportWordFailed');
 if(!confirm(t('plain')))return;
 try{
  download(NexusOfficeZip.writeDocx(title,text),filename);
  status('chatExportWordDone');
 }catch{status('chatExportWordFailed')}
}

async function operation(fn,success='apply'){
 if(busy)return;languageImport++;const rev=revision,abort=new AbortController();controller=abort;busy=true;controls();
 try{await fn(rev,abort);if(rev===revision)status(success)}catch(error){if(rev===revision)status(error?.message==='archive-damaged'?'archiveDamaged':'failed')}
 finally{if(controller===abort)controller=null;if(rev===revision)busy=false;controls()}
}
// Create a local first conversation on the user's explicit action, retaining the typed draft.
// No model request, archive write, or network activity happens here.
function newThread(isolated=false){
 const thread=S.thread(t(isolated?'isolatedChat':'newChat'));
 if(data.history_days===0||isolated)thread.temporary=true;
 if(isolated)thread.isolated=true;
 return thread;
}
function startConversation(fresh=false,{isolated=false}={}){
 if(busy)return false;
 if(isolated&&(attachmentLoading||chatAttachments.length||$('attach-document').checked||window.NexusStudioVision?.hasTransientWork?.()===true)){status('temporaryAttachments');return false;}
 const current=chat();
 if(current&&!current.archived&&!isolated){
  if(!fresh)return true;
  const before=threadId;
  $('new-thread').click(); // Existing draft-discard confirmation remains authoritative.
  return Boolean(chat()&&threadId!==before);
 }
 const draft=isolated?'':$('message').value;
 const study=!isolated&&$('study-mode').checked;
 const openWithDraft=id=>{
  resetConversation(id);
  $('message').value=draft;
  $('study-mode').checked=study;
 };
 // First-chat setup keeps workspace tools already used in this tab.
 if(!p()&&forms()){status('needApply');return false}
 try{
  let ok=false;
  if(!p()){
   const project=S.project(language==='fa'?'گفتگوهای من':'My conversations');
   const thread=newThread(isolated);
   ok=mutate(v=>{project.threads.push(thread);v.projects.push(project)},{
    afterCommit:()=>{projectId=project.id;openWithDraft(thread.id)}
   });
  }else{
   const thread=newThread(isolated);
   ok=mutate(v=>projectIn(v).threads.push(thread),{
    afterCommit:()=>openWithDraft(thread.id)
   });
  }
  if(ok)$('message').dispatchEvent(new Event('input',{bubbles:true}));
  return Boolean(ok&&chat()&&!chat().archived);
 }catch{status('failed');return false}
}
function noForms(){if(forms()||hasChatDraft()){status('needApply');return false}return true}
function candidate(regenerate=false,materials=[]){const c=chat();if(!c||!p()||c.archived)throw Error('select-chat');if(regenerate){const path=S.path(c),last=path.at(-1);if(last?.role!=='assistant')throw Error('no-answer');if(path.at(-2)?.attached_files?.length)throw Error('reattach-required');return {...S.copy(c),head:last.parent}}return S.append(c,'user',$('message').value.trim(),'human',branchBase===undefined?c.head:branchBase,materials.map(x=>x.name))}
function installThread(next){
 const installed=mutate(v=>{const q=projectIn(v);q.threads[q.threads.findIndex(x=>x.id===next.id)]=next},{afterCommit:clearChatDraft});
 if(installed&&$('auto-speak').checked&&!document.hidden){
  const reply=$('messages').lastElementChild;
  const trigger=reply?.querySelector('[data-chat-speak]');
  if(trigger)window.NexusSpeechPlayback?.start(reply.querySelector('.body').innerText,trigger,{passive:true});
 }
 return installed;
}
$('auto-speak').onchange=()=>{if(!$('auto-speak').checked)window.NexusSpeechPlayback?.stop()};
function selectedModelEngine(){return document.getElementById('model-engine')?.value==='device'?'device':'gateway'}
function prepare(regenerate=false){if(!chat()?.isolated&&(profileDirty||($('use-astrology').checked&&window.NexusAstrologyUI?.hasDraft())))return status('needApply');try{const destination=selectedModelEngine();if(destination==='device'){const info=window.NexusDevice?.info();if(!info?.ready)return status('noModel');modelInfo={...info,configured:true,gateway:'device',provider_host:'this device'}}if(!modelInfo?.configured||modelInfo.gateway!==(destination==='device'?'device':gateway()))return status('noModel');stop();const mode=$('model-mode').value,budget=Number($('model-budget').value);if(!Number.isInteger(budget)||budget<1||budget>(destination==='device'?64:8192)||(mode!=='standard'&&(destination==='device'||!modelInfo.modes?.includes(mode))))throw Error('unsupported-mode');const materials=selectedAttachments(),c=candidate(regenerate,materials),ctx=S.context(p(),c,{attachments:materials,memory:$('use-memory').checked,sources:$('use-sources').checked,relatedChats:$('use-related-chats').checked,historyDays:data.history_days,astrology:$('use-astrology').checked,astroHistorical:$('astro-historical').checked,skyTone:$('sky-tone').checked,study:$('study-mode').checked,onDevice:destination==='device'});if($('study-mode').checked&&!ctx.study)throw Error('study-context-capacity');if(destination==='device'&&JSON.stringify(ctx.messages).length>6000)throw Error('device-context-too-large');const privacyAudit=destination==='gateway'?S.inspectSecrets(ctx.messages):{categories:[],possible_secrets:false};const stream=destination==='gateway'&&modelInfo.streaming===true;
 pending={destination,stream,thread:c,body:{consent:true,configuration_id:modelInfo.configuration_id,messages:ctx.messages,...(destination==='gateway'&&selectedModelSlot!=='primary'?{model_slot:selectedModelSlot}:{}),...(mode!=='standard'||budget!==2048?{mode,max_output_tokens:budget}:{})},revision,projectId,threadId};$('request-context').textContent=JSON.stringify({destination,gateway:destination==='device'?'on-device; no prompt transmission':gateway(),...(destination==='device'?{fixed_policy:modelInfo.policy,max_input_tokens:modelInfo.max_input_tokens}:{}),model:modelInfo.model,...(destination==='gateway'?{model_slot:selectedModelSlot}:{}),provider_host:modelInfo.provider_host,...(stream?{response_delivery:'streaming'}:{}),mode,max_output_tokens:budget,response_style:ctx.study?'study':'standard',omitted_earlier_messages:ctx.omitted_messages,optional_context_truncated:ctx.optional_context_truncated,presentation:ctx.presentation,messages:ctx.messages,source_passages_supplied:ctx.citations,related_chat_passages:ctx.recalled_chats,source_search_truncated:ctx.retrieval_truncated,temporary_attachment_passages:ctx.attachments_supplied,temporary_attachments_partial:ctx.attachments_truncated},null,2);showPrivacy(privacyAudit);$('request-review').hidden=false;controls()}catch(error){status(error?.message==='reattach-required'?'chatRegenRequiresFiles':'failed')}}
function gateway(){const value=$('gateway').value.trim();const u=new URL(value||location.origin);if((u.protocol!=='https:'&&!(u.protocol==='http:'&&['127.0.0.1','[::1]'].includes(u.hostname)))||u.username||u.password||u.search||u.hash||!['','/'].includes(u.pathname))throw Error('gateway-url');return u.origin}
function gatewayFailureLabel(error,request,timedOut=false){
 if(request.destination!=='gateway')return request.stream?'streamFailed':'failed';
 if(timedOut)return 'gatewayTimeout';
 const code=typeof error?.message==='string'&&/^gateway-status-[1-5][0-9]{2}$/.test(error.message)?
  Number(error.message.slice('gateway-status-'.length)):null;
 if(code!==null){
  if(code===401||code===403)return 'gatewayUnauthorized';
  if(code===409)return 'gatewayConfigurationChanged';
  if(code===415||code===422)return 'gatewayInvalidRequest';
  if(code===429)return 'gatewayBusy';
  if(code===503)return 'gatewayUnavailable';
  if([408,500,502,504].includes(code))return 'gatewayUpstreamFailure';
  return 'gatewayRejected';
 }
 if(error?.message==='model-route-mismatch')return 'routeMismatch';
 if(error?.name==='AbortError')return 'gatewayTimeout';
 if(error instanceof TypeError)return 'gatewayNetwork';
 if(['model-stream','incomplete-stream','model-stream-frame','stream-after-end',
   'stream-capacity','model-response','response-capacity','empty-response'].includes(error?.message))
  return 'gatewayMalformedReply';
 return request.stream?'streamFailed':'failed';
}
async function boundedJson(response,max=128000){if(!response.ok)throw Error('gateway-status-'+response.status);if(!response.body)throw Error('empty-response');const reader=response.body.getReader(),chunks=[];let size=0;try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>max)throw Error('response-capacity');chunks.push(value)}const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length}return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes))}finally{await reader.cancel().catch(()=>{})}}
async function streamedAnswer(response,onDelta){
 const media=response.headers.get('content-type')?.split(';',1)[0].trim().toLowerCase();
 if(!response.ok)throw Error('gateway-status-'+response.status);
 if(!response.body||media!=='application/x-ndjson')throw Error('model-stream');
 const reader=response.body.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});
 let bytes=0,partial='',text='',receipt=null;
 try{
  while(true){
   const {done,value}=await reader.read();
   if(done)break;
   bytes+=value.length;
   if(bytes>256000)throw Error('stream-capacity');
   const lines=(partial+decoder.decode(value,{stream:true})).split('\n');
   partial=lines.pop();
   for(const line of lines){
    if(receipt)throw Error('stream-after-end');
    const frame=JSON.parse(line);
    if(frame.type==='delta'&&typeof frame.text==='string'&&frame.text.length){
     if(text.length+frame.text.length>24000)throw Error('stream-capacity');
     text+=frame.text;onDelta(frame.text);
    }else if(frame.type==='done'&&typeof frame.truncated==='boolean'){
     receipt=frame;
    }else throw Error('model-stream-frame');
   }
  }
  if(partial+decoder.decode()||!receipt||!text.trim())throw Error('incomplete-stream');
  return {...receipt,text};
 }finally{await reader.cancel().catch(()=>{})}
}
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
$('new-temporary-chat').onclick=()=>{
 if(mayReplaceChat()&&startConversation(true,{isolated:true}))$('message').focus();
};
$('new-thread').onclick=()=>{
 if(!p()||!mayReplaceChat())return;
 const c=newThread();
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
 if(!mutate(v=>projectIn(v).threads.find(x=>x.id===threadId).head=head,{afterCommit:()=>{window.NexusStudioVision?.clear?.();clearChatDraft()}}))render();
};
$('guide').onclick=()=>{if(chatAttachments.length||$('attach-document').checked)return status('chatAttachmentRequiresModel');if($('use-astrology').checked&&window.NexusAstrologyUI?.hasDraft())return status('needApply');try{const c=candidate();installThread(S.append(c,'assistant',S.guide(S.path(c).at(-1).text,language==='fa',{skyTone:!c.isolated&&$('sky-tone').checked,study:$('study-mode').checked})+(!c.isolated&&$('use-astrology').checked?'\n\n'+NexusAstrology.reflection(p().astrology,language==='fa',{historical:$('astro-historical').checked}):''),'guide'))}catch{status('failed')}};
$('prepare').onclick=()=>prepare();$('regenerate').onclick=()=>{if(!$('regenerate').disabled)prepare(true)};$('consent').onchange=controls;$('stop').onclick=()=>{stop({refresh:false});render()};
const officeReader=file=>/\.docx$/i.test(file.name)?NexusOfficeZip.readDocx:
 /\.pptx$/i.test(file.name)?NexusOfficeZip.readPptx:null;
async function readChatAttachments(files){
 if(!files.length||attachmentLoading||busy||chat()?.archived)return;
 if(!canStageAttachments(files.length)||
    files.some(file=>!file.name||file.name.length>160||file.size>(officeReader(file)?NexusOfficeZip.OFFICE_MAX_BYTES:131072)||file.size<1)){
  status('chatAttachmentInvalid');return;
 }
 const epoch=++attachmentEpoch,pid=projectId,tid=threadId;
 const current=()=>epoch===attachmentEpoch&&pid===projectId&&tid===threadId;
 attachmentLoading=true;
 stop();status('chatFilesReading');
 try{
  const incoming=[];
  for(const file of files){
   const read=officeReader(file);
   const entry=read?{id:S.uid(),name:file.name,text:await read(file)}:(await S.readSources([file]))[0];
   if(!current()||busy)return;
   incoming.push(entry);
  }
  attachmentLoading=false;
  if(!stageChatAttachments(incoming))controls();
 }catch{if(current())status('chatAttachmentInvalid')}
 finally{if(current()&&attachmentLoading){attachmentLoading=false;controls()}}
}
$('chat-file').onchange=event=>{
 const files=Array.from(event.target.files);event.target.value='';
 return readChatAttachments(files);
};
for(const type of ['dragover','drop'])$('message').addEventListener(type,event=>{
 const transfer=event.dataTransfer;
 if(!transfer||!Array.from(transfer.types).includes('Files'))return;
 event.preventDefault();
 if(type==='dragover'){
  transfer.dropEffect=$('chat-file').disabled?'none':'copy';return;
 }
 void readChatAttachments(Array.from(transfer.files));
});
$('message').addEventListener('paste',event=>{
 if(event.defaultPrevented||busy||chat()?.archived)return;
 const text=event.clipboardData?.getData('text/plain')?.replace(/\r\n?/g,'\n');
 const field=event.currentTarget;
 const available=field.maxLength-field.value.length+field.selectionEnd-field.selectionStart;
 if(!text?.trim()||text.length<=available)return;
 event.preventDefault();
 if(text.length<=131072&&new TextEncoder().encode(text).length<=131072&&stageChatContext(t('chatPasteName'),text)){
  status('chatPasteAdded');
 }else status('chatPasteLimit');
});
$('attach-document').onchange=()=>{stop();renderChatAttachments()};
$('clear-chat-files').onclick=()=>{if(busy)return;clearChatAttachments();stop()};
for(const id of ['message','gateway','gateway-token','use-memory','use-sources','use-related-chats','use-astrology','astro-historical','sky-tone','study-mode'])$(id).addEventListener('input',stop);
$('send-model').onclick=async()=>{
 if(!pending||!$('consent').checked||busy||(!privacyPanel.hidden&&!privacyAck.checked))return;
 // A reviewed gateway attempt can consume local budget even on failure;
 // invalidate the previous snapshot before any possible provider request.
 if(pending.destination==='gateway')modelReadiness=null;
 languageImport++;
 const request=pending,rev=revision,abort=new AbortController();
 const current=()=>rev===revision&&request.projectId===projectId&&request.threadId===threadId&&!abort.signal.aborted;
 controller=abort;
 let timedOut=false;
 const timer=setTimeout(()=>{timedOut=true;abort.abort()},request.destination==='device'?120000:50000);
 busy=true;controls();
 try{
  let out;
  if(request.destination==='device'){
   out=await window.NexusDevice.generate(request.body,abort.signal);
  }else{
   const endpoint=request.stream?'/studio-api/respond-stream':'/studio-api/respond';
   const response=await fetch(gateway()+endpoint,{method:'POST',mode:'cors',credentials:'omit',cache:'no-store',redirect:'error',
    headers:{'content-type':'application/json','authorization':'Bearer '+$('gateway-token').value},
    body:JSON.stringify(request.body),signal:abort.signal});
   out=request.stream?await streamedAnswer(response,delta=>{
    if(!current())return;
    const preview=$('model-stream-preview');
    $('model-stream-text').append(delta);
    if(preview.hidden){preview.hidden=false;preview.scrollIntoView({block:'nearest'})}
   }):await boundedJson(response);
  }
  if(!current())return;
  if(out.origin!=='model'||out.authority!=='none'||typeof out.text!=='string'||out.model!==modelInfo?.model)throw Error('model-response');
  const gatewayReply=request.destination==='gateway';
  const expectedSlot=request.body.model_slot||'primary';
  const reported=Object.hasOwn(out,'model_slot')||Object.hasOwn(out,'configuration_id');
  // Older gateways may omit receipt support; any explicit receipt must still
  // match. Upgraded gateways advertise v1 and MUST supply both exact values.
  if(gatewayReply&&(modelInfo?.replyReceiptVersion===1||reported)&&
     (out.model_slot!==expectedSlot||
      out.configuration_id!==request.body.configuration_id))
   throw Error('model-route-mismatch');
  const receipt=gatewayReply&&reported?
   {model_slot:expectedSlot,model:out.model,configuration_id:request.body.configuration_id}:undefined;
  busy=false;
  const label=request.destination==='device'?'[On-device draft · SmolLM2-135M · English / limited]\n\n':'';
  const installed=installThread(S.append(request.thread,'assistant',label+out.text,'model',
   undefined,[],receipt));
  if(installed&&out.truncated)$('status').textContent=language==='fa'?'پاسخ به سقف طول رسیده است.':'The response reached its length limit.';
 }catch(error){if(rev===revision)status(gatewayFailureLabel(error,request,timedOut))}
 finally{clearTimeout(timer);if(rev===revision){busy=false;clearModelReview();controller=null;controls()}}
};
function validatedModelChoices(out){
 if(out.configured!==true)return [];
 const raw=out.models===undefined?[{slot:'primary',model:out.model,provider_host:out.provider_host,
  configuration_id:out.configuration_id,streaming:out.streaming,modes:out.modes}]:out.models;
 if(!Array.isArray(raw)||raw.length<1||raw.length>3||raw[0]?.slot!=='primary')throw Error('invalid-model-catalog');
 const slots=new Set(),allowed=['primary','secondary','tertiary'];
 const items=raw.map((item,index)=>{
  if(!item||typeof item!=='object'||!allowed.includes(item.slot)||slots.has(item.slot)||
     item.slot!==allowed[index]&&!(raw.length===2&&index===1&&item.slot==='tertiary')||
     typeof item.model!=='string'||!item.model||item.model.length>150||
     typeof item.provider_host!=='string'||!item.provider_host||item.provider_host.length>255||
     typeof item.configuration_id!=='string'||!/^[a-f0-9]{64}$/.test(item.configuration_id)||
     item.streaming!==undefined&&item.streaming!==true||
     item.modes!==undefined&&(!Array.isArray(item.modes)||
        item.modes.some(mode=>!['standard','thinking','non-thinking'].includes(mode))))
    throw Error('invalid-model-catalog');
  slots.add(item.slot);
  return {slot:item.slot,model:item.model,provider_host:item.provider_host,
   configuration_id:item.configuration_id,...(item.streaming?{streaming:true}:{}),
   ...(item.modes?{modes:item.modes}:{}),...(item.max_output_tokens?{max_output_tokens:item.max_output_tokens}:{})};
 });
 if(items[0].model!==out.model||items[0].provider_host!==out.provider_host||
    items[0].configuration_id!==out.configuration_id)throw Error('primary-mismatch');
 return items;
}
$('check-model').onclick=()=>operation(async(rev,abort)=>{
 if(selectedModelEngine()==='device'){
  const info=window.NexusDevice?.info();
  modelChoices=[];selectedModelSlot='primary';
  modelInfo=info?{...info,configured:true,gateway:'device',provider_host:'this device'}:null;
  $('model-status').textContent=info?info.model+' · on-device · max 64 output tokens':t('noModel');return;
 }
 const timer=setTimeout(()=>abort.abort(),10000);
 try{
  const origin=gateway();
  const out=await boundedJson(await fetch(origin+'/studio-api/status',{
   credentials:'omit',cache:'no-store',redirect:'error',signal:abort.signal}),8000);
  if(rev===revision){
   if(out.configured!==true&&out.configured!==false)throw Error('configuration');
   if(out.reply_receipt_version!==undefined&&out.reply_receipt_version!==1)
    throw Error('reply-receipt-version');
   const choices=validatedModelChoices(out);
   const slot=choices.some(option=>option.slot===selectedModelSlot)?selectedModelSlot:'primary';
   const chosen=choices.find(option=>option.slot===slot);
   // An operator-authenticated readiness lookup is local and read-only. It
   // never probes the paid provider and cannot replace per-request consent.
   // Optional on older gateways; failure leaves only the public config state.
   let readiness=null;
   const operatorToken=$('gateway-token').value.trim();
   if(chosen&&operatorToken.length>=32){
    try{
     const diagnosticResponse=await fetch(origin+'/studio-api/operator-readiness?model_slot='+slot,{
      mode:'cors',credentials:'omit',cache:'no-store',redirect:'error',
      headers:{'authorization':'Bearer '+operatorToken},signal:abort.signal
     });
     if(diagnosticResponse.ok){
      const report=await boundedJson(diagnosticResponse,5000);
      const remaining=report.local_request_budget?.remaining;
      if(report.model_slot===slot&&report.model===chosen.model&&
         report.provider_host===chosen.provider_host&&
         report.provider_contact_attempted===false&&
         report.provider_live_verification==='NOT_RECORDED'&&
         ['READY_TO_TEST','LOCAL_BUDGET_EXHAUSTED','LOCAL_BUDGET_UNAVAILABLE'].includes(report.readiness)&&
         Number.isInteger(remaining)&&remaining>=0&&remaining<=4096){
       readiness={slot,gateway:origin,configuration_id:chosen.configuration_id,
        state:report.readiness,remaining};
      }
     }
    }catch{ /* Optional local diagnostics never block public model discovery. */ }
   }
   if(rev===revision){
    modelChoices=choices;selectedModelSlot=slot;
    modelInfo={...(chosen||out),configured:out.configured,gateway:origin,
     replyReceiptVersion:out.reply_receipt_version===1?1:0};
    modelReadiness=readiness;
    $('model-status').textContent=out.configured?t('configured')+': '+modelInfo.model+' · '+modelInfo.provider_host:t('noModel');
    controls();
   }
  }
 }finally{clearTimeout(timer)}
});
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
 if(!p()||!title||(doc()&&editorDirty&&!confirm(t('discard'))))return;
 const untitledDraft=doc()?null:$('editor').value;
 const d={id:S.uid(),title,versions:[]};
 mutate(v=>projectIn(v).documents.push(d),{afterCommit:()=>{
  selectDocument(d.id);
  if(untitledDraft){$('editor').value=untitledDraft;editorDirty=true}
  $('document-title').value='';
 }});
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
$('export-document-word').onclick=()=>{
 if(doc()&&!busy)downloadWord(doc().title,$('editor').value,'nexus-document.docx');
};
$('canvas-chat').onclick=()=>{
 if($('canvas-chat').disabled)return;
 const label=doc()?t('canvasDraft')+' · '+doc().title:t('canvasDraft');
 stageChatContext(label.slice(0,160),$('editor').value);
};
$('export-thread').onclick=()=>{if(chat()&&confirm(t('plain')))download('# '+chat().title+'\n\n'+S.path(chat()).map(n=>'## '+messageOriginLabel(n)+'\n\n'+n.text+(n.attached_files?.length?'\n\n'+t('chatAttachedUsed')+' '+n.attached_files.join(', ')+' — '+t('chatFilesNotSaved'):'')).join('\n\n'),'nexus-conversation.md','text/markdown')};
$('export-thread-html').onclick=()=>{
 const thread=chat();
 if(busy||!thread?.head||!confirm(t('plain')))return;
 const sections=S.path(thread).map(n=>({
  label:messageOriginLabel(n),
  text:n.text,format:n.origin==='model'
 }));
 download(NexusReplyFormat.exportConversation(document,sections,thread.title),'nexus-conversation.html','text/html;charset=utf-8');
 status('chatExportDone');
};
$('create-vault').onclick=()=>{const pass=$('passphrase').value;if(pass!==$('repeat-passphrase').value)return status('failed');$('passphrase').value='';$('repeat-passphrase').value='';operation((rev,abort)=>vault.create(pass,{signal:abort.signal}))};
$('unlock').onclick=()=>{if(storageSnapshot().lossRisk&&!confirm(t('discard')))return;const pass=$('passphrase').value;$('passphrase').value='';$('repeat-passphrase').value='';operation(async(rev,abort)=>{const next=await vault.unlock(pass,{signal:abort.signal});if(rev!==revision)return;undoSlot.clear();data=next;dirty=false;selectProject(data.projects[0]?.id||null);render()})};
$('history-days').onchange=()=>{
 const value=$('history-days').value,days=value===''?null:Number(value);
 if(days===0&&!confirm(t('historyConfirm'))){controls();return}
 if(!mutate(next=>{
  next.history_days=days;
  if(days===0)for(const project of next.projects)for(const thread of project.threads)thread.temporary=true;
 }))controls();
};
$('training-opt-in').onchange=()=>{clearTrainingReview();controls()};
$('training-review').onclick=()=>{
 const thread=chat();
 if(busy||!$('training-opt-in').checked||!thread?.head||thread.isolated)return;
 const messages=S.path(thread).map(({role,text})=>({role,text}));
 const payload=JSON.stringify({schema:'nexus.studio.training-export.v1',messages},null,2);
 trainingReview={thread:thread.id,head:thread.head,payload};
 $('training-preview').textContent=payload;$('training-preview').hidden=false;$('training-download').hidden=false;
};
$('training-download').onclick=()=>{
 const reviewed=trainingReview;
 if(busy||!$('training-opt-in').checked||!reviewed||reviewed.thread!==threadId||reviewed.head!==chat()?.head)return;
 if(confirm(t('trainingConfirm')))download(reviewed.payload,'nexus-training-text.json','application/json');
};
$('save').onclick=()=>{
 if(!noForms())return;
 const now=Date.now(),snapshot=S.retainHistory(data,{now,inSession:true});
 operation(async(rev,abort)=>{
  await vault.save(snapshot,{signal:abort.signal,now});if(rev!==revision)return;
  if(JSON.stringify(data)!==JSON.stringify(snapshot)){
   data=snapshot;undoSlot.clear();
   if(!chat())resetConversation(p()?.threads.find(c=>!c.archived&&!c.isolated)?.id||null);
   render();
  }
  dirty=false;
 },'saved');
};
$('lock').onclick=()=>{if(storageSnapshot().lossRisk&&!confirm(t('discard')))return;const clean=toolLifecycle('private');undoSlot.clear();stop({refresh:false});clearChatDraft();modelInfo=null;vault.lock();data=S.empty();projectId=threadId=documentId=null;dirty=profileDirty=editorDirty=false;for(const id of ['passphrase','repeat-passphrase','gateway-token','project-title','document-title','instructions','memories','editor','source-query','search'])$(id).value='';$('model-status').textContent='';$('source-results').textContent='';renderVersions();render();if(!clean)location.reload()};
$('backup').onclick=()=>{if(!noForms())return;const pass=$('passphrase').value;if(pass!==$('repeat-passphrase').value)return status('failed');$('passphrase').value='';$('repeat-passphrase').value='';operation(async(rev,abort)=>{const raw=await vault.export(data,pass,{signal:abort.signal});if(rev===revision)download(raw,'nexus-studio.encrypted.json','application/json')})};
$('restore').onclick=()=>$('restore-file').click();$('restore-file').onchange=event=>{const f=event.target.files[0];event.target.value='';if(!f||f.size>6*1024*1024||!confirm(t('discard')))return;const pass=$('passphrase').value;$('passphrase').value='';$('repeat-passphrase').value='';operation(async(rev,abort)=>{const raw=await f.text();if(rev!==revision||abort.signal.aborted)return;const opened=await S.decrypt(raw,pass,{signal:abort.signal});if(rev!==revision)return;undoSlot.clear();
 const imported=opened.data;
 if(data.history_days!==undefined)imported.history_days=data.history_days;
 data=S.retainHistory(imported);dirty=true;selectProject(data.projects[0]?.id||null);render()})};
$('erase').onclick=()=>{if(confirm(t('discard')))operation(async(rev,abort)=>{
  window.NexusDevice?.unload();await vault.erase({signal:abort.signal});
  if(rev!==revision){if(!vault.unlocked&&data.projects.length)dirty=true;return}
  const clean=toolLifecycle('private');undoSlot.clear();modelInfo=null;for(const id of ['gateway-token','source-query','search','project-title','document-title'])$(id).value='';data=S.empty();selectProject(null);dirty=false;render();if(!clean)location.reload();
})};
$('language-template').onclick=()=>download(JSON.stringify({schema:'nexus.studio.locale.v1',code:'en',dir:'ltr',messages:EN},null,2),'nexus-studio-english-labels.json','application/json');
$('language-file').onchange=async event=>{
 const f=event.target.files[0],task=++languageImport,rev=revision;event.target.value='';
 if(!f||busy)return;if(f.size>NexusLocales.MAX_BYTES)return status('failed');
 const current=()=>task===languageImport&&rev===revision&&!busy;
 try{
  const raw=await f.text();if(!current())return;const pack=localePacks.install(raw,EN,{retiredKeys:['decisionMode','decisionHelp'],optionalKeys:[...Object.keys(PRIVACY_EN),...Object.keys(CHAT_CONTEXT_EN),'storageTools','storageToolsDraft','storageToolsNone','studyMode','researchBoth','researchAll','researchPartial','researchPick','researchBrief','researchBriefChat','researchBriefExport','researchQueries','researchPlanConsent','researchProgress','researchTimeLimit','researchCardQueries','researchInvalidPlan','streamPreview','streamFailed','routeMismatch',...Object.keys(EN).filter(key=>key.startsWith('gateway')),...Object.keys(EN).filter(key=>key.startsWith('reminder')||key.startsWith('chatCopy')||key.startsWith('chatExport')||key.startsWith('chatPaste'))]});
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
function appendVisionResult({prompt,answer,selection}){
  if(!selection||typeof prompt!=='string'||typeof answer!=='string'||
     !prompt.trim()||prompt.length>4000||!answer.trim()||answer.length>24000||
     busy||!chat()||chat().archived||branchBase!==selection.branchBase||
     projectId!==selection.projectId||threadId!==selection.threadId||
     revision!==selection.revision||chat().head!==selection.head||
     $('message').value.trim()||chatAttachments.length||$('attach-document').checked)return false;
  try{
   const first=S.append(chat(),'user',prompt,'human',
    branchBase===undefined?chat().head:branchBase,['Image supplied (binary not saved)']);
   const completed=S.append(first,'assistant',answer,'model');
   return installThread(completed);
  }catch{return false}
}
function modelAvailability(){
 // Configuration is not a provider liveness or billing attestation.
 if($('model-engine')?.value==='device'){
  const info=window.NexusDevice?.info();
  return {kind:'device',checked:Boolean(info),configured:Boolean(info?.ready),
          model:info?.ready?String(info.model).slice(0,150):null};
 }
 let origin;
 try{origin=gateway()}catch{return {kind:'gateway',checked:false,configured:false}}
 if(!modelInfo||modelInfo.gateway!==origin)return {kind:'gateway',checked:false,configured:false};
 const diagnostic=modelReadiness?.gateway===origin&&
  modelReadiness.slot===selectedModelSlot&&
  modelReadiness.configuration_id===modelInfo.configuration_id?modelReadiness:null;
 return {kind:'gateway',checked:true,configured:modelInfo.configured===true,
         slot:selectedModelSlot,model:modelInfo.configured?String(modelInfo.model).slice(0,150):null,
         providerHost:modelInfo.configured?String(modelInfo.provider_host).slice(0,255):null,
         ...(diagnostic?{localReadiness:diagnostic.state,remainingRequests:diagnostic.remaining}:{})};
}
function availableModelOptions(){
 if($('model-engine')?.value==='device')return [];
 try{if(modelInfo?.gateway!==gateway())return []}catch{return []}
 return modelChoices.map(item=>({slot:item.slot,model:item.model,providerHost:item.provider_host}));
}
function selectModelSlot(slot){
 if(busy||!['primary','secondary','tertiary'].includes(slot)||
    $('model-engine')?.value==='device')return false;
 const choice=modelChoices.find(item=>item.slot===slot);
 if(!choice||!availableModelOptions().length)return false;
 if(slot===selectedModelSlot)return true;
 stop();  // Cancels stale approvals, previous provider responses and streaming.
 selectedModelSlot=slot;modelReadiness=null;
 modelInfo={...choice,configured:true,gateway:gateway(),
  replyReceiptVersion:modelInfo?.replyReceiptVersion===1?1:0};
 $('model-status').textContent=t('configured')+': '+choice.model+' · '+choice.provider_host;
 controls();return true;
}
window.NexusStudioUI=Object.freeze({schema:'nexus.studio.ui.v1',startConversation,openConversation,selection:()=>({projectId,threadId,head:chat()?.head||null,revision,branchBase}),appendVisionResult,lifecycle_version:TOOL_LIFECYCLE.version,storageStatus:storageSnapshot,snapshot:()=>S.copy(data),stageChatContext,uiStatus:()=>({vaultUnlocked:vault.unlocked,dirty,busy,unsavedForms:forms()||chatAttachments.length>0||$('attach-document').checked,unsavedLocalMedia:unsavedLocalMedia(),lossRisk:storageSnapshot().lossRisk,threadReady:!!chat(),attachmentLoading,archived:!!chat()?.archived,pendingReview:!!pending,hasChatAttachments:chatAttachments.length>0||$('attach-document').checked}),modelAvailability,availableModelOptions,selectModelSlot,revokeModelReview:()=>stop(),resetModel:()=>{stop();modelChoices=[];selectedModelSlot='primary';modelInfo=null;modelReadiness=null;$('model-status').textContent='';render()}});$('language').value=language;applyLanguage();

for(const id of ['model-mode','model-budget'])$(id).addEventListener('input',stop);
for(const id of ['gateway','gateway-token'])$(id).addEventListener('input',()=>{modelReadiness=null});
