#!/usr/bin/env python3
"""Synthetic adversarial attestation result tests; no network, keys or release."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("attestation_subject", SCRIPTS / "release-v18-attestation-subject.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

ARTIFACT = b'{"schema":"nexus.v1.8.independent-rebuild-evidence.v1"}\n'
REPO_ID = 1330624116

def valid():
    return [{"verificationResult": {
        "signature": {"certificate": {"sourceRepositoryIdentifier": str(REPO_ID)}},
        "verifiedTimestamps": [{"type": "transparency-log"}],
        "statement": {
            "predicateType": "https://slsa.dev/provenance/v1",
            "subject": [{"name": "v1.8-reproducibility-evidence.json",
                         "digest": {"sha256": hashlib.sha256(ARTIFACT).hexdigest()}}],
            "predicate": {"buildDefinition": {"externalParameters": {"UNTRUSTED": True}}},
        },
    }, "attestation": {"untrusted_metadata": True}}]


class AttestationSubjectTests(unittest.TestCase):
    def verify(self, payload=None):
        return validator.verify_verified_output(
            result=valid() if payload is None else payload,
            evidence=ARTIFACT, expected_repo_id=REPO_ID,
        )

    def deny(self, edit):
        source = copy.deepcopy(valid())
        edit(source)
        with self.assertRaises(validator.ProvenanceError):
            self.verify(source)

    def test_valid_verified_result_is_only_consistency(self):
        result = self.verify()
        self.assertEqual(result["status"], "ATTESTATION_RESULT_CONSISTENT_ONLY")
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["production_mutation"])
        self.assertEqual(result["verified_result_count"], 1)

    def test_multiple_matching_results(self):
        source = valid()
        source.append(copy.deepcopy(source[0]))
        self.assertEqual(self.verify(source)["verified_result_count"], 2)

    def test_missing_or_empty_array(self):
        for arr in ([], [None], [{}], "not an array"):
            with self.subTest(arr=arr):
                with self.assertRaises(validator.ProvenanceError):
                    self.verify(arr)

    def test_repository_reuse_id_mismatch(self):
        self.deny(lambda v: v[0]["verificationResult"]["signature"]["certificate"].update(
            sourceRepositoryIdentifier="99999"))

    def test_repository_bool_id_rejected(self):
        self.deny(lambda v: v[0]["verificationResult"]["signature"]["certificate"].update(
            sourceRepositoryIdentifier=True))

    def test_missing_certificate_rejected(self):
        self.deny(lambda v: v[0]["verificationResult"].pop("signature"))

    def test_untrusted_predicate_claim_cannot_override_signature(self):
        self.deny(lambda v: (
            v[0]["verificationResult"]["signature"]["certificate"].update(sourceRepositoryIdentifier="1"),
            v[0]["verificationResult"]["statement"]["predicate"].update(release_authorized=True),
        ))

    def test_wrong_predicate_type(self):
        self.deny(lambda v: v[0]["verificationResult"]["statement"].update(predicateType="other"))

    def test_missing_signed_subject(self):
        self.deny(lambda v: v[0]["verificationResult"]["statement"].update(subject=[]))

    def test_ambiguous_multiple_subjects(self):
        self.deny(lambda v: v[0]["verificationResult"]["statement"]["subject"].append(
            copy.deepcopy(v[0]["verificationResult"]["statement"]["subject"][0])))

    def test_wrong_hash_rejected(self):
        self.deny(lambda v: v[0]["verificationResult"]["statement"]["subject"][0]["digest"].update(
            sha256="0"*64))

    def test_hash_algorithm_missing_rejected(self):
        self.deny(lambda v: v[0]["verificationResult"]["statement"]["subject"][0]["digest"].update(
            sha256=None, sha512="0"*128))

    def test_uppercase_digest_rejected(self):
        self.deny(lambda v: v[0]["verificationResult"]["statement"]["subject"][0]["digest"].update(
            sha256=hashlib.sha256(ARTIFACT).hexdigest().upper()))

    def test_missing_verification_timestamp_field(self):
        self.deny(lambda v: v[0]["verificationResult"].pop("verifiedTimestamps"))

    def test_wrong_digest_in_second_attestation_not_ignored(self):
        source = valid()
        fake = copy.deepcopy(source[0])
        fake["verificationResult"]["statement"]["subject"][0]["digest"]["sha256"] = "1"*64
        source.append(fake)
        with self.assertRaises(validator.ProvenanceError):
            self.verify(source)

    def test_byte_mutation_not_trusted(self):
        with self.assertRaises(validator.ProvenanceError):
            validator.verify_verified_output(
                result=valid(), evidence=ARTIFACT + b"x", expected_repo_id=REPO_ID)

    def test_fake_empty_and_oversized_evidence_denied(self):
        for artifact in (b"", b"a" * (1024*1024+1)):
            with self.assertRaises(validator.ProvenanceError):
                validator.verify_verified_output(
                    result=valid(), evidence=artifact, expected_repo_id=REPO_ID)

    def test_more_than_30_results_denied(self):
        with self.assertRaises(validator.ProvenanceError):
            self.verify(valid()*31)

    def test_loader_rejects_duplicate_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"verify.json"
            path.write_text('[{"verificationResult":{"statement":1,"statement":2}}]')
            with self.assertRaises(validator.ProvenanceError):
                validator.read_attestation_results(path)

    def test_loader_rejects_invalid_json_values(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"verify.json"
            for content in ("[]", "[NaN]", "{}", "[1]"):
                path.write_text(content)
                with self.assertRaises(validator.ProvenanceError):
                    validator.read_attestation_results(path)

    def test_loader_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            orig=Path(d)/"valid.json"
            orig.write_text(json.dumps(valid()))
            symlink=Path(d)/"link.json"
            symlink.symlink_to(orig)
            with self.assertRaises(validator.ProvenanceError):
                validator.read_attestation_results(symlink)

    def test_no_external_api_or_release_mutation(self):
        text = (SCRIPTS/"release-v18-attestation-subject.py").read_text()
        for forbidden in ("subprocess.run", "gh release", "urllib.request", "requests.get", "os.system", "exec("):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
