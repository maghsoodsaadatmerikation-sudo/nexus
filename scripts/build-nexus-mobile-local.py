#!/usr/bin/env python3
"""Deterministic NEXUS Studio + Motion Android-local ZIP, no hosting mutation.

Reuses the independently tested hash-checked Studio package unchanged.
Adds only vetted static Motion assets plus a second hash-checked loader,
on the SAME 127.0.0.1:8765 origin. It does not expose the filesystem.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BASE_MODULE = ROOT / "scripts/build-studio-phone-local.py"
spec = importlib.util.spec_from_file_location("nexus_studio_base_phone_kit", BASE_MODULE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

BUNDLE = "nexus-mobile-local"
SCHEMA = "nexus.mobile-studio-motion.v1"
MOTION = (
    "motion/index.html", "motion/motion-core.js", "motion/motion-ui.js",
    "motion/offline-ui.js", "motion/offline-worker.js", "motion/manifest.json",
    "motion/icons/nexus-192.png", "motion/icons/nexus-512.png",
)
PAGE = "apps.html"
MANIFEST = "motion-integrity.json"
LAUNCHER_NAME = "run-nexus.py"
README_NAME = "README-NEXUS.txt"
EXTRA = MOTION + (PAGE, MANIFEST, LAUNCHER_NAME, README_NAME)
STAMP = (2020, 1, 1, 0, 0, 0)
MAX_ZIP = 2_000_000

README = """NEXUS MOBILE — Studio + Motion in one LOCAL package
==================================================

This is a source-bound, public-code-only Android/Termux kit.
No paid hosting, provider, API key, model weights, account, private
conversation or user media are bundled. No Render/Railway deployment.

On the same Android phone:
    pkg install python unzip
    cd "$HOME"
    unzip /path/to/nexus-mobile-local.zip
    cd nexus-mobile-local
    python3 run-nexus.py

In that phone's browser:
    http://127.0.0.1:8765/apps.html     (start page)
    http://127.0.0.1:8765/              (Studio/chat/music/writing)
    http://127.0.0.1:8765/motion/        (Motion/animation/video)

All files are SHA-256 verified BEFORE the local HTTP server starts.
The server binds ONLY 127.0.0.1 and refuses unknown files, queries
and POST/PUT/DELETE. The original Studio self-check still exists at
http://127.0.0.1:8765/device-check.html.

Motion supports original local photos, offline Canvas preview, and
short real-time local browser video export where the browser supports
MediaRecorder. It can compare a locally selected final MP4 against its
preview without uploading it. In Motion, tap "Prepare Motion offline" to
verify/cache PUBLIC app files. Only after preparation, use Chrome's menu
"Install app" or "Add to Home screen"; actual support varies by browser. For continuous high-quality 4K MP4,
the separate original NEXUS FFmpeg source scripts from the SAME reviewed
Git revision must be installed; this ZIP does not bundle FFmpeg or a
Python video renderer. Neither app has a trained text-to-video model.

Studio's service-worker scope is unchanged and covers its own existing
cache. Motion has a separate, opt-in, source-verified worker with
scope /motion/. After setup, it can reopen its PUBLIC editor code
without a running Termux server in browsers with ServiceWorker support.
This does not preserve imported user photos, audio or project state; save
a ZIP or JSON before closing. Studio encryption remains untouched.
This is a local web package, NOT an Android APK. Keeping Termux running
may require Android battery/background permissions. No model inference
or public HTTPS uptime is guaranteed.

The GitHub Actions artifact includes an independent ZIP SHA-256 and
a local browser witness. The manifest INSIDE the ZIP is not a signature.
Never copy a personal encrypted Studio archive into an unfamiliar app.
For long Motion renders, retain your original user assets separately.

