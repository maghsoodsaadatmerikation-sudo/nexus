#!/usr/bin/env python3
"""Adversarial guarded boot test against actual three historical Rust gateways.

The gate is synthetic-only; the older deployed binary has no such guard.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
GUARD = HERE / "workspace-stage-d-startup-guard.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy(commit, binary):
    return {
        "schema": "nexus.stage-d.guarded-start.v1",
        "approved_git_sha": commit,
        "approved_binary_sha256": sha(binary),
        "data_layout": "nexus.durable-requests.v1",
        "execution_scope": "synthetic-only",
        "required_quarantine_support": True,
        "production_release_authorized": False,
    }


def save(path, data):
    path.write_bytes((json.dumps(data, sort_keys=True, separators=(",", ":"))
                      + "\n").encode())
    os.chmod(path, 0o600)
    return path


def protected_root(root):
    root.mkdir(mode=0o700)
    (root / "requests").mkdir(mode=0o700)
    return root


def args(binary, commit, policy_path, root):
    return [
        "--binary", binary,
        "--binary-sha256", sha(binary),
        "--runtime-git-sha", commit,
        "--policy", policy_path,
        "--policy-sha256", sha(policy_path),
        "--data-dir", root,
    ]


def call(mode, options, ok):
    proc = subprocess.run(
        [sys.executable, str(GUARD), mode, *map(str, options)],
        capture_output=True, text=True, timeout=30)
    assert (proc.returncode == 0) == ok, (
        f"unexpected guard result={proc.returncode}, output={proc.stdout}, error={proc.stderr}")
    if ok:
        return json.loads(proc.stdout)
    assert "NEXUS STARTUP ADMISSION DENIED:" in proc.stderr, proc.stderr
    return None


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def guarded_run(opts, root, token):
    p = port()
    env = dict(os.environ)
    env["NEXUS_BIND_ADDR"] = "127.0.0.1:" + str(p)
    env["NEXUS_API_TOKEN"] = token
    proc = subprocess.Popen(
        [sys.executable, str(GUARD), "run-synthetic", *map(str, opts)],
        env=env, cwd=root, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    until = time.monotonic() + 15
    while time.monotonic() < until:
        if proc.poll() is not None:
            err = proc.stderr.read().decode(errors="replace")
            raise AssertionError("guarded server failed to start: " + err)
        try:
            import http.client
            connection = http.client.HTTPConnection("127.0.0.1", p, timeout=0.5)
            connection.request("GET", "/v1/requests/synthetic-unknown",
                               headers={"Authorization": "Bearer " + token})
            result = connection.getresponse()
            result.read()
            connection.close()
            if result.status == 404:
                return proc, p
        except (OSError, TimeoutError):
            time.sleep(0.08)
    stop(proc)
    raise AssertionError("guarded historical gateway readiness deadline reached")


def stop(process):
    import signal
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=7)


def check_http(port, token, request, expected, body=None):
    import http.client
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    headers = {"Authorization": "Bearer " + token,
               "Content-Type": "application/json"}
    try:
        connection.request(request, "/v1/requests/synthetic-accepted"
                           if request == "GET" else "/v1/requests",
                           body=json.dumps(body).encode() if body else None,
                           headers=headers)
        response = connection.getresponse()
        payload = response.read()
        assert response.status == expected, (response.status, payload)
        return json.loads(payload)
    finally:
        connection.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    for kind in ("recovery", "source", "target"):
        parser.add_argument("--" + kind + "-binary", type=Path, required=True)
    parser.add_argument("--runner-temp", type=Path, required=True)
    parser.add_argument("--synthetic-only", action="store_true", required=True)
    v = parser.parse_args()
    assert v.synthetic_only and v.runner_temp.is_absolute()
    counts = 0
    revs = {
        "recovery": "588dc7672146031425b16b34956876d644244ace",
        "source": "9abbc067aad3ebbb0956432cf6682d2ea70e2824",
        "target": "f4d027bb5f7e715b298f7cf7184fa621a2fb071d",
    }
    with tempfile.TemporaryDirectory(prefix="nexus-guard-test-", dir=v.runner_temp) as t:
        root = Path(t)
        os.chmod(root, 0o700)
        binary = {
            name: getattr(v, name + "_binary") for name in revs
        }
        policies = {}
        for name in revs:
            assert binary[name].is_absolute() and binary[name].is_file()
            policies[name] = save(root / (name + "-policy.json"),
                                  policy(revs[name], binary[name]))

        # Legacy is refused EVEN with a correctly hashed policy naming the
        # actual old executable and an empty, otherwise valid private root.
        old_root = protected_root(root / "old-data")
        legacy = args(binary["recovery"], revs["recovery"],
                      policies["recovery"], old_root)
        call("inspect", legacy, False)
        counts += 1
        call("run-synthetic", legacy, False)
        counts += 1

        # A newer gateway is allowed only with exact external binary and
        # canonical private policy pins. It must execute the checked FD.
        for name in ("source", "target"):
            workroot = protected_root(root / ("data-" + name))
            opts = args(binary[name], revs[name], policies[name], workroot)
            approved = call("inspect", opts, True)
            assert approved["runtime_git_sha"] == revs[name]
            assert approved["production_release_authorized"] is False
            assert approved["release_gate"] == "BLOCKED"
            counts += 1

            token = secrets.token_urlsafe(32)
            process, p = guarded_run(opts, workroot, token)
            try:
                from_request = {
                    "request_id": "synthetic-accepted",
                    "authority": "user", "action": "reflect",
                    "subject": "synthetic", "payload": "synthetic",
                }
                assert check_http(p, token, "POST", 202, from_request)["request_id"] == "synthetic-accepted"
                assert check_http(p, token, "POST", 409, from_request)["error"] == "request_id_replayed"
                counts += 1
            finally:
                stop(process)

            # Historical gateways create request markers with umask-based
            # mode (usually 0644) and sometimes a 0755 request directory.
            # The new guard refuses such modes: demonstrate the failure,
            # then narrow permissions ONLY on this disposable test data.
            reservation = workroot / "requests" / b"synthetic-accepted".hex()
            unsafe_permissions = (
                (reservation.stat().st_mode & 0o077)
                or ((workroot / "requests").stat().st_mode & 0o077)
            )
            if unsafe_permissions:
                call("inspect", opts, False)
                counts += 1
            os.chmod(workroot / "requests", 0o700)
            os.chmod(reservation, 0o600)
            approved = call("inspect", opts, True)
            assert approved["reservations_checked"] == 1
            counts += 1

            guard_same = args(binary["recovery"], revs["recovery"],
                              policies["recovery"], workroot)
            call("inspect", guard_same, False)
            counts += 1

            q = workroot / ".nexus-recovery-required"
            q.write_bytes(b"synthetic-blocked-restore\n")
            os.chmod(q, 0o600)
            checked = call("inspect", opts, True)
            assert checked["recovery_quarantine_present"] is True
            counts += 1
            process, p = guarded_run(opts, workroot, token)
            try:
                assert check_http(p, token, "POST", 503,
                                  dict(from_request, request_id="quarantined"))[
                                      "error"] == "recovery_acknowledgment_required"
                counts += 1
            finally:
                stop(process)
            q.unlink()

        # The guard is fail-closed if the reviewer trusts a forged approval,
        # untrusted content, a directory alias, corrupt request state, or
        # an unrecognized workspace schema. None can execute old binaries.
        workroot = protected_root(root / "negative-data")
        opts = args(binary["source"], revs["source"],
                    policies["source"], workroot)

        def expect(changes, ok=False):
            nonlocal counts
            call("inspect", changes, ok)
            counts += 1

        for position, bad in (
            (5, "x" * 40),
            (3, "f" * 64),
            (9, "f" * 64),
        ):
            modified = list(opts)
            modified[position] = bad
            expect(modified)
        false_policy = dict(policy(revs["source"], binary["source"]))
        for key, val in (
            ("execution_scope", "production"),
            ("production_release_authorized", True),
            ("required_quarantine_support", False),
            ("data_layout", "unknown"),
            ("approved_git_sha", revs["recovery"]),
            ("approved_git_sha", "0" * 40),
        ):
            bad = dict(false_policy)
            bad[key] = val
            f = save(root / ("forged-" + key + "-" + str(len(str(val))) + ".json"), bad)
            expect(args(binary["source"], revs["source"], f, workroot))
        changed = dict(false_policy, unknown_authority=True)
        f = save(root / "unknown-policy.json", changed)
        expect(args(binary["source"], revs["source"], f, workroot))

        linked_policy = root / "linked-policy.json"
        linked_policy.symlink_to(policies["source"])
        expect(args(binary["source"], revs["source"], linked_policy, workroot))
        hard = root / "hardlinked-policy.json"
        os.link(policies["source"], hard)
        expect(args(binary["source"], revs["source"], hard, workroot))
        hard.unlink()

        unknown = workroot / "configuration.env"
        unknown.write_text("bogus")
        expect(opts)
        unknown.unlink()

        requests = workroot / "requests"
        os.chmod(requests, 0o755)
        expect(opts)
        os.chmod(requests, 0o700)
        reservation = requests / b"bad-req".hex()
        reservation.write_bytes(b"ready-to-run\n")
        os.chmod(reservation, 0o600)
        expect(opts)
        reservation.unlink()

        reservation = requests / b"bad-req".hex()
        reservation.write_bytes(b"pending\n")
        os.chmod(reservation, 0o600)
        safe = root / "hardlinked-marker"
        os.link(reservation, safe)
        expect(opts)
        safe.unlink()
        reservation.unlink()

        (workroot / "requests").rmdir()
        redirect = workroot / "requests"
        redirect.symlink_to(root)
        expect(opts)
        redirect.unlink()
        (workroot / "requests").mkdir(mode=0o700)

        alias_root = root / "data-alias"
        alias_root.symlink_to(workroot)
        expect(args(binary["source"], revs["source"],
                    policies["source"], alias_root))

        bad_ws = workroot / ("w".encode().hex() + ".json")
        bad_ws.write_text('{"schema_version":2}')
        os.chmod(bad_ws, 0o600)
        expect(opts)
        bad_ws.unlink()

        no_binary = root / "malformed-executable"
        no_binary.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(no_binary, 0o700)
        wrong_binary = args(no_binary, revs["source"],
                            policies["source"], workroot)
        expect(wrong_binary)

        assert call("inspect", opts, True)["workspaces_checked"] == 0
        counts += 1

    print(json.dumps({
        "status": "PASS",
        "checks": counts,
        "scope": "real-historical-gateways-synthetic-boot-guard-and-legacy-hard-deny",
        "legacy_runtime_admitted": False,
        "modern_synthetic_runtime_exec_verified": True,
        "real_railway_data_or_services_touched": False,
        "production_release_authorized": False,
    }))


if __name__ == "__main__":
    main()
