#!/usr/bin/env python3
"""Manual, separately operated, read-only GitHub witness for reviewed Studio writes.

CHECK runs on the witness's *own* host/account with its independently held
GitHub read credential and Ed25519 key. VERIFY uses a separately pinned public
key without any network access. Neither action authorizes NEXUS mutations or
makes the local NEXUS environment an independent trust domain.
"""
import argparse
import base64
import binascii
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
from urllib.parse import quote

SCHEMA = "nexus.studio.github.witness-request.v1"
ATTESTATION = "nexus.studio.github.external-witness.v1"
DOMAIN = b"NEXUS\x00studio-github-external-witness\x00Ed25519\x00v1\x00"
MAX_REQUEST = 12 * 1024
MAX_RESPONSE = 1024 * 1024
SHA1 = re.compile(r"[a-f0-9]{40}")
SHA256 = re.compile(r"[a-f0-9]{64}")
REPO = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}")
BRANCH = re.compile(r"nexus/studio-[a-z0-9](?:[a-z0-9-]{1,46})[a-z0-9]")
KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}")
FILE_PART = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")
RECEIPT_KEYS = frozenset({
    "schema_version", "kind", "operation", "outcome", "revision",
    "followup_read_verified", "reviewed_request_matched", "file_bytes_verified",
    "independent_attestation", "deployment_verified",
})
REQUEST_KEYS = frozenset({
    "schema", "provider", "repository", "operation", "branch", "revision",
    "file_path", "file_sha256", "review_reference_sha256",
    "source_receipt", "authority", "external_witness_completed",
})
REPORT_BODY_KEYS = frozenset({
    "schema", "algorithm", "witness_id", "key_id", "request_sha256",
    "repository", "operation", "branch", "revision", "observed_file_sha256",
    "method", "independence_of_custody_not_self_proven",
    "provider_is_not_independent_of_its_own_data",
})
REPORT_KEYS = REPORT_BODY_KEYS | {"signature_base64"}


class WitnessError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise WitnessError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def no_duplicate_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


def strict_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=no_duplicate_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(WitnessError("nonfinite JSON")))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise WitnessError("invalid JSON") from exc


def read_json(path, limit=MAX_REQUEST):
    with Path(path).open("rb") as inp:
        raw = inp.read(limit + 1)
    require(len(raw) <= limit, "JSON file too large")
    return strict_json(raw)


def valid_request(obj, expected_repo):
    require(type(obj) is dict and set(obj) == REQUEST_KEYS, "unrecognized request structure")
    require(obj["schema"] == SCHEMA and obj["provider"] == "github"
            and obj["authority"] == "source_claim_only"
            and obj["external_witness_completed"] is False, "not an unauthenticated source claim")
    repo = obj["repository"]
    require(type(repo) is str and REPO.fullmatch(repo) and repo == expected_repo
            and repo.split("/")[1] not in {".", ".."}, "repository is not independently pinned")
    op, branch, revision = obj["operation"], obj["branch"], obj["revision"]
    require(op in ("github.branch", "github.file_commit")
            and type(branch) is str and BRANCH.fullmatch(branch)
            and type(revision) is str and SHA1.fullmatch(revision)
            and type(obj["review_reference_sha256"]) is str
            and SHA256.fullmatch(obj["review_reference_sha256"]), "invalid reviewed operation")
    receipt = obj["source_receipt"]
    require(type(receipt) is dict and set(receipt) == RECEIPT_KEYS
            and type(receipt["schema_version"]) is int and receipt["schema_version"] == 1
            and receipt["kind"] == "github_followup_read"
            and receipt["operation"] == op and receipt["revision"] == revision
            and receipt["followup_read_verified"] is True
            and receipt["reviewed_request_matched"] is True
            and receipt["independent_attestation"] is False
            and receipt["deployment_verified"] is False, "invalid source readback claim")
    if op == "github.branch":
        require(receipt["outcome"] in ("created", "already_exists")
                and receipt["file_bytes_verified"] is False
                and obj["file_path"] is None and obj["file_sha256"] is None,
                "branch evidence cannot include file proof")
    else:
        path, file_hash = obj["file_path"], obj["file_sha256"]
        require(receipt["outcome"] == "committed"
                and receipt["file_bytes_verified"] is True
                and type(path) is str and 1 <= len(path) <= 240
                and all(FILE_PART.fullmatch(part) and part not in (".", "..")
                        for part in path.split("/"))
                and type(file_hash) is str and SHA256.fullmatch(file_hash),
                "invalid reviewed file commitment")
    return obj


