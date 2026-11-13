#!/usr/bin/env python3
"""Strict parser for Android's actual instrumentation protocol (not synthetic CI)."""
import argparse
import json
import re
import sys
from pathlib import Path

class Refused(Exception):
    pass

REQUIRED_PROOF = (
    "native-launch", "local-asset-origin", "real-webview-crypto",
    "encrypted-idb-reopen", "human-review", "tamper-rejection",
    "document-open-save-pickers",
)

def require(condition, name):
    if not condition:
        raise Refused(name)

def witness(raw, pair):
    entries={}
    for line in raw.splitlines():
        if line.startswith("INSTRUMENTATION_RESULT: ") and "=" in line:
            item=line.removeprefix("INSTRUMENTATION_RESULT: ")
            name,value=item.split("=",1)
            require(name not in entries,"duplicate-result-field")
            entries[name]=value
    codes=re.findall(r"(?m)^INSTRUMENTATION_CODE: (-?\d+)\s*$",raw)
    require(codes==["-1"],"not-successful-Android-instrumentation")
    require(entries.get("schema")=="nexus.stage26.android-emulator.v1",
            "unexpected-emulator-report-schema")
    require(entries.get("status")=="PASS","runtime-instrumentation-failed")
    require(entries.get("real_android_emulator")=="true","emulator-not-proven")
    require(entries.get("real_android_hardware")=="false","hardware-unproven")
    require(entries.get("synthetic_only")=="true","unexpected-user-data")
    require(entries.get("original_Railway_data")=="not_accessed",
            "unreviewed-production-claim")
    require(entries.get("network_permission")=="none","network-permission")
    checks=entries.get("checks","")
    require(checks.isascii() and checks.isdigit() and
            15<=int(checks)<=80,"insufficient-runtime-checks")
    proof=entries.get("proof","").split(";")
    require(tuple(proof)==REQUIRED_PROOF,"runtime-proof-incomplete")
    require(pair.get("status")=="VERIFIED_PAIR_FOR_ANDROID_EMULATOR" and
            pair.get("same_temporary_certificate") is True and
            pair.get("app_compiled_bytes_equal") is True,
            "unverified-test-apk-pair")
    require(pair.get("real_android_emulator_executed") is False,
            "prior-run-claimed-hardware")
    return {
        "schema":"nexus.stage26.real-android-emulator.v1",
        "status":"ANDROID_EMULATOR_SYNTHETIC_ACCEPTANCE_PASS",
        "android_platform":"API_35_emulator",
        "origin":"https://appassets.androidplatform.net/nexus/index.html",
        "runtime_checks":int(checks),
        "verified_flows":proof,
        "reproducible_android_app_source":True,
        "encrypted_vault_reopened_after_activity_restart":True,
        "invalid_passphrase_and_modified_archive_rejected":True,
        "SAF_open_and_save_picker_intents_seen":True,
        "SAF_actual_document_bytes_written_and_read":False,
        "android_real_hardware_tested":False,
        "production_distribution_signed":False,
        "original_Railway_offhost_restore_proven":False,
        "human_authority":"human",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("--pair",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:
        data=witness(args.evidence.read_text(),
                     json.loads(args.pair.read_text()))
        args.out.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")
        print("PASS: independent actual Android API 35 WebView runtime witness")
        return 0
    except (Refused,OSError,ValueError) as exc:
        print("BLOCKED: Android runtime acceptance "+str(exc)[:100],file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
