# Engineering-agent expansion: a truthful Grok-inspired implementation matrix

This is an **incremental implementation**, not a claim to recreate Grok's model,
private xAI services, judgment quality, unbounded web access or safety policy.
No external company implementation has been copied. The user-supplied comparison
is treated as a requirements list, not proof of vendor features.

## Added in this change (operator-only, not deployed to Studio)

- `nexus-cloud/agent_workspace.py`: a private, named workspace with bounded
  file read, atomic write, exact-once edit and ZIP archive. File traversal uses
  directory file descriptors and `O_NOFOLLOW`, rejects hardlinks and special
  files; files persist on the operator's local disk between invocations.
- `scripts/nexus-agent-workspace.py`: an explicit local CLI for those operations.
  `run` requires `--approve-run`, a **digest-pinned** container image and a
  Docker daemon. It uses a nonroot UID/GID, drops all Linux capabilities,
  disables networking, uses a read-only container root, and bounds CPU, memory,
  PID count, output and duration. Only the selected private workspace is bind
  mounted read/write; no host home, Docker socket or secrets are mounted.
- `Workspace.manifest()` and the CLI `manifest` command give a bounded,
  deterministic SHA-256 of all visible workspace files (including dotfiles) and
  empty directories; symlinks/hardlinks/special files fail closed. A **version 2**
  plan requires `expected_workspace_sha256` and refuses to execute if the
  current snapshot differs, *before the first side effect*. This prevents stale
  plan approval for a changed workspace at execution start. Filesystem contents
  can still race after the preflight check; this is not a transactional lock or
  an isolation guarantee against concurrent writers or container processes.
- `nexus-cloud/engineering_agent.py` and `scripts/nexus-engineering-plan.py`:
  a deterministic, 12-step maximum execution plan supporting `read`, `write`,
  `edit`, `run`, `verify_sha256`, `package`. The complete plan is canonicalized
  and hashed before any action. Execution requires an **exact SHA-256 approval**
  supplied separately by the local operator. Changed plan/unknown tool/extra
  parameter fail closed. A per-step result receipt is machine-readable, with
  only output hashes for command execution. Failed verification stops the plan;
  already written files are not rolled back.
- **Operator-only code inspection and patch review**: `Workspace.search()` provides
  Unicode-aware literal search through bounded UTF-8 project files, with path/line
  labels and at most 50 visible excerpts. Invalid UTF-8 and NUL-containing files
  are skipped; links, hardlinks and special files deny scanning. `preview_edit()`
  compares an exact-once replacement as a bounded unified diff plus proposed SHA-256;
  it **does not write** any file. Preview refuses large/expensive diffs. The new
  `search` and `preview_edit` plan steps and local CLI support review-before-edit.
- **User-approved public developer metadata**: `nexus-cloud/agent_research.py`
  reads *only* PyPI, crates.io, or GitHub latest-release metadata by fixed HTTPS
  endpoints with restricted name syntax. No arbitrary URL, proxy inheritance,
  redirect, credentials, dynamic hostname, method, or header is exposed. Each
  request has an 8-second timeout and a 1 MiB response cap. A source URL,
  timestamp, raw response SHA-256 and explicitly **unverified** provenance label
  accompany the reported version. The `research` plan step needs the same exact
  operator-approved plan digest; direct CLI use needs `--approve-research`.
  This HTTPS metadata fetch occurs in the local operator process, **outside the
  Docker runner**, which stays `--network none`; it is not general search or
  network-enabled execution. Real provider availability has not been verified
  by these offline/mock-based tests. Remote metadata is inert untrusted text.
- Tests cover path traversal, symlink escape, hardlinks, FIFO handling, bounds,
  persistence, ZIP, approval, image pinning, fixed Docker invocation and
  plan mutation, and run as an independent CI check without Docker credentials.

