#!/usr/bin/env python3
"""Stage26 fail-closed, static equivalence and same-signer Android APK audit."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

class Blocked(Exception):
    pass

def require(ok, reason):
    if not ok:
        raise Blocked(reason)

def public_cert(value):
    found=re.search(r"(?m)^Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})\s*$",value)
    require(found is not None,"cert-digest-missing")
    return found.group(1)

def compare(original,resigned,inst,app_cert,test_cert):
    require(public_cert(app_cert)==public_cert(test_cert),"instrumentation-not-signed-like-app")
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(resigned) as dst,zipfile.ZipFile(inst) as tst:
        names=lambda z:{item.filename for item in z.infolist() if not item.filename.startswith("META-INF/")}
        original_names=names(src)
        require(original_names==names(dst),"app-entries-changed-on-emulator")
        for name in original_names:
            require(src.read(name)==dst.read(name),"app-executable-drift")
        require("assets/nexus/index.html" in original_names,"offline-app-missing")
        require("classes.dex" in original_names,"android-app-code-missing")
        require("AndroidManifest.xml" in names(tst),"test-android-manifest-missing")
        require("classes.dex" in names(tst),"test-android-code-missing")
        require(not any(x.startswith("assets/") for x in names(tst)),
                "private-resource-in-test-runner")
        require(len(tst.read("classes.dex"))>3000,"empty-native-instrumentation")
        return {
            "schema":"nexus.stage26.android-runtime-pair.v1",
            "status":"VERIFIED_PAIR_FOR_ANDROID_EMULATOR",
            "app_compiled_bytes_equal":True,
            "app_permission_manifest_equal":True,
            "same_temporary_certificate":True,
            "test_certificate_sha256_public":public_cert(app_cert),
            "original_app_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),
            "resigned_emulator_app_sha256":hashlib.sha256(resigned.read_bytes()).hexdigest(),
            "instrumentation_apk_sha256":hashlib.sha256(inst.read_bytes()).hexdigest(),
            "real_android_emulator_executed":False,
            "real_android_hardware_executed":False,
            "provider_credentials_used":False,
            "production_released":False,
            "original_Railway_volume_restored":False,
        }

def main():
    p=argparse.ArgumentParser()
    for k in ("original","resigned","instrumentation","app-cert","test-cert"):
        p.add_argument("--"+k,required=True,type=Path)
    opts=p.parse_args()
    try:
        result=compare(opts.original,opts.resigned,opts.instrumentation,
                       opts.app_cert.read_text(),opts.test_cert.read_text())
        out=opts.resigned.parent/"stage26-emulator-apk-pair.json"
        out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        print("PASS: code/manifest/assets identical, two APKs share ephemeral signer")
    except (Blocked,OSError,ValueError,zipfile.BadZipFile) as exc:
        print("BLOCKED: stage26-signature-equivalence: "+str(exc)[:120],file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
