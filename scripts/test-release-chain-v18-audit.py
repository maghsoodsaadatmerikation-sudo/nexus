#!/usr/bin/env python3
"""Synthetic and hostile tests for v1.8 read-only two-hop chain audit."""
from __future__ import annotations

import copy
import hashlib
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
p = importlib.util.spec_from_file_location("release_chain_v18", ROOT / "release-chain-v18-audit.py")
audit = importlib.util.module_from_spec(p)
p.loader.exec_module(audit)

REPO = "maghsoodsaadatmerikation-sudo/nexus"
SHA = "a" * 40
PARENT = 1001
CHILD = 2002
REPO_ID = 1330624116
DIGEST = "b" * 64


def fixture():
    return {
        "repo": REPO, "sha": SHA, "workflow_sha": SHA,
        "parent_id": PARENT, "rebuild_id": CHILD,
        "repository": {"id": REPO_ID, "full_name": REPO,
                       "default_branch": "main", "archived": False, "disabled": False},
        "main_branch": {"name": "main", "commit": {"sha": SHA}},
        "parent": {
            "id": PARENT, "name": "NEXUS Verification",
            "path": ".github/workflows/verify.yml", "event": "push",
            "head_branch": "main", "head_sha": SHA, "head_commit": {"id": SHA},
            "status": "completed", "conclusion": "success", "run_attempt": 1,
            "repository": {"id": REPO_ID, "full_name": REPO},
            "head_repository": {"id": REPO_ID, "full_name": REPO},
        },
        "rebuild": {
            "id": CHILD, "name": "NEXUS v1.8 Independent Rebuild",
            "path": ".github/workflows/v1.8-independent-rebuild.yml",
            "event": "workflow_run", "head_branch": "main",
            "head_sha": SHA, "head_commit": {"id": SHA},
            "status": "completed", "conclusion": "success", "run_attempt": 1,
            "repository": {"id": REPO_ID, "full_name": REPO},
            "head_repository": {"id": REPO_ID, "full_name": REPO},
        },
        "evidence": {
            "schema": "nexus.v1.8.independent-rebuild-evidence.v1",
            "status": "PASS", "candidate_sha": SHA,
            "nexus_verification_run_id": str(PARENT),
            "independent_rebuild_run_id": str(CHILD),
            "builders": {
                "a": {"environment": "github-hosted ubuntu-24.04", "executable_sha256": DIGEST},
                "b": {"environment": "github-hosted ubuntu-24.04", "executable_sha256": DIGEST},
            },
            "executable_digest_match": True,
            "production_mutation_performed": False,
            "paid_upgrade_required": False,
            "secret_value_recorded": False,
            "authority_expansion": "NONE",
            "claim_boundary": "Byte-identical gateway executable across the two independent GitHub-hosted rebuild jobs in this run under the recorded pinned build definition only.",
        },
    }


