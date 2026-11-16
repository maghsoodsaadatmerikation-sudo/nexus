#!/usr/bin/env python3
"""Local NEXUS engineering plan service; NOT accessible to browsers/HTTP."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
from agent_operator_service import OperatorServer, client
from agent_workspace import Workspace, WorkspaceDenied
from agent_chat_handoff import private_export_dir, shareable_json, write_export


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("serve", "review", "start", "stop", "status"))
    ap.add_argument("--root", required=True, help="Absolute operator-owned 0700 workspace root")
    ap.add_argument("--enable-rootless-probe", action="store_true",
                    help="Explicit single-owner server opt-in for rootless proof jobs, never tenant mode")
    ap.add_argument("--workspace", help="Workspace name for start/stop/status")
    ap.add_argument("--digest", help="Exact canonical SHA-256 of a separately reviewed v3 plan")
    ap.add_argument("--plan", help="Private 0600 v3 plan from operator's export folder")
    ap.add_argument("--out", help="Private 0700 folder to export a sanitized review or receipt for Studio")
    a = ap.parse_args()
    try:
        if a.action == "serve":
            if a.workspace or a.digest or a.plan or a.out:
                raise WorkspaceDenied("serve-has-no-plan-arguments")
            with OperatorServer(a.root, allow_rootless=a.enable_rootless_probe) as server:
                # Keep this private owner terminal attached; do not background
                # execution, create a public endpoint or expose the session token.
                print(json.dumps({"status": "operator-local-ready", "transport": "private-unix-socket", "authority": "operator-only", "rootless_probe_opt_in": a.enable_rootless_probe}),flush=True)
                try:
                    server.serve_forever(poll_interval=0.1)
                except KeyboardInterrupt:
                    pass
            return 0
        if a.enable_rootless_probe:
            raise WorkspaceDenied("rootless-opt-in-server-only")
        if not a.workspace or not a.digest or bool(a.plan) != (a.action in ("review", "start")) or (a.out and a.action not in ("status", "review")):
            raise WorkspaceDenied("command-arguments")
        result = client(a.root, workspace=a.workspace, digest=a.digest, action=a.action, plan_path=a.plan)
        if result.get("status") in ("receipt", "review"):
            review_only = result["status"] == "review"
            summary = result["summary"] if review_only else {k: v for k, v in result.items() if k != "status"}
            if a.out:
                ws = Workspace(a.root, a.workspace)
                out = private_export_dir(a.out, ws)
                kind = "review" if review_only else "result"
                path = write_export(out, f"nexus-{kind}-{a.digest[:16]}.txt", shareable_json(summary))
                response = {"status": "exported", "chat_" + kind: str(path), "authority": "none"}
                if not review_only:
                    response["execution_status"] = summary["execution_status"]
                print(json.dumps(response))
            else:
                # Exact strict Studio schema; no transport status or raw plan.
                print(json.dumps(summary, sort_keys=True))
            return 0
        if a.out:
            raise WorkspaceDenied("cannot-export-unverified-status")
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("status") not in ("denied", "unverifiable", "not-found", "busy", "already-consumed", "stale-plan-reapproval-required") else 2
    except (OSError, ValueError, WorkspaceDenied) as exc:
        print(json.dumps({"status": "denied", "reason": type(exc).__name__}), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
