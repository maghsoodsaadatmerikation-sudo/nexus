#!/usr/bin/env python3
"""Execute an actual guarded NEXUS Docker image with synthetic loopback HTTP.

Runs ONLY on a disposable GitHub Actions runner. Docker daemon privileges
can override ENTRYPOINT: this test does not claim an unbypassable image.
No Railway, Render, production data, real secrets or customer workloads.
"""
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid


SOURCE = "f4d027bb5f7e715b298f7cf7184fa621a2fb071d"
LEGACY = "588dc7672146031425b16b34956876d644244ace"
ENTRY = [
    "/usr/local/bin/python3", "-I", "-B",
    "/opt/nexus/stage-d-guarded-image-entrypoint.py",
]
IMAGE_BINARY = "/opt/nexus/nexus"


def sh(args, *, good=True, timeout=45):
    process = subprocess.run(list(map(str, args)), capture_output=True,
                             text=True, timeout=timeout)
    if (process.returncode == 0) != good:
        raise AssertionError(
            "unexpected docker command result: " + str(args[:4]) + " " +
            str(process.returncode) + "\nstdout=" + process.stdout[-2500:] +
            "\nstderr=" + process.stderr[-2500:])
    return process


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


# Retain independently computed test digest BEFORE changing the uid to
# container user 10001. The runner must not reopen this 0600 policy as root.
TEST_PINNED_DIGESTS = {}


def digest(path):
    if str(path) in TEST_PINNED_DIGESTS:
        return TEST_PINNED_DIGESTS[str(path)]
    return hashlib.sha256(path.read_bytes()).hexdigest()


def privileged_bytes(path):
    proc = subprocess.run(["sudo", "cat", str(path)], capture_output=True,
                          timeout=10, check=True)
    return proc.stdout


def privileged_mode(path):
    proc = subprocess.run(["sudo", "stat", "-c", "%a", str(path)],
                          capture_output=True, text=True, timeout=10, check=True)
    return int(proc.stdout.strip(), 8)


def privileged_exists(path):
    return subprocess.run(["sudo", "test", "-e", str(path)], timeout=10,
                          capture_output=True).returncode == 0


@contextmanager
def owner_clean_temp(parent):
    with tempfile.TemporaryDirectory(prefix="nexus-guarded-oci-", dir=parent) as tmp:
        try:
            yield tmp
        finally:
            subprocess.run(
                ["sudo", "chown", "-R", str(os.getuid()) + ":" +
                 str(os.getgid()), tmp],
                capture_output=True, timeout=20, check=True)


def policy(commit, binary_sha, **changes):
    obj = {
        "schema": "nexus.stage-d.guarded-start.v1",
        "approved_git_sha": commit,
        "approved_binary_sha256": binary_sha,
        "data_layout": "nexus.durable-requests.v1",
        "execution_scope": "synthetic-only",
        "required_quarantine_support": True,
        "production_release_authorized": False,
    }
    obj.update(changes)
    return obj


def private_file(path, contents):
    path.write_bytes(contents)
    TEST_PINNED_DIGESTS[str(path)] = hashlib.sha256(contents).hexdigest()
    os.chmod(path, 0o600)
    sh(["sudo", "chown", "10001:10001", path])
    return path


def data_root(root):
    root.mkdir(mode=0o700)
    sh(["sudo", "chown", "10001:10001", root])
    return root


def run_args(image, root, approval, binary_sha, policy_sha, git_sha, port,
             token, *, network="host", use_mount=True):
    name = "nexus-guarded-synthetic-" + uuid.uuid4().hex[:12]
    args = [
        "docker", "run", "--rm", "--name", name,
        "--network", network,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--pids-limit", "64",
        "--memory", "256m",
        "--cpus", "1",
        "--env", "NEXUS_APPROVED_GIT_SHA=" + git_sha,
        "--env", "NEXUS_BINARY_SHA256=" + binary_sha,
        "--env", "NEXUS_POLICY_SHA256=" + policy_sha,
        "--env", "NEXUS_BIND_ADDR=127.0.0.1:" + str(port),
        "--env", "NEXUS_API_TOKEN=" + token,
        "--mount", "type=bind,src=" + str(approval) +
                   ",dst=/run/nexus/approval.json,readonly",
    ]
    if use_mount:
        args += ["--mount", "type=bind,src=" + str(root) + ",dst=/data"]
    args.append(image)
    return name, args