This opt-in worker is **not an unauthenticated network API** and is deliberately
not wired to model outputs or the public cloud adapter. Docker is unavailable on
some hosts; the tests mock Docker arguments, so a real Docker execution PASS
still requires an actual operator-host test. A container image by digest is
immutable-addressed, **not** automatically trusted or vulnerability-free.
Docker daemon privilege/rootless configuration and host hardening remain the
operator's responsibility. A Linux Docker sandbox is not equivalent to a hardened
multitenant VM/microVM isolation boundary.

### Preview and execute a plan

Create an existing dedicated local directory owned by an unprivileged user,
with permission mode 0700. Example `plan.json`:

```json
{
  "version": 2,
  "workspace": "demo",
  "expected_workspace_sha256": "<64-character SHA-256 from the manifest command>",
  "steps": [
    {"tool": "write", "path": "hello.py", "text": "print('Hello NEXUS')\n"},
    {"tool": "read", "path": "hello.py"}
  ]
}
```

```bash
mkdir -m 700 -p "$HOME/nexus-workspaces"
python scripts/nexus-agent-workspace.py --root "$HOME/nexus-workspaces" --workspace demo manifest
# Put the returned sha256 under expected_workspace_sha256 in plan.json.
python scripts/nexus-engineering-plan.py --root "$HOME/nexus-workspaces" --plan plan.json
# Inspect the plan, and copy the returned plan_sha256 after independent review.
python scripts/nexus-engineering-plan.py --root "$HOME/nexus-workspaces" \
  --plan plan.json --approve-digest '<reviewed-plan-sha256>'
```

For a Docker run step, supply `{"tool":"run","image":"trusted-repo@sha256:<64 lowercase hex>","argv":["python","hello.py"],"timeout_seconds":30}`.
It has **no internet** and cannot install new packages from the network;
prebuilt, pinned images supply dependencies. A local `run` command can also be
invoked directly through `scripts/nexus-agent-workspace.py` with `--approve-run`.
Do not use the user's primary home directory as workspace root, run as root,
mount secrets, or expose the Docker daemon to untrusted parties.

## Actual capability coverage

| Grok-inspired capability | NEXUS state after this PR | Remaining dependency |
| --- | --- | --- |
| Persistent Linux filesystem | Local private per-workspace directory **implemented** | Remote multi-tenant persistence, quotas and lifecycle |
| Shell / Python / Rust / Go / C++ | Docker foreground runner **implemented** behind operator approval | Pinned runtime images, real Docker acceptance, arbitrary task portability |
| Multi-file read/write/edit + ZIP | **Implemented** with bounded file operations, literal code search and nonmutating diff previews | Semantic indexing and frontend diff review |
| Tool-using agent loop | Deterministic reviewed multi-tool plan **implemented** | Reliable model planner, step-by-step consent in Studio, evaluation |
| Internet inside sandbox | **Not enabled**; `--network none` is mandatory | Restrictive authenticated egress proxy, DNS/SSRF policy, rate/budget consent |
| Background processes / long jobs | **Not implemented** | Durable queue, lease/recovery, cancellation and accounting |
| Web search/current API verification | Existing Wikipedia/Crossref UI and operator-only fixed-provider package/release metadata | General web search, independent source verification and full-page retrieval |
| Browser automation/screenshots/network traces | **Not implemented** | Isolated browser, domain allowlist, explicit user review |
| GitHub operations | GitHub integration possible externally with user-granted access | Per-action OAuth scopes + NEXUS constitutional authorization |
| DOCX, PPTX, XLSX, PDF, ffmpeg | Existing local basic file generation; new runner can run installed tools in pinned images | Format-specific adapters, golden-file visual QA, preview/consent |
| Image/video/audio input or generation | Existing browser/device tools only | Vision/media providers, consent, cost quotas and evaluation |
| X real-time search | **Not implemented** | Authorized X developer access, rate limits, attribution |
| Security/RE tools | Code execution tools are content-agnostic subject to limits | Formal abuse policy, audit, isolated test fixtures |
| Full model-level programming parity | **Not demonstrated** | Evaluation on real repositories against a benchmark suite |

## Integration gates

