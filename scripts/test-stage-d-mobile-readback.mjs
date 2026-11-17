#!/usr/bin/env node
// No external dependencies or real backup bytes. Tests core embedded in offline HTML.
import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {webcrypto, createHash} from 'node:crypto';

const html = readFileSync(new URL('../web/stage-d-mobile-readback.html', import.meta.url), 'utf8');
const embedded = html.match(/<script id="nexus-readback-core">([\s\S]*?)<\/script>/);
assert.ok(embedded, 'single-file offline core must be embedded');
const window = {crypto: webcrypto};
vm.runInNewContext(embedded[1], {window, TextDecoder, TextEncoder, Uint8Array, Set, BigInt}, {timeout: 3000});
const {verifyCopies, selfTestBrowser} = window.NexusReadback;
const sha = b => createHash('sha256').update(b).digest('hex');
const CIPHER = Buffer.from('NOT_REAL_CMS_SYNTHETIC_' + 'x'.repeat(500));
const CERT = 'b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091';
const RECEIPT = {
  schema:'nexus.stage-d-encrypted-escrow.v1',
  status:'ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED',
  content_claim:'local_structural_intake_only',
  independent_live_restore:'not_evaluated',
  railway_origin:'not_independently_attested',
  release_authorized:false,seal:false,authority:'none',
  recipient_cert_sha256:CERT,ciphertext_sha256:sha(CIPHER),ciphertext_bytes:CIPHER.length
};
const R_BYTES=Buffer.from(JSON.stringify(RECEIPT));
const ANCHOR={
  schema:'nexus.stage-d-encrypted-log-anchor.v1',
  status:'CIPHERTEXT_LOCAL_DIGEST_BEFORE_UPLOAD',
  repository:'maghsoodsaadatmerikation-sudo/nexus',
  workflow_ref:'maghsoodsaadatmerikation-sudo/nexus/.github/workflows/stage-d-encrypted-volume-capture.yml@refs/heads/main',
  ref:'refs/heads/main',event:'workflow_dispatch',
  run_id:43000123456,run_attempt:1,commit_sha:'a'.repeat(40),
  original_volume_id:'cc47a350-6c7e-4487-89d9-c4b390f94884',
  ciphertext_sha256:sha(CIPHER),ciphertext_bytes:CIPHER.length,
  receipt_sha256:sha(R_BYTES),recipient_cert_sha256:CERT,
  provider_origin:'not_independently_attested',
  release_authorized:false,authority:'none'
};
const LINE='NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1 '+JSON.stringify(ANCHOR)+'\n';
const EXPECTED={runId:String(ANCHOR.run_id),attempt:String(ANCHOR.run_attempt),commit:ANCHOR.commit_sha};
const file=b=>{const bytes=Buffer.from(b);return {size:bytes.length,async arrayBuffer(){return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}};};
const pairs=()=>[
  {cipher:file(CIPHER),receipt:file(R_BYTES)},
  {cipher:file(CIPHER),receipt:file(R_BYTES)}
];
const mustBlock=async (line=LINE,identity=EXPECTED,p=pairs())=>assert.rejects(verifyCopies(line,identity,p));

