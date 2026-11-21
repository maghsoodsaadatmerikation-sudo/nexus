#!/usr/bin/env python3
"""Static, fail-closed CI authority gate for the repository's restricted YAML style.

This intentionally is NOT a general-purpose YAML parser. Security-critical workflow
keys must use explicit block mappings. Unknown/ambiguous spellings fail closed.
The check protects against accidental privilege widening, not malicious edits to
this verifier by someone with repository write access.
"""
from __future__ import annotations

from pathlib import Path
import re

WORKFLOWS = Path('.github/workflows')
PRIVILEGED = (
    'v2.3-revocation-freshness.yml',
    'v2.4-gateway-authority-confusion.yml',
    'v2.5-transport-authentication.yml',
)
PR_WORKFLOWS = ('pr-verify.yml', 'cloud-adapter.yml')
UNTRUSTED_EVENTS = {'pull_request', 'merge_group', 'issue_comment', 'issues',
                    'discussion', 'discussion_comment', 'pull_request_review',
                    'pull_request_review_comment', 'workflow_call'}
# pull_request_target executes in a privileged base-repository context; reject
# it outright even when a permissions block appears read-only.
FORBIDDEN_EVENTS = {'pull_request_target'}
SCOPES = {'actions', 'attestations', 'checks', 'contents', 'deployments',
          'discussions', 'id-token', 'issues', 'models', 'packages', 'pages',
          'pull-requests', 'repository-projects', 'security-events', 'statuses'}
ROOT_KEY = re.compile(r'^([a-zA-Z][a-zA-Z0-9_-]*):(.*)$')
ITEM_KEY = re.compile(r'^([a-zA-Z][a-zA-Z0-9_-]*):(.*)$')


class BoundaryError(ValueError):
    """Unsupported syntax or a violation of the trust boundary."""


def fail(name: str, detail: str) -> None:
    raise BoundaryError(f'{name}: {detail}')


def block_only(value: str, name: str, key: str) -> None:
    if value.strip() and not value.lstrip().startswith('#'):
        fail(name, f'{key} must be an explicit block mapping')


def sections(source: str, name: str) -> dict[str, tuple[str, list[str]]]:
    if '\t' in source or source.startswith('\ufeff'):
        fail(name, 'tabs and BOM are unsupported in workflow security review')
    lines = source.splitlines()
    roots: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if not line.startswith(' '):
            m = ROOT_KEY.fullmatch(line)
            if not m:
                fail(name, f'unrecognized top-level YAML at line {i + 1}')
            roots.append((i, m[1], m[2]))
    result = {}
    for k, (i, key, value) in enumerate(roots):
        if key in result:
            fail(name, f'duplicate top-level {key}')
        end = roots[k + 1][0] if k + 1 < len(roots) else len(lines)
        result[key] = (value, lines[i + 1:end])
    if 'on' not in result or 'jobs' not in result:
        fail(name, 'required top-level on/jobs mapping missing')
    return result


def items(body: list[str], indent: int, name: str, context: str) -> dict[str, tuple[str, int]]:
    mapping: dict[str, tuple[str, int]] = {}
    for i, line in enumerate(body):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if len(line) - len(line.lstrip(' ')) == indent:
            m = ITEM_KEY.fullmatch(line[indent:])
            if not m:
                fail(name, f'unsupported {context} mapping syntax, line {i + 1}')
            key, value = m[1], m[2]
            if key in mapping:
                fail(name, f'duplicate {context}.{key}')
            mapping[key] = value, i
        elif len(line) - len(line.lstrip(' ')) < indent:
            fail(name, f'unsupported indentation under {context}')
    return mapping


def parse_permissions(value: str, body: list[str], indent: int, name: str, context: str) -> dict[str, str]:
    block_only(value, name, context)
    fields = items(body, indent, name, context)
    parsed = {}
    for key, (raw, _) in fields.items():
        if key not in SCOPES:
            fail(name, f'unknown or unsupported permission scope {context}.{key}')
        setting = raw.split(' #', 1)[0].strip()
        if setting not in {'read', 'write', 'none'}:
            fail(name, f'nonliteral or unsupported permission {context}.{key}')
        parsed[key] = setting
    return parsed


