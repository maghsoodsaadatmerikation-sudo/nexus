/* Read completed answers through the browser's local voice service. */
(() => {
'use strict';
const words = (en, fa) => document.documentElement.lang === 'fa' ? fa : en;
const panel = document.createElement('section');
panel.id = 'studio-playback';
panel.className = 'message assistant';
panel.hidden = true;
const label = document.createElement('label');
const voiceLabel = document.createElement('span');
const voices = document.createElement('select');
voices.id = 'studio-playback-voice';
label.append(voiceLabel, voices);
const makeButton = id => {
 const control = document.createElement('button');
 control.id = id;
 control.type = 'button';
 control.className = 'secondary';
 return control;
};
const pause = makeButton('studio-playback-pause');
const close = makeButton('studio-playback-stop');
const status = document.createElement('p');
status.id = 'studio-playback-status';
status.setAttribute('role', 'status');
panel.append(label, pause, close, status);
document.getElementById('messages').after(panel);

let current = null, trigger = null;
function split(text) {
 const parts = [];
 for (let offset = 0; offset < text.length;) {
  let end = Math.min(offset + 240, text.length);
  if (end < text.length) {
   const separator = text.slice(offset, end).search(/\s+\S*$/);
   if (separator >= 120) end = offset + separator + 1;
   else if (/[\uD800-\uDBFF]/.test(text[end - 1])) end--;
  }
  const part = text.slice(offset, end);
  if (part.trim()) parts.push(part);
  offset = end;
 }
 return parts;
}

function stop(restoreFocus = false) {
 if (panel.hidden && !current) return;
 const session = current;
 const origin = trigger;
 current = null;
 trigger = null;
 panel.hidden = true;
 status.textContent = '';
 voices.replaceChildren();
 try { session?.engine.cancel(); } catch {}
 if (restoreFocus && origin?.isConnected) origin.focus({preventScroll:true});
}
function update(session, message) {
 pause.disabled = !(session?.utterance || session?.paused);
 voices.disabled = !session?.choices.length;
 label.hidden = !session?.choices.length;
 pause.textContent = session?.paused ? words('Resume', 'ادامهٔ پخش') : words('Pause', 'مکث');
 status.textContent = message;
}
function failed(session) {
 if (current !== session) return;
 session.utterance = null;
 session.paused = false;
 try { session.engine.cancel(); } catch {}
 update(session, words('Playback stopped. Choose a local voice or try again.', 'پخش متوقف شد. صدای محلی دیگری انتخاب کن یا دوباره تلاش کن.'));
}
function next(session) {
 if (current !== session || session.paused) return;
 if (session.index === session.parts.length) {
  session.utterance = null;
  update(session, words('Finished reading.', 'خواندن پاسخ تمام شد.'));
  return;
 }
 try {
  const voice = session.choices[Number(voices.value)];
  if (voice?.localService !== true) throw Error('local-voice-unavailable');
  const utterance = new window.SpeechSynthesisUtterance(session.parts[session.index]);
  utterance.voice = voice;
  utterance.lang = voice.lang;
  session.utterance = utterance;
  utterance.onend = () => {
   if (current !== session || session.utterance !== utterance) return;
   session.utterance = null;
   session.index++;
   next(session);
  };
  utterance.onerror = () => { if (session.utterance === utterance) failed(session); };
  update(session, words('Reading', 'در حال خواندن')+' · '+(session.index + 1)+'/'+session.parts.length);
  session.engine.speak(utterance);
 } catch { failed(session); }
}
function start(text, origin) {
 stop();
 trigger = origin;
 panel.hidden = false;
 panel.setAttribute('aria-label', words('Answer playback', 'پخش پاسخ'));
 voiceLabel.textContent = words('Local voice', 'صدای محلی');
 close.textContent = words('Stop', 'توقف');
 const engine = window.speechSynthesis;
 let choices = [];
 try { choices = engine?.getVoices().filter(voice => voice.localService === true).slice(0, 100) || []; } catch {}
 const parts = split(text);
 if (!choices.length || !parts.length || typeof window.SpeechSynthesisUtterance !== 'function') {
  update(null, words('No local playback voice is available.', 'صدای محلی برای پخش در دسترس نیست.'));
  panel.scrollIntoView({block:'nearest'});
  close.focus({preventScroll:true});
  return;
 }
 document.dispatchEvent(new Event('nexus-studio-playback-start'));
 const preferred = document.documentElement.lang.toLowerCase().split('-')[0];
 const match = choices.findIndex(voice => voice.lang.toLowerCase().split('-')[0] === preferred);
 choices.forEach((voice, index) => {
  const option = document.createElement('option');
  option.value = String(index);
  option.textContent = voice.name + ' · ' + voice.lang;
  voices.append(option);
 });
 voices.value = String(Math.max(0, match));
 const session = {engine, choices, parts, index:0, paused:false, utterance:null};
 current = session;
 try { if(engine.paused)engine.resume(); next(session); } catch { failed(session); }
 panel.scrollIntoView({block:'nearest'});
 (pause.disabled ? close : pause).focus({preventScroll:true});
}
pause.onclick = () => {
 const session = current;
 if (!session) return;
 try {
  if (session.paused) {
   session.paused = false;
   session.engine.resume();
   if (!session.utterance) next(session);
   else update(session, words('Reading', 'در حال خواندن')+' · '+(session.index + 1)+'/'+session.parts.length);
  } else {
   session.paused = true;
   session.engine.pause();
   update(session, words('Paused.', 'پخش متوقف موقت است.'));
  }
 } catch { failed(session); }
};
voices.onchange = () => {
 const session = current;
 if (!session) return;
 session.utterance = null;
 session.paused = false;
 session.index = 0;
 try {
  session.engine.cancel();
  if(session.engine.paused)session.engine.resume();
  next(session);
 } catch { failed(session); }
};
close.onclick = () => stop(true);
window.addEventListener('pagehide', () => stop());
document.addEventListener('visibilitychange', () => { if(document.hidden)stop(); });
globalThis.NexusSpeechPlayback = Object.freeze({start, stop});
})();