1. Retain `A_out <= A_in`: file/command tools can be exposed to Studio only after
   an operator- or user-scoped execution capability has been authorized by the
   NEXUS constitutional core. A model response is **not** an authorization.
2. Add a dedicated disposable runner service (prefer a microVM or similarly
   strong boundary for untrusted multi-user work); never attach the operator's
   Docker socket to a public HTTP service.
3. For optional internet add an egress proxy with explicit per-domain policies,
   size/time limits and protection against metadata/internal addresses.
4. Verify real Docker lifecycle and adversarial limits on an isolated machine;
   the static CI tests do not certify live runtime hardening.
5. Only then connect reviewed plans to Studio. Never claim the new features are
   live on the public hosted NEXUS site until independently observed there.

## Additional tools and approval examples (Grok-inspired phase 3)

```bash
# Search only the selected private project; output may include private snippets.
python scripts/nexus-agent-workspace.py --root "$HOME/nexus-workspaces" \
  --workspace demo search "TODO"

# Check a patch without changing files. before.txt/after.txt are local UTF-8 snippets.
python scripts/nexus-agent-workspace.py --root "$HOME/nexus-workspaces" \
  --workspace demo preview-edit hello.py --old-file before.txt --new-file after.txt

# Explicitly release one public metadata query, not the workspace contents.
python scripts/nexus-agent-workspace.py --root "$HOME/nexus-workspaces" \
  --workspace demo research --provider pypi --name httpx --approve-research
```

A version 2 approved plan can include `{"tool":"research","provider":"crates","name":"serde"}`,
`{"tool":"search","query":"TODO","case_sensitive":false}`, or
`{"tool":"preview_edit","path":"hello.py","before":"old","after":"new"}`.
The source is not an executable instruction or established truth. GitHub release
lookups may return 404 for a project without a conventional latest release; no
answer is fabricated. Search excerpts/plan receipts may contain private content
and should not be posted to public logs.

Tests for the code-inspection and metadata tools use local synthetic fixtures.
A separate real network acceptance check is still required on an appropriately
authorized operator host. The tooling is not a public Studio or API feature.

## Phase 4 — serialized execution and real Docker acceptance (16 November 2026)

This incremental candidate adds **advisory cross-process serialization** and
observable before/after project integrity to the reviewed engineering agent.
It is still an operator-only, local engineering capability, not a public
model-controlled shell or an auto-deployed NEXUS Studio feature.

- `Workspace.operation_lock()` takes an exclusive, time-bounded Linux `flock`
  on a private, persistent inode **outside** the hashed workspace directory.
  The lock is checked to be a single-link regular file owned by the current
  user, with no group/world permission. The lock is never unlinked while
  sessions may be active. This prevents two cooperating NEXUS CLI processes
  from approving and changing the same workspace simultaneously.
- Both approved whole-plan execution and the direct operator workspace CLI
  acquire this same lock. A second local CLI attempt fails with `workspace-busy`
  rather than silently overlapping a running plan. Individual `Workspace`
  library calls by third-party code remain an **internal API**, and callers
  using it directly must acquire the lock themselves.
- A `PlanReceipt` now records `workspace_sha256_before` and
  `workspace_sha256_after`. A failed sequence retains any earlier committed
  edits and records their actual final hash; there is **no rollback claim**.
  If a container or tool produces an invalid filesystem tree (e.g., symlink,
  special file, excessive size), the receipt reports `post-state-unverifiable`
  and never asserts a valid final snapshot.
- A separate, disposable GitHub-hosted CI job invokes a **real Docker daemon**,
  rather than mocking `subprocess.Popen`. It fetches BusyBox 1.36.1, obtains the
  pulled image's digest and passes that digest to the existing runner. It checks
  an unprivileged process, a workspace write, read-only container root and
  timeout/cleanup, with no repository write token or host secrets mounted.
  This verifies a particular CI host; it is **not** a multi-tenant isolation
  penetration test or evidence that all OCI images are trustworthy.

### Remaining trust boundary

