#!/usr/bin/env python3
"""No-credential, no-network, disposable tests for the guarded Railway capture.

The fake CLI is a local executable: no live Railway user data is fetched.
All copies live under TemporaryDirectory; no public CI artifact is uploaded.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "capture-railway-volume-readonly.py"
REPO = HERE.parent
EXAMPLE_ID = "synthetic-case"


FAKE_CLI = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
args=sys.argv[1:]
if args==["--version"]:
  if os.getenv("MOCK_MODE")=="wrong-version": print("railway 0.0.0")
  else: print("railway 5.71.0")
  sys.exit(0)
if args[-1:] == ["--help"]:
  if os.getenv("MOCK_MODE")=="broken-help":
    print("unknown command")
  elif "download" in args:
    print("Usage: railway volume files download <REMOTE_PATH> [LOCAL_PATH]\n--concurrency <N>\n--overwrite")
  else:
    print("Volume file options: download, --volume")
  sys.exit(0)
expected=[
"volume","--project","2ac7887b-d67a-48be-8a7b-bd54092893ae",
"--environment","56c4bc45-0e62-4aa9-832f-884bb1aa620c",
"--service","0032fc74-2c52-475d-b9df-9dca59237d93",
"files","--volume","cc47a350-6c7e-4487-89d9-c4b390f94884",
"download","/"
]
if args[:len(expected)]!=expected or args[-2:]!=["--concurrency","1"]:
  sys.exit(18)
if os.getenv("MOCK_MODE")=="fail":
  sys.exit(25)
target=Path(args[len(expected)])
target.mkdir(parents=True, exist_ok=False)
(target / "requests").mkdir()
workspace_id="synthetic-case"
name=workspace_id.encode().hex()
document={"schema_version":1,"workspace":{"id":workspace_id}}
(target / (name+".json")).write_text(json.dumps(document),encoding="utf-8")
(target / "requests" / name).write_bytes(b"pending\n")
mode=os.getenv("MOCK_MODE")
if mode=="symlink":
  (target/"escape").symlink_to("/etc/passwd")
if mode=="extra":
  (target/"unrecognized.dat").write_bytes(b"never-allowed")
if mode=="no-requests":
  for p in (target/"requests").iterdir(): p.unlink()
  (target/"requests").rmdir()
'''


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-capture-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.bin = self.base / "fake-railway"
        self.bin.write_text(FAKE_CLI, encoding="utf-8")
        self.bin.chmod(0o700)
        self.root = self.base / "private-capture"

    def run_capture(self, execute=False, token=True, mode=None, path=None):
        env = os.environ.copy()
        env.pop("RAILWAY_TOKEN", None)
        env.pop("RAILWAY_API_TOKEN", None)
        if token: env["RAILWAY_TOKEN"] = "synthetic-token-do-not-use"
        if mode: env["MOCK_MODE"] = mode
        cmd = [sys.executable, str(SCRIPT),
               "--private-root", str(path or self.root), "--railway-bin", str(self.bin)]
        if execute: cmd.append("--execute")
        return subprocess.run(cmd, capture_output=True, text=True,
                              env=env, timeout=30)

    def test_default_is_plan_only_without_any_copy(self):
        result=self.run_capture(token=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("PLAN ONLY", result.stdout)
        self.assertFalse(self.root.exists())

    def test_execute_requires_authentication_before_create(self):
        result=self.run_capture(execute=True, token=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.root.exists())
        self.assertNotIn("synthetic-token", result.stderr)

    def test_readonly_cli_synthetic_capture_and_quarantined_roundtrip(self):
        result=self.run_capture(execute=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STRUCTURAL REHEARSAL: PASS", result.stdout)
        self.assertIn("NOT VERIFIED", result.stdout)
        self.assertTrue((self.root.stat().st_mode & 0o077)==0)
        receipt=json.loads((self.root/"isolated-intake"/"capture-receipt.json").read_text())
        intake=json.loads((self.root/"isolated-intake"/"intake-report.json").read_text())
        self.assertEqual(receipt["status"],"PRIVATE_CLI_COPY_AND_STRUCTURAL_REHEARSAL_PASS")
        self.assertFalse(receipt["production_mutation"])
        self.assertFalse(receipt["seal"])
        self.assertEqual(receipt["authority"],"none")
        self.assertEqual(receipt["independent_complete_production_backup"],"NOT_PROVEN")
        self.assertEqual(receipt["source_consistency"],"NOT_VERIFIED_ATOMIC")
        self.assertTrue(receipt["local_copy_scans_matched_archive"])
        self.assertTrue(intake["local_copy_scans_matched_archive"])
        self.assertEqual(intake["source_consistency"],"not_verified")
        self.assertEqual(receipt["archive_sha256"],intake["snapshot_sha256"])
        self.assertTrue(intake["isolated_byte_roundtrip"])
        self.assertTrue((self.root/"isolated-intake"/
                         "isolated-restore-rehearsal"/".nexus-recovery-required").is_file())
        self.assertFalse((self.root/"copied-data"/".nexus-recovery-required").exists())
        self.assertFalse((self.root/"isolated-intake"/"capture-receipt.json").stat().st_mode & 0o077)

    def mutate_after_successful_intake(self, mutate):
        """Inject between the child's success and the parent's final receipt.

        Uses the real local fake-CLI + real private intake, never Railway.
        The only interception changes disposable files AFTER intake exits 0.
        """
        spec = importlib.util.spec_from_file_location("nexus_capture_final_test", SCRIPT)
        capture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(capture)
        arguments = argparse.Namespace(private_root=self.root, railway_bin=self.bin,
                                      rust_validator_bin=None, execute=True)
        original_run = subprocess.run
        mutated = []

        def intercept(cmd, *args, **kwargs):
            result = original_run(cmd, *args, **kwargs)
            if (len(cmd) > 1 and str(cmd[1]) == str(capture.INTAKE) and
                    result.returncode == 0):
                mutate()
                mutated.append(True)
            return result

        with patch.dict(os.environ, {"RAILWAY_TOKEN": "synthetic-token-do-not-use"}), \\
             patch.object(capture.subprocess, "run", side_effect=intercept), \\
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises((capture.CaptureBlocked, ValueError, OSError)):
                capture.execute(arguments)
        self.assertEqual(mutated, [True], "synthetic post-intake injection did not run")
        self.assertFalse((self.root / "isolated-intake" /
                          "capture-receipt.json").exists(),
                         "stale or altered private evidence must not get PASS")

    def test_archive_changed_after_child_pass_is_blocked(self):
        def mutate():
            archive = self.root / "isolated-intake" / "nexus-private-data-snapshot.json"
            with archive.open("ab") as handle:
                handle.write(b" ")
        self.mutate_after_successful_intake(mutate)

    def test_source_workspace_changed_after_child_pass_is_blocked(self):
        def mutate():
            file = self.root / "copied-data" / (EXAMPLE_ID.encode().hex() + ".json")
            value = json.loads(file.read_text())
            value["synthetic_revision"] = "post-intake-drift"
            file.write_text(json.dumps(value))
        self.mutate_after_successful_intake(mutate)

    def test_restored_quarantine_changed_after_child_pass_is_blocked(self):
        def mutate():
            marker = (self.root / "isolated-intake" /
                      "isolated-restore-rehearsal" / ".nexus-recovery-required")
            with marker.open("ab") as handle:
                handle.write(b" ")
        self.mutate_after_successful_intake(mutate)

    def test_intake_report_wrong_origin_after_child_pass_is_blocked(self):
        def mutate():
            report = self.root / "isolated-intake" / "intake-report.json"
            value = json.loads(report.read_text())
            value["volume_id"] = "00000000-0000-0000-0000-000000000000"
            report.write_text(json.dumps(value))
        self.mutate_after_successful_intake(mutate)

    def test_intake_report_forged_archive_hash_after_child_pass_is_blocked(self):
        def mutate():
            report = self.root / "isolated-intake" / "intake-report.json"
            value = json.loads(report.read_text())
            value["snapshot_sha256"] = "0" * 64
            report.write_text(json.dumps(value))
        self.mutate_after_successful_intake(mutate)

    def test_intake_report_symlink_after_child_pass_is_blocked(self):
        def mutate():
            report = self.root / "isolated-intake" / "intake-report.json"
            outside = self.base / "private-synthetic-report.json"
            report.rename(outside)
            report.symlink_to(outside)
        self.mutate_after_successful_intake(mutate)

    def test_download_failure_never_reports_pass(self):
        result=self.run_capture(execute=True,mode="fail")
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn("PASS",result.stdout)
        self.assertNotIn("synthetic-token",result.stderr)
        self.assertFalse((self.root/"isolated-intake"/"capture-receipt.json").exists())

    def test_symlink_in_copied_volume_fails_closed(self):
        result=self.run_capture(execute=True,mode="symlink")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/"isolated-intake"/"capture-receipt.json").exists())

    def test_unexpected_content_is_refused_by_existing_intake(self):
        result=self.run_capture(execute=True,mode="extra")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/"isolated-intake"/"capture-receipt.json").exists())

    def test_missing_ledger_is_refused_by_existing_intake(self):
        result=self.run_capture(execute=True,mode="no-requests")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/"isolated-intake"/"capture-receipt.json").exists())

    def test_existing_private_root_is_never_overwritten(self):
        self.root.mkdir()
        sentinel=self.root/"sentinel.txt"
        sentinel.write_text("preserve")
        result=self.run_capture(execute=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(sentinel.read_text(),"preserve")

    def test_symlink_parent_is_refused(self):
        alias=self.base/"aliased"
        alias.symlink_to(self.base, target_is_directory=True)
        result=self.run_capture(execute=True,path=alias/"backup")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.base/"backup").exists())

    def test_public_repo_destination_is_refused(self):
        result=self.run_capture(execute=True,path=REPO/".unsafe-test-capture")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((REPO/".unsafe-test-capture").exists())

    def test_mismatched_cli_version_rejected_before_private_copy(self):
        result=self.run_capture(execute=True,mode="wrong-version")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.root.exists())
        self.assertIn("version or download syntax unsupported",result.stderr)

    def test_missing_cli_flag_rejected_before_private_copy(self):
        result=self.run_capture(execute=True,mode="broken-help")
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.root.exists())
        self.assertIn("version or download syntax unsupported",result.stderr)

    def test_nonexistent_cli_binary_rejected_before_private_copy(self):
        self.bin.unlink()
        result=self.run_capture(execute=True)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.root.exists())

    def test_never_includes_any_mutating_railway_command(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location("readonly_capture",SCRIPT)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        args=mod.permitted_download_command(self.bin,self.root/"data")
        self.assertEqual(args.count("download"),1)
        self.assertIn("--volume",args)
        for prohibited in ("delete","detach","attach","upload","restore","restart",
                           "redeploy","--overwrite","--override"):
            self.assertNotIn(prohibited,args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
