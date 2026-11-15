#!/usr/bin/env python3
"""Disposable real-key offline trust registry and replay-ledger regressions."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
TRUST = ROOT / "workspace-trust.py"
ATTEST = ROOT / "workspace-attestation.py"
FIXTURE = ROOT / "test-workspace-attestation.py"
spec = importlib.util.spec_from_file_location("nexus_test_fixture", FIXTURE)
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def call(script, *args, success=True):
    r = subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    if (r.returncode == 0) != success:
        raise AssertionError(
            f"unexpected exit {r.returncode}: {script.name} {args!r}\n"
            f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
        )
    return r


def generate_key(root, name):
    private, public = root / (name + ".pem"), root / (name + ".pub.pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519",
                    "-out", str(private)], capture_output=True, check=True)
    subprocess.run(["openssl", "pkey", "-in", str(private),
                    "-pubout", "-out", str(public)], capture_output=True, check=True)
    return private, public


def sign(root, snapshot, key_id, private, suffix):
    sidecar = root / (suffix + ".attestation.json")
    call(ATTEST, "sign", "--snapshot", snapshot, "--workspace-id", "machine-history",
         "--key-id", key_id, "--private-key", private, "--output", sidecar)
    return sidecar


def mutate_snapshot(root, parent, suffix, update):
    doc = json.loads(parent.read_text())
    update(doc)
    new = root / (suffix + ".json")
    new.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True))
    return new


def add_claim_and_event(doc, suffix):
    sequence = len(doc["events"])
    doc["workspace"]["claims"].append({
        "id": "human-" + suffix, "text": "Human report " + suffix,
        "origin": "Human", "uncertainty": "Unknown",
    })
    doc["events"].append({
        "sequence": sequence, "provenance_id": "human:owner",
        "kind": {"ClaimAdded": {"claim_id": "human-" + suffix}},
    })


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-trust-regression-") as td:
        root = Path(td)
        state = root / "private-registry"
        one_private, one_public = generate_key(root, "operator-one")
        two_private, two_public = generate_key(root, "operator-two")
        rogue_private, rogue_public = generate_key(root, "rogue")
        snapshot = root / "first.json"
        snapshot.write_bytes(fixtures.json_bytes())
        first_attestation = sign(root, snapshot, "issuer-1", one_private, "first")
        base = ["--state-dir", state]
        verify = ["--snapshot", snapshot, "--attestation", first_attestation,
                  "--workspace-id", "machine-history"]

        # Trust never bootstraps implicitly from a user-supplied signature.
        call(TRUST, "inspect", *base, *verify, success=False)
        call(TRUST, "record", *base, *verify, success=False)
        assert not state.exists()
        call(TRUST, "init", *base)
        assert state.stat().st_mode & 0o077 == 0
        call(TRUST, "init", *base, success=False)

        call(TRUST, "record", *base, *verify, success=False)
        call(TRUST, "enroll", *base, "--key-id", "issuer-1", "--public-key", one_public)
        call(TRUST, "enroll", *base, "--key-id", "issuer-1", "--public-key", two_public,
             success=False)
        call(TRUST, "enroll", *base, "--key-id", "duplicate-fingerprint",
             "--public-key", one_public, success=False)
        report = json.loads(call(TRUST, "status", *base).stdout)
        assert report["keys"]["issuer-1"]["status"] == "active"
        assert report["keys"]["issuer-1"]["role"] == "offline_witness"
        assert "public_key_der_base64" not in report["keys"]["issuer-1"]

        before = (state / "trust-state.json").read_bytes()
        call(TRUST, "inspect", *base, *verify)
        assert (state / "trust-state.json").read_bytes() == before, "inspect must be read-only"
        call(TRUST, "record", *base, *verify)
        sealed = (state / "trust-state.json").read_bytes()
        call(TRUST, "record", *base, *verify, success=False)
        assert (state / "trust-state.json").read_bytes() == sealed
        assert json.loads(sealed)["workspaces"]["machine-history"]["event_count"] == 2

        # No trust of a different key merely because it signs correctly.
        rogue_att = sign(root, snapshot, "rogue-issuer", rogue_private, "rogue")
        call(TRUST, "record", *base, "--snapshot", snapshot,
             "--attestation", rogue_att, "--workspace-id", "machine-history",
             success=False)
        # Caller cannot swap the key material for an existing trusted key ID.
        fake_att = sign(root, snapshot, "issuer-1", rogue_private, "fake-issuer")
        call(TRUST, "record", *base, "--snapshot", snapshot,
             "--attestation", fake_att, "--workspace-id", "machine-history",
             success=False)

        second = mutate_snapshot(root, snapshot, "second", lambda doc:
                                 add_claim_and_event(doc, "second"))
        second_att = sign(root, second, "issuer-1", one_private, "second")
        # Revision increase alone is insufficient: the old event prefix must
        # match the one recorded under the previous signing key.
        fork = mutate_snapshot(root, second, "fork",
                               lambda d: d["events"][1].__setitem__(
                                   "provenance_id", "machine:alternate:fork"))
        fork_att = sign(root, fork, "issuer-1", one_private, "fork")
        call(TRUST, "record", *base, "--snapshot", fork, "--attestation", fork_att,
             "--workspace-id", "machine-history", success=False)
        call(TRUST, "record", *base, "--snapshot", second, "--attestation", second_att,
             "--workspace-id", "machine-history")
        call(TRUST, "record", *base, *verify, success=False)

        # Atomic revocation and rotation: an old signature must no longer
        # satisfy the *current* trust state, even when cryptographically valid.
        call(TRUST, "rotate", *base, "--old-key-id", "issuer-1",
             "--new-key-id", "issuer-2", "--new-public-key", two_public)
        report = json.loads(call(TRUST, "status", *base).stdout)
        assert report["keys"]["issuer-1"]["status"] == "revoked"
        assert report["keys"]["issuer-2"]["status"] == "active"
        call(TRUST, "inspect", *base, *verify, success=False)
        call(TRUST, "record", *base, "--snapshot", second, "--attestation", second_att,
             "--workspace-id", "machine-history", success=False)
        call(TRUST, "rotate", *base, "--old-key-id", "issuer-1",
             "--new-key-id", "issuer-3", "--new-public-key", rogue_public,
             success=False)
        call(TRUST, "enroll", *base, "--key-id", "issuer-3", "--public-key", two_public,
             success=False)

        third = mutate_snapshot(root, second, "third", lambda doc:
                                add_claim_and_event(doc, "third"))
        third_att = sign(root, third, "issuer-2", two_private, "third")
        # Two independent processes competing on the same revision may not
        # both commit: the directory descriptor is exclusively flock-locked.
        tasks = [["record", *base, "--snapshot", third, "--attestation", third_att,
                  "--workspace-id", "machine-history"] for _ in range(2)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda params: subprocess.run([sys.executable, str(TRUST), *map(str, params)],
                                              capture_output=True, text=True, timeout=45),
                tasks,
            ))
        assert sorted(x.returncode for x in results) == [0, 1], results
        assert json.loads((state / "trust-state.json").read_text())["workspaces"][
            "machine-history"]["event_count"] == 4
        call(TRUST, "record", *base, "--snapshot", second, "--attestation", second_att,
             "--workspace-id", "machine-history", success=False)

        # A fork with more events cannot reset past history; a properly
        # advancing revision with the same prefix can be recorded.
        branch_doc = json.loads(third.read_text())
        branch_doc["events"][1]["provenance_id"] = "machine:tampered:old-run"
        add_claim_and_event(branch_doc, "fourth")
        branch = root / "fourth-fork.json"
        branch.write_text(json.dumps(branch_doc))
        branch_att = sign(root, branch, "issuer-2", two_private, "fourth-fork")
        call(TRUST, "record", *base, "--snapshot", branch, "--attestation", branch_att,
             "--workspace-id", "machine-history", success=False)

        fourth = mutate_snapshot(root, third, "fourth", lambda doc:
                                 add_claim_and_event(doc, "fourth"))
        fourth_att = sign(root, fourth, "issuer-2", two_private, "fourth")
        call(TRUST, "record", *base, "--snapshot", fourth, "--attestation", fourth_att,
             "--workspace-id", "machine-history")
        call(TRUST, "revoke", *base, "--key-id", "issuer-2")
        call(TRUST, "revoke", *base, "--key-id", "issuer-2", success=False)
        call(TRUST, "inspect", *base, "--snapshot", fourth, "--attestation", fourth_att,
             "--workspace-id", "machine-history", success=False)

        # Store corruption and weak filesystem trust must fail closed; never
        # recreate missing state, accept unknown roles, or follow state links.
        saved = (state / "trust-state.json").read_bytes()
        store = state / "trust-state.json"
        store.write_bytes(b"{invalid}")
        call(TRUST, "status", *base, success=False)
        store.write_bytes(saved)
        corrupted = json.loads(saved)
        corrupted["keys"]["issuer-1"]["role"] = "runtime_import"
        store.write_text(json.dumps(corrupted))
        call(TRUST, "status", *base, success=False)
        store.write_bytes(saved)

        store.unlink()
        external = root / "external-ledger.json"
        external.write_bytes(saved)
        store.symlink_to(external)
        call(TRUST, "status", *base, success=False)
        store.unlink()
        os.link(external, store)
        call(TRUST, "status", *base, success=False)
        store.unlink()
        store.write_bytes(saved)
        os.chmod(store, 0o600)

        os.chmod(state, 0o755)
        call(TRUST, "status", *base, success=False)
        os.chmod(state, 0o700)
        linked_root = root / "alias"
        linked_root.symlink_to(state)
        call(TRUST, "status", "--state-dir", linked_root, success=False)
        store.unlink()
        call(TRUST, "status", *base, success=False)
        assert not store.exists(), "missing state must never be bootstrapped"
        print("OPERATOR TRUST REGISTRY AND MONOTONIC WITNESS LEDGER: PASS (offline only)")


if __name__ == "__main__":
    main()
