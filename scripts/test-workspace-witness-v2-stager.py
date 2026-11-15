#!/usr/bin/env python3
"""Synthetic durable v2 candidate storage: true Ed25519, crash, concurrency."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
STAGER = HERE / "workspace-witness-v2-stager.py"
TRUST = HERE / "workspace-trust.py"
WITNESS = HERE / "workspace-offsite-witness.py"
CUSTODIAN = HERE / "workspace-witness-custodian.py"
TRANSITION = HERE / "workspace-witness-key-transition.py"
spec = importlib.util.spec_from_file_location("nexus_stager_test", STAGER)
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)
trust = stage.trust
v2 = stage.v2


def call(tool, *args, good=True):
    command = [sys.executable, str(tool), *map(str, args)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=70)
    assert (result.returncode == 0) is good, (
        f"expected={good}; rc={result.returncode}; {command}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    return result


def keypair(root, label):
    private, public = root / (label + ".private.pem"), root / (label + ".public.pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519",
                    "-out", str(private)], capture_output=True, check=True, timeout=20)
    os.chmod(private, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout",
                    "-out", str(public)], capture_output=True, check=True, timeout=20)
    return private, public


def save(root, name, data):
    path = root / (name + ".json")
    path.write_bytes(trust.encode_json(data))
    os.chmod(path, 0o600)
    return path


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checked = 0
    with tempfile.TemporaryDirectory(prefix="nexus-v2-durable-stage-test-") as td:
        root = Path(td)
        out = root / "independent-inputs"
        out.mkdir(mode=0o700)
        source_dir, receiver = root / "source-state", root / "old-receiver"
        source_private, source_public = keypair(root, "source")
        old_private, old_public = keypair(root, "receiver-old")
        new_private, new_public = keypair(root, "receiver-new")
        rogue_private, rogue_public = keypair(root, "rogue")
        data1_private, data1_public = keypair(root, "data1")
        data2_private, data2_public = keypair(root, "data2")
        data3_private, data3_public = keypair(root, "data3")
        data4_private, data4_public = keypair(root, "data4")
        call(TRUST, "init", "--state-dir", source_dir)
        call(TRUST, "enroll", "--state-dir", source_dir,
             "--key-id", "data1", "--public-key", data1_public)

        def make_receipt(name):
            path = out / (name + ".receipt.json")
            call(WITNESS, "seal", "--state-dir", source_dir,
                 "--witness-key-id", "source-key",
                 "--witness-private-key", source_private, "--output", path)
            return json.loads(path.read_text())

        call(CUSTODIAN, "init", "--store", receiver,
             "--receiver-id", "separate-recipient",
             "--source-key-id", "source-key", "--source-public-key", source_public,
             "--ack-key-id", "old-recipient", "--ack-public-key", old_public)
        old_receipt = save(out, "receipt0", make_receipt("receipt0"))
        old_latest_obj = json.loads(call(
            CUSTODIAN, "receive", "--store", receiver,
            "--receipt", old_receipt, "--ack-private-key", old_private).stdout)
        old_latest = save(out, "old-latest", old_latest_obj)
        old_ledger = out / "old-ledger.json"
        old_ledger.write_bytes((receiver / "custodian.json").read_bytes())
        old_ledger_initial = old_ledger.read_bytes()

        consent_args = [
            "--receiver-id", "separate-recipient",
            "--source-key-id", "source-key", "--source-public-key", source_public,
            "--outgoing-ack-key-id", "old-recipient",
            "--outgoing-ack-public-key", old_public,
            "--incoming-ack-key-id", "new-recipient",
            "--incoming-ack-public-key", new_public,
            "--trusted-latest-package", old_latest,
            "--trusted-package-sha256", hash_file(old_latest),
            "--minimum-sequence", "1",
        ]
        proposed = out / "proposal.json"
        call(TRANSITION, "prepare", *consent_args, "--output", proposed)
        proposal = json.loads(proposed.read_text())["proposal"]
        proposal_hash = hashlib.sha256(trust.encode_json(proposal)).hexdigest()
        last_file = proposed
        for role, key in (("source", source_private),
                          ("outgoing", old_private), ("incoming", new_private)):
            approved = out / (role + "-approved.json")
            call(TRANSITION, "sign", "--input", last_file, "--output", approved,
                 "--role", role, "--private-key", key,
                 "--trusted-proposal-sha256", proposal_hash)
            last_file = approved
        consent = last_file

        def signed_entry(data_public, key_name, number, previous):
            call(TRUST, "enroll", "--state-dir", source_dir,
                 "--key-id", key_name, "--public-key", data_public)
            receipt = make_receipt(key_name)
            body = {
                "schema": v2.ACK_SCHEMA, "algorithm": "Ed25519",
                "receiver_id": "separate-recipient",
                "sequence": number, "epoch": 2,
                "source_key_id": "source-key",
                "ack_key_id": "new-recipient",
                "source_receipt_sha256": v2.custodian.digest(receipt),
                "state_sha256": receipt["state_sha256"],
                "previous_ack_sha256": previous,
                "transition_proposal_sha256": proposal_hash,
            }
            sig = trust.attestation.openssl("sign", new_private, v2.preimage(body))
            return {"receipt": receipt,
                    "ack": {**body, "signature_base64": base64.b64encode(sig).decode()}}

        previous = v2.custodian.digest(old_latest_obj["ack"])
        entry1 = signed_entry(data2_public, "data2", 2, previous)
        entry2 = signed_entry(data3_public, "data3", 3,
                              v2.custodian.digest(entry1["ack"]))
        entry3 = signed_entry(data4_public, "data4", 4,
                              v2.custodian.digest(entry2["ack"]))
        root_doc = {
            "schema": v2.SCHEMA,
            "old_ledger_sha256": hash_file(old_ledger),
            "consent_sha256": hash_file(consent),
            "transition_proposal_sha256": proposal_hash,
        }
        bridges = [
            save(out, "bridge-1", {**root_doc, "entries": [entry1]}),
            save(out, "bridge-2", {**root_doc, "entries": [entry1, entry2]}),
            save(out, "bridge-3", {**root_doc, "entries": [entry1, entry2, entry3]}),
        ]
        packages = [
            save(out, "signed-checkpoint-1",
                 {"schema": v2.PACKAGE_SCHEMA, **entry1}),
            save(out, "signed-checkpoint-2",
                 {"schema": v2.PACKAGE_SCHEMA, **entry2}),
            save(out, "signed-checkpoint-3",
                 {"schema": v2.PACKAGE_SCHEMA, **entry3}),
        ]
        common = [
            "--old-ledger", old_ledger, "--old-ledger-sha256", hash_file(old_ledger),
            "--trusted-old-package", old_latest,
            "--trusted-old-package-sha256", hash_file(old_latest),
            "--consent", consent, "--consent-sha256", hash_file(consent),
            "--receiver-id", "separate-recipient",
            "--source-key-id", "source-key", "--source-public-key", source_public,
            "--outgoing-ack-key-id", "old-recipient",
            "--outgoing-ack-public-key", old_public,
            "--incoming-ack-key-id", "new-recipient",
            "--incoming-ack-public-key", new_public,
        ]

        def init_args(store):
            return ["init", "--store", store, *common,
                    "--candidate", bridges[0],
                    "--candidate-sha256", hash_file(bridges[0]),
                    "--trusted-next-package", packages[0],
                    "--trusted-next-package-sha256", hash_file(packages[0]),
                    "--next-minimum-sequence", "2"]

        def append_args(store, index):
            assert index in (1, 2)
            previous_index = index - 1
            return [
                "append", "--store", store, *common,
                "--candidate", bridges[index],
                "--candidate-sha256", hash_file(bridges[index]),
                "--trusted-current-package", packages[previous_index],
                "--trusted-current-package-sha256", hash_file(packages[previous_index]),
                "--trusted-next-package", packages[index],
                "--trusted-next-package-sha256", hash_file(packages[index]),
                "--expected-current-sha256", hash_file(bridges[previous_index]),
                "--current-minimum-sequence", str(previous_index + 2),
                "--next-minimum-sequence", str(index + 2),
            ]

        store = root / "staging"
        report = json.loads(call(STAGER, *init_args(store)).stdout)
        assert report["status"] == "initialized-verified-v2-candidate"
        assert (store / "candidate.json").read_bytes() == bridges[0].read_bytes()
        checked += 1
        call(STAGER, *init_args(store), good=False); checked += 1
        report = json.loads(call(STAGER, *append_args(store, 1)).stdout)
        assert report["status"] == "appended-one-verified-v2-record"
        assert (store / "candidate.json").read_bytes() == bridges[1].read_bytes()
        checked += 1
        report = json.loads(call(STAGER, *append_args(store, 1)).stdout)
        assert report["status"] == "already-committed-exact-retry"
        assert (store / "candidate.json").read_bytes() == bridges[1].read_bytes()
        checked += 1

        # Two processes commit the same externally signed new candidate:
        # both may acknowledge, but only one durable entry is written.
        args = append_args(store, 2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(call, STAGER, *args) for _ in range(2)]
            concurrent = [json.loads(f.result().stdout)["status"] for f in futures]
        assert sorted(concurrent) == [
            "already-committed-exact-retry", "appended-one-verified-v2-record"
        ]
        assert (store / "candidate.json").read_bytes() == bridges[2].read_bytes()
        checked += 1

        # A historical rollback or divergent candidate cannot be quietly
        # accepted as a new history, even if it is internally well signed.
        stale_args = append_args(store, 1)
        call(STAGER, *stale_args, good=False); checked += 1
        good_head = (store / "candidate.json").read_bytes()
        bad_pins = append_args(store, 2)
        bad_pins[bad_pins.index("--expected-current-sha256") + 1] = "f" * 64
        call(STAGER, *bad_pins, good=False); checked += 1
        assert (store / "candidate.json").read_bytes() == good_head

        # Do not overwrite a verified candidate with a signature-invalid,
        # even externally SHA-pinned, proposed continuation.
        forged = json.loads(bridges[2].read_text())
        forged["entries"][-1]["ack"]["signature_base64"] = "AAAA"
        fake = save(out, "forged-bridge", forged)
        args_bad = append_args(store, 2)
        args_bad[args_bad.index("--candidate") + 1] = fake
        args_bad[args_bad.index("--candidate-sha256") + 1] = hash_file(fake)
        call(STAGER, *args_bad, good=False); checked += 1
        assert (store / "candidate.json").read_bytes() == good_head

        for case in ("before", "after"):
            crash_store = root / ("crash-" + case)
            call(STAGER, *init_args(crash_store))
            crash_args = [str(s) for s in append_args(crash_store, 1)]
            # Force an actual separate Python process to exit abnormally on
            # the staging atomic rename boundary; no live state involved.
            snippet = (
                "import os,sys,importlib.util;"
                "p=sys.argv[1];"
                "s=importlib.util.spec_from_file_location('fault_stage',p);"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                "real=os.replace;"
                "defective=lambda *a,**k: "
                + ("os._exit(73)" if case == "before"
                   else "(real(*a,**k),os._exit(74))")
                + ";os.replace=defective;"
                "sys.argv=[p]+sys.argv[2:];sys.exit(m.main())"
            )
            crashed = subprocess.run(
                [sys.executable, "-c", snippet, str(STAGER), *crash_args],
                capture_output=True, text=True, timeout=70)
            assert crashed.returncode == (73 if case == "before" else 74), (
                crashed.returncode, crashed.stderr)
            current = (crash_store / "candidate.json").read_bytes()
            assert current == (bridges[0] if case == "before"
                               else bridges[1]).read_bytes()
            result = json.loads(call(STAGER, *append_args(crash_store, 1)).stdout)
            assert result["status"] == (
                "appended-one-verified-v2-record" if case == "before"
                else "already-committed-exact-retry")
            assert (crash_store / "candidate.json").read_bytes() == bridges[1].read_bytes()
            checked += 1

        # Corrupt, missing, linked and permission-unsafe persistent candidates
        # fail closed; they cannot be automatically re-created in-place.
        for case in ("corrupt", "missing", "symlink", "hardlink", "world-readable"):
            broken = root / ("unsafe-" + case)
            call(STAGER, *init_args(broken))
            target = broken / "candidate.json"
            if case == "corrupt":
                target.write_bytes(b"{corrupted")
            elif case == "missing":
                target.unlink()
            elif case == "symlink":
                target.unlink()
                target.symlink_to(bridges[0])
            elif case == "hardlink":
                target.unlink()
                os.link(bridges[0], target)
            else:
                os.chmod(target, 0o644)
            call(STAGER, *append_args(broken, 1), good=False)
            checked += 1

        # Invalid operator inputs do not create a half-authoritative store.
        nonexistent = root / "should-not-exist"
        malicious = init_args(nonexistent)
        malicious[malicious.index("--candidate-sha256") + 1] = "a" * 64
        call(STAGER, *malicious, good=False)
        assert not nonexistent.exists()
        checked += 1
        assert old_ledger.read_bytes() == old_ledger_initial
        assert (receiver / "custodian.json").read_bytes() == old_ledger_initial
        assert all(bridge.read_bytes() == trust.encode_json(
            trust.strict_json(bridge.read_bytes())) for bridge in bridges)

    print(json.dumps({
        "status": "PASS", "checks": checked,
        "scope": "synthetic-atomic-v2-staging-concurrency-and-process-crashes",
        "live_receiver_modified": False,
        "production_key_rotation_activated": False,
    }))


if __name__ == "__main__":
    main()
