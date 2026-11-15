#!/usr/bin/env python3
"""End-to-end independent Ed25519 custodial receipt tests with disposable keys."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
CUSTODIAN = HERE / "workspace-witness-custodian.py"
WITNESS = HERE / "workspace-offsite-witness.py"
TRUST = HERE / "workspace-trust.py"


def call(tool, *params, succeeds=True):
    command = [sys.executable, str(tool), *map(str, params)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=45)
    assert (result.returncode == 0) is succeeds, (
        f"exit={result.returncode} expected_success={succeeds}: {command}\n"
        f"out={result.stdout}\nerr={result.stderr}"
    )
    return result


def keypair(root, name):
    secret = root / (name + ".private.pem")
    public = root / (name + ".public.pem")
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(secret)],
        capture_output=True, timeout=20, check=True,
    )
    os.chmod(secret, 0o600)
    subprocess.run(
        ["openssl", "pkey", "-in", str(secret), "-pubout", "-out", str(public)],
        capture_output=True, timeout=20, check=True,
    )
    return secret, public


def tamper(value, change):
    obj = json.loads(json.dumps(value))
    change(obj)
    return obj


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-independent-custodian-") as directory:
        root = Path(directory)
        owner = root / "nexus-local-private"
        recipient = root / "separate-custodian"
        receipts = root / "transport-only"
        receipts.mkdir(mode=0o700)
        data_priv, data_pub = keypair(root, "data-source")
        next_priv, next_pub = keypair(root, "later-data-source")
        source_priv, source_pub = keypair(root, "offsite-receipt-signer")
        ack_priv, ack_pub = keypair(root, "independent-custodian")
        rogue_priv, rogue_pub = keypair(root, "rogue-custodian")

        call(TRUST, "init", "--state-dir", owner)
        call(TRUST, "enroll", "--state-dir", owner,
             "--key-id", "source-data-1", "--public-key", data_pub)
        # Source receipt signing remains explicitly separate from NEXUS data keys.
        def seal(label):
            receipt = receipts / (label + ".json")
            call(WITNESS, "seal", "--state-dir", owner,
                 "--witness-key-id", "witness-authority",
                 "--witness-private-key", source_priv, "--output", receipt)
            return receipt

        a = seal("state-1")
        init = [
            "init", "--store", recipient, "--receiver-id", "external-org-1",
            "--source-key-id", "witness-authority", "--source-public-key", source_pub,
            "--ack-key-id", "receiver-key-1", "--ack-public-key", ack_pub,
        ]
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        call(CUSTODIAN, *init)
        call(CUSTODIAN, *init, succeeds=False)
        assert recipient.stat().st_mode & 0o077 == 0

        def receive(receipt=a, private=ack_priv, succeeds=True):
            result = call(
                CUSTODIAN, "receive", "--store", recipient,
                "--receipt", receipt, "--ack-private-key", private,
                succeeds=succeeds,
            )
            return json.loads(result.stdout) if succeeds else None

        package1 = receive()
        assert package1["ack"]["sequence"] == 1
        assert package1["ack"]["previous_ack_sha256"] == "0" * 64
        assert package1["receipt"]["state_sha256"] == json.loads(a.read_text())["state_sha256"]
        assert not any(
            "PRIVATE KEY" in (recipient / "custodian.json").read_text()
            or key in (recipient / "custodian.json").read_text()
            for key in ("private_key", "secret_key")
        )
        assert json.loads(call(CUSTODIAN, "latest", "--store", recipient).stdout) == package1

        def verify_package(package, *, minimum=1, state=True, pub=ack_pub,
                           source=source_pub, expected="external-org-1", succeeds=True):
            file = receipts / "independent-package.json"
            file.write_text(json.dumps(package, ensure_ascii=False))
            args = [
                "verify-package", "--package", file,
                "--expected-receiver-id", expected,
                "--trusted-source-key-id", "witness-authority",
                "--trusted-source-public-key", source,
                "--trusted-ack-key-id", "receiver-key-1",
                "--trusted-ack-public-key", pub,
                "--minimum-sequence", str(minimum),
            ]
            if state:
                args += ["--state-dir", owner]
            call(CUSTODIAN, *args, succeeds=succeeds)

        verify_package(package1)
        verify_package(package1, minimum=2, succeeds=False)
        verify_package(package1, pub=rogue_pub, succeeds=False)
        verify_package(package1, source=rogue_pub, succeeds=False)
        verify_package(package1, expected="different-organization", succeeds=False)
        receive(succeeds=False)
        # A re-signed receipt for the same state, with a different nonce,
        # must not allow receipt replay under a new sequence number.
        same_state = seal("same-state")
        receive(same_state, succeeds=False)

        for label, mutator in [
            ("ack-sig", lambda p: p["ack"].__setitem__("signature_base64", "AAAA")),
            ("receipt", lambda p: p["receipt"].__setitem__("state_sha256", "0"*64)),
            ("sequence", lambda p: p["ack"].__setitem__("sequence", 2)),
            ("status", lambda p: p["ack"].__setitem__("schema", "runtime-authority")),
            ("bool", lambda p: p["ack"].__setitem__("sequence", True)),
            ("extra", lambda p: p["ack"].__setitem__("can_import", True)),
        ]:
            verify_package(tamper(package1, mutator), succeeds=False)
        duplicate = receipts / "duplicate-object.json"
        duplicate.write_text(
            json.dumps(package1).replace('"schema":', '"schema":"injected","schema":', 1)
        )
        call(CUSTODIAN, "verify-package", "--package", duplicate,
             "--expected-receiver-id", "external-org-1",
             "--trusted-source-key-id", "witness-authority",
             "--trusted-source-public-key", source_pub,
             "--trusted-ack-key-id", "receiver-key-1",
             "--trusted-ack-public-key", ack_pub, succeeds=False)

        # Wrong key cannot issue a valid independent acknowledgment; it must
        # not advance the receiver's next sequence number.
        call(TRUST, "enroll", "--state-dir", owner,
             "--key-id", "source-data-2", "--public-key", next_pub)
        b = seal("state-2")
        receive(b, private=rogue_priv, succeeds=False)
        assert json.loads(call(CUSTODIAN, "latest", "--store", recipient).stdout) == package1
        package2 = receive(b)
        assert package2["ack"]["sequence"] == 2
        verify_package(package2, minimum=2)
        verify_package(package1, minimum=2, succeeds=False)
        verify_package(package1, state=True, succeeds=False)
        assert json.loads(call(CUSTODIAN, "latest", "--store", recipient).stdout) == package2

        # A genuine, previously valid local registry restored by an adversary
        # is not an equal match for the latest independent acknowledged state.
        old = owner / "trust-state.json"
        current = old.read_bytes()
        call(TRUST, "revoke", "--state-dir", owner, "--key-id", "source-data-2")
        c = seal("state-3")
        previous = old.read_bytes()
        old.write_bytes(current)
        assert call(TRUST, "status", "--state-dir", owner).returncode == 0
        verify_package(package2, minimum=2)
        old.write_bytes(previous)
        verify_package(package2, minimum=2, succeeds=False)

        # On a new externally retained checkpoint the current local state is
        # allowed again. Concurrency may acknowledge only once.
        receive_args = [
            sys.executable, str(CUSTODIAN), "receive", "--store", str(recipient),
            "--receipt", str(c), "--ack-private-key", str(ack_priv),
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(
                lambda _: subprocess.run(receive_args, capture_output=True, timeout=45).returncode,
                (0, 1),
            ))
        assert sorted(statuses) == [0, 1], statuses
        package3 = json.loads(call(CUSTODIAN, "latest", "--store", recipient).stdout)
        assert package3["ack"]["sequence"] == 3
        assert package3["ack"]["previous_ack_sha256"] != "0" * 64
        verify_package(package3, minimum=3)
        verify_package(package2, minimum=3, succeeds=False)

        # Corruption must prevent BOTH reads and new writes, rather than
        # silently reinitializing the receiver or resetting receipt sequence.
        ledger = recipient / "custodian.json"
        saved = ledger.read_bytes()
        ledger.write_bytes(b"{not-json}")
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        receive(c, succeeds=False)
        ledger.write_bytes(saved)
        forged = json.loads(saved)
        forged["entries"][1]["ack"]["sequence"] = 13
        ledger.write_text(json.dumps(forged))
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        ledger.write_bytes(saved)

        ledger.unlink()
        ledger.symlink_to(receipts / "state-3.json")
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        ledger.unlink()
        external = receipts / "backup-ledger.json"
        external.write_bytes(saved)
        os.link(external, ledger)
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        ledger.unlink()
        ledger.write_bytes(saved)
        os.chmod(ledger, 0o600)
        os.chmod(recipient, 0o755)
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        os.chmod(recipient, 0o700)
        ledger.unlink()
        call(CUSTODIAN, "latest", "--store", recipient, succeeds=False)
        assert not ledger.exists(), "deleted custodian state cannot be auto-initialized"

    print("INDEPENDENT CUSTODIAN RECEIPT ACCEPTANCE: PASS (disposable keys, separate simulated stores)")


if __name__ == "__main__":
    main()
