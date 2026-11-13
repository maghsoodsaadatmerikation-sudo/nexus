import {DeviceEngine,inspectReadiness} from './device-engine.js';
const $=id=>document.getElementById(id),text=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const engine=new DeviceEngine({workerURL:new URL('./device-worker.js',import.meta.url),onStatus:data=>{
 if(data.type==='phase')$('device-state').textContent=text('Loading local runtime: ','بارگذاری موتور محلی: ')+data.stage;
 else if(data.type==='download')$('device-state').textContent=text('Downloading public model file: ','دانلود فایل عمومی مدل: ')+data.file+' · '+Math.round(data.loaded/1048576)+' / '+Math.ceil(data.total/1048576)+' MiB';
 else if(data.type==='ready')$('device-state').textContent=text('Small model ready on this device. English drafts; limited accuracy.','مدل کوچک روی دستگاه آماده است؛ پیش‌نویس انگلیسی با دقت محدود.');
 else if(data.type==='generating')$('device-state').textContent=text('Generating locally. Stop terminates the Worker.','تولید روی دستگاه؛ توقف، پردازش مدل را قطع می‌کند.');
 else if(data.type==='error')$('device-state').textContent=data.code==='context-too-large'?text('Context exceeds the small model limit. Shorten it manually, then prepare again.','ورودی از ظرفیت مدل کوچک بیشتر است؛ آن را دستی کوتاه کن و دوباره آماده کن.'):text('Local generation failed. Try again or unload the model.','تولید محلی انجام نشد؛ دوباره تلاش کن یا مدل را از حافظه خارج کن.');
 else if(data.type==='idle')$('device-state').textContent=data.reason&&data.reason!=='cancelled'?recovery(data.reason):text('Model is unloaded. Conversations were retained.','مدل از حافظه خارج است؛ گفت‌وگوها حفظ شدند.');
 $('device-load').disabled=engine.state!=='idle';
}});
window.NexusDevice=engine;
let previous={mode:$('model-mode').value,budget:$('model-budget').value};
$('model-engine').onchange=()=>{
 window.NexusStudioUI.resetModel();const local=$('model-engine').value==='device';
 if(local){previous={mode:$('model-mode').value,budget:$('model-budget').value};$('model-mode').value='standard';$('model-budget').value='64';$('model-budget').max='64'}
 else{$('model-mode').value=previous.mode;$('model-budget').value=previous.budget;$('model-budget').max='8192'}
 $('model-mode').disabled=local;
};
$('device-load').onclick=async()=>{
 if(!$('device-consent').checked){$('device-state').textContent=text('Choose the download consent first.','ابتدا اجازهٔ دانلود را انتخاب کن.');return}
 window.NexusStudioUI.resetModel();$('device-load').disabled=true;$('device-state').textContent=text('Loading verified public model files…','بارگذاری فایل‌های عمومیِ بررسی‌شدهٔ مدل…');
 try{await engine.load({consent:true})}catch(error){$('device-state').textContent=recovery(error.message)}finally{$('device-load').disabled=engine.state!=='idle'}
};
$('device-consent').onchange=()=>{if(!$('device-consent').checked){engine.unload();window.NexusStudioUI.resetModel()}};
$('device-unload').onclick=()=>{engine.unload();window.NexusStudioUI.resetModel()};
$('device-erase').onclick=async()=>{try{await engine.erase();window.NexusStudioUI.resetModel();$('device-state').textContent=text('Downloaded model/runtime cache removed. Conversations and encrypted archives were retained.','کش مدل و موتور اجرا حذف شد؛ گفت‌وگوها و آرشیوهای رمزگذاری‌شده حفظ شدند.')}catch{$('device-state').textContent=text('Model cache could not be removed.','کش مدل حذف نشد.')}};

