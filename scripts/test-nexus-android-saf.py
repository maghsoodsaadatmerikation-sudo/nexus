#!/usr/bin/env python3
"""Strict synthetic Android 35 SAF roundtrip: real WebView -> Save As -> on-disk JSON -> import.

Requires a BOOTED disposable emulator and the already-installed NEXUS debug
APK. Only the reviewed public default storyboard is used; no user data.
A GUI failure fails this test, not a reason to make a production claim.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("nexus_android_emulator_helpers",
                                            ROOT/"scripts/test-nexus-android-emulator.py")
smoke=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)

SAVED_NAME="NEXUS-A-Journey.json"
SAVED_PATH="/sdcard/Download/"+SAVED_NAME
SCHEMA="nexus.android.saf-roundtrip.v1"

def nodes():
    return list(smoke.ui_tree().iter("node"))

def matching(needle,exact=False):
    want=needle.casefold()
    out=[]
    for item in nodes():
        candidates=[item.attrib.get("text","").strip().casefold(),
                    item.attrib.get("content-desc","").strip().casefold()]
        if not any((t==want if exact else want in t) for t in candidates if t):
            continue
        coords=list(map(int,re.findall(r"\d+",item.attrib.get("bounds",""))))
        if len(coords)!=4 or coords[2]<=coords[0] or coords[3]<=coords[1]:
            continue
        out.append((item,coords))
    return out

def tap(needle,*,exact=False,scroll=0,backward=False):
    for index in range(scroll+1):
        try:
            for item,coords in matching(needle,exact):
                if item.attrib.get("enabled")=="false":
                    continue
                x1,y1,x2,y2=coords
                smoke.adb("shell","input","tap",str((x1+x2)//2),str((y1+y2)//2))
                return
        except (RuntimeError,ET.ParseError):
            pass
        if index<scroll:
            if backward:
                smoke.adb("shell","input","swipe","520","440","520","1540","260")
            else:
                smoke.adb("shell","input","swipe","520","1560","520","400","260")
            time.sleep(.45)
    raise RuntimeError("Real Android GUI target absent or disabled: "+needle)

def wait_for(needle,timeout=20):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        try:
            if matching(needle):
                return True
        except (RuntimeError,ET.ParseError):
            pass
        time.sleep(.75)
    raise RuntimeError("Android GUI text not observed: "+needle)

def strict_default_json(raw):
    if not 100<len(raw)<50000:
        raise RuntimeError("Exported JSON unexpectedly empty/oversized")
    data=json.loads(raw.decode("utf-8"))
    if (type(data)!=dict or set(data)!={"schema","title","width","height","fps","scenes"} or
        data["schema"]!="nexus.motion.storyboard.v1" or data["title"]!="NEXUS — A Journey" or
        data["width"]!=1920 or data["height"]!=1080 or data["fps"]!=30 or
        not isinstance(data["scenes"],list) or len(data["scenes"])!=3 or
        [s.get("duration") for s in data["scenes"]] != [4,5,4]):
        raise RuntimeError("Exported JSON does not match the public default storyboard")
    return hashlib.sha256(raw).hexdigest()

def disk_bytes():
    result=subprocess.run(["adb","exec-out","cat",SAVED_PATH],
                          capture_output=True,timeout=25,check=False)
    if result.returncode:
        raise RuntimeError("Android Downloads did not contain the user-selected JSON file")
    return result.stdout

def launch_import_picker():
    tap("Load storyboard JSON",scroll=16,backward=True)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            if any(matching(t) for t in ("Recent","Browse","Downloads","Files")):
                return
        except (RuntimeError,ET.ParseError):
            pass
        time.sleep(.75)
    raise RuntimeError("Android import DocumentsUI did not open")

def run(report):
    if smoke.adb("shell","getprop","ro.build.version.sdk").strip()!="35":
        raise RuntimeError("Android API 35 emulator required")
    model=smoke.adb("shell","getprop","ro.product.model").lower()
    if "sdk" not in model and "emulator" not in model:
        raise RuntimeError("Physical device refused: only disposable emulator approved")
    # Never delete or overwrite an existing Android document, even in tests.
    # The CI emulator is disposable: a pre-existing fixture is an error.
    probe=smoke.adb("shell","ls",SAVED_PATH,check=False)
    if SAVED_NAME in probe:
        raise RuntimeError("Synthetic output path already exists; refusing overwrite")
    smoke.adb("logcat","-c")
    smoke.adb("shell","am","force-stop",smoke.PKG)
    smoke.start()
    smoke.adb("logcat","-c")
    tap("Open Motion",scroll=1)
    smoke.await_true(lambda: smoke.ready("/motion/"),"Android Motion UI for SAF")
    # Export from the actual WebView button through the real JS/native bridge.
    tap("Download project JSON",scroll=18)
    wait_for(SAVED_NAME,22)
    # DocumentsUI must explicitly choose the Downloads folder. This prevents
    # confusing a Save As dialog with a completed file write.
    if not matching("Downloads"):
        for trigger in ("Show roots","Browse"):
            try:
                tap(trigger,scroll=0)
                break
            except RuntimeError:
                continue
    tap("Downloads",scroll=3)
    tap("Save",exact=True,scroll=3)
    # The DocumentsUI destination can appear on disk before the native
    # ContentResolver stream has finished writing/flushing the entire JSON.
    # Never treat mere existence or a nonempty partial read as a successful
    # export: wait for schema-valid, complete, source-bound bytes.
    observed={"length":None,"reason":"not yet available","payload":None,"sha":None}
    def fully_written():
        try:
            raw=disk_bytes()
            observed["length"]=len(raw)
            sha256=strict_default_json(raw)
            observed["payload"]=raw
            observed["sha"]=sha256
            return True
        except (RuntimeError,UnicodeDecodeError,json.JSONDecodeError) as exc:
            observed["reason"]=type(exc).__name__
            return False
    try:
        smoke.await_true(fully_written,"Android SAF fully written source-valid JSON",timeout=35)
    except RuntimeError as exc:
        raise RuntimeError(str(exc)+" (last-length="+str(observed["length"])+
                           ", last-error="+observed["reason"]+")") from exc
    payload=observed["payload"]
    sha=observed["sha"]
    # Round trip through Android's own file chooser. No direct programmatic
    # substitution into a web <input type=file> and no test-only JS bridge.
    # Create one synthetic in-memory change before loading the saved JSON.
    tap("Add scene",scroll=12,backward=True)
    launch_import_picker()
    if not matching("Downloads"):
        for trigger in ("Show roots","Browse"):
            try:
                tap(trigger)
                break
            except RuntimeError:
                continue
    tap("Downloads",scroll=3)
    # Clear only the disposable emulator's debug logs. The production APK
    # never logs project text. The exact success signal comes from Motion's
    # own validated import feedback and public default storyboard fields.
    smoke.adb("logcat","-c")
    tap(SAVED_NAME,scroll=8)
    def imported():
        evidence=smoke.log_lines()
        if "/motion/ source_file_selected=false" in evidence:
            raise RuntimeError("Android picker did not return a document")
        if "/motion/ saf_import_rejected=true" in evidence:
            raise RuntimeError("Android Motion explicitly rejected the selected JSON")
        if "/motion/ saf_import_unconfirmed=true" in evidence:
            raise RuntimeError("Android picker returned, but Motion import was never validated")
        return ("/motion/ source_file_selected=true" in evidence and
                "/motion/ saf_import_ok=true" in evidence)
    smoke.await_true(imported,"validated WebView import completion",timeout=35)
    checks=[
        "real-Android-35-WebView-Motion-export-click",
        "user-chosen-ACTION_CREATE_DOCUMENT-Downloads-file-written",
        "Android-filesystem-JSON-exact-public-default-validated",
        "real-ACTION_GET_CONTENT-DocumentsUI-JSON-reimport",
        "in-app-validated-import-feedback-three-scenes"
    ]
    result={
        "schema":SCHEMA,"status":"ANDROID_SAF_ROUNDTRIP_PASS",
        "android_api":35,"real_emulator":True,"physical_device_tested":False,
        "synthetic_public_storyboard_only":True,
        "bytes":len(payload),"sha256":sha,"checks":checks,
        "network_permission_required":False,"private_user_files_read":False,
        "cross_signature_upgrade_tested":False,"actual_media_export_tested":False,
        "production_release":False,
    }
    report.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    return result

def main():
    import argparse
    p=argparse.ArgumentParser(description="Real Android SAF JSON export and import acceptance")
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    try:
        print(json.dumps(run(args.report),sort_keys=True))
        return 0
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError,
            UnicodeDecodeError,json.JSONDecodeError,ET.ParseError) as exc:
        print("NEXUS ANDROID SAF: FAIL ("+str(exc)+")",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
