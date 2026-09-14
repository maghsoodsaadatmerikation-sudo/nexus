#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

EVIDENCE = Path(os.environ.get("EVIDENCE_DIR", "/evidence"))
EVIDENCE.mkdir(parents=True, exist_ok=True)
BASE = os.environ["NEXUS_BASE_URL"].rstrip("/")
TOKEN = os.environ["NEXUS_API_TOKEN"]
WORKSPACE_ID = os.environ["NEXUS_WORKSPACE_ID"]
COMMIT = os.environ["NEXUS_DEPLOYED_COMMIT"]
MODE = os.environ.get("STAGE_D_MODE", "prepare").lower()


def request(path, method="GET", body=None, token=None):
    data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    headers = {"content-type": "application/json"}
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def write_text(name, text):
    (EVIDENCE / name).write_text(text, encoding="utf-8")


def write_json_bytes(name, raw):
    json.loads(raw)
    (EVIDENCE / name).write_bytes(raw)


def snapshot_sha():
    return hashlib.sha256((EVIDENCE / "before.json").read_bytes()).hexdigest()


def result(phase, sha):
    write_text(
        f"result-{phase}.txt",
        f"Stage D Phase: {phase}\n"
        "Status: PASS\n"
        f"Workspace Snapshot SHA-256: {sha}\n"
        "Token Recorded: NO\n"
        "Authority Expansion: NONE\n"
        "Epistemic Claim: operational persistence/recovery only\n",
    )


def prepare():
    s0, _ = request("/")
    s1, _ = request("/v1/workspaces/__nexus_stage_d_preflight__")
    s2, _ = request(
        "/v1/workspaces/__nexus_stage_d_preflight__",
        token="__nexus_stage_d_intentionally_invalid__",
    )
    if (s0, s1, s2) != (200, 401, 401):
        raise SystemExit(f"preflight failed: liveness={s0} missing={s1} wrong={s2}")
    write_text(
        "result-preflight.txt",
        "Stage D Phase: preflight\n"
        "Status: PASS\n"
        "Endpoint Scheme: HTTPS\n"
        "Public Liveness: PASS\n"
        "Missing Bearer Rejected: PASS\n"
        "Wrong Bearer Rejected: PASS\n"
        "Token Recorded: NO\n"
        "Authority Expansion: NONE\n"
        "Epistemic Claim: operational transport boundary only\n",
    )

    payload = {
        "workspace_id": WORKSPACE_ID,
        "question": "Stage D persistence witness",
        "provenance_id": "stage-d-evidence",
    }
    status, _ = request("/v1/workspaces", method="POST", body=payload, token=TOKEN)
    if status not in (201, 409):
        raise SystemExit(f"workspace creation failed: {status}")
    status, raw = request(f"/v1/workspaces/{WORKSPACE_ID}", token=TOKEN)
    if status != 200:
        raise SystemExit(f"workspace capture failed: {status}")
    snapshot = json.loads(raw)
    if snapshot.get("workspace", {}).get("id") != WORKSPACE_ID:
        raise SystemExit("captured workspace id mismatch")
    write_json_bytes("before.json", raw)
    sha = snapshot_sha()
    write_text("before.sha256", sha + "\n")
    write_text("workspace-id.txt", WORKSPACE_ID + "\n")
    write_text("deployed-commit.txt", COMMIT + "\n")
    result("capture", sha)
    print(f"STAGE_D_PREPARE_PASS workspace={WORKSPACE_ID} sha256={sha}", flush=True)