User retains control of every export, release and action.
"""

APPS = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1427">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>NEXUS Mobile — Studio &amp; Motion</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#0b1427;color:#f4f7ff;font:1rem/1.55 system-ui,-apple-system,sans-serif}
main{max-width:740px;margin:auto;padding:1.25rem clamp(1rem,5vw,2rem) 3rem}
.skip{position:absolute;top:-100px;left:1rem;z-index:2;background:#fff;color:#14223b;padding:.5rem 1rem}
.skip:focus{top:.5rem}a:focus-visible,summary:focus-visible{outline:3px solid #f8da87;outline-offset:4px}
.eyebrow{color:#b1ebdf;font-weight:700;letter-spacing:.09em;text-transform:uppercase;font-size:.78rem}
h1{font-size:clamp(2rem,7vw,3rem);line-height:1.12;margin:.35rem 0 .65rem}
.intro{font-size:1.1rem;max-width:52ch;color:#dbe5f2}
nav{display:grid;gap:.85rem;margin:1.5rem 0}
.card{display:block;min-height:80px;padding:1rem 1.2rem;border-radius:16px;border:1px solid #526886;color:inherit;text-decoration:none;background:#15233d}
.card:active{background:#243b58}
.card.primary{background:#173b46;border:2px solid #9fe4d7}
.card-title{display:block;font-size:1.16rem;font-weight:750}
.card-detail{display:block;color:#d0deed;font-size:.93rem;margin-top:.2rem}
[lang="fa"]{display:block;direction:rtl;text-align:left;color:#c1d0df;font-size:.89rem;margin-top:.35rem}
.guide{border-top:1px solid #41536b;padding-top:1rem}
h2{font-size:1.14rem;margin:.6rem 0}
ol{padding-left:1.4rem}li{margin:.35rem 0}
details{border:1px solid #526886;border-radius:12px;padding:.75rem 1rem;margin:1rem 0}
summary{cursor:pointer;font-weight:650;min-height:48px;display:flex;align-items:center}
.privacy{color:#cbd9e8;font-size:.86rem}
@media(min-width:640px){nav{grid-template-columns:repeat(2,minmax(0,1fr))}.primary{grid-column:1/-1}}
@media(prefers-reduced-motion:no-preference){.card{transition:background-color .12s ease}}
</style></head><body>
<a class="skip" href="#tools">Skip to tools</a>
<main><header>
<p class="eyebrow">Private-first · On-device start</p>
<h1>NEXUS Mobile</h1>
<p class="intro">Start with one workspace. Choose what you want to create; advanced options can wait.</p>
<p lang="fa">از اینجا شروع کنید؛ ابزار موردنظرتان را انتخاب کنید.</p>
</header>
<nav id="tools" aria-label="NEXUS tools">
<a class="card primary" href="./">
<span class="card-title">Open Studio — Chat &amp; create</span>
<span class="card-detail">Conversations, music, writing and available studio tools.</span>
<span lang="fa">گفت‌وگو، موسیقی، نوشتن و ابزارهای استودیو</span></a>
<a class="card" href="./motion/">
<span class="card-title">Open Motion — Video &amp; animation</span>
<span class="card-detail">Make a storyboard, preview scenes, and use supported local exports.</span>
<span lang="fa">ساخت و پیش‌نمایش ویدیو و انیمیشن</span></a>
<a class="card" href="./device-check.html">
<span class="card-title">Check device — Is it ready?</span>
<span class="card-detail">Open the local compatibility self-check before a larger project.</span>
<span lang="fa">بررسی سازگاری و آمادگی دستگاه</span></a>
</nav>
<section class="guide" aria-labelledby="start-title">
<h2 id="start-title">Your first two minutes</h2>
<ol><li>Open Studio to start a conversation or creative task.</li>
<li>Use Motion when you need an animated scene or video preview.</li>
<li>Export important work yourself before clearing app data or changing installations.</li></ol>
<details><summary>What's saved on this device?</summary>
<p>Only features that explicitly offer local storage can keep your project. Studio and Motion have separate storage behavior. Offline app-code caching does not automatically preserve imported photos, audio, or drafts. Save your own copy before leaving.</p>
</details></section>
<footer><p class="privacy">No server upload. This page is served only on 127.0.0.1 by Termux.
Studio offline cache does not cover Motion.</p>
<p class="privacy">This launcher makes no network requests and contains no sign-in, tracking script, or user files.</p>
</footer></main></body></html>"""

