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
        # Preview remains nonmutating with respect to project files; creating a
        # dedicated empty workspace is the same behavior as the execution path.
        workspace = Workspace(args.root, plan["workspace"])
        observed = workspace.manifest()
        matches = (plan["version"] != 2 or observed["sha256"] == plan["expected_workspace_sha256"])
        preview = {"plan_sha256": digest, "plan_version": plan["version"],
                   "workspace": plan["workspace"], "current_workspace_sha256": observed["sha256"],
                   "state_matches": matches, "tools": [step["tool"] for step in plan["steps"]],
                   "network": "fixed-provider-metadata-only" if "research" in [step["tool"] for step in plan["steps"]] else "disabled", "status": "awaiting-approval" if matches else "state-mismatch"}
        if not args.approve_digest:
            print(json.dumps(preview))
            return 0
        receipt = execute_plan(workspace, plan, digest, approved_digest=args.approve_digest)
        print(json.dumps(asdict(receipt)))
        return 0 if receipt.status == "complete" else 1
    except (OSError, WorkspaceDenied, ValueError) as exc:
        print(json.dumps({"status": "denied", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
