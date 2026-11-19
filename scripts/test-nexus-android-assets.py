#!/usr/bin/env python3
"""NEXUS native Android APK source/asset confinement and reproducibility tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "nexus_android_assets_test",ROOT/"scripts/build-nexus-android-assets.py")
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
COMMIT="1"*40

class PublicAPKAssetsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="nexus-android-verified-public-")
        self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)
        self.output=self.base/"generated"

    def test_verified_bytes_deterministic_and_no_private_files(self):
        report=b.assemble(self.output,COMMIT)
        self.assertEqual(report["status"],"VERIFIED_ANDROID_ASSETS")
        self.assertTrue(report["no_network_permission"])
        self.assertFalse(report["android_hardware_tested"])
        self.assertEqual(b.verify(self.output,COMMIT)["count"],report["assets"])
        manifest=json.loads((self.output/b.CATALOG).read_bytes())
        self.assertEqual(set(manifest),{"schema","source_commit","no_network_permission",
                                       "no_user_data","assets"})
        self.assertIn("android-export.js",manifest["assets"])
        self.assertIn("motion/motion-ui.js",manifest["assets"])
        self.assertIn("device/device-worker.js",manifest["assets"])
        for forbidden in b.SKIP:
            self.assertNotIn(forbidden,manifest["assets"])
        self.assertNotIn("by Termux",(self.output/"apps.html").read_text())

    def test_native_apk_motion_navigation_and_save_reminder(self):
        b.assemble(self.output,COMMIT)
        motion=(self.output/"motion/index.html").read_text(encoding="utf-8")
        self.assertIn('href="/apps.html"', motion)
        self.assertIn('href="/"', motion)
        self.assertIn('id="motion-save-before-exit"', motion)
        self.assertIn('Download project + media ZIP', motion)
        self.assertIn('id="motion-draft-panel"', motion)
        self.assertIn('id="motion-draft-enable"', motion)
        self.assertIn('id="motion-draft-restore"', motion)
        self.assertIn('id="motion-draft-clear"', motion)
        script=(self.output/"motion/motion-ui.js").read_text()
        self.assertIn("AES-GCM",script)
        self.assertIn("PBKDF2",script)
        self.assertIn("240000",script)
        self.assertIn("localStorage.setItem(DRAFT_SLOT",script)
        self.assertNotIn("fetch(",script)

        self.assertEqual(b.verify(self.output,COMMIT)["status"],"EXACT_PUBLIC_ASSETS")

    def test_refuses_modified_asset_and_user_private_material(self):
        b.assemble(self.output,COMMIT)
        target=self.output/"motion/motion-ui.js"
        target.write_bytes(target.read_bytes()+b"//unsafe")
        with self.assertRaisesRegex(ValueError,"changed Android asset"):
            b.verify(self.output,COMMIT)
        target.write_bytes(b.assets(COMMIT)["motion/motion-ui.js"])
        (self.output/"private-user.txt").write_text("no file permitted")
        with self.assertRaisesRegex(ValueError,"unreviewed file"):
            b.verify(self.output,COMMIT)

    def test_refuses_wrong_commit_and_replacement_of_existing_output(self):
        b.assemble(self.output,COMMIT)
        with self.assertRaises(ValueError):
            b.assemble(self.output,COMMIT)
        with self.assertRaisesRegex(ValueError,"contract mismatch"):
            b.verify(self.output,"2"*40)
        for sha in ("main","", "2"*39, "B"*40):
            with self.subTest(sha=sha),self.assertRaises(ValueError):
                b.assets(sha)

    def test_runtime_permissions_strictly_absent(self):
        manifest=(ROOT/"mobile/android/app/src/main/AndroidManifest.xml").read_text()
        java=(ROOT/"mobile/android/app/src/main/java/org/nexus/mobile/MainActivity.java").read_text()
        # Ignore comments when inspecting manifest permission declarations.
        import re
        cleared=re.sub(r"<!--.*?-->","",manifest,flags=re.S)
        self.assertNotIn("<uses-permission",cleared)
        self.assertIn('android:allowBackup="false"',manifest)
        self.assertIn('android:usesCleartextTraffic="false"',manifest)
        self.assertIn('settings.setAllowFileAccess(false)',java)
        self.assertIn('settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW)',java)
        self.assertIn('Intent.ACTION_CREATE_DOCUMENT',java)
        self.assertIn('getContentResolver().openOutputStream',java)
        self.assertNotIn('android.permission.INTERNET',cleared)
        self.assertNotIn('setWebContentsDebuggingEnabled(true)',java)
        self.assertNotIn('http://',java)

    def test_native_export_is_bounded_and_user_chosen_only(self):
        js=(ROOT/"mobile/android/android-export.js").read_text()
        java=(ROOT/"mobile/android/app/src/main/java/org/nexus/mobile/MainActivity.java").read_text()
        self.assertIn("96*1024*1024",js)
        self.assertIn("48*1024",js)
        self.assertIn("MAX_EXPORT",java)
        self.assertIn("ACTION_CREATE_DOCUMENT",java)
        self.assertIn("Base64.decode",java)
        self.assertNotIn("fetch(",js)
        self.assertNotIn("XMLHttpRequest",js)

if __name__=="__main__":
    unittest.main(verbosity=2)
