#!/usr/bin/env python3
"""Build deterministic phone-local NEXUS Studio ZIP; public assets only.

No production Railways/Render changes; no user data, keys, cookies, model
weights, credentials or real provider client are included. The included
launcher serves only reviewed public assets on IPv4 loopback.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public/studio"
BUNDLE = "nexus-studio-phone-local"
STAMP = (2020, 1, 1, 0, 0, 0)
SOURCE_NAMES = (
    "index.html",
    "service-worker.js",
    "manifest.json",
    "icons/nexus-192.png",
    "icons/nexus-512.png",
    "device/device-engine.js",
    "device/device-ui.js",
    "device/device-worker.js",
    "device/model-manifest.json",
    "device/vendor/LICENSE-jinja.txt",
    "device/vendor/LICENSE-onnxruntime.txt",
    "device/vendor/LICENSE-transformers.txt",
    "device/vendor/ort-wasm-simd-threaded.asyncify.mjs",
)
SCHEMA = "nexus.studio-phone-local-kit.v1"
CHECK_NAME = "device-check.html"
CHECK_SOURCE = ROOT / "scripts/studio-phone-fieldcheck.html"
README = """NEXUS Studio / Android offline-capable local edition
====================================================

A local web app you can open from a phone, without paid hosting and
without sharing its local project archive with the production server.

The ZIP contains only public Studio code, icons, licenses, service worker,
and a local-only Python launcher. It contains NO private data, no
Railway credentials, no model API key, no provider subscription, and NO
pre-downloaded large language-model weights.

Android Termux, or any trusted Python 3 installation:
  pkg install python unzip
  cd "$HOME"
  unzip /ABSOLUTE/PATH/nexus-studio-phone-local.zip
  cd nexus-studio-phone-local
  python3 run-local.py

Open in the SAME phone's browser:
  http://127.0.0.1:8765/

Then open the PHONE SELF-CHECK on the same device:
  http://127.0.0.1:8765/device-check.html

Tap 'Run private checks' for a no-upload browser/PWA/asset witness.
For an optional real-world note, manually tick the independent tests only
AFTER actually stopping the Termux server, disconnecting the internet and
reopening the main app; those checkmarks are OWNER-REPORTED, not verified.
Use the 'Save JSON locally' action only if you choose to share the
booleans and reviewed public-code hash. No device ID, IP address,
passphrase, user conversation or private content is collected or uploaded.

Create a project, talk to the LOCAL deterministic reflection guide, use
writing/data/code tools, and explicitly save a separately encrypted
browser archive (keep its passphrase and backup in private custody).
Select "Prepare offline use" to cache public app code. If supported,
the browser's "Install app"/"Add to Home screen" can then be used.
Installed PWA browser storage is bound to EXACT origin/port; switching
hosts, scheme or port starts a DIFFERENT archive. No automatic migration.

Without Termux/Python the above localhost URL does not serve pages; this
ZIP is NOT an installable APK. Closing Termux may stop the server; after
preparing offline code, service-worker support depends on the browser.
Do not rely on background service permanence or unsaved drafts.

The local launcher binds strictly to 127.0.0.1, never 0.0.0.0,
and serves a closed allowlist of the shipped public files.
The self-check page does not mutate app storage and its report is only
created on your phone after you choose Run and Save/Copy. Cached shell
readiness is not a proof that Studio ran while the Termux server was off. It refuses
POST, URL queries, unknown paths and modified public assets. Browser
functions that fetch external sources, optional on-device model weights,
or a separately configured model gateway require their own consent,
connectivity and correct configuration. No hosted generative model is
bundled; ChatGPT subscription is not an API key. On-device inference
depends on device capability and a separate opt-in model download.

The repository's main and the existing separately hosted Render Studio
are different origins. No production service, Railway Volume, Render
service, app-store account or paid resource is modified by this kit.

For code provenance, use a successful GitHub CI run on main and compare
its independently printed ZIP SHA-256 with the downloaded file.
The manifest inside a ZIP is NOT an independent signature.

Real CI Chromium tests the extracted ZIP at a localhost HTTP origin,
including encrypted archive reopen and a disconnected-network case.
It is not a real Android hardware or Termux acceptance test.
"""
LAUNCHER = r'''#!/usr/bin/env python3
"""Closed-world, public-assets-only NEXUS Studio server for localhost.

