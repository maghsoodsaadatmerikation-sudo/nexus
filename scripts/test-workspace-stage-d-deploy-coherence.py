#!/usr/bin/env python3
"""Offline synthetic Railway deployment-history source/recovery coherence tests."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
VERIFIER = HERE / "workspace-stage-d-deploy-coherence.py"
spec = importlib.util.spec_from_file_location(
    "nexus_stage_d_provider_fixture",
    HERE / "test-workspace-stage-d-railway-preflight.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def dump(path, data):
    path.write_bytes((json.dumps(data, sort_keys=True, separators=(",", ":"))
                      + "\n").encode("utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, good=True):
    cmd = [sys.executable, str(VERIFIER), *[str(x) for x in args]]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    assert (result.returncode == 0) is good, (
        f"expected={good}, code={result.returncode}, command={cmd}, "
        f"stdout={result.stdout}, stderr={result.stderr}")
    return result


def deployment(ident, service, region, commit, status="SUCCESS"):
    return {
        "id": "deploy-" + ident,
        "serviceId": ident,
        "environmentId": "env-example",
        "status": status,
        "regions": [region],
        "meta": {"branch": "main", "commitHash": commit, "reason": "deploy"},
    }


def main():
    checks = 0
    approved = "a" * 40
    other = "b" * 40
    with tempfile.TemporaryDirectory(prefix="nexus-stage-d-commit-proof-") as tmp:
        root = Path(tmp)
        inventory, health = fixture.fixture()
        source = {"deployments": [
            deployment("origin-example", "nexus-stage-d", "sfo", approved)]}
        restored = {"deployments": [
            deployment("restore-example", "nexus-stage-d-restore",
                       "us-west2", approved)]}
        files = {
            "inventory": root / "inventory.json",
            "health": root / "health.json",
            "source_deployments": root / "source.json",
            "restore_deployments": root / "restore.json",
        }
        originals = [inventory, health, source, restored]
        for (_, path), content in zip(files.items(), originals):
            dump(path, content)

        def opts(mode="inspect", *, data=None, override=None):
            selected = data or files
            params = {
                "inventory": selected["inventory"],
                "inventory_sha256": sha(selected["inventory"]),
                "health": selected["health"],
                "health_sha256": sha(selected["health"]),
                "source_deployments": selected["source_deployments"],
                "source_deployments_sha256": sha(selected["source_deployments"]),
                "restore_deployments": selected["restore_deployments"],
                "restore_deployments_sha256": sha(selected["restore_deployments"]),
                "project_id": "proj-example",
                "environment_id": "env-example",
                "expected_repo": "example/nexus",
                "source_service_id": "origin-example",
                "restore_service_id": "restore-example",
                "source_volume_id": "volume-origin",
                "restore_volume_id": "volume-restore",
                "expected_commit": approved,
            }
            params.update(override or {})
            return [mode] + [
                item for k, value in params.items()
                for item in ("--" + k.replace("_", "-"), value)
            ]

        result = json.loads(run(opts()).stdout)
        assert result["commit_coherence"] == "SNAPSHOT_CONSISTENT_ONLY"
        assert result["release_gate"] == "BLOCKED"
        assert result["source"]["reported_git_commit"] == approved
        assert result["recovery"]["reported_git_commit"] == approved
        assert result["running_versions_cryptographically_attested"] is False
        assert result["real_offhost_restore_proven"] is False
        assert result["production_release_authorized"] is False
        checks += 1
        gate = run(opts("release-gate"), good=False)
        assert json.loads(gate.stdout)["release_gate"] == "BLOCKED"
        checks += 1

        def changed(name, callback, *, rejected=False):
            nonlocal checks
            inputs = [deepcopy(x) for x in originals]
            callback(*inputs)
            pathmap = {key: root / (name + "-" + key + ".json")
                       for key in files}
            for (_, path), content in zip(pathmap.items(), inputs):
                dump(path, content)
            result = run(opts(data=pathmap), good=not rejected)
            if rejected:
                assert "DENIED" in result.stderr
            else:
                obj = json.loads(result.stdout)
                assert obj["commit_coherence"] == "BLOCKED", obj
                assert obj["blocked_reasons"]
                assert obj["release_gate"] == "BLOCKED"
                assert obj["production_release_authorized"] is False
            checks += 1

        changed("different-commits",
                lambda a, h, s, r: r["deployments"][0]["meta"].update(
                    commitHash=other))
        changed("both-old-commits",
                lambda a, h, s, r: (s["deployments"][0]["meta"].update(
                    commitHash=other),
                    r["deployments"][0]["meta"].update(commitHash=other)))
        changed("source-sleeping",
                lambda a, h, s, r: (
                    a["services"][0]["latestDeployment"].update(status="SLEEPING"),
                    h["services"][0]["activeDeployments"][0].update(status="SLEEPING"),
                    h["services"][0].update(state="sleeping", replicaStatus=None),
                    s["deployments"][0].update(status="SLEEPING")))
        changed("restore-sleeping",
                lambda a, h, s, r: (
                    a["services"][1]["latestDeployment"].update(status="SLEEPING"),
                    h["services"][1]["activeDeployments"][0].update(status="SLEEPING"),
                    h["services"][1].update(state="sleeping", replicaStatus=None),
                    r["deployments"][0].update(status="SLEEPING")))
        changed("unapplied-patch",
                lambda a, h, s, r: (
                    a.update(staged={"status": "STAGED", "changeCount": 2}),
                    h["pendingWork"].append({"kind": "EnvironmentPatch"})))
        changed("runtime-no-replicas",
                lambda a, h, s, r: h["services"][1]["replicaStatus"].update(
                    running=0))
        changed("same-region",
                lambda a, h, s, r: (
                    a["services"][1].update(regions=["sfo"]),
                    a["volumes"][1].update(region="sfo"),
                    r["deployments"][0].update(regions=["sfo"])))

        changed("wrong-branch",
                lambda a, h, s, r: r["deployments"][0]["meta"].update(
                    branch="unapproved"), rejected=True)
        changed("missing-commit",
                lambda a, h, s, r: s["deployments"][0]["meta"].pop(
                    "commitHash"), rejected=True)
        changed("non-full-commit",
                lambda a, h, s, r: s["deployments"][0]["meta"].update(
                    commitHash="a" * 12), rejected=True)
        changed("wrong-service",
                lambda a, h, s, r: r["deployments"][0].update(
                    serviceId="origin-example"), rejected=True)
        changed("wrong-environment",
                lambda a, h, s, r: s["deployments"][0].update(
                    environmentId="another-environment"), rejected=True)
        changed("source-deployment-region",
                lambda a, h, s, r: s["deployments"][0].update(
                    regions=["missing-region"]), rejected=True)
        changed("latest-status-discrepancy",
                lambda a, h, s, r: r["deployments"][0].update(
                    status="FAILED"), rejected=True)
        changed("wrong-active-deployment",
                lambda a, h, s, r: h["services"][0]["activeDeployments"][0].update(
                    id="other-id"), rejected=True)
        changed("wrong-latest-deployment",
                lambda a, h, s, r: a["services"][1]["latestDeployment"].update(
                    id="other-id"), rejected=True)
        changed("missing-history",
                lambda a, h, s, r: s.update(deployments=[]), rejected=True)
        changed("duplicate-history-id",
                lambda a, h, s, r: s["deployments"].append(
                    deepcopy(s["deployments"][0])), rejected=True)
        changed("stale-history-order",
                lambda a, h, s, r: s["deployments"].insert(0, {
                    **deepcopy(s["deployments"][0]), "id": "newer-deployment",
                }), rejected=True)
        changed("unrelated-historical-service",
                lambda a, h, s, r: r["deployments"].append({
                    **deepcopy(r["deployments"][0]),
                    "id": "previous-record",
                    "serviceId": "some-other-service",
                }), rejected=True)
        changed("unknown-envelope",
                lambda a, h, s, r: s.update(authorization="granted"), rejected=True)
        changed("no-provenance",
                lambda a, h, s, r: r["deployments"][0].update(meta=None),
                rejected=True)

        for change in (
            {"inventory_sha256": "f" * 64},
            {"health_sha256": "f" * 64},
            {"source_deployments_sha256": "f" * 64},
            {"restore_deployments_sha256": "f" * 64},
            {"expected_commit": "truncated"},
            {"expected_commit": "b" * 40},
            {"project_id": "another-project"},
            {"source_service_id": "restore-example"},
            {"restore_service_id": "origin-example"},
        ):
            result = run(opts(override=change), good=False if change.get(
                "expected_commit") != "b" * 40 else True)
            if change.get("expected_commit") == "b" * 40:
                assert json.loads(result.stdout)["commit_coherence"] == "BLOCKED"
            checks += 1

        dup = root / "duplicate-json.json"
        dup.write_bytes(files["inventory"].read_bytes().replace(
            b'"project":', b'"project":{},"project":', 1))
        run(opts(override={"inventory": dup}), good=False)
        checks += 1
        link = root / "linked-history.json"
        link.symlink_to(files["restore_deployments"])
        run(opts(override={"restore_deployments": link}), good=False)
        checks += 1
        hard = root / "hardlinked-history.json"
        os.link(files["source_deployments"], hard)
        run(opts(override={"source_deployments": hard}), good=False)
        hard.unlink()
        checks += 1
        assert files["inventory"].read_bytes() == (
            json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        checks += 1

    print(json.dumps({
        "status": "PASS",
        "checks": checks,
        "scope": "synthetic-provider-deployment-history-commit-drift-and-fail-closed-gate",
        "live_railway_services_modified": False,
        "real_two_host_recovery_proven": False,
    }))


if __name__ == "__main__":
    main()
