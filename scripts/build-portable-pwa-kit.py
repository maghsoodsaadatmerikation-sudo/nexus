#!/usr/bin/env python3
"""Build a relocatable, opt-in, integrity-bound NEXUS PWA static-site ZIP.

The package contains only public code, icons and instructions. It can be
hosted at any HTTPS path but cannot be installed from file://. No accounts,
tokens, user data, cloud writes or authority are included.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web/offline-pilot.html"
WORKER = ROOT / "public/service-worker.js"
WEB_MANIFEST = ROOT / "public/manifest.json"
ICONS = {size: ROOT / f"public/icons/nexus-{size}.png" for size in (192, 512)}
SCHEMA = "nexus.portable.installable-site.v1"
PREFIX = "nexus/"
FILES = {
    "index.html", "service-worker.js", "manifest.json",
    "icons/nexus-192.png", "icons/nexus-512.png",
    "PWA-KIT.json", "START-HERE.txt",
}
MAX_FILE = 500000
MAX_ARCHIVE = 850000
SHA = re.compile(r"[a-f0-9]{40}\Z")
README = """NEXUS scoped installable offline web app (English-first + فارسی)
----------------------------------------------------------------
This is a static PWA deployment bundle, NOT an Android APK or a file:// PWA.

1. Extract the ZIP. Upload CONTENTS of the nexus/ folder, unchanged,
   to a static HTTPS host such as an eligible GitHub Pages project directory,
   or upload nexus/ as a subfolder. The app supports any HTTPS path prefix.
2. Visit its HTTPS URL with a trailing slash, e.g. https://example.org/nexus/.
3. Click "Prepare offline mode". This opt-in caches only public app HTML.
4. Use the browser menu > Install app / Add to Home Screen when supported.
5. Reopen with airplane mode. Browser and Android support varies.
6. Export your workspace with a password separately; the app cache is NOT
   a workspace backup. Verify your downloaded encrypted file before relying.
7. Nothing in this kit connects to the NEXUS Rust gateway or hosts a model.
   Human judgment remains with the user (A_out <= A_in).

فارسی:
۱. فایل را استخراج کنید؛ محتوای پوشهٔ nexus را روی یک میزبان HTTPS
   استاتیک قرار دهید. برنامه در مسیر زیرپوشه هم کار می‌کند.
۲. آدرس HTTPS را باز کنید و «آماده‌سازی حالت آفلاین» را انتخاب کنید.
۳. از منوی مرورگر «نصب برنامه» یا «افزودن به صفحهٔ اصلی» را بزنید.
۴. حالت بدون اینترنت را روی گوشی خودتان آزمایش کنید.
۵. برای حفظ کار خود، جداگانه خروجی رمزگذاری‌شده بگیرید و صحت بازیابی
   فایل دانلودشده را کنترل کنید. کش برنامه پشتیبان اطلاعات شما نیست.

