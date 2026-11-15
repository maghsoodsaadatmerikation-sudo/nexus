#!/usr/bin/env python3
"""Three-custody role-separated key-transition evidence with real Ed25519."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "workspace-witness-key-transition.py"
TRUST = ROOT / "workspace-trust.py"
WITNESS = ROOT / "workspace-offsite-witness.py"
CUSTODIAN = ROOT / "workspace-witness-custodian.py"


def call(script, *args, success=True):
    result = subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True, text=True, check=False, timeout=45,
    )
    assert (result.returncode == 0) == success, (
        f"expected={success}, code={result.returncode}, cmd={script.name}, "
        f"args={[str(x) for x in args]}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    return result


def keypair(root, role):
    private = root / (role + ".private.pem")
    public = root / (role + ".public.pem")
    subprocess.run(
        ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(private)],
        capture_output=True, check=True, timeout=15,
    )
    os.chmod(private, 0o600)
    subprocess.run(
        ["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
        capture_output=True, check=True, timeout=15,
    )
    return private, public


def direct_hash(obj):
    return hashlib.sha256(
        (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                    separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-key-transition-fixture-") as folder:
        root = Path(folder)
        parties = {}
        for label in ("source", "outgoing", "incoming", "rogue"):
            p = root / ("custody-" + label)
            p.mkdir(mode=0o700)
            parties[label] = keypair(p, label)
        source_private, source_public = parties["source"]
        old_private, old_public = parties["outgoing"]
        new_private, new_public = parties["incoming"]
        rogue_private, rogue_public = parties["rogue"]

        operator = root / "operator"
        store = root / "receiver"
        data_private, data_public = keypair(root, "data-key")
        call(TRUST, "init", "--state-dir", operator)
        call(TRUST, "enroll", "--state-dir", operator,
             "--key-id", "data-key", "--public-key", data_public)
        signed = root / "source-receipt.json"
        call(WITNESS, "seal", "--state-dir", operator,
             "--witness-key-id", "source-approval",
             "--witness-private-key", source_private, "--output", signed)
        call(CUSTODIAN, "init", "--store", store,
             "--receiver-id", "independent-recipient",
             "--source-key-id", "source-approval",
             "--source-public-key", source_public,
             "--ack-key-id", "old-receiver-key",
             "--ack-public-key", old_public)
        package = root / "previous-signed-latest.json"
        issued = json.loads(call(CUSTODIAN, "receive", "--store", store,
                               "--receipt", signed,
                               "--ack-private-key", old_private).stdout)
        package.write_text(json.dumps(issued, ensure_ascii=False))
        os.chmod(package, 0o600)
        package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
        old_ledger = (store / "custodian.json").read_bytes()

        params = [
            "--receiver-id", "independent-recipient",
            "--source-key-id", "source-approval",
            "--source-public-key", source_public,
            "--outgoing-ack-key-id", "old-receiver-key",
            "--outgoing-ack-public-key", old_public,
            "--incoming-ack-key-id", "new-receiver-key",
            "--incoming-ack-public-key", new_public,
            "--trusted-latest-package", package,
            "--trusted-package-sha256", package_sha,
            "--minimum-sequence", "1",
        ]
        proposed = root / "proposal.json"
        result = call(TOOL, "prepare", *params, "--output", proposed)
        assert "0/3 consent signatures" in result.stdout
        assert not (store / "custodian.json").read_bytes() != old_ledger
        doc = json.loads(proposed.read_text())
        assert doc["approvals"] == {}
        proposal_sha = direct_hash(doc["proposal"])
        assert proposal_sha in result.stdout
        call(TOOL, "verify", *params, "--input", proposed, success=False)

        def sign(role, secret, incoming, output, approved=proposal_sha,
                 success=True):
            return call(
                TOOL, "sign", "--role", role, "--private-key", secret,
                "--trusted-proposal-sha256", approved,
                "--input", incoming, "--output", output,
                success=success,
            )

        sign("source", old_private, proposed, root / "wrong-signer.json",
             success=False)
        sign("source", source_private, proposed,
             root / "wrong-sha.json", approved="0" * 64, success=False)
        sign("incoming", rogue_private, proposed,
             root / "rogue-incoming.json", success=False)
        assert not (root / "wrong-signer.json").exists()

        source_approved = root / "source-approved.json"
        sign("source", source_private, proposed, source_approved)
        sign("source", source_private, source_approved,
             root / "duplicate-role.json", success=False)
        old_approved = root / "old-approved.json"
        sign("outgoing", old_private, source_approved, old_approved)
        call(TOOL, "verify", *params, "--input", old_approved, success=False)
        all_approved = root / "three-approvals.json"
        sign("incoming", new_private, old_approved, all_approved)
        result = call(TOOL, "verify", *params, "--input", all_approved)
        assert "3/3 Ed25519 approvals" in result.stdout
        assert "no actual key rotation" in result.stdout

        # Every signature is role-segregated and binds the whole exact
        # proposal: an attacker cannot repurpose old-role consent for new.
        original = all_approved.read_bytes()
        for label, mutation in (
            ("receiver", lambda d: d["proposal"].__setitem__("receiver_id", "wrong")),
            ("incoming-id", lambda d: d["proposal"].__setitem__("incoming_ack_key_id", "rogue")),
            ("latest", lambda d: d["proposal"].__setitem__("latest_sequence", 2)),
            ("fingerprint", lambda d: d["proposal"].__setitem__("incoming_public_sha256", "a" * 64)),
            ("signature", lambda d: d["approvals"].__setitem__("incoming", "AAAA")),
            ("wrong-role", lambda d: d["approvals"].__setitem__(
                "outgoing", d["approvals"]["incoming"])),
            ("extra", lambda d: d["proposal"].__setitem__("permit_runtime_import", True)),
            ("boolean", lambda d: d["proposal"].__setitem__("latest_sequence", True)),
        ):
            altered = json.loads(original)
            mutation(altered)
            bad = root / ("forged-" + label + ".json")
            bad.write_text(json.dumps(altered))
            call(TOOL, "verify", *params, "--input", bad, success=False)

        doubled = root / "duplicate-json.json"
        doubled.write_bytes(original.replace(b'"schema":', b'"schema":"evil","schema":', 1))
        call(TOOL, "verify", *params, "--input", doubled, success=False)
        symlink = root / "symlink.json"
        symlink.symlink_to(all_approved)
        call(TOOL, "verify", *params, "--input", symlink, success=False)

        call(TOOL, "verify", *params[:-2], "--minimum-sequence", "2",
             "--input", all_approved, success=False)
        wrong_pub = [
            rogue_public if item == new_public else item for item in params
        ]
        call(TOOL, "verify", *wrong_pub, "--input", all_approved,
             success=False)
        wrong_package_sha = [
            "f" * 64 if item == package_sha else item for item in params
        ]
        call(TOOL, "verify", *wrong_package_sha, "--input", all_approved,
             success=False)

        # All three authorizations are an offline agreement only. The v1
        # recipient cannot accept a new private signing key until a
        # separately reviewed versioned-ledger migration is implemented.
        assert (store / "custodian.json").read_bytes() == old_ledger
        call(TRUST, "revoke", "--state-dir", operator, "--key-id", "data-key")
        next_receipt = root / "next-source-receipt.json"
        call(WITNESS, "seal", "--state-dir", operator,
             "--witness-key-id", "source-approval",
             "--witness-private-key", source_private,
             "--output", next_receipt)
        call(CUSTODIAN, "receive", "--store", store,
             "--receipt", next_receipt,
             "--ack-private-key", new_private, success=False)
        assert (store / "custodian.json").read_bytes() == old_ledger
        continuation = json.loads(call(CUSTODIAN, "receive",
             "--store", store, "--receipt", next_receipt,
             "--ack-private-key", old_private).stdout)
        assert continuation["ack"]["sequence"] == 2
        # Previous approvals are still correctly signed, but referencing an
        # old latest checkpoint with a now-pinned floor of 2 is denied.
        call(TOOL, "verify", *params[:-2], "--minimum-sequence", "2",
             "--input", all_approved, success=False)
        print("NEXUS RECEIVER KEY TRANSITION CONSENT: PASS "
              "(independent role signatures, exact prior checkpoint, no unsafe key cutover)")


if __name__ == "__main__":
    main()
