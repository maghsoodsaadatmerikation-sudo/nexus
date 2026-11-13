#!/usr/bin/env python3
"""Stage25 native offline source tests without SDK/provider credentials."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("stage25",
    ROOT/"scripts"/"build-stage25-android-assets.py")
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class NativeOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage=a.stage23()
        cls.upstream=cls.stage.assemble_html(cls.stage.portable_source())
        cls.site=a.compile_html(cls.upstream)
        cls.html=cls.site.decode('utf8')
        cls.java=(ROOT/"android/stage25/src/org/nexus/offline/stage25/MainActivity.java").read_text()
        cls.manifest=(ROOT/"android/stage25/AndroidManifest.xml").read_text()

    def test_reproducible_assets(self):
        self.assertEqual(a.produce(self.upstream),a.produce(self.upstream))

    def test_compatible_encrypted_store(self):
        self.assertIn("indexedDB.open('nexus-private-work-mode-mobile-v23',1)",self.html)
        self.assertIn("vault.backup",self.html)
        self.assertIn("vault.restore",self.html)
        self.assertIn("window.NEXUS_NATIVE_EXPORT.save(name,btoa(encoded))",self.html)

    def test_no_native_auto_install_or_external_calls(self):
        for t in ["navigator.serviceWorker","URL.createObjectURL","fetch(",
                  "XMLHttpRequest", 'id="mobile-prepare"',"<iframe"]:
            self.assertNotIn(t,self.html)
        self.assertIn("connect-src 'none'",self.html)
        self.assertIn("form-action 'none'",self.html)
        self.assertIn("frame-src 'none'",self.html)

    def test_document_export_explicit_and_bounded(self):
        self.assertIn("blob.size>6*1024*1024",self.html)
        self.assertIn("Intent.ACTION_CREATE_DOCUMENT",self.java)
        self.assertIn("payload.length>LIMIT",self.java)
        self.assertIn("START.equals(webView.getUrl())",self.java)

    def test_file_import_user_picker_only(self):
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT",self.java)
        self.assertIn("Intent.CATEGORY_OPENABLE",self.java)
        self.assertIn("new Uri[]{uri}",self.java)
        self.assertNotIn("MANAGE_EXTERNAL_STORAGE",self.java)

    def test_network_blocked_on_every_request(self):
        self.assertIn('!\"GET\".equals(req.getMethod())',self.java)
        self.assertIn("return localResource(req.getUrl())",self.java)
        self.assertIn("return deny()",self.java)
        self.assertIn('new WebResourceResponse("text/html", "UTF-8"',self.java)
        self.assertIn("HOST.equals(uri.getHost())",self.java)
        self.assertIn('\"https\".equals(uri.getScheme())',self.java)
        self.assertNotIn("loadUrl(\"http",self.java)

    def test_webview_disables_unsafe_file_and_content_access(self):
        for forbidden in ("setAllowFileAccess(false)",
             "setAllowContentAccess(false)",
             "setAllowFileAccessFromFileURLs(false)",
             "setAllowUniversalAccessFromFileURLs(false)",
             "MIXED_CONTENT_NEVER_ALLOW",
             "setJavaScriptCanOpenWindowsAutomatically(false)"):
            self.assertIn(forbidden,self.java)

    def test_no_internet_permission_in_manifest(self):
        root=ET.fromstring(self.manifest)
        self.assertEqual(root.tag,"manifest")
        self.assertEqual(len(root.findall("uses-permission")),0)
        app=root.find("application")
        self.assertEqual(app.attrib["{http://schemas.android.com/apk/res/android}allowBackup"],"false")
        self.assertEqual(app.attrib["{http://schemas.android.com/apk/res/android}usesCleartextTraffic"],"false")

    def test_android_26_and_main_export_only(self):
        root=ET.fromstring(self.manifest)
        sdk=root.find('uses-sdk')
        self.assertEqual(sdk.attrib["{http://schemas.android.com/apk/res/android}minSdkVersion"],"26")
        activities=root.findall("application/activity")
        self.assertEqual(len(activities),1)
        self.assertEqual(activities[0].attrib["{http://schemas.android.com/apk/res/android}exported"],"true")

    def test_untrusted_change_to_upstream_pwa_rejected(self):
        with self.assertRaises(a.Blocked):
            a.compile_html(self.upstream+b"fetch('https://untrusted.example/')")

    def test_untrusted_change_to_archive_rejected(self):
        with self.assertRaises(a.Blocked):
            a.compile_html(self.upstream.replace(
              b"indexedDB.open('nexus-private-work-mode-mobile-v23',1)",
              b"indexedDB.open('evil',1)"))

    def test_change_to_export_function_rejected(self):
        with self.assertRaises(a.Blocked):
            a.compile_html(self.upstream.replace(
                a.ORIGINAL_DOWNLOAD.encode(),b"function download(){return true}"))

    def test_missing_reviewed_pwa_source_rejected(self):
        with self.assertRaises(a.Blocked):
            a.compile_html(self.upstream.replace(
                self.stage.MOBILE_SECTION.encode(),b"altered"))

    def test_bridge_is_only_native_js_interface(self):
        self.assertEqual(self.java.count("@JavascriptInterface"),1)
        self.assertEqual(self.java.count("webView.addJavascriptInterface("),1)
        self.assertIn('\"NEXUS_NATIVE_EXPORT\"',self.java)
        self.assertNotIn("android.permission.INTERNET",self.manifest.split("<!--")[0])

    def test_no_auto_privileged_audio_camera_or_background(self):
        for word in ("RECORD_AUDIO", "CAMERA", "ACCESS_FINE_LOCATION",
                     "FOREGROUND_SERVICE", "BOOT_COMPLETED", "READ_CONTACTS"):
            self.assertNotIn('android:name="'+word+'"',self.manifest)
        self.assertNotIn("getDeviceId(",self.java)

    def test_site_generates_only_exact_asset_set(self):
        self.assertEqual(set(a.produce(self.upstream)),{
            "nexus/index.html","mipmap-nodpi/ic_launcher.png",
            "nexus-stage25-input-integrity.json"})
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name,data in a.produce(self.upstream).items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            self.assertEqual((root/"nexus/index.html").read_bytes(),self.site)

if __name__=="__main__":
    unittest.main(verbosity=2)
