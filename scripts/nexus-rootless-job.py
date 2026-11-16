#!/usr/bin/env python3
"""Local rootless job: prepare, inspect, approve exact digest, stop, and status.

The operator server must be started separately with --enable-rootless-probe.
No remote HTTP/API, no browser authorization, and no agent-provided privileges.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nexus-cloud'))

from agent_chat_handoff import private_export_dir, write_export
from agent_operator_service import client
from agent_rootless_job import prepare_job
from agent_workspace import Workspace, WorkspaceDenied


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'review', 'start', 'stop', 'status'))
    p.add_argument('--root', required=True, help='Operator-owned absolute private 0700 root')
    p.add_argument('--workspace', required=True)
    p.add_argument('--digest', help='Separately reviewed canonical job-plan SHA256')
    p.add_argument('--plan', help='Full private 0600 operator job plan for review/start')
    p.add_argument('--executable', help='Private statically linked ELF for prepare')
    p.add_argument('--sha256', help='Exact reviewed executable SHA256 for prepare')
    p.add_argument('--out', help='Owner-only 0700 plan export folder for prepare')
    p.add_argument('--timeout', type=int, default=6)
    p.add_argument('--arg', action='append', default=[], help='One literal guest argument')
    a = p.parse_args(argv)
    try:
        if a.action == 'prepare':
            if a.digest or a.plan or not a.executable or not a.sha256 or not a.out:
                raise WorkspaceDenied('rootless-prepare-arguments')
            ws = Workspace(a.root, a.workspace)
            out = private_export_dir(a.out, ws)
            raw, review = prepare_job(ws, a.executable, a.sha256,
                                      argv=a.arg, timeout_seconds=a.timeout)
            path = write_export(out, f"nexus-plan-{review['plan_sha256'][:16]}.json", raw)
            print(json.dumps({'status': 'prepared-not-approved', 'private_plan': str(path),
                              'plan_sha256': review['plan_sha256'],
                              'workspace_sha256': review['workspace_sha256'],
                              'authority': 'none'}))
            return 0
        if a.executable or a.sha256 or a.out or a.arg or a.timeout != 6 or not a.digest or bool(a.plan) != (a.action in ('review', 'start')):
            raise WorkspaceDenied('rootless-job-arguments')
        result = client(a.root, workspace=a.workspace, digest=a.digest,
                        action='probe-' + a.action, plan_path=a.plan)
        if result.get('status') in ('review', 'receipt'):
            print(json.dumps(result['summary'] if result['status'] == 'review'
                             else {k: v for k, v in result.items() if k != 'status'},
                             sort_keys=True))
            return 0
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get('status') in ('submitted-not-verified', 'stop-requested-not-confirmed',
                                              'queued-not-verified') else 2
    except (OSError, ValueError, WorkspaceDenied) as exc:
        print(json.dumps({'status': 'denied', 'reason': type(exc).__name__,
                          'authority': 'none'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
