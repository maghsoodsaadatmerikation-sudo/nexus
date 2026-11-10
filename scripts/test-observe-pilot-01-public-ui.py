#!/usr/bin/env python3
"""No-network contract tests for historical/public UI revision classification."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).with_name("observe-pilot-01-public-ui.py")
spec = importlib.util.spec_from_file_location("pilot_01_public_ui", SCRIPT)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

LEGACY = (b'<title>NEXUS old</title><input id="token">'
          b'<button onclick="createWorkspace()">Create</button>'
          b'<button onclick="recordJudgment()">Decide</button>'
          b'<button onclick="backupWorkspace()">Export</button>')
CURRENT = LEGACY.replace(b'NEXUS old', b'NEXUS new') + b'<button id="readinessButton"></button>'


class PilotUIClassificationTests(unittest.TestCase):
    def test_exact_legacy_pinned_html_is_recognized(self):
        self.assertEqual(observer.inspect_page(LEGACY, LEGACY, CURRENT), "OLDER_PINNED_UI")

    def test_exact_current_pinned_html_is_recognized(self):
        self.assertEqual(observer.inspect_page(CURRENT, CURRENT, CURRENT), "CURRENT_MAIN_UI")

    def test_mismatched_runtime_html_fails_closed(self):
        self.assertEqual(observer.inspect_page(CURRENT, LEGACY, CURRENT), "PINNED_UI_MISMATCH")

    def test_invalid_exact_html_fails_closed(self):
        self.assertEqual(observer.inspect_page(b"<title>NEXUS</title>", b"<title>NEXUS</title>", CURRENT),
                         "UNRECOGNIZED_UI")

    def test_oversized_html_fails_closed(self):
        huge = LEGACY + b" " * (observer.LIMIT + 1)
        self.assertEqual(observer.inspect_page(huge, huge, CURRENT), "BODY_OVERSIZE")


if __name__ == "__main__":
    unittest.main()