`flock` is cooperative among processes using this implementation. Another
program using the same Unix account, a hostile host administrator or a running
container with a writeable workspace bind can still alter files; a plan-state
hash does not create an atomic snapshot of every external writer. This is why
neither the local Docker CLI nor its socket is exposed to remote users or
untrusted model outputs. A remote service still needs dedicated disposable
workers, authenticated policy mediation, nonshared storage, quotas and isolated
attestation. All CI claims must refer to an actually completed GitHub run;
adding a CI step is not evidence that the step has passed.

## Phase 5 — crash-conscious approval consumption and durable receipts

**Local operator-only; draft branch, not deployed into Studio or the public service.**

Every reviewed engineering plan (versions 1–3) now consumes its exact canonical
SHA-256 approval **at most once** on a particular private workspace root. Under
the existing cross-process workspace lock, after an optional workspace-state
check and **before any plan step**, the worker creates a 0600 exclusive journal
record and fsyncs its data and parent directory. The per-workspace 0700 journal
is adjacent to, not inside, the project's content manifest directory. Existing
completed or incomplete approvals deny replay, including read-only plans,
network metadata calls, and shell commands that produced no file changes.

A clean return atomically replaces the record with a bounded final receipt:
plan SHA-256, workspace SHA-256 before/after, execution status, and sanitized
per-step status. It deliberately **excludes** file text, source excerpts,
command output, API results and plan contents. If the process is terminated
between claim and completion, the record remains `started`; an operator can
inspect it but **cannot** implicitly resume/replay an unknown partial execution.
If final receipt persistence fails, the CLI reports an ambiguous result rather
than claiming success; the consumed approval remains unavailable.

**Plan v3** additionally requires both the complete workspace-state digest and
an independently generated, lowercase, 128-bit `execution_nonce` (32 hex
characters). A deliberately repeated operation must obtain a new nonce, a new
plan SHA-256 and a new explicit operator approval. The prior v1/v2 schemas
remain readable but new plans should use v3. An illustrative plan:

```json
{
  "version": 3,
  "workspace": "demo",
  "expected_workspace_sha256": "<current 64-hex digest from manifest>",
  "execution_nonce": "<fresh 32-hex nonce from secrets.token_hex(16)>",
  "steps": [{"tool": "read", "path": "hello.py"}]
}
```

```bash
# Review first (does not spend the approval):
python scripts/nexus-engineering-plan.py --root "$HOME/nexus-workspaces" --plan plan.json
# Execute with the exact reviewed digest, once:
python scripts/nexus-engineering-plan.py --root "$HOME/nexus-workspaces" \
  --plan plan.json --approve-digest '<plan_sha256>'
# Read a persisted sanitized receipt; this does NOT execute or grant approval:
python scripts/nexus-engineering-plan.py --root "$HOME/nexus-workspaces" \
  --plan plan.json --receipt
```

Receipts live on the *same host and filesystem*. They are **not** a distributed
exactly-once transaction, a signed audit log, an anti-root tamper seal, or a
rollback implementation. A privileged process, direct filesystem writes, host
loss, symlink races by an external co-owner, and Docker daemon access remain
outside this boundary. The operator must keep the private root, journal files,
backups and permissions intact. At most 1,024 retained records are allowed per
workspace; there is deliberately no automatic pruning of spent approvals.

The previous phase's **real Docker CI job passed** on commit `9370b9c` in a
disposable GitHub runner; this does not establish multi-tenant production safety.
Phase 5 adds positive and negative tests for read-only replay, partial failure,
crash-before-completion, forged/insecure journal paths, restrictive modes,
unique nonce reapproval, CLI receipt lookup, fsync failure and output privacy.
GitHub CI must independently validate this phase's new commit before promotion.

## Phase 6 — explicit NEXUS Studio ⇄ operator handoff (candidate, 16 November 2026)

This phase **does not** add a browser-controlled shell or an autonomous agent.
It adds an operator-only, local, file-based handoff between Studio's existing
**explicit text attachment** feature and the reviewed engineering CLI. The
proposal and executable code are *untrusted input*, not model authority.

### What is implemented

