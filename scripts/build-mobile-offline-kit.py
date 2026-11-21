#!/usr/bin/env python3
"""Build and verify a deterministic, user-downloadable NEXUS single-file mobile kit.

Never includes personal workspaces, credentials, generated chat content,
production evidence or a release Seal. Does not deploy any service.
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
SOURCE = ROOT / "web/offline-pilot.html"
ARCHIVE_SCHEMA = "nexus.offline-mobile-kit.v1"
MAX_SOURCE = 1024 * 1024
MAX_ZIP = 2 * 1024 * 1024
APP = "NEXUS-offline.html"
README = "START-HERE.txt"
MANIFEST = "MANIFEST.json"
ALLOWED = {APP, README, MANIFEST}
COMMIT = re.compile(r"[0-9a-f]{40}\Z")

GUIDE = """NEXUS — standalone mobile decision workshop
NEXUS — کارگاه مستقل تصمیم‌سازی برای گوشی

ENGLISH
1. Extract this ZIP using the Files app on your phone or computer.
2. Open NEXUS-offline.html in a browser that supports local HTML and WebCrypto.
   If the Files app only shows source code, use its Open with/browser option.
3. Choose Language at the top of the page. English is the default; Persian
   is bundled. No signup, server account or model API key is needed.
4. Try the clearly labeled synthetic demonstration, then create a new
   workspace. NEXUS does not make your decision.
5. Save an encrypted export to private storage and verify that you can
   re-open your actual downloaded export. Keep the password separately.
6. Phone browsers differ: local HTML, Downloads and encryption may be
   unsupported or restricted. If opening the file fails, use the existing
   HTTPS pilot instead: https://nexus-offline-pilot.onrender.com/
7. The HTML runs locally. This bundle is NOT an APK, hosted AI, a verified
   production recovery backup or a server-connected edition.

فارسی
۱. فایل ZIP را در برنامهٔ فایل‌های گوشی یا رایانه از حالت فشرده خارج کنید.
۲. فایل NEXUS-offline.html را در مرورگری که فایل HTML محلی و WebCrypto
   را پشتیبانی می‌کند باز کنید. اگر فقط کد دیده می‌شود، «باز کردن با مرورگر»
   را انتخاب کنید.
۳. زبان را از بالای صفحه انتخاب کنید. انگلیسی پیش‌فرض و فارسی موجود است.
   حساب کاربری، سرور یا کلید API لازم نیست.
۴. نمونهٔ ساختگی را آزمایش کنید و سپس کارگاه جدید بسازید. تصمیم نهایی با شماست.
۵. خروجی رمزگذاری‌شده بگیرید و بازشدن همان فایل دانلودشده را آزمایش کنید.
   گذرواژه را جدا و امن نگه دارید.
۶. بازکردن فایل HTML و رمزنگاری در همهٔ مرورگرهای گوشی تضمین‌شده نیست.
   در صورت مشکل از نسخهٔ HTTPS استفاده کنید:
   https://nexus-offline-pilot.onrender.com/
۷. این بسته APK، هوش مصنوعی میزبانی‌شده، پشتیبان واقعی محیط تولید یا
   نسخهٔ متصل به درگاه NEXUS نیست.

