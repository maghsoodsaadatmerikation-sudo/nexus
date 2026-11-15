#!/usr/bin/env python3
"""Adversarial synthetic tests of real NEXUS v1 archive downgrade screening.

These use the production data-snapshot backup encoder with ephemeral, synthetic
workspace/marker bytes. They do NOT run historical Rust service binaries.
"""
import base64
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TOOL = HERE / "workspace-stage-d-data-rollback-screen.py"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


snapshot = load("nexus_compat_synthetic_backup", "data-snapshot.py")
rehearsal_fixture = load(
    "nexus_compat_synthetic_operator", "test-workspace-stage-d-upgrade-rehearsal.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def run(args, good=True):
    result = subprocess.run(
        [sys.executable, str(TOOL), *[str(v) for v in args]],
        capture_output=True, text=True, timeout=25)
    assert (result.returncode == 0) is good, (
        f"unexpected code={result.returncode} good={good}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}")
    return result


def initial_workspace(workspace_id="w"):
    return {
        "schema_version": 1,
        "workspace": {
            "id": workspace_id, "question": "Synthetic question", "goal": None,
            "constraints": [], "values": [], "claims": [], "alternatives": [],
            "judgment": None,
        },
        "events": [{
            "sequence": 0, "provenance_id": "human:creator",
            "kind": "WorkspaceCreated",
        }],
    }


def add_claim(workspace):
    w = workspace
    w["workspace"]["claims"].append({
        "id": "claim-1", "text": "Synthetic statement",
        "origin": "Human", "uncertainty": "Unknown",
    })
    w["events"].append({
        "sequence": len(w["events"]), "provenance_id": "human:claim-1",
        "kind": {"ClaimAdded": {"claim_id": "claim-1"}},
    })


def base_data():
    return {
        "77.json": canonical(initial_workspace()),
        "requests/" + b"accepted".hex(): b"pending\n",
        "requests/" + b"uncertain".hex(): b"p",
    }


def write_source(root, objects):
    root.mkdir(mode=0o700)
    (root / "requests").mkdir(mode=0o700)
    for name, data in objects.items():
        path = root / name
        path.write_bytes(data)
        os.chmod(path, 0o600)


def main():
    count = 0
    with tempfile.TemporaryDirectory(prefix="nexus-v1-downgrade-screen-") as tmp:
        root = Path(tmp)
        plan = root / "operator-plan.json"
        plan.write_bytes(canonical(rehearsal_fixture.contract()))
        os.chmod(plan, 0o600)
        before = root / "baseline-snapshot.json"
        write_source(root / "base-state", base_data())
        snapshot.backup(root / "base-state", before)
        assert before.read_bytes() and before.stat().st_nlink == 1

        def cli(target=before, mode="inspect", overrides=None):
            flags = {
                "before": before, "before_sha256": sha(before),
                "after": target, "after_sha256": sha(target),
                "plan": plan, "plan_sha256": sha(plan),
                "source_commit": rehearsal_fixture.SOURCE_COMMIT,
                "restore_commit": rehearsal_fixture.RESTORE_COMMIT,
                "target_commit": rehearsal_fixture.TARGET_COMMIT,
            }
            flags.update(overrides or {})
            return [mode] + [
                arg for key, v in flags.items()
                for arg in ("--" + key.replace("_", "-"), v)
            ]

        identical = json.loads(run(cli()).stdout)
        assert identical["status"] == "offline-archive-data-difference-screened"
        assert identical["structural_screen"] == "NO_CONTENT_DELTA_ONLY"
        assert identical["snapshots_byte_identical"] is True
        assert identical["findings"] == []
        assert identical["old_rust_reader_executed"] is False
        assert identical["new_rust_reader_executed"] is False
        assert identical["reverse_schema_migration_verified"] is False
        assert identical["release_gate"] == "BLOCKED"
        assert identical["automatic_data_rollback_authorized"] is False
        count += 1

        denied_release = run(cli(mode="rollback-gate"), good=False)
        assert "BLOCKED" in denied_release.stderr
        assert json.loads(denied_release.stdout)["release_gate"] == "BLOCKED"
        count += 1

        def modified(name, mutate, expect=None, rejected=False):
            nonlocal count
            objects = deepcopy(base_data())
            mutate(objects)
            original = root / (name + "-source")
            artifact = root / (name + "-archive.json")
            write_source(original, objects)
            snapshot.backup(original, artifact)
            result = run(cli(artifact), good=not rejected)
            if rejected:
                assert "DENIED" in result.stderr, result.stderr
            else:
                parsed = json.loads(result.stdout)
                assert parsed["release_gate"] == "BLOCKED"
                assert parsed["structural_screen"] == "DOWNGRADE_REVIEW_REQUIRED"
                assert parsed["automatic_data_rollback_authorized"] is False
                assert parsed["findings"]
                if expect is not None:
                    assert expect in parsed["findings"], (expect, parsed)
            count += 1
            return artifact

        def edit_workspace(objects, callback, id="w"):
            path = id.encode().hex() + ".json"
            w = json.loads(objects[path])
            callback(w)
            objects[path] = canonical(w)

        modified("add-workspace", lambda d: d.update({
            "78.json": canonical(initial_workspace("x"))}),
            "new_workspace_not_proven_readable_by_old_runtime")
        modified("remove-workspace", lambda d: d.pop("77.json"),
            "workspace_disappeared")
        modified("extend-audit", lambda d: edit_workspace(d, add_claim),
            "new_event_requires_legacy_reader_compatibility_proof")
        modified("alter-question", lambda d: edit_workspace(
            d, lambda x: x["workspace"].update(question="changed")),
            "workspace_state_changed_without_versioned_reverse_migration")
        modified("drop-audit", lambda d: edit_workspace(
            d, lambda w: w.update(events=[])),
            rejected=True)
        modified("forge-audit-sequence", lambda d: edit_workspace(
            d, lambda w: w["events"][0].update(sequence=42)),
            rejected=True)
        modified("forge-audit-provenance", lambda d: edit_workspace(
            d, lambda w: w["events"][0].update(provenance_id="   ")),
            rejected=True)
        modified("unknown-event-kind", lambda d: edit_workspace(
            d, lambda w: w["events"][0].update(kind="MachineTrustGranted")),
            rejected=True)
        modified("unknown-schema", lambda d: edit_workspace(
            d, lambda w: w.update(schema_version=2)),
            rejected=True)
        modified("unknown-top-level", lambda d: edit_workspace(
            d, lambda w: w.update(new_authority="yes")),
            rejected=True)

        modified("new-request", lambda d: d.update({
            "requests/" + b"new-req".hex(): b"pending\n"}),
            "new_request_reservations_not_proven_downgrade_safe")
        modified("drop-request", lambda d: d.pop(
            "requests/" + b"accepted".hex()),
            "request_reservation_lost")
        modified("pending-to-unknown", lambda d: d.update({
            "requests/" + b"accepted".hex(): b"pend"}),
            "pending_request_became_indeterminate")
        modified("uncertain-to-pending", lambda d: d.update({
            "requests/" + b"uncertain".hex(): b"pending\n"}),
            "uncertain_request_made_pending_again")
        modified("new-quarantine", lambda d: d.update({
            snapshot.RECOVERY_MARKER: snapshot.RECOVERY_BYTES}),
            "recovery_quarantine_added")

        # The recovery marker must not be silently dropped from a versioned
        # recovery copy, even if the rest of the data matches exactly.
        marker_before = root / "marker-before.json"
        marked = base_data()
        marked[snapshot.RECOVERY_MARKER] = snapshot.RECOVERY_BYTES
        write_source(root / "marked-source", marked)
        snapshot.backup(root / "marked-source", marker_before)
        dropped_marker = json.loads(run(cli(overrides={
            "before": marker_before, "before_sha256": sha(marker_before)})).stdout)
        assert "recovery_quarantine_disappeared" in dropped_marker["findings"]
        count += 1

        # The snapshot file's outer base64/size/SHA must be strict, and the
        # independent checksum is NEVER recomputed from a poisoned source.
        def forged(name, callback, *, expect_denial=True):
            nonlocal count
            obj = json.loads(before.read_bytes())
            callback(obj)
            artifact = root / ("forged-" + name + ".json")
            artifact.write_bytes(canonical(obj))
            report = run(cli(artifact), good=not expect_denial)
            assert "DENIED" in report.stderr if expect_denial else True
            count += 1
            return artifact

        forged("duplicate-record", lambda d: d["files"].append(
            deepcopy(d["files"][0])))
        forged("wrong-file-size", lambda d: d["files"][0].update(size=999))
        forged("wrong-inner-digest", lambda d: d["files"][0].update(
            sha256="a" * 64))
        forged("invalid-base64", lambda d: d["files"][0].update(data="!BAD!"))
        forged("unsupported-file-name", lambda d: d["files"][0].update(
            path="secrets.env"))
        forged("unapproved-envelope", lambda d: d.update(
            authority="operator-asserted"))
        forged("invalid-format", lambda d: d.update(
            schema="nexus.data-snapshot.v2"))
        forged("extra-top-level", lambda d: d.update(
            production_approval=True))

        for changes in (
            {"before_sha256": "a" * 64},
            {"after_sha256": "b" * 64},
            {"plan_sha256": "c" * 64},
            {"source_commit": "d" * 40},
            {"restore_commit": "e" * 40},
            {"target_commit": "0" * 40},
            {"source_commit": "not-a-commit"},
        ):
            run(cli(overrides=changes), good=False)
            count += 1

        def corrupt_plan(name, change):
            nonlocal count
            wrong = deepcopy(rehearsal_fixture.contract())
            change(wrong)
            path = root / (name + "-plan.json")
            path.write_bytes(canonical(wrong))
            run(cli(overrides={"plan": path, "plan_sha256": sha(path)}),
                good=False)
            count += 1

        corrupt_plan("allow-live-write", lambda p: p.update(
            permit_source_volume_write=True))
        corrupt_plan("allow-restore-write", lambda p: p.update(
            permit_restore_volume_write=True))
        corrupt_plan("allow-deploy", lambda p: p.update(
            permit_deploy_or_wake=True))
        corrupt_plan("allow-key-rotation", lambda p: p.update(
            permit_signer_rotation=True))
        corrupt_plan("skip-schema-review", lambda p: p.update(
            require_data_schema_rollback_review=False))
        corrupt_plan("override-fallback", lambda p: p.update(
            source_fallback_commit="0" * 40))
        corrupt_plan("bad-plan-schema", lambda p: p.update(
            schema="nexus.stage-d.rehearsal-direct-deploy.v2"))

        symlink = root / "linked-before.json"
        symlink.symlink_to(before)
        run(cli(overrides={"before": symlink}), good=False)
        count += 1
        hardlink = root / "hardlinked-before.json"
        os.link(before, hardlink)
        run(cli(overrides={"before": hardlink}), good=False)
        hardlink.unlink()
        count += 1
        duplicate = root / "ambiguous-before.json"
        duplicate.write_bytes(before.read_bytes().replace(
            b'"schema":', b'"schema":"wrong","schema":', 1))
        run(cli(overrides={"before": duplicate}), good=False)
        count += 1
        bad_json = root / "noncanonical-before.json"
        bad_json.write_bytes(before.read_bytes() + b" ")
        run(cli(overrides={"before": bad_json}), good=False)
        count += 1

        assert before.read_bytes()
        assert plan.read_bytes() == canonical(rehearsal_fixture.contract())
        count += 1

    print(json.dumps({
        "status": "PASS",
        "checks": count,
        "scope": "real-nexus-data-snapshot-format-synthetic-offline-downgrade-screen",
        "old_rust_binary_executed": False,
        "new_rust_binary_executed": False,
        "live_railway_data_read_or_modified": False,
        "production_release_authorized": False,
    }))


if __name__ == "__main__":
    main()
