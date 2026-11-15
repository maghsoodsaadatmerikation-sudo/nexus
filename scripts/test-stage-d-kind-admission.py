#!/usr/bin/env python3
"""Prove real Kubernetes API-server admission deny/allow in a throwaway kind cluster.

Only server-side DRY RUN Pod CREATE calls, never a workload run. A deliberately
unpullable image ref and nonexistent approval Secret prevent accidental runtime
boots. The static CEL policy checks launch shape, NOT an Ed25519 signature or
registered image provenance. Run only with the workflow's isolated kubeconfig.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

NS = "nexus-stage-d-sandbox"
POLICY = "nexus-stage-d-sandbox.nexus.example"
IMAGE = ("registry.invalid/nexus-stage-d-synthetic@sha256:"
         + "a" * 64)
REVIEWER = "system:serviceaccount:" + NS + ":nexus-sandbox-reviewer"


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def kubectl(*args):
    p = subprocess.run(
        ["kubectl", "--request-timeout=10s", *map(str, args)],
        capture_output=True, text=True, timeout=22)
    return p.returncode, p.stdout, p.stderr


def pod():
    return {
        "apiVersion": "v1", "kind": "Pod",
        "metadata": {"name": "nexus-admission-dry-run", "namespace": NS},
        "spec": {
            "automountServiceAccountToken": False,
            "serviceAccountName": "nexus-sandbox-reviewer",
            "hostNetwork": False, "hostPID": False, "hostIPC": False,
            "securityContext": {
                "runAsNonRoot": True, "runAsUser": 10001,
                "runAsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [{
                "name": "synthetic-only",
                "image": IMAGE, "imagePullPolicy": "Never",
                "securityContext": {
                    "runAsNonRoot": True, "runAsUser": 10001,
                    "runAsGroup": 10001,
                    "readOnlyRootFilesystem": True,
                    "allowPrivilegeEscalation": False,
                    "capabilities": {"drop": ["ALL"]},
                },
                "volumeMounts": [
                    {"name": "data", "mountPath": "/data",
                     "readOnly": False},
                    {"name": "approval",
                     "mountPath": "/run/nexus/approval.json",
                     "readOnly": True, "subPath": "approval.json"},
                ],
            }],
            "volumes": [
                {"name": "data", "emptyDir": {"medium": "Memory"}},
                {"name": "approval", "secret": {
                    "secretName": "unavailable-synthetic-approval"}},
            ],
        },
    }


def submit(root, data, expect, label, require_policy=True):
    path = root / "proposal.json"
    path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    code, stdout, stderr = kubectl(
        "--as=" + REVIEWER, "create", "--dry-run=server",
        "-f", path, "-o", "json")
    if expect:
        require(code == 0, label + ": expected admission: " + stderr[-1300:])
        doc = json.loads(stdout)
        require(doc["metadata"]["namespace"] == NS,
                "dry-run response has wrong namespace")
        require(doc["spec"]["containers"][0]["image"] == IMAGE,
                "server silently rewrote image ref")
    else:
        require(code != 0, label + ": bypassed enforced admission")
        if require_policy:
            require(POLICY in stderr or "ValidatingAdmissionPolicy" in stderr,
                    label + ": failure was not caused by the real VAP: " +
                    stderr[-1100:])
    return code


def main():
    require(os.environ.get("NEXUS_KIND_ONLY") == "yes",
            "requires explicit disposable CI cluster boundary")
    require(os.environ.get("KUBECONFIG", "").startswith("/"),
            "requires separate absolute disposable kubeconfig")
    require("nexus-stage-d-" in os.environ["KUBECONFIG"],
            "refuses general developer/provider kubeconfig")
    # No Kubernetes pod is ever created by this script. Admission is checked
    # through API server dry-run, which still invokes native policy.
    rc, out, err = kubectl("auth", "can-i", "create", "pods",
                          "-n", NS, "--as=" + REVIEWER)
    require(rc == 0 and out.strip() == "yes",
            "reviewer lacks narrow pod CREATE permission")
    for resource in ("validatingadmissionpolicies", "validatingadmissionpolicybindings",
                     "namespaces", "secrets"):
        rc, out, err = kubectl(
            "auth", "can-i", "update", resource, "--as=" + REVIEWER)
        require(rc == 0 and out.strip() == "no",
                "untrusted Pod submitter could edit release control: " + resource)

    count = 5
    with tempfile.TemporaryDirectory(prefix="nexus-api-admission-") as tmp:
        root = Path(tmp)
        sample = pod()
        # Await policy convergence; fail if no rejection occurs by deadline.
        invalid = deepcopy(sample)
        invalid["spec"]["containers"][0]["image"] = "busybox:latest"
        deadline = time.monotonic() + 40
        while True:
            path = root / "proposal.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            rc, _, stderr = kubectl(
                "--as=" + REVIEWER, "create", "--dry-run=server",
                "-f", path)
            if rc != 0 and (POLICY in stderr or
                            "ValidatingAdmissionPolicy" in stderr):
                break
            if time.monotonic() >= deadline:
                raise AssertionError(
                    "VAP never activated as a real API-server Deny rule: " +
                    stderr[-700:])
            time.sleep(1)

        submit(root, sample, True, "valid exact synthetic dry-run")
        count += 1

        def bad(label, edit):
            nonlocal count
            obj = deepcopy(sample)
            edit(obj)
            submit(root, obj, False, label)
            count += 1

        bad("unregistered-image", lambda d: d["spec"]["containers"][0].update(
            image="registry.invalid/nexus@sha256:" + "b" * 64))
        bad("mutable-tag", lambda d: d["spec"]["containers"][0].update(
            image="nexus:latest"))
        bad("pull-from-registry", lambda d: d["spec"]["containers"][0].update(
            imagePullPolicy="Always"))
        bad("replace-oci-entrypoint", lambda d: d["spec"]["containers"][0].update(
            command=["/opt/nexus/nexus"]))
        bad("inject-argument", lambda d: d["spec"]["containers"][0].update(
            args=["--disable-guard"]))
        bad("inject-environment", lambda d: d["spec"]["containers"][0].update(
            env=[{"name": "NEXUS_UNSAFE", "value": "true"}]))
        bad("inject-envfrom", lambda d: d["spec"]["containers"][0].update(
            envFrom=[{"configMapRef": {"name": "bypass"}}]))
        bad("root-user", lambda d: d["spec"]["securityContext"].update(
            runAsUser=0))
        bad("writable-rootfs", lambda d: d["spec"]["containers"][0][
            "securityContext"].update(readOnlyRootFilesystem=False))
        bad("allow-escalation", lambda d: d["spec"]["containers"][0][
            "securityContext"].update(allowPrivilegeEscalation=True))
        bad("removed-capability-drop", lambda d: d["spec"]["containers"][0][
            "securityContext"].update(capabilities={"drop": []}))
        bad("host-network", lambda d: d["spec"].update(hostNetwork=True))
        bad("host-pid", lambda d: d["spec"].update(hostPID=True))
        bad("service-account-token", lambda d: d["spec"].update(
            automountServiceAccountToken=True))
        bad("arbitrary-sa", lambda d: d["spec"].update(
            serviceAccountName="default"))
        bad("hostpath-volume", lambda d: d["spec"]["volumes"][0].update(
            emptyDir={}, hostPath={"path": "/"}))
        bad("another-mount", lambda d: d["spec"]["containers"][0][
            "volumeMounts"].append({"name": "data", "mountPath": "/opt/nexus"}))
        bad("read-only-approval-disabled", lambda d: d["spec"]["containers"][0][
            "volumeMounts"][1].update(readOnly=False))
        bad("wrong-secret", lambda d: d["spec"]["volumes"][1]["secret"].update(
            secretName="production-token"))
        bad("extra-init-container", lambda d: d["spec"].update(
            initContainers=[deepcopy(sample["spec"]["containers"][0])]))
        bad("additional-container", lambda d: d["spec"]["containers"].append(
            deepcopy(sample["spec"]["containers"][0])))
        bad("host-alias", lambda d: d["spec"].update(
            hostAliases=[{"ip": "1.1.1.1", "hostnames": ["example.invalid"]}]))
        bad("seccomp-unconfined", lambda d: d["spec"]["securityContext"].update(
            seccompProfile={"type": "Unconfined"}))

        # Even when submitted by a cluster-admin, Kubernetes admission
        # evaluates the same policy. This test does not allow a real run.
        path = root / "proposal.json"
        path.write_text(json.dumps(invalid), encoding="utf-8")
        rc, stdout, stderr = kubectl(
            "create", "--dry-run=server", "-f", path)
        require(rc != 0 and
                (POLICY in stderr or "ValidatingAdmissionPolicy" in stderr),
                "admin Pod creation unexpectedly bypassed installed policy")
        count += 1

        rc, stdout, stderr = kubectl("get", "pods", "-n", NS, "-o", "json")
        require(rc == 0 and json.loads(stdout)["items"] == [],
                "disposable namespace contains a real Pod")
        count += 1

    print(json.dumps({
        "status": "PASS", "checks": count,
        "scope": "actual-ephemeral-kubernetes-api-server-v1-CEL-admission-dry-run",
        "server_enforced_deny": True,
        "policy_signed_provenance_enforced": False,
        "real_pods_created": False,
        "live_railway_or_render_changed": False,
        "image_registry_published": False,
        "release_authorized": False,
        "release_gate": "BLOCKED",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
