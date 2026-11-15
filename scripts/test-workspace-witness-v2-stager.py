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
RECOVERY = HERE / "workspace-witness-v2-recovery.py"
TWO_OBSERVERS = HERE / "workspace-witness-two-custody-evidence.py"
CHALLENGE_LEDGER = HERE / "workspace-witness-challenge-ledger.py"
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

        # Two DISTINCT fully valid Ed25519 continuations of the same prior
        # head must not both succeed. This is a real cross-process fork test.
        fork_store = root / "distinct-fork-staging"
        call(STAGER, *init_args(fork_store))
        call(STAGER, *append_args(fork_store, 1))
        _, data5_public = keypair(root, "data5")
        competing = signed_entry(data5_public, "data5", 4,
                                 v2.custodian.digest(entry2["ack"]))
        rival_bridge = save(out, "competing-bridge", {
            **root_doc, "entries": [entry1, entry2, competing]})
        rival_package = save(out, "competing-package", {
            "schema": v2.PACKAGE_SCHEMA, **competing})
        first_args = [str(x) for x in append_args(fork_store, 2)]
        second_args = first_args.copy()
        for flag, value in (
            ("--candidate", rival_bridge),
            ("--candidate-sha256", hash_file(rival_bridge)),
            ("--trusted-next-package", rival_package),
            ("--trusted-next-package-sha256", hash_file(rival_package)),
        ):
            second_args[second_args.index(flag) + 1] = str(value)

        def direct_run(argv):
            return subprocess.run(
                [sys.executable, str(STAGER), *argv],
                capture_output=True, text=True, timeout=70)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [f.result() for f in (
                executor.submit(direct_run, first_args),
                executor.submit(direct_run, second_args))]
        assert sum(result.returncode == 0 for result in results) == 1, [
            (result.returncode, result.stderr) for result in results
        ]
        assert (fork_store / "candidate.json").read_bytes() in (
            bridges[2].read_bytes(), rival_bridge.read_bytes())
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
            if case == "hardlink":
                target.unlink()  # release input inode before the next independent fixture
            checked += 1

        # Invalid operator inputs do not create a half-authoritative store.
        nonexistent = root / "should-not-exist"
        malicious = init_args(nonexistent)
        malicious[malicious.index("--candidate-sha256") + 1] = "a" * 64
        call(STAGER, *malicious, good=False)
        assert not nonexistent.exists()
        checked += 1
        # OFFLINE COLD-BACKUP / FRESH-RESTORE fixture. Independent custody
        # is simulated by separate temp paths, not claimed to be real.
        recovery_common = [
            *common,
            "--expected-bridge-sha256", hash_file(bridges[2]),
            "--trusted-latest-package", packages[2],
            "--trusted-latest-package-sha256", hash_file(packages[2]),
            "--minimum-sequence", "4",
        ]
        backup_file = out / "cold-backup.json"
        export_params = [
            "export", "--store", store,
            *recovery_common, "--backup", backup_file,
        ]
        exported = json.loads(call(RECOVERY, *export_params).stdout)
        assert exported["status"] == "exported-verifiable-cold-backup"
        assert exported["backup_sha256"] == hash_file(backup_file)
        assert exported["bridge_sha256"] == hash_file(bridges[2])
        checked += 1
        call(RECOVERY, *export_params, good=False)
        checked += 1

        verify_params = [
            "verify", *recovery_common, "--backup", backup_file,
            "--backup-sha256", hash_file(backup_file),
        ]
        checked_report = json.loads(call(RECOVERY, *verify_params).stdout)
        assert checked_report["status"] == "cold-backup-cryptographically-verified"
        checked += 1
        fresh = root / "fresh-v2-restore"
        restored = json.loads(call(
            RECOVERY, "restore", *recovery_common,
            "--backup", backup_file, "--backup-sha256", hash_file(backup_file),
            "--new-store", fresh).stdout)
        assert restored["status"] == "fresh-offline-stage-restored-and-reverified"
        assert (fresh / "candidate.json").read_bytes() == (store / "candidate.json").read_bytes()
        assert (fresh / "candidate.json").read_bytes() == bridges[2].read_bytes()
        assert fresh.stat().st_mode & 0o077 == 0
        checked += 1
        call(RECOVERY, "restore", *recovery_common,
             "--backup", backup_file, "--backup-sha256", hash_file(backup_file),
             "--new-store", fresh, good=False)
        checked += 1

        def changed_flags(items, updates):
            changed = list(items)
            for key, value in updates.items():
                flag = "--" + key.replace("_", "-")
                assert flag in changed
                changed[changed.index(flag) + 1] = str(value)
            return changed

        for case in (
            {"backup_sha256": "e" * 64},
            {"expected_bridge_sha256": "f" * 64},
            {"minimum_sequence": "5"},
            {"trusted_latest_package": packages[1],
             "trusted_latest_package_sha256": hash_file(packages[1])},
            {"incoming_ack_public_key": rogue_public},
        ):
            call(RECOVERY, *changed_flags(verify_params, case), good=False)
            checked += 1

        bad_envelope = json.loads(backup_file.read_text())
        bad_envelope["latest_ack_sha256"] = "a" * 64
        poisoned = save(out, "recovery-forged-envelope", bad_envelope)
        call(RECOVERY, *changed_flags(verify_params, {
            "backup": poisoned, "backup_sha256": hash_file(poisoned),
        }), good=False)
        checked += 1

        bad_candidate = json.loads(backup_file.read_text())
        bad_candidate["candidate"]["entries"][-1]["ack"]["signature_base64"] = "AAAA"
        tainted = save(out, "recovery-forged-signature", bad_candidate)
        call(RECOVERY, *changed_flags(verify_params, {
            "backup": tainted, "backup_sha256": hash_file(tainted),
        }), good=False)
        checked += 1

        ambiguous = out / "ambiguous-cold-backup.json"
        ambiguous.write_bytes(backup_file.read_bytes().replace(
            b'"schema":', b'"schema":"evil","schema":', 1))
        call(RECOVERY, *changed_flags(verify_params, {
            "backup": ambiguous, "backup_sha256": hash_file(ambiguous),
        }), good=False)
        checked += 1

        noncanonical = out / "noncanonical-cold-backup.json"
        noncanonical.write_bytes(backup_file.read_bytes() + b" \n")
        call(RECOVERY, *changed_flags(verify_params, {
            "backup": noncanonical, "backup_sha256": hash_file(noncanonical),
        }), good=False)
        checked += 1

        shortcut = out / "linked-cold-backup.json"
        shortcut.symlink_to(backup_file)
        call(RECOVERY, *changed_flags(verify_params, {
            "backup": shortcut, "backup_sha256": hash_file(backup_file),
        }), good=False)
        checked += 1
        shortcut.unlink()
        hardlink = out / "hardlinked-cold-backup.json"
        os.link(backup_file, hardlink)
        call(RECOVERY, *changed_flags(verify_params, {
            "backup": hardlink, "backup_sha256": hash_file(backup_file),
        }), good=False)
        checked += 1
        hardlink.unlink()

        # Genuine older signed backup is independently valid but cannot be
        # restored after a later monotonic floor is approved off-site.
        stale_stage = root / "stale-v2-stage"
        call(STAGER, *init_args(stale_stage))
        call(STAGER, *append_args(stale_stage, 1))
        stale_snapshot = out / "stale-cold-backup.json"
        old_head_flags = changed_flags(recovery_common, {
            "expected_bridge_sha256": hash_file(bridges[1]),
            "trusted_latest_package": packages[1],
            "trusted_latest_package_sha256": hash_file(packages[1]),
            "minimum_sequence": 3,
        })
        call(RECOVERY, "export", "--store", stale_stage,
             *old_head_flags, "--backup", stale_snapshot)
        call(RECOVERY, "verify", *changed_flags(old_head_flags, {
            "minimum_sequence": 4,
        }), "--backup", stale_snapshot,
             "--backup-sha256", hash_file(stale_snapshot), good=False)
        checked += 1

        # Crash during restore cannot partially overwrite a *pre-existing*
        # store; it leaves a visibly incomplete fresh destination requiring
        # explicit operator handling, not automatic privileged repair.
        crash_dir = root / "interrupted-offline-restore"
        snippet = (
            "import os,sys,importlib.util;"
            "p=sys.argv[1];"
            "s=importlib.util.spec_from_file_location('recovery_fault',p);"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "os.replace=lambda *a,**k:os._exit(75);"
            "sys.argv=[p]+sys.argv[2:];sys.exit(m.main())"
        )
        crash_flags = [
            "restore", *recovery_common,
            "--backup", backup_file, "--backup-sha256", hash_file(backup_file),
            "--new-store", crash_dir,
        ]
        abnormal = subprocess.run(
            [sys.executable, "-c", snippet, str(RECOVERY),
             *[str(s) for s in crash_flags]],
            capture_output=True, text=True, timeout=70)
        assert abnormal.returncode == 75, (abnormal.returncode, abnormal.stderr)
        assert crash_dir.exists() and not (crash_dir / "candidate.json").exists()
        call(RECOVERY, *crash_flags, good=False)
        checked += 1
        assert (store / "candidate.json").read_bytes() == bridges[2].read_bytes()
        assert (fresh / "candidate.json").read_bytes() == bridges[2].read_bytes()
        checked += 1

        # Two role-separated observers sign the exact same externally
        # approved challenge and cryptographically verified v2 head. This
        # fixture uses two local temp directories, NOT two physical hosts.
        origin_private, origin_public = keypair(root, "origin-observer")
        restore_private, restore_public = keypair(root, "restore-observer")
        outsider_private, outsider_public = keypair(root, "outsider-observer")
        # Issue a cryptographically random 32-byte challenge into a distinct
        # private append-only ledger before either observer signs it.
        registry = root / "separate-review-challenge-registry"
        initialized = json.loads(call(
            CHALLENGE_LEDGER, "init", "--registry", registry).stdout)
        assert initialized["events"] == 0
        head = initialized["registry_sha256"]
        assert head == hash_file(registry / "challenges.json")
        checked += 1
        issued = json.loads(call(
            CHALLENGE_LEDGER, "issue", "--registry", registry,
            "--expected-registry-sha256", head).stdout)
        nonce = issued["challenge_hex"]
        assert len(nonce) == 64 and nonce != "0" * 64
        assert issued["registry_sha256"] == hash_file(registry / "challenges.json")
        checked += 1
        current_registry_sha = issued["registry_sha256"]
        pending = json.loads(call(
            CHALLENGE_LEDGER, "inspect", "--registry", registry,
            "--expected-registry-sha256", current_registry_sha).stdout)
        assert pending["pending_challenges"] == [nonce]
        checked += 1
        shared_observation = [
            *common,
            "--trusted-latest-package", packages[2],
            "--trusted-latest-package-sha256", hash_file(packages[2]),
            "--expected-bridge-sha256", hash_file(bridges[2]),
            "--minimum-sequence", "4",
            "--challenge-hex", nonce,
        ]

        def observe(role, location, secret, pub, observer_id, report, good=True):
            return call(
                TWO_OBSERVERS, "observe", *shared_observation,
                "--role", role, "--store", location,
                "--observer-private-key", secret,
                "--observer-public-key", pub,
                "--observer-id", observer_id,
                "--output", report, good=good,
            )

        origin_report = out / "origin-observer-report.json"
        recovered_report = out / "restored-observer-report.json"
        origin_output = json.loads(observe(
            "origin", store, origin_private, origin_public,
            "independent-origin-observer", origin_report).stdout)
        assert origin_output["physical_host_independence_proven"] is False
        checked += 1
        recovered_output = json.loads(observe(
            "recovery", fresh, restore_private, restore_public,
            "independent-recovery-observer", recovered_report).stdout)
        assert recovered_output["production_release_authorized"] is False
        checked += 1

        pair = [
            "verify-pair", *shared_observation,
            "--approved-bridge", bridges[2],
            "--origin-report", origin_report,
            "--origin-report-sha256", hash_file(origin_report),
            "--origin-public-key", origin_public,
            "--origin-observer-id", "independent-origin-observer",
            "--recovery-report", recovered_report,
            "--recovery-report-sha256", hash_file(recovered_report),
            "--recovery-public-key", restore_public,
            "--recovery-observer-id", "independent-recovery-observer",
        ]
        paired = json.loads(call(TWO_OBSERVERS, *pair).stdout)
        assert paired["status"] == "two-distinct-signer-observations-verified"
        assert paired["distinct_signer_public_keys_verified"] is True
        assert paired["physical_host_independence_proven"] is False
        assert paired["real_offsite_restore_performed"] is False
        assert paired["production_release_authorized"] is False
        checked += 1

        # Release-facing verification must consume the independently minted
        # challenge exactly once, while holding a cross-process directory lock.
        consume_params = [
            "consume", "--registry", registry,
            "--expected-registry-sha256", current_registry_sha,
            *pair[1:],
        ]
        consumed_result = json.loads(call(
            CHALLENGE_LEDGER, *consume_params).stdout)
        assert consumed_result["status"] == "one-time-observer-evidence-consumed"
        assert consumed_result["event_count"] == 2
        assert consumed_result["latest_sequence"] == 4
        assert consumed_result["physical_host_independence_proven"] is False
        assert consumed_result["production_release_authorized"] is False
        checked += 1
        used_registry_sha = hash_file(registry / "challenges.json")
        assert used_registry_sha == consumed_result["registry_sha256"]
        # A persisted replay must fail with both the stale predecessor
        # checkpoint AND with the newest externally retained registry head.
        call(CHALLENGE_LEDGER, *consume_params, good=False)
        checked += 1
        call(CHALLENGE_LEDGER, *changed_flags(consume_params, {
            "expected_registry_sha256": used_registry_sha,
        }), good=False)
        checked += 1
        post = json.loads(call(
            CHALLENGE_LEDGER, "inspect", "--registry", registry,
            "--expected-registry-sha256", used_registry_sha).stdout)
        assert post["pending_challenges"] == []
        assert post["consumed_count"] == 1
        checked += 1

        # New challenge after consumption must be fresh and must not let
        # signatures over the previous challenge count as new evidence.
        new_issue = json.loads(call(
            CHALLENGE_LEDGER, "issue", "--registry", registry,
            "--expected-registry-sha256", used_registry_sha).stdout)
        assert new_issue["challenge_hex"] != nonce
        assert new_issue["event_count"] == 3
        checked += 1
        updated_registry_sha = new_issue["registry_sha256"]
        call(CHALLENGE_LEDGER, *changed_flags(consume_params, {
            "expected_registry_sha256": updated_registry_sha,
        }), good=False)
        checked += 1
        for changes in (
            {"expected_registry_sha256": "b" * 64},
            {"challenge_hex": "f" * 64},
            {"challenge_hex": new_issue["challenge_hex"]},
            {"origin_report_sha256": "d" * 64},
            {"recovery_public_key": origin_public},
            {"minimum_sequence": "5"},
        ):
            call(CHALLENGE_LEDGER, *changed_flags(consume_params, {
                "expected_registry_sha256": updated_registry_sha,
                **changes,
            }), good=False)
            checked += 1

        # Two concurrent consumers of exactly the same signed evidence:
        # one succeeds and one is refused, with no double consumption.
        race_registry = root / "concurrent-challenge-registry"
        race_init = json.loads(call(
            CHALLENGE_LEDGER, "init", "--registry", race_registry).stdout)
        # For the concurrency fixture, issue a *different* challenge and
        # produce genuinely signed observations over that challenge.
        issued_race = json.loads(call(
            CHALLENGE_LEDGER, "issue", "--registry", race_registry,
            "--expected-registry-sha256", race_init["registry_sha256"]).stdout)
        race_challenge = issued_race["challenge_hex"]
        race_shared = changed_flags(shared_observation, {
            "challenge_hex": race_challenge,
        })
        race_origin = out / "race-origin-observation.json"
        race_recovery = out / "race-recovery-observation.json"
        call(TWO_OBSERVERS, "observe", *race_shared,
             "--role", "origin", "--store", store,
             "--observer-private-key", origin_private,
             "--observer-public-key", origin_public,
             "--observer-id", "independent-origin-observer",
             "--output", race_origin)
        call(TWO_OBSERVERS, "observe", *race_shared,
             "--role", "recovery", "--store", fresh,
             "--observer-private-key", restore_private,
             "--observer-public-key", restore_public,
             "--observer-id", "independent-recovery-observer",
             "--output", race_recovery)
        race_pair = [
            *changed_flags(pair, {
                "challenge_hex": race_challenge,
                "origin_report": race_origin,
                "origin_report_sha256": hash_file(race_origin),
                "recovery_report": race_recovery,
                "recovery_report_sha256": hash_file(race_recovery),
            })[1:],
        ]
        concurrent_consume = [
            "consume", "--registry", race_registry,
            "--expected-registry-sha256", issued_race["registry_sha256"],
            *race_pair,
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(
                lambda: subprocess.run(
                    [sys.executable, str(CHALLENGE_LEDGER),
                     *[str(x) for x in concurrent_consume]],
                    capture_output=True, text=True, timeout=80))
                for _ in range(2)]
            results = [f.result() for f in futures]
        assert sorted(x.returncode for x in results) == [0, 1], [
            (x.returncode, x.stderr) for x in results]
        assert json.loads((race_registry / "challenges.json").read_text())["events"][-1]["kind"] == "consume"
        checked += 1

        # Missing/invalid ledger, changed previous hash, unsafe inode and
        # corruption may never be silently reset or reused for issuance.
        for case in ("wrong-head", "symlink", "hardlink", "corrupt", "permission", "missing"):
            test_registry = root / ("unsafe-challenge-" + case)
            first = json.loads(call(
                CHALLENGE_LEDGER, "init", "--registry", test_registry).stdout)
            ledger_file = test_registry / "challenges.json"
            if case == "wrong-head":
                chosen = "f" * 64
            else:
                chosen = first["registry_sha256"]
                if case == "symlink":
                    ledger_file.unlink()
                    ledger_file.symlink_to(registry / "challenges.json")
                elif case == "hardlink":
                    ledger_file.unlink()
                    os.link(registry / "challenges.json", ledger_file)
                elif case == "corrupt":
                    ledger_file.write_bytes(b"{not json")
                elif case == "permission":
                    os.chmod(ledger_file, 0o644)
                elif case == "missing":
                    ledger_file.unlink()
            call(CHALLENGE_LEDGER, "issue", "--registry", test_registry,
                 "--expected-registry-sha256", chosen, good=False)
            if case == "hardlink":
                ledger_file.unlink()
            checked += 1
        assert (registry / "challenges.json").read_bytes() == trust.encode_json(
            trust.strict_json((registry / "challenges.json").read_bytes()))
        checked += 1

        for changes in (
            {"challenge_hex": "c4" * 32},
            {"challenge_hex": "0" * 64},
            {"minimum_sequence": "5"},
            {"expected_bridge_sha256": "d" * 64},
            {"trusted_latest_package": packages[1],
             "trusted_latest_package_sha256": hash_file(packages[1])},
            {"origin_report_sha256": "f" * 64},
            {"recovery_report_sha256": "f" * 64},
            {"origin_public_key": outsider_public},
            {"recovery_public_key": origin_public},
            {"origin_observer_id": "renamed-observer"},
            {"recovery_observer_id": "independent-origin-observer"},
            {"approved_bridge": bridges[1]},
        ):
            call(TWO_OBSERVERS, *changed_flags(pair, changes), good=False)
            checked += 1

        def modified_report(title, mutate):
            obj = json.loads(origin_report.read_text())
            mutate(obj)
            altered = save(out, "forged-observer-" + title, obj)
            call(TWO_OBSERVERS, *changed_flags(pair, {
                "origin_report": altered,
                "origin_report_sha256": hash_file(altered),
            }), good=False)
        for title, mutate in (
            ("signature", lambda d: d.__setitem__("signature_base64", "AAAA")),
            ("role", lambda d: d.__setitem__("role", "recovery")),
            ("sequence", lambda d: d.__setitem__("latest_sequence", 3)),
            ("nonce", lambda d: d.__setitem__("challenge_hex", "b8" * 32)),
            ("digest", lambda d: d.__setitem__("latest_ack_sha256", "f" * 64)),
            ("scope", lambda d: d.__setitem__("production_release_authorized", True)),
            ("boolean", lambda d: d.__setitem__("latest_sequence", True)),
        ):
            modified_report(title, mutate)
            checked += 1

        # Same signing key cannot impersonate two distinct custody roles.
        same_pub = changed_flags(pair, {
            "recovery_public_key": origin_public,
            "recovery_observer_id": "another-person-same-key",
        })
        call(TWO_OBSERVERS, *same_pub, good=False)
        checked += 1
        rogue_report = out / "invalid-role-key-report.json"
        observe("recovery", fresh, origin_private, restore_public,
                "independent-recovery-observer", rogue_report, good=False)
        assert not rogue_report.exists()
        checked += 1
        stale_report = out / "stale-observation.json"
        observe("recovery", stale_stage, restore_private, restore_public,
                "independent-recovery-observer", stale_report, good=False)
        assert not stale_report.exists()
        checked += 1

        ambiguous_observer = out / "duplicate-observer-keys.json"
        ambiguous_observer.write_bytes(origin_report.read_bytes().replace(
            b'"schema":', b'"schema":"evil","schema":', 1))
        call(TWO_OBSERVERS, *changed_flags(pair, {
            "origin_report": ambiguous_observer,
            "origin_report_sha256": hash_file(ambiguous_observer),
        }), good=False)
        checked += 1
        symlink_observer = out / "symlink-observer.json"
        symlink_observer.symlink_to(origin_report)
        call(TWO_OBSERVERS, *changed_flags(pair, {
            "origin_report": symlink_observer,
            "origin_report_sha256": hash_file(origin_report),
        }), good=False)
        checked += 1
        hardlink_observer = out / "hardlink-observer.json"
        os.link(origin_report, hardlink_observer)
        call(TWO_OBSERVERS, *changed_flags(pair, {
            "origin_report": hardlink_observer,
            "origin_report_sha256": hash_file(origin_report),
        }), good=False)
        checked += 1
        hardlink_observer.unlink()
        assert (store / "candidate.json").read_bytes() == bridges[2].read_bytes()
        assert (fresh / "candidate.json").read_bytes() == bridges[2].read_bytes()
        checked += 1

        assert old_ledger.read_bytes() == old_ledger_initial
        assert (receiver / "custodian.json").read_bytes() == old_ledger_initial
        assert all(bridge.read_bytes() == trust.encode_json(
            trust.strict_json(bridge.read_bytes())) for bridge in bridges)

    print(json.dumps({
        "status": "PASS", "checks": checked,
        "scope": "synthetic-v2-recovery-two-observers-and-one-time-durable-challenges",
        "live_receiver_modified": False,
        "production_key_rotation_activated": False,
    }))


if __name__ == "__main__":
    main()
