/* Speech goes to the browser's recognition service only after explicit opt-in. */
(() => {
'use strict';
const message = document.getElementById('message');
const actions = document.getElementById('nexus-zen-suggestions');
const button = (id) => {
  const element = document.createElement('button');
  element.id = id;
  element.type = 'button';
  element.className = 'secondary';
  return element;
};
const toggle = button('studio-voice-toggle');
toggle.dataset.en = 'Dictate';
toggle.dataset.fa = 'دیکته';
toggle.setAttribute('aria-expanded', 'false');
const panel = document.createElement('section');
panel.id = 'studio-voice-panel';
panel.hidden = true;
toggle.setAttribute('aria-controls', panel.id);
const note = document.createElement('p');
const status = document.createElement('p');
status.setAttribute('role', 'status');
const start = button('studio-voice-start');
const stop = button('studio-voice-stop');
const close = button('studio-voice-close');
panel.append(note, start, stop, close, status);
actions.after(panel);
actions.append(toggle);

const words = (en, fa) => document.documentElement.lang === 'fa' ? fa : en;
const recognition = () => window.SpeechRecognition || window.webkitSpeechRecognition;
const ui = window.NexusStudioUI;
let current = null;
let context = null;
function captureContext() {
  const {projectId, threadId} = ui.selection();
  return {projectId, threadId, draft: message.value, lang: document.documentElement.lang};
}
function contextStillOpen() {
  const now = captureContext();
  const state = ui.uiStatus();
  return context && now.projectId === context.projectId && now.threadId === context.threadId &&
    now.draft === context.draft && now.lang === context.lang && !state.busy && !state.archived;
}
function finish() {
  const session = current;
  current = null;
  if (session) clearTimeout(session.timer);
  start.disabled = !recognition();
  stop.hidden = true;
  stop.disabled = false;
  return session;
}
function hide() {
  const session = finish();
  context = null;
  status.textContent = '';
  panel.hidden = true;
  toggle.setAttribute('aria-expanded', 'false');
  try { session?.engine.abort(); } catch {}
}
function show() {
  const state = ui.uiStatus();
  if (state.busy || state.archived) return;
  context = captureContext();
  note.textContent = words(
    'Your browser may send microphone audio to its speech service. Review the text before sending it.',
    'مرورگر ممکن است صدای میکروفون را به سرویس تشخیص گفتار خود بفرستد. متن را پیش از ارسال بازبینی کن.');
  start.textContent = words('Allow microphone and start', 'اجازهٔ میکروفون و شروع');
  stop.textContent = words('Finish dictation', 'پایان دیکته');
  close.textContent = words('Close', 'بستن');
  finish();
  if (start.disabled) status.textContent = words('Dictation is unavailable in this browser.', 'دیکته در این مرورگر در دسترس نیست.');
  panel.hidden = false;
  toggle.setAttribute('aria-expanded', 'true');
  (start.disabled ? close : start).focus();
}
toggle.onclick = () => panel.hidden ? show() : hide();
close.onclick = () => { hide(); toggle.focus(); };
panel.addEventListener('keydown', event => {
  if (event.key === 'Escape') { event.preventDefault(); close.click(); }
});
start.onclick = () => {
  const Engine = recognition();
  if (!Engine || current || !contextStillOpen()) return;
  const separator = /\S$/.test(message.value) ? ' ' : '';
  const room = message.maxLength - message.value.length - separator.length;
  if (room <= 0) {
    status.textContent = words('The message is full.', 'کادر پیام پر است.');
    return;
  }
  const fail = (session) => {
    if (current !== session) return;
    finish();
    status.textContent = words('Dictation stopped. Check microphone permission and speech service availability.',
      'دیکته متوقف شد. مجوز میکروفون و دسترسی به سرویس گفتار را بررسی کن.');
    try { session.engine.abort(); } catch {}
  };
  let engine;
  try { engine = new Engine(); } catch {
    status.textContent = words('The speech service is unavailable.', 'سرویس گفتار در دسترس نیست.');
    return;
  }
  const session = {engine, text:'', timer:null};
  current = session;
  engine.lang = document.documentElement.lang === 'fa' ? 'fa-IR' : document.documentElement.lang;
  engine.continuous = true;
  engine.interimResults = false;
  engine.onstart = () => {
    if (current === session && contextStillOpen()) return;
    if (current === session) hide();
    else {
      try { engine.abort(); } catch {}
    }
  };
  engine.onresult = ({resultIndex, results}) => {
    if (current !== session || !contextStillOpen()) return;
    for (let i = resultIndex; i < results.length && session.text.length < room; i += 1) {
      const text = results[i].isFinal ? results[i][0]?.transcript?.trim() : '';
      if (text) session.text = [session.text, text].filter(Boolean).join(' ').slice(0, room);
    }
  };
  engine.onerror = () => fail(session);
  engine.onend = () => {
    if (current !== session) return;
    if (!contextStillOpen()) { hide(); return; }
    finish();
    // The textarea limit counts UTF-16 code units. Drop a trailing half-surrogate.
    const text = session.text.replace(/[\uD800-\uDBFF]$/, '');
    if (!text) {
      status.textContent = words('No speech was transcribed.', 'گفتاری به متن تبدیل نشد.');
      return;
    }
    message.value += separator + text;
    hide();
    message.dispatchEvent(new Event('input', {bubbles:true}));
    message.focus();
  };
  start.disabled = true;
  stop.hidden = false;
  status.textContent = words('Listening…', 'در حال شنیدن…');
  session.timer = setTimeout(() => stop.click(), 45000);
  try { engine.start(); } catch { fail(session); }
};
stop.onclick = () => {
  const session = current;
  if (!session) return;
  clearTimeout(session.timer);
  stop.disabled = true;
  session.timer = setTimeout(hide, 3000);
  try { session.engine.stop(); } catch { hide(); }
};
for (const event of ['nexus-studio-private-clear', 'nexus-studio-chat-layout', 'nexus-studio-open-chat']) {
  document.addEventListener(event, hide);
}
const cancelStale = () => { if (!panel.hidden && !contextStillOpen()) hide(); };
message.addEventListener('input', cancelStale);
document.addEventListener('nexus-studio-state', cancelStale);
document.getElementById('language').addEventListener('change', hide);
document.addEventListener('visibilitychange', () => { if (document.hidden) hide(); });
window.addEventListener('pagehide', hide);
toggle.textContent = words(toggle.dataset.en, toggle.dataset.fa);
})();
