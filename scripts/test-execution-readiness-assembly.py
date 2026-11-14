#!/usr/bin/env python3
"""Negative tests for four-source assembly and CI reconciliation proof."""
import copy
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "execution_assembly", HERE / "verify-execution-readiness-assembly.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FourPRAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nexus-integrated-ci-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = copy.deepcopy(mod.load())
        paths = [i["path"] for i in self.manifest["inputs"]]
        paths += [".github/workflows/pr-verify.yml"]
        for path in paths:
            destination = self.root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(mod.ROOT / path, destination)

    def blocked(self, manifest=None):
        with self.assertRaises(mod.AssemblyBlocked):
            mod.verify(manifest if manifest is not None else self.manifest, self.root)

    def test_exact_assembly_and_ci_are_verified_without_release(self):
        report = mod.verify(self.manifest, self.root)
        self.assertEqual(report["status"], "SOURCE_ASSEMBLY_VERIFIED")
        self.assertEqual(report["exact_blob_files"], 16)
        self.assertEqual(report["original_source_prs"], [187, 188, 189, 190])
        self.assertEqual(report["manually_reconciled_primary_ci_tests"], 3)
        for field in ("production_backup_inspected", "production_restore_verified",
                      "merge_authorized", "release_authorized",
                      "live_deploy_settings_changed"):
            self.assertIs(report[field], False)

    def test_changed_bytes_fail_even_if_original_manifest_is_untouched(self):
        path = self.root / "ops/stage_d_transport.py"
        path.write_bytes(path.read_bytes() + b"\n# attempted drift\n")
        self.blocked()

    def test_modified_origin_blob_sha_is_detected(self):
        self.manifest["inputs"][0]["blob_sha"] = "0" * 40
        self.blocked()

    def test_wrong_commits_cannot_replace_original_sources(self):
        self.manifest["inputs"][0]["source_commit"] = "f" * 40
        self.blocked()

    def test_wrong_source_pr_cannot_replace_original_sources(self):
        self.manifest["inputs"][0]["pr"] = 190
        self.blocked()

    def test_missing_or_extra_source_is_blocked(self):
        self.manifest["inputs"].pop()
        self.blocked()
        self.manifest = copy.deepcopy(mod.load())
        self.manifest["inputs"][0]["path"] = "untrusted/file.txt"
        self.blocked()

    def test_duplicate_input_and_boolean_as_pr_are_blocked(self):
        self.manifest["inputs"][1] = copy.deepcopy(self.manifest["inputs"][0])
        self.blocked()
        self.manifest = copy.deepcopy(mod.load())
        self.manifest["inputs"][0]["pr"] = True
        self.blocked()

    def test_releasing_or_claiming_production_recovery_is_blocked(self):
        for key in ("production_recovery_verified",
                    "render_autodeploy_disabled_verified",
                    "strict_ruleset_enabled_verified", "release_authorized"):
            with self.subTest(field=key):
                document = copy.deepcopy(self.manifest)
                document[key] = True
                self.blocked(document)

    def test_arbitrary_base_or_manual_assembly_scope_is_blocked(self):
        self.manifest["base_sha"] = "b" * 40
        self.blocked()
        self.manifest = copy.deepcopy(mod.load())
        self.manifest["manually_reconciled"] = []
        self.blocked()

    def test_unchecked_operator_security_step_is_blocked(self):
        path = self.root / ".github/workflows/pr-verify.yml"
        text = path.read_text()
        text = text.replace("python3 scripts/test-stage-d-operator-transport.py", "")
        path.write_text(text)
        self.blocked()

    def test_unchecked_runtime_or_freeze_security_step_is_blocked(self):
        path = self.root / ".github/workflows/pr-verify.yml"
        original = path.read_text()
        for entry in ("python3 scripts/test-observe-pilot-runtime.py",
                      "python3 scripts/test-production-freeze-preflight.py"):
            with self.subTest(entry=entry):
                path.write_text(original.replace(entry, ""))
                self.blocked()

    def test_bypassed_workflow_permissions_and_unsafe_checkouts_fail(self):
        path = self.root / ".github/workflows/pilot-cross-runner-recovery.yml"
        original = path.read_text()
        for old, new in (("permissions:\n  contents: read",
                          "permissions:\n  contents: write"),
                         ("persist-credentials: false", "persist-credentials: true"),
                         ("ref: " + "$" + "{{ github.sha }}", "ref: main")):
            with self.subTest(old=old):
                path.write_text(original.replace(old, new))
                self.blocked()

    def test_missing_file_and_symlinked_file_fail(self):
        f = self.root / "scripts/production-freeze-preflight.py"
        f.unlink()
        self.blocked()
        f.symlink_to(mod.ROOT / "scripts/production-freeze-preflight.py")
        self.blocked()

    def test_duplicate_json_is_not_accepted(self):
        with self.assertRaises(mod.AssemblyBlocked):
            mod.unique_object([("schema", 1), ("schema", 2)])

    def test_manifest_forged_release_and_extra_keys_are_blocked(self):
        self.manifest["authority"] = "production"
        self.blocked()
        self.manifest = copy.deepcopy(mod.load())
        self.manifest["extra"] = "safety-bypass"
        self.blocked()


if __name__ == "__main__":
    unittest.main()
