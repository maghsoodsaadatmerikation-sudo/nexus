/* A text-only Markdown subset for finished model replies. */
(() => {
'use strict';

function inline(parent, text) {
 const doc = parent.ownerDocument;
 const tokens = /(<[^<>\n]*>)|\\([\\*`\[\]|])|(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(!?)\[([^\[\]\n]{1,500})\]\(([^\s()<>]{1,2048})\)/g;
 let offset = 0;
 for (const match of text.matchAll(tokens)) {
  parent.append(text.slice(offset, match.index));
  const [original, tag, escaped, code, bold, emphasis, image, label, destination] = match;
  let node = null;
  if (code || bold || emphasis) {
   node = doc.createElement(code ? 'code' : bold ? 'strong' : 'em');
   const value = code || bold || emphasis;
   const delimiter = bold ? 2 : 1;
   node.textContent = value.slice(delimiter, -delimiter);
  } else if (!tag && !escaped && image === '') {
   try {
    const url = new URL(destination);
    if (url.protocol === 'https:' && !url.username && !url.password) {
     node = doc.createElement('a');
     node.href = url.href;
     node.target = '_blank';
     node.rel = 'noopener noreferrer';
     node.textContent = label;
    }
   } catch { /* Unsupported destinations remain literal text. */ }
  }
  parent.append(node || escaped || original);
  offset = match.index + original.length;
 }
 parent.append(text.slice(offset));
}

const fence = /^ {0,3}(`{3,}|~{3,})([^\n]*)$/;
const heading = /^ {0,3}(#{1,6})\s+(.+)$/;
const item = /^ {0,3}([-+*]|\d{1,9}[.)])\s+(.+)$/;
const quote = /^ {0,3}> ?(.*)$/;

function cells(line) {
 if (!line?.includes('|')) return [];
 return line.trim().replace(/^\||(?<!\\)\|$/g, '').split(/(?<!\\)\|/).map(cell => cell.trim());
}

function tableWidth(lines, row) {
 const width = cells(lines[row]).length;
 const rule = cells(lines[row + 1]);
 return width >= 2 && width <= 12 && width === rule.length &&
  rule.every(cell => /^:?-{3,}:?$/.test(cell)) ? width : 0;
}

function render(container, text) {
 const doc = container.ownerDocument;
 const lines = text.split(/\r\n?|\n/);
 if (lines.length > 800) {
  container.textContent = text;
  return;
 }
 container.classList.add('reply-format');
 const append = (tag, content) => {
  const node = doc.createElement(tag);
  inline(node, content);
  container.append(node);
 };
 let row = 0;
 while (row < lines.length) {
  const line = lines[row];
  if (!line.trim()) { row++; continue; }
  const opened = fence.exec(line);
  if (opened) {
   const marker = opened[1], content = [];
   row++;
   while (row < lines.length) {
    const close = fence.exec(lines[row]);
    if (close?.[1][0] === marker[0] && close[1].length >= marker.length && !close[2].trim()) {
     row++;
     break;
    }
    content.push(lines[row++]);
   }
   const pre = doc.createElement('pre');
   pre.tabIndex = 0;
   const code = doc.createElement('code');
   code.textContent = content.join('\n');
   pre.append(code);
   container.append(pre);
   continue;
  }
  const title = heading.exec(line);
  if (title) {
   append('h' + Math.min(title[1].length + 2, 6), title[2]);
   row++;
   continue;
  }
  const entry = item.exec(line);
  if (entry) {
   const ordered = /\d/.test(entry[1]);
   const list = doc.createElement(ordered ? 'ol' : 'ul');
   if (ordered) list.start = Number.parseInt(entry[1], 10);
   for (let next = entry; next && /\d/.test(next[1]) === ordered; next = item.exec(lines[row] || '')) {
    const li = doc.createElement('li');
    inline(li, next[2]);
    list.append(li);
    row++;
   }
   container.append(list);
   continue;
  }
  if (quote.test(line)) {
   const content = [];
   for (let next; (next = quote.exec(lines[row] || '')); row++) content.push(next[1]);
   append('blockquote', content.join('\n'));
   continue;
  }
  const width = tableWidth(lines, row);
  if (width) {
   const wrapper = doc.createElement('div');
   wrapper.className = 'reply-table';
   wrapper.tabIndex = 0;
   const table = doc.createElement('table');
   const head = table.createTHead().insertRow();
   for (const value of cells(line)) {
    const th = doc.createElement('th');
    th.scope = 'col';
    inline(th, value);
    head.append(th);
   }
   const body = table.createTBody();
   row += 2;
   for (let values = cells(lines[row]); values.length === width; values = cells(lines[++row])) {
    const tr = body.insertRow();
    for (const value of values) inline(tr.insertCell(), value);
   }
   wrapper.append(table);
   container.append(wrapper);
   continue;
  }
  const paragraph = [line];
  for (row++; lines[row]?.trim() && !fence.test(lines[row]) && !heading.test(lines[row]) &&
    !item.test(lines[row]) && !quote.test(lines[row]) && !tableWidth(lines, row); row++) {
   paragraph.push(lines[row]);
  }
  append('p', paragraph.join('\n'));
 }
}

const exportStyle = `
 :root {color-scheme: light dark; font: 17px/1.6 system-ui, sans-serif;}
 body {margin: 0; padding: clamp(1rem, 4vw, 3rem);}
 main {max-width: 74ch; margin: auto; overflow-wrap: anywhere; white-space: pre-wrap;}
 .reply-format {white-space: normal;}
 .reply-format :is(p,blockquote) {white-space: pre-wrap;}
 h1 {font-size: 1.5rem;}
 ul, ol {padding-inline-start: 1.5rem;}
 blockquote {margin-inline: 0; padding-inline-start: .75rem; border-inline-start: 3px solid;}
 pre, .reply-table {overflow: auto;}
 pre {direction: ltr; text-align: left; white-space: pre; border: 1px solid; border-radius: .5rem; padding: .75rem;}
 pre:focus-visible, .reply-table:focus-visible {outline: 2px solid; outline-offset: 2px;}
 table {width: 100%; border-collapse: collapse;}
 th, td {border: 1px solid; text-align: start; padding: .35rem .6rem;}
 @media print {body {padding: 0;} pre {white-space: pre-wrap;}}
`;

function exportHtml(sourceDocument, text, {title, format}) {
 const doc = sourceDocument.implementation.createHTMLDocument(title);
 doc.documentElement.lang = sourceDocument.documentElement.lang || 'en';
 doc.documentElement.dir = sourceDocument.documentElement.dir === 'rtl' ? 'rtl' : 'ltr';
 const charset = doc.createElement('meta');
 charset.setAttribute('charset', 'utf-8');
 const policy = doc.createElement('meta');
 policy.httpEquiv = 'Content-Security-Policy';
 policy.content = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'";
 doc.head.prepend(charset, policy);
 const viewport = doc.createElement('meta');
 viewport.name = 'viewport';
 viewport.content = 'width=device-width, initial-scale=1';
 const referrer = doc.createElement('meta');
 referrer.name = 'referrer';
 referrer.content = 'no-referrer';
 const style = doc.createElement('style');
 style.textContent = exportStyle;
 doc.head.append(viewport, referrer, style);
 const article = doc.createElement('main');
 article.dir = 'auto';
 const heading = doc.createElement('h1');
 heading.textContent = title;
 const content = doc.createElement('div');
 if (format) render(content, text);
 else content.textContent = text;
 article.append(heading, content);
 doc.body.append(article);
 return '<!doctype html>\n' + doc.documentElement.outerHTML;
}

globalThis.NexusReplyFormat = Object.freeze({render, exportHtml});
})();
