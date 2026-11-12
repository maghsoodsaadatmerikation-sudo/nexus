#!/usr/bin/env python3
"""Real-Chromium acceptance of the exact standalone mobile offline HTML.

The app is exercised in a disposable file:// browser and has no backend.
No production credential, URL, storage, real user data, or mock network response.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load', async () => {
  const output = document.getElementById('nexus-browser-result');
  const byId = id => document.getElementById(id);
  const assert = (ok, why) => { if (!ok) throw new Error(why); };
  const tick = () => new Promise(resolve => setTimeout(resolve, 60));
  const waitFor = async (predicate,why) => {
    for(let n=0;n<300;n++) {if(predicate())return; await tick();}
    throw Error(why);
  };
  const fill = (id, value) => {
    byId(id).value = value;
    byId(id).dispatchEvent(new Event('input', {bubbles:true}));
  };
  const submit = async id => {
    byId(id).dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}));
    await tick();
  };
  const upload = async text => {
    const file = new File([text], 'nexus-offline-test.json', {type:'application/json'});
    const input = byId('file');
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', {bubbles:true}));
    await tick();
  };
  let requests = 0, blob, blobCount=0;
  window.fetch = () => { requests++; throw new Error('network-disallowed'); };
  window.XMLHttpRequest = class { constructor(){ requests++; throw Error('network-disallowed'); } };
  window.confirm = () => true;
  const realObjectURL = URL.createObjectURL.bind(URL);
  URL.createObjectURL = value => {blob = value; blobCount++; return realObjectURL(value);};
  const checks = [];
  let coreFixture = null;
  try {
    // The marker exists in test-only window.name, not the app or its vault.
    // Reload creates new app state and discards the in-page WebCrypto key.
    const reloadMarker='nexus-p08-real-reload:';
    if(window.name.startsWith(reloadMarker)){
      const prior=JSON.parse(window.name.slice(reloadMarker.length));
      window.name='';
      const slot='nexus.offline-pilot.local-encrypted.v1';
      assert(byId('decision-view').textContent.includes('هیچ تصمیم انسانی') &&
        byId('question-view').textContent.includes('هنوز پرسشی') &&
        window.localStorage.getItem(slot)!==null,
        'reloaded-page-inherited-plaintext-or-lost-ciphertext');
      fill('vault-open-password','synthetic-reload-secret-2026');
      byId('vault-restore').click();
      await waitFor(()=>byId('question-view').textContent.includes('پرسش پس از بارگذاری مجدد'),
        'real-page-reload-vault-restore-failed');
      assert(byId('vault-open-password').value==='' &&
        !window.localStorage.getItem(slot).includes('پرسش پس از بارگذاری مجدد'),
        'reloaded-page-exposed-plaintext');
      byId('vault-delete').click();
      assert(window.localStorage.getItem(slot)===null,
        'reload-cleanup-checkpoint-failed');
      prior.checks.push('real-page-reload-requires-passphrase-and-recovers');
      output.textContent=JSON.stringify({...prior,network_requests:requests});
      return;
    }
    const narrow = window.innerWidth <= 760;
    assert(byId('export').disabled, 'blank-workspace-export-enabled');
    assert(byId('decision-view').textContent.includes('هیچ تصمیم انسانی'), 'implicit-judgment');
    checks.push('empty-workspace-no-auto-decision');
    fill('question','آیا این گزینه برای من مناسب است؟');
    fill('goal','استقلال');
    fill('constraints','زمان، بودجه');
    fill('values','شفافیت، استقلال');
    await submit('ask-form');
    assert(!byId('export').disabled, 'question-not-accepted');
    assert(byId('question-view').textContent.includes('استقلال'), 'goal-not-rendered');
    checks.push('question-goal-constraints-values');
    assert(byId('question-view').textContent.includes('زمان • بودجه') &&
      byId('question-view').textContent.includes('شفافیت • استقلال'), 'comma-separated-fields-not-split');
    await submit('ask-form');
    assert(byId('audit').querySelectorAll('.entry').length === 1, 'unchanged-question-created-audit-event');
    checks.push('comma-lists-and-noop-resubmission');
    fill('origin','external_evidence');
    fill('claim','<img src=x onerror="window.testXss=true"> شاهد آزمایشی');
    await submit('claim-form');
    assert(byId('status').classList.contains('error'), 'source-less-external-claim-accepted');
    assert(byId('claims').textContent.includes('شاهدی ثبت نشده'), 'invalid-claim-materialized');
    fill('source','test:synthetic');
    fill('uncertainty','high');
    await submit('claim-form');
    assert(byId('claims').textContent.includes('<img'), 'external-evidence-missing');
    assert(byId('claims').querySelector('img') === null && !window.testXss, 'xss-as-html');
    checks.push('source-required-and-html-escaped');
    fill('origin','machine_analysis'); fill('claim','فقط تحلیل آزمایشی');
    await submit('claim-form');
    assert(byId('decision-view').textContent.includes('هیچ تصمیم انسانی'), 'machine-turned-into-decision');
    checks.push('machine-analysis-non-authority');
    byId('core-export').click();
    const earlyCore=JSON.parse(await blob.text());
    assert(earlyCore.schema_version===1 &&
      earlyCore.workspace.judgment===null &&
      earlyCore.events[0].kind==='WorkspaceCreated' &&
      earlyCore.events.every(e=>!e.kind.HumanJudgmentTransition) &&
      earlyCore.events.some(e=>e.kind.ClaimAdded) &&
      earlyCore.events.every(e=>e.provenance_id==='offline-bridge:user-supplied-unattested'),
      'core-export-invented-early-human-judgment');
    assert(earlyCore.workspace.claims[1].origin==='MachineAnalysis' &&
      !earlyCore.events.some(e=>e.kind.MachineAnalysisRecorded),
      'core-export-forged-machine-adapter');
    checks.push('core-bridge-before-human-choice-is-nonauthoritative');
    fill('option','گزینهٔ A');
    await submit('option-form');
    assert(byId('status').classList.contains('error') &&
      byId('alternatives').textContent.includes('گزینه‌ای ثبت نشده'), 'empty-consequence-accepted');
    checks.push('empty-consequence-rejected');
    fill('consequences','ریسک\nفایده');
    await submit('option-form');
    assert(byId('alternatives').textContent.includes('گزینهٔ A'), 'option-not-recorded');
    checks.push('explicit-option-with-consequences');
    fill('decision','انتخاب آگاهانهٔ من');
    await submit('decision-form');
    assert(byId('status').classList.contains('error') &&
      byId('decision-view').textContent.includes('هیچ تصمیم انسانی'), 'empty-rationale-accepted');
    checks.push('empty-rationale-rejected');
    fill('rationale','به تصمیم خودم');
    await submit('decision-form');
    assert(byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من'), 'human-judgment-not-recorded');
    checks.push('human-judgment-click-only');
    byId('export').click();
    assert(blob && blob.size > 0, 'download-not-created');
    const exported = JSON.parse(await blob.text());
    assert(exported.schema === 'nexus.offline-pilot.v1' &&
      exported.authority === 'none' && exported.storage === 'memory_only',
      'export-false-authority');
    assert(exported.workspace.judgment.decision === 'انتخاب آگاهانهٔ من' &&
      exported.workspace.claims.length === 2 &&
      exported.workspace.alternatives.length === 1 &&
      exported.events.length === 5, 'export-incomplete');
    checks.push('downloadable-full-workspace');
    byId('core-export').click();
    coreFixture=JSON.parse(await blob.text());
    assert(coreFixture.schema_version===1 &&
       coreFixture.workspace.id===exported.workspace.id &&
       coreFixture.workspace.question===exported.workspace.question &&
       coreFixture.workspace.goal===exported.workspace.goal &&
       coreFixture.workspace.constraints.join('|')==='زمان|بودجه' &&
       coreFixture.workspace.values.join('|')==='شفافیت|استقلال' &&
       coreFixture.workspace.claims.length===2 &&
       coreFixture.workspace.claims[0].origin.ExternalEvidence.source==='test:synthetic' &&
       coreFixture.workspace.claims[0].uncertainty==='High' &&
       coreFixture.workspace.claims[1].origin==='MachineAnalysis' &&
       coreFixture.workspace.alternatives[0].consequences.length===2 &&
       coreFixture.workspace.judgment.decision===exported.workspace.judgment.decision &&
       coreFixture.events.length===5 &&
       coreFixture.events[0].sequence===0 &&
       coreFixture.events.every((e,i)=>e.sequence===i &&
          e.provenance_id==='offline-bridge:user-supplied-unattested') &&
       JSON.stringify(coreFixture).includes('HumanJudgmentTransition') &&
       !JSON.stringify(coreFixture).includes('machine_analysis_recorded') &&
       !JSON.stringify(coreFixture).includes(exported.events[0].at),
       'core-bridge-schema-or-data-mismatch');
    checks.push('core-bridge-preserves-content-reconstructs-local-audit');
    const originalBlob=blob;
    window.confirm=()=>false;
    byId('core-export').click();
    assert(blob===originalBlob,'core-bridge-plaintext-bypassed-user-decline');
    checks.push('core-bridge-must-confirm-plaintext');
    window.confirm=()=>true;
    byId('new').click(); await tick();
    assert(byId('export').disabled && byId('decision-view').textContent.includes('هیچ تصمیم انسانی'),
      'fresh-workspace-retained-decision');
    await upload(JSON.stringify(exported));
    assert(byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من') &&
      byId('audit').textContent.includes('#5'), 'import-not-restored');
    checks.push('json-import-retains-state');
    const legacy = {...exported, workspace:{...exported.workspace,
      judgment:{...exported.workspace.judgment, rationale:''},
      alternatives:exported.workspace.alternatives.map(a=>({...a,consequences:[]}))}};
    await upload(JSON.stringify(legacy));
    assert(byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من') &&
      byId('quality').textContent.includes('دلیل تصمیم در فایل وجود ندارد') &&
      byId('quality').textContent.includes('بدون پیامد'), 'historical-incomplete-json-not-reviewed');
    checks.push('older-incomplete-export-imported-with-warning');
    const prior = byId('decision-view').textContent;
    const corrupt = {...exported, workspace:{...exported.workspace, claims:[]}};
    await upload(JSON.stringify(corrupt));
    assert(byId('status').classList.contains('error') &&
      byId('decision-view').textContent === prior,'corrupt-import-mutated-state');
    checks.push('corrupt-import-fail-closed');
    // Synthetic browser-only protected-file acceptance: no user secrets.
    let oldBlob=blob;
    fill('export-passphrase','short');
    fill('confirm-passphrase','short');
    byId('encrypt-export').click();
    await tick();
    assert(blob===oldBlob && byId('status').classList.contains('error'),
      'weak-password-accepted');
    fill('export-passphrase','a-long-synthetic-passphrase-2026');
    fill('confirm-passphrase','wrong-password-test');
    byId('encrypt-export').click();
    await tick();
    assert(blob===oldBlob && byId('status').classList.contains('error'),
      'password-mismatch-accepted');
    checks.push('protected-export-password-guards');
    fill('confirm-passphrase','a-long-synthetic-passphrase-2026');
    byId('encrypt-export').click();
    await waitFor(()=>blob!==oldBlob,'protected-export-timeout');
    const encrypted=JSON.parse(await blob.text());
    assert(encrypted.schema==='nexus.offline-pilot.encrypted.v1' &&
      encrypted.kdf.iterations===310000 &&
      encrypted.kdf.name==='PBKDF2' && encrypted.kdf.hash==='SHA-256' &&
      encrypted.cipher.name==='AES-GCM' && encrypted.cipher.tagLength===128 &&
      !JSON.stringify(encrypted).includes('انتخاب آگاهانهٔ من') &&
      !JSON.stringify(encrypted).includes('a-long-synthetic-passphrase-2026'),
      'weak-or-plaintext-encrypted-envelope');
    await waitFor(()=>byId('export-passphrase').value==='','export-password-not-cleared');
    checks.push('aes256-gcm-encrypted-no-plaintext-or-password');
    oldBlob=blob;
    fill('export-passphrase','a-long-synthetic-passphrase-2026');
    fill('confirm-passphrase','a-long-synthetic-passphrase-2026');
    byId('encrypt-export').click();
    await waitFor(()=>blob!==oldBlob,'second-encrypted-export-timeout');
    const encrypted2=JSON.parse(await blob.text());
    assert(encrypted.kdf.salt!==encrypted2.kdf.salt &&
      encrypted.cipher.iv!==encrypted2.cipher.iv &&
      encrypted.ciphertext!==encrypted2.ciphertext,'reused-salt-or-nonce');
    checks.push('fresh-random-salt-nonce-per-export');
    const preserved=byId('decision-view').textContent;
    await upload(JSON.stringify(encrypted2));
    assert(byId('status').classList.contains('error') &&
      byId('decision-view').textContent===preserved &&
      byId('status').textContent.includes('گذرواژهٔ'), 'missing-import-passphrase');
    checks.push('encrypted-import-needs-user-passphrase');
    fill('restore-passphrase','bad-test-password-2026');
    await upload(JSON.stringify(encrypted2));
    await waitFor(()=>byId('status').classList.contains('error'),'wrong-passphrase-timeout');
    assert(byId('decision-view').textContent===preserved &&
      byId('restore-passphrase').value==='','wrong-passphrase-mutated-state');
    checks.push('wrong-passphrase-fail-closed');
    const corrupted={...encrypted2,ciphertext:
      (encrypted2.ciphertext[0]==='A'?'B':'A')+encrypted2.ciphertext.slice(1)};
    fill('restore-passphrase','a-long-synthetic-passphrase-2026');
    await upload(JSON.stringify(corrupted));
    await waitFor(()=>byId('restore-passphrase').value==='','tamper-restore-did-not-finish');
    assert(byId('status').classList.contains('error') &&
      byId('decision-view').textContent===preserved,'tampered-ciphertext-accepted');
    checks.push('tampered-ciphertext-fail-closed');
    byId('new').click(); await tick();
    assert(byId('decision-view').textContent.includes('هیچ تصمیم انسانی'),'new-did-not-clear');
    fill('restore-passphrase','a-long-synthetic-passphrase-2026');
    await upload(JSON.stringify(encrypted2));
    await waitFor(()=>byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من'),
      'encrypted-roundtrip-not-restored');
    assert(byId('restore-passphrase').value==='' &&
      byId('audit').textContent.includes('#5'),'encrypted-state-mismatch');
    checks.push('real-webcrypto-restores-synthetic-workspace');
    // A long KDF must not combine a new workspace ID with an older payload.
    const beforeConcurrent=blobCount, encryptedBefore=blob;
    fill('export-passphrase','a-long-synthetic-passphrase-2026');
    fill('confirm-passphrase','a-long-synthetic-passphrase-2026');
    byId('encrypt-export').click();
    byId('encrypt-export').click();
    byId('new').click(); await tick();
    assert(byId('decision-view').textContent.includes('هیچ تصمیم انسانی'),
      'concurrent-new-workspace-failed');
    await waitFor(()=>blob!==encryptedBefore,'snapshot-crypto-timeout');
    await waitFor(()=>byId('export-passphrase').value==='','busy-not-released');
    assert(blobCount===beforeConcurrent+1 && byId('encrypt-export').disabled,
      'duplicate-simultaneous-encrypt-exports');
    checks.push('no-concurrent-protected-exports');
    fill('restore-passphrase','a-long-synthetic-passphrase-2026');
    await upload(await blob.text());
    await waitFor(()=>byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من'),
      'snapshot-was-mutated-while-encrypting');
    checks.push('atomic-snapshot-survives-concurrent-new-workspace');
    // Regression: a self-exported large workspace must be importable.
    const stamp=exported.events[0].at;
    const manyClaims=Array.from({length:100},(_,i)=>({
      id:'synthetic-claim-'+i,text:'ش'.repeat(1900),
      origin:'human',source:'',uncertainty:'unknown'
    }));
    const manyEvents=[{sequence:1,kind:'question',at:stamp}];
    for(let i=0;i<100;i++)manyEvents.push({sequence:i+2,kind:'claim',at:stamp});
    manyEvents.push({sequence:102,kind:'alternative',at:stamp});
    manyEvents.push({sequence:103,kind:'judgment',at:stamp});
    const big={...exported,workspace:{...exported.workspace,claims:manyClaims},
      events:manyEvents};
    const bigJson=JSON.stringify(big);
    assert(new Blob([bigJson]).size>256*1024 &&
      new Blob([bigJson]).size<2*1024*1024,'oversize-fixture-invalid');
    await upload(bigJson);
    await waitFor(()=>byId('claims').querySelectorAll('.entry').length===100,
      'large-plaintext-export-was-not-restored');
    checks.push('large-legacy-workspace-importable');
    const preLargeBlob=blob;
    fill('export-passphrase','a-long-synthetic-passphrase-2026');
    fill('confirm-passphrase','a-long-synthetic-passphrase-2026');
    byId('encrypt-export').click();
    await waitFor(()=>blob!==preLargeBlob,'large-encryption-timeout');
    const protectedLarge=await blob.text();
    byId('new').click(); await tick();
    fill('restore-passphrase','a-long-synthetic-passphrase-2026');
    await upload(protectedLarge);
    await waitFor(()=>byId('claims').querySelectorAll('.entry').length===100,
      'large-encrypted-restore-failed');
    checks.push('large-encrypted-workspace-recoverable');
    // Only explicitly enabled local browser storage may hold encrypted bytes.
    const vaultSlot='nexus.offline-pilot.local-encrypted.v1';
    assert(window.localStorage.getItem(vaultSlot)===null,
      'vault-autosaved-without-consent');
    fill('vault-new-password','long-synthetic-local-key-2026');
    fill('vault-new-confirm','long-synthetic-local-key-2026');
    byId('vault-enable').click();
    await waitFor(()=>window.localStorage.getItem(vaultSlot)!==null,
      'encrypted-local-checkpoint-timeout');
    const privateCopy=window.localStorage.getItem(vaultSlot);
    const localEnvelope=JSON.parse(privateCopy);
    assert(localEnvelope.schema==='nexus.offline-pilot.local-encrypted.v1' &&
       localEnvelope.kdf.iterations===310000 &&
       localEnvelope.cipher.name==='AES-GCM' &&
       !privateCopy.includes('انتخاب آگاهانهٔ من') &&
       !privateCopy.includes('long-synthetic-local-key-2026') &&
       byId('vault-new-password').value==='' &&
       byId('vault-new-confirm').value==='',
       'local-checkpoint-exposed-secret-or-plaintext');
    checks.push('opt-in-encrypted-local-checkpoint');
    byId('new').click(); await tick();
    assert(byId('question-view').textContent.includes('هنوز پرسشی') &&
       window.localStorage.getItem(vaultSlot)===privateCopy,
       'new-workspace-erased-or-overwrote-protected-copy');
    checks.push('new-workspace-pauses-vault-without-losing-checkpoint');
    fill('vault-open-password','incorrect-synthetic-key-2026');
    byId('vault-restore').click();
    await waitFor(()=>byId('vault-open-password').value==='',
       'wrong-local-passphrase-timeout');
    assert(byId('status').classList.contains('error') &&
       byId('question-view').textContent.includes('هنوز پرسشی'),
       'wrong-local-key-altered-workspace');
    checks.push('local-checkpoint-wrong-key-fail-closed');
    const corruptLocal={...localEnvelope,ciphertext:
       (localEnvelope.ciphertext[0]==='A'?'B':'A')+localEnvelope.ciphertext.slice(1)};
    window.localStorage.setItem(vaultSlot,JSON.stringify(corruptLocal));
    fill('vault-open-password','long-synthetic-local-key-2026');
    byId('vault-restore').click();
    await waitFor(()=>byId('vault-open-password').value==='',
       'corrupt-local-checkpoint-timeout');
    assert(byId('status').classList.contains('error') &&
       byId('question-view').textContent.includes('هنوز پرسشی'),
       'tampered-local-vault-altered-workspace');
    checks.push('local-checkpoint-tamper-fail-closed');
    window.localStorage.setItem(vaultSlot,privateCopy);
    fill('vault-open-password','long-synthetic-local-key-2026');
    byId('vault-restore').click();
    // Deletion races the intentionally asynchronous PBKDF2; the old
    // encrypted copy must never reappear after explicit deletion.
    byId('vault-delete').click();
    await waitFor(()=>byId('vault-open-password').value==='',
       'deleted-while-decrypting-timeout');
    assert(window.localStorage.getItem(vaultSlot)===null &&
       byId('question-view').textContent.includes('هنوز پرسشی'),
       'deleted-vault-resurrected-through-inflight-decryption');
    checks.push('delete-during-decrypt-never-resurrects-workspace');
    window.localStorage.setItem(vaultSlot,privateCopy);
    fill('vault-open-password','long-synthetic-local-key-2026');
    byId('vault-restore').click();
    await waitFor(()=>byId('claims').querySelectorAll('.entry').length===100,
       'local-checkpoint-restore-timeout');
    assert(byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من') &&
       byId('vault-open-password').value==='',
       'local-checkpoint-restored-incomplete-data');
    checks.push('local-checkpoint-restores-complete-workspace');
    await waitFor(()=>window.localStorage.getItem(vaultSlot)!==privateCopy,
       'restored-vault-was-not-refreshed');
    byId('vault-pause').click();
    const pausedCopy=window.localStorage.getItem(vaultSlot);
    byId('new').click(); await tick();
    assert(window.localStorage.getItem(vaultSlot)===pausedCopy,
       'paused-local-vault-was-overwritten');
    checks.push('paused-vault-never-autosaves');
    byId('vault-delete').click();
    assert(window.localStorage.getItem(vaultSlot)===null,
       'explicit-vault-delete-failed');
    checks.push('explicit-local-checkpoint-erasure');
    assert(requests === 0, 'network-attempted');
    checks.push('no-external-requests');
    const width = window.innerWidth;
    assert(narrow === (width <= 760), 'viewport-mismatch');
    checks.push(narrow?'narrow-mobile-layout':'wide-desktop-layout');
    // Real page lifecycle, not merely clearing forms in the same JS heap.
    // Only a synthetic local vault and a test-runner window.name marker survive.
    fill('question','پرسش پس از بارگذاری مجدد');
    await submit('ask-form');
    fill('vault-new-password','synthetic-reload-secret-2026');
    fill('vault-new-confirm','synthetic-reload-secret-2026');
    byId('vault-enable').click();
    await waitFor(()=>window.localStorage.getItem('nexus.offline-pilot.local-encrypted.v1')!==null,
      'real-reload-checkpoint-not-written');
    window.name=reloadMarker+JSON.stringify({status:'PASS',width,checks,
      scope:'standalone-browser-file-only',production_verified:false,
      authority:'none',core_fixture:coreFixture});
    window.location.reload();
    return;

  } catch (e) {
    const code=String(e?.message||'offline-pilot-contract').replace(/[^A-Za-z0-9-]/g,'').slice(0,120);
    output.textContent = JSON.stringify({status:'FAIL',reason:code});
  }
});
"""


