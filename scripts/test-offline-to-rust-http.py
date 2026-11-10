#!/usr/bin/env python3
"""Synthetic-only bridge acceptance: Chromium-exported JSON -> real Rust API.

Never accepts production credentials, remote URLs or actual user files.
All server requests target the ephemeral 127.0.0.1 Docker listener.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

IMAGE = "nexus-pilot-06:ci"
REPORT = "pilot-06-rust-bridge-report.json"
PROVENANCE = "offline-bridge:user-supplied-unattested"


def require(cond, label):
    if not cond:
        raise AssertionError(label)


def docker(*args, timeout=90):
    run = subprocess.run(["docker", *map(str, args)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    require(run.returncode == 0, "disposable-docker-failed")


def request(port, method, route, bearer=None, body=None):
    require(route.startswith("/v1/") and "//" not in route and
            ".." not in route and "?" not in route, "unsafe-route")
    content = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    headers={"cache-control": "no-store"}
    if bearer is not None:
        headers["authorization"] = "Bearer " + bearer
    if content is not None:
        headers["content-type"] = "application/json"
    req=urllib.request.Request(
        "http://127.0.0.1:" + str(port) + route,
        data=content, headers=headers, method=method)
    try:
        response=urllib.request.urlopen(req,timeout=8)
    except urllib.error.HTTPError as err:
        response=err
    with response:
        data=response.read(2*1024*1024+1)
        require(len(data) <= 2*1024*1024, "oversized-response")
        return response.status, json.loads(data)


def ready(port):
    stop=time.monotonic()+60
    while time.monotonic()<stop:
        try:
            req=urllib.request.Request("http://127.0.0.1:"+
                                       str(port)+"/readyz")
            with urllib.request.urlopen(req,timeout=3) as r:
                if r.status==200 and json.load(r)=={"status":"ready"}:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.3)
    raise AssertionError("rust-gateway-not-ready")


def main():
    require(os.getenv("GITHUB_ACTIONS")=="true", "ci-only")
    require(os.getenv("NEXUS_BRIDGE_DISPOSABLE")=="true", "disposable-only")
    require(not any(os.getenv(k) for k in
                    ("RAILWAY_TOKEN","RAILWAY_API_TOKEN","RENDER_API_KEY",
                     "NEXUS_API_TOKEN")), "external-credential-present")
    run_id=os.getenv("GITHUB_RUN_ID", "")
    require(re.fullmatch(r"\d{1,15}",run_id)!=None,"bad-run-id")
    runner=Path(os.environ["RUNNER_TEMP"]).resolve()
    fixture=Path(os.environ["NEXUS_BRIDGE_SYNTHETIC_OUTPUT"])
    require(fixture.is_file() and fixture.parent.resolve()==runner and
            fixture.stat().st_size < 600_000, "untrusted-fixture-location")
    snap=json.loads(fixture.read_text())
    w=snap["workspace"]
    require(snap["schema_version"]==1 and
            w["question"]=="آیا این گزینه برای من مناسب است؟" and
            w["judgment"]["decision"]=="انتخاب آگاهانهٔ من" and
            len(w["claims"])==2 and len(w["alternatives"])==1 and
            len(snap["events"])==5 and
            all(x["provenance_id"]==PROVENANCE for x in snap["events"]),
            "not-exact-synthetic-browser-fixture")
    require(w["claims"][1]["origin"]=="MachineAnalysis" and
            snap["events"][2]["kind"].get("ClaimAdded") is not None,
            "machine-claim-forged-analysis-event")
    require(not Path(REPORT).exists(), "existing-report")
    token=secrets.token_urlsafe(48)
    port=32000+int(run_id[-4:])
    name="nexus-p06-"+run_id
    scratch=Path(tempfile.mkdtemp(prefix="nexus-p06-core-",dir=runner))
    storage=scratch/"data"
    storage.mkdir()
    storage.chmod(0o777) # docker's unprivileged UID 10001
    phase="start"
    started=False
    try:
        docker("run","-d","--name",name,
               "-p",f"127.0.0.1:{port}:3000",
               "-e","NEXUS_API_TOKEN="+token,
               "-e","NEXUS_DATA_DIR=/data",
               "-e","NEXUS_BIND_ADDR=0.0.0.0:3000",
               "--mount",f"type=bind,source={storage},target=/data",
               IMAGE,timeout=60)
        started=True
        ready(port)
        phase="auth-gate"
        route="/v1/workspaces/import"
        code, _ = request(port,"POST",route,body=snap)
        require(code==401,"unauthenticated-import-accepted")
        code, _ = request(port,"POST",route,bearer="synthetic-wrong-token",body=snap)
        require(code==401,"wrong-bearer-accepted")
        phase="exact-rust-import"
        code, imported=request(port,"POST",route,bearer=token,body=snap)
        require(code==201 and imported==snap,"rust-import-rejected-browser-json")
        workspace_route="/v1/workspaces/"+w["id"]
        code, saved=request(port,"GET",workspace_route,bearer=token)
        require(code==200 and saved==snap,"rust-persistence-differed")
        code, _ =request(port,"POST",route,bearer=token,body=snap)
        require(code==409,"duplicate-import-was-not-denied")
        phase="reject-audit-forgery"
        bad=json.loads(json.dumps(snap))
        bad["events"][-1]["kind"]["HumanJudgmentTransition"]["current"]["decision"]="forged"
        code, _=request(port,"POST",route,bearer=token,body=bad)
        require(code==422,"tampered-audit-succeeded")
        phase="restart-retain"
        docker("stop","-t","8",name,timeout=35)
        docker("rm",name,timeout=35)
        started=False
        docker("run","-d","--name",name,
               "-p",f"127.0.0.1:{port}:3000",
               "-e","NEXUS_API_TOKEN="+token,
               "-e","NEXUS_DATA_DIR=/data",
               "-e","NEXUS_BIND_ADDR=0.0.0.0:3000",
               "--mount",f"type=bind,source={storage},target=/data",
               IMAGE,timeout=60)
        started=True
        ready(port)
        code, after=request(port,"GET",workspace_route,bearer=token)
        require(code==200 and after==snap,"bridge-import-did-not-survive-restart")
        report={
            "schema":"nexus.pilot06.synthetic-bridge.v1",
            "status":"PASS_REAL_RUST_IMPORT_OF_BROWSER_RECONSTRUCTION",
            "scope":"local-ci-rust-docker-synthetic-only",
            "browser_generated_schema_accepted":True,
            "missing_and_wrong_bearer_denied":True,
            "import_creates_new_workspace":True,
            "duplicate_conflict":True,
            "audit_tampering_rejected":True,
            "human_judgment_not_machine_generated":True,
            "provenance_explicitly_unattested":True,
            "survived_disposable_restart":True,
            "source_workspace_sha256":hashlib.sha256(
                json.dumps(snap,ensure_ascii=False,sort_keys=True,
                           separators=(",",":")).encode()).hexdigest(),
            "user_content_uploaded_to_ci":False,
            "production_gateway_contacted":False,
            "production_backup_proven":False,
            "external_host_independence_proven":False,
            "human_authenticated_live_pilot":False,
            "production_mutation":False,
            "authority":"none","seal":False
        }
        with open(REPORT,"x",encoding="utf8") as f:
            json.dump(report,f,indent=2,sort_keys=True)
            f.write("\n")
        print("NEXUS PILOT 06: REAL RUST IMPORT OF SYNTHETIC BROWSER BRIDGE PASS")
    except Exception as error:
        print("PILOT 06 BLOCKED phase="+phase+
              " exception="+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if started:
            subprocess.run(["docker","rm","-f",name],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           timeout=40,check=False)


if __name__=="__main__":
    main()
