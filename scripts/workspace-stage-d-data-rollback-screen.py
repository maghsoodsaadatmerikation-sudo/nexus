#!/usr/bin/env python3
"""Offline Stage D data-compatibility screening; never approves a downgrade.

Compares independently pinned, real NEXUS data-snapshot.v1 archives using
strict bounded file/marker validation. A structural PASS is NOT evidence that
the old Rust binary can decode, import or safely continue on newer data.
"""
import argparse
import base64
import binascii
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent


def imported(alias, filename):
    spec = importlib.util.spec_from_file_location(alias, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("NEXUS snapshot dependency missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshot = imported("nexus_data_compat_snapshot", "data-snapshot.py")
trust = imported("nexus_data_compat_trust", "workspace-trust.py")
rehearsal = imported(
    "nexus_data_compat_rehearsal", "workspace-stage-d-upgrade-rehearsal.py")

SCHEMA = "nexus.stage-d.data-rollback-screen.v1"
EVENT_NAMES = {
    "WorkspaceCreated", "ClaimAdded", "AlternativeAdded",
    "MachineAnalysisRecorded", "HumanJudgmentTransition",
}
PLAN_FIELDS = rehearsal.PLAN_FIELDS


class CompatibilityError(Exception):
    pass


def deny(reason):
    raise CompatibilityError(reason)


def parse_workspace(path, raw):
    obj = trust.strict_json(raw)
    if not isinstance(obj, dict) or set(obj) != {"schema_version", "workspace", "events"}:
        deny("workspace snapshot must have exact recognized top-level shape")
    if type(obj["schema_version"]) is not int or obj["schema_version"] != 1:
        deny("unrecognized workspace schema version")
    ws = obj["workspace"]
    if not isinstance(ws, dict) or not isinstance(ws.get("id"), str):
        deny("workspace missing an explicit string identity")
    try:
        encoded = path[:-5]
        expected_id = bytes.fromhex(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise CompatibilityError("invalid workspace filename encoding") from exc
    if ws["id"] != expected_id:
        deny("workspace identity differs from selected snapshot file")
    events = obj["events"]
    if not isinstance(events, list) or not events:
        deny("workspace history has no creation event")
    for n, entry in enumerate(events):
        if not isinstance(entry, dict) or set(entry) != {
                "sequence", "provenance_id", "kind"}:
            deny("unknown workspace event layout")
        if type(entry["sequence"]) is not int or entry["sequence"] != n:
            deny("workspace audit history is not contiguous and monotonically numbered")
        if not isinstance(entry["provenance_id"], str) or not entry["provenance_id"].strip():
            deny("missing or malformed workspace event provenance")
        kind = entry["kind"]
        if isinstance(kind, str):
            name = kind
        elif isinstance(kind, dict) and len(kind) == 1:
            name = next(iter(kind))
        else:
            deny("unknown workspace event discriminant")
        if name not in EVENT_NAMES:
            deny("unrecognized workspace event kind requires a new versioned parser")
        if (n == 0) != (name == "WorkspaceCreated"):
            deny("workspace creation event missing or repeated")
    return obj


def archive(path, pinned_sha):
    if not path.is_absolute():
        deny("snapshot archive must use an explicit absolute path")
    if not isinstance(pinned_sha, str) or not trust.SHA256_HEX.fullmatch(pinned_sha):
        deny("independent lowercase SHA-256 archive pin required")
    raw = trust.open_no_symlinks(path, snapshot.MAX_BYTES)
    if hashlib.sha256(raw).hexdigest() != pinned_sha:
        deny("archive differs from independently approved SHA-256")
    doc = trust.strict_json(raw)
    if trust.encode_json(doc) != raw:
        deny("NEXUS archive must be strictly canonical JSON bytes")
    if (not isinstance(doc, dict)
            or set(doc) != {"schema", "authority", "consistency", "files"}
            or doc["schema"] != snapshot.SCHEMA
            or doc["authority"] != "none"
            or doc["consistency"] != "offline-caller-asserted"):
        deny("invalid NEXUS data archive envelope")
    files = doc["files"]
    if not isinstance(files, list) or len(files) > snapshot.MAX_FILES:
        deny("data archive file index exceeds limit")
    result = {}
    total = 0
    for record in files:
        if not isinstance(record, dict) or set(record) != {
                "path", "size", "sha256", "data"}:
            deny("invalid NEXUS data archive file record")
        name = record["path"]
        if not isinstance(name, str) or name in result:
            deny("duplicate or invalid supported archive path")
        if not isinstance(record["data"], str):
            deny("data archive record requires canonical base64")
        try:
            decoded = base64.b64decode(record["data"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CompatibilityError("invalid data archive base64") from exc
        if base64.b64encode(decoded).decode("ascii") != record["data"]:
            deny("noncanonical data archive base64")
        total += len(decoded)
        if total > snapshot.MAX_BYTES:
            deny("decoded snapshot capacity exceeded")
        if (type(record["size"]) is not int or record["size"] != len(decoded)
                or not isinstance(record["sha256"], str)
                or record["sha256"] != hashlib.sha256(decoded).hexdigest()):
            deny("data archive record digest or size invalid")
        snapshot.validate_file(name, decoded)
        if name.endswith(".json"):
            parse_workspace(name, decoded)
        result[name] = decoded
    if list(result) != sorted(result):
        deny("noncanonical data archive record order")
    return result


def metadata_plan(args):
    # Hold the approved bytes fixed across hashing and parsing; a second
    # pathname open would admit a swap between those two operations.
    raw = trust.open_no_symlinks(args.plan, 16384)
    p = trust.strict_json(raw)
    # Caller pins *exact* approved immutable bytes; do not trust a plan's
    # self-declared digest or internally recompute a trusted floor.
    if (not isinstance(args.plan_sha256, str)
            or not trust.SHA256_HEX.fullmatch(args.plan_sha256)
            or hashlib.sha256(raw).hexdigest() != args.plan_sha256):
        deny("operator plan differs from independently approved exact hash")
    if trust.encode_json(p) != raw:
        deny("noncanonical operator plan")
    if not isinstance(p, dict) or set(p) != PLAN_FIELDS or p["schema"] != rehearsal.SCHEMA:
        deny("invalid operator-approved upgrade rehearsal plan")
    # Reuse strict full review-only policy from prior stage; separately
    # pin selected commit identities so a coherent but malicious plan
    # cannot authorize changing the workload role.
    a = argparse.Namespace(
        project_id=p["project_id"],
        environment_id=p["environment_id"],
        expected_repo=p["repository"],
        source_service_id=p["source_service_id"],
        restore_service_id=p["restore_service_id"],
        source_volume_id=p["source_volume_id"],
        restore_volume_id=p["restore_volume_id"],
        plan=args.plan,
        plan_sha256=args.plan_sha256,
    )
    rehearsal.load_plan(a)
    for key, flag in (
        ("source_current_commit", args.source_commit),
        ("restore_current_commit", args.restore_commit),
        ("proposed_rehearsal_commit", args.target_commit),
    ):
        if p[key] != rehearsal.commit(flag, key):
            deny("independently selected Git revision differs from operator plan")
    return p


def inspect(before, after):
    a_work = {p for p in before if p.endswith(".json")}
    b_work = {p for p in after if p.endswith(".json")}
    a_request = {p for p in before if p.startswith("requests/")}
    b_request = {p for p in after if p.startswith("requests/")}
    reasons = set()
    counters = {
        "previous_workspaces": len(a_work),
        "candidate_workspaces": len(b_work),
        "new_workspaces": len(b_work - a_work),
        "missing_workspaces": len(a_work - b_work),
        "changed_workspaces": 0,
        "history_prefix_divergences": 0,
        "history_shortened": 0,
        "history_extended": 0,
        "workspace_fields_changed": 0,
        "new_request_markers": len(b_request - a_request),
        "missing_request_markers": len(a_request - b_request),
        "marker_bytes_changed": 0,
        "indeterminate_to_pending": 0,
        "pending_to_indeterminate": 0,
    }
    if a_work - b_work:
        reasons.add("workspace_disappeared")
    if b_work - a_work:
        reasons.add("new_workspace_not_proven_readable_by_old_runtime")
    if a_request - b_request:
        reasons.add("request_reservation_lost")
    if b_request - a_request:
        reasons.add("new_request_reservations_not_proven_downgrade_safe")
    for name in a_work & b_work:
        if before[name] == after[name]:
            continue
        counters["changed_workspaces"] += 1
        a, b = parse_workspace(name, before[name]), parse_workspace(name, after[name])
        a_events, b_events = a["events"], b["events"]
        if len(b_events) < len(a_events):
            counters["history_shortened"] += 1
            reasons.add("audit_history_rollback")
        elif b_events[:len(a_events)] != a_events:
            counters["history_prefix_divergences"] += 1
            reasons.add("audit_history_divergence")
        elif len(b_events) > len(a_events):
            counters["history_extended"] += 1
            reasons.add("new_event_requires_legacy_reader_compatibility_proof")
        if a["workspace"] != b["workspace"]:
            counters["workspace_fields_changed"] += 1
            reasons.add("workspace_state_changed_without_versioned_reverse_migration")
        if (a["events"] == b["events"] and a["workspace"] == b["workspace"]):
            reasons.add("workspace_json_rewritten_without_content_change")
    for name in a_request & b_request:
        old, new = before[name], after[name]
        if old == new:
            continue
        counters["marker_bytes_changed"] += 1
        reasons.add("request_marker_bytes_changed")
        if old != b"pending\n" and new == b"pending\n":
            counters["indeterminate_to_pending"] += 1
            reasons.add("uncertain_request_made_pending_again")
        if old == b"pending\n" and new != b"pending\n":
            counters["pending_to_indeterminate"] += 1
            reasons.add("pending_request_became_indeterminate")
    old_quarantine = snapshot.RECOVERY_MARKER in before
    new_quarantine = snapshot.RECOVERY_MARKER in after
    if old_quarantine and not new_quarantine:
        reasons.add("recovery_quarantine_disappeared")
    if new_quarantine and not old_quarantine:
        reasons.add("recovery_quarantine_added")
    identical = before == after
    if not identical:
        reasons.add("snapshot_contents_differ")
    if not a_work:
        reasons.add("no_workspace_history_available_for_reader_test")
    return counters, reasons, identical


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("inspect", "rollback-gate"))
    for name in ("before", "after", "plan"):
        p.add_argument("--" + name, type=Path, required=True)
        p.add_argument("--" + name + "-sha256", required=True)
    for name in ("source-commit", "restore-commit", "target-commit"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    try:
        metadata_plan(args)
        before = archive(args.before, args.before_sha256)
        after = archive(args.after, args.after_sha256)
        counts, reasons, identical = inspect(before, after)
        # A zero content delta is not an older-binary decoder test. A
        # rollback gate may never be elevated by this structural tool.
        report = {
            "schema": SCHEMA,
            "status": "offline-archive-data-difference-screened",
            "before_archive_sha256": args.before_sha256,
            "after_archive_sha256": args.after_sha256,
            "audit": counts,
            "snapshots_byte_identical": identical,
            "findings": sorted(reasons),
            "structural_screen": (
                "NO_CONTENT_DELTA_ONLY" if identical else "DOWNGRADE_REVIEW_REQUIRED"),
            "old_rust_reader_executed": False,
            "new_rust_reader_executed": False,
            "reverse_schema_migration_verified": False,
            "independent_runtime_volume_backups_proven": False,
            "automatic_data_rollback_authorized": False,
            "production_release_authorized": False,
            "release_gate": "BLOCKED",
        }
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        if args.mode == "rollback-gate":
            print("NEXUS DATA DOWNGRADE: BLOCKED; old Rust reader/schema reversal not proven",
                  file=sys.stderr)
            return 1
        return 0
    except (CompatibilityError, rehearsal.RehearsalError,
            snapshot.SnapshotError, trust.TrustError, TypeError,
            ValueError, OSError, KeyError, UnicodeError) as exc:
        print("NEXUS DATA DOWNGRADE SCREEN DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