INTEGRITY / صحت فایل
Compare the HTML SHA-256 with source_sha256 in MANIFEST.json.
The manifest is a checksum record, NOT a cryptographic signature.
GitHub CI verifies this exact ZIP against the tracked source revision.
Archive contains only three public files and no personal user data.
"""


class PackageBlocked(ValueError):
    pass


def require(ok, message="invalid-mobile-kit"):
    if not ok:
        raise PackageBlocked(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, "duplicate-json-field")
        out[k] = v
    return out


def nonfinite(_):
    raise PackageBlocked("nonfinite-json")


def check_source(data):
    require(type(data) is bytes and 0 < len(data) <= MAX_SOURCE, "invalid-app-size")
    text = data.decode("utf-8")
    for required in ('<!doctype html>', "connect-src 'none'", "nexus.offline-pilot",
                     'Content-Security-Policy', 'type="password"'):
        require(required.lower() in text.lower(), "unrecognized-local-app")
    require("<script" in text.lower(), "not-a-runnable-app")


def source_revision():
    value = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        stderr=subprocess.DEVNULL, timeout=4, text=True).strip()
    require(COMMIT.fullmatch(value) is not None, "unknown-source-revision")
    return value


def make_manifest(source, sha):
    require(type(sha) is str and COMMIT.fullmatch(sha) is not None, "invalid-source-sha")
    check_source(source)
    return {
        "schema": ARCHIVE_SCHEMA,
        "source_revision": sha,
        "source_path": "web/offline-pilot.html",
        "source_sha256": digest(source),
        "source_bytes": len(source),
        "files": sorted(ALLOWED),
        "format": "single-file-local-html",
        "contains_user_data": False,
        "requires_server": False,
        "production_verified": False,
        "production_backup": False,
        "release_authorized": False,
        "authority": "none",
    }


def build_bytes(source, sha):
    manifest = make_manifest(source, sha)
    files = {
        APP: source,
        README: GUIDE.encode("utf-8"),
        MANIFEST: (json.dumps(manifest, sort_keys=True,
                              ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"),
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=True) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info._compresslevel = 9
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name])
    encoded = output.getvalue()
    require(len(encoded) <= MAX_ZIP, "oversized-package")
    return encoded


def inspect_bytes(encoded, expected_html, expected_sha):
    require(type(encoded) is bytes and 0 < len(encoded) <= MAX_ZIP, "oversized-package")
    check_source(expected_html)
    require(type(expected_sha) is str and COMMIT.fullmatch(expected_sha), "invalid-commit")
    try:
        with zipfile.ZipFile(io.BytesIO(encoded), "r") as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            require(len(infos) == len(ALLOWED) and set(names) == ALLOWED,
                    "unexpected-or-duplicate-archive-entry")
            for i in infos:
                require(not i.is_dir() and "/" not in i.filename and "\\" not in i.filename,
                        "unsafe-archive-entry")
                require((i.external_attr >> 16) == 0o100644 and
                        i.create_system == 3 and
                        i.date_time == (1980, 1, 1, 0, 0, 0),
                        "nonreproducible-archive-entry")
                require(i.file_size <= MAX_SOURCE and
                        i.compress_type == zipfile.ZIP_DEFLATED,
                        "unbounded-or-unexpected-entry")
            require(z.testzip() is None, "corrupt-archive")
            content = {n: z.read(n) for n in names}
    except (zipfile.BadZipFile, EOFError, RuntimeError, OverflowError):
        raise PackageBlocked("corrupt-archive") from None
    require(content[APP] == expected_html, "app-bytes-differ-from-source")
    require(content[README] == GUIDE.encode("utf-8"), "instructions-were-modified")
    manifest = json.loads(content[MANIFEST], object_pairs_hook=unique,
                          parse_constant=nonfinite)
    require(type(manifest) is dict and manifest == make_manifest(expected_html, expected_sha),
            "invalid-manifest")
    return {
        "schema": ARCHIVE_SCHEMA,
        "status": "VERIFIED_PUBLIC_SINGLE_FILE_KIT",
        "source_revision": expected_sha,
        "source_sha256": digest(expected_html),
        "zip_sha256": digest(encoded),
        "zip_bytes": len(encoded),
        "file_count": 3,
        "personal_data_included": False,
        "production_verified": False,
        "release_authorized": False,
        "authority": "none",
    }


def read_archive(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= MAX_ZIP, "unsafe-archive-file")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(MAX_ZIP + 1)
        after = os.fstat(fd)
        require(len(raw) <= MAX_ZIP and len(raw) == before.st_size
                and (before.st_dev, before.st_ino, before.st_size,
                     before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size,
                     after.st_mtime_ns, after.st_ctime_ns),
                "archive-changed-during-read")
        return raw
    finally:
        os.close(fd)


def publish_no_replace(destination, encoded):
    parent = destination.parent
    require(parent.is_dir() and not parent.is_symlink() and
            not destination.exists() and not destination.is_symlink(),
            "output-already-exists-or-unsafe")
    fd, temporary = tempfile.mkstemp(prefix=".nexus-kit-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.link(temporary, destination, follow_symlinks=False)
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=["build", "verify"])
    p.add_argument("archive", type=Path)
    args = p.parse_args()
    try:
        source = SOURCE.read_bytes()
        sha = source_revision()
        if args.operation == "build":
            encoded = build_bytes(source, sha)
            publish_no_replace(args.archive.absolute(), encoded)
        else:
            encoded = read_archive(args.archive)
        report = inspect_bytes(encoded, source, sha)
        print(json.dumps(report, sort_keys=True))
    except (ValueError, OSError, UnicodeError, TypeError, subprocess.SubprocessError):
        print("NEXUS OFFLINE MOBILE KIT: BLOCKED", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
