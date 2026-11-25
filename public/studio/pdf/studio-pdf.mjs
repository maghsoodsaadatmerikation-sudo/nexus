const $ = id => document.getElementById(id);
const input = $('studio-pdf-file');
const status = $('studio-pdf-status');
const ui = window.NexusStudioUI;
const gate = window.NexusMusicUI;
const MAX_FILE = 2 * 1024 * 1024;
const MAX_PAGES = 20;
const MAX_TEXT = 32000;
const words = (en, fa) => document.documentElement.lang === 'fa' ? fa : en;
let active = null;

function refresh() {
  const {busy, archived} = ui.uiStatus();
  const resourceBlocked = !gate || gate.audioBusy();
  input.disabled = Boolean(active || busy || archived || resourceBlocked);
  input.title = resourceBlocked && !active ? words('Finish the active local job or unload the local model first.', 'ابتدا پردازش محلی را پایان بده یا مدل محلی را از حافظه خارج کن.') : '';
  $('studio-pdf-label').textContent = words('Attach a PDF', 'پیوست PDF');
  $('studio-pdf-help').textContent = words(
    'Extracts selectable text from the first 20 pages locally. Maximum file size is 2 MiB.',
    'متن قابل انتخاب ۲۰ صفحهٔ اول را روی همین دستگاه استخراج می‌کند. حداکثر حجم فایل ۲ مگابایت است.'
  );
}

function cancel(clear = true) {
  const job = active;
  active = null;
  if (job) {
    clearTimeout(job.timer);
    job.abort();
    job.worker?.terminate();
  }
  if (clear) status.textContent = '';
  refresh();
}

function stillSelected(job) {
  const {projectId, threadId} = ui.selection();
  const {busy, archived} = ui.uiStatus();
  return active === job && projectId === job.projectId && threadId === job.threadId && !busy && !archived;
}

input.onchange = async () => {
  const [file] = input.files;
  input.value = '';
  if (!file || active || input.disabled) return;
  if (!/\.pdf$/i.test(file.name) || !file.size || file.size > MAX_FILE) {
    status.textContent = words('Choose a PDF up to 2 MiB.', 'یک PDF تا حجم ۲ مگابایت انتخاب کن.');
    return;
  }
  const release = gate?.acquireAudioJob();
  if (!release) return;
  const job = {...ui.selection(), worker: null};
  let initialSettled;
  const canceled = new Promise((_, reject) => { job.abort = () => reject(Error('pdf-cancelled')); });
  const wait = operation => Promise.race([operation, canceled]);
  active = job;
  job.timer = setTimeout(() => {
    if (active !== job) return;
    cancel(false);
    status.textContent = words('PDF extraction timed out.', 'مهلت استخراج متن PDF به پایان رسید.');
  }, 20000);
  refresh();
  status.textContent = words('Reading PDF locally…', 'در حال خواندن PDF روی دستگاه…');
  try {
    // Racing cancellation does not stop a browser file read or module import.
    // Keep the resource lease until both underlying promises settle.
    const operations = [Promise.resolve().then(() => file.arrayBuffer()),
      Promise.resolve().then(() => import('./pdf.min.mjs'))];
    initialSettled = Promise.allSettled(operations);
    const [bytes, pdf] = await wait(Promise.all(operations));
    if (!stillSelected(job)) return;
    job.worker = new Worker(new URL('./pdf.worker.min.mjs', import.meta.url), {type: 'module'});
    const worker = new pdf.PDFWorker({port: job.worker});
    const loading = pdf.getDocument({
      data: new Uint8Array(bytes), worker, stopAtErrors: true,
      isEvalSupported: false, enableScripting: false, enableXfa: false,
      disableFontFace: true, useSystemFonts: false, useWasm: false, useWorkerFetch: false
    });
    const doc = await wait(loading.promise);
    const pages = Math.min(MAX_PAGES, doc.numPages);
    let text = '';
    for (let i = 1; i <= pages && text.length < MAX_TEXT; i++) {
      const page = await wait(doc.getPage(i));
      const content = await wait(page.getTextContent());
      if (!stillSelected(job)) return;
      const passage = content.items.map(item => (item.str || '') + (item.hasEOL ? '\n' : ' ')).join('').trim();
      if (passage) text += ('Page ' + i + '\n' + passage + '\n\n').slice(0, MAX_TEXT - text.length);
      page.cleanup();
    }
    if (!stillSelected(job)) return;
    if (!text.trim()) {
      status.textContent = words('No selectable text found. Scans need text recognition first.',
        'متن قابل انتخابی پیدا نشد. فایل اسکن‌شده ابتدا به تشخیص متن نیاز دارد.');
      return;
    }
    const header = 'PDF text extract; up to ' + pages + ' of ' + doc.numPages + ' pages, capped at ' + MAX_TEXT + ' characters.\n\n';
    cancel(false);
    status.textContent = ui.stageChatContext(file.name.slice(0, 160), header + text) ?
      words('PDF excerpts are ready for review.', 'گزیده‌های PDF آمادهٔ بازبینی‌اند.') :
      words('Could not attach the excerpts. Check attachment capacity.', 'گزیده‌ها پیوست نشدند. ظرفیت پیوست را بررسی کن.');
  } catch {
    if (active === job) status.textContent = words(
      'Could not extract PDF text. Check that the file opens without a password.',
      'متن PDF استخراج نشد. بررسی کن که فایل بدون گذرواژه باز شود.'
    );
  } finally {
    if (active === job) cancel(false);
    job.worker?.terminate();
    if (initialSettled) await initialSettled;
    release();
    refresh();
  }
};
document.addEventListener('nexus-studio-state', () => {
  if (active && !stillSelected(active)) cancel();
  refresh();
});
document.addEventListener('nexus-audio-job-state', refresh);
document.addEventListener('nexus-studio-private-clear', () => cancel());
$('clear-chat-files').addEventListener('click', () => cancel());
window.addEventListener('pagehide', () => cancel());
refresh();
