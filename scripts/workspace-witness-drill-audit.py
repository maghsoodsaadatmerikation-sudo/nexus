#!/usr/bin/env python3
"""Read-only end-to-end NEXUS witness drill audit; production ALWAYS BLOCKED.

Checks exact independently pinned registry, a consumed challenge, both signed
observer reports, two full verified v2 staged copies, and cold backup restore
consistency. Optional Stage D script is corroborating evidence only: it never
proves physical host separation or authorizes a release.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("NEXUS drill verifier dependency unavailable")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


ledger = load("nexus_drill_challenges", "workspace-witness-challenge-ledger.py")
recovery = load("nexus_drill_recovery", "workspace-witness-v2-recovery.py")
two = ledger.two
stager = two.stager
trust = two.trust
v2 = two.v2


class DrillError(Exception):
    pass


def fail(reason):
    raise DrillError(reason)


def pinned_stage(path, expected_hash, label):
    if not path.is_absolute():
        fail(label + " must be an explicit absolute private staging directory")
    fd = trust.protected_directory(path)
    try:
        stager.assert_directory_identity(path, fd)
        raw = stager.read_locked(fd)
        if stager.digest(raw) != expected_hash:
            fail(label + " does not equal independently pinned approved v2 history")
        stager.assert_directory_identity(path, fd)
        return raw
    finally:
        os.close(fd)


def verify_consumption(args, pair):
    if not args.registry.is_absolute():
        fail("one-time challenge ledger must be an absolute private directory")
    fd = trust.protected_directory(args.registry)
    try:
        stager.assert_directory_identity(args.registry, fd)
        state, raw = ledger.read_locked(fd)
        if stager.digest(raw) != ledger.pin(args.registry_sha256, "challenge ledger"):
            fail("challenge ledger differs from independently pinned latest head")
        ledger.validate(state)
        matches = [e for e in state["events"]
                   if e["kind"] == "consume" and e["challenge_hex"] == args.challenge_hex]
        issued = [e for e in state["events"]
                  if e["kind"] == "issue" and e["challenge_hex"] == args.challenge_hex]
        if len(issued) != 1 or len(matches) != 1 or issued[0]["sequence"] >= matches[0]["sequence"]:
            fail("signed challenge must be issued once and already consumed exactly once")
        event = matches[0]
        if (event["origin_report_sha256"] != args.origin_report_sha256
                or event["recovery_report_sha256"] != args.recovery_report_sha256
                or event["bridge_sha256"] != pair["bridge_sha256"]
                or event["latest_sequence"] != pair["latest_sequence"]
                or event["latest_ack_sha256"] != pair["latest_ack_sha256"]):
            fail("consumed challenge does not bind the reviewed signed observer reports")
        stager.assert_directory_identity(args.registry, fd)
        if ledger.read_locked(fd)[1] != raw:
            fail("one-time challenge ledger changed during the audit")
        return {"registry_head_sha256": stager.digest(raw),
                "challenge_consume_sequence": event["sequence"],
                "events": len(state["events"])}
    finally:
        os.close(fd)


def check_stage_d(args):
    if args.stage_d_evidence is None and args.deployed_commit is None:
        return "NOT_SUPPLIED"
    if args.stage_d_evidence is None or args.deployed_commit is None:
        fail("Stage D evidence and expected deployed commit must both be specified")
    if not re.fullmatch(r"[0-9a-f]{40}", args.deployed_commit):
        fail("expected deployed commit must be a full 40-character SHA")
    if not args.stage_d_evidence.is_absolute() or not args.stage_d_evidence.is_dir():
        fail("Stage D evidence must be an explicitly selected existing directory")
    try:
        test = subprocess.run(
            ["bash", str(HERE / "v1.1-release-readiness.sh"),
             str(args.stage_d_evidence), args.deployed_commit],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30,
            check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DrillError("Stage D readiness verification did not finish") from exc
    if test.returncode != 0:
        return "BLOCKED_INCOMPLETE_OR_INVALID"
    return "EVIDENCE_SCRIPT_VERIFIED_NOT_HOST_INDEPENDENCE"


def audit(args):
    pair = two.verify_pair(args)
    if pair["status"] != "two-distinct-signer-observations-verified":
        fail("two independent signed observer reports were not validated")
    origin = pinned_stage(args.origin_store, pair["bridge_sha256"], "origin")
    restored = pinned_stage(args.restored_store, pair["bridge_sha256"], "restored")
    approved = trust.open_no_symlinks(args.approved_bridge, stager.MAX)
    if origin != restored or origin != approved:
        fail("origin and recovery staging copies diverge from approved canonical bridge")

    # Cold-backup verification includes all v1/v2 Ed25519 signed material,
    # the 3-party transition consent, independently selected keys and floor.
    _, backup_raw, proof = recovery.verify_backup(args)
    if (backup_raw != origin
            or proof["new_sequence"] != pair["latest_sequence"]
            or proof["new_last_ack_sha256"] != pair["latest_ack_sha256"]):
        fail("verified cold backup differs from independently approved restored state")
    consumed = verify_consumption(args, pair)
    stage_d = check_stage_d(args)
    return {
        "schema": "nexus.offsite.two-host-drill-audit.v1",
        "status": "offline-cryptographic-drill-consistent",
        "origin_and_restored_stage_identical": True,
        "cold_backup_verified": True,
        "separate_observer_ed25519_keys_verified": True,
        "challenge_consumed_once_in_pinned_ledger": True,
        "challenge_hex": args.challenge_hex,
        "registry_sha256": consumed["registry_head_sha256"],
        "registry_event_count": consumed["events"],
        "challenge_consume_sequence": consumed["challenge_consume_sequence"],
        "bridge_sha256": pair["bridge_sha256"],
        "latest_sequence": pair["latest_sequence"],
        "latest_ack_sha256": pair["latest_ack_sha256"],
        "stage_d_status": stage_d,
        "physical_host_independence_proven": False,
        "real_destructive_offhost_restore_proven": False,
        "provider_identity_and_failure_domain_attested": False,
        "production_key_cutover_implemented": False,
        "release_authorized": False,
        "release_gate": "BLOCKED",
        "remaining_evidence": [
            "independent physical host and failure-domain evidence",
            "real off-host encrypted backup and destructive restore drill",
            "third-party custody of current SHA-256 and sequence floors",
            "actual provider/service lifecycle and HTTPS Stage D evidence",
            "separately reviewed production v2 receiver and key cutover",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("verify", "release-gate"))
    two.common(parser)
    for flag in ("approved-bridge", "origin-report", "recovery-report",
                 "origin-public-key", "recovery-public-key",
                 "registry", "origin-store", "restored-store", "backup"):
        parser.add_argument("--" + flag, type=Path, required=True)
    for flag in ("origin-report-sha256", "recovery-report-sha256",
                 "origin-observer-id", "recovery-observer-id",
                 "registry-sha256", "backup-sha256"):
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--stage-d-evidence", type=Path)
    parser.add_argument("--deployed-commit")
    args = parser.parse_args()
    # recovery.verify_backup uses an independently pinned candidate SHA.
    # Only bind to the same CLI value after v2.verify independently checked it.
    args.expected_bridge_sha256 = ledger.pin(args.expected_bridge_sha256, "bridge")
    try:
        result = audit(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if args.mode == "release-gate":
            print("NEXUS TWO-HOST RELEASE GATE: BLOCKED; physical independence and operational cutover not proven", file=sys.stderr)
            return 1
        return 0
    except (DrillError, ledger.LedgerError, two.ObservationError,
            recovery.RecoveryError, stager.StageError, v2.EpochError,
            v2.transition.ConsentError, v2.custodian.CustodianError,
            v2.custodian.witness.WitnessError,
            trust.TrustError, OSError, ValueError, TypeError, KeyError) as exc:
        print("NEXUS TWO-HOST DRILL AUDIT DENIED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
