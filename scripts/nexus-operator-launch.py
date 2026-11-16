#!/usr/bin/env python3
"""NEXUS installed-operator gate: verify all installed bytes before any action.

Only doctor/check and explicitly approved disposable smoke are supported.
No HTTP, Docker socket, arbitrary plan, model or public server is exposed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

SCHEMA = 'nexus.operator.launch.v1'
MAX_OUTPUT = 16_384


def _fail(reason: str) -> int:
    print(json.dumps({'schema': SCHEMA, 'status': 'denied', 'reason': reason,
                      'production_ready': False, 'authority': 'none'},
                     sort_keys=True), file=sys.stderr)
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('doctor', 'check', 'smoke'))
    ap.add_argument('--root', help='Existing 0700 operator root for check only')
    ap.add_argument('--workspace', help='Existing workspace for check only')
    ap.add_argument('--inspect-docker', action='store_true',
                    help='Read-only, no host attestation')
    ap.add_argument('--approve-disposable', action='store_true',
                    help='Explicit permission for a fixed synthetic disposable smoke only')
    ap.add_argument('--expected-manifest-sha256',
                    help='Out-of-band SHA-256 anchor for the installed manifest (not a signature)')
    args = ap.parse_args(argv)
    if args.action == 'doctor':
        if args.root or args.workspace or args.inspect_docker or args.approve_disposable:
            return _fail('invalid-doctor-options')
    elif args.action == 'check':
        if not args.root or args.approve_disposable:
            return _fail('invalid-check-options')
    elif args.root or args.workspace or args.inspect_docker or not args.approve_disposable:
        return _fail('smoke-needs-explicit-disposable-consent')
    if (os.name != 'posix' or not sys.platform.startswith('linux') or
            os.getuid() == 0 or sys.version_info < (3, 13)):
        return _fail('requires-unprivileged-linux-python-313')
    installation = Path(__file__).resolve().parents[1]
    # Import only the standard-library distribution verifier; it verifies its
    # own bytes as well. This is NOT a publisher signature or same-UID defense.
    path = installation / 'scripts' / 'nexus-operator-distribution.py'
    try:
        spec = importlib.util.spec_from_file_location('nexus_distribution', path)
        if spec is None or spec.loader is None:
            return _fail('distribution-verifier-unavailable')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        verification = module.installed_verify(
            installation, expected_manifest_sha256=args.expected_manifest_sha256)
    except (OSError, ValueError, ImportError, RecursionError, RuntimeError):
        return _fail('installed-integrity-unverifiable')
    if verification.get('status') != 'installed-integrity-verified':
        return _fail('installed-integrity-unverifiable')
    if args.action == 'doctor':
        print(json.dumps({'schema': SCHEMA, 'status': 'installed-pilot-ready-not-attested',
                          'installed_files_verified': verification['file_count'],
                          'python_compatible': True, 'operator_unprivileged': True,
                          'publisher_authenticated': False,
                          'manifest_anchor_matched': verification['manifest_anchor_matched'],
                          'manifest_sha256': verification['manifest_sha256'],
                          'production_ready': False, 'authority': 'none',
                          'execution_performed': False}, sort_keys=True))
        return 0
    cmd = [sys.executable, '-I', '-B', str(installation / 'scripts' / 'nexus-operator-pilot.py')]
    if args.action == 'check':
        cmd.extend(('check', '--root', args.root))
        if args.workspace:
            cmd.extend(('--workspace', args.workspace))
        if args.inspect_docker:
            cmd.append('--inspect-docker')
    else:
        cmd.extend(('smoke', '--approve-disposable'))
    try:
        result = subprocess.run(cmd, cwd=installation, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=30,
                                env={'PATH': '/usr/bin:/bin',
                                     'PYTHONDONTWRITEBYTECODE': '1'}, check=False)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return _fail('operator-probe-unverifiable')
    if result.returncode not in (0, 2) or len(result.stdout) > MAX_OUTPUT:
        return _fail('operator-probe-unverifiable')
    if result.returncode == 2:
        return _fail('operator-probe-denied')
    try:
        response = json.loads(result.stdout)
    except (UnicodeError, ValueError):
        return _fail('operator-probe-unverifiable')
    if (not isinstance(response, dict) or response.get('authority') != 'none'
            or response.get('production_ready') is not False or
            response.get('schema') not in ('nexus.operator.pilot-acceptance.v1',)):
        return _fail('operator-probe-unverifiable')
    if args.action == 'smoke' and response.get('status') != 'disposable-operator-cycle-passed':
        return _fail('synthetic-smoke-not-confirmed')
    if args.action == 'check' and response.get('status') != 'preflight-clear-not-attested':
        return _fail('operator-check-not-clear')
    print(json.dumps({'schema': SCHEMA, 'status': ('disposable-smoke-passed' if
                     args.action == 'smoke' else 'preflight-clear-not-attested'),
                      'result': response, 'authority': 'none',
                      'manifest_anchor_matched': verification['manifest_anchor_matched'],
                      'manifest_sha256': verification['manifest_sha256'],
                      'production_ready': False, 'host_attested': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
