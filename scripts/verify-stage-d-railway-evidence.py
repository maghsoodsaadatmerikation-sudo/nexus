#!/usr/bin/env python3
"""Fail-closed verifier for committed Railway Stage D evidence.

This validates integrity, internal consistency, hygiene, and the recorded
independent review. It performs no network calls and grants no authority.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_DIR = Path("evidence/stage-d-588dc767-20261006")
REQUIRED_FILES = {
    "result-preflight.txt",
    "before.json",
    "before.sha256",
    "workspace-id.txt",
    "deployed-commit.txt",
    "result-capture.txt",
    "replacement-event.txt",
    "after-survival.json",
    "result-survival.txt",
    "absence-response.json",
    "destructive-event.txt",
    "result-absence.txt",
    "after-restore.json",
    "result-restore.txt",
}
PHASE_RESULTS = {
    "result-preflight.txt": "Stage D Phase: preflight",
    "result-capture.txt": "Stage D Phase: capture",
    "result-survival.txt": "Stage D Phase: survival",
    "result-absence.txt": "Stage D Phase: absence",
    "result-restore.txt": "Stage D Phase: restore",
}
CREDENTIAL_PATTERN = re.compile(
    rb"(authorization\s*:\s*bearer\s+\S+|NEXUS_API_TOKEN\s*=|password\s*=|secret\s*=)",
    re.IGNORECASE,
)


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"STAGE D RAILWAY EVIDENCE: BLOCKED — {message}")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"{path} must contain a JSON object")
    return value


def decode_files(pack: dict) -> dict[str, bytes]:
    files = pack.get("files")
    if not isinstance(files, dict):
        fail("files map missing")
    decoded: dict[str, bytes] = {}
    for name, entry in files.items():
        if not isinstance(name, str) or "/" in name or name in {".", ".."}:
            fail("invalid evidence filename")
        if not isinstance(entry, dict) or entry.get("encoding") != "base64":
            fail(f"{name} is not base64 encoded")
        encoded = entry.get("content_base64")
        if not isinstance(encoded, str):
            fail(f"{name} content is missing")
        if entry.get("base64_chars") != len(encoded):
            fail(f"{name} encoded length mismatch")
        try:
            decoded[name] = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            fail(f"{name} has invalid base64: {exc}")
    return decoded


def require_line(data: bytes, line: str, name: str) -> None:
    lines = data.decode("utf-8").splitlines()
    if line not in lines:
        fail(f"{name} missing exact marker: {line}")


def main() -> None:
    evidence_dir = Path(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_DIR
    if len(sys.argv) > 2:
        fail("usage: verify-stage-d-railway-evidence.py [evidence-dir]")

    pack_path = evidence_dir / "evidence-pack.json"
    review_path = evidence_dir / "independent-review.json"
    pack = load_json(pack_path)
    review = load_json(review_path)

    if pack.get("schema") != "nexus.stage-d-evidence-pack.v1":
        fail("unexpected evidence-pack schema")
    commit = pack.get("base_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        fail("invalid exact commit binding")
    run_id = pack.get("verification_run_id")
    if not isinstance(run_id, str) or not run_id.isdigit():
        fail("invalid verification run id")

    safeguards = pack.get("safeguards")
    expected_safeguards = {
        "authority_expansion": "NONE",
        "release_action_performed": "NO",
        "token_recorded": "NO",
        "primary_volume_deleted": False,
        "absence_method": "clean durable instance",
    }
    if safeguards != expected_safeguards:
        fail("safeguards changed or incomplete")

    decoded = decode_files(pack)
    missing = sorted(REQUIRED_FILES - decoded.keys())
    if missing:
        fail(f"missing required files: {', '.join(missing)}")
    if len(decoded) != 16:
        fail("evidence file count must remain exactly 16")

    for name, data in decoded.items():
        if CREDENTIAL_PATTERN.search(data):
            fail(f"credential-like material found in {name}")

    before = decoded["before.json"]
    digest = hashlib.sha256(before).hexdigest()
    recorded_digest = decoded["before.sha256"].decode("ascii").strip()
    if digest != recorded_digest or digest != pack.get("snapshot_sha256"):
        fail("snapshot SHA-256 mismatch")
    if before != decoded["after-survival.json"]:
        fail("replacement-survival snapshot differs")
    if before != decoded["after-restore.json"]:
        fail("restored snapshot differs")
    if json.loads(decoded["absence-response.json"]) != {"error": "workspace_not_found"}:
        fail("absence response is not exact workspace_not_found")

    workspace = json.loads(before).get("workspace", {}).get("id")
    if not isinstance(workspace, str) or not workspace:
        fail("workspace id missing from witness")
    if decoded["workspace-id.txt"].decode("utf-8").strip() != workspace:
        fail("workspace id binding mismatch")
    if pack.get("workspace_id") != workspace:
        fail("pack workspace id mismatch")
    if decoded["deployed-commit.txt"].decode("ascii").strip() != commit:
        fail("deployed commit file mismatch")

    for name, phase_marker in PHASE_RESULTS.items():
        require_line(decoded[name], phase_marker, name)
        require_line(decoded[name], "Status: PASS", name)
        require_line(decoded[name], "Token Recorded: NO", name)
        require_line(decoded[name], "Authority Expansion: NONE", name)

    require_line(decoded["result-preflight.txt"], "Endpoint Scheme: HTTPS", "result-preflight.txt")
    require_line(decoded["result-preflight.txt"], "Missing Bearer Rejected: PASS", "result-preflight.txt")
    require_line(decoded["result-preflight.txt"], "Wrong Bearer Rejected: PASS", "result-preflight.txt")
    require_line(decoded["replacement-event.txt"], "Lifecycle Event: service-replacement", "replacement-event.txt")
    require_line(decoded["replacement-event.txt"], f"Deployed Commit: {commit}", "replacement-event.txt")
    require_line(decoded["destructive-event.txt"], "Observed HTTP Status: 404", "destructive-event.txt")
    require_line(decoded["destructive-event.txt"], "Observed Error: workspace_not_found", "destructive-event.txt")
    require_line(decoded["result-release-readiness.txt"], "V1.1 RELEASE READINESS: PASS", "result-release-readiness.txt")
    require_line(decoded["result-release-readiness.txt"], "Release Action Performed: NO", "result-release-readiness.txt")

    if review.get("schema") != "nexus.stage-d-independent-review.v1":
        fail("unexpected independent-review schema")
    if review.get("result") != "PASS":
        fail("independent review is not PASS")
    subject = review.get("subject", {})
    if subject.get("base_commit") != commit or subject.get("verification_run_id") != run_id:
        fail("independent review subject binding mismatch")
    if subject.get("evidence_pack_blob_sha") != "046803044a280664e72908f1d049fc437ee3566b":
        fail("independent review does not bind the original pack blob")
    checks = review.get("checks", {})
    if checks.get("snapshot_sha256_recomputed") != digest:
        fail("independent review digest mismatch")
    if checks.get("authority_expansion") != "NONE" or checks.get("release_action_performed") != "NO":
        fail("independent review exceeds authority boundary")
    scope = review.get("constitutional_scope", {})
    if scope.get("a_out_le_a_in") != "preserved" or scope.get("evidence_is_authority") is not False:
        fail("constitutional scope marker invalid")
    release = review.get("release_context", {})
    if release.get("new_seal_created") is not False:
        fail("unexpected Seal claim")

    print("STAGE D RAILWAY EVIDENCE: PASS")
    print(f"Deployed Commit: {commit}")
    print(f"Verification Run ID: {run_id}")
    print(f"Workspace Snapshot SHA-256: {digest}")
    print("Independent Review: PASS")
    print("Token Recorded: NO")
    print("Authority Expansion: NONE")
    print("Release Action Performed: NO")


if __name__ == "__main__":
    main()