Only public files are included. PWA-KIT.json binds bytes to Git source
revision and SHA-256; this metadata is NOT an independent digital signature.
The CI witness is Chromium at localhost, not physical Android certification.
No production deployment, full-volume restore, human release decision or Seal.
"""


class KitBlocked(ValueError):
    pass


def require(ok, code="kit-blocked"):
    if not ok:
        raise KitBlocked(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    require(text.count(old) == 1, "source-anchor-changed")
    return text.replace(old, new)


def revision():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                     cwd=ROOT, stderr=subprocess.DEVNULL,
                                     text=True, timeout=5).strip()
    require(bool(SHA.fullmatch(commit)), "invalid-source-revision")
    return commit


def payloads(source=None, worker=None, manifest=None, icons=None):
    source = SRC.read_bytes() if source is None else source
    worker = WORKER.read_bytes() if worker is None else worker
    manifest = WEB_MANIFEST.read_bytes() if manifest is None else manifest
    icons = {size: path.read_bytes() for size, path in ICONS.items()} if icons is None else icons
    require(10000 < len(source) < MAX_FILE, "invalid-html-size")
    require(b"connect-src 'none'" in source and b"nexus.offline-pilot" in source,
            "unexpected-html-contract")
    base = source.decode("utf-8")
    base = replace_once(base, 'href="/manifest.json"', 'href="./manifest.json"')
    base = replace_once(
        base, "navigator.serviceWorker.register('/service-worker.js',{\n        scope:'/',",
        "navigator.serviceWorker.register('./service-worker.js',{\n        scope:'./',")
    base = replace_once(
        base, "ready.scope!==location.origin+'/'",
        "ready.scope!==new URL('./',location.href).href")
    base = replace_once(
        base, "navigator.serviceWorker.getRegistration('/')",
        "navigator.serviceWorker.getRegistration(new URL('./',location.href).href)")
    base = replace_once(base, "startsWith('nexus-app-shell-v12-')",
                        "startsWith('nexus-portable-'+encodeURIComponent(new URL('./',location.href).pathname)+'-v1-')")
    base = replace_once(base, "startsWith('nexus-app-shell-')",
                        "startsWith('nexus-portable-'+encodeURIComponent(new URL('./',location.href).pathname)+'-')")
    html = base.encode("utf-8")

    sw = worker.decode("utf-8")
    original_hash = digest(source)
    sw = replace_once(
        sw, "const EXPECTED_SHA256='" + original_hash + "';",
        "const EXPECTED_SHA256='" + digest(html) + "';")
    sw = replace_once(
        sw, "const CACHE_NAME='nexus-app-shell-v12-'+EXPECTED_SHA256.slice(0,16);",
        "const PREFIX='nexus-portable-'+encodeURIComponent(new URL('./',self.location.href).pathname)+'-';\n"
        "const CACHE_NAME=PREFIX+'v1-'+EXPECTED_SHA256.slice(0,16);")
    sw = replace_once(sw, "const ENTRY=new URL('/',self.location.origin).href;",
                      "const ENTRY=new URL('./',self.location.href).href;")
    sw = replace_once(sw, "x.startsWith('nexus-app-shell-')", "x.startsWith(PREFIX)")
    sw = replace_once(
        sw, "!['/','/index.html'].includes(target.pathname)||target.search",
        "![new URL(ENTRY).pathname,new URL('index.html',ENTRY).pathname].includes(target.pathname)||target.search")
    require("nexus-app-shell-" not in sw, "old-unscoped-cache-name")

    page = json.loads(manifest)
    require(page["start_url"] == page["scope"] == "/", "manifest-root-drift")
    require(page["display"] == "standalone", "manifest-not-installable")
    page["start_url"] = page["scope"] = "./"
    page["icons"] = [{**item, "src": "./icons/" + Path(item["src"]).name}
                     for item in page["icons"]]
    require({i["sizes"] for i in page["icons"]} == {"192x192", "512x512"},
            "icon-size-drift")
    result = {
        "index.html": html,
        "service-worker.js": sw.encode("utf-8"),
        "manifest.json": (json.dumps(page, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")) + "\n").encode(),
        "START-HERE.txt": README.encode("utf-8"),
    }
    for size, data in icons.items():
        require(size in ICONS and data[:8] == b"\x89PNG\r\n\x1a\n"
                and len(data) < 20000 and
                int.from_bytes(data[16:20], "big") == size and
                int.from_bytes(data[20:24], "big") == size,
                "invalid-app-icon")
        result[f"icons/nexus-{size}.png"] = data
    require(set(result) == FILES - {"PWA-KIT.json"}, "unrecognized-public-file-set")
    return result


def package_parts(parts, commit):
    require(type(commit) is str and SHA.fullmatch(commit), "bad-source-revision")
    require(set(parts) == FILES - {"PWA-KIT.json"}, "wrong-public-assets")
    receipt = {
        "schema": SCHEMA, "source_revision": commit,
        "source_html_sha256": digest(SRC.read_bytes()),
        "path_scope": "relative",
        "payload_sha256": {key: digest(value) for key, value in sorted(parts.items())},
        "private_data": False,
        "hosted_model": False,
        "production_deployed": False,
        "android_device_tested": False,
        "release_authorized": False, "authority": "none",
    }
    return {**parts, "PWA-KIT.json":
            (json.dumps(receipt, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":")) + "\n").encode("utf-8")}


def build_bytes(commit):
    pieces = package_parts(payloads(), commit)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        for name, raw in sorted(pieces.items()):
            info = zipfile.ZipInfo(PREFIX + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info._compresslevel = 9
            z.writestr(info, raw)
    content = buffer.getvalue()
    require(0 < len(content) <= MAX_ARCHIVE, "unbounded-package")
    return content


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate-metadata")
        result[key] = value
    return result


def inspect_bytes(content, commit):
    require(type(content) is bytes and 0 < len(content) <= MAX_ARCHIVE,
            "oversized-or-invalid-zip")
    expected = package_parts(payloads(), commit)
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            require(len(infos) == len(FILES) and set(names) ==
                    {PREFIX + item for item in FILES}, "unexpected-zip-members")
            for i in infos:
                require(i.filename.startswith(PREFIX) and
                        ".." not in i.filename and "\\" not in i.filename and
                        (i.external_attr >> 16) == 0o100644 and
                        i.create_system == 3 and
                        i.date_time == (1980, 1, 1, 0, 0, 0) and
                        i.file_size <= MAX_FILE and
                        i.compress_type == zipfile.ZIP_DEFLATED,
                        "unsafe-or-unstable-zip-entry")
            require(archive.testzip() is None, "zip-crc-error")
            actual = {name[len(PREFIX):]: archive.read(name) for name in names}
    except (zipfile.BadZipFile, EOFError, RuntimeError, OverflowError):
        raise KitBlocked("corrupt-zip") from None
    require(actual == expected, "source-or-asset-drift")
    receipt = json.loads(actual["PWA-KIT.json"], object_pairs_hook=no_duplicates)
    require(receipt["authority"] == "none" and
            receipt["release_authorized"] is False and
            receipt["private_data"] is False and
            receipt["production_deployed"] is False, "release-claim-expansion")
    return {
        "schema": SCHEMA, "status": "VERIFIED_PORTABLE_PWA_PACKAGE",
        "git_revision": commit, "zip_sha256": digest(content),
        "html_sha256": digest(actual["index.html"]),
        "files": len(actual), "zip_bytes": len(content),
        "production_deployed": False, "android_hardware_verified": False,
        "release_authorized": False, "authority": "none",
    }


def read_zip(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                0 < before.st_size <= MAX_ARCHIVE, "unsafe-zip-input")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(MAX_ARCHIVE + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and
                (before.st_dev, before.st_ino, before.st_size,
                 before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size,
                 after.st_mtime_ns, after.st_ctime_ns),
                "zip-changed-during-read")
        return raw
    finally:
        os.close(fd)


def publish(path, content):
    path = path.absolute()
    parent = path.parent
    require(parent.is_dir() and not parent.is_symlink()
            and not path.exists() and not path.is_symlink(),
            "destination-already-exists")
    fd, temp = tempfile.mkstemp(prefix=".nexus-portable-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.link(temp, path, follow_symlinks=False)
        d = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(d)
        finally:
            os.close(d)
    finally:
        os.unlink(temp)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=("build", "verify"))
    p.add_argument("archive", type=Path)
    args = p.parse_args()
    try:
        commit = revision()
        if args.operation == "build":
            data = build_bytes(commit)
            publish(args.archive, data)
        else:
            data = read_zip(args.archive)
        print(json.dumps(inspect_bytes(data, commit), sort_keys=True))
    except (OSError, ValueError, UnicodeError, TypeError, subprocess.SubprocessError):
        print("NEXUS PORTABLE PWA KIT: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
