/* NEXUS Studio: opt-out chat-first mobile navigation; presentation-only. */
(()=>{'use strict';
const $=id=>document.getElementById(id),media=matchMedia('(max-width:780px)');
const targets=[
  ['conversation-card','chat','Chat','گفتگو'],
  ['projects-card','projects','Projects','پروژه‌ها'],
  ['vault-card','save','Save','ذخیره']
];
const tools=[
  ['music-card','Music Lab','موسیقی'],
  ['orchestra-card','Orchestra & vocal','ارکستر و آواز'],
  ['data-card','Data analysis','تحلیل داده'],
  ['research-card','Research','پژوهش'],
  ['code-card','Code','کدنویسی'],
  ['tasks-card','Tasks','کارها'],
  ['chart-card','Charts','نمودارها'],
  ['canvas-card','Writing','نوشتن'],
  ['sources-card','Sources','منابع'],
  ['profile-card','Assistant & memory','دستیار و حافظه'],
  ['astrology-card','Astrology','اخترشناسی'],
  ['sky-card','Sky','آسمان']
];
const sections=[...targets.map(x=>x[0]),...tools.map(x=>x[0])];
if(sections.some(id=>!$(id))||!$('language')||!$('conversation-card'))return;
const main=document.querySelector('body>main');
const nav=document.createElement('nav');nav.id='studio-focus-nav';nav.setAttribute('aria-label','Primary Studio navigation');
const bar=document.createElement('div');bar.id='studio-focus-bar';
const toggle=document.createElement('button');toggle.id='studio-focus-toggle';toggle.type='button';toggle.className='secondary';
const top=document.createElement('div');top.id='studio-focus-top';top.append(toggle);
const toolsTray=document.createElement('div');toolsTray.id='studio-focus-tools';toolsTray.hidden=true;
toolsTray.setAttribute('role','group');toolsTray.setAttribute('aria-label','Studio tools');
const toolHeading=document.createElement('strong');toolHeading.id='studio-focus-tools-title';
const toolsGrid=document.createElement('div');toolsGrid.className='studio-focus-tools-grid';toolsTray.append(toolHeading,toolsGrid);
const onboarding=document.createElement('div');onboarding.id='studio-focus-onboarding';onboarding.className='studio-focus-onboarding';
onboarding.setAttribute('role','group');onboarding.setAttribute('aria-label','Getting started');
const hint=document.createElement('p'),start=document.createElement('button');start.type='button';onboarding.append(hint,start);
$('conversation-card').insertBefore(onboarding,$('conversation-card').children[1]||null);
const existingNav=document.querySelector('nav.tool-nav');existingNav.before(top,toolsTray);main.append(nav);
const labels=[
  ['conversation-card','Chat','گفتگو'],
  ['projects-card','Projects','پروژه‌ها'],
  ['tools','Tools','ابزارها'],
  ['vault-card','Save','ذخیره']
];
for(const [id,en,fa] of labels){
 const button=document.createElement('button');button.type='button';button.className='studio-focus-tab';
 button.dataset.panel=id;button.dataset.en=en;button.dataset.fa=fa;
 button.setAttribute('aria-controls',id==='tools'?'studio-focus-tools':id);
 button.addEventListener('click',()=>id==='tools'?openTools():openPanel(id));
 nav.append(button);
}
for(const [id,en,fa] of tools){
 const button=document.createElement('button');button.type='button';
 button.dataset.panel=id;button.dataset.en=en;button.dataset.fa=fa;
 button.setAttribute('aria-controls',id);
 button.addEventListener('click',()=>openPanel(id));toolsGrid.append(button);
}
let selected='conversation-card',focused=media.matches,manual=false,toolsOpen=false;
const isFa=()=>document.documentElement.lang==='fa';
const words=(en,fa)=>isFa()?fa:en;
function refreshLabels(){
 toggle.textContent=focused?words('Show all sections','نمایش همهٔ بخش‌ها'):words('Focus on one section','تمرکز بر یک بخش');
 toggle.setAttribute('aria-pressed',String(focused));
 nav.setAttribute('aria-label',words('Primary Studio navigation','ناوبری اصلی نکسوس'));
 toolsTray.setAttribute('aria-label',words('Studio tools','ابزارهای نکسوس'));
 onboarding.setAttribute('aria-label',words('Getting started','شروع کار'));
 toolHeading.textContent=words('Choose a tool','انتخاب ابزار');
 for(const button of [...nav.querySelectorAll('button'),...toolsGrid.querySelectorAll('button')])
  button.textContent=words(button.dataset.en,button.dataset.fa);
}
function layout(){
 document.documentElement.classList.toggle('studio-focus-mode',focused);
 nav.hidden=!focused;toolsTray.hidden=!focused||!toolsOpen;
 for(const id of sections)$(id).hidden=focused&&(toolsOpen||id!==selected);
 const category=toolsOpen||tools.some(x=>x[0]===selected)?'tools':selected;
 for(const button of nav.querySelectorAll('button')){
  const active=focused&&button.dataset.panel===category;
  button.setAttribute('aria-current',active?'page':'false');
 }
 for(const button of toolsGrid.querySelectorAll('button')){
  button.setAttribute('aria-current',focused&&!toolsOpen&&button.dataset.panel===selected?'page':'false');
 }
 refreshLabels();refreshOnboarding();syncTyping();requestAnimationFrame(syncTyping);
}
function moveTo(element){
 if(!focused)return;
 element.scrollIntoView({block:'start',behavior:'instant'});
}
function openPanel(id){
 if(!sections.includes(id))return false;
 if(!focused){const element=$(id);element.scrollIntoView({block:'start',behavior:'instant'});return true}
 selected=id;toolsOpen=false;layout();moveTo($(id));
 const heading=$(id).querySelector('h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true})}
 return true;
}
function openTools(){
 if(!focused){existingNav.scrollIntoView({block:'start',behavior:'instant'});return}
 toolsOpen=true;layout();moveTo(toolsTray);
 const first=toolsGrid.querySelector('button');first?.focus({preventScroll:true});
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
 const visible=focused&&(!projects.length||!hasThread);
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
$('language').addEventListener('change',()=>queueMicrotask(()=>{refreshLabels();refreshOnboarding()}));
document.addEventListener('nexus-studio-open-chat',()=>openPanel('conversation-card'));
document.addEventListener('keydown',event=>{
 if(event.key==='Escape'&&focused&&toolsOpen){event.preventDefault();openPanel('conversation-card')}
});
const textControls='input:not([type="checkbox"]):not([type="radio"]),textarea,select';
function syncTyping(){
 const active=document.activeElement;
 document.documentElement.classList.toggle('studio-focus-typing',Boolean(active?.matches?.(textControls)));
}
document.addEventListener('focusin',syncTyping);
document.addEventListener('focusout',()=>queueMicrotask(syncTyping));
window.NexusStudioFocus={openPanel,openTools,setFocus,isFocused:()=>focused,active:()=>toolsOpen?'tools':selected};
layout();
})();
