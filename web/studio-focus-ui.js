/* NEXUS Studio: opt-out chat-first mobile navigation; presentation-only. */
(()=>{'use strict';
const $=id=>document.getElementById(id),media=matchMedia('(max-width:780px)');
const targets=[
  ['conversation-card','chat','Chat','گفتگو'],
  ['projects-card','projects','Projects','پروژه‌ها'],
  ['vault-card','save','Save','ذخیره']
];
const tools=[
  ['canvas-card','Writing','نوشتن','¶','Draft and revisit versions','پیش‌نویس و بازبینی نسخه‌ها'],
  ['research-card','Research','پژوهش','⌕','Look up public sources','جست‌وجوی منابع عمومی'],
  ['music-card','Music Lab','موسیقی','♪','Compose and export WAV or MIDI','آهنگ‌سازی و خروجی WAV یا MIDI'],
  ['orchestra-card','Orchestra & vocal','ارکستر و آواز','♫','Arrange and mix your vocal','تنظیم ارکستر و میکس وکال'],
  ['data-card','Data analysis','تحلیل داده','∑','Summarize CSV and JSON','خلاصه‌سازی CSV و JSON'],
  ['chart-card','Charts','نمودارها','▥','Draw charts and export PNG','رسم نمودار و خروجی PNG'],
  ['sources-card','Sources','منابع','▤','Find text in your files','یافتن متن در فایل‌های پروژه'],
  ['profile-card','Assistant & memory','دستیار و حافظه','◎','Set project preferences','تنظیم ترجیحات پروژه'],
  ['code-card','Code','کدنویسی','‹›','Run reviewed JavaScript','اجرای JavaScript بازبینی‌شده'],
  ['tasks-card','Tasks','کارها','▦','Run a reviewed task plan','اجرای برنامهٔ بازبینی‌شدهٔ کارها'],
  ['astrology-card','Astrology','اخترشناسی','✧','Explore charts and transits','بررسی چارت و گذرها'],
  ['sky-card','Sky','آسمان','◐','Inspect local sky calculations','بررسی محاسبات آسمان']
];
const sections=[...targets.map(x=>x[0]),...tools.map(x=>x[0])];
if(sections.some(id=>!$(id))||!$('language')||!$('conversation-card'))return;
const main=document.querySelector('body>main');
const nav=document.createElement('nav');nav.id='studio-focus-nav';nav.setAttribute('aria-label','Primary Studio navigation');
const toggle=document.createElement('button');toggle.id='studio-focus-toggle';toggle.type='button';toggle.className='secondary';
const catalog=document.createElement('button');catalog.id='studio-tools-toggle';catalog.type='button';
catalog.setAttribute('aria-controls','studio-focus-tools');
const top=document.createElement('div');top.id='studio-focus-top';top.append(catalog,toggle);
const toolsTray=document.createElement('div');toolsTray.id='studio-focus-tools';toolsTray.hidden=true;
toolsTray.setAttribute('role','group');toolsTray.setAttribute('aria-label','Studio tools');
const toolHeading=document.createElement('h2');toolHeading.id='studio-focus-tools-title';
const search=document.createElement('input');search.id='studio-tool-search';search.type='search';
const noTools=document.createElement('p');noTools.className='help';noTools.hidden=true;noTools.setAttribute('role','status');
const toolsGrid=document.createElement('div');toolsGrid.className='studio-focus-tools-grid';
toolsTray.append(toolHeading,search,toolsGrid,noTools);
const onboarding=document.createElement('div');onboarding.id='studio-focus-onboarding';onboarding.className='studio-focus-onboarding';
onboarding.setAttribute('role','group');onboarding.setAttribute('aria-label','Getting started');
const hint=document.createElement('p'),start=document.createElement('button');start.type='button';
const tryTools=document.createElement('button');tryTools.type='button';tryTools.className='secondary';
onboarding.append(hint,start,tryTools);
$('conversation-card').insertBefore(onboarding,$('conversation-card').children[1]||null);
const existingNav=document.querySelector('nav.tool-nav');existingNav.before(top,toolsTray);main.append(nav);
document.documentElement.classList.add('studio-enhanced');
const labels=[
  ['conversation-card','Chat','گفتگو','◫'],
  ['projects-card','Projects','پروژه‌ها','▤'],
  ['tools','Tools','ابزارها','▦'],
  ['vault-card','Save','ذخیره','◇']
];
const labelsToRefresh=[];
function labelButton(button,icon,en,fa,descriptionEn='',descriptionFa=''){
 const symbol=document.createElement('span');symbol.className='studio-control-icon';symbol.textContent=icon;
 symbol.setAttribute('aria-hidden','true');
 const label=document.createElement('span');label.className='studio-control-label';
 const title=document.createElement('span');label.append(title);
 const detail=document.createElement('small');
 if(descriptionEn)label.append(detail);
 button.append(symbol,label);
 labelsToRefresh.push(()=>{title.textContent=words(en,fa);detail.textContent=words(descriptionEn,descriptionFa)});
}
for(const [id,en,fa,icon] of labels){
 const button=document.createElement('button');button.type='button';button.className='studio-focus-tab';
 button.dataset.panel=id;
 labelButton(button,icon,en,fa);
 button.setAttribute('aria-controls',id==='tools'?'studio-focus-tools':id);
 button.addEventListener('click',()=>id==='tools'?openTools():openPanel(id));
 nav.append(button);
}
for(const [id,en,fa,icon,descriptionEn,descriptionFa] of tools){
 const button=document.createElement('button');button.type='button';
 button.dataset.panel=id;
 labelButton(button,icon,en,fa,descriptionEn,descriptionFa);
 labelsToRefresh.push(()=>button.setAttribute('aria-label',words(en,fa)));
 button.setAttribute('aria-controls',id);
 button.addEventListener('click',()=>openPanel(id));toolsGrid.append(button);
}
let selected='conversation-card',focused=media.matches,manual=false,toolsOpen=false;
const words=window.NexusStudioUI.words;
const normalize=value=>value.toLocaleLowerCase(document.documentElement.lang).replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/\u200c/g,' ').trim();
function filterTools(){
 const query=normalize(search.value).split(/\s+/).filter(Boolean);
 let results=0;
 for(const [index,tool] of tools.entries()){
  const text=normalize([...tool.slice(1,3),...tool.slice(4),words(tool[1],tool[2]),words(tool[4],tool[5])].join(' '));
  const visible=query.every(word=>text.includes(word));
  toolsGrid.children[index].hidden=!visible;
  if(visible)results++;
 }
 noTools.hidden=results!==0;
}
function refreshLabels(){
 toggle.textContent=focused?words('Show all sections','نمایش همهٔ بخش‌ها'):words('Focus on one section','تمرکز بر یک بخش');
 toggle.setAttribute('aria-pressed',String(focused));
 nav.setAttribute('aria-label',words('Primary Studio navigation','ناوبری اصلی نکسوس'));
 toolsTray.setAttribute('aria-label',words('Studio tools','ابزارهای نکسوس'));
 onboarding.setAttribute('aria-label',words('Getting started','شروع کار'));
 toolHeading.textContent=words('Choose a tool','انتخاب ابزار');
 catalog.textContent=toolsOpen?words('Close tools','بستن ابزارها'):words('Browse tools','دیدن ابزارها');
 catalog.setAttribute('aria-expanded',String(toolsOpen));
 search.placeholder=words('Search tools','جست‌وجوی ابزار');
 search.setAttribute('aria-label',search.placeholder);
 noTools.textContent=words('No tools match your search.','ابزاری با این جست‌وجو پیدا نشد.');
 tryTools.textContent=words('Browse tools','دیدن ابزارها');
 labelsToRefresh.forEach(update=>update());
}
function layout(){
 document.documentElement.classList.toggle('studio-focus-mode',focused);
 nav.hidden=!focused;toolsTray.hidden=!toolsOpen;
 for(const id of sections)$(id).hidden=focused&&(toolsOpen||id!==selected);
 const category=toolsOpen||tools.some(x=>x[0]===selected)?'tools':selected;
 for(const button of nav.querySelectorAll('button')){
  const active=focused&&button.dataset.panel===category;
  button.setAttribute('aria-current',active?'page':'false');
 }
 refreshLabels();refreshOnboarding();syncTyping();requestAnimationFrame(syncTyping);
}
function moveTo(element){
 if(!focused)return;
 element.scrollIntoView({block:'start',behavior:'instant'});
}
function openPanel(id){
 if(!sections.includes(id))return false;
 selected=id;toolsOpen=false;layout();$(id).scrollIntoView({block:'start',behavior:'instant'});
 const heading=$(id).querySelector('h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true})}
 return true;
}
function openTools(){
 if(!toolsOpen){search.value='';filterTools()}
 toolsOpen=true;layout();toolsTray.scrollIntoView({block:'start',behavior:'instant'});
 toolHeading.tabIndex=-1;toolHeading.focus({preventScroll:true});
}
function setFocus(on,explicit=false){
 if(explicit)manual=true;
 focused=Boolean(on);if(!focused)toolsOpen=false;
 layout();
 if(focused)moveTo(toolsOpen?toolsTray:$(selected));
}
function refreshOnboarding(){
 let state=null;try{state=window.NexusStudioUI?.snapshot()}catch{}
 const projects=state?.projects||[];
 const selectedProject=projects.find(p=>p.id===$('projects').value);
 const hasThread=selectedProject?.threads?.some(t=>!t.archived);
 const visible=!projects.length||!hasThread;
 onboarding.hidden=!visible;
 if(!visible)return;
 const create=projects.length===0;
 hint.textContent=create
  ?words('Step 1 of 2: Create a project. Your work stays in this tab until you explicitly save it to an encrypted archive.',
         'گام ۱ از ۲: یک پروژه بساز. کارها تا زمانی که صریحاً در آرشیو رمزگذاری‌شده ذخیره نشوند، فقط در همین برگه‌اند.')
  :words('Step 2 of 2: Start a conversation. The local reflection guide is not a generative AI model.',
         'گام ۲ از ۲: یک گفتگو آغاز کن. راهنمای محلی مدل هوش مصنوعی مولد نیست.');
 start.textContent=create?words('Create a project','ساخت پروژه'):words('New conversation','گفتگوی جدید');
 start.onclick=()=>{
  if(create){openPanel('projects-card');$('project-title').focus({preventScroll:true})}
  else{if($('new-thread').disabled)return;$('new-thread').click();openPanel('conversation-card');$('message').focus({preventScroll:true})}
 };
}
toggle.addEventListener('click',()=>setFocus(!focused,true));
catalog.addEventListener('click',()=>toolsOpen?openPanel(selected):openTools());
tryTools.addEventListener('click',openTools);
search.addEventListener('input',filterTools);
media.addEventListener('change',()=>{if(!manual)setFocus(media.matches)});
existingNav.addEventListener('click',event=>{
 if(!focused)return;
 const anchor=event.target.closest('a[href^="#"]');
 if(!anchor||!existingNav.contains(anchor))return;
 const id=anchor.getAttribute('href').slice(1);
 if(sections.includes(id)){event.preventDefault();openPanel(id)}
});
const observer=new MutationObserver(()=>refreshOnboarding());
observer.observe($('projects'),{childList:true});
observer.observe($('history'),{childList:true});
document.addEventListener('nexus-studio-language',()=>queueMicrotask(()=>{refreshLabels();refreshOnboarding();filterTools()}));
document.addEventListener('nexus-studio-open-chat',()=>openPanel('conversation-card'));
document.addEventListener('keydown',event=>{
 if(event.key!=='Escape'||!toolsOpen||!toolsTray.contains(document.activeElement))return;
 event.preventDefault();
 if(search.value){search.value='';filterTools();return}
 openPanel(selected);
});
function openLinkedPanel(){if(location.hash)openPanel(location.hash.slice(1))}
window.addEventListener('hashchange',openLinkedPanel);
const textControls='input:not([type="checkbox"]):not([type="radio"]),textarea,select';
function syncTyping(){
 const active=document.activeElement;
 document.documentElement.classList.toggle('studio-focus-typing',Boolean(active?.matches?.(textControls)));
}
document.addEventListener('focusin',syncTyping);
document.addEventListener('focusout',()=>queueMicrotask(syncTyping));
window.NexusStudioFocus={openPanel,openTools,setFocus,isFocused:()=>focused,active:()=>toolsOpen?'tools':selected};
layout();
openLinkedPanel();
})();
