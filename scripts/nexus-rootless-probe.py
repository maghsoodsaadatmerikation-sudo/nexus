#!/usr/bin/env python3
"""Operator-only rootless namespace proof, never an LLM-executable tool."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nexus-cloud'))
from agent_rootless_probe import run_probe
from agent_workspace import WorkspaceDenied


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--workspace', required=True)
    p.add_argument('--executable', required=True, help='Private regular static ELF (operator supplied)')
    p.add_argument('--sha256', required=True, help='Exact SHA-256 of reviewed executable')
    p.add_argument('--arg', action='append', default=[])
    p.add_argument('--timeout', type=int, default=6)
    p.add_argument('--approve-rootless', action='store_true', help='Independent operator approval')
    a = p.parse_args(argv)
    try:
        receipt = run_probe(a.root, a.workspace, a.executable, a.sha256,
                            args=a.arg, timeout=a.timeout, approved=a.approve_rootless)
        print(json.dumps(receipt, sort_keys=True))
        return 0 if receipt['status'] == 'complete' and receipt['exit_code'] == 0 else 2
    except (OSError, ValueError, WorkspaceDenied) as exc:
        print(json.dumps({'schema':'nexus.rootless-probe.v1','status':'denied',
                          'authority':'none','reason_type':type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
