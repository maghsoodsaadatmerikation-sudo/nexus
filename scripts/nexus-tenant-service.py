#!/usr/bin/env python3
"""Tenant-scoped operator service; host must provision UID + cgroup first.

NO user switching, sudo, HTTP, browser bridge or agent-controlled capability.
If the machine lacks required quotas/NNP, this service refuses to start.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nexus-cloud'))
from agent_operator_service import OperatorServer
from agent_tenant_boundary import harden_tenant_daemon
from agent_workspace import WorkspaceDenied


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    a = p.parse_args(argv)
    try:
        report = harden_tenant_daemon(a.root)
        with OperatorServer(a.root, allow_container=False) as daemon:
            print(json.dumps({'status': 'tenant-local-ready',
                              'transport': 'private-unix-socket',
                              'isolation': report['isolation'],
                              'authority': 'operator-only'}), flush=True)
            try:
                daemon.serve_forever(poll_interval=0.1)
            except KeyboardInterrupt:
                pass
        return 0
    except (OSError, WorkspaceDenied, ValueError):
        print(json.dumps({'status': 'denied-host-not-isolated',
                          'authority': 'none'}), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
