#!/usr/bin/env python3
"""Synthetic transport tests for the non-authoritative public auth watch."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("observe-stage-d-auth.sh").resolve()


class PublicAuthWatchTests(unittest.TestCase):
    def run_case(self, missing="401", wrong="401", missing_exit=0, wrong_exit=0,
                 base="https://example.invalid", expected=True):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            curl = work / "curl"
            curl.write_text('''#!/usr/bin/env python3
import os, sys
args = sys.argv
is_wrong = '-H' in args
status = os.environ['WRONG_STATUS'] if is_wrong else os.environ['MISSING_STATUS']
exit_code = int(os.environ['WRONG_EXIT'] if is_wrong else os.environ['MISSING_EXIT'])
print(status, end='')
sys.exit(exit_code)
''')
            curl.chmod(0o755)
            env = dict(os.environ,
                       PATH=str(work) + os.pathsep + os.environ["PATH"],
                       NEXUS_BASE_URL=base,
                       MISSING_STATUS=missing, WRONG_STATUS=wrong,
                       MISSING_EXIT=str(missing_exit), WRONG_EXIT=str(wrong_exit),
                       GITHUB_SHA="a" * 40)
            result = subprocess.run(["bash", str(SCRIPT)], cwd=work, env=env,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode == 0, expected,
                             result.stdout + result.stderr)
            if base != "https://example.invalid":
                self.assertFalse((work / "stage-d-public-auth-evidence.json").exists())
                return
            evidence = json.loads((work / "stage-d-public-auth-evidence.json").read_text())
            self.assertEqual(evidence["status"], "PASS" if expected else "FAIL")
            self.assertFalse(evidence["credentials_used"])
            self.assertFalse(evidence["proves_recovery"])
            self.assertFalse(evidence["proves_persistence"])
            self.assertTrue(all(x is False for x in evidence["mutation_scope"].values()))
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(evidence) + result.stdout + result.stderr)
            subprocess.run(["sha256sum", "-c", "stage-d-public-auth-evidence.sha256"],
                           cwd=work, check=True, capture_output=True)

    def test_unauthorized_requests_fail_closed(self):
        self.run_case()

    def test_all_transport_and_status_failures_are_evidence(self):
        for kwargs in [
            dict(missing="200"), dict(wrong="200"),
            dict(missing="302"), dict(wrong="404"),
            dict(missing="401", missing_exit=28),
            dict(wrong="401", wrong_exit=7),
            dict(missing="PRIVATE_SENTINEL"),
            dict(wrong="PRIVATE_SENTINEL"),
        ]:
            with self.subTest(kwargs=kwargs):
                self.run_case(expected=False, **kwargs)

    def test_reject_unsafe_url_before_network_request(self):
        for base in ["http://example.invalid", "https://name:secret@example.invalid",
                     "https://example.invalid/path", "https://example.invalid?secret=x",
                     "https://example.invalid:3000"]:
            with self.subTest(base=base):
                self.run_case(base=base, expected=False)


if __name__ == "__main__":
    unittest.main()
