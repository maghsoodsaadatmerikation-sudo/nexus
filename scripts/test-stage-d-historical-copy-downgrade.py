#!/usr/bin/env python3
"""Live historical NEXUS gateway DOWNGRADE test on a disposable data COPY.

Requires real binary revisions built in GitHub Actions, but no user data,
provider credentials, Railway access or writable real deployment mounts.
An observational PASS means known UNSAFE historical downgrade behavior was
detected and forced into the release-block report, NOT safe production rollback.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "nexus_gateway_existing_restart",
    HERE / "test-stage-d-historical-gateway-restart.py")
if spec is None or spec.loader is None:
    raise RuntimeError("historical gateway test helpers not found")
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)

OLD = "588dc7672146031425b16b34956876d644244ace"
NEW = {
    "source": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
    "target": "f4d027bb5f7e715b298f7cf7184fa621a2fb071d",
}
REQUEST = "synthetic-previously-accepted"
UNCERTAIN = "synthetic-interrupted"
WORKSPACE = "synthetic-before-downgrade"
POST_QUARANTINE_WORKSPACE = "synthetic-written-by-legacy-during-quarantine"
QUARANTINED_REQUEST = "synthetic-accepted-by-old-while-quarantined"
MAX_TREE = 80
MAX_BYTES = 4 * 1024 * 1024


def require(condition, reason):
    gateway.require(condition, reason)


def request_body(request_id):
    return {
        "request_id": request_id, "authority": "user",
        "action": "reflect", "subject": "synthetic",
        "payload": "disposable-synthetic-request",
    }


def work_body(workspace_id):
    return {
        "workspace_id": workspace_id, "question": "Disposable question",
        "provenance_id": "human:synthetic",
    }


def call(port, token, method, path, payload=None, expected=None):
    status, data = gateway.http_call(port, token, method, path, payload)
    if expected is not None:
        require(status == expected, f"unexpected synthetic HTTP {status} at {method} {path}, wanted {expected}")
    return status, data


def get_request(port, token, request_id, expected):
    _, doc = call(port, token, "GET", "/v1/requests/" + request_id,
                  expected=expected)
    if expected == 200:
        require(doc.get("request_id") == request_id,
                "requested ID differs from response identity")
    return doc


def digest_tree(root):
    require(root.is_dir() and not root.is_symlink(), "untrusted synthetic filesystem root")
    seen = {}
    total = 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        meta = path.lstat()
        require(not stat.S_ISLNK(meta.st_mode), "snapshot includes a symlink")
        if stat.S_ISDIR(meta.st_mode):
            continue
        require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1,
                "snapshot includes a nonregular or linked file")
        total += meta.st_size
        require(total <= MAX_BYTES, "synthetic snapshot exceeds size budget")
        require(len(seen) < MAX_TREE, "synthetic snapshot exceeds entry budget")
        seen[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return seen


def new_marker(root, request, payload):
    target = root / "requests" / request.encode().hex()
    require(not target.exists(), "synthetic reservation already exists")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())
    gateway.check_file(target, payload)
    return target


def clone(source, target):
    require(source != target and not target.exists(),
            "cannot overwrite a source or previously used test copy")
    shutil.copytree(source, target, symlinks=False)
    require(source.stat().st_ino != target.stat().st_ino
            or source.stat().st_dev != target.stat().st_dev,
            "rollback test must never reuse the same directory inode")
    require(digest_tree(source) == digest_tree(target),
            "synthetic data clone does not match source bytes")


def stop(child):
    gateway.stop(child)


def run_service(binary, folder, role, token):
    return gateway.start(binary, folder, role, token)


def test_one(role, modern_binary, recovery_binary, root):
    token = secrets.token_urlsafe(32)
    orig = root / (role + "-original")
    orig.mkdir(mode=0o700)
    modern = None
    old = None
    checks = 0
    try:
        modern, p = run_service(modern_binary, orig, role, token)
        _, result = call(p, token, "POST", "/v1/workspaces",
                         work_body(WORKSPACE), expected=201)
        require(result.get("workspace", {}).get("id") == WORKSPACE,
                "modern service did not create synthetic workspace")
        checks += 1
        _, accepted = call(p, token, "POST", "/v1/requests",
                           request_body(REQUEST), expected=202)
        require(accepted.get("request_id") == REQUEST,
                "modern service did not accept the unique synthetic request")
        checks += 1
        require(get_request(p, token, REQUEST, 200).get("status", "").lower() == "pending",
                "modern service did not report committed pending status")
        checks += 1
        stop(modern)
        modern = None
        gateway.check_file(orig / "requests" / REQUEST.encode().hex(), b"pending\n")
        baseline = digest_tree(orig)
        checks += 1

        # 1) Normal downgrade against a wholly independent COPY, never the
        # newer service's original root: old runtime must NOT be considered
        # safe merely because it can read the workspace JSON.
        clean = root / (role + "-downgrade-copy")
        clone(orig, clean)
        before_old = digest_tree(clean)
        marker = new_marker(clean, UNCERTAIN, b"p")
        expected_pre_old = digest_tree(clean)
        checks += 1

        old, old_port = run_service(recovery_binary, clean, "recovery", token)
        _, value = call(old_port, token, "GET", "/v1/workspaces/" + WORKSPACE,
                        expected=200)
        require(value.get("workspace", {}).get("id") == WORKSPACE,
                "legacy gateway cannot read modern synthetic workspace")
        checks += 1
        require(get_request(old_port, token, REQUEST, 404).get("error") ==
                "request_not_found", "legacy unexpectedly understands committed request marker")
        checks += 1
        require(get_request(old_port, token, UNCERTAIN, 404).get("error") ==
                "request_not_found", "legacy unexpectedly understands partial marker")
        checks += 1
        _, reply = call(old_port, token, "POST", "/v1/requests",
                        request_body(REQUEST), expected=202)
        require(reply.get("request_id") == REQUEST,
                "legacy request acceptance behavior changed unexpectedly")
        checks += 1
        _, reply = call(old_port, token, "POST", "/v1/requests",
                        request_body(UNCERTAIN), expected=202)
        require(reply.get("request_id") == UNCERTAIN,
                "legacy erroneously claimed to enforce partial marker quarantine")
        checks += 1
        stop(old)
        old = None
        require(digest_tree(clean) == expected_pre_old,
                "legacy replay case unexpectedly modified committed on-disk copy")
        gateway.check_file(marker, b"p")
        checks += 1

        modern, again = run_service(modern_binary, clean, role, token)
        require(get_request(again, token, REQUEST, 200).get("status", "").lower() == "pending",
                "modern resumed with lost accepted request status")
        checks += 1
        require(get_request(again, token, UNCERTAIN, 200).get("status", "").lower() ==
                "indeterminate", "modern resumed with unsafe partial reservation state")
        checks += 1
        for req in (REQUEST, UNCERTAIN):
            _, response = call(again, token, "POST", "/v1/requests",
                               request_body(req), expected=409)
            require(response.get("error") == "request_id_replayed",
                    "modern failed to block old-replayed request")
            checks += 1
        stop(modern)
        modern = None
        require(digest_tree(clean) == expected_pre_old,
                "modern reader unexpectedly changed copy-only reservation state")
        require(digest_tree(orig) == baseline,
                "never-authorized modern original root changed during downgrade rehearsal")
        checks += 1

        # 2) Quarantine from a separately created modern-only copy. Old
        # version ignores .nexus-recovery-required, accepts NEW work and
        # writes a workspace. This is a real behavioral counterexample to
        # treating a copy-only rollback as policy-compatible.
        quarantined = root / (role + "-quarantine-copy")
        clone(orig, quarantined)
        quarantine_file = quarantined / ".nexus-recovery-required"
        quarantine_file.write_bytes(b"offline-test-recovery-not-approved\n")
        os.chmod(quarantine_file, 0o600)
        locked_digest = digest_tree(quarantined)
        modern, pq = run_service(modern_binary, quarantined, role, token)
        _, denied = call(pq, token, "POST", "/v1/requests",
                         request_body(QUARANTINED_REQUEST), expected=503)
        require(denied.get("error") == "recovery_acknowledgment_required",
                "modern recovery quarantine did not reject request")
        checks += 1
        _, denied = call(pq, token, "POST", "/v1/workspaces",
                         work_body(POST_QUARANTINE_WORKSPACE), expected=503)
        require(denied.get("error") == "recovery_acknowledgment_required",
                "modern recovery quarantine did not reject workspace creation")
        checks += 1
        stop(modern)
        modern = None
        require(digest_tree(quarantined) == locked_digest,
                "recovery quarantine should prevent synthetic data changes")
        checks += 1

        old, old_port = run_service(recovery_binary, quarantined, "recovery", token)
        _, accepted = call(old_port, token, "POST", "/v1/requests",
                           request_body(QUARANTINED_REQUEST), expected=202)
        require(accepted.get("request_id") == QUARANTINED_REQUEST,
                "old gateway unexpectedly enforced modern quarantine on request")
        checks += 1
        _, created = call(old_port, token, "POST", "/v1/workspaces",
                          work_body(POST_QUARANTINE_WORKSPACE), expected=201)
        require(created.get("workspace", {}).get("id") == POST_QUARANTINE_WORKSPACE,
                "old gateway unexpectedly enforced modern quarantine on workspace mutation")
        checks += 1
        stop(old)
        old = None
        after_old = digest_tree(quarantined)
        added = sorted(set(after_old) - set(locked_digest))
        require(added == [POST_QUARANTINE_WORKSPACE.encode().hex() + ".json"],
                "old gateway caused unexpected data changes while ignoring quarantine")
        require(all(after_old[p] == locked_digest[p] for p in locked_digest),
                "old gateway modified existing quarantine or synthetic data")
        require(not (quarantined / "requests" /
                     QUARANTINED_REQUEST.encode().hex()).exists(),
                "old gateway unexpectedly wrote modern request marker")
        checks += 1
        gateway.check_file(quarantine_file, b"offline-test-recovery-not-approved\n")
        checks += 1

        modern, pq2 = run_service(modern_binary, quarantined, role, token)
        _, recovered = call(pq2, token, "GET",
                            "/v1/workspaces/" + POST_QUARANTINE_WORKSPACE, expected=200)
        require(recovered.get("workspace", {}).get("id") ==
                POST_QUARANTINE_WORKSPACE,
                "new gateway cannot read legacy-written synthetically quarantined file")
        checks += 1
        _, denied = call(pq2, token, "POST", "/v1/requests",
                         request_body("new-work-after-upgrade"), expected=503)
        require(denied.get("error") == "recovery_acknowledgment_required",
                "return to new gateway bypassed persisted quarantine")
        checks += 1
        stop(modern)
        modern = None
        require(digest_tree(quarantined) == after_old,
                "returning to new gateway unexpectedly changed quarantine copy")
        require(digest_tree(orig) == baseline,
                "original synthetic baseline was modified instead of copy")
        checks += 1

        return {
            "origin": role,
            "origin_git_sha": NEW[role],
            "legacy_git_sha": OLD,
            "checks": checks,
            "source_and_copy_distinct": True,
            "legacy_reaccepted_pending_and_uncertain_request_ids": True,
            "newer_reader_rejects_replay_after_return": True,
            "old_writer_ignores_newer_recovery_quarantine": True,
            "old_writer_modified_disposable_copy_while_quarantined": True,
            "unchanged_modern_original_sha256": hashlib.sha256(
                json.dumps(baseline, sort_keys=True).encode()).hexdigest(),
            "user_data": "synthetic-only",
            "safe_downgrade_approved": False,
        }
    finally:
        stop(old)
        stop(modern)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-binary", type=Path, required=True)
    parser.add_argument("--source-binary", type=Path, required=True)
    parser.add_argument("--target-binary", type=Path, required=True)
    parser.add_argument("--runner-temp", type=Path, required=True)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    args = parser.parse_args()
    try:
        require(args.synthetic_only, "explicit synthetic-only boundary required")
        require(args.runner_temp.is_absolute()
                and args.runner_temp.is_dir()
                and not args.runner_temp.is_symlink(),
                "disposable private absolute root required")
        binaries = {}
        for role in ("recovery", "source", "target"):
            path = getattr(args, role + "_binary")
            require(path.is_absolute() and path.is_file() and not path.is_symlink(),
                    "historical binary must be an explicit regular absolute path")
            binaries[role] = path
        with tempfile.TemporaryDirectory(
                prefix="nexus-unsafe-version-downgrade-",
                dir=args.runner_temp) as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            results = [
                test_one(role, binaries[role], binaries["recovery"], root)
                for role in ("source", "target")
            ]
        require(len(results) == 2
                and all(x["safe_downgrade_approved"] is False for x in results),
                "an isolated downgrade must never grant production permission")
        print(json.dumps({
            "status": "PASS_WITH_CONFIRMED_UNSAFE_LEGACY_DOWNGRADE",
            "checks": sum(v["checks"] for v in results),
            "scenarios": results,
            "actual_historical_http_binaries_used": True,
            "copied_data_not_live_volumes": True,
            "hardware_power_failure_or_actual_offhost_restore_proven": False,
            "rollback_approved": False,
            "production_release_authorized": False,
            "release_gate": "BLOCKED",
        }, sort_keys=True))
        return 0
    except (gateway.GatewayTestError, OSError, ValueError, TypeError,
            KeyError) as exc:
        print("NEXUS COPY-ONLY HISTORICAL DOWNGRADE DENIED: " + str(exc),
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
