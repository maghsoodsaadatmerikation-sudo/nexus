#!/usr/bin/env python3
"""Private, atomic, no-clobber single-workspace snapshot export.

Unlike full-data recovery, this exports exactly one authenticated workspace.
The bearer token stays out of subprocess argument lists and output artifacts.
"""
from __future__ import annotations

import json
import http.client
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 64 * 1024 * 1024
READ_SIZE = 64 * 1024
TIMEOUT = 20
WORKSPACE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


class BackupBlocked(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise BackupBlocked(reason)


def origin_url(value: str) -> str:
    require(bool(value) and value == value.strip() and
            not any(c.isspace() or ord(c) < 32 for c in value) and
            "\\" not in value, "invalid NEXUS_BASE_URL")
    try:
        url = urllib.parse.urlsplit(value)
        port = url.port
        host = url.hostname
    except ValueError as error:
        raise BackupBlocked("invalid NEXUS_BASE_URL") from error
    require(url.scheme in ("http", "https") and bool(host),
            "expected HTTPS origin or loopback HTTP")
    require(url.username is None and url.password is None and
            not url.query and not url.fragment and url.path in ("", "/") and
            "@" not in url.netloc and "%" not in url.netloc,
            "base URL must be an origin without credentials or a path")
    require(port is None or 1 <= port <= 65535, "invalid NEXUS_BASE_URL port")
    require(url.scheme == "https" or host in ("localhost", "127.0.0.1", "::1"),
            "plaintext HTTP allowed only for local loopback")
    return f"{url.scheme}://{url.netloc}"


def read_env() -> tuple[str, str, str]:
    origin = origin_url(os.getenv("NEXUS_BASE_URL", ""))
    workspace_id = os.getenv("NEXUS_WORKSPACE_ID", "")
    require(bool(WORKSPACE_ID.fullmatch(workspace_id)),
            "workspace ID is not a safe single URL segment")
    token = os.getenv("NEXUS_API_TOKEN", "")
    require(bool(token) and token.isascii() and
            not any(ord(c) < 33 or ord(c) > 126 for c in token),
            "invalid or absent NEXUS_API_TOKEN")
    return origin, workspace_id, token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_snapshot(stream, workspace_id: str) -> None:
    try:
        # Bounded by MAX_BYTES before parsing. Reject duplicate JSON keys,
        # so parser ambiguity cannot conceal a mismatched workspace ID.
        def reject_duplicate_keys(items):
            result = {}
            for key, value in items:
                require(key not in result, "duplicate JSON object member")
                result[key] = value
            return result

        stream.seek(0)
        document = json.load(stream, object_pairs_hook=reject_duplicate_keys)
        require(type(document) is dict and
                type(document.get("schema_version")) is int and
                type(document.get("events")) is list and
                type(document.get("workspace")) is dict and
                document["workspace"].get("id") == workspace_id,
                "response is not the requested workspace snapshot")
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BackupBlocked("workspace response is not valid JSON") from error


def _safe_destination(output: Path) -> tuple[int, str]:
    name = output.name
    require(name not in ("", ".", "..") and len(os.fsencode(name)) <= 230,
            "invalid output filename")
    require(output != Path("/") and not output.is_dir(),
            "output must name a new private regular file")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(output.parent, flags)
    try:
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return directory_fd, name
        raise BackupBlocked("output exists; no overwrite permitted")
    except BaseException:
        os.close(directory_fd)
        raise


def write_backup(origin: str, workspace_id: str, token: str,
                 output: Path, opener=None) -> None:
    directory_fd, name = _safe_destination(output)
    temp_name = f".nexus-workspace-{secrets.token_hex(16)}.tmp"
    temp_fd = None
    created = False
    try:
        temp_fd = os.open(
            temp_name, os.O_RDWR | os.O_CREAT | os.O_EXCL |
            getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory_fd)
        # Even a permissive operator umask must not change the private mode.
        os.fchmod(temp_fd, stat.S_IRUSR | stat.S_IWUSR)
        url = origin + "/v1/workspaces/" + urllib.parse.quote(workspace_id, safe="")
        request = urllib.request.Request(
            url, method="GET", headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Cache-Control": "no-store",
            })
        if opener is None:
            # Never use ambient proxy credentials or forward the bearer token
            # across an HTTP redirect.
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=TIMEOUT) as response:
            require(response.geturl() == url and response.status == 200,
                    "unexpected HTTP response or redirect")
            kind = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            require(kind == "application/json", "non-JSON workspace response")
            require(response.headers.get("content-encoding", "identity").lower() == "identity",
                    "compressed workspace response is unsupported")
            claimed = response.headers.get("content-length")
            if claimed is not None:
                require(claimed.isascii() and claimed.isdecimal() and
                        int(claimed) <= MAX_BYTES,
                        "invalid or excessive Content-Length")
            total = 0
            with os.fdopen(temp_fd, "w+b", buffering=0, closefd=False) as temp:
                while True:
                    chunk = response.read(min(READ_SIZE, MAX_BYTES - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    require(total <= MAX_BYTES, "workspace snapshot exceeds size cap")
                    temp.write(chunk)
                if claimed is not None:
                    require(total == int(claimed), "truncated workspace response")
                require(total > 0, "empty workspace response")
                check_snapshot(temp, workspace_id)
                temp.flush()
            os.fsync(temp_fd)
        # Hard-link to a NEW name provides an atomic no-replace publication.
        # This refuses existing files and symlinks, even if created mid-request.
        os.link(temp_name, name, src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd, follow_symlinks=False)
        created = True
        os.fsync(directory_fd)
    except BaseException:
        if created:
            os.unlink(name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        raise
    finally:
        if temp_fd is not None:
            os.close(temp_fd)
            os.unlink(temp_name, dir_fd=directory_fd)
            if created:
                os.fsync(directory_fd)
        os.close(directory_fd)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        require(len(args) <= 1, "at most one output path is supported")
        origin, workspace_id, token = read_env()
        output = Path(args[0] if args else f"nexus-workspace-{workspace_id}.json")
        write_backup(origin, workspace_id, token, output)
        print(f"Backup written: {output} (private, atomic, no replacement)")
        print("Scope: SINGLE WORKSPACE ONLY; NOT A FULL-DATA RECOVERY BACKUP")
        return 0
    except (BackupBlocked, OSError, urllib.error.URLError,
            http.client.HTTPException, TimeoutError) as error:
        # No token, URL, output file, workspace content or HTTP body is echoed.
        print(f"WORKSPACE BACKUP: BLOCKED ({type(error).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
