'use strict';
(function(){
const L=NexusLab,run=new L.Sandbox();let epoch=0,searchController=null,codeController=null,cards=[],result=null,chartData=null;
const selectedSources=new Set();
let localAttempt=0,activeResearchAttempt=null,activeCodeAttempt=null;
function localLifecycle(tool,runId,phase){
 // No prompts, user input, result bytes, credentials, or arbitrary payload.
 document.dispatchEvent(new CustomEvent('nexus-studio-local-tool-lifecycle',{
  detail:{tool,runId,phase}
 }));
}
Object.assign(EN,{research:'Live research desk',researchHelp:'Only the exact queries below are sent directly to the selected public APIs. Conversations, files, memory and credentials are not added. Results are source leads, not verified facts or automatic research conclusions.',researchQuery:'Public query (up to 250 characters)',researchProvider:'Source provider',researchLanguage:'Wikipedia language',researchConsent:'Send this exact query to the selected source provider(s) once.',researchSearch:'Search public sources',researchStop:'Cancel research',researchAdd:'Keep excerpt as a project source',researchEmpty:'No matching sources were returned.',researchWorking:'Retrieving public source leads…',researchFailed:'Source retrieval failed or was blocked. Check connectivity, provider availability and query.',researchNote:'Crossref provides bibliographic metadata, not paper findings or full text. Wikipedia extracts carry its attribution terms.',codeLab:'Local JavaScript lab',codeHelp:'Runs exactly the code and input shown in an opaque-origin browser worker. It has no access to Studio DOM, archive storage or network. Execution stops after 3 seconds and output is capped at 64,000 bytes. There is no hard memory quota; this is not a Python or operating-system sandbox. Inputs and outputs are temporary; copy output to the writing canvas to keep it.',codeSource:'JavaScript function body — use input (a string), console.log and return',codeInput:'Only this input is passed to the code',codeConsent:'Run this exact code and input locally once.',codeSample:'Load calculation sample',codeRun:'Run locally',codeStop:'Stop execution',codeCopy:'Copy output into writing canvas',codeOutput:'Untrusted local program output',codeWorking:'Running locally…',codeFailed:'Execution failed, exceeded a limit, or was cancelled.',chartLab:'Local data chart',chartHelp:'Provide JSON: type (bar or line), title, labels and numeric values. At most 200 points; finite values up to ±10¹². No model, upload or code execution is used to draw the chart.',chartDraw:'Draw chart',chartUse:'Use code result',chartExport:'Export PNG',chartJson:'Chart data JSON',chartFailed:'Invalid chart data. Check type, matching labels/values and numeric limits.'});
Object.assign(FA,{research:'میز پژوهش زنده',researchHelp:'فقط عبارت‌های دقیق زیر مستقیماً به APIهای عمومی انتخاب‌شده فرستاده می‌شوند. گفتگو، فایل، حافظه و توکن‌ها اضافه نمی‌شوند. نتیجه‌ها سرنخ منبع‌اند، نه حقیقت تأییدشده یا نتیجه‌گیری خودکار.',researchQuery:'عبارت عمومی — حداکثر ۲۵۰ نویسه',researchProvider:'ارائه‌دهندهٔ منبع',researchLanguage:'زبان ویکی‌پدیا',researchConsent:'این عبارت دقیق را یک بار به منابع انتخاب‌شده بفرست.',researchSearch:'جست‌وجوی منابع عمومی',researchStop:'لغو پژوهش',researchAdd:'نگهداری گزیده به‌عنوان منبع پروژه',researchEmpty:'منبع مطابق پیدا نشد.',researchWorking:'در حال دریافت سرنخ‌های منابع عمومی…',researchFailed:'دریافت منبع ناموفق یا مسدود شد. اتصال، دسترس‌پذیری سرویس و عبارت را بررسی کن.',researchNote:'Crossref اطلاعات کتاب‌شناختی می‌دهد، نه یافته یا متن کامل مقاله. گزیده‌های ویکی‌پدیا تابع شرایط انتساب آن هستند.',codeLab:'آزمایشگاه محلی JavaScript',codeHelp:'فقط کد و ورودی نمایش‌داده‌شده در یک Worker مرورگر با مبدأ ایزوله اجرا می‌شوند. به صفحه، آرشیو و شبکهٔ Studio دسترسی ندارد. پس از ۳ ثانیه متوقف می‌شود و خروجی تا ۶۴٬۰۰۰ بایت محدود است. سقف سخت حافظه ندارد؛ محیط Python یا سیستم‌عامل نیست. ورودی و خروجی موقت‌اند؛ برای نگهداری، خروجی را به ویرایشگر نوشته کپی کن.',codeSource:'بدنهٔ تابع JavaScript — از input به‌صورت رشته، console.log و return استفاده کن',codeInput:'فقط همین ورودی به کد داده می‌شود',codeConsent:'این کد و ورودی دقیق را یک بار محلی اجرا کن.',codeSample:'بارگذاری نمونهٔ محاسبه',codeRun:'اجرای محلی',codeStop:'توقف اجرا',codeCopy:'کپی خروجی به ویرایشگر نوشته',codeOutput:'خروجی تأییدنشدهٔ برنامهٔ محلی',codeWorking:'در حال اجرای محلی…',codeFailed:'اجرا ناموفق، لغو یا متوقف شد یا از محدودیت گذشت.',chartLab:'نمودار دادهٔ محلی',chartHelp:'JSON شامل type برابر bar یا line، عنوان title، برچسب‌های labels و مقادیر عددی values بده. حداکثر ۲۰۰ نقطه و عدد متناهی تا ±۱۰¹². رسم نمودار به مدل، ارسال داده یا اجرای کد نیاز ندارد.',chartDraw:'رسم نمودار',chartUse:'استفاده از نتیجهٔ کد',chartExport:'خروجی PNG',chartJson:'دادهٔ JSON نمودار',chartFailed:'دادهٔ نمودار معتبر نیست. نوع، تعداد برابر برچسب و مقدار و محدودیت عددی را بررسی کن.'});
Object.assign(EN,{researchChat:'Use source excerpt in next chat',codeChat:'Use code result in next chat'});Object.assign(FA,{researchChat:'استفاده از گزیدهٔ منبع در پیام بعدی',codeChat:'استفاده از نتیجهٔ کد در پیام بعدی'});
Object.assign(EN,{
 researchBoth:'Wikipedia and Crossref',researchAll:'Wikipedia, Crossref and Europe PMC',researchPartial:'Some providers failed: ',researchPick:'Include in brief',
 researchBrief:'Research brief',researchBriefChat:'Attach brief excerpts to chat',researchBriefExport:'Download brief',
 researchQueries:'Search queries (up to four, one per line, 250 characters each)',
 researchPlanConsent:'Send these exact queries once to the selected providers.',
 researchProgress:'Queries completed',researchTimeLimit:'The search reached its time limit. Available results are shown below.',
 researchCardQueries:'Matched queries',researchInvalidPlan:'Enter up to four queries, one per line, with 250 characters or fewer per query.'
});
Object.assign(FA,{
 researchBoth:'ویکی‌پدیا و کراس‌رف',researchAll:'ویکی‌پدیا، کراس‌رف و Europe PMC',researchPartial:'دریافت از بعضی منابع ناموفق بود: ',researchPick:'افزودن به پرونده',
 researchBrief:'پروندهٔ پژوهشی',researchBriefChat:'پیوست گزیدهٔ پرونده به گفتگو',researchBriefExport:'دریافت پرونده',
 researchQueries:'عبارت‌های جست‌وجو (حداکثر چهار عبارت، هر خط یک عبارت تا ۲۵۰ نویسه)',
 researchPlanConsent:'همین عبارت‌ها را یک بار به ارائه‌دهندگان انتخاب‌شده بفرست.',
 researchProgress:'عبارت‌های بررسی‌شده',researchTimeLimit:'مهلت جست‌وجو پایان یافت. نتایج دریافت‌شده در پایین آمده‌اند.',
 researchCardQueries:'عبارت‌های مرتبط',researchInvalidPlan:'حداکثر چهار عبارت وارد کن؛ هر عبارت در یک خط و تا ۲۵۰ نویسه.'
});
function renderBrief(){
 const picked=cards.filter(card=>selectedSources.has(card));
 $('research-brief').hidden=!picked.length;
 const brief=picked.length?L.researchBrief(picked):'';
 $('research-brief-text').textContent=brief;
 $('research-brief-chat').onclick=()=>{if(brief)window.NexusStudioUI.stageChatContext(t('researchBrief'),brief)};
 $('research-brief-export').onclick=()=>{if(brief&&confirm(t('plain')))download(brief,'nexus-research-brief.txt')};
 const limit=selectedSources.size===5;
 for(const checkbox of $('research-cards').querySelectorAll('input[type="checkbox"]')){
  checkbox.disabled=limit&&!checkbox.checked;
 }
}
function syncCodeRun(){
 const gate=window.NexusMusicUI;
 $('code-run').disabled=Boolean(codeController||!gate||gate.audioBusy());
 $('code-run').title=gate?.audioBusy()?(gate.resourceMessage?.()||t('localResourceBusy')):'';
}
Object.assign(EN,{localResourceBusy:'Finish the active local job or unload the local model first.'});
Object.assign(FA,{localResourceBusy:'ابتدا پردازش محلی فعال را پایان بده یا مدل محلی را از حافظه خارج کن.'});
document.addEventListener('nexus-audio-job-state',syncCodeRun);
function cancel(){const oldResearch=activeResearchAttempt,oldCode=activeCodeAttempt;
 activeResearchAttempt=activeCodeAttempt=null;
 epoch++;searchController?.abort();codeController?.abort();searchController=codeController=null;
 if(oldResearch!==null)localLifecycle('research',oldResearch,'cancelled');
 if(oldCode!==null)localLifecycle('code',oldCode,'cancelled');run.cancel();$('research-consent').checked=false;$('code-consent').checked=false;$('research-run').disabled=false;syncCodeRun();$('research-stop').disabled=true;$('code-stop').disabled=true;$('code-status').textContent='';$('research-status').textContent=''}
const workFields=['research-query','code','code-input','chart-json'];
function hasTransientWork(){return workFields.some(id=>$(id).value.length>0)}
function clear(){cancel();cards=[];selectedSources.clear();result=chartData=null;for(const id of workFields)$(id).value='';for(const id of ['research-cards','research-status','code-result','code-console','code-status'])$(id).replaceChildren();$('chart').hidden=true;$('chart').width=1;$('chart').height=1;renderBrief()}
function renderCards(){
 $('research-cards').replaceChildren();for(const card of cards){const box=el('article','');box.className='message';const link=el('a',card.title);link.href=card.url;link.target='_blank';link.rel='noopener noreferrer';box.append(link,el('p',card.kind+' · '+card.at),el('p',card.excerpt),el('p',card.license));const add=el('button',t('researchAdd'));add.disabled=!p();add.onclick=()=>{if(!p())return;const source={id:S.uid(),name:(card.engine+' · '+card.title).slice(0,160),text:L.sourceText(card)};mutate(v=>projectIn(v).sources.push(source))};const use=el('button',t('researchChat'));use.className='secondary';use.onclick=()=>{window.NexusStudioUI?.stageChatContext((card.engine+' · '+card.title).slice(0,160),L.sourceText(card))};const pick=el('input','');pick.type='checkbox';pick.checked=selectedSources.has(card);
 const label=el('label','');label.className='inline';label.append(pick,' '+t('researchPick'));
 pick.onchange=()=>{if(pick.checked)selectedSources.add(card);else selectedSources.delete(card);renderBrief()};
 box.append(el('p',t('researchCardQueries')+' · '+card.queries.join(' | ')));
 box.append(add,use,label);$('research-cards').append(box)}
 renderBrief();
}
for(const id of ['research-query','research-provider','research-language'])for(const event of ['input','change'])$(id).addEventListener(event,()=>{cancel();cards=[];selectedSources.clear();renderCards();$('research-status').textContent=''});
$('research-run').onclick=async()=>{
 if(!$('research-consent').checked||searchController)return;
 const query=$('research-query').value.trim(),provider=$('research-provider').value,lang=$('research-language').value,scope=epoch;const abort=new AbortController();searchController=abort;$('research-consent').checked=false;$('research-run').disabled=true;$('research-stop').disabled=false;$('research-status').textContent=t('researchWorking');cards=[];selectedSources.clear();renderCards();const timer=setTimeout(()=>abort.abort(),20000),runId=++localAttempt;
 activeResearchAttempt=runId;localLifecycle('research',runId,'started');
 try{
  const {cards:found,failed,successful,timedOut}=await L.researchPlan(provider,query,lang,abort.signal,(completed,total)=>{
   if(scope===epoch&&total>1)$('research-status').textContent=t('researchProgress')+' · '+completed+'/'+total;
  });
  if(scope!==epoch)return;
  cards=found;renderCards();
  $('research-status').textContent=timedOut?t('researchTimeLimit'):!successful?t('researchFailed'):
   failed.length?t('researchPartial')+failed.join(', '):cards.length?'':t('researchEmpty');
  localLifecycle('research',runId,!successful?'failed':timedOut||failed.length?'partial':'succeeded');
 }catch(error){if(scope===epoch){$('research-status').textContent=t(error?.message==='query-plan'?'researchInvalidPlan':'researchFailed');localLifecycle('research',runId,'failed')}}finally{clearTimeout(timer);if(scope===epoch){activeResearchAttempt=null;searchController=null;$('research-run').disabled=false;$('research-stop').disabled=true}}
};
$('research-stop').onclick=cancel;
for(const id of ['code','code-input'])$(id).addEventListener('input',()=>{cancel();result=null;$('code-result').textContent='';$('code-console').textContent=''});
$('code-sample').onclick=()=>{if($('code').value&&!confirm(t('discard')))return;cancel();result=null;$('code-result').textContent='';$('code-console').textContent='';$('code-input').value='{"values":[3,5,2]}';$('code').value="const data = JSON.parse(input);\nconst values = data.values;\nconsole.log({count: values.length, sum: values.reduce((a,b)=>a+b, 0)});\nreturn {type:'bar', title:'Local calculation', labels: values.map((_,i)=>String(i+1)), values};";renderStorage()};
$('code-run').onclick=async()=>{
 if(!$('code-consent').checked||codeController)return;
 const release=window.NexusMusicUI?.acquireAudioJob('code');
 if(!release){$('code-status').textContent=t('localResourceBusy');return}
 const scope=epoch,abort=new AbortController();codeController=abort;$('code-consent').checked=false;$('code-run').disabled=true;$('code-stop').disabled=false;$('code-status').textContent=t('codeWorking');$('code-console').textContent='';$('code-result').textContent='';result=null;
 const runId=++localAttempt;activeCodeAttempt=runId;localLifecycle('code',runId,'started');
 try{const text=await run.run($('code').value,$('code-input').value,{signal:abort.signal,onLog:line=>{if(scope===epoch)$('code-console').textContent+=line+'\n'}});if(scope!==epoch)return;result=text;$('code-result').textContent=text;$('code-status').textContent='';localLifecycle('code',runId,'succeeded')}catch{if(scope===epoch){$('code-status').textContent=t('codeFailed');localLifecycle('code',runId,'failed')}}finally{if(scope===epoch){activeCodeAttempt=null;codeController=null;$('code-stop').disabled=true}release();syncCodeRun()}
};
$('code-stop').onclick=cancel;
$('code-chat').onclick=()=>{if(result!==null)window.NexusStudioUI?.stageChatContext('Local code result · untrusted',result)};
$('code-copy').onclick=()=>{if(result===null)return;if($('editor').value&&!confirm(t('discard')))return;$('editor').value=result;editorDirty=true;stop()};
$('chart-use').onclick=()=>{if(result!==null){$('chart-json').value=result;chartData=null;$('chart').hidden=true;renderStorage()}};
$('chart-json').addEventListener('input',()=>{chartData=null;$('chart').hidden=true});
$('chart-draw').onclick=()=>{try{chartData=L.draw($('chart'),JSON.parse($('chart-json').value));$('chart').hidden=false;$('chart-status').textContent=''}catch{chartData=null;$('chart').hidden=true;$('chart-status').textContent=t('chartFailed')}};
$('chart-export').onclick=()=>{if(!chartData||!confirm(t('plain')))return;const scope=epoch,snapshot=chartData;$('chart').toBlob(blob=>{if(!blob||scope!==epoch||snapshot!==chartData)return;const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download='nexus-chart.png';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)},'image/png')};
window.NexusLabUI=Object.freeze({cancel,clear,hasTransientWork,render:renderCards,setChart:value=>{const checked=L.chart(value);$('chart-json').value=JSON.stringify(checked);$('chart-draw').click();renderStorage()}});applyLanguage();
})();