- `agent_chat_handoff.py`: a strict, bounded `nexus.engineering.proposal.v1`
  JSON intake. Duplicate keys, unknown fields, traversal paths, unpinned
  images, invalid command arguments, malformed numbers and excess steps are
  rejected through the same `engineering_agent.parse_plan` schema.
- `prepare` builds a **v3 private plan** from the live local workspace manifest
  and a new cryptographic execution nonce. It creates a 0600 file containing
  the complete private plan and a separate, sanitized review `.txt`. The
  review includes plan/workspace SHA-256, ordered tool types and risk flags,
  but **no file contents, filenames, shell arguments, provider results or logs**.
- `execute` requires the exact reviewed SHA-256 typed separately by the
  operator. It uses existing single-use approvals, workspace lock, bounded
  Docker and durable journal; there is no new execution bypass. It exports a
  separate sanitized `.txt` status receipt for the next Studio chat turn.
- `receipt` inspects an already claimed or finished plan **without rerunning**
  anything. An interrupted/started record is labeled ambiguous, never PASS.
- All output files are exclusive (`O_EXCL`, 0600), in a private operator-owned
  directory separate from workspace content. Candidate plan input is bounded,
  regular-file-only with no-follow semantics. Failed or stale approvals do not
  trigger local execution. Output artifacts and execution receipts are not
  stored on a hosted server by this bridge.

### Human-operated Studio workflow

Create dedicated 0700 folders for the local workspace and outbox. Take an
**untrusted** proposal from Studio's writing area or conversation into a local
`proposal.json` file, e.g.:

```json
{
  "schema": "nexus.engineering.proposal.v1",
  "workspace": "demo",
  "steps": [{"tool":"write", "path":"hello.py", "text":"print('hello NEXUS')\n"}]
}
```

```bash
mkdir -m 700 -p "$HOME/nexus-agent-workspaces" "$HOME/nexus-agent-outbox"
python scripts/nexus-chat-engineering.py prepare \
  --root "$HOME/nexus-agent-workspaces" --workspace demo \
  --proposal proposal.json --out "$HOME/nexus-agent-outbox"

# READ THE ENTIRE GENERATED PRIVATE nexus-plan-<prefix>.json BEFORE APPROVAL.
# The reviewed plan SHA-256 is printed in prepare's JSON output.
python scripts/nexus-chat-engineering.py execute \
  --root "$HOME/nexus-agent-workspaces" --workspace demo \
  --plan "$HOME/nexus-agent-outbox/nexus-plan-<prefix>.json" \
  --approve-digest '<EXACT-REVIEWED-64-HEX-PLAN-SHA256>' \
  --out "$HOME/nexus-agent-outbox"

# No execution — query the durable journal by a known local plan.
python scripts/nexus-chat-engineering.py receipt \
  --root "$HOME/nexus-agent-workspaces" --workspace demo \
  --plan "$HOME/nexus-agent-outbox/nexus-plan-<prefix>.json"
```

The operator may attach the resulting `nexus-review-*.txt` or
`nexus-result-*.txt` to **one next Studio chat message** using Studio's
existing **Attach text files** control, and then separately review/approve any
configured model send. Studio's local guide remains non-generative. Do **not**
attach the private `nexus-plan-*.json` to a hosted model unless the operator
intends to transmit its full contents; generated plans can include private
code, paths and commands. A review file contains only opaque hashes/statuses,
so a model cannot infer full implementation details from it.

### Limitations and admission gates

This bridge is a **manual local file exchange**, not a new native Studio tab,
remotely hosted service, model-controlled tool loop, or direct in-browser
execution. A prepared plan is **not** an approval; operator review and explicit
`execute` are still required. The local machine needs a compatible Linux
installation and a Docker daemon for `run` steps. Ctrl+C can leave a
**consumed** approval and partially changed files; inspect `receipt` and review
a **new** plan instead of silently retrying. The journal is local evidence, not
a cryptographic signature or independent attestation. No automatic cloud
persistence, cross-device sync, network-enabled container, background daemon or
untrusted multi-tenant isolation is added. Keep `A_out <= A_in`.

