#!/usr/bin/env python3
"""Stage26 source and negative-proof tests, independent of emulator availability."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
src=ROOT/"scripts/test-stage26-emulator-witness.py"
spec=importlib.util.spec_from_file_location("stage26_witness",src)
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
EXAMPLE={
  "status":"VERIFIED_PAIR_FOR_ANDROID_EMULATOR",
  "same_temporary_certificate":True,
  "app_compiled_bytes_equal":True,
  "real_android_emulator_executed":False,
}
PROOF=";".join(w.REQUIRED_PROOF)
LOG=("\n".join("INSTRUMENTATION_RESULT: "+x for x in (
    "schema=nexus.stage26.android-emulator.v1",
    "status=PASS",
    "real_android_emulator=true",
    "real_android_hardware=false",
    "synthetic_only=true",
    "original_Railway_data=not_accessed",
    "network_permission=none",
    "checks=18",
    "proof="+PROOF,
))+"\nINSTRUMENTATION_CODE: -1\n")

class Stage26Source(unittest.TestCase):
    def test_real_witness_fixture_validates_only_matching_evidence(self):
        result=w.witness(LOG,EXAMPLE)
        self.assertEqual(result["status"],"ANDROID_EMULATOR_SYNTHETIC_ACCEPTANCE_PASS")
        self.assertFalse(result["android_real_hardware_tested"])
        self.assertFalse(result["SAF_actual_document_bytes_written_and_read"])

    def test_failure_without_real_instrumentation_code(self):
        with self.assertRaises(w.Refused):
            w.witness(LOG.replace("CODE: -1","CODE: 0"),EXAMPLE)

    def test_failure_on_false_live_device_claim(self):
        with self.assertRaises(w.Refused):
            w.witness(LOG.replace("real_android_hardware=false","real_android_hardware=true"),EXAMPLE)

    def test_failure_on_missing_picker_proof(self):
        with self.assertRaises(w.Refused):
            w.witness(LOG.replace(";document-open-save-pickers",""),EXAMPLE)

    def test_failure_on_missing_runtime_checks(self):
        with self.assertRaises(w.Refused):
            w.witness(LOG.replace("checks=18","checks=2"),EXAMPLE)

    def test_failure_on_duplicate_protocol_field(self):
        with self.assertRaises(w.Refused):
            w.witness(LOG+"INSTRUMENTATION_RESULT: status=PASS\n",EXAMPLE)

    def test_failure_on_unverified_apk_pair(self):
        with self.assertRaises(w.Refused):
            w.witness(LOG,{**EXAMPLE,"app_compiled_bytes_equal":False})

    def test_instrumentation_only_contains_synthetic_data(self):
        src=(ROOT/"android/stage26/src/org/nexus/offline/stage26/test/Stage26Instrumentation.java").read_text()
        for token in ("SYNTHETIC_STAGE26_DO_NOT_USE",
                      "UiAutomation",
                      "getRootInActiveWindow",
                      "GLOBAL_ACTION_BACK",
                      "new W.Vault()",
                      "work-review-required",
                      "work-unlock-failed",
                      "tampered-archive-accepted"):
            self.assertIn(token,src)
        native_app=(ROOT/"android/stage25/src/org/nexus/offline/stage25/MainActivity.java").read_text()
        self.assertIn("Intent.ACTION_CREATE_DOCUMENT", native_app)
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT", native_app)
        for unsafe in ("https://github.com", "https://api.openai.com",
                       "RAILWAY_TOKEN", "getSharedPreferences",
                       "setWebContentsDebuggingEnabled(true)"):
            self.assertNotIn(unsafe,src)

    def test_run_isolated_from_real_phone_and_production(self):
        src=(ROOT/"scripts/run-stage26-android-emulator.sh").read_text()
        for marker in ("avdmanager create avd", "adb shell am instrument -w -r",
                       "pm clear org.nexus.offline.stage25",
                       "adb install", "no-window", "/dev/kvm",
                       "stage26-emulator-witness.json"):
            self.assertIn(marker,src)
        self.assertNotIn("adb -s user",src)
        self.assertNotIn("https://",src)

    def test_signing_key_is_ephemeral_and_never_uploaded(self):
        src=(ROOT/"scripts/build-stage26-test-apks.sh").read_text()
        self.assertIn("cleanup",src)
        self.assertIn("rm -rf \"$KEY_DIR\"",src)
        self.assertIn("test ! -d \"$KEY_DIR\"",src)
        self.assertIn("stage26-instrumentation-only.apk",src)
        self.assertNotIn("git push",src)

    def test_only_pull_request_read_permissions(self):
        workflow=(ROOT/".github/workflows/stage26-android-emulator.yml").read_text()
        self.assertIn("  pull_request:",workflow)
        self.assertNotIn("pull_request_target",workflow)
        self.assertIn("permissions:\n  contents: read",workflow)
        self.assertNotIn("contents: write",workflow)
        self.assertNotIn("id-token: write",workflow)
        self.assertNotIn("attestations: write",workflow)

if __name__=="__main__":
    unittest.main(verbosity=2)
