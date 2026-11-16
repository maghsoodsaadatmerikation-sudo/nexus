#!/usr/bin/env python3
"""NEXUS operator: inspect local barriers or run a fixed disposable smoke test.

check: local non-authorizing snapshot (no workspace creation).
smoke: real owner-only socket/journal roundtrip, explicitly approved and disposable.
Never deploys or exposes a browser, model or public execution endpoint.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))

from agent_operator_pilot import readiness_snapshot, synthetic_smoke
from agent_workspace import WorkspaceDenied


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "smoke"))
    parser.add_argument("--root", help="Existing absolute 0700 local operator root (check only)")
    parser.add_argument("--workspace", help="Existing workspace to verify without creating")
    parser.add_argument("--inspect-docker", action="store_true",
                        help="Read-only labelled Docker inventory; not daemon attestation")
    parser.add_argument("--approve-disposable", action="store_true",
                        help="Explicitly allow a fixed synthetic plan in a temporary root")
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            if not args.root or args.approve_disposable:
                raise WorkspaceDenied("pilot-check-options")
            result = readiness_snapshot(args.root, workspace=args.workspace,
                                        inspect_docker=args.inspect_docker)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["status"] == "preflight-clear-not-attested" else 2
        if (args.root or args.workspace or args.inspect_docker
                or not args.approve_disposable):
            raise WorkspaceDenied("pilot-smoke-options")
        result = synthetic_smoke(approved=True)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, WorkspaceDenied, ValueError) as exc:
        # Do not echo private paths, tokens, source code, stack traces or text.
        print(json.dumps({"status": "denied", "reason": type(exc).__name__,
                          "authority": "none", "production_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
