#!/usr/bin/env python3
"""Adversarial, fully offline Railway Stage D provider-snapshot preflight tests.

All provider snapshots here are synthetic. Real provider services are not
contacted, woken, deployed, queried for credentials, or modified.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TOOL = HERE / "workspace-stage-d-railway-preflight.py"


def dump(path, value):
    path.write_bytes((json.dumps(value, sort_keys=True, separators=(",", ":"))
                      + "\n").encode("utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, good=True):
    x = subprocess.run([sys.executable, str(TOOL), *[str(z) for z in args]],
                       capture_output=True, text=True, timeout=15)
    assert (x.returncode == 0) is good, (
        f"unexpected exit {x.returncode} good={good}\n"
        f"stdout={x.stdout}\nstderr={x.stderr}")
    return x


def fake_service(ident, name, volume, region):
    return {
        "id": ident,
        "name": name,
        "state": "live",
        "source": {"repo": "example/nexus", "branch": "main"},
        "regions": [region],
        "numReplicas": 1,
        "volumeMounts": [{"volumeId": volume, "mountPath": "/data"}],
        "latestDeployment": {"id": "deploy-" + ident, "status": "SUCCESS"},
    }


def fake_health(ident, name):
    return {
        "serviceId": ident, "serviceName": name,
        "state": "online", "statusText": "Online",
        "activeDeployments": [
            {"id": "deploy-" + ident, "status": "SUCCESS"}],
        "replicaStatus": {"running": 1, "crashed": 0, "total": 1},
        "issues": {"warningCount": 0, "criticalCount": 0},
        "hasIssues": False, "hasVolume": True,
    }


def fixture():
    return (
        {
            "project": {"id": "proj-example", "name": "Stage D"},
            "environment": {"id": "env-example", "name": "production"},
            "staged": None,
            "services": [
                fake_service("origin-example", "nexus-stage-d", "volume-origin", "sfo"),
                fake_service("restore-example", "nexus-stage-d-restore", "volume-restore", "us-west2"),
            ],
            "volumes": [
                {"id": "volume-origin", "state": "live", "region": "sfo",
                 "mountedOn": {"serviceId": "origin-example", "mountPath": "/data"}},
                {"id": "volume-restore", "state": "live", "region": "us-west2",
                 "mountedOn": {"serviceId": "restore-example", "mountPath": "/data"}},
            ],
        }, {
            "environment": {"id": "env-example", "name": "production"},
            "services": [
                fake_health("origin-example", "nexus-stage-d"),
                fake_health("restore-example", "nexus-stage-d-restore"),
            ],
            "pendingWork": [],
            "summary": {"servicesWithIssues": 0, "totalFailures": 0},
        },
    )


def main():
    checks = 0
    with tempfile.TemporaryDirectory(prefix="nexus-provider-health-") as tmp:
        root = Path(tmp)
        a, h = fixture()
        inventory = root / "inventory.json"
        health = root / "health.json"
        dump(inventory, a)
        dump(health, h)

        def args(mode="inspect", *, inv=inventory, runtime=health, overrides=None):
            opts = {
                "inventory": inv, "inventory_sha256": sha(inv),
                "health": runtime, "health_sha256": sha(runtime),
                "project_id": "proj-example", "environment_id": "env-example",
                "expected_repo": "example/nexus",
                "source_service_id": "origin-example",
                "restore_service_id": "restore-example",
                "source_volume_id": "volume-origin",
                "restore_volume_id": "volume-restore",
            }
            opts.update(overrides or {})
            return [mode] + [
                item for k, v in opts.items()
                for item in ("--" + k.replace("_", "-"), v)
            ]

        ok = json.loads(run(args()).stdout)
        assert ok["online_topology_preflight"] == "SNAPSHOT_CONSISTENT_ONLY"
        assert ok["blocked_reasons"] == []
        assert ok["release_gate"] == "BLOCKED"
        assert ok["production_release_authorized"] is False
        assert ok["provider_signed_snapshots_verified"] is False
        assert ok["independent_failure_domains_proven"] is False
        assert ok["real_offhost_restore_proven"] is False
        assert ok["current_deployed_commit_verified"] is False
        checks += 1

        gate = run(args("release-gate"), good=False)
        assert json.loads(gate.stdout)["release_gate"] == "BLOCKED"
        assert "BLOCKED" in gate.stderr
        checks += 1

        def mutated(name, change, *, expect="blocked"):
            nonlocal checks
            inv, runtime = (deepcopy(a), deepcopy(h))
            change(inv, runtime)
            inv_path = root / (name + "-inventory.json")
            health_path = root / (name + "-health.json")
            dump(inv_path, inv)
            dump(health_path, runtime)
            result = run(args(inv=inv_path, runtime=health_path),
                         good=(expect != "denied"))
            if expect == "denied":
                assert "DENIED" in result.stderr
            else:
                report = json.loads(result.stdout)
                assert report["online_topology_preflight"] == "BLOCKED"
                assert report["blocked_reasons"]
                assert report["release_gate"] == "BLOCKED"
                assert report["production_release_authorized"] is False
            checks += 1

        # Blocking statuses: provider's global hasIssues=false is not a
        # sufficient readiness indicator for a sleeping/stale service.
        mutated("source-sleeping",
                lambda i, h: h["services"][0].update(state="sleeping"))
        mutated("restore-sleeping",
                lambda i, h: h["services"][1].update(state="sleeping"))
        mutated("deployment-sleeping",
                lambda i, h: i["services"][0]["latestDeployment"].update(status="SLEEPING"))
        mutated("replica-not-running",
                lambda i, h: h["services"][0]["replicaStatus"].update(running=0))
        mutated("replica-unknown",
                lambda i, h: h["services"][1].update(replicaStatus=None))
        mutated("deployment-rolled",
                lambda i, h: h["services"][0]["activeDeployments"][0].update(id="old-deployment"))
        mutated("deployment-failed",
                lambda i, h: h["services"][1]["activeDeployments"][0].update(status="FAILED"))
        mutated("staged-env",
                lambda i, h: i.update(staged={"status": "STAGED", "changeCount": 2}))
        mutated("pending-work",
                lambda i, h: h["pendingWork"].append({"kind": "EnvironmentPatch"}))
        mutated("service-staged-changes",
                lambda i, h: i["services"][0].update(state="live-with-staged-changes"))
        mutated("same-region",
                lambda i, h: (i["services"][1].update(regions=["sfo"]),
                              i["volumes"][1].update(region="sfo")))
        mutated("boolean-replica",
                lambda i, h: h["services"][0]["replicaStatus"].update(running=True))
        mutated("crashed-replica",
                lambda i, h: h["services"][0]["replicaStatus"].update(crashed=1))

        # Reproduce the *shape*, not the data authority, of the real
        # read-only provider observation: two sleeping services, no running
        # replicas, and an unapplied source health-check configuration.
        def current_stage_d_shape(inventory, health):
            inventory["services"][0]["state"] = "live-with-staged-changes"
            inventory["staged"] = {
                "status": "STAGED", "changeCount": 2,
            }
            health["pendingWork"] = [{"kind": "EnvironmentPatch",
                                      "status": "staged"}]
            for service, observed in zip(
                    inventory["services"], health["services"]):
                service["latestDeployment"]["status"] = "SLEEPING"
                observed["activeDeployments"][0]["status"] = "SLEEPING"
                observed["state"] = "sleeping"
                observed["replicaStatus"] = None
                observed["hasIssues"] = False
        mutated("observed-stage-d-blocked-shape", current_stage_d_shape)

        # Metadata integrity: wrong identity, volume, repo, missing service,
        # or inconsistent provider snapshot must not look like 'blocked but
        # well-attested topology'; it is structurally denied.
        mutated("wrong-repo",
                lambda i, h: i["services"][1]["source"].update(repo="attacker/other"),
                expect="denied")
        mutated("unmounted-volume",
                lambda i, h: i["services"][0].update(volumeMounts=[]),
                expect="denied")
        mutated("volume-wrong-owner",
                lambda i, h: i["volumes"][0]["mountedOn"].update(serviceId="restore-example"),
                expect="denied")
        mutated("volume-not-live",
                lambda i, h: i["volumes"][1].update(state="staged-create"),
                expect="denied")
        mutated("wrong-health-name",
                lambda i, h: h["services"][0].update(serviceName="fake-provider"),
                expect="denied")
        mutated("duplicated-service",
                lambda i, h: i["services"].append(deepcopy(i["services"][0])),
                expect="denied")
        mutated("missing-restore-health",
                lambda i, h: h["services"].pop(),
                expect="denied")
        mutated("different-environment",
                lambda i, h: h["environment"].update(id="env-other"),
                expect="denied")
        mutated("wrong-mount-path",
                lambda i, h: i["services"][1]["volumeMounts"][0].update(mountPath="/tmp"),
                expect="denied")

        for override in (
            {"inventory_sha256": "f" * 64},
            {"health_sha256": "f" * 64},
            {"project_id": "wrong-project"},
            {"source_service_id": "restore-example"},
            {"restore_service_id": "origin-example"},
            {"source_volume_id": "volume-restore"},
            {"restore_volume_id": "volume-origin"},
            {"source_service_id": "origin-example",
             "restore_service_id": "origin-example"},
            {"source_volume_id": "volume-origin",
             "restore_volume_id": "volume-origin"},
        ):
            run(args(overrides=override), good=False)
            checks += 1

        noncanonical = root / "duplicate-keys.json"
        noncanonical.write_bytes(inventory.read_bytes().replace(
            b'"project":', b'"project":{},"project":', 1))
        run(args(inv=noncanonical), good=False)
        checks += 1
        naive = root / "nan-snapshot.json"
        naive.write_bytes(health.read_bytes().replace(
            b'"pendingWork":[]', b'"pendingWork":NaN', 1))
        run(args(runtime=naive), good=False)
        checks += 1
        sym = root / "symlink-inventory.json"
        sym.symlink_to(inventory)
        run(args(inv=sym), good=False)
        checks += 1
        hard = root / "hardlinked-health.json"
        os.link(health, hard)
        run(args(runtime=hard), good=False)
        hard.unlink()
        checks += 1

        assert inventory.read_bytes() == (
            json.dumps(a, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        checks += 1

    print(json.dumps({
        "status": "PASS",
        "checks": checks,
        "scope": "synthetic-provider-inventory-health-fail-closed-and-release-denial",
        "real_railway_service_touched": False,
        "physical_host_independence_proven": False,
    }))


if __name__ == "__main__":
    main()
