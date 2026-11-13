# Stage 22 — portable, zero-cost, offline Work Mode

## Why this stage exists

The source-grounded research conversation, optional MCP connections and new Work Mode live on an **authenticated Rust gateway development branch**. A no-computer, no-budget user cannot assume a live authenticated host or that the original Railway /data volume is independently recoverable. The Stage 22 portable edition is a useful **independent companion**, not a substitute for fixing that infrastructure.

This stage builds one self-contained HTML file from the existing reviewed Work Mode HTML and core JavaScript. It operates entirely in a browser, without a server, installation, plugin, external provider, Web API, LLM, payment or new hosting plan.

## Human workflow (supported browser)

1. Download `nexus-work-mode-portable.html` from the verified `nexus-stage22-portable-work-mode` GitHub Actions artifact; keep the companion and its `integrity.json` receipt together. The artifact has a 30-day GitHub retention limit, not a perpetual release.
2. Open the HTML as a **local file** in a browser supporting `file://` Web Crypto and IndexedDB. Browser/Android file-handling policy varies; Android hardware has **not** been independently tested. On unsupported browsers, use a secure local/HTTPS origin instead of pretending encrypted storage works.
3. In English or Persian, enter a title, goal, criteria and steps. Add tasks, dependencies, optional notes and attached local evidence files. A task cannot become Done without human review, supporting evidence and completed prerequisites.
4. Initially projects are **RAM-only**. To retain one, create an optional password-protected archive (at least 12 characters), then explicitly press **Save current project**.
5. Explicitly **Download encrypted archive** and keep a separate private copy. Lock to clear work from the tab; unlock and reopen the saved project. Forgotten passphrases cannot be recovered. Device eviction/browser clearing can lose IndexedDB; the independent encrypted download is essential for portability.
6. A Markdown report, if deliberately downloaded, is **plaintext** and excludes original file bytes. The encrypted archive carries the included files. It is not the original Railway backup.

No network chat, Internet search, app connector, cross-device sync, server workspace authorization, deployment or autonomous work is available in this edition. Those controls are **hidden** and the work-mode page's only fetch-based chat handler is **removed** from the produced HTML; the policy is `connect-src 'none'`. The UI retains a bilingual warning. Local file contents are not automatically inspected by an AI model.

## Reproducible build

```bash
python3 scripts/build-work-mode-portable.py \
  --out build/nexus-work-mode-portable.html \
  --manifest build/nexus-work-mode-portable.integrity.json
python3 scripts/build-work-mode-portable.py \
  --out build/nexus-work-mode-portable.html \
  --manifest build/nexus-work-mode-portable.integrity.json --check
python3 scripts/test-work-mode-portable.py
python3 scripts/test-work-mode-portable-browser.py
```

Builder fails closed if the reviewed source's chat handler, CSP, navigation, external script, or security-sensitive DOM boundaries change. Integrity JSON contains SHA-256 hashes of the exact bundled HTML and its inputs, plus explicit unverified production claims. Hashes are integrity checks, **not** third-party authenticity signatures.

GitHub Actions uses no production/provider credentials. Real disposable Chromium opens the **generated HTML via file://** at two widths and proves project creation, refusal of unreviewed completion, explicit human-review evidence, note/file privacy, opt-in encryption, no plaintext persistence, encrypted download, lock/unlock, project resume, Persian RTL and zero application network calls. Tests use synthetic strings and files only. No real Android microphone, physical speaker, Google account, MCP third-party access or live host is claimed.

The portable companion is a separate output and **does not change the previously published no-cost Render static pilot or its integrity-pinned service worker**. It does not merge the feature stack to `main`, touch production Railway or declare a new Seal.

## Self-critique and unresolved constraints

- The standalone file cannot replace a generative model, a search service or authenticated gateway. Those require separate, explicitly consented resources.
- Browser-side AES-GCM protects an at-rest archive against casual inspection, **not** a compromised active browser or device. File-origin storage may be partitioned differently across browsers or lost on app/file moves. The encrypted external backup requires actual user custody and an independently tested import to claim durable recovery.
- A synthetic Chrome `file://` PASS is not verification on the owner's Android handset; the produced artifact is a candidate until tested on an actual target device.
- Genuine Railway full offhost backup + isolated original-volume restore remain unproven under [Issue #104](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/104). Authenticated human live-host acceptance remains open under [Issue #70](https://github.com/maghsoodsaadatmerikation-sudo/nexus/issues/70).
- No forced main promotion, payment, new provider, original live volume operation or automatic final judgment. `A_out <= A_in`.

Stage 22's acceptance is **downloadable, reproducibly built, browser-tested, network-disabled offline project planning**. Nothing more.
