#!/usr/bin/env python3
"""Synthetic real-Ed25519 key-epoch bridge and hostile-history regression."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TRUST = HERE / "workspace-trust.py"
WITNESS = HERE / "workspace-offsite-witness.py"
CUSTODIAN = HERE / "workspace-witness-custodian.py"
TRANSITION = HERE / "workspace-witness-key-transition.py"
VERIFIER = HERE / "workspace-witness-key-epoch-v2.py"
spec = importlib.util.spec_from_file_location("nexus_test_v2_verifier", VERIFIER)
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)


def call(script, *args, good=True):
    command = [sys.executable, str(script), *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert (result.returncode == 0) is good, (
        f"exit {result.returncode}, expected {good}; {command}; "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}")
    return result


def keypair(root, label):
    private, public = root / (label + ".private.pem"), root / (label + ".public.pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519",
                    "-out", str(private)], check=True, capture_output=True, timeout=20)
    os.chmod(private, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(private),
                    "-pubout", "-out", str(public)], check=True,
                   capture_output=True, timeout=20)
    return private, public


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(root, name, data):
    path = root / (name + ".json")
    path.write_bytes(v2.trust.encode_json(data))
    os.chmod(path, 0o600)
    return path


def main():
    checked = 0
    with tempfile.TemporaryDirectory(prefix="nexus-v2-key-epoch-fixture-") as td:
        root = Path(td)
        source = root / "data-state"
        store = root / "receiver-v1"
        retained = root / "independent-checkpoints"
        retained.mkdir(mode=0o700)
        source_priv, source_pub = keypair(root, "witness-source")
        old_priv, old_pub = keypair(root, "outgoing-receiver")
        new_priv, new_pub = keypair(root, "incoming-receiver")
        rogue_priv, rogue_pub = keypair(root, "rogue-receiver")
        data1_priv, data1_pub = keypair(root, "data1")
        data2_priv, data2_pub = keypair(root, "data2")
        data3_priv, data3_pub = keypair(root, "data3")
        call(TRUST, "init", "--state-dir", source)
        call(TRUST, "enroll", "--state-dir", source,
             "--key-id", "data1", "--public-key", data1_pub)

        def source_receipt(label):
            receipt = retained / (label + ".receipt.json")
            call(WITNESS, "seal", "--state-dir", source,
                 "--witness-key-id", "source-signer",
                 "--witness-private-key", source_priv, "--output", receipt)
            return json.loads(receipt.read_text())

        call(CUSTODIAN, "init", "--store", store,
             "--receiver-id", "custodian-organization",
             "--source-key-id", "source-signer", "--source-public-key", source_pub,
             "--ack-key-id", "receiver-old", "--ack-public-key", old_pub)
        old_receipt = save(retained, "old-receipt", source_receipt("first"))
        old_package = json.loads(call(
            CUSTODIAN, "receive", "--store", store, "--receipt", old_receipt,
            "--ack-private-key", old_priv).stdout)
        old_package_file = save(retained, "old-latest-package", old_package)
        old_ledger = retained / "old-custodian.json"
        old_ledger.write_bytes((store / "custodian.json").read_bytes())
        original_store_bytes = (store / "custodian.json").read_bytes()
        old_ack_hash = v2.custodian.digest(old_package["ack"])

        common = [
            "--receiver-id", "custodian-organization",
            "--source-key-id", "source-signer", "--source-public-key", source_pub,
            "--outgoing-ack-key-id", "receiver-old",
            "--outgoing-ack-public-key", old_pub,
            "--incoming-ack-key-id", "receiver-new",
            "--incoming-ack-public-key", new_pub,
            "--trusted-latest-package", old_package_file,
            "--trusted-package-sha256", sha(old_package_file),
            "--minimum-sequence", "1",
        ]
        proposal_file = retained / "proposal.json"
        call(TRANSITION, "prepare", *common, "--output", proposal_file)
        proposal = json.loads(proposal_file.read_text())["proposal"]
        proposal_hash = hashlib.sha256(v2.trust.encode_json(proposal)).hexdigest()
        in_file = proposal_file
        for role, private in (("source", source_priv),
                              ("outgoing", old_priv),
                              ("incoming", new_priv)):
            out_file = retained / (role + "-consent.json")
            call(TRANSITION, "sign", "--input", in_file, "--output", out_file,
                 "--role", role, "--private-key", private,
                 "--trusted-proposal-sha256", proposal_hash)
            in_file = out_file
        consent_file = in_file
        call(TRANSITION, "verify", *common, "--input", consent_file)
        approval = json.loads(consent_file.read_text())
        assert set(approval["approvals"]) == {"source", "outgoing", "incoming"}

        def new_entry(receipt, number, previous):
            body = {
                "schema": v2.ACK_SCHEMA, "algorithm": "Ed25519",
                "receiver_id": "custodian-organization",
                "sequence": number, "epoch": 2,
                "source_key_id": "source-signer",
                "ack_key_id": "receiver-new",
                "source_receipt_sha256": v2.custodian.digest(receipt),
                "state_sha256": receipt["state_sha256"],
                "previous_ack_sha256": previous,
                "transition_proposal_sha256": proposal_hash,
            }
            sig = v2.trust.attestation.openssl(
                "sign", new_priv, v2.preimage(body))
            ack = {**body, "signature_base64": base64.b64encode(sig).decode("ascii")}
            return {"receipt": receipt, "ack": ack}

        call(TRUST, "enroll", "--state-dir", source,
             "--key-id", "data2", "--public-key", data2_pub)
        receipt2 = source_receipt("second")
        entry2 = new_entry(receipt2, 2, old_ack_hash)
        call(TRUST, "enroll", "--state-dir", source,
             "--key-id", "data3", "--public-key", data3_pub)
        receipt3 = source_receipt("third")
        entry3 = new_entry(receipt3, 3, v2.custodian.digest(entry2["ack"]))
        bridge = {
            "schema": v2.SCHEMA, "old_ledger_sha256": sha(old_ledger),
            "consent_sha256": sha(consent_file),
            "transition_proposal_sha256": proposal_hash,
            "entries": [entry2, entry3],
        }
        bridge_file = save(retained, "v2-bridge", bridge)
        last = save(retained, "latest-v2-package",
                    {"schema": v2.PACKAGE_SCHEMA, **entry3})

        base_args = [
            "--old-ledger", old_ledger, "--old-ledger-sha256", sha(old_ledger),
            "--trusted-old-package", old_package_file,
            "--trusted-old-package-sha256", sha(old_package_file),
            "--consent", consent_file, "--consent-sha256", sha(consent_file),
            "--bridge", bridge_file, "--bridge-sha256", sha(bridge_file),
            "--trusted-new-package", last,
            "--trusted-new-package-sha256", sha(last),
            "--receiver-id", "custodian-organization",
            "--source-key-id", "source-signer", "--source-public-key", source_pub,
            "--outgoing-ack-key-id", "receiver-old",
            "--outgoing-ack-public-key", old_pub,
            "--incoming-ack-key-id", "receiver-new",
            "--incoming-ack-public-key", new_pub,
            "--minimum-sequence", "3",
        ]
        def verify(changes=None, good=True):
            params = base_args.copy()
            for key, value in (changes or {}).items():
                marker = "--" + key.replace("_", "-")
                params[params.index(marker) + 1] = str(value)
            return call(VERIFIER, *params, good=good)

        report = json.loads(verify().stdout); checked += 1
        assert (report["old_sequence"], report["new_sequence"]) == (1, 3)
        assert report["old_last_ack_sha256"] == old_ack_hash
        assert report["historical_v1_signatures_preserved"] is True
        assert report["production_cutover_authorized"] is False
        assert report["independent_custody_proven"] is False

        # A separately signed, newer v2 continuation cannot be rolled back to
        # a previously approved v2 candidate unless the independent floor permits it.
        shorter = save(retained, "shorter", {**bridge, "entries": [entry2]})
        first_pkg = save(retained, "first-v2-pkg",
                         {"schema": v2.PACKAGE_SCHEMA, **entry2})
        verify({"bridge": shorter, "bridge_sha256": sha(shorter),
                "trusted_new_package": first_pkg,
                "trusted_new_package_sha256": sha(first_pkg)},
               good=False); checked += 1

        for changed in [
            {"old_ledger_sha256": "a" * 64},
            {"trusted_old_package_sha256": "b" * 64},
            {"consent_sha256": "c" * 64},
            {"bridge_sha256": "d" * 64},
            {"trusted_new_package_sha256": "e" * 64},
            {"incoming_ack_public_key": rogue_pub},
            {"minimum_sequence": 4},
            {"receiver_id": "another-receiver"},
        ]:
            verify(changed, good=False); checked += 1

        def changed_case(label, modify):
            value = json.loads(json.dumps(bridge))
            modify(value)
            candidate = save(retained, label, value)
            verify({"bridge": candidate, "bridge_sha256": sha(candidate)},
                   good=False)

        mutations = [
            ("wrong-epoch", lambda x: x["entries"][0]["ack"].__setitem__("epoch", 1)),
            ("wrong-sequence", lambda x: x["entries"][0]["ack"].__setitem__("sequence", 3)),
            ("legacy-schema", lambda x: x["entries"][0]["ack"].__setitem__("schema", v2.custodian.ACK_SCHEMA)),
            ("wrong-chain", lambda x: x["entries"][0]["ack"].__setitem__("previous_ack_sha256", "0" * 64)),
            ("wrong-proposal", lambda x: x["entries"][0]["ack"].__setitem__("transition_proposal_sha256", "f" * 64)),
            ("tampered-signature", lambda x: x["entries"][0]["ack"].__setitem__("signature_base64", "AAAA")),
            ("changed-source-state", lambda x: x["entries"][0]["receipt"].__setitem__("state_sha256", "a" * 64)),
            ("duplicate-ack", lambda x: x["entries"].__setitem__(1, x["entries"][0])),
            ("swapped", lambda x: x.__setitem__("entries", list(reversed(x["entries"])))),
            ("consent-identity", lambda x: x.__setitem__("consent_sha256", "a" * 64)),
            ("new-authority", lambda x: x.__setitem__("allow_runtime_import", True)),
            ("boolean-epoch", lambda x: x["entries"][0]["ack"].__setitem__("epoch", True)),
            ("empty", lambda x: x.__setitem__("entries", [])),
            ("oversize", lambda x: x.__setitem__("entries", [entry2] * 65)),
        ]
        for label, mutation in mutations:
            changed_case(label, mutation)
            checked += 1

        compromised = json.loads(consent_file.read_text())
        compromised["approvals"]["outgoing"] = compromised["approvals"]["incoming"]
        unsafe_consent = save(retained, "tampered-consent", compromised)
        verify({"consent": unsafe_consent, "consent_sha256": sha(unsafe_consent)},
               good=False); checked += 1
        # Consent tampering must be denied EVEN IF bridge document rebinds it.
        changed_case("bad-approval-in-bridge",
                     lambda x: x.__setitem__("consent_sha256", sha(unsafe_consent)))
        checked += 1

        ambiguous = retained / "duplicate-json-fields.json"
        ambiguous.write_bytes(bridge_file.read_bytes().replace(
            b'"schema":', b'"schema":"evil","schema":', 1))
        verify({"bridge": ambiguous, "bridge_sha256": sha(ambiguous)}, good=False)
        checked += 1

        symlink = retained / "linked-bridge.json"
        symlink.symlink_to(bridge_file)
        verify({"bridge": symlink}, good=False); checked += 1
        linked = retained / "hardlinked-bridge.json"
        os.link(bridge_file, linked)
        verify({"bridge": linked}, good=False); checked += 1
        linked.unlink()

        old_changed = json.loads(old_ledger.read_text())
        old_changed["entries"][0]["ack"]["signature_base64"] = "AAAA"
        altered_old = save(retained, "tampered-history", old_changed)
        verify({"old_ledger": altered_old,
                "old_ledger_sha256": sha(altered_old)}, good=False)
        checked += 1

        assert (store / "custodian.json").read_bytes() == original_store_bytes
        # The actual v1 receiver is NOT allowed to use the new key, irrespective
        # of all approvals and this separately verified proposed v2 history.
        next_receipt = save(retained, "v1-should-reject", receipt3)
        call(CUSTODIAN, "receive", "--store", store, "--receipt", next_receipt,
             "--ack-private-key", new_priv, good=False)
        checked += 1
        assert (store / "custodian.json").read_bytes() == original_store_bytes

    print(json.dumps({
        "status": "PASS", "checks": checked,
        "scope": "synthetic-three-party-consent-v1-and-domain-separated-v2-chain",
        "real_receiver_key_rotated": False,
        "live_host_tested": False,
    }))


if __name__ == "__main__":
    main()
