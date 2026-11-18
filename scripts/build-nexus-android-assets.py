#!/usr/bin/env python3
"""Build bounded, source-pinned public NEXUS assets for a sandboxed Android APK.

No Python/Termux server in APK, no secrets, no user media. The native
Android app checks every embedded asset digest before opening a WebView.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
BUILDER=ROOT/"scripts/build-nexus-mobile-local.py"
spec=importlib.util.spec_from_file_location("nexus_android_source_bundle",BUILDER)
source=importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
SCHEMA="nexus.android.public-assets.v1"
SKIP={"source-manifest.json","motion-integrity.json","run-local.py",
      "run-nexus.py","README.txt","README-NEXUS.txt"}
TYPES={".html":"text/html",".js":"text/javascript",".mjs":"text/javascript",
       ".json":"application/json",".png":"image/png",".txt":"text/plain"}
LIMIT=500_000
CATALOG="nexus-catalog.json"


def sha(data: bytes)->str:
    return hashlib.sha256(data).hexdigest()


def assets(commit: str)->dict[str,bytes]:
    if not isinstance(commit,str) or not re.fullmatch("[0-9a-f]{40}",commit):
        raise ValueError("exact Git commit SHA is required")
    raw=source.source_assets(commit)
    old_message=(b"No server upload. This page is served only on 127.0.0.1 by Termux.\n"
                 b"Studio offline cache does not cover Motion.")
    if old_message not in raw["apps.html"]:
        raise ValueError("mobile launcher messaging changed")
    raw["apps.html"]=raw["apps.html"].replace(
        old_message,
        b"Native Android test app: offline public assets embedded in the APK. "
        b"No Termux server or external connection. Private projects remain local."
    )
    raw["android-export.js"]=(ROOT/"mobile/android/android-export.js").read_bytes()
    selected={}
    for name,data in raw.items():
        if name in SKIP:continue
        pieces=PurePosixPath(name).parts
        if (name.startswith("/") or ".." in pieces or "." in pieces or
            name.endswith("/") or name.startswith(".") or
            not all(re.fullmatch(r"[a-zA-Z0-9_.-]+",p) for p in pieces) or
            PurePosixPath(name).suffix not in TYPES or
            not isinstance(data,bytes) or not 0<len(data)<=LIMIT):
            raise ValueError("invalid public Android asset: "+name)
        selected[name]=data
    required={"apps.html","index.html","motion/index.html",
              "motion/motion-core.js","motion/motion-ui.js",
              "device/device-engine.js","motion/manifest.json",
              "service-worker.js","android-export.js"}
    if not required<=set(selected):
        raise ValueError("missing required Studio/Motion public assets")
    return selected


def catalog(data:dict[str,bytes],commit:str)->bytes:
    manifest={
        "schema":SCHEMA,"source_commit":commit,
        "no_network_permission":True,"no_user_data":True,
        "assets":{name:{"bytes":len(body),"sha256":sha(body),
                        "mime":TYPES[PurePosixPath(name).suffix]}
                  for name,body in sorted(data.items())}
    }
    return (json.dumps(manifest,sort_keys=True,separators=(",",":"))+"\n").encode()


def assemble(destination:Path,commit:str)->dict:
    if destination.is_symlink() or destination.exists():
        raise ValueError("refusing to overwrite existing assets")
    if not destination.parent.is_dir():
        raise ValueError("asset destination parent does not exist")
    src=assets(commit)
    destination.mkdir(mode=0o700)
    (destination/CATALOG).write_bytes(catalog(src,commit))
    for name,body in sorted(src.items()):
        target=destination/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("xb") as f:f.write(body)
    verify(destination,commit)
    return {"status":"VERIFIED_ANDROID_ASSETS","source_commit":commit,
            "assets":len(src),"public_only":True,
            "no_network_permission":True,"android_hardware_tested":False}


def verify(directory:Path,commit:str)->dict:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("invalid asset directory")
    p=directory/CATALOG
    if p.is_symlink() or not p.is_file() or p.stat().st_size>20000:
        raise ValueError("catalog missing or altered")
    def unique(pairs):
        d={}
        for key,value in pairs:
            if key in d:raise ValueError("duplicate JSON key")
            d[key]=value
        return d
    manifest=json.loads(p.read_bytes(),object_pairs_hook=unique)
    expected=assets(commit)
    if (manifest.get("schema")!=SCHEMA or
        manifest.get("source_commit")!=commit or
        manifest.get("no_network_permission") is not True or
        manifest.get("no_user_data") is not True or
        type(manifest.get("assets")) is not dict or
        set(manifest["assets"])!=set(expected)):
        raise ValueError("source/catalog contract mismatch")
    found={str(f.relative_to(directory)) for f in directory.rglob("*") if f.is_file()}
    if found!=set(expected)|{CATALOG}:
        raise ValueError("unreviewed file in Android APK asset tree")
    for name,body in expected.items():
        info=manifest["assets"][name]
        target=directory/name
        if (target.is_symlink() or not target.is_file() or
            type(info) is not dict or set(info)!={"bytes","sha256","mime"} or
            info["bytes"]!=len(body) or info["sha256"]!=sha(body) or
            info["mime"]!=TYPES[PurePosixPath(name).suffix] or
            target.read_bytes()!=body):
            raise ValueError("changed Android asset: "+name)
    return {"status":"EXACT_PUBLIC_ASSETS","commit":commit,"count":len(expected)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    try:
        result=(verify(args.output_dir,args.source_commit) if args.verify_only
                else assemble(args.output_dir,args.source_commit))
        print(json.dumps(result,sort_keys=True))
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print("NEXUS ANDROID PUBLIC ASSETS: BLOCKED ("+str(exc)+")",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
