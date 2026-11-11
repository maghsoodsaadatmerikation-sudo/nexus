#!/usr/bin/env python3
"""No-credential regression: secret allowlisting across provider subprocesses."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from private_subprocess_env import RAILWAY_CREDENTIAL_KEYS, child_env


class ScopedChildEnvironmentTests(unittest.TestCase):
    def test_only_download_inherits_the_two_explicit_railway_auth_values(self):
        credentials = {
            "RAILWAY_TOKEN": "synthetic-provider-secret",
            "RAILWAY_API_TOKEN": "synthetic-api-provider-secret",
            "GITHUB_TOKEN": "synthetic-ci-secret",
            "RENDER_API_KEY": "synthetic-render-secret",
            "NEXUS_API_TOKEN": "synthetic-app-secret",
            "UNRELATED_PRIVATE_SECRET": "synthetic-personal-secret",
            "AWS_SECRET_ACCESS_KEY": "synthetic-cloud-secret",
            "PYTHONPATH": "/synthetic/private/python",
            "HTTPS_PROXY": "http://synthetic-private-proxy",
        }
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, credentials):
            help_env = child_env()
            download_env = child_env(railway_download=True)
            validator_env = child_env(private_home=Path(root))

        for key, value in credentials.items():
            if key in RAILWAY_CREDENTIAL_KEYS:
                self.assertNotIn(key, help_env)
                self.assertEqual(download_env[key], value)
                self.assertNotIn(key, validator_env)
            else:
                for stage in (help_env, download_env, validator_env):
                    self.assertNotIn(key, stage)
        self.assertEqual(validator_env["HOME"], root)
        self.assertTrue(help_env["RAILWAY_NO_AUTO_UPDATE"] == "1")
        self.assertEqual(set(download_env) - set(help_env), set(RAILWAY_CREDENTIAL_KEYS))
        self.assertEqual(set(validator_env), set(help_env))

    def test_absent_railway_credentials_are_never_invented(self):
        with patch.dict(os.environ, {}, clear=True):
            allowed = child_env(railway_download=True)
        self.assertFalse(set(allowed) & set(RAILWAY_CREDENTIAL_KEYS))
        self.assertFalse(allowed.get("PYTHONPATH"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