class TestReleaseChain(unittest.TestCase):
    def deny(self, modify, message=None):
        inputs = copy.deepcopy(fixture())
        modify(inputs)
        with self.assertRaises(audit.ProvenanceError) as ctx:
            audit.validate_chain(**inputs)
        if message:
            self.assertIn(message, str(ctx.exception))

    def test_real_public_2026_11_18_artifact_byte_identity_and_chain(self):
        # Source: GitHub Actions artifact ID 14390824887, run 44222980195.
        # SHA-256 is calculated from the ORIGINAL JSON entry in the ZIP,
        # independently of this committed regression fixture.
        artifact = (ROOT / "fixtures" / "v1.8-rebuild-evidence-main-2026-11-18.json").read_bytes()
        self.assertEqual(hashlib.sha256(artifact).hexdigest(),
                         "220b08c8c41f875679cbb18044746dc00f7e3d16e8d5a411cd276a0fd02a4474")
        real = json.loads(artifact)
        self.assertIs(type(real["nexus_verification_run_id"]), str)
        self.assertIs(type(real["independent_rebuild_run_id"]), str)
        inputs = fixture()
        inputs["evidence"] = real
        inputs["sha"] = real["candidate_sha"]
        inputs["workflow_sha"] = real["candidate_sha"]
        inputs["parent_id"] = int(real["nexus_verification_run_id"])
        inputs["rebuild_id"] = int(real["independent_rebuild_run_id"])
        inputs["parent"]["id"] = inputs["parent_id"]
        inputs["rebuild"]["id"] = inputs["rebuild_id"]
        for obj in (inputs["parent"], inputs["rebuild"]):
            obj["head_sha"] = real["candidate_sha"]
            obj["head_commit"]["id"] = real["candidate_sha"]
        inputs["main_branch"]["commit"]["sha"] = real["candidate_sha"]
        report = audit.validate_chain(**inputs)
        self.assertEqual(report["status"], "CONSISTENT_ONLY")
        self.assertFalse(report["release_authorized"])
        self.assertEqual(report["independent_executable_sha256"],
                         "c6dd176f82b2789e669bcc5fc1f9e0cd47b569c46d888612457ca44f2166de32")

    def test_valid_two_hop_consistency_without_release_authority(self):
        report = audit.validate_chain(**fixture())
        self.assertEqual(report["status"], "CONSISTENT_ONLY")
        self.assertEqual(report["authority"], "none")
        self.assertIs(report["release_authorized"], False)
        self.assertIs(report["production_mutation"], False)
        self.assertEqual(report["independent_executable_sha256"], DIGEST)

    def test_child_pr_or_dispatch_rejected(self):
        for event in ("push", "pull_request", "workflow_dispatch", "schedule"):
            with self.subTest(event=event):
                self.deny(lambda v: v["rebuild"].update(event=event), "chained workflow_run")

    def test_parent_chain_substitution_rejected(self):
        self.deny(lambda v: v["parent"].update(event="workflow_run"), "actual push")

    def test_child_fork_main_rejected(self):
        self.deny(lambda v: v["rebuild"]["head_repository"].update(id=33), "fork")

    def test_parent_fork_main_rejected(self):
        self.deny(lambda v: v["parent"]["head_repository"].update(id=33), "fork")

    def test_rebuild_wrong_repo_rejected(self):
        self.deny(lambda v: v["rebuild"]["repository"].update(full_name="bad/nexus"), "repository")

    def test_parent_failed_rejected(self):
        self.deny(lambda v: v["parent"].update(conclusion="failure"), "successfully completed")

    def test_rebuild_failed_rejected(self):
        self.deny(lambda v: v["rebuild"].update(conclusion="failure"), "successfully")

    def test_rebuild_rerun_rejected(self):
        self.deny(lambda v: v["rebuild"].update(run_attempt=2), "rerun")

    def test_parent_rerun_rejected(self):
        self.deny(lambda v: v["parent"].update(run_attempt=2), "rerun")

    def test_rebuild_wrong_workflow_rejected(self):
        self.deny(lambda v: v["rebuild"].update(path=".github/workflows/other.yml"), "name/path")

    def test_parent_wrong_workflow_rejected(self):
        self.deny(lambda v: v["parent"].update(name="Fake Verification"), "name/path")

    def test_rebuild_sha_mismatch_rejected(self):
        self.deny(lambda v: v["rebuild"].update(head_sha="c" * 40), "SHA mismatch")

    def test_main_advanced_since_rebuild_rejected(self):
        self.deny(lambda v: v["main_branch"]["commit"].update(sha="c" * 40), "current trusted main")

    def test_actual_evidence_requires_canonical_string_run_ids(self):
        for key, wrong in (
            ("nexus_verification_run_id", PARENT),
            ("independent_rebuild_run_id", CHILD),
            ("nexus_verification_run_id", "0" + str(PARENT)),
            ("independent_rebuild_run_id", "+" + str(CHILD)),
            ("independent_rebuild_run_id", str(CHILD) + " "),
            ("nexus_verification_run_id", True),
        ):
            with self.subTest(key=key, wrong=wrong):
                self.deny(lambda v: v["evidence"].update({key: wrong}), "run ID mismatch")

    def test_evidence_wrong_parent_run_id_rejected(self):
        self.deny(lambda v: v["evidence"].update(nexus_verification_run_id=999), "parent run ID")

    def test_evidence_wrong_rebuild_run_id_rejected(self):
        self.deny(lambda v: v["evidence"].update(independent_rebuild_run_id=999), "rebuild run ID")

    def test_evidence_wrong_sha_rejected(self):
        self.deny(lambda v: v["evidence"].update(candidate_sha="c" * 40), "candidate SHA")

    def test_evidence_duplicate_or_missing_builder_rejected(self):
        self.deny(lambda v: v["evidence"]["builders"].pop("b"), "two exact builder")

    def test_evidence_fake_matching_flag_not_enough(self):
        self.deny(lambda v: v["evidence"]["builders"]["b"].update(executable_sha256="c"*64),
                  "digests disagree")

    def test_evidence_nonhex_digest_rejected(self):
        self.deny(lambda v: v["evidence"]["builders"]["a"].update(executable_sha256="g"*64),
                  "invalid builder a")

    def test_evidence_boolean_int_confusion_rejected(self):
        self.deny(lambda v: v["evidence"].update(nexus_verification_run_id=True),
                  "parent run ID")

    def test_evidence_assertions_are_exact_booleans(self):
        self.deny(lambda v: v["evidence"].update(production_mutation_performed=0), "unsafe")
        self.deny(lambda v: v["evidence"].update(executable_digest_match=1), "digests")

    def test_evidence_unauthorized_claim_rejected(self):
        self.deny(lambda v: v["evidence"].update(authority_expansion="GRANTED"), "authority")

    def test_evidence_unknown_key_rejected(self):
        self.deny(lambda v: v["evidence"].update(release_authorized=True), "unexpected")

    def test_evidence_bad_environment_rejected(self):
        self.deny(lambda v: v["evidence"]["builders"]["a"].update(environment="unsafe runner"),
                  "environment")

    def test_evidence_bad_status_rejected(self):
        self.deny(lambda v: v["evidence"].update(status="UNKNOWN"), "schema/status")

    def test_evidence_nonstring_claim_rejected(self):
        self.deny(lambda v: v["evidence"].update(claim_boundary=12), "claim boundary")

    def test_child_parent_same_run_id_rejected(self):
        self.deny(lambda v: v.update(rebuild_id=PARENT), "identical rebuild")

    def test_missing_parent_run_identity_rejected(self):
        self.deny(lambda v: v["parent"].pop("head_repository"), "head repository")

    def test_unknown_json_properties_denied_before_report(self):
        self.deny(lambda v: v["evidence"].pop("status"), "missing")

    def test_loader_has_no_network_or_release_capability(self):
        src = (ROOT / "release-chain-v18-audit.py").read_text(encoding="utf-8")
        for term in ("gh release create", "subprocess.run(", "requests.get(", "urllib.request"):
            self.assertNotIn(term, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
