#!/usr/bin/env python3
"""Read-only exact-SHA check of six stacked NEXUS development PRs.

Development preflight ONLY. Never authorizes deployment or live data changes.
"""
import argparse
import json
import os
import re
import sys
from urllib.request import Request, urlopen

REPO = 'maghsoodsaadatmerikation-sudo/nexus'
CHAIN = [
    (129, 'main', 'fix/workspace-storage-integrity-20261112'),
    (130, 'fix/workspace-storage-integrity-20261112', 'fix/execution-admission-20261112'),
    (131, 'fix/execution-admission-20261112', 'feat/source-grounded-chat-20261112'),
    (132, 'feat/source-grounded-chat-20261112', 'feat/optional-chat-history-20261112'),
    (133, 'feat/optional-chat-history-20261112', 'feat/optional-app-connections-20261112'),
    (134, 'feat/optional-app-connections-20261112', 'feat/work-mode-20261113'),
]
REQUIRED = {'readonly-verification', 'verify', 'local-pilot',
            'offline-pilot-browser', 'public-ui-readonly', 'disposable-real-browser'}
SHA = re.compile(r'^[0-9a-f]{40}$')

class Blocked(Exception):
    pass

def require(condition, message):
    if not condition:
        raise Blocked(message)

def validate(metadata):
    require(isinstance(metadata, dict) and metadata.get('repository') == REPO, 'wrong-repository')
    main = metadata.get('main_sha')
    require(isinstance(main, str) and SHA.fullmatch(main), 'invalid-main-sha')
    prs = metadata.get('prs')
    require(isinstance(prs, list) and len(prs) == len(CHAIN), 'incomplete-stack')
    parent, report, seen = main, [], {main}
    for pr, (number, expected_base, expected_head) in zip(prs, CHAIN):
        require(type(pr) is dict and pr.get('number') == number, 'unexpected-pr')
        require(pr.get('state') == 'open' and pr.get('draft') is False,
                f'pr-{number}-not-open-ready')
        require(pr.get('mergeable') is True, f'pr-{number}-mergeability-unknown-or-blocked')
        require(pr.get('base_ref') == expected_base and pr.get('head_ref') == expected_head,
                f'pr-{number}-branch-chain-changed')
        require(pr.get('base_sha') == parent, f'pr-{number}-parent-commit-changed')
        head = pr.get('head_sha')
        require(isinstance(head, str) and SHA.fullmatch(head) and head not in seen,
                f'pr-{number}-invalid-or-reused-head')
        seen.add(head)
        checks = pr.get('checks')
        require(isinstance(checks, list) and 1 <= len(checks) <= 100,
                f'pr-{number}-check-list-absent-or-over-cap')
        by_name = {}
        for c in checks:
            require(isinstance(c, dict) and isinstance(c.get('name'), str),
                    f'pr-{number}-invalid-check-record')
            name = c['name']
            require(name not in by_name, f'pr-{number}-duplicate-check')
            require(c.get('head_sha') == head and c.get('status') == 'completed' and
                    c.get('conclusion') == 'success', f'pr-{number}-nonpassing-check')
            by_name[name] = c
        needed = REQUIRED | ({'research-chat'} if number >= 131 else set())
        require(needed <= by_name.keys(), f'pr-{number}-required-check-missing')
        report.append({'pr': number, 'sha': head, 'successful_checks': len(checks)})
        parent = head
    return {
        'schema': 'nexus.stage21.development-stack-preflight.v1',
        'status': 'STACK_INTEGRATION_CHECKS_PASS__PRODUCTION_BLOCKED',
        'repository': REPO, 'main_sha': main, 'candidate_head_sha': parent,
        'stack': report,
        'original_railway_volume_recovery': 'UNPROVEN',
        'independent_real_restore': 'NOT_PROVEN',
        'production_merge_authorized': False,
        'deployment_authorized': False,
        'release_seal': False,
        'human_judgment_authority': 'retained',
    }

def github_json(path):
    token = os.getenv('GITHUB_TOKEN', '')
    require(os.getenv('GITHUB_ACTIONS') == 'true' and len(token) > 10,
            'live-mode-requires-readonly-github-actions-token')
    url = f'https://api.github.com/repos/{REPO}/{path}'
    req = Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'nexus-readonly-stage21-preflight',
    })
    with urlopen(req, timeout=15) as response:
        require(response.status == 200, 'github-read-failed')
        raw = response.read(512 * 1024 + 1)
        require(len(raw) <= 512 * 1024, 'github-response-too-large')
    return json.loads(raw)

def collect_live():
    main = github_json('branches/main')['commit']['sha']
    output = {'repository': REPO, 'main_sha': main, 'prs': []}
    for number, _, _ in CHAIN:
        pr = github_json(f'pulls/{number}')
        sha = pr['head']['sha']
        result = github_json(f'commits/{sha}/check-runs?per_page=100')
        require(result.get('total_count') == len(result.get('check_runs', [])),
                f'pr-{number}-check-results-truncated')
        output['prs'].append({
            'number': number, 'state': pr['state'], 'draft': pr['draft'],
            'mergeable': pr['mergeable'],
            'base_ref': pr['base']['ref'], 'base_sha': pr['base']['sha'],
            'head_ref': pr['head']['ref'], 'head_sha': sha,
            'checks': [
                {'name': c['name'], 'head_sha': c['head_sha'],
                 'status': c['status'], 'conclusion': c['conclusion']}
                for c in result['check_runs']
            ]
        })
    # Re-read heads to detect a moving PR during metadata collection.
    require(github_json('branches/main')['commit']['sha'] == main, 'main-moved-during-observation')
    for pr in output['prs']:
        now = github_json(f"pulls/{pr['number']}")
        require(now['head']['sha'] == pr['head_sha'] and
                now['base']['sha'] == pr['base_sha'] and
                now['state'] == 'open', f"pr-{pr['number']}-moved-during-observation")
    return output

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--fixture')
    args = parser.parse_args()
    try:
        if args.live:
            data = collect_live()
        else:
            with open(args.fixture, 'rb') as f:
                raw = f.read(256 * 1024 + 1)
            require(len(raw) <= 256 * 1024, 'fixture-too-large')
            data = json.loads(raw)
        print(json.dumps(validate(data), sort_keys=True, separators=(',', ':')))
        return 0
    except (Blocked, OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({'schema':'nexus.stage21.development-stack-preflight.v1',
                          'status':'BLOCKED', 'reason':str(e),
                          'production_merge_authorized':False,
                          'deployment_authorized':False, 'release_seal':False},
                         sort_keys=True))
        return 1
    except Exception:
        print(json.dumps({'status':'BLOCKED', 'reason':'unexpected-read-error',
                          'deployment_authorized':False, 'release_seal':False}))
        return 1

if __name__ == '__main__':
    sys.exit(main())
