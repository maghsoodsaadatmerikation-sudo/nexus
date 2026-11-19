#!/usr/bin/env python3
"""Real Android emulator: install, open pages, reinstall without clearing user app data.

Requires a RUNNING Android emulator; never claims to test physical hardware,
user credentials, camera, mic, long-form video or a production-signing upgrade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PKG = "org.nexus.mobile"
ACTIVITY = PKG + "/.MainActivity"
TAG = "NEXUS_ANDROID_SMOKE"
WAIT_SECONDS = 55
RESULT_SCHEMA = "nexus.android.emulator-ui-acceptance.v1"


def adb(*args: str, timeout: float = 25, check: bool = True) -> str:
    result = subprocess.run(
        ["adb", *args], capture_output=True, timeout=timeout,
        check=False,
    )
    if check and result.returncode:
        raise RuntimeError("ADB rejected operation " + " ".join(args[:3]) +
                           " (exit " + str(result.returncode) + "): " +
                           result.stderr.decode("utf-8", "replace")[-250:])
    return result.stdout.decode("utf-8", "replace")


def await_true(predicate, label: str, timeout: float = WAIT_SECONDS) -> None:
    cutoff = time.monotonic() + timeout
    while time.monotonic() < cutoff:
        if predicate():
            return
        time.sleep(1)
    raise RuntimeError("Android emulator evidence unavailable: " + label)


def log_lines() -> str:
    return adb("logcat", "-d", "-s", TAG + ":I", "*:S", timeout=15)


def ready(page: str) -> bool:
    return (TAG + ": " + page + " ready=true") in log_lines()


def start() -> None:
    command = adb("shell", "am", "start", "-W", "-n", ACTIVITY, timeout=30)
    if "Error" in command or "Exception" in command:
        raise RuntimeError("Android Activity start failed")
    await_true(lambda: ready("/apps.html"), "app chooser JavaScript DOM readiness")


def ui_tree() -> ET.Element:
    adb("shell", "uiautomator", "dump", "/sdcard/nexus-emulator-ui.xml", timeout=35)
    raw = adb("exec-out", "cat", "/sdcard/nexus-emulator-ui.xml", timeout=20)
    if not raw.lstrip().startswith("<?xml") and not raw.lstrip().startswith("<hierarchy"):
        raise RuntimeError("Android UIAutomator did not produce an XML hierarchy")
    return ET.fromstring(raw)


def tap_link(needle: str) -> None:
    for index in range(5):
        try:
            tree = ui_tree()
            for node in tree.iter("node"):
                title = (node.attrib.get("text", "") + " " +
                         node.attrib.get("content-desc", ""))
                if needle.lower() not in title.lower():
                    continue
                bounds = node.attrib.get("bounds", "")
                coords = re.findall(r"\d+", bounds)
                if len(coords) != 4:
                    continue
                x1, y1, x2, y2 = map(int, coords)
                if x2 <= x1 or y2 <= y1:
                    continue
                adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
                return
        except (ET.ParseError, RuntimeError):
            pass
        if index == 4:
            break
        adb("shell", "input", "swipe", "480", "1300", "480", "360", "350", timeout=15)
        time.sleep(1)
    raise RuntimeError("Real UI did not expose an actionable link: " + needle)


def package_private_file() -> bytes:
    # The emulator creates *synthetic* private bytes. No real user data or
    # private archive is ever copied to/from CI.
    adb("shell", "run-as", PKG, "mkdir", "-p", "files")
    adb("shell", "run-as", PKG, "dd", "if=/dev/zero",
        "of=files/nexus-emulator-upgrade-witness.bin", "bs=64", "count=1")
    record = subprocess.run(
        ["adb", "exec-out", "run-as", PKG, "cat",
         "files/nexus-emulator-upgrade-witness.bin"],
        capture_output=True, check=True, timeout=20,
    ).stdout
    if record != bytes(64):
        raise RuntimeError("emulator private app data did not match synthetic witness")
    return record


def installed_permissions() -> None:
    output = adb("shell", "dumpsys", "package", PKG, timeout=30)
    if "Package [" + PKG + "]" not in output and "pkg=" + PKG not in output:
        raise RuntimeError("NEXUS package not present in Android package manager")
    section = output.split("requested permissions:", 1)
    if len(section) == 2:
        section = section[1].split("install permissions:", 1)[0]
        section = section.split("User 0:", 1)[0]
        if "android.permission.INTERNET" in section or "android.permission.READ_EXTERNAL_STORAGE" in section:
            raise RuntimeError("unexpected native APK dangerous/network permission")


def run(apk: Path, out: Path) -> dict:
    if not apk.is_file() or apk.suffix != ".apk" or apk.stat().st_size < 50_000:
        raise RuntimeError("actual compiled Android APK required")
    version = adb("shell", "getprop", "ro.build.version.sdk").strip()
    if version != "35":
        raise RuntimeError("expected Android API 35, got " + version)
    if "emulator" not in adb("shell", "getprop", "ro.product.model").lower() and \
       "sdk" not in adb("shell", "getprop", "ro.product.model").lower():
        raise RuntimeError("this automated acceptance must run on a synthetic emulator")
    adb("logcat", "-c")
    adb("install", "-r", str(apk), timeout=75)
    installed_permissions()
    adb("shell", "am", "force-stop", PKG)
    start()
    checks = ["installed-and-real-native-activity-opened",
              "actual-WebView-public-chooser-DOM-ready"]
    adb("logcat", "-c")
    tap_link("Open Motion")
    await_true(lambda: ready("/motion/"), "Motion canvas + script executed")
    checks.append("real-WebView-Motion-canvas-and-engine-ready")
    # Use the visible in-page All tools link, not just browser history.
    adb("logcat", "-c")
    tap_link("All tools")
    await_true(lambda: ready("/apps.html"),
               "Motion All tools link returned to the real chooser")
    checks.append("Motion-to-chooser-visible-home-link")
    adb("logcat", "-c")
    tap_link("Open Motion")
    await_true(lambda: ready("/motion/"),
               "Motion reopened from the real chooser")
    # Android should genuinely return to native chooser, without internet.
    adb("logcat", "-c")
    adb("shell", "input", "keyevent", "4")
    await_true(lambda: ready("/apps.html"), "Android back-button restored app chooser")
    checks.append("Android-back-button-returns-to-chooser")
    adb("logcat", "-c")
    tap_link("Open Studio")
    await_true(lambda: ready("/"), "Studio chat container loaded in WebView")
    checks.append("real-WebView-Studio-chat-DOM-ready")
    screenshot=out.parent / "nexus-android-emulator-studio.png"
    subprocess.run(["adb", "exec-out", "screencap", "-p"],
                   check=True, stdout=screenshot.open("wb"), timeout=20)
    if not screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Android emulator UI screenshot was not a valid PNG")
    checks.append("real-emulator-Studio-screen-captured")
    marker=package_private_file()
    sha=hashlib.sha256(marker).hexdigest()
    adb("shell", "am", "force-stop", PKG)
    # Same signed build. This proves reinstall does NOT clear Android's
    # app-private data. This is NOT a proof of cross-key app upgrades.
    adb("install", "-r", str(apk), timeout=75)
    check=subprocess.run(
        ["adb", "exec-out", "run-as", PKG, "cat",
         "files/nexus-emulator-upgrade-witness.bin"],
        capture_output=True, timeout=20, check=True,
    ).stdout
    if hashlib.sha256(check).hexdigest() != sha or check != marker:
        raise RuntimeError("app-private synthetic file was lost during reinstall")
    checks.append("reinstall-with-same-debug-signature-preserves-private-data")
    adb("logcat", "-c")
    start()
    checks.append("reinstalled-APK-still-launches-real-WebView")
    logs=adb("logcat", "-d", timeout=20)
    if re.search(r"FATAL EXCEPTION:.*?org\.nexus\.mobile", logs, flags=re.S):
        raise RuntimeError("NEXUS fatal Java exception detected in emulator logs")
    checks.append("no-NEXUS-main-thread-fatal-crash")
    result={
        "schema":RESULT_SCHEMA, "status":"EMULATOR_RUNTIME_PASS",
        "source_apk_sha256":hashlib.sha256(apk.read_bytes()).hexdigest(),
        "api_level":int(version), "checks":checks,
        "real_android_emulator":True, "physical_android_device_tested":False,
        "native_page_navigation_verified":True,
        "upgrade_same_signature_data_preserved":True,
        "upgrade_different_signature_tested":False,
        "saf_export_tested":False,
        "on_device_video_recording_tested":False,
        "permissions_granted":False,
        "production_deployment":False,
    }
    out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n")
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description="NEXUS actual Android emulator UI acceptance")
    parser.add_argument("apk", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(run(args.apk, args.report), sort_keys=True))
        return 0
    except (RuntimeError, subprocess.SubprocessError, OSError, ET.ParseError) as exc:
        print("NEXUS EMULATOR ACCEPTANCE: FAILED (" + str(exc) + ")", file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
