#!/usr/bin/env python3
"""Build a one-file, network-disabled NEXUS Work Mode companion.

The portable edition retains human-reviewed tasks, local files and optional
AES-GCM archives. Its server-assisted conversation panel is removed from
view AND its only HTTP transport call is removed from executable code.
No provider configuration or production credential is needed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web" / "work-mode.html"
CORE = ROOT / "web" / "work-mode-core.js"
SCRIPT_TAG = '<script src="/work-mode-core.js"></script>'
CHAT_BEGIN = "$('send').onclick=async()=>{"
CHAT_END = "\n$('keep-reply').onclick="
ASSIST_BEGIN = '<section class="full"><h2 data-k="assist">'
CSP_OLD = "connect-src 'self'"
CSP_NEW = "connect-src 'none'"
BANNER = (
    '<section id="portable-mode" aria-label="Portable offline mode" '
    'style="border:2px solid #14675a">'
    '<strong>Offline portable Work Mode · حالت کار آفلاین</strong>'
    '<p>No account, server, search, plugin, sync, or external network call. '
    'Use your own projects, notes, files and explicit human review; '
    'save an encrypted archive and download a separate encrypted backup. '
    'An unsaved tab can lose work.</p>'
    '<p dir="rtl" lang="fa">بدون اتصال اینترنت، حساب کاربری، جست‌وجو، افزونه یا '
    'همگام‌سازی. پروژه‌ها و فایل‌ها فقط در همین مرورگر هستند. '
    'ذخیره و دانلود نسخهٔ پشتیبان رمزنگاری‌شده به انتخاب شماست؛ '
    'کار ذخیره‌نشده ممکن است از دست برود.</p></section>'
)


class BuildBlocked(ValueError):
    pass


def one(value, old, new, name):
    if value.count(old) != 1:
        raise BuildBlocked("unexpected-" + name + "-source")
    return value.replace(old, new)


def assemble(page, core):
    if len(page.encode()) > 160_000 or len(core.encode()) > 60_000:
        raise BuildBlocked("source-size-out-of-bounds")
    if "</script" in core.lower() or "<script" in core.lower():
        raise BuildBlocked("unsafe-inline-core")
    if page.count("fetch(") != 1:
        raise BuildBlocked("server-transport-shape-changed")
    if page.count("<script") != 2:
        raise BuildBlocked("unexpected-script-count")
    if not page.lower().startswith("<!doctype html>"):
        raise BuildBlocked("unexpected-document")
    page = one(page, SCRIPT_TAG, "<script>\n" + core + "\n</script>", "external-core")
    page = one(page, CSP_OLD, CSP_NEW, "csp")
    page = one(page, ASSIST_BEGIN,
               '<section class="full" hidden aria-hidden="true"><h2 data-k="assist">',
               "remote-assist-panel")
    first, remainder = page.split(CHAT_BEGIN, 1)
    if remainder.count(CHAT_END) != 1:
        raise BuildBlocked("remote-assist-handler-changed")
    _transport, remainder = remainder.split(CHAT_END, 1)
    page = first + "$('send').onclick=()=>status('chatFailed');" + CHAT_END + remainder
    nav_pattern = re.compile(r"<nav>[^<]*(?:<[^>]+>[^<]*)*</nav>")
    navs = list(nav_pattern.finditer(page))
    if len(navs) != 1:
        raise BuildBlocked("navigation-shape-changed")
    page = page[:navs[0].start()] + (
        "<nav>Standalone, locally operated · مستقل و بدون سرور</nav>"
    ) + page[navs[0].end():]
    page = one(page, "<main><nav>",
               "<main>" + BANNER + "<nav>", "main")
    if ("fetch(" in page or "<script src=" in page or "<link rel=" in page
        or "<iframe" in page or "<form " in page
        or CSP_NEW not in page or 'id="portable-mode"' not in page):
        raise BuildBlocked("portable-offline-safety-invariant")
    if not all(token in page for token in (
        "NexusWorkMode", "indexedDB", "vault.create", "vault.save",
        "vault.restore", "vault.backup", 'id="file"', 'id="tasks"'
    )):
        raise BuildBlocked("required-local-capability-missing")
    output = page.encode("utf-8")
    if not 10_000 < len(output) < 180_000:
        raise BuildBlocked("portable-output-size-out-of-bounds")
    return output


def make_manifest(data, page, core):
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    return {
        "schema": "nexus.stage22.portable-work-mode.v1",
        "edition": "offline_single_html",
        "sha256": sha(data),
        "bytes": len(data),
        "work_mode_html_sha256": sha(page),
        "work_mode_core_sha256": sha(core),
        "network": "CSP_connect_src_none_and_no_fetch",
        "archive": "opt_in_aes_gcm_browser_storage",
        "source_of_truth": "web/work-mode.html + web/work-mode-core.js",
        "external_providers": False,
        "production_deployment": False,
        "railway_volume_captured": False,
        "release_seal": False,
        "authority": "human",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--check", action="store_true",
                        help="regenerate in RAM, compare exact existing artifact")
    opts = parser.parse_args()
    try:
        page = PAGE.read_bytes()
        core = CORE.read_bytes()
        result = assemble(page.decode("utf-8"), core.decode("utf-8"))
        manifest = (json.dumps(make_manifest(result, page, core),
                               sort_keys=True, indent=2) + "\n").encode()
        if opts.check:
            if opts.out.read_bytes() != result or opts.manifest.read_bytes() != manifest:
                raise BuildBlocked("artifact-mismatch")
        else:
            for path, data in ((opts.out, result), (opts.manifest, manifest)):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        print("STAGE22 PORTABLE WORK MODE: PASS"
              if opts.check else "STAGE22 PORTABLE WORK MODE: BUILT")
        return 0
    except (BuildBlocked, OSError, UnicodeError) as exc:
        print("STAGE22 PORTABLE WORK MODE: BLOCKED (" + str(exc) + ")",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
