#!/usr/bin/env python3
"""Explicit local NEXUS Studio-to-engineering handoff (NO remote shell)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
from agent_workspace import Workspace, WorkspaceDenied
from agent_chat_handoff import (parse_proposal, prepare, chat_receipt,
                                private_export_dir, write_export, shareable_json, read_operator_file)
from engineering_agent import execute_plan, parse_plan
from agent_journal import ApprovalJournal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "execute", "receipt"))
    parser.add_argument("--root", required=True, help="Operator-owned private workspace root")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--proposal", help="Untrusted model JSON proposal, prepare only")
    parser.add_argument("--plan", help="Private reviewed v3 plan, execute/receipt")
    parser.add_argument("--out", help="Owned private directory outside workspace root")
    parser.add_argument("--approve-digest", help="Exact SHA-256 of reviewed plan, execute only")
    args = parser.parse_args(argv)
    try:
        if args.action == "prepare":
            if not args.proposal or not args.out or args.plan or args.approve_digest:
                raise WorkspaceDenied("prepare-requires-proposal-and-out-only")
        elif args.action == "execute":
            if not args.plan or not args.approve_digest or not args.out or args.proposal:
                raise WorkspaceDenied("execute-requires-plan-approval-and-out-only")
        elif not args.plan or args.proposal or args.approve_digest or args.out:
            raise WorkspaceDenied("receipt-requires-plan-only")
        workspace = Workspace(args.root, args.workspace)
        if args.action == "prepare":
            out = private_export_dir(args.out, workspace)
            proposal = parse_proposal(read_operator_file(args.proposal))
            raw, review = prepare(workspace, proposal)
            digest = review["plan_sha256"]
            plan_path = write_export(out, f"nexus-plan-{digest[:16]}.json", raw)
            try:
                review_path = write_export(out, f"nexus-review-{digest[:16]}.txt", shareable_json(review))
            except BaseException:
                plan_path.unlink(missing_ok=True)
                raise
            print(json.dumps({"status": "prepared-not-executed", "plan_sha256": digest,
                              "private_plan": str(plan_path), "chat_review": str(review_path),
                              "requires_separate_exact_approval": True}))
            return 0
        raw_plan = read_operator_file(args.plan)
        plan, digest = parse_plan(raw_plan)
        if plan["version"] != 3 or plan["workspace"] != workspace.name:
            raise WorkspaceDenied("handoff-requires-reviewed-v3-plan")
        if args.action == "execute":
            if args.approve_digest != digest:
                raise WorkspaceDenied("exact-plan-approval-required")
            out = private_export_dir(args.out, workspace)
            receipt = execute_plan(workspace, plan, digest, approved_digest=args.approve_digest)
        with workspace.operation_lock():
            journal = ApprovalJournal(workspace).read(digest)
        summary = chat_receipt(journal)
        if args.action == "execute":
            output = write_export(out, f"nexus-result-{digest[:16]}.txt", shareable_json(summary))
            print(json.dumps({"status": receipt.status, "plan_sha256": digest,
                              "chat_result": str(output), "authority": "none"}))
            return 0 if receipt.status == "complete" else 1
        print(json.dumps(summary, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "warning": "Approval may be consumed and partial effects may remain; use receipt, never replay"}), file=sys.stderr)
        return 130
    except (OSError, WorkspaceDenied, ValueError, RecursionError) as exc:
        print(json.dumps({"status": "denied", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
