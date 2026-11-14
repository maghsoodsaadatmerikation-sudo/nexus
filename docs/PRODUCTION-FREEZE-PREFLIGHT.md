# Production freeze preflight: Render + GitHub settings

Status: SOURCE-ONLY / UNSEALED. The command is an **offline diagnosis of
operator-supplied metadata**. It does not connect to providers, capture a backup,
prove source authenticity, permit merging, deploy or authorize a release.

## Why a new gate is necessary

The current Render legacy service `nexus` (ID
`srv-dabhmn0u01pc73b1v1og`) was observed on 14 November 2026 with
`autoDeploy=yes`, `autoDeployTrigger=commit`, tracking `main`.
A merge into `main` can therefore change the Docker backend without an
independent production recovery gate. The GitHub main ruleset ID
`20870033` was read on the same date with
`strict_required_status_checks_policy=false`. This allows required-check
results from an older base to remain eligible for merging.

The required safe controls are **Render autoDeployTrigger=off** and a GitHub
ruleset that covers the default branch, requires PRs, prevents deletion and
force-push, and requires strict/up-to-date `readonly-verification`.
These are *provider settings*, not just repository files. Editing
`render.yaml` or adding a repository test **does not change them**.
Treat missing or redacted bypass actor information as unknown, not empty.

## Operator action: no redeploy or backup modification

1. At the existing Render service's Settings > Auto-Deploy, choose **Off**.
   Read the service settings back using an authorized Render service read;
   require both `autoDeployTrigger: off` and `autoDeploy: no`.
   Do not infer an existing service's configuration from a Blueprint alone.
2. GitHub > Settings > Rules > Rulesets > Merikation (ID 20870033):
   require branches to be up to date before merging; preserve
   `readonly-verification`, required PR, no deletion/force push, and
   inspect bypass scope with authorized settings access. Read the *actual*
   ruleset back; require `strict_required_status_checks_policy: true`.
3. Independently establish an encrypted, off-host **complete** production
   volume backup, point-in-time provenance and successful isolated restore.
   Never test destructive restore on the mounted production `/data`.
4. Run exact candidate CI again after the protected base and provider settings
   are stable. Keep pending integration PRs as draft until real recovery has
   independently passed.

## Offline executable check

Create a **private** JSON file from current sanitized provider GET responses,
using this envelope. This is a shape example, not real provider evidence.
Do not commit snapshots, tokens, private paths or raw backup material.

```json
{
  "schema": "nexus.production-freeze-observation.v1",
  "observed_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "render": {"id": "provider service metadata"},
  "github_ruleset": {"id": 20870033},
  "github_main_ref": {"ref": "refs/heads/main", "object": {"sha": "current 40-hex SHA", "type": "commit"}}
}
```

The `render` and `github_ruleset` objects must contain their actual
complete enough **read-only** GET fields, including Render repo, branch,
runtime, autoDeploy and autoDeployTrigger, and ruleset source, conditions,
rules, bypass_actors and current_user_can_bypass. Do not substitute the
illustrative objects above for real provider responses.

```bash
python3 scripts/production-freeze-preflight.py private-sanitized-observation.json \
  --expected-main-sha <EXACT_CURRENT_MAIN_SHA>
```

The tool rejects symlinks/hardlinks, duplicate JSON keys, invalid shapes and
stale metadata (older than 30 minutes or more than 2 minutes into the future).
It never prints provider input, file paths or tokens. Exit 1 means a configuration
blocker. Exit 2 means invalid/unsafe input. Exit 0 means **only** the supplied
input is internally consistent with the intended frozen configuration.
`CONSISTENT_INPUT_ONLY` is deliberately **not** a production-green signal:
the tool cannot authenticate the supplied file, test a real backup or
authorize a GitHub merge. Separate human approval is always required.

```bash
python3 scripts/test-production-freeze-preflight.py
```

This adversarial synthetic suite runs in a dedicated read-only PR workflow and
in the existing required `readonly-verification` job. CI exercises code
behavior but never calls Render or GitHub settings APIs with write permissions.

## Current integration blockers

- #154: Render remains commit-autodeploy; real off-host backup and independent
  production restore are not established.
- #168: main ruleset does not yet require strict up-to-date PR checks.
- #187: stricter public runtime observation is source-only, not merged.
- The Stage D Railway environment still has a staged patch; it is not a safe
  substitute for independently verifying the original persistent volume.

`A_out <= A_in`; evidence is not release authority.
