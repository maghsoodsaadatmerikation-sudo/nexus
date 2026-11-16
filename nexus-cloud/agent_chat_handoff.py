"""Review-only bridge between NEXUS Studio text and local operator-run plans.

Untrusted model proposals are parsed, bounded and converted into v3 plans. No
proposal can authorize itself. There is no HTTP endpoint, model connection or
background execution in this module. Generated chat receipts contain hashes and
statuses only, not code, paths, network payloads or command output.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from agent_workspace import Workspace, WorkspaceDenied
from engineering_agent import MAX_PLAN_BYTES, parse_plan

PROPOSAL_SCHEMA = "nexus.engineering.proposal.v1"
REVIEW_SCHEMA = "nexus.engineering.review.v1"
RESULT_SCHEMA = "nexus.engineering.chat-receipt.v1"
HASH = re.compile(r"^[0-9a-f]{64}$")


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            raise WorkspaceDenied("duplicate-proposal-key")
        obj[key] = value
    return obj


def parse_proposal(raw: bytes) -> dict:
    """Parse an explicitly exported model draft. No auth/nonce/hash from model."""
    if not isinstance(raw, bytes) or len(raw) > MAX_PLAN_BYTES or not raw:
        raise WorkspaceDenied("proposal-size")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(WorkspaceDenied("nonfinite-proposal-number")))
    except WorkspaceDenied:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise WorkspaceDenied("invalid-proposal-json") from exc
    if not isinstance(obj, dict) or set(obj) != {"schema", "workspace", "steps"} or obj["schema"] != PROPOSAL_SCHEMA:
        raise WorkspaceDenied("proposal-schema")
    # Validate steps through the EXACT local execution schema with safe dummy
    # identity fields. The independent random nonce/current manifest come later.
    candidate = {"version": 3, "workspace": obj["workspace"], "steps": obj["steps"],
                 "expected_workspace_sha256": "0" * 64, "execution_nonce": "0" * 32}
    try:
        raw_candidate = json.dumps(candidate, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise WorkspaceDenied("proposal-encoding") from exc
    parse_plan(raw_candidate)
    return obj


def prepare(workspace: Workspace, proposal: dict) -> tuple[bytes, dict]:
    """Create an inert single-use candidate, not an execution permission."""
    if not isinstance(proposal, dict) or proposal.get("schema") != PROPOSAL_SCHEMA:
        raise WorkspaceDenied("invalid-proposal")
    # Second validation protects direct callers from unchecked objects.
    try:
        parse_proposal(json.dumps(proposal, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError) as exc:
        raise WorkspaceDenied("invalid-proposal") from exc
    if proposal["workspace"] != workspace.name:
        raise WorkspaceDenied("proposal-workspace-mismatch")
    with workspace.operation_lock():
        manifest = workspace.manifest()["sha256"]
        plan = {"version": 3, "workspace": workspace.name,
                "expected_workspace_sha256": manifest,
                "execution_nonce": os.urandom(16).hex(),
                "steps": proposal["steps"]}
        raw = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        checked, digest = parse_plan(raw)
        if checked != plan:
            raise WorkspaceDenied("candidate-mismatch")
    # Intentionally exclude raw argv, file text, paths, URLs, source snippets.
    steps = [{"index": i, "tool": s["tool"],
              "risk": "executes-container" if s["tool"] == "run"
              else "network-metadata" if s["tool"] == "research"
              else "writes-files" if s["tool"] in ("write", "edit")
              else "exports-archive" if s["tool"] == "package"
              else "read-only"}
             for i, s in enumerate(checked["steps"])]
    review = {"schema": REVIEW_SCHEMA, "authority": "none",
              "plan_sha256": digest, "workspace_sha256": manifest,
              "workspace": workspace.name, "plan_version": 3, "steps": steps,
              "status": "not-executed", "review_required": True,
              "note": "Untrusted proposal. Inspect the ENTIRE private plan file; execute only with separately supplied exact plan SHA-256. This report is not permission or verification."}
    return raw, review


def chat_receipt(journal: dict) -> dict:
    """Shareable status-only evidence; not an independent security attestation."""
    if not isinstance(journal, dict) or journal.get("state") not in {"started", "finished"}:
        raise WorkspaceDenied("invalid-journal")
    sha = journal.get("plan_sha256")
    before = journal.get("workspace_sha256_before")
    after = journal.get("workspace_sha256_after")
    if not isinstance(sha, str) or not HASH.fullmatch(sha) or not isinstance(before, str) or not HASH.fullmatch(before):
        raise WorkspaceDenied("invalid-journal-hash")
    if after is not None and (not isinstance(after, str) or not HASH.fullmatch(after)):
        raise WorkspaceDenied("invalid-journal-hash")
    state = journal["state"]
    status = journal.get("result") if state == "finished" else "interrupted-or-in-progress"
    if state == "finished" and (not isinstance(status, str) or status not in {"complete", "execution-failed", "step-denied", "post-state-unverifiable", "cancelled"}):
        raise WorkspaceDenied("invalid-journal-result")
    steps = journal.get("steps", []) if state == "finished" else []
    if not isinstance(steps, list) or len(steps) > 12:
        raise WorkspaceDenied("invalid-journal-steps")
    safe_steps = []
    for item in steps:
        if not isinstance(item, dict) or type(item.get("index")) is not int or item["index"] < 0 or item["index"] > 11 or item.get("tool") not in {"read","write","edit","run","verify_sha256","package","search","preview_edit","research"} or item.get("status") not in {"completed", "failed", "denied", "cancelled"}:
            raise WorkspaceDenied("invalid-journal-steps")
        safe_steps.append({"index": item["index"], "tool": item["tool"], "status": item["status"]})
    result = {"schema": RESULT_SCHEMA, "origin": "local-engineering-worker",
              "authority": "none", "verification": "not-independent-attestation",
              "plan_sha256": sha, "journal_state": state,
              "execution_status": status, "workspace_sha256_before": before,
              "workspace_sha256_after": after if state == "finished" else None,
              "steps": safe_steps,
              "note": "Machine-observed local outcome, not a human decision. No source contents, secrets or command logs are included. A started record may reflect partial side effects."}
    return result


def read_operator_file(path: str | Path, *, require_private: bool = False) -> bytes:
    """Bounded file intake; daemon plan files additionally require owner-only mode."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > MAX_PLAN_BYTES:
            raise WorkspaceDenied("operator-input-not-bounded-regular-file")
        if require_private and (st.st_uid != os.getuid() or st.st_mode & 0o077):
            raise WorkspaceDenied("operator-plan-requires-private-owner-only-file")
        chunks = bytearray()
        while len(chunks) <= MAX_PLAN_BYTES:
            chunk = os.read(fd, min(65536, MAX_PLAN_BYTES + 1 - len(chunks)))
            if not chunk:
                return bytes(chunks)
            chunks.extend(chunk)
        raise WorkspaceDenied("operator-input-too-large")
    finally:
        os.close(fd)