const issues={
 'memory-unknown':['Memory estimate unavailable','برآورد رم در دسترس نیست'],
 'storage-unknown':['Storage estimate unavailable','برآورد فضای ذخیره‌سازی در دسترس نیست'],
 'storage-low':['Storage headroom is low; free space or erase unused model files','فضای ذخیره‌سازی کم است؛ فضا آزاد کن یا فایل‌های مدل بلااستفاده را حذف کن'],
 'insufficient-device-memory':['Reported device memory is below 4 GB','رم گزارش‌شده کمتر از ۴ گیگابایت است'],
 'missing-secure':['Open the HTTPS site','سایت HTTPS را باز کن'],
 'missing-worker':['Worker support is unavailable','پشتیبانی Worker در دسترس نیست'],
 'missing-wasm':['WebAssembly support is unavailable','WebAssembly در دسترس نیست'],
 'missing-cache':['Browser cache support is unavailable','کش مرورگر در دسترس نیست'],
 'missing-crypto':['Browser cryptography is unavailable','رمزنگاری مرورگر در دسترس نیست']
};
$('device-check').onclick=async()=>{
 $('device-check').disabled=true;
 try{const report=await inspectReadiness(167471893),lines=[text('Readiness: ','آمادگی: ')+report.status];
 if(report.memory_gib!==null)lines.push(text('Reported RAM (approximate): ','رم گزارش‌شده — تقریبی: ')+report.memory_gib+' GiB');
 if(report.storage_available_bytes!==null)lines.push(text('Estimated available storage: ','فضای ذخیره‌سازی تخمینی: ')+Math.floor(report.storage_available_bytes/1048576)+' MiB');
 lines.push(text('Suggested storage headroom: ','فضای ذخیره‌سازی پیشنهادی: ')+Math.ceil(report.storage_headroom_bytes/1048576)+' MiB');
 for(const issue of report.issues){const label=issues[issue];if(label)lines.push(text(...label))}
 lines.push(text('Actual model execution has not been verified by this check.','این بررسی اجرای واقعی مدل را تأیید نمی‌کند.'));$('device-readiness').textContent=lines.join('\n');
 }catch{$('device-readiness').textContent=text('Readiness could not be checked.','بررسی آمادگی انجام نشد.')}finally{$('device-check').disabled=false}
};
$('device-report').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(engine.report(),null,2)+'\n'],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download='nexus-device-runtime-report.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};

function recovery(code){const messages={
 'generation-timeout':['Generation timed out and the model was stopped. Shorten the request and reload.','مهلت تولید تمام شد و مدل متوقف شد؛ درخواست را کوتاه و مدل را دوباره بارگذاری کن.'],
 'worker-start-failed':['The model process could not start. Check browser permissions and retry.','پردازش مدل شروع نشد؛ مجوزهای مرورگر را بررسی و دوباره تلاش کن.'],
 'worker-send-failed':['The request could not reach the local model. Reload the model and prepare the request again.','درخواست به مدل محلی نرسید؛ مدل را دوباره بارگذاری و درخواست را دوباره آماده کن.'],
 'worker-message-failed':['Local model communication failed and the model was stopped. Reload and retry.','ارتباط با مدل محلی ناموفق بود و مدل متوقف شد؛ دوباره بارگذاری و تلاش کن.'],
 'worker-failed':['The model process stopped unexpectedly. Unload and retry; check memory.','پردازش مدل ناگهان متوقف شد؛ مدل را خارج و دوباره بارگذاری کن و رم را بررسی کن.'],
 'load-timeout':['Loading timed out. Reconnect and retry; complete verified files can be reused.','مهلت بارگذاری تمام شد؛ اتصال را بررسی و دوباره تلاش کن. فایل‌های کامل بررسی‌شده قابل استفادهٔ مجددند.'],
 'insufficient-device-memory':['Reported memory is below 4 GB; use another device or the local guide.','رم گزارش‌شده کمتر از ۴ گیگابایت است؛ از دستگاه دیگر یا راهنمای محلی استفاده کن.'],
 'unsupported-device':['Use a secure browser supporting Worker, WASM, cache and cryptography.','از مرورگر امن با پشتیبانی Worker، WASM، کش و رمزنگاری استفاده کن.'],
 'cancelled':['Loading was cancelled. Conversations were retained.','بارگذاری لغو شد؛ گفت‌وگوها حفظ شدند.']};return text(...(messages[code]||['Model unavailable. Check network, storage and memory, then retry.','مدل در دسترس نیست؛ اتصال، فضای ذخیره‌سازی و رم را بررسی و دوباره تلاش کن.']))}