Verification: deterministic unit tests for hostile proposals, real local
prepare/execute/receipt, private export permissions, no-effect preview, stale
approval and replay denial, sanitized output, interruption-state labeling, and
oversized/symlink input denial. Dedicated CI must PASS at the committed SHA;
no deployment, merge or production readiness is implied by local test success.


## Phase 7 — Engineering review embedded in Studio (draft branch only)

- Add a conversation-area Engineering Agent panel with a strictly bounded, in-browser read-only parser for `nexus.engineering.proposal.v1`, `nexus.engineering.review.v1`, and `nexus.engineering.chat-receipt.v1`.
- Only sanitized summaries display step tool, risk, status, workspace digest and plan digest. Raw source/command strings remain in a private proposal textbox and are **never** silently staged into chat.
- Exact-content review and an explicit checkbox precede manual proposal download or summary handoff to the existing one-turn Studio chat attachment mechanism. Staged summaries still require separate per-message model-request review.
- No Docker process, shell, remote agent, GitHub write, privileged model tool call, or new server endpoint is invoked by the browser panel. Execution continues to require an operator-run v3 plan and its single-use approval journal; UI inspection is **not** executable approval.
- Input is bounded to 32,768 bytes with strict duplicate JSON-key detection, exact recognized field names, workspace and step checks, and status restrictions. A secure importer invalidates stale file reads after lock or chat/project switches. No proposal is saved to the Studio archive.
- Node contract tests, real Chromium narrow/wide behavioral checks, deterministic Studio bundle and static integrity verification are CI gates. Static site deployment is **not** part of this PR.
- The local operator remains responsible for full private plan examination and independent authorization, and the browser's parser is not equivalent to the operator's Python validator.


## Phase 10 — Private operator service and cancellation

The engineering agent now supports a **local, non-root Linux operator service**
over a private Unix socket (no HTTP listener or public Docker API). A 0600
random token plus Linux SO_PEERCRED same-user verification protects the local
channel. The owner chooses and reviews the **entire private plan** and supplies
the exact canonical digest; generated model text alone never grants authority.
A v3 nonce, workspace-state precondition and crash-conscious single-use journal
remain enforced. Replays are rejected.

Operator workflow:

1. Prepare a private v3 proposal using scripts/nexus-chat-engineering.py;
   store it in an owned 0700 outbox outside the owned 0700 workspace root.
2. Start scripts/nexus-operator-service.py with the serve action and --root
   in a foreground operator terminal. The token remains local and is never
   printed, transmitted to a browser or persisted in a transcript.
3. From another terminal use start --root --workspace --digest --plan after
   inspecting the complete plan. Submitted means queued, not verified.
4. Read status --root --workspace --digest; optional --out writes a sanitized
   0600 result file for manual import in the Studio Engineering Agent panel.
5. To request stopping an active plan, use stop --root --workspace --digest.
   Stop-requested is not completion; inspect a durable terminal receipt.
   When cancellation is observed it is recorded as CANCELLED, not PASS.
   File edits that happened before stop are NOT rolled back.

The socket refuses oversized or malformed JSON, duplicate keys, unsafe plan
paths, invalid peer identity or token, unapproved digests and multiple active
plans for one workspace. The protocol returns only status and sanitized
hashes/step summaries; raw code, stdout, stderr, passwords and source text
are not returned. A same-UID process is within the same operator trust domain:
this is **not** hostile same-user isolation or multi-tenant production hosting.

Local Python contract tests and CI cover replay, peer/token rejection,
privacy-preserving export, a simulated mid-command stop, and actual Docker
termination using a digest-pinned test image on an unprivileged ephemeral host.
Studio's strict inert parser now accepts cancelled receipts as non-success.
The deterministic Studio and offline service worker are regenerated together.

There remains **no browser-driven execution**, autonomous tool loop, remote
tenant container host, deployed service, general browsing, or independent
production-security attestation. The model never holds an operator capability.
Keep PR #244 in Draft until all required CI and security checks are reviewed.
