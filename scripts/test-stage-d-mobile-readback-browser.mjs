#!/usr/bin/env node
// Real Chromium smoke, purely synthetic and loopback-only. No production data.
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile, mkdtemp, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';

const chrome=process.env.NEXUS_READBACK_CHROME;
if(process.env.GITHUB_ACTIONS!=='true'||!chrome||[
  'RAILWAY_TOKEN','RAILWAY_API_TOKEN','NEXUS_API_TOKEN','RENDER_API_KEY'
].every(k=>!process.env[k])===false) throw Error('synthetic_ci_only');

const html=await readFile(new URL('../web/stage-d-mobile-readback.html',import.meta.url),'utf8');
function syntheticBrowserScenario() {
  (async()=>{
    const sleep=ms=>new Promise(r=>setTimeout(r,ms));
    const check=(ok,msg)=>{if(!ok)throw Error(msg)};
    try{
      check(!!window.crypto?.subtle&&!!window.NexusReadback&&window.isSecureContext,'missing_crypto');
      const payload=new TextEncoder().encode('SYNTHETIC_NOT_REAL_CMS_'+'a'.repeat(650));
      const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
      const cert='b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091';
      const csha=await digest(payload);
      const receipt={schema:'nexus.stage-d-encrypted-escrow.v1',
        status:'ENCRYPTED_PRIVATE_COPY_NOT_ATOMICALLY_VERIFIED',
        content_claim:'local_structural_intake_only',independent_live_restore:'not_evaluated',
        railway_origin:'not_independently_attested',release_authorized:false,seal:false,
        authority:'none',recipient_cert_sha256:cert,ciphertext_sha256:csha,ciphertext_bytes:payload.length};
      const receiptRaw=new TextEncoder().encode(JSON.stringify(receipt));
      const anchor={schema:'nexus.stage-d-encrypted-log-anchor.v1',
        status:'CIPHERTEXT_LOCAL_DIGEST_BEFORE_UPLOAD',
        repository:'maghsoodsaadatmerikation-sudo/nexus',
        workflow_ref:'maghsoodsaadatmerikation-sudo/nexus/.github/workflows/stage-d-encrypted-volume-capture.yml@refs/heads/main',
        ref:'refs/heads/main',event:'workflow_dispatch',run_id:43000000021,run_attempt:1,
        commit_sha:'a'.repeat(40),original_volume_id:'cc47a350-6c7e-4487-89d9-c4b390f94884',
        ciphertext_sha256:csha,ciphertext_bytes:payload.length,receipt_sha256:await digest(receiptRaw),
        recipient_cert_sha256:cert,provider_origin:'not_independently_attested',
        release_authorized:false,authority:'none'};
      const node=id=>document.getElementById(id);
      // Real Chromium must run the synthetic device self-check without
      // any user-selected backup, before exercising the file-upload controls.
      check(node('self-check') && node('self-check-result'),'missing_ondevice_control');
      check(node('self-check-result').dataset.state==='idle','unexpected_automatic_selfcheck');
      node('self-check').click();
      for(let i=0;i<150 && node('self-check-result').dataset.state==='busy';i++)await sleep(20);
      check(node('self-check-result').dataset.state==='pass','selfcheck_not_passed');
      check(node('self-check-result').textContent.includes('NOT TESTED'),'missing_selfcheck_nonclaims');
      node('anchor').value='NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1 '+JSON.stringify(anchor)+'\n';
      node('run-id').value=String(anchor.run_id);
      node('attempt').value='1';node('commit').value=anchor.commit_sha;
      const choose=(id,bytes,label)=>{
        const files=new DataTransfer();
        files.items.add(new File([bytes],label));
        node(id).files=files.files;
      };
      choose('cipher-a',payload,'first.cms');choose('cipher-b',payload,'second.cms');
      choose('receipt-a',receiptRaw,'first.json');choose('receipt-b',receiptRaw,'second.json');
      const poll=async expected=>{
        for(let i=0;i<100;i++){if(node('result').dataset.state===expected)return;await sleep(20)}
        throw Error('timeout_'+expected);
      };
      node('verify').click();await poll('pass');
      check(node('result').textContent.includes('NOT PROVEN'),'missing_nonclaims');
      node('run-id').value='9';node('verify').click();await poll('blocked');
      check(node('result').textContent.includes('BLOCKED'),'missing_denial');
      check(document.documentElement.scrollWidth<=window.innerWidth+3,'horizontal_overflow');
      document.body.dataset.nexusBrowserTest='PASS';
    }catch(_){document.body.dataset.nexusBrowserTest='BLOCKED';}
  })();
}
const inject='<script id="nexus-test-harness">('+syntheticBrowserScenario.toString()+')();</script>';
if(!html.includes('</body>'))throw Error('html_missing_body');
const served=html.replace('</body>',inject+'\n</body>');
const server=createServer((req,res)=>{
  if(req.method==='GET'&&req.url==='/readback'){
    res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});
    res.end(served);
  }else{res.writeHead(404);res.end();}
});
await new Promise((resolve,reject)=>server.listen(0,'127.0.0.1',err=>err?reject(err):resolve()));
const origin='http://127.0.0.1:'+server.address().port;
const work=await mkdtemp(path.join(tmpdir(),'nexus-chrome-readback-'));
let count=0;
try{
  for(const width of [390,1280]){
    const args=['--headless=new','--no-sandbox','--disable-dev-shm-usage',
      '--disable-extensions','--disable-background-networking','--no-first-run',
      '--no-default-browser-check','--window-size='+width+',900',
      '--user-data-dir='+path.join(work,'profile-'+width),
      '--virtual-time-budget=5000','--dump-dom',origin+'/readback'];
    const result=await new Promise((resolve,reject)=>{
      const proc=spawn(chrome,args,{stdio:['ignore','pipe','ignore']});
      let output='',settled=false;
      const fail=()=>{if(!settled){settled=true;proc.kill('SIGKILL');reject(Error('chromium_timeout_or_error'))}};
      const timer=setTimeout(fail,25000);
      proc.stdout.setEncoding('utf8');
      proc.stdout.on('data',data=>{output+=data;if(output.length>1048576)fail()});
      proc.on('error',()=>{clearTimeout(timer);fail()});
      proc.on('close',code=>{clearTimeout(timer);if(!settled){settled=true;code===0?resolve(output):reject(Error('chromium_nonzero'))}});
    });
    if(!/data-nexus-browser-test="PASS"/.test(result))throw Error('real_browser_test_failed');
    count++;
  }
  console.log(JSON.stringify({schema:'nexus.stage-d-mobile.real-browser.v1',status:'PASS',
    browser_runs:count,synthetic_only:true,actual_android_device_tested:false,
    production_backup_tested:false,release_authorized:false,authority:'none'}));
}finally{
  server.close();
  await rm(work,{recursive:true,force:true});
}
