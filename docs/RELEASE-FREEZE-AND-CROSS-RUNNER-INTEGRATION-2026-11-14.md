# Release safety candidate: freeze verification + cross-runner synthetic restore

Date: 2026-11-14
Base candidate: PR #203, head `f27f806fbf44fb424d715d3db049b7820f04ed15`.
Status: **DRAFT / SOURCE VERIFICATION ONLY / NO PRODUCTION AUTHORITY**.

## Problems addressed by this composition

PR #203 consolidates hardening and has passing CI, but two required operational
controls cannot be inferred from repository test results: (a) Render can deploy
unreviewed main commits, (b) GitHub branch protection may permit stale required
checks. Also, same-runner synthetic restore does not test transfer of a complete
workspace + request ledger to a separately scheduled runner.

Integrates two previously independently tested source-only PRs while preserving
exact Git blob identities:

### PR #188 — freeze preflight
Source commit `851e68aec2416bd6a54ea3a0e734e0205347c685`.

- `scripts/production-freeze-preflight.py`: `67004efa104f9932bcf262e53c8e497c8fd81d4d`
- `scripts/test-production-freeze-preflight.py`: `1802953a0671bef7464bc5f18eaf58759570686f`
- `docs/PRODUCTION-FREEZE-PREFLIGHT.md`: `758da07b0c7d4d9b605626d9aab3a3c814fe8db9`
- `.github/workflows/production-freeze-preflight.yml`: `e5e14092b1685b9246a31324f0c45983308ecb59`

The script parses a *private, sanitized, operator-supplied* snapshot.
It refuses oversized/symlinked or malformed/ambiguous JSON; checks observation
freshness and exact main SHA; requires Render auto-deploy disabled and a
GitHub ruleset with fresh up-to-date required checks. It never grants merge,
deployment or seal authority even if the supplied metadata is consistent.
The full adversarial unit suite is now run by the existing required
`readonly-verification` status, not merely in an optional workflow.

### PR #189 — separate GitHub Actions runners, synthetic records only
Source commit `e0660f330ee80f6ed12db44730cb594cc7bf5703`.

- `scripts/pilot-cross-runner-recovery.py`: `b4113ca9d7301dd48510a8433c681e2376d739a9`
- `docs/PILOT-CROSS-RUNNER-RECOVERY.md`: `bd76958b5beeb363ed11f29b775bf794a28c19c4`
- `.github/workflows/pilot-cross-runner-recovery.yml`: `07688b9ef3cfbef7ae79611f37c17bb1a4833b45`

A source job builds a disposable gateway, writes synthetic workspace and
request ledger records, stops writers, archives the synthetic volume and
uploads just its archive and SHA-256 receipt. A separate recipient GitHub job
downloads the exact artifact ID, rebuilds the gateway, rejects a corrupted
archive, restores a fresh directory and validates quarantine, readback and
post-resume request semantics. It uses no real production data or secrets.
The independent full workflow runs on this candidate PR. Its read-only
`self-test` also runs in the required `readonly-verification` job.

## Current observed state (read-only provider inspection on 2026-11-14)

Render service `srv-dabhmn0u01pc73b1v1og`: branch `main`,
`autoDeploy=yes`, `autoDeployTrigger=commit`.
GitHub ruleset `Merikation` ID `20870033`: enforced and requires
`readonly-verification`, but
`strict_required_status_checks_policy=false`.

Therefore the **production freeze preflight is BLOCKED**.
These observations are not provider signed attestations and become stale.
A passing synthetic preflight *test* does not mean real settings are frozen.

## Release hold

- Do not merge this PR or its base #203 to `main`: Render still auto-deploys.
- Do not relax the hold until a properly authorized operator changes Render
  auto-deploy **off**, enables strict GitHub up-to-date checks, and reads back
  both provider configurations.
- Require independently witnessed encrypted offsite **real** full-volume
  backup and isolated cold restore (workspace + ledger, with recovery gate).
  Cross-runner synthetic CI is necessary evidence of code behavior but
  does not inspect any actual host volume, independently held keys or custody.
- Recheck all required CI statuses on the final base/current candidate SHA.
  PR #188/#189 tests are source code and synthetic evidence, not provider
  authority. Real deployment, release tags and Stage D Seal remain blocked.

No production secrets, hosted settings, user data, provider deployment,
release tags or `main` commit were changed by this integration.
