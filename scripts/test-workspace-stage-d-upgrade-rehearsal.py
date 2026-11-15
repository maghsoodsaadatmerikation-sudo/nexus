#!/usr/bin/env python3
"""Synthetic Stage D upgrade rehearsal: Git ancestry, plan, rollback denial."""
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
SCRIPT = HERE / "workspace-stage-d-upgrade-rehearsal.py"

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base_fixture = load("nexus_railway_base_for_rehearsal",
                    "test-workspace-stage-d-railway-preflight.py")
deploy_fixture = load("nexus_deployed_for_rehearsal",
                      "test-workspace-stage-d-deploy-coherence.py")

SOURCE_COMMIT = "9" * 40
RESTORE_COMMIT = "5" * 40
TARGET_COMMIT = "f" * 40

def save(path, data):
    path.write_bytes((json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode())
    return path

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(arguments, succeeds=True):
    proc = subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)],
                          capture_output=True, text=True, timeout=20)
    if (proc.returncode == 0) != succeeds:
        raise AssertionError(f"unexpected exit {proc.returncode}; stdout={proc.stdout}; stderr={proc.stderr}")
    return proc

def compare(old, new, count):
    return {
        "repository_full_name": "example/nexus",
        "base": old,
        "head": new,
        "status": "identical" if old == new else "ahead",
        "ahead_by": count,
        "behind_by": 0,
        "total_commits": count,
        "too_large": False,
        "base_commit": {"sha": old},
        "merge_base_commit": {"sha": old},
        "files": [],
    }

def contract():
    return {
        "schema": "nexus.stage-d.nonexecuting-upgrade-rehearsal.v1",
        "project_id": "proj-example",
        "environment_id": "env-example",
        "repository": "example/nexus",
        "source_service_id": "origin-example",
        "restore_service_id": "restore-example",
        "source_volume_id": "volume-origin",
        "restore_volume_id": "volume-restore",
        "source_current_commit": SOURCE_COMMIT,
        "restore_current_commit": RESTORE_COMMIT,
        "proposed_rehearsal_commit": TARGET_COMMIT,
        "source_fallback_commit": SOURCE_COMMIT,
        "restore_fallback_commit": RESTORE_COMMIT,
        "run_mode": "review-only",
        "destination_policy": "new-disposable-isolated-volume",
        "permit_source_volume_write": False,
        "permit_restore_volume_write": False,
        "permit_destructive_test": False,
        "permit_apply_provider_patch": False,
        "permit_deploy_or_wake": False,
        "permit_signer_rotation": False,
        "require_independent_backup_and_checkpoint": True,
        "require_data_schema_rollback_review": True,
    }


def fixtures():
    inv, health = base_fixture.fixture()
    src = {"deployments": [
        deploy_fixture.deployment("origin-example", "nexus-stage-d",
                                  "sfo", SOURCE_COMMIT)]}
    rec = {"deployments": [
        deploy_fixture.deployment("restore-example", "nexus-stage-d-restore",
                                  "us-west2", RESTORE_COMMIT)]}
    return {
        "inventory": inv,
        "health": health,
        "source_deployments": src,
        "restore_deployments": rec,
        "restore_to_source": compare(RESTORE_COMMIT, SOURCE_COMMIT, 139),
        "source_to_target": compare(SOURCE_COMMIT, TARGET_COMMIT, 40),
        "plan": contract(),
    }


