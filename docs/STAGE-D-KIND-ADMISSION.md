# Stage D 243 — real Kubernetes API-server admission, disposable CI only

## Concrete advance beyond Stage 242

Stage 242 checked two different Ed25519 public keys and a **nonexecuting** proposed launch specification. That static check cannot stop a provider from accepting an unsafe workload. Stage 243 adds a real, native Kubernetes \`admissionregistration.k8s.io/v1\` **ValidatingAdmissionPolicy + ValidatingAdmissionPolicyBinding** with \`failurePolicy: Fail\` and \`validationActions: [Deny]\`, in the isolated \`kind\` Kubernetes cluster created on an ephemeral GitHub Actions runner.

The API server evaluates CEL rules on **real Kubernetes API admission requests**. The test uses **only \`kubectl create --dry-run=server\`**, so a successful candidate is *admitted in dry-run* but **never persisted as a Pod, scheduled, started, or able to contact an image registry**. Denied candidates must be rejected by the actual named ValidatingAdmissionPolicy, not simply by malformed YAML or client-only validation.

### Exact test platform

- kind CLI **v0.30.0** binary SHA-256 \`517ab7fc89ddeed5fa65abf71530d90648d9638ef0c4cde22c2c11f8097b8889\`.
- kubectl **v1.34.0** binary SHA-256 \`cfda68cba5848bc3b6c6135ae2f20ba2c78de20059f68789c090166d6abc3e2c\`.
- Kubernetes kind node image **\`kindest/node:v1.34.0@sha256:7416a61b42b1662ca6ca89f02028ac133a309a2a30ba309614e8ec94d976dc5a\`**.
- A fresh \`KUBECONFIG\` in a separately named \`nexus-stage-d-ci-*\` runner temporary directory. No attached production kubeconfig or cloud credentials.
- Test namespace \`nexus-stage-d-sandbox\`, with Pod Security Admission **restricted** and a dedicated ServiceAccount restricted by namespaced RBAC to GET/CREATE Pods only. The ServiceAccount cannot edit namespaces, secrets or admission policies.

The files are \`deploy/kind-stage-d-sandbox-admission.yaml\`, \`scripts/test-stage-d-kind-admission.py\` and \`.github/workflows/stage-d-kind-admission.yml\`. This is an API-server level **real rejection**, not a simulation of how a provider might behave.

### Enforced launch shape

The policy applies to Pod CREATE/UPDATE in the **exact** throwaway namespace (match by request namespace, not a mutable namespace label). It rejects wrong/tagged images, image pull, Kubernetes command/entrypoint overrides or arguments, additional containers/init/ephemeral containers, environment injection, host networking/PID, hostPath and arbitrary mounts, root/privileged mode, capability additions, writable container root, token automount and unknown service accounts. The policy requires a single owner-limited container, its default OCI ENTRYPOINT unmodified, pod-level RuntimeDefault seccomp, drop ALL Linux capabilities, read-only root filesystem and two declared synthetic-only mount types.

The only literal image accepted by the policy is **\`registry.invalid/nexus-stage-d-synthetic@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\`** with \`imagePullPolicy: Never\`. This digest is **deliberately fictitious**; there is **no published signed NEXUS image** at that location. The approval Secret name is likewise deliberately absent. This prevents the server-side dry-run tests from being misinterpreted as an operational deploy or published image attestation. Even the valid dry-run Pod would not be a working NEXUS service; the file is intentionally a restricted *admission-test fixture*.

### Test cases and limits

The Python test verifies the narrow proposal account's real RBAC permissions, confirms an approved synthetic Pod is accepted through API-server dry-run and checks representative malicious proposals are *rejected specifically by the named VAP*: wrong image or pull policy, command/args/env overrides, root or writable runtime, host network/PID, privilege escalation, hostPath and volume substitution, injected init/second container, altered service account or token automount, wrong secret, etc. It confirms the cluster contains **zero actual Pods** in the sandbox namespace. The workflow **always deletes** the throwaway kind cluster.

This is a demonstrably **real Kubernetes control-plane admission path**, but **not Railway or Render enforcement**. Those services may not expose equivalent Kubernetes admission policies. An authorized cluster administrator can edit/delete the policy or binding, and the test cannot prove non-bypassability against that administrator. It does not verify an Ed25519 signature inside the API server; the independent signing evidence remains handled by Stages 241–242 in an offline verifier. There is no published registry digest or SLSA provenance, no real key custodian, no live host restoration and **no actual synthetic NEXUS Pod is started**.

The combined lesson is that: *structural release approval* (two reviews) and *enforced deployment controls* (this Kubernetes API server) are both needed, but are **not yet cryptographically joined in a trusted production admission controller**. The next step requires a separately approved deployment platform that actually supports immutable registry digest admission and a verified external signature policy, plus an independent disposable-host restore rehearsal. An offline guard or a green kind test cannot make the existing vulnerable historical Railway image safe.

**No deployment to Railway/Render, real provider mutation, new paid resources, live data, production signing keys, registry push, Docker image publication or merge to main.** Release remains \`BLOCKED\`.
