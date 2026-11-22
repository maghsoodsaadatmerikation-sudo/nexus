'use strict';
(function(){
const runner=new NexusTasks.Runner();let epoch=0,report=null,working=false,reviewedStep=null;
function clearReviewedStep(){reviewedStep=null}
function armReviewedStep(kind,callback){
 if(kind!=='tasks'||typeof callback!=='function'||working)return false;
 reviewedStep=callback;return true;
}
function observeTasks(value){
 if(!reviewedStep||!value?.jobs?.length||value.jobs.length>12||
    value.jobs.some(job=>job.status!=='succeeded'))return;
 const callback=reviewedStep;reviewedStep=null;
 try{callback(Object.freeze({kind:'tasks',source:'studio-local-tasks',
  completed:true,artifact:'task-report',succeeded:value.jobs.length,
  failed:0,cancelled:0}))}catch{}
}
Object.assign(EN,{tasks:'Parallel local tasks',tasksHelp:'Review a JSON plan of up to 12 JavaScript jobs. Up to two isolated Workers run dependencies after success. Each job has a 3-second watchdog and the plan a 60-second limit. No network/archive access or hard memory quota. Chat stays usable. Runs need consent; drafts and reports are temporary, not an autonomous agent.',tasksPlan:'Exact plan — version: 1; jobs: id, code, input, needs; concurrency: 1 or 2. Worker input is JSON containing input (string) and dependencies (map of result strings).',tasksConsent:'Execute this exact plan locally once.',tasksSample:'Load dependency example',tasksRun:'Run plan',tasksStop:'Cancel plan',tasksExport:'Export report',tasksFailed:'Invalid plan or execution unavailable.'});
Object.assign(FA,{tasks:'کارهای محلی هم‌زمان',tasksHelp:'طرح JSON حداکثر ۱۲ کار JavaScript را بازبینی کن. حداکثر دو Worker ایزوله کارها را پس از موفقیت پیش‌نیاز اجرا می‌کنند. هر کار ۳ ثانیه و کل طرح ۶۰ ثانیه مهلت دارد. شبکه و آرشیو در دسترس نیستند؛ سقف سخت حافظه هم وجود ندارد. گفتگو فعال می‌ماند. اجرا به تأیید تو نیاز دارد؛ طرح و گزارش موقت‌اند و عامل خودمختار نیستند.',tasksPlan:'طرح دقیق — version: 1؛ jobs: id, code, input, needs؛ concurrency: 1 یا 2. ورودی Worker یک JSON شامل input به‌صورت رشته و dependencies به‌صورت نگاشت خروجی‌های رشته‌ای است.',tasksConsent:'همین طرح دقیق را یک بار محلی اجرا کن.',tasksSample:'بارگذاری نمونهٔ کارهای وابسته',tasksRun:'اجرای طرح',tasksStop:'لغو طرح',tasksExport:'خروجی گزارش',tasksFailed:'طرح نامعتبر است یا اجرا در دسترس نیست.'});
const progressLabels={
 en:{queued:'queued',running:'running',succeeded:'succeeded',failed:'failed',blocked:'blocked by dependencies',cancelled:'cancelled',deadline:'Plan time limit reached.'},
 fa:{queued:'در صف',running:'در حال اجرا',succeeded:'موفق',failed:'ناموفق',blocked:'متوقف به‌دلیل پیش‌نیاز',cancelled:'لغوشده',deadline:'مهلت اجرای طرح تمام شد.'}
};
function show(){
 $('task-report').textContent=report?JSON.stringify(report,null,2):'';
 $('task-run').disabled=working;
 $('task-stop').disabled=!working;
 $('task-export').disabled=!report||working;
 if(!report)return;
 const labels=progressLabels[document.documentElement.lang==='fa'?'fa':'en'];
 const counts={};
 for(const job of report.jobs)counts[job.status]=(counts[job.status]??0)+1;
 const summary=Object.keys(labels).filter(key=>counts[key]).map(key=>counts[key]+' '+labels[key]).join(' · ');
 const deadline=report.jobs.some(job=>job.error==='deadline-exceeded');
 const status=deadline?labels.deadline+' '+summary:summary;
 if($('task-status').textContent!==status)$('task-status').textContent=status;
}
function cancel(){epoch++;runner.cancel();working=false;$('task-consent').checked=false;show()}
function clear(){clearReviewedStep();cancel();report=null;$('task-plan').value='';$('task-status').textContent='';show()}
$('task-plan').addEventListener('input',()=>{cancel();report=null;$('task-status').textContent='';show()});
$('task-sample').onclick=()=>{if($('task-plan').value&&!confirm(t('discard')))return;clear();$('task-plan').value=JSON.stringify({version:1,concurrency:2,jobs:[{id:'sum',input:'[2,3,5]',code:'const data=JSON.parse(input); return JSON.parse(data.input).reduce((a,b)=>a+b,0);'},{id:'count',input:'[2,3,5]',code:'return JSON.parse(JSON.parse(input).input).length;'},{id:'mean',needs:['sum','count'],code:'const d=JSON.parse(input).dependencies; return JSON.parse(d.sum)/JSON.parse(d.count);'}]},null,2);renderStorage()};
$('task-run').onclick=async()=>{if(working||!$('task-consent').checked)return;const scope=++epoch;$('task-consent').checked=false;$('task-status').textContent='';report=null;try{const plan=NexusTasks.validate(JSON.parse($('task-plan').value));working=true;const result=await runner.run(plan,{onUpdate:value=>{if(scope===epoch){report=value;show()}}});if(scope===epoch)observeTasks(result)}catch{if(scope===epoch)$('task-status').textContent=t('tasksFailed')}finally{if(scope===epoch){working=false;show()}}};
$('language').addEventListener('change',()=>queueMicrotask(show));
$('task-stop').onclick=()=>{clearReviewedStep();runner.cancel();working=false;$('task-consent').checked=false;show()};
$('task-export').onclick=()=>{if(report&&!working&&confirm(t('plain')))download(JSON.stringify(report,null,2),'nexus-task-report.json','application/json')};
window.NexusTasksUI=Object.freeze({clear,cancel,render:show,armReviewedStep,clearReviewedStep,hasTransientWork:()=>Boolean($('task-plan').value||report)});show();applyLanguage();
})();