test('two valid synthetic pairs match SHA-256 but never confer release authority',async()=>{
  const result=await verifyCopies(LINE,EXPECTED,pairs());
  assert.equal(result.status,'TWO_SELECTED_FILE_PAIRS_MATCH_ANCHOR_BYTES_ONLY');
  assert.equal(result.ciphertext_sha256,sha(CIPHER));
  for (const k of ['deployment_authorized','complete_production_backup','ciphertext_decrypted','original_github_run_authenticated','data_uploaded']) assert.equal(result[k],false);
  assert.equal(result.independent_storage,'NOT_VERIFIED_BY_BROWSER');
});
test('run, attempt and exact commit binding fail closed',async()=>{
  await mustBlock(LINE,{...EXPECTED,runId:'43000123457'});
  await mustBlock(LINE,{...EXPECTED,attempt:'2'});
  await mustBlock(LINE,{...EXPECTED,commit:'b'.repeat(40)});
});
test('tampered ciphertext with matching forged receipt still blocks',async()=>{
  const p=pairs(),evil=Buffer.concat([CIPHER,Buffer.from('mutation')]);
  p[1]={cipher:file(evil),receipt:file(Buffer.from(JSON.stringify({...RECEIPT,ciphertext_sha256:sha(evil),ciphertext_bytes:evil.length})))};
  await mustBlock(LINE,EXPECTED,p);
});
test('raw receipt reserialization changes original SHA and blocks',async()=>{
  const p=pairs();p[0].receipt=file(Buffer.from(JSON.stringify(RECEIPT,null,2)));
  await mustBlock(LINE,EXPECTED,p);
});
test('duplicate JSON keys, nested payloads, missing braces and forged authority block',async()=>{
  await mustBlock(LINE.replace(/}\n$/,',"authority":"none"}\n'));
  await mustBlock(LINE.replace('"run_id":43000123456','"run_id":[]'));
  await mustBlock(LINE.replace('"status":"CIPHERTEXT_LOCAL_DIGEST_BEFORE_UPLOAD"','"status":{"x":1}'));
  await mustBlock(LINE.replace('"release_authorized":false','"release_authorized":true'));
  await mustBlock(LINE.trim().slice(0,-1));
});
test('missing, same-selection, and oversized files block',async()=>{
  let p=pairs();p[1].cipher=p[0].cipher;await mustBlock(LINE,EXPECTED,p);
  p=pairs();p[0].receipt=null;await mustBlock(LINE,EXPECTED,p);
  p=pairs();p[0].cipher={size:65*1024*1024+1,arrayBuffer:async()=>new ArrayBuffer(0)};await mustBlock(LINE,EXPECTED,p);
});
test('browser without WebCrypto blocks instead of contacting a service',async()=>{
  window.crypto=undefined;try{await mustBlock();}finally{window.crypto=webcrypto;}
});
test('single HTML has strict CSP and no external resources or network APIs',()=>{
  assert.match(html,/default-src 'none'/);
  assert.match(html,/connect-src 'none'/);
  assert.doesNotMatch(html,/<script[^>]+src=|<link[^>]+href=|<img\b/i);
  assert.doesNotMatch(html,/fetch\(|XMLHttpRequest|sendBeacon|WebSocket|serviceWorker\.register|https?:\/\//i);
});

test('device self-check uses synthetic SHA-256, matching, tamper denial and no authority',async()=>{
  const result = await selfTestBrowser();
  assert.equal(result.status,'SYNTHETIC_BROWSER_SELFTEST_PASS');
  assert.equal(result.checks,4);
  for(const key of ['synthetic_only']) assert.equal(result[key],true);
  for(const key of ['file_picker_tested','real_ciphertext_tested','real_backup_decrypted',
    'independent_custody_proven','deployment_authorized','network_required']) assert.equal(result[key],false);
  assert.equal(result.authority,'none');
});
test('device self-check rejects unavailable WebCrypto rather than faking pass',async()=>{
  window.crypto=undefined;
  try {await assert.rejects(selfTestBrowser())} finally {window.crypto=webcrypto}
});
test('device self-check blocks corrupted SHA implementation',async()=>{
  const original=window.crypto;
  window.crypto={subtle:{digest:async()=>new Uint8Array(32).buffer}};
  try {await assert.rejects(selfTestBrowser(),/sha256_known_answer_failed/)}
  finally {window.crypto=original}
});
test('device-check is an explicit action; does not silently load files',()=>{
  assert.match(html,/id="self-check"[^>]*>Run on-device safety check<\/button>/);
  assert.match(html,/id="self-check-result"/);
  assert.match(html,/selfCheck.addEventListener\('click'/);
  assert.doesNotMatch(html,/localStorage\.|sessionStorage\./);
});