def inspect_workflow(source: str, name: str) -> tuple[set[str], dict[str, str]]:
    parts = sections(source, name)
    on_value, on_body = parts['on']
    block_only(on_value, name, 'on')
    events = items(on_body, 2, name, 'on')
    if not events:
        fail(name, 'workflow events cannot be empty')
    for event, (value, _) in events.items():
        block_only(value, name, f'on.{event}')
    triggers = set(events)
    if triggers & FORBIDDEN_EVENTS:
        fail(name, 'pull_request_target is prohibited')

    # Every workflow must override repository-default GITHUB_TOKEN permissions.
    if 'permissions' not in parts:
        fail(name, 'explicit workflow-level token permissions missing')
    value, body = parts['permissions']
    global_perms = parse_permissions(value, body, 2, name, 'permissions')

    job_value, job_body = parts['jobs']
    block_only(job_value, name, 'jobs')
    jobs = items(job_body, 2, name, 'jobs')
    if not jobs:
        fail(name, 'workflow has no jobs')
    for job, (value, _) in jobs.items():
        block_only(value, name, f'jobs.{job}')

    if triggers & UNTRUSTED_EVENTS:
        # Explicit read-only PR token; never inherit an uncertain repository default.
        if global_perms.get('contents') != 'read':
            fail(name, 'untrusted workflow requires explicit contents: read')
        if any(v == 'write' for v in global_perms.values()):
            fail(name, 'untrusted workflow cannot have write permissions')

    # Job-level permissions override workflow-level permissions.
    indices = sorted((at, job) for job, (_, at) in jobs.items())
    for j, (start, job) in enumerate(indices):
        stop = indices[j + 1][0] if j + 1 < len(indices) else len(job_body)
        job_lines = job_body[start + 1:stop]
        job_items = items(job_lines, 4, name, f'jobs.{job}')
        if 'permissions' in job_items:
            raw, line_idx = job_items['permissions']
            rest = job_lines[line_idx + 1:]
            next_peer = next((i for i, line in enumerate(rest)
                              if line.strip() and not line.lstrip().startswith('#')
                              and len(line) - len(line.lstrip(' ')) <= 4), len(rest))
            job_perms = parse_permissions(raw, rest[:next_peer], 6, name, f'jobs.{job}.permissions')
            if triggers & UNTRUSTED_EVENTS and any(v == 'write' for v in job_perms.values()):
                fail(name, f'job {job} widens PR permissions')

    return triggers, global_perms


def check(directory: Path = WORKFLOWS) -> None:
    paths = sorted(directory.glob('*.yml')) + sorted(directory.glob('*.yaml'))
    if not paths:
        fail(str(directory), 'no workflow files found')
    summaries = {}
    for path in paths:
        source = path.read_text(encoding='utf-8')
        events, perms = inspect_workflow(source, path.name)
        summaries[path.name] = (events, perms, source)

    for filename in PR_WORKFLOWS:
        if filename not in summaries or 'pull_request' not in summaries[filename][0]:
            fail(filename, 'required read-only PR entry point missing')

    for filename in PRIVILEGED:
        if filename not in summaries:
            fail(filename, 'required privileged verification workflow missing')
        events, perms, source = summaries[filename]
        if events - {'push', 'workflow_dispatch'} or 'push' not in events:
            fail(filename, 'attesting verification may run only on push/main or manual dispatch')
        # Only literal, exact push-on-main branches are an accepted publication source.
        event_body = sections(source, filename)['on'][1]
        event_map = items(event_body, 2, filename, 'on')
        push_at = event_map['push'][1]
        following = sorted(i for e, (_, i) in event_map.items() if i > push_at)
        push_lines = event_body[push_at + 1:(following[0] if following else len(event_body))]
        push_options = items(push_lines, 4, filename, 'on.push')
        if set(push_options) != {'branches'} or push_options['branches'][0].strip() != '[main]':
            fail(filename, 'attesting push must target only literal [main]')
        if perms.get('id-token') != 'write' or perms.get('attestations') != 'write':
            fail(filename, 'required publish permissions are missing or ambiguous')


if __name__ == '__main__':
    check()
    print('WORKFLOW AUTHORITY BOUNDARY: PASS')
