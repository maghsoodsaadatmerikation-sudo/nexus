"""Owner-approved, single-use rootless proof jobs. Not an LLM tool or public endpoint.

A plan binds the workspace manifest, reviewed ELF digest, arguments and timeout.
The authenticated operator service journals its approval before any guest run.
A crash leaves the digest consumed. This is local, not cross-host attestation.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from agent_rootless_probe import private_executable, validate_args
from agent_workspace import Workspace, WorkspaceDenied, WORKSPACE_ID

SCHEMA = 'nexus.rootless.operator-job.v1'
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
NONCE = re.compile(r'[0-9a-f]{32}\Z')
FIELDS = {'schema', 'workspace', 'workspace_sha256', 'executable',
          'executable_sha256', 'argv', 'timeout_seconds', 'nonce'}
MAX_PLAN = 8192


def _canonical(value: dict) -> bytes:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                     allow_nan=False).encode('ascii') + b'\n'
    if len(raw) > MAX_PLAN:
        raise WorkspaceDenied('rootless-job-plan-too-large')
    return raw


def _unique(pairs):
    value = {}
    for key, data in pairs:
        if key in value:
            raise WorkspaceDenied('rootless-job-duplicate-key')
        value[key] = data
    return value


def validate_job(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA:
        raise WorkspaceDenied('rootless-job-invalid-schema')
    if not isinstance(value['workspace'], str) or not WORKSPACE_ID.fullmatch(value['workspace']):
        raise WorkspaceDenied('rootless-job-workspace')
    for key in ('workspace_sha256', 'executable_sha256'):
        if not isinstance(value[key], str) or not DIGEST.fullmatch(value[key]):
            raise WorkspaceDenied('rootless-job-invalid-digest')
    if not isinstance(value['nonce'], str) or not NONCE.fullmatch(value['nonce']):
        raise WorkspaceDenied('rootless-job-nonce')
    if not isinstance(value['executable'], str) or len(value['executable']) > 1024:
        raise WorkspaceDenied('rootless-job-executable')
    path = Path(value['executable'])
    if not path.is_absolute() or '..' in path.parts or path.is_symlink():
        raise WorkspaceDenied('rootless-job-executable')
    validate_args(value['argv'], value['timeout_seconds'])


def parse_job(raw: bytes) -> tuple[dict, str]:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PLAN:
        raise WorkspaceDenied('rootless-job-size')
    try:
        value = json.loads(raw, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise WorkspaceDenied('rootless-job-json') from exc
    validate_job(value)
    if _canonical(value) != raw:
        raise WorkspaceDenied('rootless-job-noncanonical')
    return value, hashlib.sha256(raw).hexdigest()


def prepare_job(workspace: Workspace, executable: str | Path,
                executable_sha256: str, *, argv: list[str] | None = None,
                timeout_seconds: int = 6) -> tuple[bytes, dict]:
    """No execution: create a fresh plan for independent human review."""
    args = [] if argv is None else argv
    validate_args(args, timeout_seconds)
    private_executable(executable, executable_sha256)
    with workspace.operation_lock():
        observed = workspace.manifest()['sha256']
    value = {'schema': SCHEMA, 'workspace': workspace.name,
             'workspace_sha256': observed, 'executable': str(executable),
             'executable_sha256': executable_sha256, 'argv': args,
             'timeout_seconds': timeout_seconds, 'nonce': os.urandom(16).hex()}
    validate_job(value)
    raw = _canonical(value)
    digest = hashlib.sha256(raw).hexdigest()
    review = {'schema': 'nexus.rootless.operator-review.v1',
              'status': 'not-executed', 'authority': 'none', 'review_required': True,
              'workspace': workspace.name, 'workspace_sha256': observed,
              'plan_sha256': digest, 'executable_sha256': executable_sha256,
              'time_limit_seconds': timeout_seconds, 'argument_count': len(args),
              'note': 'Review the full private plan locally. No guest has run and no approval has been issued.'}
    return raw, review


def summarize_job(record: dict) -> dict:
    """Never expose the private executable pathname, arguments or raw output."""
    if not isinstance(record, dict) or record.get('plan_version') != 4 or record.get('schema') != 1:
        raise WorkspaceDenied('rootless-job-invalid-receipt')
    digest = record.get('plan_sha256')
    before = record.get('workspace_sha256_before')
    after = record.get('workspace_sha256_after')
    if (not isinstance(digest, str) or not DIGEST.fullmatch(digest)
            or not isinstance(before, str) or not DIGEST.fullmatch(before)
            or (after is not None and (not isinstance(after, str) or not DIGEST.fullmatch(after)))):
        raise WorkspaceDenied('rootless-job-invalid-receipt')
    state = record.get('state')
    if state not in ('started', 'finished'):
        raise WorkspaceDenied('rootless-job-invalid-receipt')
    result = record.get('result') if state == 'finished' else 'interrupted-or-in-progress'
    if state == 'finished' and result not in ('complete', 'execution-failed', 'cancelled', 'post-state-unverifiable'):
        raise WorkspaceDenied('rootless-job-invalid-receipt')
    return {'schema': 'nexus.rootless.operator-receipt.v1', 'origin': 'local-rootless-job',
            'authority': 'none', 'verification': 'not-independent-attestation',
            'plan_sha256': digest, 'workspace': record['workspace'],
            'journal_state': state, 'execution_status': result,
            'workspace_sha256_before': before,
            'workspace_sha256_after': after if state == 'finished' else None,
            'guest_output_included': False, 'tenant_execution_enabled': False,
            'note': 'Local operator-only result. An interrupted record must not be retried. Never interpret this as a production isolation attestation.'}
