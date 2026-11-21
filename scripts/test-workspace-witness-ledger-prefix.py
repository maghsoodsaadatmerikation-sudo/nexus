#!/usr/bin/env python3
"""Synthetic adversarial proof of Ed25519 witness-ledger prefix continuity."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TRUST = HERE / "workspace-trust.py"
WITNESS = HERE / "workspace-offsite-witness.py"
RECEIVER = HERE / "workspace-witness-custodian.py"
PROOF = HERE / "workspace-witness-ledger-prefix.py"


def invoke(script, *args, good=True):
    cmd = [sys.executable, str(script), *map(str, args)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=50)
    assert (out.returncode == 0) is good, (
        f"unexpected exit {out.returncode}: {cmd}\n{out.stdout}\n{out.stderr}"
    )
    return out


def keypair(root, label):
    secret, public = root / (label + ".secret.pem"), root / (label + ".public.pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519",
                    "-out", str(secret)], check=True, capture_output=True, timeout=20)
    os.chmod(secret, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(secret), "-pubout", "-out",
                    str(public)], check=True, capture_output=True, timeout=20)
    return secret, public


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = 0
    with tempfile.TemporaryDirectory(prefix="nexus-ledger-prefix-proof-") as td:
        root = Path(td)
        state, receiver, independent = root / "source", root / "receiver", root / "external"
        independent.mkdir(mode=0o700)
        data_a, pub_a = keypair(root, "state-a")
        data_b, pub_b = keypair(root, "state-b")
        data_c, pub_c = keypair(root, "state-c")
        data_d, pub_d = keypair(root, "state-d")
        source_secret, source_public = keypair(root, "receipt-source")
        ack_secret, ack_public = keypair(root, "recipient")
        _, rogue_public = keypair(root, "rogue")
        invoke(TRUST, "init", "--state-dir", state)
        invoke(RECEIVER, "init", "--store", receiver,
               "--receiver-id", "independent-history",
               "--source-key-id", "receipt-signer", "--source-public-key", source_public,
               "--ack-key-id", "recipient-signer", "--ack-public-key", ack_public)

        def seal(label):
            receipt = root / (label + ".receipt.json")
            invoke(WITNESS, "seal", "--state-dir", state,
                   "--witness-key-id", "receipt-signer",
                   "--witness-private-key", source_secret, "--output", receipt)
            return receipt

        def accept(receipt, destination=receiver):
            return json.loads(invoke(
                RECEIVER, "receive", "--store", destination, "--receipt", receipt,
                "--ack-private-key", ack_secret).stdout)

        def snapshot(label, destination=receiver):
            path = independent / (label + ".json")
            path.write_bytes((destination / "custodian.json").read_bytes())
            os.chmod(path, 0o600)
            return path

        def checkpoint(label, obj):
            path = independent / (label + ".json")
            path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")))
            os.chmod(path, 0o600)
            return path

        invoke(TRUST, "enroll", "--state-dir", state,
               "--key-id", "data-a", "--public-key", pub_a)
        p1 = accept(seal("first"))
        first = snapshot("ledger-first")
        assert p1["ack"]["sequence"] == 1
        invoke(TRUST, "enroll", "--state-dir", state,
               "--key-id", "data-b", "--public-key", pub_b)
        p2 = accept(seal("second"))
        baseline = snapshot("baseline")
        assert p2["ack"]["sequence"] == 2
        invoke(TRUST, "enroll", "--state-dir", state,
               "--key-id", "data-c", "--public-key", pub_c)
        p3 = accept(seal("third"))
        candidate = snapshot("candidate")
        latest = checkpoint("external-checkpoint", p3)
        initial = (sha(baseline), sha(candidate), sha(latest))

        def proof(*, old=baseline, new=candidate, package=latest,
                  old_pin=initial[0], new_pin=initial[1], package_pin=initial[2],
                  identity="independent-history", ack_pub=ack_public,
                  floor=2, good=True):
            params = [
                "--baseline-ledger", old, "--baseline-sha256", old_pin,
                "--candidate-ledger", new, "--candidate-sha256", new_pin,
                "--trusted-latest-package", package, "--trusted-package-sha256", package_pin,
                "--receiver-id", identity,
                "--source-key-id", "receipt-signer", "--source-public-key", source_public,
                "--ack-key-id", "recipient-signer", "--ack-public-key", ack_pub,
                "--minimum-sequence", floor,
            ]
            return invoke(PROOF, *params, good=good)

        report = json.loads(proof().stdout); checks += 1
        assert report["status"] == "verified-signed-prefix"
        assert (report["baseline_sequence"], report["candidate_sequence"],
                report["new_acknowledgments"]) == (2, 3, 1)
        assert report["independent_host_or_custody_proven"] is False
        assert report["authorizes_import_deployment_or_key_rotation"] is False

        for opts in [
            {"old_pin": "0" * 64},
            {"new_pin": "a" * 64},
            {"package_pin": "b" * 64},
            {"identity": "other-receiver"},
            {"ack_pub": rogue_public},
            {"floor": 4},
            {"floor": 1},
            {"new": baseline, "new_pin": sha(baseline)},
            {"new": first, "new_pin": sha(first)},
            {"package": checkpoint("stale-checkpoint", p2),
             "package_pin": sha(checkpoint("stale-checkpoint-copy", p2))},
        ]:
            proof(**opts, good=False)
            checks += 1

        # A different valid signed ledger, forked from sequence 1, is not
        # allowed to supplant a separately approved two-entry baseline.
        fork = root / "forked-receiver"
        fork.mkdir(mode=0o700)
        (fork / "custodian.json").write_bytes(first.read_bytes())
        os.chmod(fork / "custodian.json", 0o600)
        invoke(TRUST, "enroll", "--state-dir", state,
               "--key-id", "data-d", "--public-key", pub_d)
        accept(seal("fork-second"), fork)
        invoke(TRUST, "revoke", "--state-dir", state, "--key-id", "data-d")
        fork_last = accept(seal("fork-third"), fork)
        fork_file = snapshot("valid-but-forked", fork)
        fork_checkpoint = checkpoint("forked-latest", fork_last)
        proof(new=fork_file, new_pin=sha(fork_file), package=fork_checkpoint,
              package_pin=sha(fork_checkpoint), good=False)
        checks += 1

        corrupted = json.loads(candidate.read_text())
        corrupted["entries"][0]["ack"]["signature_base64"] = "AAAA"
        invalid = checkpoint("invalid-signature", corrupted)
        proof(new=invalid, new_pin=sha(invalid), good=False)
        checks += 1
        duplicate = independent / "ambiguous.json"
        duplicate.write_bytes(candidate.read_bytes().replace(
            b'"schema":', b'"schema":"forged","schema":', 1))
        proof(new=duplicate, new_pin=sha(duplicate), good=False)
        checks += 1

        linked = independent / "linked.json"
        linked.symlink_to(candidate)
        proof(new=linked, good=False)
        checks += 1
        hardlinked = independent / "hardlinked.json"
        os.link(candidate, hardlinked)
        proof(new=hardlinked, good=False)
        checks += 1
        hardlinked.unlink()
        assert (sha(baseline), sha(candidate), sha(latest)) == initial
    print(json.dumps({"status": "PASS", "checks": checks,
                      "scope": "synthetic-signed-prefix-and-adversarial-forks",
                      "independent_real_receiver_tested": False}))


if __name__ == "__main__":
    main()
