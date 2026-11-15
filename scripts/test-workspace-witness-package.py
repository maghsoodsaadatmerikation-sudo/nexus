#!/usr/bin/env python3
"""Test root-installed, independently pinned custodian Python bundle.

Creates only ephemeral local CI state and a randomly named /run directory.
Requires passwordless sudo on the disposable GitHub runner.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PKG = HERE / "workspace-witness-package.py"
TRUST = HERE / "workspace-trust.py"
CUSTODIAN = HERE / "workspace-witness-custodian.py"
HOST_NAME = "workspace-witness-host.py"


def run(*args, success=True):
    argv = [str(a) for a in args]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=45)
    assert (result.returncode == 0) == success, (
        f"expected success={success}, rc={result.returncode}, argv={argv!r}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    return result


def keypair(folder, name):
    secret = folder / (name + ".private.pem")
    public = folder / (name + ".pub.pem")
    run("openssl", "genpkey", "-algorithm", "Ed25519", "-out", secret)
    os.chmod(secret, 0o600)
    run("openssl", "pkey", "-in", secret, "-pubout", "-out", public)
    return secret, public


def main():
    if os.name != "posix" or shutil.which("sudo") is None:
        raise RuntimeError("test requires POSIX runner with sudo")
    target = Path("/run") / ("nexus-witness-code-test-" + secrets.token_hex(10))
    with tempfile.TemporaryDirectory(prefix="nexus-installed-witness-") as folder:
        root = Path(folder)
        bundle = root / "code-bundle.json"
        run(sys.executable, PKG, "build", "--source-dir", HERE,
            "--output", bundle)
        good_digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        assert len(good_digest) == 64
        duplicate = root / "duplicate.json"
        run(sys.executable, PKG, "build", "--source-dir", HERE,
            "--output", duplicate)
        assert duplicate.read_bytes() == bundle.read_bytes(), "non-deterministic bundle"
        run(sys.executable, PKG, "build", "--source-dir", HERE,
            "--output", bundle, success=False)

        install = [
            sys.executable, PKG, "install", "--bundle", bundle,
            "--trusted-sha256", good_digest, "--destination", target,
        ]
        run(*install, success=False)  # root authority is mandatory
        run("sudo", "-n", *install[:-4], "--trusted-sha256", "0" * 64,
            "--destination", target, success=False)
        assert not target.exists()
        try:
            run("sudo", "-n", *install)
            assert target.is_dir()
            verify = [
                sys.executable, PKG, "verify", "--destination", target,
                "--bundle", bundle, "--trusted-sha256", good_digest,
            ]
            run(*verify)
            run("sudo", "-n", *install, success=False)  # no overwrite
            run(*verify[:-1], "0" * 64, success=False)

            # Exercise the complete installed dependency graph from the
            # actual installed root-owned code (without inserting its
            # untrusted checkout path onto Python's import search path).
            data_secret, data_pub = keypair(root, "data")
            source_secret, source_pub = keypair(root, "external-source")
            ack_secret, ack_pub = keypair(root, "independent-ack")
            wrong_secret, wrong_pub = keypair(root, "wrong-ack")
            state = root / "operator-owned"
            store = root / "receiver"
            run(sys.executable, TRUST, "init", "--state-dir", state)
            run(sys.executable, TRUST, "enroll", "--state-dir", state,
                "--key-id", "source-data", "--public-key", data_pub)
            run(sys.executable, CUSTODIAN, "init", "--store", store,
                "--receiver-id", "independent-code-install",
                "--source-key-id", "source-witness",
                "--source-public-key", source_pub,
                "--ack-key-id", "receiver-ack", "--ack-public-key", ack_pub)

            config_root = Path("/run") / (
                "nexus-witness-rootcfg-" + secrets.token_hex(10)
            )
            unsafe_config = root / "user-config.json"
            unsafe_config.write_text(json.dumps({
                "schema": "nexus.offsite.root-pinned-launch.v1",
                "store_dir": str(store),
                "ack_private_key": str(ack_secret),
            }))
            run("sudo", "-n", "install", "-d", "-o", "root", "-g", "root",
                "-m", "0755", config_root)
            try:
                config = config_root / "config.json"
                run("sudo", "-n", "install", "-o", "root", "-g", "root",
                    "-m", "0644", unsafe_config, config)
                deployed_host = target / HOST_NAME
                run(sys.executable, "-I", deployed_host, "check", "--config", config)
                run(sys.executable, "-I", deployed_host, "check", "--config",
                    unsafe_config, success=False)

                # An unrelated key or world-writable root config cannot
                # claim deploy readiness, even if the receiver has a valid
                # previous history.
                wrong_config = root / "wrong-key-config.json"
                wrong_config.write_text(json.dumps({
                    "schema": "nexus.offsite.root-pinned-launch.v1",
                    "store_dir": str(store),
                    "ack_private_key": str(wrong_secret),
                }))
                wrong_installed = config_root / "wrong.json"
                run("sudo", "-n", "install", "-o", "root", "-g", "root",
                    "-m", "0644", wrong_config, wrong_installed)
                run(sys.executable, "-I", deployed_host, "check",
                    "--config", wrong_installed, success=False)
                run("sudo", "-n", "chmod", "0666", config)
                run(sys.executable, "-I", deployed_host, "check",
                    "--config", config, success=False)
                run("sudo", "-n", "chmod", "0644", config)
                run(sys.executable, "-I", deployed_host, "check", "--config", config)

                # Integrity check must catch code replacement and extraneous
                # new files in the exact installed directory.
                code_path = target / HOST_NAME
                run("sudo", "-n", "chmod", "0666", code_path)
                run(*verify, success=False)
                run("sudo", "-n", "chmod", "0644", code_path)
                run(*verify)
                extra = target / "unexpected.py"
                run("sudo", "-n", "touch", extra)
                run(*verify, success=False)
                run("sudo", "-n", "rm", "-f", extra)
                run(*verify)

                # Rewritten package with the same external expected digest
                # is rejected even if its internal files are self-consistent.
                changed_bundle = root / "altered.json"
                tampered = json.loads(bundle.read_text())
                tampered["files"][0]["content_base64"] = "AAAA"
                changed_bundle.write_text(json.dumps(tampered))
                run(sys.executable, PKG, "verify", "--destination", target,
                    "--bundle", changed_bundle,
                    "--trusted-sha256", good_digest, success=False)
            finally:
                run("sudo", "-n", "rm", "-f", config_root / "config.json",
                    config_root / "wrong.json")
                run("sudo", "-n", "rmdir", config_root)
        finally:
            # Disposable /run code is never exported or installed on an
            # external host. The path is a fresh random test-owned directory.
            if target.exists():
                run("sudo", "-n", "rm", "-rf", target)
    print("ROOT-OWNED WITNESS CODE PACKAGE: PASS (CI-only ephemeral installation)")


if __name__ == "__main__":
    main()
