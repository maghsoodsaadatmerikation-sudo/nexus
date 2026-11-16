"""Review-bound, deterministic multi-step engineering plan; no LLM tool authority.

Plan review is separate from execution. Plan bytes are hashed in a canonical form;
any change requires a new approval. Evidence is a receipt, not a verification seal.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_workspace import (IMAGE_DIGEST, MAX_FILE_BYTES, Workspace, WorkspaceDenied,
                             run_container, safe_parts)
from agent_research import ResearchDenied, endpoint, fetch_metadata
from agent_journal import ApprovalJournal

MAX_PLAN_BYTES = 32_768
MAX_STEPS = 12
TOOLS = frozenset(("read", "write", "edit", "run", "verify_sha256", "package",
                   "search", "preview_edit", "research"))
HASH = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise WorkspaceDenied("invalid-text")
    try:
        encoded_size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise WorkspaceDenied("invalid-text-encoding") from exc
    if encoded_size > MAX_FILE_BYTES:
        raise WorkspaceDenied("invalid-text")
    return value


def parse_plan(raw: bytes) -> tuple[dict[str, Any], str]:
    if not isinstance(raw, bytes) or len(raw) > MAX_PLAN_BYTES:
        raise WorkspaceDenied("plan-size")
    def strict_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WorkspaceDenied("duplicate-plan-key")
            result[key] = value
        return result
    try:
        plan = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(WorkspaceDenied("invalid-plan-number")))
    except WorkspaceDenied:
        raise
    except (UnicodeError, ValueError) as exc:
        raise WorkspaceDenied("plan-json") from exc
    if not isinstance(plan, dict) or type(plan.get("version")) is not int or plan["version"] not in (1, 2, 3):
        raise WorkspaceDenied("plan-schema")
    expected_keys = {"version", "workspace", "steps"}
    if plan["version"] in (2, 3):
        expected_keys.add("expected_workspace_sha256")
    if plan["version"] == 3:
        expected_keys.add("execution_nonce")
    if set(plan) != expected_keys:
        raise WorkspaceDenied("plan-schema")
    if plan["version"] in (2, 3) and (not isinstance(plan["expected_workspace_sha256"], str)
                                  or not HASH.fullmatch(plan["expected_workspace_sha256"])):
        raise WorkspaceDenied("plan-workspace-state")
    if plan["version"] == 3 and (not isinstance(plan["execution_nonce"], str)
                                  or not re.fullmatch(r"[0-9a-f]{32}", plan["execution_nonce"])):
        raise WorkspaceDenied("invalid-execution-nonce")
    if not isinstance(plan["workspace"], str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}", plan["workspace"]):
        raise WorkspaceDenied("plan-workspace")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise WorkspaceDenied("plan-step-count")
    shapes = {
        "read": {"tool", "path"},
        "write": {"tool", "path", "text"},
        "edit": {"tool", "path", "before", "after"},
        "run": {"tool", "image", "argv", "timeout_seconds"},
        "verify_sha256": {"tool", "path", "expected_sha256"},
        "package": {"tool", "output"},
        "search": {"tool", "query", "case_sensitive"},
        "preview_edit": {"tool", "path", "before", "after"},
        "research": {"tool", "provider", "name"},
    }
    for step in steps:
        if not isinstance(step, dict) or step.get("tool") not in TOOLS or set(step) != shapes[step["tool"]]:
            raise WorkspaceDenied("plan-step-schema")
        tool = step["tool"]
        if "path" in step:
            safe_parts(step["path"])
        if tool == "write":
            _text(step["text"], allow_empty=True)
        if tool in ("edit", "preview_edit"):
            _text(step["before"])
            _text(step["after"], allow_empty=True)
        if tool == "search":
            query = step["query"]
            if not isinstance(query, str) or not query or len(query) > 128 or any(c in query for c in ("\x00", "\r", "\n")) or type(step["case_sensitive"]) is not bool:
                raise WorkspaceDenied("invalid-search-query")
        if tool == "research":
            endpoint(step["provider"], step["name"])
        if tool == "run":
            if not isinstance(step["image"], str) or not IMAGE_DIGEST.fullmatch(step["image"]):
                raise WorkspaceDenied("plan-image-digest")
            argv = step["argv"]
            if not isinstance(argv, list) or not 1 <= len(argv) <= 64 or any(not isinstance(x, str) or not x or "\x00" in x for x in argv) or sum(len(x.encode("utf-8")) for x in argv) > 16_384:
                raise WorkspaceDenied("plan-argv")
            if type(step["timeout_seconds"]) is not int or not 1 <= step["timeout_seconds"] <= 120:
                raise WorkspaceDenied("plan-timeout")
        if tool == "verify_sha256" and (not isinstance(step["expected_sha256"], str) or not HASH.fullmatch(step["expected_sha256"])):
            raise WorkspaceDenied("plan-expected-hash")
        if tool == "package" and (not isinstance(step["output"], str) or not Path(step["output"]).is_absolute()):
            raise WorkspaceDenied("plan-package-output")
    try:
        canonical = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except UnicodeError as exc:
        raise WorkspaceDenied("invalid-plan-encoding") from exc
    return plan, hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class PlanReceipt:
    plan_sha256: str
    status: str
    completed_steps: int
    results: tuple[dict[str, Any], ...]
    authority: str = "operator-reviewed-only"
    workspace_sha256_before: str = ""
    workspace_sha256_after: str | None = None


def execute_plan(workspace: Workspace, plan: dict[str, Any], digest: str, *, approved_digest: str, cancel_event=None) -> PlanReceipt:
    if not isinstance(approved_digest, str) or approved_digest != digest or not HASH.fullmatch(digest):
        raise WorkspaceDenied("exact-plan-approval-required")
    try:
        serialized = json.dumps(plan, ensure_ascii=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise WorkspaceDenied("invalid-plan-encoding") from exc
    checked, actual_digest = parse_plan(serialized)
    if actual_digest != digest or checked["workspace"] != workspace.name:
        raise WorkspaceDenied("plan-changed-or-wrong-workspace")
    with workspace.operation_lock():
        # Versions 2 and 3 couple the approved plan to the entire workspace.
        # The check occurs before the first mutation or executable command.
        if checked["version"] in (2, 3):
            observed = workspace.manifest()["sha256"]
            if observed != checked["expected_workspace_sha256"]:
                raise WorkspaceDenied("workspace-state-changed-reapproval-required")
        workspace_sha256_before = workspace.manifest()["sha256"]
        journal = ApprovalJournal(workspace)
        # Crash-safe single-use approval is consumed before any side effects.
        # An interrupted process leaves a STARTED record, never safe to retry.
        journal.claim(digest, version=checked["version"],
                      workspace_before=workspace_sha256_before,
                      execution_nonce=checked.get("execution_nonce"))
        results: list[dict[str, Any]] = []
        status = "complete"
        for index, step in enumerate(checked["steps"]):
            if cancel_event is not None and cancel_event.is_set():
                status = "cancelled"
                break
            tool = step["tool"]
            try:
                if tool == "write":
                    workspace.write(step["path"], step["text"].encode(), create_parents=True)
                    item = {"index": index, "tool": tool, "sha256": hashlib.sha256(workspace.read(step["path"])).hexdigest()}
                elif tool == "edit":
                    workspace.edit(step["path"], step["before"].encode(), step["after"].encode())
                    item = {"index": index, "tool": tool, "sha256": hashlib.sha256(workspace.read(step["path"])).hexdigest()}
                elif tool in ("read", "verify_sha256"):
                    data = workspace.read(step["path"])
                    digest_file = hashlib.sha256(data).hexdigest()
                    if tool == "verify_sha256" and digest_file != step["expected_sha256"]:
                        raise WorkspaceDenied("file-hash-mismatch")
                    item = {"index": index, "tool": tool, "sha256": digest_file, "bytes": len(data)}
                elif tool == "search":
                    info = workspace.search(step["query"], case_sensitive=step["case_sensitive"])
                    item = {"index": index, "tool": tool, **info}
                elif tool == "preview_edit":
                    info = workspace.preview_edit(step["path"], step["before"].encode(), step["after"].encode())
                    item = {"index": index, "tool": tool, **info}
                elif tool == "research":
                    info = fetch_metadata(step["provider"], step["name"])
                    item = {"index": index, "tool": tool, **info}
                elif tool == "package":
                    info = workspace.package(step["output"])
                    item = {"index": index, "tool": tool, **info}
                elif tool == "run":
                    receipt = run_container(workspace, step["image"], step["argv"], approved=True, timeout_seconds=step["timeout_seconds"], **({"cancel_event": cancel_event} if cancel_event is not None else {}))
                    item = {"index": index, "tool": tool, "exit_code": receipt.exit_code, "status": receipt.status,
                            "stdout_sha256": hashlib.sha256(receipt.stdout.encode()).hexdigest(),
                            "stderr_sha256": hashlib.sha256(receipt.stderr.encode()).hexdigest(),
                            "duration_ms": receipt.duration_ms}
                    if receipt.status == "cancelled":
                        status = "cancelled"
                    elif receipt.status != "complete" or receipt.exit_code != 0:
                        status = "execution-failed"
                else:
                    raise WorkspaceDenied("unknown-tool")
                results.append(item)
                if status != "complete":
                    break
            except (OSError, WorkspaceDenied, ResearchDenied, ValueError) as exc:
                status = "step-denied"
                results.append({"index": index, "tool": tool, "status": "denied", "reason": type(exc).__name__})
                break
        if status == "complete" and cancel_event is not None and cancel_event.is_set():
            status = "cancelled"
        try:
            workspace_sha256_after = workspace.manifest()["sha256"]
        except (WorkspaceDenied, OSError):
            # A command may have created a symlink, FIFO or oversized file. Never
            # claim a clean end state when its integrity cannot be observed.
            workspace_sha256_after = None
            status = "post-state-unverifiable"
        completed = sum(item.get("status") in (None, "complete") for item in results)
        summaries = [{"index": item["index"], "tool": item["tool"],
                      "status": "denied" if item.get("status") == "denied" else
                      ("cancelled" if item.get("status") == "cancelled" else
                      ("failed" if item.get("status") not in (None, "complete") else "completed"))}
                     for item in results]
        try:
            journal.finish(digest, status=status, workspace_after=workspace_sha256_after,
                           completed_steps=completed, step_summaries=summaries)
        except (OSError, WorkspaceDenied) as exc:
            raise WorkspaceDenied("durable-receipt-failed-workspace-may-have-changed") from exc
        return PlanReceipt(digest, status, completed, tuple(results),
                           workspace_sha256_before=workspace_sha256_before,
                           workspace_sha256_after=workspace_sha256_after)
