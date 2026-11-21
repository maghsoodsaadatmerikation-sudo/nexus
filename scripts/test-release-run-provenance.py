#!/usr/bin/env python3
"""Hostile, offline tests of the NEXUS release-run provenance evaluator."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("release_provenance", HERE / "release-run-provenance.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

REPO = "maghsoodsaadatmerikation-sudo/nexus"
SHA = "a" * 40
ID = 142857
REPO_ID = 1330624116


def good(release="v2.5"):
    name, path = gate.SOURCE_WORKFLOWS[release]
    return {
        "release": release,
        "repo": REPO,
        "run_id": ID,
        "sha": SHA,
        "workflow_sha": SHA,
        "run": {
            "id": ID, "name": name, "path": path,
            "event": "push", "head_branch": "main", "status": "completed",
            "conclusion": "success", "run_attempt": 1, "head_sha": SHA,
            "head_commit": {"id": SHA},
            "repository": {"id": REPO_ID, "full_name": REPO},
            "head_repository": {"id": REPO_ID, "full_name": REPO},
        },
        "repository": {"id": REPO_ID, "full_name": REPO, "default_branch": "main",
                       "archived": False, "disabled": False},
        "main_branch": {"name": "main", "commit": {"sha": SHA}},
    }


class TestReleaseRunProvenance(unittest.TestCase):
    def denies(self, patch, reason=None):
        args = copy.deepcopy(good())
        patch(args)
        with self.assertRaises(gate.ProvenanceError) as failure:
            gate.validate(**args)
        if reason:
            self.assertIn(reason, str(failure.exception))

    def test_good_run(self):
        gate.validate(**good())

    def test_each_version_uses_exact_trusted_workflow(self):
        self.assertEqual(len(gate.SOURCE_WORKFLOWS), 10)
        for version in gate.SOURCE_WORKFLOWS:
            with self.subTest(version=version):
                gate.validate(**good(version))

    def test_wrong_workflow_name(self):
        self.denies(lambda v: v["run"].update(name="NEXUS Verification"), "name/path")

    def test_wrong_workflow_path(self):
        self.denies(lambda v: v["run"].update(path=".github/workflows/fake.yml"), "name/path")

    def test_pull_request_success_cannot_publish(self):
        self.denies(lambda v: v["run"].update(event="pull_request"), "actual push")

    def test_manual_success_cannot_publish(self):
        self.denies(lambda v: v["run"].update(event="workflow_dispatch"), "actual push")

    def test_chain_success_not_implicitly_trusted(self):
        # v1.8 currently depends on a workflow_run intermediate; until parent
        # provenance is proven, fail closed rather than granting release power.
        self.denies(lambda v: v.update(release="v1.8", run={
            **good("v1.8")["run"], "event": "workflow_run",
        }), "actual push")

    def test_success_on_fork_main_cannot_publish(self):
        self.denies(lambda v: v["run"]["head_repository"].update(
            id=999, full_name="other/nexus"), "fork")

    def test_success_from_other_repo_cannot_publish(self):
        self.denies(lambda v: v["run"]["repository"].update(id=999), "repository")

    def test_wrong_run_identity(self):
        self.denies(lambda v: v["run"].update(id=99), "run ID")

    def test_wrong_sha(self):
        self.denies(lambda v: v["run"].update(head_sha="b"*40), "head SHA")

    def test_wrong_head_commit(self):
        self.denies(lambda v: v["run"].update(head_commit={"id": "b"*40}), "head commit")

    def test_stale_main_sha(self):
        self.denies(lambda v: v["main_branch"]["commit"].update(sha="b"*40), "current trusted main")

    def test_workflow_context_sha_mismatch(self):
        self.denies(lambda v: v.update(workflow_sha="b"*40), "current trusted main")

    def test_wrong_branch(self):
        self.denies(lambda v: v["run"].update(head_branch="feature"), "actual push")

    def test_skipped_workflow(self):
        self.denies(lambda v: v["run"].update(conclusion="skipped"), "successfully completed")

    def test_partial_workflow(self):
        self.denies(lambda v: v["run"].update(status="in_progress", conclusion=None), "successfully completed")

    def test_run_rerun_denied(self):
        self.denies(lambda v: v["run"].update(run_attempt=2), "rerun")

    def test_boolean_id_denied(self):
        self.denies(lambda v: v["run"].update(id=True), "source run ID")

    def test_missing_source_metadata_denied(self):
        self.denies(lambda v: v["run"].pop("head_repository"), "fork")

    def test_archived_repository_denied(self):
        self.denies(lambda v: v["repository"].update(archived=True), "archived")

    def test_wrong_default_branch_denied(self):
        self.denies(lambda v: v["repository"].update(default_branch="develop"), "default branch")

    def test_unknown_release_denied(self):
        self.denies(lambda v: v.update(release="v2.6"), "unknown release")

    def test_duplicate_json_keys_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "run.json"
            file.write_text('{"id": 1, "id": 2}', encoding="utf-8")
            with self.assertRaises(gate.ProvenanceError):
                gate.read_json(file)

    def test_infinite_json_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "run.json"
            file.write_text('{"id": NaN}', encoding="utf-8")
            with self.assertRaises(gate.ProvenanceError):
                gate.read_json(file)

    def test_invalid_utf8_and_top_level_list_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "run.json"
            file.write_bytes(b"\xff\xfe")
            with self.assertRaises(gate.ProvenanceError):
                gate.read_json(file)
            file.write_text("[]", encoding="utf-8")
            with self.assertRaises(gate.ProvenanceError):
                gate.read_json(file)

    def test_metadata_reader_caps_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "oversized.json"
            file.write_bytes(b" " * (2*1024*1024 + 1))
            with self.assertRaises(gate.ProvenanceError):
                gate.read_json(file)

    def test_no_python_assert_as_security_gate(self):
        src = (HERE / "release-run-provenance.py").read_text(encoding="utf-8")
        self.assertNotIn("assert ", src)

    def test_no_network_or_publish_code(self):
        src = (HERE / "release-run-provenance.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "urllib.request", "requests.", "httpx.",
                          "gh release", "gh api", "os.system", "exec(", "eval("):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