# Reuse the exact existing, reviewed loopback-only HTTP server. All of the
# original 14 Studio files and their hash validation remain unmodified.
MOTION_LOADER = r'''
def load_motion():
    path = BASE / "motion-integrity.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("invalid motion manifest")
    manifest = json.loads(path.read_bytes())
    items = manifest.get("assets")
    names = ("motion/index.html", "motion/motion-core.js",
             "motion/motion-ui.js", "motion/offline-ui.js",
             "motion/offline-worker.js", "motion/manifest.json",
             "motion/icons/nexus-192.png", "motion/icons/nexus-512.png",
             "apps.html")
    studio = json.loads((BASE / "source-manifest.json").read_bytes())
    if (manifest.get("schema") != "nexus.mobile-studio-motion.v1" or
        manifest.get("source_commit") != studio.get("source_commit") or
        manifest.get("authority") != "none" or
        manifest.get("private_user_data_included") is not False or
        type(items) is not dict or set(items) != set(names)):
        raise ValueError("unexpected motion package contract")
    resources = {}
    for name in names:
        entry = items[name]
        file = BASE / name
        if (type(entry) is not dict or set(entry) != {"bytes", "sha256"} or
            type(entry["bytes"]) is not int or
            not 0 < entry["bytes"] <= 450000 or
            not isinstance(entry["sha256"], str) or
            not file.is_file() or file.is_symlink() or
            file.parent != file.parent.resolve()):
            raise ValueError("unsafe motion asset")
        info = file.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != entry["bytes"]:
            raise ValueError("motion file identity changed")
        data = file.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("motion asset integrity failed")
        resources["/" + name] = data
    resources["/motion/"] = resources["/motion/index.html"]
    return resources
'''


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_assets(commit: str) -> dict[str, bytes]:
    if type(commit) is not str or re.fullmatch("[0-9a-f]{40}", commit) is None:
        raise ValueError("exact lowercase 40-character Git commit required")
    baseline = base.contents(commit)
    page = (ROOT / "web/motion.html").read_text(encoding="utf-8")
    if page.count('href="/studio"') != 1:
        raise ValueError("Motion's Rust-only Studio link changed")
    page = page.replace('href="/studio"', 'href="/"')
    if (page.count("<title>") != 1 or
        page.count("<section><h2>Storyboard") != 1 or
        page.count("</body>") != 1 or
        page.count("connect-src 'none';") != 1):
        raise ValueError("Motion HTML offline-integration anchors changed")
    page = page.replace(
        "connect-src 'none';",
        "connect-src 'none'; worker-src 'self'; manifest-src 'self';",
    )
    page = page.replace(
        "<title>", '<link rel="manifest" href="./manifest.json">'
        '<meta name="theme-color" content="#0b1020"><title>',
    )
    panel = (
        '<section id="motion-offline-panel">'
        '<h2>Install / استفاده آفلاین</h2>'
        '<p class="muted">Cache only verified public Motion code on this phone. '
        'No photos, audio, drafts or exported movies are cached. '
        'The Studio offline copy is separate. / فقط کد عمومی ذخیره می‌شود.</p>'
        '<div class="row"><button id="motion-offline-prepare" class="secondary">'
        'Prepare Motion offline / آماده‌سازی آفلاین</button>'
        '<button id="motion-offline-remove" class="secondary">'
        'Remove offline copy / حذف نسخه آفلاین</button></div>'
        '<p id="motion-offline-status" role="status" aria-live="polite" '
        'class="muted small">Use your browser menu to install or add to home '
        'screen after preparation. The local app can still need Termux for '
        'new video sources, models or uncached features.</p></section>'
    )
    page = page.replace("<section><h2>Storyboard", panel + "<section><h2>Storyboard")
    page = page.replace("</body>", '<script src="./offline-ui.js"></script></body>')
    browser_manifest = {
        "id": "./", "name": "NEXUS Motion", "short_name": "Motion",
        "start_url": "./", "scope": "./", "display": "standalone",
        "lang": "en", "dir": "ltr", "background_color": "#0b1020",
        "theme_color": "#0b1020",
        "icons": [
            {"src": f"./icons/nexus-{size}.png", "sizes": f"{size}x{size}",
             "type": "image/png", "purpose": "any"}
            for size in (192, 512)
        ],
    }
    motion = {
        MOTION[0]: page.encode("utf-8"),
        MOTION[1]: (ROOT / "web/motion-core.js").read_bytes(),
        MOTION[2]: (ROOT / "web/motion-ui.js").read_bytes(),
        MOTION[3]: (ROOT / "web/motion-offline-ui.js").read_bytes(),
        MOTION[5]: (json.dumps(browser_manifest, sort_keys=True) + "\n").encode(),
        MOTION[6]: (ROOT / "public/icons/nexus-192.png").read_bytes(),
        MOTION[7]: (ROOT / "public/icons/nexus-512.png").read_bytes(),
        PAGE: APPS.encode("utf-8"),
    }
    public = []
    for name, data in sorted(motion.items()):
        if not name.startswith("motion/"):
            continue
        suffix = name.removeprefix("motion/")
        kind = (
            "html" if name.endswith(".html") else
            "javascript" if name.endswith(".js") else
            "json" if name.endswith(".json") else "png"
        )
        public.append({"path": suffix, "bytes": len(data),
                       "sha256": digest(data), "kind": kind})
    template = (ROOT / "web/motion-offline-worker-template.js").read_text()
    if template.count("/*STATIC_DESCRIPTOR__*/[]") != 1 or template.count("__VERSION__") != 1:
        raise ValueError("Motion offline worker template changed")
    assets_json = json.dumps(public, sort_keys=True, separators=(",", ":"))
    motion[MOTION[4]] = template.replace(
        "/*STATIC_DESCRIPTOR__*/[]", assets_json,
    ).replace("__VERSION__", digest(assets_json.encode())[:16]).encode()

    for name, data in motion.items():
        if not (0 < len(data) <= 450000):
            raise ValueError("motion public asset exceeds size budget")
    manifest = {
        "schema": SCHEMA,
        "source_commit": commit,
        "assets": {
            name: {"bytes": len(data), "sha256": digest(data)}
            for name, data in sorted(motion.items())
        },
        "authority": "none",
        "private_user_data_included": False,
        "android_hardware_verified": False,
        "production_deploy_performed": False,
    }
    launcher = base.LAUNCHER
    needle = "def main():\n"
    if launcher.count(needle) != 1:
        raise ValueError("base launcher entrypoint changed")
    launcher = launcher.replace(needle, MOTION_LOADER + "\n\n" + needle)
    old = '    assets["/"] = assets["/index.html"]'
    if launcher.count(old) != 1:
        raise ValueError("base launcher routing changed")
    launcher = launcher.replace(old, old + '\n    assets["/motion/"] = assets["/motion/index.html"]')
    opener = "        assets = load_public()"
    if launcher.count(opener) != 1:
        raise ValueError("base public asset verification flow changed")
    launcher = launcher.replace(opener, opener + '\n        assets.update(load_motion())')
    mime = 'Path("/index.html" if name == "/" else name).suffix'
    if launcher.count(mime) != 1:
        raise ValueError("base launcher MIME selection changed")
    launcher = launcher.replace(
        mime,
        'Path("/index.html" if name == "/" else '
        '"/motion/index.html" if name == "/motion/" else name).suffix'
    )
    original_mime = 'name == "/manifest.json" else mime'
    if launcher.count(original_mime) != 1:
        raise ValueError("base PWA manifest MIME routing changed")
    launcher = launcher.replace(
        original_mime,
        'name in ("/manifest.json", "/motion/manifest.json") else mime'
    )
    if '("127.0.0.1", args.port)' not in launcher:
        raise ValueError("base launcher bind boundary changed")
    output = {
        **baseline,
        **motion,
        MANIFEST: (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(),
        LAUNCHER_NAME: launcher.encode(),
        README_NAME: README.encode(),
    }
    assert set(output) == set(baseline) | set(EXTRA)
    return output


def verify(path: Path, commit: str | None = None) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_ZIP:
        raise ValueError("missing, symlinked or oversized mobile ZIP")
    with zipfile.ZipFile(path, "r", allowZip64=False) as archive:
        entries = archive.infolist()
        expected_names = set(base.SOURCE_NAMES + (
            base.CHECK_NAME, "run-local.py", "README.txt", "source-manifest.json"
        )) | set(EXTRA)
        if len(entries) != len(expected_names):
            raise ValueError("unexpected archive entry count")
        found = {}
        for info in entries:
            prefix = BUNDLE + "/"
            if (info.flag_bits & 1 or info.is_dir() or
                info.compress_type != zipfile.ZIP_STORED or
                info.file_size > 450000 or
                not info.filename.startswith(prefix)):
                raise ValueError("unsafe archive entry")
            name = info.filename[len(prefix):]
            if (name not in expected_names or name in found or
                ".." in PurePosixPath(name).parts or
                not stat.S_ISREG(info.external_attr >> 16)):
                raise ValueError("unknown, duplicate or linked archive member")
            found[name] = archive.read(info)
    original = json.loads(found["source-manifest.json"])
    source_sha = original.get("source_commit")
    if (not isinstance(source_sha, str) or
        re.fullmatch("[0-9a-f]{40}", source_sha) is None or
        (commit is not None and commit != source_sha)):
        raise ValueError("ZIP revision mismatch")
    if found != source_assets(source_sha):
        raise ValueError("source-bound NEXUS mobile ZIP bytes mismatch")
    return {"status": "VERIFIED_LOCAL_PUBLIC_CODE", "source_commit": source_sha,
            "sha256": digest(path.read_bytes()), "asset_count": len(found),
            "private_user_data": False, "production_deploy": False,
            "android_hardware_verified": False}


def build(path: Path, commit: str) -> dict:
    if (not path.is_absolute() or path.exists() or path.is_symlink() or
        path.is_relative_to(ROOT) or ROOT.is_relative_to(path) or
        not path.parent.is_dir() or path.parent != path.parent.resolve()):
        raise ValueError("new external absolute ZIP destination required")
    files = source_assets(commit)
    old_umask = os.umask(0o077)
    try:
        with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED,
                             allowZip64=False) as archive:
            for name, payload in sorted(files.items()):
                info = zipfile.ZipInfo(BUNDLE + "/" + name, date_time=STAMP)
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, payload)
    finally:
        os.umask(old_umask)
    return verify(path, commit)


def main() -> int:
    cli = argparse.ArgumentParser(description="Build or independently verify NEXUS local Android Studio+Motion")
    group = cli.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify-zip", type=Path)
    cli.add_argument("--source-commit", required=True)
    args = cli.parse_args()
    try:
        if args.output:
            result = build(args.output, args.source_commit)
        else:
            result = verify(args.verify_zip, args.source_commit)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AssertionError,
            zipfile.BadZipFile):
        print("NEXUS MOBILE LOCAL KIT: BLOCKED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