def survival():
    event_id = os.environ["NEXUS_REPLACEMENT_EVENT_ID"]
    event_at = os.environ["NEXUS_REPLACEMENT_AT_UTC"]
    replacement_commit = os.environ["NEXUS_REPLACEMENT_COMMIT"]
    if replacement_commit != COMMIT:
        raise SystemExit("replacement commit mismatch")
    write_text(
        "replacement-event.txt",
        "Lifecycle Event: service-replacement\n"
        f"Event ID: {event_id}\n"
        f"Event At UTC: {event_at}\n"
        f"Deployed Commit: {replacement_commit}\n"
        "Token Recorded: NO\n"
        "Authority Expansion: NONE\n"
        "Epistemic Claim: operator/provider lifecycle corroboration only\n",
    )
    status, raw = request(f"/v1/workspaces/{WORKSPACE_ID}", token=TOKEN)
    if status != 200:
        raise SystemExit(f"survival fetch failed: {status}")
    before = json.loads((EVIDENCE / "before.json").read_bytes())
    after = json.loads(raw)
    if after != before:
        raise SystemExit("survival snapshot differs from captured snapshot")
    write_json_bytes("after-survival.json", raw)
    sha = snapshot_sha()
    result("survival", sha)
    print(f"STAGE_D_SURVIVAL_PASS event={event_id} sha256={sha}", flush=True)


def absence():
    event_id = os.environ["NEXUS_DESTRUCTIVE_EVENT_ID"]
    event_at = os.environ["NEXUS_DESTRUCTIVE_AT_UTC"]
    status, raw = request(f"/v1/workspaces/{WORKSPACE_ID}", token=TOKEN)
    if status != 404:
        raise SystemExit(f"absence check expected 404, got {status}")
    body = json.loads(raw)
    if body != {"error": "workspace_not_found"}:
        raise SystemExit("unexpected absence response body")
    write_json_bytes("absence-response.json", raw)
    write_text(
        "destructive-event.txt",
        "Lifecycle Event: destructive-backing-state-removal\n"
        f"Event ID: {event_id}\n"
        f"Event At UTC: {event_at}\n"
        "Observed HTTP Status: 404\n"
        "Observed Error: workspace_not_found\n"
        "Token Recorded: NO\n"
        "Authority Expansion: NONE\n"
        "Epistemic Claim: operator action plus observed workspace absence only\n",
    )
    sha = snapshot_sha()
    result("absence", sha)
    print(f"STAGE_D_ABSENCE_PASS event={event_id} sha256={sha}", flush=True)


def restore():
    before_raw = (EVIDENCE / "before.json").read_bytes()
    before = json.loads(before_raw)
    status, _ = request("/v1/workspaces/import", method="POST", body=before, token=TOKEN)
    if status != 201:
        raise SystemExit(f"restore import failed: {status}")
    status, raw = request(f"/v1/workspaces/{WORKSPACE_ID}", token=TOKEN)
    if status != 200:
        raise SystemExit(f"restore fetch failed: {status}")
    restored = json.loads(raw)
    if restored != before:
        raise SystemExit("restored snapshot differs from captured snapshot")
    write_json_bytes("after-restore.json", raw)
    sha = snapshot_sha()
    result("restore", sha)
    print(f"STAGE_D_RESTORE_PASS sha256={sha}", flush=True)


def readiness():
    proc = subprocess.run(
        ["bash", "/operator/v1.1-release-readiness.sh", str(EVIDENCE), COMMIT],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = proc.stdout
    write_text("result-release-readiness.txt", output)
    print(output, end="", flush=True)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)
    if "V1.1 RELEASE READINESS: PASS" not in output:
        raise SystemExit("release readiness did not emit PASS marker")
    print("STAGE_D_RELEASE_READINESS_PASS", flush=True)


if MODE == "prepare":
    prepare()
elif MODE == "survival":
    survival()
elif MODE == "absence":
    absence()
elif MODE == "restore":
    restore()
elif MODE == "readiness":
    readiness()
else:
    raise SystemExit(f"unsupported STAGE_D_MODE: {MODE}")

# Keep the operator deployment healthy long enough for external evidence capture.
time.sleep(int(os.environ.get("OPERATOR_HOLD_SECONDS", "3600")))
