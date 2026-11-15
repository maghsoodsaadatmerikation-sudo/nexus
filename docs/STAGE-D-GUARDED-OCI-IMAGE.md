# Stage D — Docker/OCI guarded synthetic image (NOT a production image)

## What is packaged

This experimental image is constructed by \`deploy/Dockerfile.stage-d-guarded-synthetic\` from an **exact detached checkout** of the previously tested NEXUS baseline Git revision \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\`. The GitHub Actions job copies the reviewed guard scripts from the PR into that temporary build context. The image is *not* built from a guessed revision, nor from the sleeping Railway restore service.

The final image contains:
- the genuine compiled historical \`nexus-artifact-05-gateway\` at \`/opt/nexus/nexus\`, an owner-private unprivileged ELF;
- Python 3 and the strict NEXUS guarded-start policy verifier and its dependencies;
- a **single configured default OCI ENTRYPOINT**:
  \`["/usr/bin/python3","-I","-B","/opt/nexus/stage-d-guarded-image-entrypoint.py"]\`.

The entrypoint does **not** automatically trust the image or a digest computed from itself. It requires externally supplied, independently retained, exact SHA-256 values for an approved synthetic-only policy and the exact ELF file. It rejects the known unsafe historical restore SHA \`588dc7672146031425b16b34956876d644244ace\`. The reviewed target binary's revision must be \`f4d027bb5f7e715b298f7cf7184fa621a2fb071d\`, and the policy must name that revision. The policy is a **mounted, privately owned 0600 read-only file**, not an automatic in-image authority.

## Runtime boundaries

The image runs as **non-root UID/GID 10001**, disallows alternative CLI arguments, requires \`NEXUS_BIND_ADDR=127.0.0.1:PORT\` and an ephemeral synthetic bearer token, and accepts a strictly private, separately mounted \`/data\` directory. The guard checks workspace-v1 event history, request reservation markers and quarantine. It launches the **already-SHA-256-verified binary file descriptor** through Python's \`os.execve(fd)\`, retaining the data-directory flock across the exec. Unrecognized revisions, wrong digests, missing evidence, missing mounts, unsafe modes or unknown data fail closed.

The dedicated CI test runs actual \`docker run\` with Linux host-loopback networking, \`--read-only\`, \`--cap-drop ALL\`, \`--security-opt no-new-privileges\`, resource limits, a private disposable mounted data directory, and an independent read-only policy mount. The test checks:
- default image ENTRYPOINT and UID;
- refusal of an absent data mount, wrong executable/policy digest, unknown revision, old known-unsafe restore revision, forged production authority, production execution scope and insecure data mount mode;
- actual HTTP request accepted once and duplicate refused;
- guarded restart on the original synthetic state;
- continued refusal of mutations during \`.nexus-recovery-required\` quarantine;
- unrecognized data schema rejected **before** execution;
- a second guarded launcher must not take an already-locked data directory.
  
The historical baseline binary predates the current PR's new restrictive 0700/0600 request creation fix. If it creates a permissively readable request marker, the guard **correctly refuses** the next startup, and CI narrows permissions *only on the disposable synthetic dataset* before retrying. Existing production volumes are never automatically chmodded or migrated.

The CI reports \`local_image_id\` from \`docker image inspect\`. **This is not a registry-owned image digest, provider attestation, reproducible build record, SBOM, two-host recovery proof or deployment authorization.** In Stage 240, the runtime Python base was pinned to the exact official `python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c` image index, and mutable apt/pip installation was removed. A separate partial CycloneDX inventory and SHA-pinned build-input manifest are now generated in CI. This narrows build-input drift but **does not prove bit-identical rebuilds, independent provenance, a signed registry image digest or production readiness**. See `STAGE-D-OCI-BUILD-EVIDENCE.md`.

## Important bypass/limits

The default Docker ENTRYPOINT is enforced **only if the orchestrator launches the image without overriding it**. An authorized Docker daemon user or operator can override ENTRYPOINT or run the underlying executable directly, so this is not a tamper-proof guarantee against a malicious administrator. To achieve a governed deployment, a separately controlled orchestrator policy must pin the image digest, deny entrypoint overrides and enforce non-root, read-only rootfs, allowed mounts, private policy custody and network isolation. Nothing here provisions that orchestrator policy.

This is a **synthetic-only** artifact: it does not support production bind addresses, live data or changing the Stage D Railway services. It does not package an operational full v2 receiver migration, real off-host immutable backup, independently attested second physical host or destructive recovery. All release gates remain \`BLOCKED\` and \`production_release_authorized=false\`.

## Safe way to test this feature

Run the dedicated \`NEXUS Stage D Guarded OCI Image — Synthetic Only\` GitHub Actions workflow on the draft PR. The workflow creates an exact Git worktree, builds the ephemeral image **locally on the Actions runner**, inspects it and exercises its HTTP behavior. It does not \`docker push\`, publish an image digest, apply a Railway patch, merge to \`main\` or charge a new provider resource.

A real next stage would be an independently reviewed immutable release candidate with pinned OS packages/OCI base image, SBOM and signed image provenance, an externally approved policy/control plane and a **separate authorized disposable** host/volume recovery drill. Production activation cannot be derived from these synthetic tests alone.
