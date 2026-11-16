#!/usr/bin/env python3
"""Independent, read-only host gate for 2+ already-running NEXUS tenants.

Root is allowed only for this *audit*; root MUST NOT start the operator daemon.
No tenant credentials are read, exported or used for actions.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nexus-cloud'))
from agent_tenant_boundary import audit_tenants
from agent_workspace import WorkspaceDenied


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tenant', action='append', required=True, metavar='PRIVATE_ROOT:PID')
    a = p.parse_args(argv)
    try:
        if os.geteuid() != 0:
            raise WorkspaceDenied('tenant-host-auditor-requires-root-read-only')
        values = []
        for entry in a.tenant:
            root, sep, pid = entry.rpartition(':')
            if not sep or not pid.isdecimal() or not root:
                raise WorkspaceDenied('tenant-invalid-argument')
            values.append((root, int(pid)))
        report = audit_tenants(values)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, WorkspaceDenied):
        print(json.dumps({'schema': 'nexus.tenant-boundary.audit.v1',
                          'status': 'FAIL_CLOSED', 'authority': 'none',
                          'production_attested': False}))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
