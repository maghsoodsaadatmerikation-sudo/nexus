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
// Human-entered source notes are never downloaded, fetched, trusted or persisted.
// A quoted source or user's classification is not independent evidence.
const ASSESSMENTS=Object.freeze(['not-assessed','supports','contradicts','unclear']);
function recordEvidence(answer,claimId,entry){
 const report=review(answer);
 if(report.blocked)throw Error('claim-evidence-blocked');
 if(typeof claimId!=='string'||!/^c(?:[1-9]|1[0-2])$/.test(claimId))throw Error('claim-evidence-id');
 const claim=report.claims.find(c=>c.id===claimId);
 if(!claim||!entry||typeof entry!=='object'||Array.isArray(entry)||
    Object.keys(entry).some(k=>!['source_url','source_date','note','assessment'].includes(k)))throw Error('claim-evidence-input');
 const {source_url='',source_date='',note='',assessment='not-assessed'}=entry;
 if(typeof source_url!=='string'||source_url.length>1000||
    typeof source_date!=='string'||source_date.length>10||
    typeof note!=='string'||note.length>500||
    !ASSESSMENTS.includes(assessment))throw Error('claim-evidence-input');
 if(inspect(source_url+'\n'+note).length)throw Error('claim-evidence-private');
 let url='';
 if(source_url){
  try{
   const parsed=new URL(source_url);
   if(parsed.protocol!=='https:'||!parsed.hostname||parsed.username||parsed.password||
      /[\s<>"'\\]/.test(source_url))throw Error('invalid');
   url=parsed.href;
  }catch{throw Error('claim-evidence-url')}
 }
 if(source_date){
  let valid=false;
  if(/^\d{4}-\d{2}-\d{2}$/.test(source_date)){
   const d=new Date(source_date+'T00:00:00Z');
   valid=Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===source_date;
  }
  if(!valid)throw Error('claim-evidence-date');
  if(!url)throw Error('claim-evidence-url');
 }
 if(['supports','contradicts'].includes(assessment)&&(!url||!source_date))
  throw Error('claim-evidence-needs-source-and-date');
 return Object.freeze({
  schema:'nexus.claim-evidence.v1',claim_id:claim.id,statement:claim.statement,
  source_url:url,source_date,user_note:note,reviewer_assessment:assessment,
  verification:'not-independently-verified',source_retrieved:false,authority:'none'
 });
}

const MAX_QUOTATION=400,MAX_SOURCE_TEXT=12000;
// A text-presence result says nothing about provenance, authorship or support.
function locateQuote(answer,claimId,entry,sourceText,quotation){
 const evidence=recordEvidence(answer,claimId,entry);
 if(!evidence.source_url||!evidence.source_date)throw Error('claim-quote-source-needed');
 if(typeof sourceText!=='string'||sourceText.length<30||sourceText.length>MAX_SOURCE_TEXT||
    typeof quotation!=='string'||quotation.length<30||quotation.length>MAX_QUOTATION)
  throw Error('claim-quote-input');
 if(inspect(sourceText+'\n'+quotation).length)throw Error('claim-quote-private');
 const fold=s=>s.normalize('NFKC').replace(/\s+/gu,' ').trim();
 const text=fold(sourceText),needle=fold(quotation);
 if(needle.length<30)throw Error('claim-quote-input');
 const occurrences=text.split(needle).length-1;
 return Object.freeze({
  schema:'nexus.quote-presence.v1',claim_id:evidence.claim_id,
  text_presence:occurrences?'present-in-user-paste':'not-found-in-user-paste',
  match_count:Math.min(occurrences,99),normalization:'NFKC-and-whitespace',
  quotation,source_url:evidence.source_url,source_date:evidence.source_date,
  source_origin:'human-pasted',source_retrieved:false,source_authenticity:'not-assessed',
  claim_support:'not-assessed',verification:'not-independently-verified',authority:'none'
 });
}
// Browser navigation is a separate user action, not source retrieval or verification.
// A syntactically public DNS name is NOT a vetted or safe website.
function planSourceOpen(answer,claimId,sourceURL){
 const entry=recordEvidence(answer,claimId,{source_url:sourceURL});
 if(!entry.source_url)throw Error('claim-source-url-required');
 const parsed=new URL(entry.source_url),hostname=parsed.hostname.toLowerCase();
 // Disallow local names, IP literals, unusual ports and reserved network suffixes.
 // The destination can still redirect or be malicious after the user opens it.
 const parts=hostname.split('.');
 const reserved=new Set(['localhost','local','internal','lan','home','corp','onion','arpa','test','invalid','example']);
 if(parts.length<2||reserved.has(parts.at(-1))||reserved.has(parts.at(-2))||
    !/^[a-z]{2,63}$/.test(parts.at(-1))||parsed.port||
    parts.some(part=>!part||part.length>63||!/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(part))||
    /^(?:\d+\.){3}\d+$/.test(hostname)||
    hostname.includes(':')||hostname.includes('[')||hostname.includes(']'))
   throw Error('claim-source-public-host-required');
 return Object.freeze({
  schema:'nexus.source-open-plan.v1',claim_id:entry.claim_id,
  url:entry.source_url,hostname,method:'explicit-browser-navigation',
  source_retrieved:false,source_verified:false,claim_verified:false,
  authority:'none'
 });
}
function evidenceReport(answer,entries,language='en'){
 if(!['en','fa'].includes(language)||!Array.isArray(entries)||entries.length>MAX_CLAIMS)
  throw Error('claim-evidence-report');
 const checked=review(answer);if(checked.blocked)throw Error('claim-evidence-blocked');
 const seen=new Set(),safe=[];
 for(const entry of entries){
  if(!entry||typeof entry!=='object'||Array.isArray(entry)||seen.has(entry.claim_id)||
     Object.keys(entry).some(key=>!['schema','claim_id','statement','source_url','source_date','user_note','reviewer_assessment','verification','source_retrieved','authority','source_text','quotation'].includes(key))||
     (entry.schema!==undefined&&entry.schema!=='nexus.claim-evidence.v1')||
     (entry.verification!==undefined&&entry.verification!=='not-independently-verified')||
     (entry.source_retrieved!==undefined&&entry.source_retrieved!==false)||
     (entry.authority!==undefined&&entry.authority!=='none'))
   throw Error('claim-evidence-report');
  seen.add(entry.claim_id);
  const checked=recordEvidence(answer,entry.claim_id,{
   source_url:entry.source_url,source_date:entry.source_date,
   note:entry.user_note,assessment:entry.reviewer_assessment
  });
  if(entry.statement!==undefined&&entry.statement!==checked.statement)
   throw Error('claim-evidence-report');
  safe.push(checked);
 }
 const fa=language==='fa';
 const plain=value=>value.replace(/[\r\n]+/g,' ').replace(/[\\`*_{}\[\]()#+.!>|~<]/g,character=>'\\'+character);
 const lines=[
  fa?'# یادداشت بررسی ادعاها — تأیید مستقل نشده':'# Human claim review notes — not independently verified',
  '',
  fa?'منابع و ارزیابی‌ها فقط توسط کاربر وارد شده‌اند. نکسوس هیچ منبعی را باز نکرده، اعتبارسنجی نکرده و صحت هیچ ادعایی را تأیید نکرده است.':'All references and assessments were entered by the user. NEXUS has not fetched or validated sources or verified any claim.',
  ''
 ];
 for(const entry of safe){
  lines.push('## '+entry.claim_id,'',plain(entry.statement),'',
   (fa?'ارزیابی کاربر: ':'User assessment: ')+entry.reviewer_assessment,
   (fa?'نشانی منبعِ واردشده: ':'User-entered source: ')+(entry.source_url||'—'),
   (fa?'تاریخ منبع به ادعای کاربر: ':'Source date as entered: ')+(entry.source_date||'—'),
   (fa?'یادداشت کاربر: ':'User note: ')+(entry.user_note?plain(entry.user_note):'—'),
   fa?'وضعیت: تأیید مستقل نشده':'Status: not independently verified','');
  const original=entries.find(candidate=>candidate.claim_id===entry.claim_id);
  const sourceText=original.source_text??'',quotation=original.quotation??'';
  if(sourceText||quotation){
   const checked=locateQuote(answer,entry.claim_id,{
    source_url:entry.source_url,source_date:entry.source_date,
    note:entry.user_note,assessment:entry.reviewer_assessment
   },sourceText,quotation);
   lines.push(fa?'نقل‌قولِ واردشده:':'User-entered quotation:',plain(checked.quotation),
    (fa?'حضور رشته در متن چسبانده‌شده: ':'Text sequence in pasted text: ')+checked.text_presence,
    fa?'اعتبار متن منبع و ارتباط آن با ادعا بررسی نشده است.':'Source authenticity and claim support have not been checked.','');
  }
 }
 return lines.join('\n');
}
root.NexusClaimReview=Object.freeze({MAX_INPUT,MAX_CLAIMS,MAX_QUOTATION,MAX_SOURCE_TEXT,review,checklist,recordEvidence,locateQuote,planSourceOpen,evidenceReport});
})(globalThis);
