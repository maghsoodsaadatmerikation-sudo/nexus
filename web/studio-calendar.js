/* Local iCalendar export for explicitly reviewed reminder fields. */
(() => {
'use strict';
const encoder = new TextEncoder();
const frequencies = {daily:'DAILY', weekly:'WEEKLY'};
const escapeText = value => value.replace(/\\/g, '\\\\').replace(/\r\n?|\n/g, '\\n')
  .replace(/([,;])/g, '\\$1');

function fold(line) {
  let result = '', length = 0;
  for (const character of line) {
    const size = encoder.encode(character).length;
    if (length + size > 75) {
      result += '\r\n ';
      length = 1;
    }
    result += character;
    length += size;
  }
  return result;
}

function calendarFile({title, start, repeat, advance}, {uid = crypto.randomUUID(), now = new Date()} = {}) {
  const text = title.trim();
  if (!text || text.length > 160 || /[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/.test(text) ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(start) ||
      !['once', 'daily', 'weekly'].includes(repeat) ||
      !['0', '5', '15', '60'].includes(advance)) throw Error('invalid-reminder');
  // Validate in UTC without adopting the browser time zone. DTSTART below is
  // deliberately a floating date-time, preserving the selected clock time.
  const checked = new Date(start + ':00Z');
  if (!Number.isFinite(checked.getTime()) || checked.toISOString().slice(0, 16) !== start ||
      start.startsWith('0000')) throw Error('invalid-reminder');
  const compact = value => value.replace(/[-:]/g, '');
  const summary = escapeText(text);
  const lines = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//NEXUS Studio//Calendar reminders//EN',
    'BEGIN:VEVENT', 'UID:' + uid + '@nexus-studio', 'DTSTAMP:' + compact(now.toISOString().slice(0, 19)) + 'Z',
    'DTSTART:' + compact(start) + '00', 'DURATION:PT5M', 'TRANSP:TRANSPARENT', 'SUMMARY:' + summary
  ];
  if (repeat !== 'once') lines.push('RRULE:FREQ=' + frequencies[repeat]);
  lines.push('BEGIN:VALARM', 'ACTION:DISPLAY', 'TRIGGER:' + (advance === '0' ? 'PT0S' : '-PT' + advance + 'M'),
    'DESCRIPTION:' + summary, 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR');
  return lines.map(fold).join('\r\n') + '\r\n';
}

const api = {calendarFile};
if (typeof document !== 'undefined') {
  const form = $('reminder-form');
  const status = $('reminder-status');
  let lastExport = '';
  const values = () => ({
    title:$('reminder-title').value, start:$('reminder-start').value,
    repeat:$('reminder-repeat').value, advance:$('reminder-advance').value
  });
  Object.assign(api, {
    clear() { form.reset(); lastExport = ''; status.textContent = ''; },
    hasTransientWork() {
      const draft = values();
      return Boolean((draft.title || draft.start) && JSON.stringify(draft) !== lastExport);
    }
  });
  form.oninput = () => { status.textContent = ''; };
  form.onsubmit = event => {
    event.preventDefault();
    const draft = values();
    try {
      const calendar = calendarFile(draft);
      download(calendar, 'nexus-reminder.ics', 'text/calendar;charset=utf-8');
      lastExport = JSON.stringify(draft);
      status.textContent = t('reminderDownloaded');
      renderStorage();
    } catch {
      status.textContent = t('reminderInvalid');
    }
  };
}
globalThis.NexusCalendar = Object.freeze(api);
})();
