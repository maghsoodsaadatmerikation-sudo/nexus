"""Phase 21 — non-deploying operator readiness snapshot and synthetic acceptance.

No model-facing API, Docker socket, production workspace mutation, background
service, secret export, or autonomous approval. Check is a local snapshot, not
an authorization or host-security attestation. Smoke runs a *fixed* synthetic
two-step plan only after explicit operator consent, in a disposable root.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import time

from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
from agent_host_census import admission_lock, docker_inventory, journal_census
from agent_journal import ApprovalJournal
from agent_operator_service import OperatorServer, client
from agent_workspace import WORKSPACE_ID, Workspace, WorkspaceDenied

SCHEMA = "nexus.operator.pilot-acceptance.v1"
INPUT = b"NEXUS_OPERATOR_DISPOSABLE_INPUT_V1"
OUTPUT = "NEXUS_OPERATOR_DISPOSABLE_PASS_V1"


def readiness_snapshot(root: str | Path, *, workspace: str | None = None,
                       inspect_docker: bool = False) -> dict:
    """Observe one protected root. Never infer absent orphans from a clean ledger.

    admission_lock may create an owner-only lock *metadata inode*. This method
    never creates a workspace, journal claim, transport token, or guest.
    """
    if os.name != "posix" or not sys.platform.startswith("linux") or os.getuid() == 0:
        raise WorkspaceDenied("pilot-needs-nonroot-linux-operator")
    if type(inspect_docker) is not bool:
        raise WorkspaceDenied("pilot-invalid-options")
    if workspace is not None and (not isinstance(workspace, str)
                                  or not WORKSPACE_ID.fullmatch(workspace)):
        raise WorkspaceDenied("pilot-invalid-workspace")
    with admission_lock(root):
        census = journal_census(root)
        workspace_status = "not-requested"
        if workspace is not None:
            target = Path(root) / workspace
            try:
                st = target.lstat()
            except FileNotFoundError:
                workspace_status = "missing"
            else:
                workspace_status = ("existing" if stat.S_ISDIR(st.st_mode)
                                    and st.st_uid == os.getuid()
                                    and not st.st_mode & 0o077 else "unsafe")
        docker_status = "not-inspected"
        labelled_count = None
        if inspect_docker:
            observed = docker_inventory()
            docker_status = observed["status"]
            labelled_count = observed["labelled_container_count"]
    blockers = []
    if census["status"] != "clear":
        blockers.append("approval-ledger-not-clear")
    if workspace_status in ("missing", "unsafe"):
        blockers.append("workspace-unavailable")
    if inspect_docker and docker_status != "no-labelled-containers-observed":
        blockers.append("docker-observation-not-clear")
    return {
        "schema": SCHEMA,
        "mode": "check",
        "status": "blocked" if blockers else "preflight-clear-not-attested",
        "workspace_status": workspace_status,
        "journal_status": census["status"],
        "unfinished_count": len(census["unfinished"]),
        "finished_count": census["finished_count"],
        "docker_cleanup_unverified_count": census["docker_cleanup_unverified_count"],
        "docker_inventory_status": docker_status,
        "labelled_container_count": labelled_count,
        "blockers": blockers,
        "authority": "none",
        "production_ready": False,
        "host_attested": False,
        "orphaned_processes_ruled_out": False,
        "executed": False,
        "note": "Read-only evidence snapshot except for a private flock metadata inode; this is not approval to run code or a production host attestation.",
    }


def synthetic_smoke(*, approved: bool = False) -> dict:
    """Real Unix-socket roundtrip, fixed synthetic plan, completely disposable."""
    if approved is not True or os.name != "posix" or not sys.platform.startswith("linux") or os.getuid() == 0:
        raise WorkspaceDenied("pilot-requires-explicit-disposable-nonroot-approval")
    with tempfile.TemporaryDirectory(prefix="nexus-operator-pilot-") as temp:
        root = Path(temp) / "operator-root"
        root.mkdir(mode=0o700)
        out = Path(temp) / "private-outbox"
        out.mkdir(mode=0o700)
        ws = Workspace(root, "acceptance")
        ws.write("input.txt", INPUT)
        original_manifest = ws.manifest()["sha256"]
        proposal = {
            "schema": PROPOSAL_SCHEMA, "workspace": "acceptance",
            "steps": [
                {"tool": "verify_sha256", "path": "input.txt",
                 "expected_sha256": hashlib.sha256(INPUT).hexdigest()},
                {"tool": "write", "path": "result.txt", "text": OUTPUT},
            ],
        }
        raw, review = prepare(ws, proposal)
        digest = review["plan_sha256"]
        plan_path = write_export(out, f"nexus-plan-{digest[:16]}.json", raw)
        with OperatorServer(root, allow_container=False, allow_rootless=False) as server:
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.02},
                daemon=True)
            thread.start()
            try:
                review_result = client(root, workspace="acceptance", digest=digest,
                                       action="review", plan_path=str(plan_path))
                if (review_result.get("status") != "review"
                        or review_result.get("summary", {}).get("status") != "not-executed"
                        or ws.manifest()["sha256"] != original_manifest
                        or (ws.path / "result.txt").exists()):
                    raise WorkspaceDenied("pilot-review-not-inert")
                ack = client(root, workspace="acceptance", digest=digest,
                             action="start", plan_path=str(plan_path))
                if ack.get("status") != "submitted-not-verified":
                    raise WorkspaceDenied("pilot-start-not-admitted")
                result = None
                deadline = time.monotonic() + 12.0
                while time.monotonic() < deadline:
                    value = client(root, workspace="acceptance", digest=digest,
                                   action="status")
                    if (value.get("status") == "receipt"
                            and value.get("journal_state") == "finished"):
                        result = value
                        break
                    if value.get("status") not in ("receipt", "queued-not-verified"):
                        raise WorkspaceDenied("pilot-unknown-status")
                    time.sleep(0.05)
                if result is None:
                    raise WorkspaceDenied("pilot-no-terminal-receipt")
                record = ApprovalJournal(ws).read(digest)
                if (result.get("execution_status") != "complete"
                        or result.get("authority") != "none"
                        or result.get("verification") != "not-independent-attestation"
                        or record.get("result") != "complete"
                        or record.get("state") != "finished"
                        or record.get("plan_sha256") != digest
                        or record.get("completed_steps") != 2
                        or ws.read("result.txt") != OUTPUT.encode()
                        or ws.manifest()["sha256"] == original_manifest):
                    raise WorkspaceDenied("pilot-result-not-verified")
                replay = client(root, workspace="acceptance", digest=digest,
                                action="start", plan_path=str(plan_path))
                if replay.get("status") == "submitted-not-verified":
                    raise WorkspaceDenied("pilot-one-use-approval-replayed")
                return {
                    "schema": SCHEMA,
                    "mode": "smoke",
                    "status": "disposable-operator-cycle-passed",
                    "real_private_unix_socket": True,
                    "review_inert": True,
                    "journal_durable": True,
                    "synthetic_steps_executed": 2,
                    "one_use_replay_denied": True,
                    "guest_or_container_executed": False,
                    "source_project_changed": False,
                    "authority": "none",
                    "production_ready": False,
                    "host_attested": False,
                    "orphaned_processes_ruled_out": False,
                }
            finally:
                server.shutdown()
                thread.join(timeout=5)
                if thread.is_alive():
                    raise WorkspaceDenied("pilot-service-did-not-stop")