def main():
    tests = 0
    with tempfile.TemporaryDirectory(prefix="nexus-stage-d-safe-rehearsal-") as tmp:
        root = Path(tmp)
        original = fixtures()

        def write_fixture(data, tag):
            output = {}
            for key, value in data.items():
                output[key] = save(root / f"{tag}-{key}.json", value)
            return output

        files = write_fixture(original, "original")

        def arguments(fileset=files, mode="inspect", overrides=None):
            options = {}
            for key, path in fileset.items():
                options[key] = path
                options[key + "_sha256"] = digest(path)
            options.update({
                "project_id": "proj-example",
                "environment_id": "env-example",
                "expected_repo": "example/nexus",
                "source_service_id": "origin-example",
                "restore_service_id": "restore-example",
                "source_volume_id": "volume-origin",
                "restore_volume_id": "volume-restore",
            })
            options.update(overrides or {})
            return [mode, *[
                item for key, value in options.items()
                for item in ("--" + key.replace("_", "-"), value)
            ]]

        result = json.loads(run(arguments()).stdout)
        assert result["status"] == "reviewed-offline-upgrade-rehearsal-only"
        assert result["recovery_to_source_ancestor_steps"] == 139
        assert result["source_to_target_ancestor_steps"] == 40
        assert "restore_deployment_trails_source_by_139_commits" in result["blocked_reasons"]
        assert "proposed_code_rehearsal_ahead_of_source_by_40_commits" in result["blocked_reasons"]
        assert "source_and_restore_deployed_commits_differ" in result["blocked_reasons"]
        assert result["release_gate"] == "BLOCKED"
        assert result["provider_release_authorized"] is False
        assert result["actual_rehearsal_executed"] is False
        assert result["real_rollback_tested"] is False
        assert result["original_volumes_mutated"] is False
        tests += 1

        release = run(arguments(mode="release-gate"), succeeds=False)
        assert json.loads(release.stdout)["release_gate"] == "BLOCKED"
        assert "BLOCKED" in release.stderr
        tests += 1

        def mutated(name, callback, *, denied=True):
            nonlocal tests
            values = deepcopy(original)
            callback(values)
            actual = write_fixture(values, name)
            response = run(arguments(actual), succeeds=not denied)
            if denied:
                assert "DENIED" in response.stderr
            else:
                obj = json.loads(response.stdout)
                assert obj["release_gate"] == "BLOCKED"
                assert obj["provider_release_authorized"] is False
            tests += 1

        # Operator contract: no wake/redeploy, staging patch, signer rotation,
        # destructive test or *either* production volume may be authorized.
        for field in (
            "permit_source_volume_write", "permit_restore_volume_write",
            "permit_destructive_test", "permit_apply_provider_patch",
            "permit_deploy_or_wake", "permit_signer_rotation",
        ):
            mutated("permit-" + field,
                    lambda v, fld=field: v["plan"].update({fld: True}))
        for field in (
            "require_independent_backup_and_checkpoint",
            "require_data_schema_rollback_review",
        ):
            mutated("skip-" + field,
                    lambda v, fld=field: v["plan"].update({fld: False}))
        for field, bad in (
            ("run_mode", "deploy-now"),
            ("destination_policy", "reuse-production-volume"),
            ("source_fallback_commit", RESTORE_COMMIT),
            ("restore_fallback_commit", SOURCE_COMMIT),
            ("source_current_commit", RESTORE_COMMIT),
            ("restore_current_commit", SOURCE_COMMIT),
            ("project_id", "wrong-project"),
            ("environment_id", "another-environment"),
            ("repository", "not-trusted/repo"),
            ("source_volume_id", "volume-restore"),
            ("restore_service_id", "origin-example"),
            ("proposed_rehearsal_commit", "0" * 40),
        ):
            mutated("plan-" + field, lambda v, f=field, val=bad:
                    v["plan"].update({f: val}))
        mutated("unknown-plan-field", lambda v: v["plan"].update(
            {"auto_accept_release": True}))
        mutated("unknown-plan-schema", lambda v: v["plan"].update(
            {"schema": "nexus.stage-d.production-ready.v2"}))
        mutated("wrong-boolean-type", lambda v: v["plan"].update(
            {"permit_deploy_or_wake": 0}))
        mutated("unknown-rollback-mode", lambda v: v["plan"].update(
            {"require_data_schema_rollback_review": 1}))

        for field, bad in (
            ("base", SOURCE_COMMIT),
            ("head", RESTORE_COMMIT),
            ("repository_full_name", "outsider/repo"),
            ("status", "diverged"),
            ("ahead_by", 0),
            ("behind_by", 1),
            ("total_commits", 99),
            ("too_large", True),
        ):
            mutated("bad-comparison-" + field, lambda v, f=field, val=bad:
                    v["restore_to_source"].update({f: val}))
        mutated("bad-merge-base", lambda v:
                v["restore_to_source"]["merge_base_commit"].update(
                    {"sha": TARGET_COMMIT}))
        mutated("bad-direct-ancestor", lambda v:
                v["restore_to_source"]["base_commit"].update(
                    {"sha": SOURCE_COMMIT}))
        mutated("bad-ahead-boolean", lambda v:
                v["source_to_target"].update(ahead_by=True))
        mutated("backward-graph", lambda v:
                v["source_to_target"].update(behind_by=5))
        mutated("missing-compare", lambda v:
                v["source_to_target"].pop("merge_base_commit"))
        mutated("truncated-commit", lambda v:
                v["source_to_target"].update(head=TARGET_COMMIT[:12]))
        mutated("wrong-target-head", lambda v:
                v["source_to_target"].update(head=SOURCE_COMMIT))

        # Supported target may equal already observed source revision:
        # no source-to-target ahead count may be fabricated in that case.
        def no_target_ahead(v):
            v["plan"]["proposed_rehearsal_commit"] = SOURCE_COMMIT
            v["source_to_target"] = compare(SOURCE_COMMIT, SOURCE_COMMIT, 0)
        mutated("rehearsal-source-commit", no_target_ahead, denied=False)

        # Rehearsal still cannot pass provider checks on sleeping services,
        # pending changes or a production commit mismatch.
        def blocked_provider(v):
            for i, svc in enumerate(v["inventory"]["services"]):
                svc["latestDeployment"]["status"] = "SLEEPING"
                v["health"]["services"][i]["activeDeployments"][0]["status"] = "SLEEPING"
                v["health"]["services"][i].update(
                    state="sleeping", replicaStatus=None)
            for d in ("source_deployments", "restore_deployments"):
                v[d]["deployments"][0]["status"] = "SLEEPING"
            v["inventory"]["staged"] = {"status": "STAGED", "changeCount": 1}
            v["health"]["pendingWork"] = [{"kind": "EnvironmentPatch", "status": "staged"}]
        mutated("observed-railway-sleeping-drift", blocked_provider, denied=False)

        # Hash pins are separately required. Any stolen/replaced bytes are
        # rejected even if the new snapshot has valid strict JSON.
        for name in ("plan", "inventory", "source_deployments",
                     "restore_to_source", "source_to_target"):
            options = {name + "_sha256": "a" * 64}
            result = run(arguments(overrides=options), succeeds=False)
            assert "DENIED" in result.stderr
            tests += 1

        symlink = root / "aliased-plan.json"
        symlink.symlink_to(files["plan"])
        run(arguments(overrides={"plan": symlink}), succeeds=False)
        tests += 1
        hard = root / "hardlinked-plan.json"
        os.link(files["plan"], hard)
        run(arguments(overrides={"plan": hard}), succeeds=False)
        hard.unlink()
        tests += 1
        ambiguous = root / "duplicate-plan.json"
        ambiguous.write_bytes(files["plan"].read_bytes().replace(
            b'"schema":', b'"schema":"forged","schema":', 1))
        run(arguments(overrides={"plan": ambiguous}), succeeds=False)
        tests += 1
        assert files["plan"].read_bytes() == (
            json.dumps(original["plan"], sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        tests += 1

    print(json.dumps({
        "status": "PASS", "checks": tests,
        "scope": "synthetic-version-ancestry-isolated-rehearsal-and-rollback-safety-denial",
        "live_provider_changed": False,
        "rollback_on_real_data_tested": False,
        "production_release_authorized": False,
    }))


if __name__ == "__main__":
    main()