def main():
    html = (Path(__file__).resolve().parents[1] / "web/offline-pilot.html").read_text()
    for fragment in ["Content-Security-Policy", "connect-src 'none'", "storage:'memory_only'",
                     "authority:'none'", "function validate(raw)"]:
        assert fragment in html
    assert "localStorage.setItem(VAULT_SLOT" in html and "sessionStorage" not in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    browser = next((shutil.which(name) for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if shutil.which(name)), None)
    if browser is None:
        raise RuntimeError("real Chrome unavailable: no browser test was performed")
    html = html.replace("</body>", '<pre id="nexus-browser-result" hidden></pre><script>'
                        + WITNESS + "</script></body>")
    reports = []
    bridge_output=os.environ.get("NEXUS_BRIDGE_SYNTHETIC_OUTPUT")
    if bridge_output:
        path=Path(bridge_output)
        runner=Path(os.environ.get("RUNNER_TEMP", "/nonexistent"))
        assert (path.is_absolute() and path.parent.resolve()==runner.resolve()
                and runner.is_dir() and not path.exists()), "unsafe-synthetic-destination"
    with tempfile.TemporaryDirectory(prefix="nexus-offline-pilot-test-") as td:
        root = Path(td)
        page = root / "index.html"
        page.write_text(html)
        for layout, dimensions in [("narrow", "500,980"), ("wide", "1280,980")]:
            cmd = ["node", str(Path(__file__).with_name("workspace-browser-runner.mjs")),
                   browser, page.as_uri(), str(root / layout), dimensions, "45000"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=105)
            if proc.returncode:
                raise RuntimeError("real browser did not report PASS: exit="+str(proc.returncode)+" stdout="+proc.stdout.strip()[:300]+" stderr="+proc.stderr.strip()[-450:])
            report = json.loads(proc.stdout)
            if (report.get("status") != "PASS" or len(report.get("checks", [])) != 38 or
                report.get("network_requests") != 0 or
                (layout == "narrow") != (report["width"] <= 760)):
                raise RuntimeError("offline real-browser contract did not PASS")
            fixture=report.pop("core_fixture", None)
            assert isinstance(fixture, dict) and fixture.get("schema_version")==1
            if bridge_output and layout=="narrow":
                descriptor=os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(fixture, handle, ensure_ascii=False, separators=(",", ":"))
                    handle.write("\n")
            reports.append({"layout": layout, **report})
    print(json.dumps({"schema":"nexus.offline-pilot.browser-witness.v1","status":"PASS",
                      "reports":reports, "production_verified":False,
                      "server_recoverability_proven":False,
                      "authority":"none"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