def request(port, token, method, route, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/json"}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode()
    try:
        connection.request(method, route, payload, headers)
        response = connection.getresponse()
        content = response.read(1048577)
        assert len(content) <= 1048576, "gateway response size exceeded"
        return response.status, json.loads(content)
    finally:
        connection.close()


def choose_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def await_ready(port, token, container):
    deadline = time.monotonic() + 18
    while time.monotonic() < deadline:
        try:
            status, _ = request(port, token, "GET", "/v1/requests/no-such-request")
            if status == 404:
                return
            raise AssertionError("unexpected gateway readiness HTTP status")
        except (OSError, TimeoutError):
            status = sh(["docker", "inspect", "--format", "{{.State.Running}}",
                         container], good=True).stdout.strip()
            if status != "true":
                raise AssertionError("guarded image container exited before readiness")
            time.sleep(0.12)
    raise AssertionError("guarded image never served loopback requests")


def stop(name):
    # Container can have already exited due to negative policy test.
    subprocess.run(["docker", "rm", "-f", name], capture_output=True,
                   timeout=15, check=False)


def image_binary_sha(image, root):
    container = sh(["docker", "create", image]).stdout.strip()
    assert container, "cannot create image inspection container"
    binary = root / "extracted-historical-gateway"
    try:
        sh(["docker", "cp", container + ":" + IMAGE_BINARY, binary])
    finally:
        stop(container)
    assert binary.is_file() and binary.stat().st_size > 1024
    return digest(binary)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--runner-temp", type=Path, required=True)
    p.add_argument("--synthetic-only", action="store_true", required=True)
    args = p.parse_args()
    assert args.synthetic_only
    assert args.runner_temp.is_absolute() and args.runner_temp.is_dir()
    image = args.image
    inspect = json.loads(sh(["docker", "image", "inspect", image]).stdout)[0]
    assert inspect["Config"]["Entrypoint"] == ENTRY, "default image entrypoint is not guard"
    assert inspect["Config"]["User"] == "10001:10001"
    assert inspect["Config"]["Labels"]["nexus.runtime_scope"] == "synthetic-only"
    image_id = inspect["Id"]
    checks = 3
    with owner_clean_temp(args.runner_temp) as temp:
        root = Path(temp)
        binary_sha = image_binary_sha(image, root)
        checks += 1
        approvals = root / "approvals"
        approvals.mkdir(mode=0o700)
        token = secrets.token_urlsafe(32)
        private = data_root(root / "isolated-synthetic-root")
        good_policy = private_file(
            approvals / "good.json", canonical(policy(SOURCE, binary_sha)))
        expected_policy = digest(good_policy)
        port = choose_port()

        def denied(label, *, git=SOURCE, binary_hash=binary_sha,
                   approval=good_policy, policy_hash=expected_policy,
                   datadir=private, mounted=True):
            nonlocal checks
            name, cmd = run_args(image, datadir, approval, binary_hash,
                                 policy_hash, git, port, token, use_mount=mounted,
                                 network="none")
            try:
                rejected = sh(cmd, good=False, timeout=25)
                assert ("DENIED" in rejected.stderr or "DENIED" in rejected.stdout), (
                    label + " did not produce a fail-closed reason")
                checks += 1
            finally:
                stop(name)

        denied("no-data-mount", mounted=False)
        denied("mismatch-binary", binary_hash="e" * 64)
        denied("stale-external-policy", policy_hash="e" * 64)
        denied("unapproved-revision", git="a" * 40)

        old_policy = private_file(
            approvals / "legacy.json", canonical(policy(LEGACY, binary_sha)))
        denied("banned-old-revision", git=LEGACY,
               approval=old_policy, policy_hash=digest(old_policy))

        production_policy = private_file(
            approvals / "production-policy.json",
            canonical(policy(SOURCE, binary_sha,
                             production_release_authorized=True)))
        denied("forged-production-grant", approval=production_policy,
               policy_hash=digest(production_policy))

        bad_scope = private_file(
            approvals / "bad-scope.json",
            canonical(policy(SOURCE, binary_sha,
                             execution_scope="production")))
        denied("production-scope", approval=bad_scope,
               policy_hash=digest(bad_scope))

        # A directory that was not operator-private is denied before reading
        # any data. Revert permissions on the test-only mounted directory.
        sh(["sudo", "chmod", "0755", private])
        denied("insecure-mount-permissions")
        sh(["sudo", "chmod", "0700", private])

        # Boot the *actual* guarded image with no alternative entrypoint.
        name, cmd = run_args(image, private, good_policy, binary_sha,
                             expected_policy, SOURCE, port, token)
        try:
            sh(cmd[:2] + ["-d"] + cmd[2:])
            await_ready(port, token, name)
            checks += 1
            message = {
                "request_id": "synthetic-guarded-container-request",
                "authority": "user", "action": "reflect",
                "subject": "synthetic", "payload": "disposable",
            }
            status, data = request(port, token, "POST", "/v1/requests", message)
            assert status == 202 and data.get("request_id") == message["request_id"]
            checks += 1
            status, data = request(port, token, "POST", "/v1/requests", message)
            assert status == 409 and data.get("error") == "request_id_replayed"
            checks += 1
        finally:
            stop(name)

        request_file = private / "requests" / message["request_id"].encode().hex()
        assert privileged_exists(request_file)
        assert privileged_bytes(request_file) == b"pending\n"
        checks += 1
        # Existing HISTORICAL target binary is permissive about umask.
        # Our guard catches this, then operator narrows permissions only on
        # this synthetic clone; the *new candidate Rust fix* is checked by
        # the independent full-head Cargo CI.
        if (privileged_mode(request_file) & 0o077 or
                privileged_mode(private / "requests") & 0o077):
            denied("historical-insecure-request-permissions")
            sh(["sudo", "chmod", "0700", private / "requests"])
            sh(["sudo", "chmod", "0600", request_file])
            checks += 1
        # A second guarded container on the same volume must not execute
        # concurrently with the first, even if policy and SHA are valid.
        # The *guard* directory flock remains held across fd-based exec.
        name, cmd = run_args(image, private, good_policy, binary_sha,
                             expected_policy, SOURCE, port, token)
        try:
            sh(cmd[:2] + ["-d"] + cmd[2:])
            await_ready(port, token, name)
            checks += 1
            status, data = request(port, token, "GET",
                                   "/v1/requests/" + message["request_id"])
            assert status == 200 and data.get("status", "").lower() == "pending"
            checks += 1
            duplicate_name, duplicate_cmd = run_args(
                image, private, good_policy, binary_sha, expected_policy,
                SOURCE, choose_port(), token, network="none")
            try:
                duplicate = sh(duplicate_cmd, good=False)
                assert ("DENIED" in duplicate.stderr or
                        "DENIED" in duplicate.stdout), "duplicate guarded launch was not blocked"
                checks += 1
            finally:
                stop(duplicate_name)
        finally:
            stop(name)

        # A modern runtime must keep a recovery quarantine intact through
        # the image entrypoint. Writes are refused even after positive boot.
        quarantine = private / ".nexus-recovery-required"
        sh(["sudo", "sh", "-c",
            "printf 'synthetic-recovery-not-authorized\\n' > " +
            str(quarantine)])
        sh(["sudo", "chown", "10001:10001", quarantine])
        sh(["sudo", "chmod", "0600", quarantine])
        name, cmd = run_args(image, private, good_policy, binary_sha,
                             expected_policy, SOURCE, port, token)
        try:
            sh(cmd[:2] + ["-d"] + cmd[2:])
            await_ready(port, token, name)
            status, data = request(
                port, token, "POST", "/v1/requests",
                dict(message, request_id="synthetic-quarantine-refusal"))
            assert status == 503 and data.get("error") == "recovery_acknowledgment_required"
            checks += 1
            assert not privileged_exists(private / "requests" /
                        "synthetic-quarantine-refusal".encode().hex())
            checks += 1
        finally:
            stop(name)
        assert privileged_bytes(quarantine) == b"synthetic-recovery-not-authorized\n"
        checks += 1

        # Tampered workspace schema must be denied before the gateway is
        # executed, even if the recovery marker is still present.
        workspace = private / (b"unsafe-workspace".hex() + ".json")
        sh(["sudo", "sh", "-c",
            "printf '{\"schema_version\":2}\\n' > " + str(workspace)])
        sh(["sudo", "chown", "10001:10001", workspace])
        sh(["sudo", "chmod", "0600", workspace])
        denied("unknown-workspace-schema")
        checks += 1

    print(json.dumps({
        "status": "PASS",
        "checks": checks,
        "scope": "real-oci-guarded-entrypoint-synthetic-rollback-exclusion",
        "local_image_id": image_id,
        "registry_image_digest_verified": False,
        "operator_image_provenance_attested": False,
        "legacy_image_deployment_changed": False,
        "production_release_authorized": False,
        "provider_runtime_touched": False,
        "release_gate": "BLOCKED",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
