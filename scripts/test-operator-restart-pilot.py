#!/usr/bin/env python3
"""Disposable installed-operator restart/recovery acceptance (NOT a deployment).

Exercises a genuine child server process, durable finished receipt, SIGKILL,
explicit local stale-transport revocation, fresh process/token, old receipt,
and no replay of the already-consumed plan. Fixed synthetic workspace only.
Never contacts the Internet, invokes Docker, executes model output, or touches
a real operator root. Linux nonroot Python 3.13+ required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time


def check(condition: bool, label: str) -> None:
    if not condition:
        raise RuntimeError(label)


def _verified_install(installed: Path, manifest_sha: str) -> None:
    check(installed.is_absolute() and ".." not in installed.parts,
          "invalid-install-path")
    check(len(manifest_sha) == 64 and
          all(c in "0123456789abcdef" for c in manifest_sha),
          "invalid-manifest-anchor")
    verify = subprocess.run(
        [sys.executable, "-I", "-B",
         str(installed / "scripts" / "nexus-operator-distribution.py"),
         "verify-installed", "--destination", str(installed),
         "--expected-manifest-sha256", manifest_sha],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=12,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    check(verify.returncode == 0, "installed-integrity-unverifiable")
    try:
        report = json.loads(verify.stdout)
    except ValueError as exc:
        raise RuntimeError("invalid-installed-verifier-output") from exc
    check(report.get("status") == "installed-integrity-verified" and
          report.get("manifest_anchor_matched") is True and
          report.get("publisher_authenticated") is False,
          "installed-manifest-anchor-not-confirmed")


def _spawn(installed: Path, root: Path) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-I", "-B",
         str(installed / "scripts" / "nexus-operator-service.py"),
         "serve", "--root", str(root)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        readable, _, _ = select.select([proc.stdout], [], [], 8)
        check(bool(readable), "operator-service-not-ready")
        ready = json.loads(proc.stdout.readline())
        check(proc.poll() is None and
              ready.get("status") == "operator-local-ready" and
              ready.get("transport") == "private-unix-socket",
              "operator-service-invalid-readiness")
        return proc
    except BaseException:
        _end(proc, force=True)
        raise


def _end(proc: subprocess.Popen, *, force: bool) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGKILL if force else signal.SIGINT)
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=6)
            if not force:
                raise RuntimeError("operator-service-did-not-stop-cleanly")
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()


def acceptance(installed: Path, expected_manifest_sha256: str) -> dict:
    check(os.name == "posix" and sys.platform.startswith("linux") and
          os.getuid() != 0 and sys.version_info >= (3, 13),
          "requires-unprivileged-linux-python-313")
    _verified_install(installed, expected_manifest_sha256)
    sys.path.insert(0, str(installed / "nexus-cloud"))
    from agent_chat_handoff import PROPOSAL_SCHEMA, prepare, write_export
    from agent_journal import ApprovalJournal
    from agent_operator_service import (
        TOKEN_NAME, SOCKET_NAME, client, recover_stale_service
    )
    from agent_workspace import Workspace, WorkspaceDenied

    synthetic_input = b"NEXUS_RESTART_PILOT_INPUT_V1"
    synthetic_output = "NEXUS_RESTART_PILOT_FINISHED_V1"
    with tempfile.TemporaryDirectory(prefix="nexus-restart-disposable-") as temp:
        base = Path(temp)
        root = base / "operator-root"
        root.mkdir(mode=0o700)
        outbox = base / "outbox"
        outbox.mkdir(mode=0o700)
        ws = Workspace(root, "acceptance")
        ws.write("input.txt", synthetic_input)
        proposal = {"schema": PROPOSAL_SCHEMA, "workspace": "acceptance",
                    "steps": [
                        {"tool": "verify_sha256", "path": "input.txt",
                         "expected_sha256": hashlib.sha256(synthetic_input).hexdigest()},
                        {"tool": "write", "path": "result.txt", "text": synthetic_output},
                    ]}
        raw, review = prepare(ws, proposal)
        digest = review["plan_sha256"]
        plan_path = write_export(outbox, f"nexus-plan-{digest[:16]}.json", raw)
        first = None
        second = None
        try:
            first = _spawn(installed, root)
            # Transport credentials are synthetic, local and never printed.
            old_token = (root / TOKEN_NAME).read_bytes()
            reviewed = client(root, workspace="acceptance", digest=digest,
                              action="review", plan_path=str(plan_path))
            check(reviewed.get("status") == "review" and
                  not (ws.path / "result.txt").exists(), "review-was-not-inert")
            submitted = client(root, workspace="acceptance", digest=digest,
                               action="start", plan_path=str(plan_path))
            check(submitted.get("status") == "submitted-not-verified",
                  "synthetic-plan-not-submitted")
            deadline = time.monotonic() + 12
            finished = None
            while time.monotonic() < deadline:
                observed = client(root, workspace="acceptance", digest=digest,
                                  action="status")
                if (observed.get("status") == "receipt" and
                        observed.get("journal_state") == "finished"):
                    finished = observed
                    break
                check(observed.get("status") in ("receipt", "queued-not-verified"),
                      "unexpected-pilot-status")
                time.sleep(0.05)
            check(finished is not None and
                  finished.get("execution_status") == "complete",
                  "durable-completion-not-confirmed")
            with ws.operation_lock():
                journal_before = ApprovalJournal(ws).read(digest)
            check(journal_before.get("state") == "finished" and
                  journal_before.get("result") == "complete" and
                  journal_before.get("completed_steps") == 2 and
                  ws.read("result.txt") == synthetic_output.encode(),
                  "finished-journal-or-output-invalid")

            # Real SIGKILL leaves transport credentials behind. Recovery
            # must not claim that other possible orphan processes were found
            # or safely terminated on an arbitrary external host.
            _end(first, force=True)
            first = None
            check((root / TOKEN_NAME).exists() and
                  (root / SOCKET_NAME).is_socket(),
                  "crash-evidence-missing")
            try:
                recover_stale_service(root)
            except WorkspaceDenied:
                pass
            else:
                raise RuntimeError("stale-recovery-lacked-explicit-acknowledgment")
            recovered = recover_stale_service(
                root, acknowledge_possible_orphans=True)
            check(recovered.get("status") == "stale-transport-revoked" and
                  recovered.get("journal_preserved") is True and
                  recovered.get("jobs_restarted") is False and
                  recovered.get("orphaned_processes_ruled_out") is False,
                  "unsafe-or-unverified-transport-recovery")
            second = _spawn(installed, root)
            check((root / TOKEN_NAME).read_bytes() != old_token,
                  "service-credential-not-rotated")
            restored = client(root, workspace="acceptance", digest=digest,
                              action="status")
            check(restored.get("status") == "receipt" and
                  restored.get("execution_status") == "complete" and
                  restored.get("journal_state") == "finished",
                  "restart-did-not-recover-finished-receipt")
            again = client(root, workspace="acceptance", digest=digest,
                           action="start", plan_path=str(plan_path))
            check(again.get("status") == "already-consumed",
                  "restart-allowed-approved-plan-replay")
            with ws.operation_lock():
                journal_after = ApprovalJournal(ws).read(digest)
            check(journal_after == journal_before and
                  ws.read("result.txt") == synthetic_output.encode(),
                  "restart-mutated-completed-evidence")
            _end(second, force=False)
            second = None
            check(not (root / TOKEN_NAME).exists() and
                  not (root / SOCKET_NAME).exists(),
                  "graceful-close-left-transport")
            return {"schema": "nexus.operator.restart-acceptance.v1",
                    "status": "disposable-process-restart-passed",
                    "installed_manifest_anchor_matched": True,
                    "real_child_processes": 2,
                    "synthetic_completed_steps": 2,
                    "forced_service_crash_tested": True,
                    "explicit_stale_transport_recovery": True,
                    "service_credential_rotated": True,
                    "durable_receipt_restored": True,
                    "replay_denied_after_restart": True,
                    "guest_or_container_executed": False,
                    "publisher_authenticated": False,
                    "production_ready": False,
                    "host_attested": False,
                    "orphaned_processes_ruled_out": False,
                    "authority": "none"}
        finally:
            if second is not None:
                _end(second, force=True)
            if first is not None:
                _end(first, force=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True,
                        help="Existing, verified and private installed operator directory")
    parser.add_argument("--expected-manifest-sha256", required=True,
                        help="Out-of-band 64-character manifest SHA-256 pin")
    parser.add_argument("--approve-disposable", action="store_true",
                        help="Explicitly allow ONLY the fixed disposable process/restart acceptance")
    args = parser.parse_args()
    try:
        check(args.approve_disposable, "explicit-disposable-approval-required")
        result = acceptance(args.installed, args.expected_manifest_sha256)
    except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
        # Do not expose tokens, private source paths, plan content or stack traces.
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "production_ready": False, "authority": "none"},
                         sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
