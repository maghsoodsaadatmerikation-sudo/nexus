#!/usr/bin/env python3
"""Fail-closed APK structure, signing and permission audit (no Android device)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

def need(condition, label):
    if not condition:
        raise ValueError(label)


def audit(apk: Path,badging: str,permissions: str,public_cert: str,
          manifest_tree: str):
    source=Path("build/stage25-android/generated/nexus/index.html").read_bytes()
    with zipfile.ZipFile(apk) as archive:
        names=set(archive.namelist())
        need("AndroidManifest.xml" in names,"missing-binary-manifest")
        need("classes.dex" in names,"missing-dex")
        need("assets/nexus/index.html" in names,"missing-bundled-offline-html")
        need(not any(n.startswith("assets/") and n!="assets/nexus/index.html"
                       for n in names), "unexpected-private-asset")
        need(archive.read("assets/nexus/index.html")==source,"bundled-html-source-drift")
        need(any(n.startswith("res/") and n.endswith(".png") for n in names), "native-launcher-icon-absent")
        dex=archive.read("classes.dex")
        need(dex.startswith(b"dex\n"), "bad-dex-header")
        need(len(dex)>2000, "dex-too-small")
    need("package: name='org.nexus.offline.stage25'" in badging,"unexpected-package-id")
    need("targetSdkVersion:'35'" in badging,"bad-target-sdk")
    need("E: uses-sdk" in manifest_tree,"binary-uses-sdk-missing")
    need(re.search(r"(?m)^\\s+A: http://schemas.android.com/apk/res/android:minSdkVersion\\(0x[0-9a-f]+\\)=26\\s*$",manifest_tree) is not None,
         "binary-min-sdk-not-26")
    need(re.search(r"(?m)^\\s+A: http://schemas.android.com/apk/res/android:targetSdkVersion\\(0x[0-9a-f]+\\)=35\\s*$",manifest_tree) is not None,
         "binary-target-sdk-not-35")
    need(not re.search(r"(?m)^uses-permission",permissions),"manifest-requests-permissions")
    need("Signer #1 certificate SHA-256 digest" in public_cert,"signer-digest-missing")
    need(len(apk.read_bytes())>15000,"apk-too-small")
    return {
        "schema":"nexus.stage25.android-sdk-apk-witness.v1",
        "status":"SIGNED_TEST_APK_STATIC_CHECKS_PASS",
        "apk_sha256":hashlib.sha256(apk.read_bytes()).hexdigest(),
        "apk_bytes":apk.stat().st_size,
        "packaged_html_sha256":hashlib.sha256(source).hexdigest(),
        "cert_sha256_public":re.search(
             r"Signer #1 certificate SHA-256 digest: ([a-f0-9]+)",public_cert).group(1),
        "manifest_permissions":[],
        "native_internet_permission":False,
        "signed_by_ephemeral_test_certificate":True,
        "updates_require_uninstall_or_same_key":True,
        "actual_android_hardware_tested":False,
        "actual_android_emulator_tested":False,
        "google_play_published":False,
        "github_pages_enabled":False,
        "railway_production_mutation":False,
        "release_seal":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apk",type=Path,required=True)
    p.add_argument("--badging",type=Path,required=True)
    p.add_argument("--permissions",type=Path,required=True)
    p.add_argument("--public-cert",type=Path,required=True)
    p.add_argument("--manifest-tree",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:
        result=audit(a.apk,a.badging.read_text(),a.permissions.read_text(),
                     a.public_cert.read_text(),a.manifest_tree.read_text())
        a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        print("PASS: signed standalone APK, no declared Android permissions, exact offline HTML")
    except (OSError,AssertionError,ValueError,KeyError,AttributeError,
            zipfile.BadZipFile) as exc:
        print("BLOCKED: Android native APK audit ("+str(exc)[:85]+")",
              file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
