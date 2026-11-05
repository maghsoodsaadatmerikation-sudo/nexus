#!/usr/bin/env python3
"""Exercise actual shell observer with a bounded synthetic curl transport."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("observe-runtime-drift.sh").resolve()
DIGEST = "d" * 64
VALID = {"schema": "nexus.runtime-identity.v1", "authority": "non_authoritative_build_metadata", "source_tree_sha256": DIGEST}

class ObservationTests(unittest.TestCase):
    def observe(self, body, code="200", transport=0, passed=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            curl = root / "curl"
            curl.write_text('#!/usr/bin/env python3\nimport os,sys\na=sys.argv\nopen(a[a.index("--output")+1],"w").write(os.environ["BODY"])\nprint(os.environ["CODE"],end="")\nsys.exit(int(os.environ["TRANSPORT"]))\n')
            curl.chmod(0o755)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], URL="https://example.invalid/v1/runtime-identity", EXPECTED_DIGEST=DIGEST, BODY=body, CODE=code, TRANSPORT=str(transport), GITHUB_SHA="a"*40)
            result = subprocess.run(["bash", str(SCRIPT)], cwd=tmp, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0 if passed else 1, result.stderr)
            evidence = json.loads((root / "v1.9-runtime-drift-evidence.json").read_text())
            self.assertEqual(evidence["status"], "PASS" if passed else "FAIL")
            self.assertTrue(all(v is False for v in evidence["mutation_scope"].values()))
            self.assertNotIn("PRIVATE_SENTINEL", result.stdout + result.stderr + json.dumps(evidence))
            subprocess.run(["sha256sum", "-c", "v1.9-runtime-drift-evidence.sha256"], cwd=tmp, check=True, capture_output=True)
            return evidence

    def test_exact_identity_passes(self):
        self.observe(json.dumps(VALID), passed=True)

    def test_failures_still_emit_evidence(self):
        cases = [
            ("", "000", 28),
            (json.dumps(VALID), "200", 28),
            ('{"secret":"PRIVATE_SENTINEL"}', "503", 0),
            ("PRIVATE_SENTINEL", "200", 0),
            ("[]", "200", 0),
            (json.dumps(VALID) + json.dumps(VALID), "200", 0),
            (json.dumps(dict(VALID, schema="PRIVATE_SENTINEL")), "200", 0),
            (json.dumps(dict(VALID, authority="PRIVATE_SENTINEL")), "200", 0),
            (json.dumps(dict(VALID, source_tree_sha256="e"*64)), "200", 0),
            (json.dumps(dict(VALID, source_tree_sha256="PRIVATE_SENTINEL")), "200", 0),
        ]
        for body, code, transport in cases:
            with self.subTest(code=code, transport=transport, body=body):
                self.observe(body, code, transport)

if __name__ == "__main__":
    unittest.main()
