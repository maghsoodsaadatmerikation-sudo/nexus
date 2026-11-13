#!/usr/bin/env python3
"""Send exactly the validated private snapshot bytes, never a reopened pathname."""
from __future__ import annotations

import http.client
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import urllib.error
import urllib.request

BACKUP_MODULE = Path(__file__).with_name('workspace-backup.py')
spec = importlib.util.spec_from_file_location('nexus_backup_common', BACKUP_MODULE)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class RestoreBlocked(ValueError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RestoreBlocked(reason)


def snapshot_bytes(path: Path) -> tuple[bytes, str]:
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                0 < before.st_size <= backup.MAX_BYTES,
                'snapshot must be a bounded, unique regular file')
        with os.fdopen(fd, 'rb', closefd=False) as handle:
            raw = handle.read(backup.MAX_BYTES + 1)
        after = os.fstat(fd)
        current = path.lstat()
        identity = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                  value.st_mtime_ns, value.st_ctime_ns)
        require(len(raw) == before.st_size and identity(before) == identity(after)
                and identity(before) == identity(current)
                and stat.S_ISREG(current.st_mode) and current.st_nlink == 1,
                'snapshot changed or was replaced while reading')
    finally:
        os.close(fd)

    def no_duplicates(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate snapshot JSON member')
            result[key] = value
        return result
    try:
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=no_duplicates)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RestoreBlocked('invalid snapshot JSON') from error
    require(type(document) is dict and
            type(document.get('schema_version')) is int and
            document['schema_version'] > 0 and
            type(document.get('workspace')) is dict and
            type(document['workspace'].get('id')) is str and
            bool(document['workspace']['id']) and
            type(document.get('events')) is list,
            'not a NEXUS workspace snapshot')
    return raw, document['workspace']['id']


def import_snapshot(origin: str, token: str, raw: bytes, opener=None) -> None:
    require(bool(token) and token.isascii() and
            not any(ord(c) < 33 or ord(c) > 126 for c in token),
            'invalid or absent API token')
    url = origin + '/v1/workspaces/import'
    request = urllib.request.Request(
        url, data=raw, method='POST', headers={
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'Accept-Encoding': 'identity',
        })
    if opener is None:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), backup.NoRedirect())
    with opener.open(request, timeout=120) as response:
        require(response.geturl() == url and response.status == 201,
                'workspace import was not accepted by the expected endpoint')


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        require(len(args) == 1, 'exactly one snapshot path is required')
        origin = backup.origin_url(os.getenv('NEXUS_BASE_URL', ''))
        token = os.getenv('NEXUS_API_TOKEN', '')
        # Validation must precede network access. Keep the validated bytes
        # immutable in memory across the whole POST, not reopen the pathname.
        raw, _workspace_id = snapshot_bytes(Path(args[0]))
        import_snapshot(origin, token, raw)
        print('Workspace restore accepted by NEXUS (single-workspace import only).')
        return 0
    except (RestoreBlocked, backup.BackupBlocked, OSError, urllib.error.URLError,
            http.client.HTTPException, TimeoutError) as error:
        # No tokens, path, workspace ID or server body reach logs.
        print('WORKSPACE RESTORE: BLOCKED (' + type(error).__name__ + ')',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