def private_export_dir(path: str | Path, workspace: Workspace) -> Path:
    """Require operator-owned private outbox outside all workspaces/journals."""
    folder = Path(path)
    if not folder.is_absolute() or folder.is_symlink() or folder.resolve().is_relative_to(workspace.root.resolve()):
        raise WorkspaceDenied("export-directory-must-be-private-and-outside-root")
    st = folder.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise WorkspaceDenied("export-directory-must-be-private-and-owned")
    return folder


def write_export(directory: Path, name: str, content: bytes) -> Path:
    if not isinstance(name, str) or not re.fullmatch(r"nexus-(plan|review|result)-[0-9a-f]{16}\.(json|txt)", name):
        raise WorkspaceDenied("invalid-export-name")
    if not isinstance(content, bytes) or len(content) > 65_536:
        raise WorkspaceDenied("export-too-large")
    rootfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        st = os.fstat(rootfd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise WorkspaceDenied("export-directory-changed")
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=rootfd)
        except FileExistsError as exc:
            raise WorkspaceDenied("export-already-exists") from exc
        try:
            with os.fdopen(fd, "wb", closefd=False) as f:
                f.write(content)
                f.flush()
            os.fsync(fd)
        except BaseException:
            os.unlink(name, dir_fd=rootfd)
            raise
        finally:
            os.close(fd)
        os.fsync(rootfd)
        return directory / name
    finally:
        os.close(rootfd)


def shareable_json(value: dict) -> bytes:
    data = json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    if len(data) > 65_536:
        raise WorkspaceDenied("export-too-large")
    return data
