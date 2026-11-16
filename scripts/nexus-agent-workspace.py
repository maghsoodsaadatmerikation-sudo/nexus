#!/usr/bin/env python3
"""Operator-only entrypoint. No public HTTP route and no automatic model calls."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nexus-cloud"))
from agent_workspace import Workspace, WorkspaceDenied, run_container
from agent_research import ResearchDenied, fetch_metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description="NEXUS opt-in local engineering workspace")
    parser.add_argument("--root", required=True, help="absolute private existing directory (chmod 700)")
    parser.add_argument("--workspace", required=True, help="single safe workspace ID")
    operations = parser.add_subparsers(dest="operation", required=True)
    read = operations.add_parser("read")
    read.add_argument("path")
    write = operations.add_parser("write")
    write.add_argument("path")
    write.add_argument("--from-file", required=True)
    write.add_argument("--create-parents", action="store_true")
    edit = operations.add_parser("edit")
    edit.add_argument("path")
    edit.add_argument("--old-file", required=True)
    edit.add_argument("--new-file", required=True)
    preview = operations.add_parser("preview-edit", help="Review an exact edit before applying it")
    preview.add_argument("path")
    preview.add_argument("--old-file", required=True)
    preview.add_argument("--new-file", required=True)
    search = operations.add_parser("search", help="Search bounded UTF-8 files, without regex or execution")
    search.add_argument("query")
    search.add_argument("--case-sensitive", action="store_true")
    research = operations.add_parser("research", help="Query one fixed public developer metadata provider")
    research.add_argument("--provider", choices=["pypi", "crates", "github-release"], required=True)
    research.add_argument("--name", required=True)
    research.add_argument("--approve-research", action="store_true")
    operations.add_parser("manifest", help="List bounded files and current content identity (no mutation)")
    package = operations.add_parser("package")
    package.add_argument("--output", required=True)
    run = operations.add_parser("run")
    run.add_argument("--image", required=True)
    run.add_argument("--approve-run", action="store_true")
    run.add_argument("--timeout", type=int, default=30)
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        workspace = Workspace(args.root, args.workspace)
        with workspace.operation_lock():
            if args.operation == "read":
                sys.stdout.buffer.write(workspace.read(args.path))
            elif args.operation == "write":
                workspace.write(args.path, Path(args.from_file).read_bytes(), create_parents=args.create_parents)
                print(json.dumps({"status": "written", "path": args.path}))
            elif args.operation == "edit":
                workspace.edit(args.path, Path(args.old_file).read_bytes(), Path(args.new_file).read_bytes())
                print(json.dumps({"status": "edited", "path": args.path}))
            elif args.operation == "preview-edit":
                print(json.dumps(workspace.preview_edit(args.path, Path(args.old_file).read_bytes(), Path(args.new_file).read_bytes())))
            elif args.operation == "search":
                print(json.dumps(workspace.search(args.query, case_sensitive=args.case_sensitive), ensure_ascii=False))
            elif args.operation == "research":
                if not args.approve_research:
                    raise ResearchDenied("research-requires-explicit-approval")
                print(json.dumps(fetch_metadata(args.provider, args.name)))
            elif args.operation == "manifest":
                print(json.dumps(workspace.manifest(), ensure_ascii=False))
            elif args.operation == "package":
                print(json.dumps(workspace.package(args.output)))
            elif args.operation == "run":
                command = args.command[1:] if args.command[:1] == ["--"] else args.command
                result = run_container(workspace, args.image, command,
                                       approved=args.approve_run, timeout_seconds=args.timeout)
                print(json.dumps(result.__dict__))
                return 0 if result.status == "complete" and result.exit_code == 0 else 1
    except (WorkspaceDenied, ResearchDenied, OSError, ValueError) as exc:
        print(json.dumps({"status": "denied", "reason": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
