#!/usr/bin/env python3
"""Semantic Rust audit of synthetic, private, operator-copied NEXUS data only.

Run only in disposable CI with a newly built validator. No user data,
provider credentials, network, or public artifact bytes.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

VALIDATOR = os.environ.get("NEXUS_PRIVATE_CORE_AUDIT_BIN", "")
INTAKE = Path(__file__).with_name("verify-offhost-volume-export.py")
VOLUME = "cc47a350-6c7e-4487-89d9-c4b390f94884"
DEPLOYMENT = "db2fd959-918e-49d5-b077-1ac74fac9a82"
COMMIT = "3c0977f4c7fc9fb5e9a78bdb1eeb581cb3cb4959"


class PrivateCoreAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nexus-rust-audit-synthetic-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "copy"
        self.data.mkdir()
        (self.data / "requests").mkdir()
        self.id = "synthetic-audit-case"
        self.filename = self.id.encode().hex() + ".json"
        self.target = self.data / self.filename
        self.work = self.root / "private-intake"
        self.snapshot = {
            "schema_version": 1,
            "workspace": {
                "id": self.id,
                "question": "Synthetic recovery semantics?",
                "goal": None, "constraints": [], "values": [],
                "claims": [], "alternatives": [], "judgment": None,
            },
            "events": [{
                "sequence": 0, "provenance_id": "synthetic:human",
                "kind": "WorkspaceCreated",
            }],
        }
        self.write()

    def write(self):
        self.target.write_text(json.dumps(self.snapshot, ensure_ascii=False))

    def invoke(self, include_validator=True, bin_path=None):
        args = [
            sys.executable, str(INTAKE), "--export-root", str(self.data),
            "--private-evidence-dir", str(self.work),
            "--volume-id", VOLUME, "--deployment-id", DEPLOYMENT,
            "--runtime-commit", COMMIT,
        ]
        if include_validator:
            args += ["--rust-validator-bin", str(bin_path or VALIDATOR)]
        return subprocess.run(args, capture_output=True, text=True, timeout=30)

    def assert_blocked(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / "intake-report.json").exists())
        self.assertNotIn(self.id, result.stdout + result.stderr)
        self.assertNotIn(self.snapshot["workspace"]["question"],
                         result.stdout + result.stderr)

    def test_real_rust_audit_accepts_full_valid_synthetic_history(self):
        self.snapshot["workspace"]["claims"].append({
            "id": "c-1", "text": "Synthetic evidence",
            "origin": "Human", "uncertainty": "Unknown",
        })
        self.snapshot["events"].append({
            "sequence": 1, "provenance_id": "synthetic:human",
            "kind": {"ClaimAdded": {"claim_id": "c-1"}},
        })
        self.snapshot["workspace"]["judgment"] = {
            "decision": "Synthetic choice", "rationale": "Fixture only",
        }
        self.snapshot["events"].append({
            "sequence": 2, "provenance_id": "synthetic:human",
            "kind": {"HumanJudgmentTransition": {
                "previous": None, "current": self.snapshot["workspace"]["judgment"]
            }},
        })
        self.write()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.work / "intake-report.json").read_text())
        self.assertEqual(report["status"], "STRUCTURAL_REHEARSAL_PASS")
        self.assertEqual(report["rust_core_audit"],
                         "pass_operator_supplied_rust_binary")
        self.assertEqual(report["rust_core_binary_identity"],
                         "operator_supplied_unverified")
        self.assertEqual(report["source_consistency"], "not_verified")
        self.assertEqual(report["independent_railway_backup"], "not_proven")
        self.assertTrue(report["local_copy_scans_matched_archive"])
        self.assertTrue(report["isolated_byte_roundtrip"])
        self.assertTrue(report["post_rust_source_and_restore_rechecked"])
        self.assertNotIn(self.id, result.stdout + result.stderr)

    def test_unverified_rust_check_never_appears_as_audit_pass(self):
        result = self.invoke(include_validator=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.work / "intake-report.json").read_text())
        self.assertEqual(report["rust_core_audit"], "not_evaluated")
        self.assertEqual(report["rust_core_binary_identity"], "not_verified")
        self.assertFalse(report["post_rust_source_and_restore_rechecked"])

    def test_structurally_valid_but_tampered_audit_sequence_fails(self):
        self.snapshot["events"][0]["sequence"] = 9
        self.write()
        self.assert_blocked(self.invoke())

    def test_unrecorded_human_judgment_fails(self):
        self.snapshot["workspace"]["judgment"] = {
            "decision": "NOT-AUTHORIZED", "rationale": "Synthetic",
        }
        self.write()
        self.assert_blocked(self.invoke())

    def test_unrecorded_claim_fails(self):
        self.snapshot["workspace"]["claims"].append({
            "id": "unlogged", "text": "Synthetic", "origin": "Human",
            "uncertainty": "Unknown",
        })
        self.write()
        self.assert_blocked(self.invoke())

    def test_missing_event_provenance_fails(self):
        self.snapshot["events"][0]["provenance_id"] = " "
        self.write()
        self.assert_blocked(self.invoke())

    def post_rust_mutator(self, target):
        """Run the actual Rust binary first, then alter synthetic private bytes.

        This recreates the window that was unguarded between a successful
        Rust subprocess exit and an intake receipt; no provider is involved.
        """
        targets = {
            "source": repr(str(self.target)),
            "restored_workspace": "str(Path(sys.argv[1]) / " + repr(self.filename) + ")",
            "restored_marker": "str(Path(sys.argv[1]) / '.nexus-recovery-required')",
        }
        location = targets[target]
        wrapper = self.root / ("post-rust-" + target + ".py")
        wrapper.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import subprocess, sys\n"
            "done = subprocess.run([" + repr(str(VALIDATOR)) + ", sys.argv[1]], "
            "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)\n"
            "if done.returncode != 0: sys.exit(done.returncode)\n"
            "with open(" + location + ", 'ab') as file: file.write(b' ')\n"
        )
        wrapper.chmod(0o700)
        return wrapper

    def test_copy_changed_after_rust_validated_is_blocked(self):
        self.assert_blocked(
            self.invoke(bin_path=self.post_rust_mutator("source"))
        )

    def test_quarantine_workspace_changed_after_rust_validated_is_blocked(self):
        self.assert_blocked(
            self.invoke(bin_path=self.post_rust_mutator("restored_workspace"))
        )

    def test_quarantine_marker_changed_after_rust_validated_is_blocked(self):
        self.assert_blocked(
            self.invoke(bin_path=self.post_rust_mutator("restored_marker"))
        )

    def test_invalid_core_validator_binary_fails_closed(self):
        self.assert_blocked(self.invoke(bin_path=self.root / "missing-rust-binary"))

    def test_symlinked_rust_validator_fails_closed(self):
        linked = self.root / "linked-rust-validator"
        linked.symlink_to(VALIDATOR)
        self.assert_blocked(self.invoke(bin_path=linked))


if __name__ == "__main__":
    if not VALIDATOR or not Path(VALIDATOR).is_file():
        raise SystemExit("BLOCKED: disposable compiled Rust audit binary not supplied")
    unittest.main(verbosity=2)
