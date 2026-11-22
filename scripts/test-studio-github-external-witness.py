#!/usr/bin/env python3
"""Offline adversarial tests for a separately operated Studio GitHub witness."""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


w = load(HERE / "studio-github-external-witness.py", "studio_external_witness")
source = load(ROOT / "nexus-cloud" / "studio_audit_request.py", "studio_source_audit")


def expect_error(action, message):
    try:
        action()
    except w.WitnessError:
        return
    raise AssertionError(message)


def fixture(operation="github.file_commit"):
    repo, branch, sha = "example/nexus", "nexus/studio-revised", "a" * 40
    reviewed = b"After\n"
    receipt = {
        "schema_version": 1, "kind": "github_followup_read",
        "operation": operation,
        "outcome": "committed" if operation == "github.file_commit" else "created",
        "revision": sha, "followup_read_verified": True,
        "reviewed_request_matched": True, "file_bytes_verified": operation == "github.file_commit",
        "independent_attestation": False, "deployment_verified": False,
    }
    return source.make_request(operation, repo, branch, sha, "c" * 64, receipt,
                               **({"file_path": "docs/intro.md", "file_bytes": reviewed}
                                  if operation == "github.file_commit" else {}))


def fake_fetch(request, changed=False, symlink=False, truncated=False, wrong_commit=False):
    records = []
    branch = request["branch"]
    revision = request["revision"]
    sha = "b" * 40
    content = b"Tampered\n" if changed else b"After\n"
    blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\x00" + content).hexdigest()

    def fetch(path):
        records.append(path)
        assert path.startswith("/repos/example/nexus/"), "witness escaped pinned repository"
        if "/branches/" in path:
            return {"name": branch, "commit": {"sha": ("f" * 40 if wrong_commit else revision)}}
        if "/git/commits/" in path:
            return {"sha": revision, "tree": {"sha": sha}}
        if "/git/trees/" in path:
            return {"truncated": truncated, "tree": [
                {"path": "docs/intro.md", "mode": "120000" if symlink else "100644",
                 "type": "blob", "sha": blob},
            ]}
        assert path.endswith("/contents/docs/intro.md?ref=" + revision), path
        return {"type": "file", "path": "docs/intro.md", "encoding": "base64",
                "sha": blob, "content": base64.b64encode(content).decode()}

    return fetch, records


def keypair(root):
    private = root / "external-private.pem"
    public = root / "external-public.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(private)],
                   capture_output=True, check=True, timeout=15)
    subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                   capture_output=True, check=True, timeout=15)
    return private, public