This server has no remote bind, user upload, private storage or network
fetching. The client application may independently request optional public
sources or explicitly configured providers, subject to the web app's controls.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import stat
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent
LIMIT = 450000
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
}


def load_public():
    manifest = json.loads((BASE / "source-manifest.json").read_bytes())
    if manifest.get("schema") != "nexus.studio-phone-local-kit.v1" or \
       manifest.get("authority") != "none" or \
       manifest.get("private_user_data_included") is not False:
        raise ValueError("untrusted package manifest")
    items = manifest.get("assets")
    if not isinstance(items, dict) or len(items) != 14:
        raise ValueError("unexpected public asset contract")
    assets = {}
    for name, expected in items.items():
        path = BASE / name
        if name.startswith("/") or ".." in Path(name).parts or \
           path.parent != path.parent.resolve():
            raise ValueError("unsafe public asset name")
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or path.is_symlink() or \
           not (0 < st.st_size <= LIMIT):
            raise ValueError("unsafe public asset type or length")
        payload = path.read_bytes()
        if len(payload) != expected["bytes"] or \
           hashlib.sha256(payload).hexdigest() != expected["sha256"]:
            raise ValueError("public asset mismatch")
        assets["/" + name] = payload
    return assets


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--port", type=int, default=8765)
    args = cli.parse_args()
    if not (1024 <= args.port <= 65535):
        raise SystemExit("PORT BLOCKED")
    try:
        assets = load_public()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise SystemExit("LOCAL PUBLIC PACKAGE VERIFICATION BLOCKED") from None
    assets["/"] = assets["/index.html"]

    class Handler(BaseHTTPRequestHandler):
        def reply(self, head=False):
            split = urlsplit(self.path)
            # Never serve a user-input path or arbitrary files in Termux HOME.
            name = split.path
            if split.query or split.fragment or "%" in name or name not in assets:
                self.send_error(404, "Public asset not found")
                return
            mime = MIME.get(Path("/index.html" if name == "/" else name).suffix)
            if mime is None:
                self.send_error(404, "Public asset unavailable")
                return
            data = assets[name]
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json" if name == "/manifest.json" else mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not head:
                self.wfile.write(data)

        def do_GET(self):
            self.reply()

        def do_HEAD(self):
            self.reply(head=True)

        def do_POST(self):
            self.send_error(405, "Read-only public code server")

        def do_PUT(self):
            self.send_error(405, "Read-only public code server")

        def do_DELETE(self):
            self.send_error(405, "Read-only public code server")

        def log_message(self, *_args):
            # Never print user path or browser request details to shared logs.
            return

    # 127.0.0.1 is deliberate: no LAN/public interface; no file upload.
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print("NEXUS Studio local-only ready: http://127.0.0.1:%d/" % args.port, flush=True)
        try:
            server.serve_forever(poll_interval=.2)
        except KeyboardInterrupt:
            print("Local NEXUS Studio server stopped.")


if __name__ == "__main__":
    main()
