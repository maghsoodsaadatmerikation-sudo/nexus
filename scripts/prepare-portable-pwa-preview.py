#!/usr/bin/env python3
"""Render-safe static preview builder for NEXUS's immutable scoped PWA.

This script packages only public source assets; it never accesses runtime
credentials, production data, authenticated APIs or application state.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/build-portable-pwa-kit.py"
SPEC = importlib.util.spec_from_file_location("portable_pwa_build", SOURCE)
KIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KIT)

PUBLIC = {
    "nexus/index.html", "nexus/service-worker.js", "nexus/manifest.json",
    "nexus/icons/nexus-192.png", "nexus/icons/nexus-512.png",
    "nexus/PWA-KIT.json", "nexus/START-HERE.txt",
    "nexus/device-check.html",
}
ENTRY = ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>NEXUS isolated mobile preview</title></head>
<body style="font:1.1rem system-ui,sans-serif;max-width:42rem;margin:3rem auto;padding:1rem">
<h1>NEXUS Mobile Preview</h1>
<p>Public static beta. No account, online model, or production gateway.</p>
<p><a href="./nexus/">Open the installable NEXUS workshop</a></p>
<p><a href="./nexus/device-check.html">Check compatibility on your device (no data sent)</a></p>
<p lang="fa" dir="rtl">نسخه آزمایشی عمومی؛ بدون اتصال به اطلاعات تولید.
<a href="./nexus/">ورود به نسخهٔ قابل‌نصب</a></p>
<p>Prepare offline mode from inside the app; encrypted work exports remain yours.</p>
</body></html>
""").encode("utf-8")


def device_check_page(shell):
    template = (ROOT / "web/mobile-readiness.html").read_text("utf-8")
    marker = "__NEXUS_SHELL_SHA256__"
    KIT.require(template.count(marker) == 1, "diagnostic-hash-marker-drift")
    KIT.require("connect-src 'none'" in template and
                "worker-src 'none'" in template and
                "form-action 'none'" in template and
                "nexus.device-readiness.self-report.v1" in template and
                "navigator.serviceWorker.register(" not in template and
                "fetch(" not in template and
                "XMLHttpRequest" not in template,
                "diagnostic-privacy-contract-drift")
    result = template.replace(marker, KIT.digest(shell)).encode("utf-8")
    KIT.require(0 < len(result) < 60_000, "oversized-diagnostic")
    return result


def expected(commit):
    KIT.require(type(commit) is str and KIT.SHA.fullmatch(commit), "bad-source-sha")
    data = KIT.build_bytes(commit)
    KIT.inspect_bytes(data, commit)
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        packaged = PUBLIC - {"nexus/device-check.html"}
        KIT.require(len(names) == len(packaged) and set(names) == packaged,
                    "unexpected-preview-asset")
        site = {"index.html": ENTRY, **{name: archive.read(name) for name in names}}
        site["nexus/device-check.html"] = device_check_page(site["nexus/index.html"])
        KIT.require(set(site) == PUBLIC | {"index.html"}, "untracked-public-site-file")
        return site


def file_is_safe(root, path):
    current = root
    for part in path.parts:
        current = current / part
        KIT.require(not current.is_symlink(), "symlinked-preview-path")
    return current


def safe_output_dir(path):
    path = path.absolute()
    KIT.require(path.name not in ("", ".", "..") and not path.exists()
                and path.parent.is_dir() and not path.parent.is_symlink(),
                "preview-output-exists")
    KIT.require(path.parent.resolve() == path.parent, "unsafe-preview-parent")
    return path


def build(path, commit):
    path = safe_output_dir(path)
    records = expected(commit)
    path.mkdir(mode=0o755)
    for name, data in sorted(records.items()):
        file = file_is_safe(path, Path(name))
        file.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    return verify(path, commit)


def verify(path, commit):
    path = path.absolute()
    KIT.require(path.is_dir() and not path.is_symlink(), "preview-output-missing")
    records = expected(commit)
    observed = {}
    for item in path.rglob("*"):
        KIT.require(not item.is_symlink(), "unexpected-symlink")
        if item.is_file():
            KIT.require(stat.S_ISREG(item.stat().st_mode), "not-a-regular-file")
            relative = item.relative_to(path).as_posix()
            KIT.require(relative in records, "unexpected-preview-file")
            observed[relative] = item.read_bytes()
    KIT.require(observed == records, "preview-file-drift")
    receipt = json.loads(observed["nexus/PWA-KIT.json"])
    KIT.require(receipt["source_revision"] == commit
                and receipt["private_data"] is False
                and receipt["production_deployed"] is False
                and receipt["release_authorized"] is False
                and receipt["authority"] == "none", "unsafe-preview-manifest")
    return {
        "status": "PUBLIC_STATIC_PREVIEW_VERIFIED",
        "files": len(observed),
        "deployable_path": "nexus/",
        "candidate_sha": commit,
        "source_digest": receipt["source_html_sha256"],
        "private_data_included": False,
        "production_deployed": False,
        "release_authorized": False,
        "authority": "none",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("build", "verify"))
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        commit = KIT.revision()
        result = (build(args.destination, commit) if args.operation == "build"
                  else verify(args.destination, commit))
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, UnicodeError, TypeError):
        print("NEXUS PUBLIC STATIC PREVIEW: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