def github_get(path, token):
    # Only this hardcoded HTTPS origin is ever contacted. Redirects are errors.
    require(path.startswith("/repos/") and not any(ch in path for ch in "\r\n"),
            "invalid read-only provider path")
    connection = http.client.HTTPSConnection("api.github.com", timeout=12,
                                             context=ssl.create_default_context())
    try:
        headers = {"Accept": "application/vnd.github+json",
                   "Accept-Encoding": "identity", "User-Agent": "nexus-external-witness-v1",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = "Bearer " + token
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        require(response.status == 200 and response.getheader("Content-Encoding", "identity").lower() == "identity",
                "GitHub read unavailable, rejected, or redirected")
        raw = response.read(MAX_RESPONSE + 1)
        require(len(raw) <= MAX_RESPONSE, "provider response too large")
        require(response.getheader("Content-Type", "").split(";")[0].lower() in
                ("application/json", "application/vnd.github+json"), "unexpected provider content type")
        return strict_json(raw)
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise WitnessError("independent GitHub read unavailable") from exc
    finally:
        connection.close()


def observed_state(request, fetch):
    repo, branch, revision = request["repository"], request["branch"], request["revision"]
    root = "/repos/" + quote(repo, safe="/")
    observed = fetch(root + "/branches/" + quote(branch, safe=""))
    require(type(observed) is dict and observed.get("name") == branch
            and type(observed.get("commit")) is dict
            and observed["commit"].get("sha") == revision, "witness branch revision diverged")
    if request["operation"] == "github.branch":
        return None
    commit = fetch(root + "/git/commits/" + revision)
    require(type(commit) is dict and commit.get("sha") == revision
            and type(commit.get("tree")) is dict
            and type(commit["tree"].get("sha")) is str
            and SHA1.fullmatch(commit["tree"]["sha"]), "unverified commit tree")
    tree = fetch(root + "/git/trees/" + commit["tree"]["sha"] + "?recursive=1")
    require(type(tree) is dict and tree.get("truncated") is False
            and type(tree.get("tree")) is list and len(tree["tree"]) < 20000,
            "unverified or truncated file tree")
    path = request["file_path"]
    matches = [entry for entry in tree["tree"]
               if type(entry) is dict and entry.get("path") == path]
    require(len(matches) == 1 and matches[0].get("type") == "blob"
            and matches[0].get("mode") == "100644"
            and type(matches[0].get("sha")) is str
            and SHA1.fullmatch(matches[0]["sha"]), "not a unique regular file")
    file = fetch(root + "/contents/" + quote(path, safe="/") + "?ref=" + revision)
    require(type(file) is dict and file.get("type") == "file"
            and file.get("path") == path and file.get("encoding") == "base64"
            and file.get("sha") == matches[0]["sha"]
            and type(file.get("content")) is str, "file is not bound to commit tree")
    try:
        raw = base64.b64decode(file["content"].replace("\n", ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WitnessError("invalid base64 file bytes") from exc
    require(0 < len(raw) <= 24 * 1024 and b"\x00" not in raw, "reviewed file size or content invalid")
    git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    require(git_blob == file["sha"], "Git blob identity mismatch")
    actual_digest = hashlib.sha256(raw).hexdigest()
    require(actual_digest == request["file_sha256"], "reviewed bytes not found at revision")
    return actual_digest


def signature_bytes(action, key, preimage, signature=b""):
    with tempfile.TemporaryDirectory(prefix="nexus-external-witness-") as tmp:
        root = Path(tmp)
        source = root / "message.bin"
        source.write_bytes(preimage)
        os.chmod(source, 0o600)
        sigfile = root / "sig.bin"
        if action == "verify":
            sigfile.write_bytes(signature)
            os.chmod(sigfile, 0o600)
            cmd = ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
                   "-inkey", str(key), "-in", str(source), "-sigfile", str(sigfile)]
        else:
            cmd = ["openssl", "pkeyutl", "-sign", "-rawin",
                   "-inkey", str(key), "-in", str(source), "-out", str(sigfile)]
        try:
            outcome = subprocess.run(cmd, capture_output=True, timeout=15, check=False)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise WitnessError("OpenSSL signature operation unavailable") from exc
        require(outcome.returncode == 0, "external Ed25519 signature invalid")
        return sigfile.read_bytes() if action == "sign" else b""


def preimage(body):
    payload = canonical(body)
    return DOMAIN + len(payload).to_bytes(8, "big") + payload


def checked_report(req, witness_id, key_id, fetch, signing_key):
    require(type(witness_id) is str and KEY_ID.fullmatch(witness_id)
            and type(key_id) is str and KEY_ID.fullmatch(key_id), "invalid independently assigned key IDs")
    observed = observed_state(req, fetch)
    body = {
        "schema": ATTESTATION, "algorithm": "Ed25519",
        "witness_id": witness_id, "key_id": key_id,
        "request_sha256": digest(req), "repository": req["repository"],
        "operation": req["operation"], "branch": req["branch"],
        "revision": req["revision"], "observed_file_sha256": observed,
        "method": "independent_operator_github_https_read",
        "independence_of_custody_not_self_proven": True,
        "provider_is_not_independent_of_its_own_data": True,
    }
    signature = signature_bytes("sign", signing_key, preimage(body))
    require(len(signature) == 64, "unexpected signature size")
    return {**body, "signature_base64": base64.b64encode(signature).decode("ascii")}


def verify_report(req, report, witness_id, key_id, trusted_public_key):
    require(type(report) is dict and set(report) == REPORT_KEYS, "invalid witness report")
    body = {key: report[key] for key in REPORT_BODY_KEYS}
    require(body["schema"] == ATTESTATION and body["algorithm"] == "Ed25519"
            and body["witness_id"] == witness_id and body["key_id"] == key_id
            and body["request_sha256"] == digest(req)
            and body["repository"] == req["repository"]
            and body["operation"] == req["operation"]
            and body["branch"] == req["branch"]
            and body["revision"] == req["revision"]
            and body["observed_file_sha256"] == req["file_sha256"]
            and body["method"] == "independent_operator_github_https_read"
            and body["independence_of_custody_not_self_proven"] is True
            and body["provider_is_not_independent_of_its_own_data"] is True,
            "external report not bound to the reviewed request")
    try:
        signature = base64.b64decode(report["signature_base64"], validate=True)
    except (ValueError, binascii.Error, TypeError) as exc:
        raise WitnessError("invalid report signature encoding") from exc
    require(len(signature) == 64, "invalid report signature size")
    signature_bytes("verify", trusted_public_key, preimage(body), signature)
    return True


def write_new(path, obj):
    raw = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"
    require(len(raw) <= MAX_REQUEST, "signed witness report exceeds limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    check = commands.add_parser("check", help="Manually re-check GitHub and sign with external key")
    check.add_argument("--request", type=Path, required=True)
    check.add_argument("--expected-repository", required=True)
    check.add_argument("--witness-id", required=True)
    check.add_argument("--key-id", required=True)
    check.add_argument("--private-key", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--token-env", default="NEXUS_GITHUB_WITNESS_TOKEN")
    verify = commands.add_parser("verify", help="Offline verify against independently pinned key")
    verify.add_argument("--request", type=Path, required=True)
    verify.add_argument("--expected-repository", required=True)
    verify.add_argument("--report", type=Path, required=True)
    verify.add_argument("--expected-witness-id", required=True)
    verify.add_argument("--trusted-key-id", required=True)
    verify.add_argument("--trusted-public-key", type=Path, required=True)
    args = parser.parse_args()
    try:
        req = valid_request(read_json(args.request), args.expected_repository)
        if args.action == "check":
            require(re.fullmatch(r"[A-Z_][A-Z0-9_]{0,63}", args.token_env),
                    "invalid environment variable name")
            token = os.getenv(args.token_env, "").strip()
            require(not token or ("\r" not in token and "\n" not in token and len(token) <= 1024),
                    "invalid witness read token")
            report = checked_report(req, args.witness_id, args.key_id,
                                    lambda path: github_get(path, token), args.private_key)
            write_new(args.output, report)
            print("GITHUB EXTERNAL WITNESS: signed separate-key readback; custody independence not self-proven")
        else:
            verify_report(req, read_json(args.report), args.expected_witness_id,
                          args.trusted_key_id, args.trusted_public_key)
            print("GITHUB WITNESS SIGNATURE VALID: pinned key and request; no global freshness proof")
    except (WitnessError, OSError) as exc:
        parser.exit(1, "GITHUB WITNESS UNVERIFIED: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
