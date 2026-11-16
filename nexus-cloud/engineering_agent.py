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

MAX_PLAN_BYTES = 32_768
MAX_STEPS = 12
TOOLS = frozenset(("read", "write", "edit", "run", "verify_sha256", "package"))
HASH = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value) or len(value.encode("utf-8")) > MAX_FILE_BYTES:
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
    if not isinstance(plan, dict) or set(plan) != {"version", "workspace", "steps"} or type(plan["version"]) is not int or plan["version"] != 1:
        raise WorkspaceDenied("plan-schema")
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
    }
    for step in steps:
        if not isinstance(step, dict) or step.get("tool") not in TOOLS or set(step) != shapes[step["tool"]]:
            raise WorkspaceDenied("plan-step-schema")
        tool = step["tool"]
        if "path" in step:
            safe_parts(step["path"])
        if tool == "write":
            _text(step["text"], allow_empty=True)
        if tool == "edit":
            _text(step["before"])
            _text(step["after"], allow_empty=True)
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
    canonical = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return plan, hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class PlanReceipt:
    plan_sha256: str
    status: str
    completed_steps: int
    results: tuple[dict[str, Any], ...]
    authority: str = "operator-reviewed-only"


def execute_plan(workspace: Workspace, plan: dict[str, Any], digest: str, *, approved_digest: str) -> PlanReceipt:
    if not isinstance(approved_digest, str) or approved_digest != digest or not HASH.fullmatch(digest):
        raise WorkspaceDenied("exact-plan-approval-required")
    checked, actual_digest = parse_plan(json.dumps(plan, ensure_ascii=False).encode("utf-8"))
    if actual_digest != digest or checked["workspace"] != workspace.name:
        raise WorkspaceDenied("plan-changed-or-wrong-workspace")
    results: list[dict[str, Any]] = []
    status = "complete"
    for index, step in enumerate(checked["steps"]):
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
            elif tool == "package":
                info = workspace.package(step["output"])
                item = {"index": index, "tool": tool, **info}
            elif tool == "run":
                receipt = run_container(workspace, step["image"], step["argv"], approved=True, timeout_seconds=step["timeout_seconds"])
                item = {"index": index, "tool": tool, "exit_code": receipt.exit_code, "status": receipt.status,
                        "stdout_sha256": hashlib.sha256(receipt.stdout.encode()).hexdigest(),
                        "stderr_sha256": hashlib.sha256(receipt.stderr.encode()).hexdigest(),
                        "duration_ms": receipt.duration_ms}
                if receipt.status != "complete" or receipt.exit_code != 0:
                    status = "execution-failed"
            else:
                raise WorkspaceDenied("unknown-tool")
            results.append(item)
            if status != "complete":
                break
        except (OSError, WorkspaceDenied, ValueError) as exc:
            status = "step-denied"
            results.append({"index": index, "tool": tool, "status": "denied", "reason": type(exc).__name__})
            break
    return PlanReceipt(digest, status, sum(item.get("status") != "denied" for item in results), tuple(results))
