# NEXUS Mobile execution step — Studio + Motion on one Android phone

**Date:** 2026-11-18. **Scope:** candidate only; no production mutation.

## What this implements

NEXUS now has a proposed **single Android-local public-code ZIP** with two
separate applications under one fixed localhost origin and one start page:

- `http://127.0.0.1:8765/apps.html`: launcher with clear Studio/Motion links.
- `http://127.0.0.1:8765/`: existing Studio with conversations, encrypted
  opt-in projects, writing, data and music tools, optional model-provider
  bridge and offline Studio shell. It is the **unchanged** source-bound
  Studio phone kit, not a new back-end model or a ChatGPT-equivalent product.
- `http://127.0.0.1:8765/motion/`: the entire standalone browser NEXUS
  Motion editor with editable scene timeline, optional user photos/sound,
  procedural animations, short browser media recording and local MP4
  comparison. This is not neural text-to-video generation.

The server runs locally using Python 3 / Termux and binds **only**
`127.0.0.1`, never the internet/LAN. It allows GET and HEAD of exact
reviewed static files, refuses arbitrary paths, manifest/code downloads,
URL queries and POST/PUT/DELETE. All Studio files are SHA-256 verified
using the original strict `source-manifest.json`; all Motion files and
the app selector are verified by a separate `motion-integrity.json`
manifest before the listener starts. The manifests describe integrity
relative to a reviewed Git commit; they do **not** themselves attest to
a trusted source or offer cryptographic signatures.

## Actual Android instructions

The successful GitHub Action
[NEXUS Android Studio + Motion Offline-Local Distribution](https://github.com/maghsoodsaadatmerikation-sudo/nexus/actions/workflows/nexus-mobile-local.yml)
produces an artifact named `nexus-mobile-studio-motion-local`. It contains
`nexus-mobile-local.zip`, its independently printed `.sha256` file, and
the builder's JSON receipt. Ensure the run refers to the intended reviewed
source commit. Download this artifact from GitHub on the Android phone.

From Termux installed from a trusted source:

```sh
pkg install python unzip
cd "$HOME"
unzip /path/to/nexus-mobile-local.zip
cd nexus-mobile-local
python3 run-nexus.py
```

Then open **`http://127.0.0.1:8765/apps.html`** in the phone's browser.
Both Studio and Motion are served by the same loopback process. To stop,
return to Termux and use Ctrl+C. Do not run from a public working
directory containing secrets. Use the system's file picker when explicitly
selecting private photos or audio in Motion; no media uploads are implemented
in the local server.

If port 8765 is already in use, use `python3 run-nexus.py --port 8766` and
open the **new** origin. **WARNING:** a changed port creates a different
browser origin, so existing Studio encrypted storage/service worker may
not be accessible there. Maintain separately encrypted Studio backups.

The bundled Studio's original self-check remains at
`http://127.0.0.1:8765/device-check.html` and does **not** certify Motion
while Termux is stopped. Studio's service-worker cache remains untouched;
Motion is served from localhost only while the local server runs. This
package is **not** an APK, a cloud service or a persistent Android background
daemon. Closing/killing Termux can stop the app. Browsers/Android versions
differ in MediaRecorder codecs, RAM and permissions.

## Large video limitation

The ZIP includes only Motion's **browser** static editor and its local
capture capability. It does not include FFmpeg, model weights, ML GPUs,
Python long-form rendering scripts or a video render queue daemon.
For continuous 1080p/4K MP4 and checkpointed video construction, separately
obtain the reviewed repository source and install FFmpeg/ffprobe. All
such exports are user-initiated and subject to battery, disk and memory.
No 4K/60fps throughput test on a real Android device has passed.

## Why this route avoids unsafe deployment

Read-only inspection of connected production Railway on 2026-11-18
identified the active Stage D `nexus-stage-d` runtime as **SLEEPING**, not
healthy/always-on, with a mounted production `/data` volume and **two
pending staged settings** (healthcheck path `/` to `/readyz`, and a
sleep setting shown as true→true). The Railway source deployment pointed
at an older commit than current GitHub main. The disconnected second
Railway project contains no services. This mobile ZIP deliberately
**does not** accept those staged production changes or restart/deploy the
sleeping service. Separate operator review, restore witness and explicit
approval are needed for any production cutover.

## CI and release boundary

The read-only workflow `.github/workflows/nexus-mobile-local.yml`:

1. Checks pinned Studio static bundle, Python/JavaScript syntax and Motion
   deterministic timeline tests.
2. Creates the entire package repeatedly to compare byte-identical ZIPs.
3. Opens the actual extracted package on an ephemeral loopback HTTP server,
   checks both apps and resource MIME types, and rejects unknown paths,
   queries, HTTP writes and manifest/script downloads.
4. Mutates one Motion and one Studio file in turn; server must fail
   **before listening**. Incorrect source SHA or unexpected ZIP members
   must also be rejected.
5. Emits a downloadable ZIP, independent SHA-256 and source commit receipt
   **only if all previous steps pass**. CI tests Linux loopback, not a
   particular Android phone or optional on-device model.

There is no change to `main`, production data, Render/Railway deploys,
secrets, tokens, required status checks or paid infrastructure. This
is a stacked **draft** on the Motion PR chain, not a production release.

## Engineering gaps remaining

- Actual Android/Termux hardware acceptance, background/battery behavior,
  and secure on-device storage checks.
- Connection to a real configured generative model if requested and
  explicitly authorized; none is embedded in this ZIP.
- Motion's long-form FFmpeg scripts are still separate from the simple
  browser-only mobile package.
- Security review and deliberate integration of PR #290–#296 before
  changing `main`, plus independent Railway production readiness checks.
