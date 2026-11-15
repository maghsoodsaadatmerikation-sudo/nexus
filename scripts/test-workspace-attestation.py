#!/usr/bin/env python3
"""Real disposable Ed25519 signing and verification; no imported trust or keys."""

import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).resolve().with_name("workspace-attestation.py")


def invoke(*args, success):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert (result.returncode == 0) is success, (
        f"result={result.returncode} out={result.stdout!r} err={result.stderr!r}"
    )
    return result


def json_bytes(snapshot_id="machine-history"):
    doc = {
        "schema_version": 1,
        "workspace": {
            "id": snapshot_id, "question": "کدام مدرک می‌تواند این فرضیه را رد کند؟",
            "goal": None, "constraints": [], "values": [],
            "claims": [{
                "id": "machine-observation", "text": "Local question — not verified evidence",
                "origin": "MachineAnalysis", "uncertainty": "High",
            }],
            "alternatives": [], "judgment": None,
        },
        "events": [
            {"sequence": 0, "provenance_id": "human:owner", "kind": "WorkspaceCreated"},
            {"sequence": 1, "provenance_id": "machine:nexus-local-question-probe-v1:run-a",
             "kind": {"MachineAnalysisRecorded": {
                 "claim_id": "machine-observation", "adapter_id": "nexus-local-question-probe-v1",
                 "run_id": "run-a", "observation_kind": "UncertaintyNote", "source_ids": [],
             }}},
        ],
    }
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def change_json(path, edit):
    contents = json.loads(path.read_text())
    edit(contents)
    path.write_text(json.dumps(contents, indent=2) + "\n")


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-ed25519-witness-") as td:
        root = Path(td)
        snapshot = root / "snapshot.json"
        sidecar = root / "attestation.json"
        sk = root / "operator-secret.pem"
        pk = root / "operator-public.pem"
        sk_other = root / "wrong-private.pem"
        pk_other = root / "wrong-public.pem"
        for private, public in [(sk, pk), (sk_other, pk_other)]:
            subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(private)],
                           check=True, capture_output=True)
            subprocess.run(["openssl", "pkey", "-in", str(private),
                            "-pubout", "-out", str(public)], check=True, capture_output=True)

        snapshot.write_bytes(json_bytes())
        sign = ["sign", "--snapshot", snapshot, "--workspace-id", "machine-history",
                "--key-id", "operator-r1", "--private-key", sk, "--output", sidecar]
        verify = ["verify", "--snapshot", snapshot, "--attestation", sidecar,
                  "--expected-workspace-id", "machine-history",
                  "--trusted-key-id", "operator-r1", "--trusted-public-key", pk]
        invoke(*sign, success=True)
        invoke(*verify, success=True)
        assert sidecar.is_file()
        assert sidecar.stat().st_mode & 0o077 == 0, "attestation created world-readable"
        invoke(*sign, success=False)  # Must not overwrite a prior witness.

        # Independent caller trust and identity: no key is accepted from an
        # untrusted sidecar, and a swapped public key is not a valid signer.
        wrong_key = verify.copy()
        wrong_key[-1] = pk_other
        invoke(*wrong_key, success=False)
        wrong_kid = verify.copy()
        wrong_kid[-3] = "operator-r2"
        invoke(*wrong_kid, success=False)
        different_workspace = verify.copy()
        different_workspace[-5] = "other-workspace"
        invoke(*different_workspace, success=False)
        wrong_sign_dest = sign.copy()
        wrong_sign_dest[4] = "other-workspace"
        wrong_sign_dest[-1] = root / "bad-identity.json"
        invoke(*wrong_sign_dest, success=False)

        original_bytes = snapshot.read_bytes()
        for tampered in [
            original_bytes + b" ",  # Exact-byte binding, even same parsed JSON.
            original_bytes.replace(b"not verified evidence", b"trusted evidence"),
            json_bytes("different-workspace"),
            original_bytes.replace(b'"schema_version": 1', b'"schema_version": 2'),
            original_bytes.replace(b'"id": "machine-history"',
                                   b'"id": "machine-history", "id": "machine-history"'),
        ]:
            snapshot.write_bytes(tampered)
            invoke(*verify, success=False)
        snapshot.write_bytes(original_bytes)
        invoke(*verify, success=True)

        original_att = sidecar.read_bytes()
        def invalid_sidecar(changer):
            sidecar.write_bytes(original_att)
            change_json(sidecar, changer)
            invoke(*verify, success=False)
        invalid_sidecar(lambda d: d.__setitem__("key_id", "operator-r2"))
        invalid_sidecar(lambda d: d.__setitem__("algorithm", "RSA"))
        invalid_sidecar(lambda d: d.__setitem__("schema", "nexus.workspace.detached-attestation.v2"))
        invalid_sidecar(lambda d: d.__setitem__("destination_workspace_id", "wrong"))
        invalid_sidecar(lambda d: d.__setitem__("snapshot_size_bytes", True))
        invalid_sidecar(lambda d: d.__setitem__("snapshot_sha256", "f" * 64))
        invalid_sidecar(lambda d: d.__setitem__("snapshot_sha256", "not-a-hash"))
        invalid_sidecar(lambda d: d.__setitem__("signature_base64", "%%%"))
        invalid_sidecar(lambda d: d.__setitem__("signature_base64", base64.b64encode(b"x" * 64).decode()))
        invalid_sidecar(lambda d: d.__setitem__("operator_public_key", "attacker.pem"))
        sidecar.write_bytes(original_att.replace(b'"schema":', b'"schema":"injected", "schema":'))
        invoke(*verify, success=False)
        sidecar.write_bytes(original_att)
        invoke(*verify, success=True)

        # A signature is useless if there is no machine-provenance claim. No
        # default conversion from a human report into claimed machine history.
        human = json.loads(original_bytes)
        human["workspace"]["claims"][0]["origin"] = "Human"
        human["events"][1]["kind"] = {"ClaimAdded": {"claim_id": "machine-observation"}}
        human["events"][1]["provenance_id"] = "human:user"
        human_path = root / "human.json"
        human_path.write_text(json.dumps(human))
        empty_sign = sign.copy()
        empty_sign[2] = human_path
        empty_sign[-1] = root / "human-sidecar.json"
        invoke(*empty_sign, success=False)

        # Old runtime import remains unmodified: detached verification is NOT
        # authority to import machine history or bypass the HTTP denial.
        print("DETACHED ED25519 REAL SIGN/VERIFY REGRESSION: PASS (operator-side only; no import)")


if __name__ == "__main__":
    main()
