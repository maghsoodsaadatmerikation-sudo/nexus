#!/usr/bin/env python3
"""Synthetic offsite-rollback witnesses with independently pinned real Ed25519 keys."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
WITNESS = HERE / "workspace-offsite-witness.py"
TRUST = HERE / "workspace-trust.py"


def run(script, *args, success=True):
    result = subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        text=True, capture_output=True, timeout=45, check=False,
    )
    assert (result.returncode == 0) == success, (
        f"{script.name} expected success={success}, exit={result.returncode}; "
        f"stdout={result.stdout!r}; stderr={result.stderr!r}"
    )
    return result


def pair(root: Path, name: str):
    private, public = root / (name + "-private.pem"), root / (name + "-public.pem")
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(private)],
        capture_output=True, timeout=20, check=True,
    )
    os.chmod(private, 0o600)
    subprocess.run(
        ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
        capture_output=True, timeout=20, check=True,
    )
    return private, public


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-offsite-synthetic-") as folder:
        root = Path(folder)
        state = root / "operator-owned"
        distant = root / "separate-witness-copy"
        distant.mkdir()
        data_secret, data_public = pair(root, "data-issuer")
        next_secret, next_public = pair(root, "next-issuer")
        witness_secret, witness_public = pair(root, "independent-witness")
        forged_secret, forged_public = pair(root, "false-witness")
        args = ("--state-dir", state)
        record_a = distant / "a.json"
        record_b = distant / "b.json"
        record_c = distant / "c.json"

        run(TRUST, "init", *args)
        run(TRUST, "enroll", *args, "--key-id", "data-a", "--public-key", data_public)
        seal_a = (
            "seal", *args, "--output", record_a, "--witness-key-id", "external-r1",
            "--witness-private-key", witness_secret,
        )
        check = (
            "check", *args, "--receipt", record_a,
            "--trusted-key-id", "external-r1", "--trusted-public-key", witness_public,
        )
        run(WITNESS, *seal_a)
        assert record_a.stat().st_mode & 0o077 == 0
        run(WITNESS, *seal_a, success=False)  # no overwrite
        run(WITNESS, *check)
        run(WITNESS, "verify-receipt", "--receipt", record_a,
            "--trusted-key-id", "external-r1", "--trusted-public-key", witness_public)

        # Identity selection must come from the independently approved key,
        # not the receipt contents or NEXUS data-key registry.
        run(WITNESS, "check", *args, "--receipt", record_a,
            "--trusted-key-id", "untrusted-alias", "--trusted-public-key",
            witness_public, success=False)
        run(WITNESS, "check", *args, "--receipt", record_a,
            "--trusted-key-id", "external-r1", "--trusted-public-key",
            forged_public, success=False)
        run(WITNESS, "seal", *args, "--output", distant / "invalid-data-signer.json",
            "--witness-key-id", "external-r1", "--witness-private-key",
            data_secret, success=False)

        # A legitimate local change must *not* be mislabeled a match for the
        # previous checkpoint. The operator needs to publish a new receipt.
        snapshot_a = (state / "trust-state.json").read_bytes()
        run(TRUST, "enroll", *args, "--key-id", "data-b", "--public-key", next_public)
        run(WITNESS, *check, success=False)
        run(WITNESS, "seal", *args, "--output", record_b,
            "--witness-key-id", "external-r1", "--witness-private-key",
            witness_secret)
        check_b = (
            "check", *args, "--receipt", record_b, "--trusted-key-id",
            "external-r1", "--trusted-public-key", witness_public,
        )
        run(WITNESS, *check_b)
        snapshot_b = (state / "trust-state.json").read_bytes()

        # The attacker may replace the entire valid registry with a former
        # real state. A separately retained newest receipt catches rollback.
        (state / "trust-state.json").write_bytes(snapshot_a)
        run(TRUST, "status", *args)  # Previous state is internally well formed.
        run(WITNESS, *check_b, success=False)
        run(WITNESS, "verify-receipt", "--receipt", record_b,
            "--trusted-key-id", "external-r1", "--trusted-public-key", witness_public)
        (state / "trust-state.json").write_bytes(snapshot_b)
        run(WITNESS, *check_b)

        # Permanent key revocation changes state and needs its own witness.
        run(TRUST, "revoke", *args, "--key-id", "data-b")
        run(WITNESS, *check_b, success=False)
        run(WITNESS, "seal", *args, "--output", record_c,
            "--witness-key-id", "external-r1", "--witness-private-key",
            witness_secret)
        check_c = (
            "check", *args, "--receipt", record_c, "--trusted-key-id",
            "external-r1", "--trusted-public-key", witness_public,
        )
        run(WITNESS, *check_c)
        run(WITNESS, *check_b, success=False)

        # Neither a digest edit nor a re-labeled key nor a fabricated
        # signature can create a valid independently authenticated receipt.
        original = record_c.read_bytes()
        for label, mutation in (
            ("digest", lambda doc: doc.__setitem__("state_sha256", "0" * 64)),
            ("key", lambda doc: doc.__setitem__("witness_key_id", "different")),
            ("role", lambda doc: doc.__setitem__("role", "runtime_import")),
            ("type", lambda doc: doc.__setitem__("key_count", True)),
            ("signature", lambda doc: doc.__setitem__("signature_base64", "AAAA")),
        ):
            tampered = json.loads(original)
            mutation(tampered)
            bad = distant / (label + ".json")
            bad.write_text(json.dumps(tampered))
            run(WITNESS, "check", *args, "--receipt", bad,
                "--trusted-key-id", "external-r1",
                "--trusted-public-key", witness_public, success=False)
        duplicate = distant / "duplicate.json"
        duplicate.write_bytes(original.replace(b'"schema":', b'"schema":"fake", "schema":'))
        run(WITNESS, "verify-receipt", "--receipt", duplicate,
            "--trusted-key-id", "external-r1",
            "--trusted-public-key", witness_public, success=False)

        # Signing key cannot be public, world-readable, a directory, or
        # linked to another file.
        os.chmod(witness_secret, 0o644)
        run(WITNESS, "seal", *args, "--output", distant / "world-readable.json",
            "--witness-key-id", "external-r1",
            "--witness-private-key", witness_secret, success=False)
        os.chmod(witness_secret, 0o600)
        run(WITNESS, "seal", *args, "--output", state / "inside.json",
            "--witness-key-id", "external-r1",
            "--witness-private-key", witness_secret, success=False)
        symlink = distant / "alias.json"
        symlink.symlink_to(record_c)
        run(WITNESS, "check", *args, "--receipt", symlink,
            "--trusted-key-id", "external-r1",
            "--trusted-public-key", witness_public, success=False)
        hardlink = distant / "hardlink.json"
        os.link(record_c, hardlink)
        run(WITNESS, "check", *args, "--receipt", hardlink,
            "--trusted-key-id", "external-r1",
            "--trusted-public-key", witness_public, success=False)

        # Exclusive destination creation is safe under concurrent signers.
        race = distant / "one-shot.json"
        race_args = [
            "seal", *args, "--output", race, "--witness-key-id", "external-r1",
            "--witness-private-key", witness_secret,
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(
                lambda _: subprocess.run([sys.executable, str(WITNESS), *map(str, race_args)],
                                         capture_output=True, timeout=45).returncode,
                range(2),
            ))
        assert sorted(outcomes) == [0, 1], outcomes
        run(WITNESS, "check", *args, "--receipt", race,
            "--trusted-key-id", "external-r1", "--trusted-public-key", witness_public)

        print("OFFSITE ROLLBACK WITNESS: PASS (synthetic, independent key, no external publication)")


if __name__ == "__main__":
    main()
