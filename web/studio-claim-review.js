/* NEXUS: local, non-authoritative review prompts for AI-generated statements. */
(function(root){'use strict';
const MAX_INPUT=24000,MAX_CLAIMS=12;
const CREDENTIALS=[
 ['private-key block',/(?:^|\n)-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----/],
 ['GitHub token',/(?:^|[^\w])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})(?!\w)/],
 ['model API key',/(?:^|[^\w-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}(?![\w-])/],
 ['AWS access key',/(?:^|[^A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])/],
 ['bearer credential',/\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~-]{24,}/i]
];
function input(value){
 if(typeof value!=='string'||value.length>MAX_INPUT)throw Error('claim-review-input');
 return value;
}
function inspect(value){return CREDENTIALS.filter(([,pattern])=>pattern.test(value)).map(([label])=>label)}
function candidates(value){
 // Exclude fenced code, URLs, headings and Markdown tables. Never execute content.
 const prose=value.replace(/```[\s\S]*?```/g,'\n').replace(/`[^`\n]*`/g,' ')
  .replace(/https?:\/\/[^\s<>]+/gi,'[link]');
 const rows=prose.split(/\r?\n/),out=[];
 for(const row of rows){
  const line=row.trim();
  if(!line||/^\s*(?:#|>|\||[-*_]{3,})/.test(line)||/^\s*(?:Source|Sources|منابع)\s*:/i.test(line))continue;
  const plain=line.replace(/^(?:[-*+]\s+|\d+[.)]\s+)/,'').trim();
  for(const part of plain.split(/(?<=[.!?؟])\s+/u)){
   const sentence=part.trim();
   if(sentence.length<20||sentence.length>1800||/[?؟]$/.test(sentence)||
      /^(?:please|click|try|consider|you can|i can|i cannot|let me|لطفاً|می‌توانی|میتوانی|اگر می‌خواهی)\b/i.test(sentence))continue;
   out.push(sentence);
  }
 }
 return out;
}
function reason(sentence){
 if(/(?:\b\d+(?:[.,]\d+)?\s*(?:%|percent|million|billion|km|kg|years?|people|patients?)\b|\b(?:19|20)\d{2}\b|[۰-۹٠-٩]{2,})/iu.test(sentence))return 'quantity-or-date';
 if(/\b(?:caus(?:es?|ed|ing)|leads? to|because|reduces?|increases?|results? in|associated with)\b|(?:سبب|علت|باعث|افزایش|کاهش|منجر می‌شود|ارتباط دارد)/iu.test(sentence))return 'causal-or-associational';
 if(/\b(?:more|less|higher|lower|better|worse|than|compared|largest|first|most)\b|(?:بیشتر|کمتر|بهتر|بدتر|نخستین|مقایسه)/iu.test(sentence))return 'comparison';
 return 'general-claim';
}
function review(answer){
 const value=input(answer),categories=inspect(value);
 if(categories.length)return Object.freeze({schema:'nexus.claim-review.v1',blocked:true,possible_credentials:Object.freeze(categories),claims:Object.freeze([]),total_candidates:0,truncated:false,verified:false});
 const sentences=candidates(value),seen=new Set(),claims=[];
 for(const sentence of sentences){
  const key=sentence.normalize('NFKC').toLocaleLowerCase();
  if(seen.has(key))continue;
  seen.add(key);
  if(claims.length<MAX_CLAIMS)claims.push(Object.freeze({id:'c'+(claims.length+1),statement:sentence,review_reason:reason(sentence),verification:'not-checked'}));
 }
 return Object.freeze({schema:'nexus.claim-review.v1',blocked:false,possible_credentials:Object.freeze([]),claims:Object.freeze(claims),total_candidates:seen.size,truncated:seen.size>MAX_CLAIMS,verified:false});
}
function checklist(answer,language='en'){
 if(!['en','fa'].includes(language))throw Error('claim-review-language');
 const report=review(answer);
 if(report.blocked)throw Error('claim-review-possible-credentials');
 const fa=language==='fa';
 const heading=fa?'بازبینی ادعاها — تأییدنشده':'Claim review — not verified';
 const lead=fa?'این فهرست صرفاً از متن ساخته شده است. هر مورد را با منبع مستقل، تاریخ و زمینه بررسی کنید. تأیید حقیقت انجام نشده است.':'Locally extracted review candidates only. Verify each with an independent source, date and context. No fact-checking has occurred.';
 const parts=['# '+heading,'',lead,''];
 if(!report.claims.length)parts.push(fa?'موردی برای بررسی خودکار پیدا نشد؛ این به معنی صحت متن نیست.':'No candidates identified; this does not establish accuracy.');
 for(const claim of report.claims){
  // Block HTML and Markdown markers from becoming active markup in the export.
  const escaped=claim.statement.replace(/[\\`*_{}\[\]()#+.!>|~-]/g,'\\$&').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  parts.push('## '+claim.id+' · '+claim.review_reason,'',escaped,'',fa?'منبع مستقل: ______    وضعیت: بررسی‌نشده':'Independent source: ______    Status: not checked','');
 }
 if(report.truncated)parts.push(fa?'فهرست به ۱۲ مورد محدود شد.':'Only the first 12 candidates are listed.');
 return parts.join('\n');
}
root.NexusClaimReview=Object.freeze({MAX_INPUT,MAX_CLAIMS,review,checklist});
})(globalThis);