'''


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def public_assets():
    subprocess.run([sys.executable, str(ROOT / "scripts/build-studio-static.py"), "--check"],
                   check=True, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
    items = {}
    for name in SOURCE_NAMES:
        source = PUBLIC / name
        st = source.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or source.is_symlink() or \
           not (0 < st.st_size <= 450000):
            raise ValueError("public Studio asset is missing, linked or oversized")
        items[name] = source.read_bytes()
    html = items["index.html"]
    if b'id="studio-offline"' not in html or b"No model hosted here" not in html:
        raise ValueError("not the honest opt-in static Studio source")
    worker = items["service-worker.js"]
    if b"const EXPECTED_SHA256='" + sha(html).encode() + b"'" not in worker:
        raise ValueError("public Studio worker is not source hash-pinned")
    manifest = json.loads(items["manifest.json"])
    if manifest.get("scope") != "./" or manifest.get("start_url") != "./":
        raise ValueError("not a scoped PWA")
    return items


def phone_check_page(assets):
    """Reviewed, public-only HTML with exact build-time SHA-256 bindings."""
    source = CHECK_SOURCE
    st = source.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or source.is_symlink() or not (0 < st.st_size < 30000):
        raise ValueError("fieldcheck source type or length invalid")
    template = source.read_text(encoding="utf-8")
    if template.count("__APP_SHA256__") != 1 or template.count("__SW_SHA256__") != 1:
        raise ValueError("fieldcheck expected-digest placeholders missing")
    if "http://" in template or "https://" in template or "localStorage" in template or "indexedDB" in template:
        raise ValueError("fieldcheck cannot embed external network or private storage")
    result = template.replace("__APP_SHA256__", sha(assets["index.html"])).replace(
        "__SW_SHA256__", sha(assets["service-worker.js"]))
    if "</script>" not in result or "personal_data_collected:false" not in result:
        raise ValueError("fieldcheck minimal public safety contract missing")
    return result.encode("utf-8")


def contents(commit):
    if not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("exact lowercase Git source commit required")
    assets = public_assets()
    assets[CHECK_NAME] = phone_check_page(assets)
    manifest = {
        "schema": SCHEMA,
        "source_commit": commit,
        "assets": {name: {"bytes": len(data), "sha256": sha(data)} for name, data in sorted(assets.items())},
        "loopback_only": True,
        "private_user_data_included": False,
        "production_deploy_performed": False,
        "model_weights_included": False,
        "android_device_verified": False,
        "authority": "none",
    }
    return {
        **assets,
        "run-local.py": LAUNCHER.encode(),
        "README.txt": README.encode(),
        "source-manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
    }


def verify(zip_file, exact_commit=None):
    if not zip_file.is_file() or zip_file.is_symlink() or zip_file.stat().st_size > 900000:
        raise ValueError("ZIP missing or too large")
    with zipfile.ZipFile(zip_file, "r", allowZip64=False) as archive:
        infos = archive.infolist()
        if len(infos) != len(SOURCE_NAMES) + 4:
            raise ValueError("unexpected ZIP entry count")
        payloads = {}
        for info in infos:
            if info.flag_bits & 1 or info.is_dir() or \
               info.file_size > 450000 or info.compress_type != zipfile.ZIP_STORED:
                raise ValueError("unsupported ZIP entry")
            prefix = BUNDLE + "/"
            if not info.filename.startswith(prefix):
                raise ValueError("unexpected ZIP entry root")
            name = info.filename[len(prefix):]
            if name not in SOURCE_NAMES + (CHECK_NAME, "README.txt", "run-local.py", "source-manifest.json") or \
               name in payloads or ".." in PurePosixPath(name).parts or \
               not stat.S_ISREG(info.external_attr >> 16):
                raise ValueError("unsafe ZIP entry")
            payloads[name] = archive.read(info)
    item = json.loads(payloads["source-manifest.json"])
    commit = item.get("source_commit")
    if not isinstance(commit, str) or not re.fullmatch("[0-9a-f]{40}", commit) or \
       (exact_commit is not None and commit != exact_commit):
        raise ValueError("wrong ZIP source revision")
    if payloads != contents(commit):
        raise ValueError("ZIP content differs from reviewed public source")
    return True


def build(output, commit):
    if not output.is_absolute() or output.exists() or output.is_symlink() or \
       output.is_relative_to(ROOT) or ROOT.is_relative_to(output) or \
       not output.parent.is_dir() or output.parent != output.parent.resolve():
        raise ValueError("new canonical out-of-repo ZIP destination required")
    items = contents(commit)
    old_mask = os.umask(0o077)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as archive:
            for name, payload in sorted(items.items()):
                info = zipfile.ZipInfo(BUNDLE + "/" + name, date_time=STAMP)
                info.create_system = 3
                info.external_attr = (0o100644 << 16)
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, payload)
    finally:
        os.umask(old_mask)
    verify(output, exact_commit=commit)
    return sha(output.read_bytes())


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    action = cli.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--verify-zip", type=Path)
    cli.add_argument("--source-commit")
    args = cli.parse_args()
    try:
        if args.output:
            if not args.source_commit:
                raise ValueError("source commit required")
            print("NEXUS LOCAL STUDIO ZIP SHA-256: " + build(args.output, args.source_commit))
            print("Public code only; no production hosting or private user data copied.")
        else:
            verify(args.verify_zip, exact_commit=args.source_commit)
            print("NEXUS LOCAL STUDIO SOURCE-INTEGRITY PASS (not a digital signature)")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError,
            zipfile.BadZipFile, json.JSONDecodeError):
        print("NEXUS LOCAL STUDIO PACKAGING: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
