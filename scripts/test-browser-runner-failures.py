#!/usr/bin/env python3
"""Linux synthetic child-process failures; no Chrome or external service used."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNNER = Path(__file__).with_name('workspace-browser-runner.mjs')


class BrowserRunnerFailures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profile = self.root / 'private-profile'

    def run_driver(self, browser, timeout=8):
        return subprocess.run(['node', str(RUNNER), str(browser),
            'file:///synthetic-private-page', str(self.profile), '500,1100'],
            capture_output=True, text=True, timeout=timeout)

    def diagnostic(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        value = json.loads(result.stderr.splitlines()[0])
        self.assertEqual(value['event'], 'browser-witness-failure')
        self.assertEqual(value['stage'], 'devtools-port')
        self.assertEqual(value['authority'], 'none')
        self.assertIs(value['production_verified'], False)
        self.assertNotIn(str(self.root), result.stderr)
        self.assertNotIn('synthetic-private-page', result.stderr)
        self.assertNotIn('SECRET_BROWSER_STDERR', result.stderr)
        return value

    def test_missing_executable_finishes_without_waiting_for_exit(self):
        # The old cleanup always waited three seconds for a nonexistent child.
        value = self.diagnostic(self.run_driver(self.root / 'absent', timeout=2.5))
        self.assertIs(value['launch_failed'], True)

    def test_immediate_child_exit_is_failure_and_stderr_is_not_forwarded(self):
        browser = self.root / 'exit-browser'
        browser.write_text('#!/bin/sh\necho SECRET_BROWSER_STDERR >&2\nexit 0\n')
        browser.chmod(0o700)
        value = self.diagnostic(self.run_driver(browser))
        self.assertIs(value['process_exited'], True)
        self.assertIs(value['launch_failed'], False)

    def test_existing_profile_is_refused_without_launch(self):
        self.profile.mkdir()
        sentinel = self.profile / 'sentinel'
        sentinel.write_text('unchanged')
        browser = self.root / 'must-not-launch'
        marker = self.root / 'launched'
        browser.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        browser.chmod(0o700)
        result = self.run_driver(browser)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertFalse(marker.exists())
        self.assertEqual(sentinel.read_text(), 'unchanged')

    def test_missing_port_times_out_and_terminates_owned_child(self):
        browser = self.root / 'sleep-browser'
        pidfile = self.root / 'owned-pid'
        browser.write_text('#!/bin/sh\necho $$ > "' + str(pidfile) + '"\nexec sleep 60\n')
        browser.chmod(0o700)
        result = self.run_driver(browser, timeout=20)
        value = self.diagnostic(result)
        self.assertIs(value['process_exited'], False)
        self.assertGreaterEqual(value['elapsed_ms'], 9900)
        self.assertLess(value['elapsed_ms'], 15000)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pidfile.read_text()), 0)


if __name__ == '__main__':
    unittest.main()
