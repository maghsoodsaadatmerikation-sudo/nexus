#!/usr/bin/env python3
"""Fail closed if untrusted PR code can acquire publication privileges.

This is intentionally a restrictive, standard-library-only gate, not a general
YAML parser. Unknown event/permission layouts fail instead of being guessed.
"""

from pathlib import Path
import re

WORKFLOWS = Path('.github/workflows')
PR_WORKFLOWS = ('pr-verify.yml', 'cloud-adapter.yml')
PRIVILEGED = (
    'v2.3-revocation-freshness.yml',
    'v2.4-gateway-authority-confusion.yml',
    'v2.5-transport-authentication.yml',
)


def require(condition: bool, message: str) -> None:
    # `assert` is disabled by `python -O` and is not a security control.
    if not condition:
        raise ValueError(message)


def event_block(source: str) -> str:
    match = re.search(r'(?m)^on:\s*\n(.*?)(?=^[A-Za-z][\w-]*:|\Z)', source, re.S | re.M)
    if match is None:
        raise ValueError('missing or unsupported top-level workflow events')
    return match.group(1)


def event_names(events: str) -> set[str]:
    names: set[str] = set()
    first = True
    for line in events.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        # Support the documented two-space workflow-event map only. Reject
        # quoted keys, YAML aliases and irregular nesting rather than miss a
        # dangerous trigger hidden behind valid but unexpected YAML syntax.
        if first:
            require(line.startswith('  ') and not line.startswith('   '),
                    'unsupported workflow event indentation')
            first = False
        if line.startswith('  ') and not line.startswith('   '):
            m = re.match(r'^  ([a-z][a-z_]*):(?:\s|$)', line)
            require(m is not None, f'unsupported workflow event key: {line.strip()}')
            require(m.group(1) not in names,
                    f'duplicate workflow event: {m.group(1)}')
            names.add(m.group(1))
    require(bool(names), 'workflow has no supported events')
    return names


def has_event(events: str, name: str) -> bool:
    return name in event_names(events)


def permissions(source: str, filename: str) -> list[tuple[int, dict[str, str]]]:
    """Read conventional block-style permissions; disallow ambiguous syntax.

    GitHub permits `permissions: write-all`, inline maps and nested overrides.
    Instead of trying to approximate arbitrary YAML, this PR safety gate only
    admits explicit block-style permission maps and rejects other forms.
    """
    lines = source.splitlines()
    blocks: list[tuple[int, dict[str, str]]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r'(?P<indent> *)permissions:\s*(?P<tail>.*)', line)
        if match is None:
            continue
        indent = len(match['indent'])
        tail = match['tail'].split('#', 1)[0].strip()
        require(not tail, f'{filename}: inline/scalar permissions are forbidden')
        values: dict[str, str] = {}
        for child in lines[index + 1:]:
            if not child.strip() or child.lstrip().startswith('#'):
                continue
            child_indent = len(child) - len(child.lstrip(' '))
            if child_indent <= indent:
                break
            # Only an unambiguous simple map is permitted, never nested expressions.
            match_child = re.fullmatch(
                r' {' + str(indent + 2) + r'}([a-z][a-z-]*):\s*(none|read|write)\s*(?:#.*)?',
                child,
            )
            require(match_child is not None,
                    f'{filename}: unsupported permissions entry: {child.strip()}')
            scope, access = match_child.groups()
            require(scope not in values, f'{filename}: duplicate permission {scope}')
            values[scope] = access
        require(bool(values), f'{filename}: empty permission map')
        blocks.append((indent, values))
    return blocks


def check() -> None:
    paths = sorted({*WORKFLOWS.glob('*.yml'), *WORKFLOWS.glob('*.yaml')})
    require(bool(paths), 'no workflow files were found')
    for path in paths:
        source = path.read_text(encoding='utf-8')
        events = event_block(source)
        require(not has_event(events, 'pull_request_target'),
                f'{path.name}: pull_request_target is forbidden')
        if has_event(events, 'pull_request'):
            blocks = permissions(source, path.name)
            root_blocks = [p for indent, p in blocks if indent == 0]
            require(len(root_blocks) == 1 and root_blocks[0] == {'contents': 'read'},
                    f'{path.name}: PR workflow must explicitly grant only contents: read')
            for _indent, mapping in blocks:
                require(all(access != 'write' for access in mapping.values()),
                        f'{path.name}: PR workflow may not request write permissions')
        # Fail closed if a scalar event alias could hide a PR trigger.
        require(not re.search(r'(?m)^on:\s*\[', source),
                f'{path.name}: inline event declarations are unsupported')

    for name in PR_WORKFLOWS:
        path = WORKFLOWS / name
        require(path.is_file(), f'missing required PR workflow {name}')
        source = path.read_text(encoding='utf-8')
        events = event_block(source)
        require(has_event(events, 'pull_request'), f'{name}: missing pull_request trigger')
        # Its read-only permissions were verified by the generic PR pass above.

    for name in PRIVILEGED:
        path = WORKFLOWS / name
        require(path.is_file(), f'missing protected privileged workflow {name}')
        source = path.read_text(encoding='utf-8')
        events = event_block(source)
        require(has_event(events, 'push'), f'{name}: missing push trigger')
        require(re.search(r'(?m)^    branches: \[main\]\s*$', events) is not None,
                f'{name}: privileged workflow must target main')
        require(not has_event(events, 'pull_request'),
                f'{name}: privileged workflow must not run untrusted PRs')
        block_maps = [p for _indent, p in permissions(source, name)]
        require(any(p.get('id-token') == 'write' and p.get('attestations') == 'write'
                    for p in block_maps), f'{name}: missing attestation permissions')


if __name__ == '__main__':
    check()
    print('WORKFLOW AUTHORITY BOUNDARY: PASS')
