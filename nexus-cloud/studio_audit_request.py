"""Build a bounded, privacy-conscious request for a separately run GitHub witness.

This package contains declarative identifiers and a same-provider readback
receipt. It is not signed, not independent, and not an authorization token.
An external operator must explicitly transfer it to a separate verifier.
"""
import hashlib
import re

SCHEMA = "nexus.studio.github.witness-request.v1"
REPOSITORY = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}")
SHA1 = re.compile(r"[a-f0-9]{40}")
SHA256 = re.compile(r"[a-f0-9]{64}")
BRANCH = re.compile(r"nexus/studio-[a-z0-9](?:[a-z0-9-]{1,46})[a-z0-9]")


def make_request(operation, target, branch, revision, review_id, receipt,
                 *, file_path=None, file_bytes=None):
    """Source statement: external auditors must ignore its truth claims."""
    if (operation not in {"github.branch", "github.file_commit"}
            or not isinstance(target, str) or not REPOSITORY.fullmatch(target)
            or target.split("/")[1] in {".", ".."}
            or not isinstance(branch, str) or not BRANCH.fullmatch(branch)
            or not isinstance(revision, str) or not SHA1.fullmatch(revision)
            or not isinstance(review_id, str) or not SHA256.fullmatch(review_id)):
        raise ValueError("invalid reviewed operation identifiers")
    if (not isinstance(receipt, dict)
            or receipt.get("kind") != "github_followup_read"
            or receipt.get("operation") != operation
            or receipt.get("revision") != revision
            or receipt.get("followup_read_verified") is not True
            or receipt.get("reviewed_request_matched") is not True
            or receipt.get("independent_attestation") is not False
            or receipt.get("deployment_verified") is not False):
        raise ValueError("reviewed follow-up receipt is missing or mismatched")
    if operation == "github.branch":
        if (file_path is not None or file_bytes is not None
                or receipt.get("outcome") not in ("created", "already_exists")
                or receipt.get("file_bytes_verified") is not False):
            raise ValueError("invalid branch witness payload")
        digest = None
    else:
        if (not isinstance(file_path, str) or len(file_path) > 240
                or not file_path or any(not p or p in (".", "..") for p in file_path.split("/"))
                or any(c in file_path for c in ("\\", "%", "?", "#"))
                or not isinstance(file_bytes, bytes) or not 0 < len(file_bytes) <= 24 * 1024
                or receipt.get("outcome") != "committed"
                or receipt.get("file_bytes_verified") is not True):
            raise ValueError("invalid file witness payload")
        digest = hashlib.sha256(file_bytes).hexdigest()
    return {
        "schema": SCHEMA,
        "provider": "github",
        "repository": target,
        "operation": operation,
        "branch": branch,
        "revision": revision,
        "file_path": file_path,
        "file_sha256": digest,
        "review_reference_sha256": hashlib.sha256(review_id.encode("ascii")).hexdigest(),
        "source_receipt": dict(receipt),
        "authority": "source_claim_only",
        "external_witness_completed": False,
    }
