#!/usr/bin/env python3
"""Explicit preview + exact-hash consent for bounded engineering tool sequences."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
from agent_workspace import Workspace, WorkspaceDenied
from engineering_agent import execute_plan, parse_plan


def main():
    parser = argparse.ArgumentParser(description="Review-bound NEXUS engineering plan")
    parser.add_argument("--root", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--approve-digest", default="")
    args = parser.parse_args()
    try:
        plan, digest = parse_plan(Path(args.plan).read_bytes())
        preview = {"plan_sha256": digest, "workspace": plan["workspace"],
                   "tools": [step["tool"] for step in plan["steps"]],
                   "network": "disabled", "status": "awaiting-approval"}
        if not args.approve_digest:
            print(json.dumps(preview))
            return 0
        workspace = Workspace(args.root, plan["workspace"])
        receipt = execute_plan(workspace, plan, digest, approved_digest=args.approve_digest)
        print(json.dumps(asdict(receipt)))
        return 0 if receipt.status == "complete" else 1
    except (OSError, WorkspaceDenied, ValueError) as exc:
        print(json.dumps({"status": "denied", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
