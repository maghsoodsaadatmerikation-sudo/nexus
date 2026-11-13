#!/usr/bin/env python3
"""Fail-closed, read-only HTTPS observations for an operator-held Stage D witness.

This is NOT a production backup, deployment, or proof of an independently
restorable volume. It only replaces authenticated curl argv and unsafe output
redirection in historical single-workspace network witness collection.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "nexus_private_workspace_backup", ROOT / "workspace-backup.py"
)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)

ABSENCE_LIMIT = 512


class ObservationBlocked(ValueError):
    pass


def require(value: bool, reason: str) -> None:
    if not value:
        raise ObservationBlocked(reason)


def exact_json(raw: bytes) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON member")
            result[key] = value
        return result

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ObservationBlocked("invalid JSON witness") from error


def read_404(origin: str, workspace_id: str, token: str, opener=None) -> bytes:
    """Accept only exact-origin, authenticated JSON HTTP 404 from gateway."""
    require(backup.WORKSPACE_ID.fullmatch(workspace_id) is not None,
            "unsafe workspace ID")
    require(token and token.isascii()
            and all(33 <= ord(ch) <= 126 for ch in token),
            "invalid operator bearer")
    url = origin + "/v1/workspaces/" + urllib.parse.quote(workspace_id, safe="")
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-store",
        },
    )
    if opener is None:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), backup.NoRedirect()
        )
    try:
        with opener.open(request, timeout=20):
            # A 200, redirect, or other non-HTTPError response is never absence.
            raise ObservationBlocked("gateway did not return HTTP 404")
    except urllib.error.HTTPError as response:
        with response:
            require(response.code == 404 and response.geturl() == url,
                    "missing exact-origin 404")
            headers = response.headers
            kind = headers.get("content-type", "").lower().split(";", 1)[0].strip()
            require(kind == "application/json", "unexpected absence content type")
            require(headers.get("content-encoding", "identity").lower() == "identity",
                    "encoded absence response rejected")
            require("no-store" in headers.get("cache-control", "").lower(),
                    "absence response is cacheable")
            claimed = headers.get("content-length")
            if claimed is not None:
                require(claimed.isascii() and claimed.isdecimal()
                        and int(claimed) <= ABSENCE_LIMIT,
                        "invalid absence body length")
            raw = response.read(ABSENCE_LIMIT + 1)
            require(0 < len(raw) <= ABSENCE_LIMIT, "missing or oversized absence body")
            if claimed is not None:
                require(int(claimed) == len(raw), "truncated absence body")
            require(exact_json(raw) == {"error": "workspace_not_found"},
                    "404 body is not workspace_not_found")
            return raw


def write_private_new(data: bytes, target: Path) -> None:
    """Never follow or replace a target, including names created mid-write."""
    dir_fd, name = backup._safe_destination(target)
    temp_name = ".nexus-stage-d-" + secrets.token_hex(16) + ".tmp"
    fd = None
    published = False
    try:
        fd = os.open(temp_name,
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0),
                     0o600, dir_fd=dir_fd)
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "wb", closefd=False) as output:
            output.write(data)
            output.flush()
        os.fsync(fd)
        os.link(temp_name, name, src_dir_fd=dir_fd,
                dst_dir_fd=dir_fd, follow_symlinks=False)
        published = True
        os.fsync(dir_fd)
    except BaseException:
        if published:
            os.unlink(name, dir_fd=dir_fd)
            os.fsync(dir_fd)
        raise
    finally:
        if fd is not None:
            os.close(fd)
            os.unlink(temp_name, dir_fd=dir_fd)
        os.close(dir_fd)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        require(len(args) == 2 and args[0] in ("snapshot", "absence"),
                "expected: snapshot|absence <new-output-file>")
        origin, workspace_id, token = backup.read_env()
        target = Path(args[1])
        if args[0] == "snapshot":
            backup.write_backup(origin, workspace_id, token, target)
        else:
            body = read_404(origin, workspace_id, token)
            write_private_new(body, target)
        print("STAGE D PRIVATE NETWORK WITNESS: PASS")
        print("Scope: ONE AUTHENTICATED WORKSPACE; NO RELEASE AUTHORITY")
        return 0
    except (ObservationBlocked, backup.BackupBlocked, OSError,
            urllib.error.URLError, http.client.HTTPException, TimeoutError):
        # Never print operator URL, token, workspace ID, server body or path.
        print("STAGE D PRIVATE NETWORK WITNESS: BLOCKED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