def run():
    branch = fixture("github.branch")
    file = fixture()
    assert w.valid_request(branch, "example/nexus") == branch
    assert w.valid_request(file, "example/nexus") == file
    assert "After\n" not in json.dumps(file) and "c" * 64 not in json.dumps(file)
    assert file["file_sha256"] == hashlib.sha256(b"After\n").hexdigest()
    assert branch["file_sha256"] is None and branch["file_path"] is None
    expect_error(lambda: w.valid_request(file, "another/repo"), "witness accepted a swapped repository")
    for key, value in [
        ("repository", "attacker/repo"), ("branch", "main"),
        ("operation", "github.pull"), ("authority", "verified"),
        ("external_witness_completed", True),
    ]:
        changed = copy.deepcopy(file)
        changed[key] = value
        expect_error(lambda changed=changed: w.valid_request(changed, "example/nexus"),
                     "forged request metadata accepted: " + key)
    for key in ("independent_attestation", "deployment_verified"):
        changed = copy.deepcopy(file)
        changed["source_receipt"][key] = True
        expect_error(lambda changed=changed: w.valid_request(changed, "example/nexus"),
                     "fabricated source provider authority accepted")
    changed = copy.deepcopy(file)
    changed["source_receipt"]["file_bytes_verified"] = False
    expect_error(lambda: w.valid_request(changed, "example/nexus"), "fabricated file receipt accepted")
    changed = copy.deepcopy(file)
    changed["extra_secret"] = "malicious"
    expect_error(lambda: w.valid_request(changed, "example/nexus"), "extra fields accepted")
    expect_error(lambda: w.strict_json(b'{"schema":"a","schema":"b"}'),
                 "ambiguous JSON key accepted")
    expect_error(lambda: w.strict_json(b'{"value":NaN}'), "nonfinite JSON accepted")

    branch_fetch, branch_records = fake_fetch(branch)
    assert w.observed_state(branch, branch_fetch) is None
    assert len(branch_records) == 1 and "/branches/" in branch_records[0]
    for opts in ({"wrong_commit": True},):
        bad, _ = fake_fetch(branch, **opts)
        expect_error(lambda: w.observed_state(branch, bad), "mismatched branch accepted")
    valid_fetch, records = fake_fetch(file)
    assert w.observed_state(file, valid_fetch) == file["file_sha256"]
    assert len(records) == 4
    for opts in (
        {"changed": True}, {"symlink": True}, {"truncated": True},
        {"wrong_commit": True},
    ):
        bad, _ = fake_fetch(file, **opts)
        expect_error(lambda bad=bad: w.observed_state(file, bad),
                     "invalid external file readback accepted: " + str(opts))

    with tempfile.TemporaryDirectory(prefix="nexus-external-witness-test-") as temp:
        root = Path(temp)
        private, public = keypair(root)
        report = w.checked_report(file, "independent-org-1", "witness-key-1", valid_fetch, private)
        assert report["request_sha256"] == w.digest(file)
        assert report["observed_file_sha256"] == file["file_sha256"]
        assert report["independence_of_custody_not_self_proven"] is True
        assert report["provider_is_not_independent_of_its_own_data"] is True
        assert w.verify_report(file, report, "independent-org-1", "witness-key-1", public)
        w.write_new(root / "report.json", report)
        assert w.read_json(root / "report.json") == report
        try:
            w.write_new(root / "report.json", report)
        except FileExistsError:
            pass
        else:
            raise AssertionError("witness report overwritten without explicit new path")
        altered = copy.deepcopy(report)
        altered["revision"] = "b" * 40
        expect_error(lambda: w.verify_report(file, altered, "independent-org-1", "witness-key-1", public),
                     "forged signed revision accepted")
        altered = copy.deepcopy(report)
        altered["signature_base64"] = base64.b64encode(b"\x00" * 64).decode()
        expect_error(lambda: w.verify_report(file, altered, "independent-org-1", "witness-key-1", public),
                     "forged signature accepted")
        expect_error(lambda: w.verify_report(file, report, "wrong-custodian", "witness-key-1", public),
                     "wrong custodian accepted")
        expect_error(lambda: w.verify_report(file, report, "independent-org-1", "wrong-key", public),
                     "wrong key ID accepted")
        altered_req = copy.deepcopy(file)
        altered_req["review_reference_sha256"] = "f" * 64
        expect_error(lambda: w.verify_report(altered_req, report, "independent-org-1",
                                             "witness-key-1", public),
                     "unrelated reviewed request reused an attestation")
        forged_report = copy.deepcopy(report)
        forged_report["extra_claim"] = "deployment_verified"
        expect_error(lambda: w.verify_report(file, forged_report, "independent-org-1",
                                             "witness-key-1", public),
                     "unknown authority field accepted")
        # Branch audit also signs and validates an exact reference, not file bytes.
        bfetch, _ = fake_fetch(branch)
        breport = w.checked_report(branch, "independent-org-1", "witness-key-1", bfetch, private)
        assert breport["observed_file_sha256"] is None
        assert w.verify_report(branch, breport, "independent-org-1", "witness-key-1", public)
        assert w.digest(branch) != w.digest(file)
        assert w.DOMAIN.startswith(b"NEXUS\x00studio-")
        assert len(w.canonical(file)) < w.MAX_REQUEST

    print(json.dumps({"status": "PASS", "witness": "external-offline-unit",
                      "checks": ["source-only-export", "pinned-repository", "strict-json",
                                 "real-ed25519-sign-and-verify", "different-source-request",
                                 "no-false-provider-independence", "branch-sha-verification",
                                 "file-blob-and-byte-verification", "symlink-rejection",
                                 "truncated-tree-rejection", "forged-signature-rejection",
                                 "signature-key-identity", "no-overwrite-output"],
                      "real_provider_calls": 0, "independent_host_provisioned": False}))


if __name__ == "__main__":
    run()
