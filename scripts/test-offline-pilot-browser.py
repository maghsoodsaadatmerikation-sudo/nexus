#!/usr/bin/env python3
"""Real-Chromium acceptance of the exact standalone mobile offline HTML.

The app is exercised in a disposable file:// browser and has no backend.
No production credential, URL, storage, real user data, or mock network response.
"""
import json
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
  let requests = 0, blob;
  window.fetch = () => { requests++; throw new Error('network-disallowed'); };
  window.XMLHttpRequest = class { constructor(){ requests++; throw Error('network-disallowed'); } };
  window.confirm = () => true;
  const realObjectURL = URL.createObjectURL.bind(URL);
  URL.createObjectURL = value => {blob = value; return realObjectURL(value);};
  const checks = [];
  try {
    const narrow = window.innerWidth <= 760;
    assert(byId('export').disabled, 'blank-workspace-export-enabled');
    assert(byId('decision-view').textContent.includes('هیچ تصمیم انسانی'), 'implicit-judgment');
    checks.push('empty-workspace-no-auto-decision');
    fill('question','آیا این گزینه برای من مناسب است؟');
    fill('goal','استقلال');
    fill('constraints','زمان\nبودجه');
    fill('values','دقت');
    await submit('ask-form');
    assert(!byId('export').disabled, 'question-not-accepted');
    assert(byId('question-view').textContent.includes('استقلال'), 'goal-not-rendered');
    checks.push('question-goal-constraints-values');
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
    fill('option','گزینهٔ A');fill('consequences','ریسک\nفایده');
    await submit('option-form');
    assert(byId('alternatives').textContent.includes('گزینهٔ A'), 'option-not-recorded');
    checks.push('explicit-option-with-consequences');
    fill('decision','انتخاب آگاهانهٔ من');
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
    byId('new').click(); await tick();
    assert(byId('export').disabled && byId('decision-view').textContent.includes('هیچ تصمیم انسانی'),
      'fresh-workspace-retained-decision');
    await upload(JSON.stringify(exported));
    assert(byId('decision-view').textContent.includes('انتخاب آگاهانهٔ من') &&
      byId('audit').textContent.includes('#5'), 'import-not-restored');
    checks.push('json-import-retains-state');
    const prior = byId('decision-view').textContent;
    const corrupt = {...exported, workspace:{...exported.workspace, claims:[]}};
    await upload(JSON.stringify(corrupt));
    assert(byId('status').classList.contains('error') &&
      byId('decision-view').textContent === prior,'corrupt-import-mutated-state');
    checks.push('corrupt-import-fail-closed');
    assert(requests === 0, 'network-attempted');
    checks.push('no-external-requests');
    const width = window.innerWidth;
    assert(narrow === (width <= 760), 'viewport-mismatch');
    checks.push(narrow?'narrow-mobile-layout':'wide-desktop-layout');
    output.textContent = JSON.stringify({status:'PASS',width,checks,
      scope:'standalone-browser-file-only',network_requests:requests,
      production_verified:false,authority:'none'});
  } catch {
    output.textContent = JSON.stringify({status:'FAIL',reason:'offline-pilot-contract'});
  }
});
"""


def main():
    html = (Path(__file__).resolve().parents[1] / "web/offline-pilot.html").read_text()
    for fragment in ["Content-Security-Policy", "connect-src 'none'", "storage:'memory_only'",
                     "authority:'none'", "function validate(raw)"]:
        assert fragment in html
    assert "localStorage" not in html and "sessionStorage" not in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    browser = next((shutil.which(name) for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
        if shutil.which(name)), None)
    if browser is None:
        raise RuntimeError("real Chrome unavailable: no browser test was performed")
    html = html.replace("</body>", '<pre id="nexus-browser-result" hidden></pre><script>'
                        + WITNESS + "</script></body>")
    reports = []
    with tempfile.TemporaryDirectory(prefix="nexus-offline-pilot-test-") as td:
        root = Path(td)
        page = root / "index.html"
        page.write_text(html)
        for layout, dimensions in [("narrow", "500,980"), ("wide", "1280,980")]:
            cmd = ["node", str(Path(__file__).with_name("workspace-browser-runner.mjs")),
                   browser, page.as_uri(), str(root / layout), dimensions]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode:
                raise RuntimeError("real browser did not report PASS")
            report = json.loads(proc.stdout)
            if (report.get("status") != "PASS" or len(report.get("checks", [])) != 11 or
                report.get("network_requests") != 0 or
                (layout == "narrow") != (report["width"] <= 760)):
                raise RuntimeError("offline real-browser contract did not PASS")
            reports.append({"layout": layout, **report})
    print(json.dumps({"schema":"nexus.offline-pilot.browser-witness.v1","status":"PASS",
                      "reports":reports, "production_verified":False,
                      "server_recoverability_proven":False,
                      "authority":"none"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
