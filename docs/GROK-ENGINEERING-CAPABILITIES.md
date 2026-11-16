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
| Multi-file read/write/edit + ZIP | **Implemented** with bounded file operations | Rich project indexing/diff review/UI |
| Tool-using agent loop | Deterministic reviewed multi-tool plan **implemented** | Reliable model planner, step-by-step consent in Studio, evaluation |
| Internet inside sandbox | **Not enabled**; `--network none` is mandatory | Restrictive authenticated egress proxy, DNS/SSRF policy, rate/budget consent |
| Background processes / long jobs | **Not implemented** | Durable queue, lease/recovery, cancellation and accounting |
| Web search/current API verification | Existing human-directed Wikipedia/Crossref retrieval | Multiple search providers, provenance checks, content sanitation |
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
