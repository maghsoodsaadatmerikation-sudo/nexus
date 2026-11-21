"""Offline audit tests. Synthetic-only; no provider key or network needed."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from model_compare_evidence import (
    HOLD, SCHEMA, InvalidEvidence, build_receipt, verify_receipt, _load, _canonical,
)
from model_quality_compare import MAX_PROBES


SOURCE = "1b2cd2f58d79f4833e512585a62c7700725bd7a4"
SLOTS = "primary,secondary"
SLOT_NAMES = ["primary", "secondary"]


def offline(*, configured=True):
    return {
        "status": "READY_TO_TEST" if configured else "NOT_READY",
        "scope": "offline_config_only",
        "models": [{"slot": "primary", "configured": True},
                   {"slot": "secondary", "configured": configured}],
        "provider_requests_planned_for_full_quality": 30,
        "provider_contact_attempted": False,
        "live_model_evaluated": False,
        "quality_gate": "NOT_RUN",
        "truth_claim": "NOT_PROVEN",
        "authority": "none",
    }


def entry(slot, passed=15, *, critical=False, aborted=False):
    return {
        "slot": slot,
        "status": "PASS" if passed >= 13 and not critical and not aborted else "FAIL",
        "evaluated": 15 if not aborted else 1,
        "passed": passed,
        "failed": 15 - passed if not aborted else 0,
        "errors": 0 if not aborted else 1,
        "critical_failures": ["hostile_excerpt"] if critical else [],
        "aborted_early": aborted,
        "abort_reason": "rate_limited" if aborted else None,
    }


def full(*, passed=(15, 15)):
    e = [entry(name, score) for name, score in zip(SLOT_NAMES, passed)]
    return {
        "status": "PASS" if min(passed) >= 13 else "FAIL",
        "scope": "fictional_text_probe_comparison",
        "run_mode": "full_quality",
        "models_requested": SLOT_NAMES,
        "models_evaluated": 2,
        "models": e,
        "comparison_complete": True,
        "comparable": True,
        "heuristic_order": sorted(SLOT_NAMES, key=lambda name: (
            -e[SLOT_NAMES.index(name)]["passed"], SLOT_NAMES.index(name))),
        "provider_requests_cap": 30,
        "provider_requests_attempted": 30,
        "provider_contact_attempted": True,
        "live_model_evaluated": True,
        "quality_gate": "HEURISTIC_ONLY",
        "billing_limit": "REQUEST_COUNT_ONLY_NOT_A_CURRENCY_CAP",
        "truth_claim": "NOT_PROVEN",
        "authority": "none",
    }


def receipt(report, *, mode="full_quality"):
    return build_receipt(
        report=report, mode=mode, slots=SLOTS,
        source_commit=SOURCE, run_id="44944344174", run_attempt="1"
    )


def test_valid_full_comparison_receipt_is_deterministic_and_always_holds():
    original = full()
    a = receipt(original)
    b = receipt(original)
    assert a == b and verify_receipt(a)
    assert a["schema"] == SCHEMA
    assert a["source_commit"] == SOURCE
    assert a["release_state"] == HOLD
    assert a["deploy_authorized"] is False
    assert a["public_origin_verified"] is False
    assert a["rollback_artifact_verified"] is False
    assert a["provider_billing_verified"] is False
    assert a["provider_response_independently_attested"] is False
    assert a["authority"] == "none"
    assert a["integrity_type"] == "unkeyed_sha256_not_an_independent_signature"
    assert a["receipt_sha256"] == hashlib.sha256(
        _canonical({k: v for k, v in a.items() if k != "receipt_sha256"})
    ).hexdigest()
    assert a["comparison"]["status"] == "PASS"
    assert a["comparison"]["heuristic_order"] == ["primary", "secondary"]


@pytest.mark.parametrize("configured", [True, False])
def test_offline_preflight_never_becomes_a_live_attestation(configured):
    a = receipt(offline(configured=configured), mode="check_config")
    assert verify_receipt(a)
    assert a["release_state"] == HOLD
    assert a["comparison"]["status"] == ("READY_TO_TEST" if configured else "NOT_READY")
    assert a["comparison"]["provider_contact_attempted"] is False
    assert a["comparison"]["live_model_evaluated"] is False
    assert a["comparison"]["quality_gate"] == "NOT_RUN"


def test_comparison_failure_still_has_verifiable_receipt_without_approval():
    source = full(passed=(12, 15))
    source["models"][0]["status"] = "FAIL"
    a = receipt(source)
    assert verify_receipt(a)
    assert a["comparison"]["heuristic_order"] == ["secondary", "primary"]
    assert a["comparison"]["status"] == "FAIL"
    assert a["release_state"] == HOLD


def test_incomplete_provider_comparison_cannot_be_ranked():
    report = full()
    report.update({
        "status": "FAIL",
        "models_evaluated": 1,
        "models": [entry("primary", passed=0, aborted=True)],
        "comparison_complete": False,
        "comparable": False,
        "heuristic_order": [],
        "provider_requests_attempted": 1,
        "live_model_evaluated": False,
        "quality_gate": "NOT_RUN",
    })
    report["models"][0]["failed"] = 0
    report["models"][0]["passed"] = 0
    a = receipt(report)
    assert verify_receipt(a)
    assert a["comparison"]["models_evaluated"] == 1
    assert a["comparison"]["heuristic_order"] == []


@pytest.mark.parametrize("change", [
    lambda r: r.__setitem__("endpoint", "https://secret-host.invalid"),
    lambda r: r.__setitem__("raw_answer", "private chat text"),
    lambda r: r.__setitem__("models", r["models"] + [{"slot": "tertiary", "model": "provider-secret"}]),
    lambda r: r.__setitem__("status", "READY_TO_DEPLOY"),
    lambda r: r.__setitem__("provider_requests_attempted", 31),
    lambda r: r.__setitem__("provider_requests_attempted", True),
    lambda r: r.__setitem__("provider_requests_cap", 999),
    lambda r: r.__setitem__("provider_contact_attempted", False),
    lambda r: r.__setitem__("quality_gate", "CERTIFIED"),
    lambda r: r.__setitem__("truth_claim", "PROVEN"),
    lambda r: r.__setitem__("authority", "owner"),
    lambda r: r.__setitem__("comparable", False),
    lambda r: r.__setitem__("heuristic_order", ["tertiary"]),
    lambda r: r["models"][0].__setitem__("api_key", "private-key"),
    lambda r: r["models"][0].__setitem__("slot", "tertiary"),
    lambda r: r["models"][0].__setitem__("critical_failures", ["arbitrary-id"]),
    lambda r: r["models"][0].__setitem__("abort_reason", "https://sensitive.invalid"),
    lambda r: r["models"][0].__setitem__("passed", -1),
    lambda r: r["models"][0].__setitem__("evaluated", 16),
])
def test_unapproved_or_inconsistent_metrics_fail_closed(change):
    report = full()
    change(report)
    with pytest.raises(InvalidEvidence):
        receipt(report)


@pytest.mark.parametrize("tamper", [
    lambda r: r.__setitem__("release_state", "GO"),
    lambda r: r.__setitem__("deploy_authorized", True),
    lambda r: r.__setitem__("public_origin_verified", True),
    lambda r: r.__setitem__("rollback_artifact_verified", True),
    lambda r: r.__setitem__("provider_billing_verified", True),
    lambda r: r.__setitem__("authority", "production"),
    lambda r: r.__setitem__("github_run_id", "not-an-id"),
    lambda r: r.__setitem__("source_commit", "0" * 39),
    lambda r: r.__setitem__("integrity_type", "cryptographic_signature"),
    lambda r: r.__setitem__("receipt_sha256", "0" * 64),
    lambda r: r["comparison"]["models"][0].__setitem__("passed", 4),
    lambda r: r.__setitem__("text", "fictional provider answer"),
])
def test_receipt_tampering_or_forged_release_pass_is_rejected(tamper):
    a = receipt(full())
    tamper(a)
    with pytest.raises(InvalidEvidence):
        verify_receipt(a)


@pytest.mark.parametrize("source_sha,run_id,attempt", [
    ("not-a-sha", "1", "1"),
    ("A" * 40, "1", "1"),
    (SOURCE, "0", "1"),
    (SOURCE, "1", "0"),
    (SOURCE, "-1", "1"),
    (SOURCE, "1", "unknown"),
])
def test_invalid_git_provenance_rejected_before_write(source_sha, run_id, attempt):
    with pytest.raises(InvalidEvidence):
        build_receipt(report=offline(), mode="check_config", slots=SLOTS,
                      source_commit=source_sha, run_id=run_id,
                      run_attempt=attempt)


def test_load_rejects_duplicate_keys_and_oversize_without_logging(tmp_path, capsys):
    p = tmp_path / "report.json"
    p.write_text('{"status":"READY_TO_TEST","status":"PRODUCTION"}', encoding="utf-8")
    with pytest.raises(InvalidEvidence):
        _load(str(p))
    p.write_bytes(b"x" * 32769)
    with pytest.raises(InvalidEvidence):
        _load(str(p))
    assert not capsys.readouterr().out


def test_cli_build_verify_round_trip_is_non_authoritative(tmp_path, monkeypatch, capsys):
    from model_compare_evidence import main
    path = tmp_path / "private-comparison-report.json"
    artifact = tmp_path / "auditable-evidence.json"
    path.write_text(json.dumps(full()), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "model_compare_evidence", "--build", "--report", str(path),
        "--out", str(artifact), "--mode", "full_quality",
        "--slots", SLOTS, "--source-commit", SOURCE,
        "--run-id", "44944344174", "--run-attempt", "1"
    ])
    assert main() == 0
    data = json.loads(artifact.read_text())
    assert verify_receipt(data)
    built = json.loads(capsys.readouterr().out)
    assert built["status"] == "EVIDENCE_RECORDED_NOT_DEPLOYED"
    assert built["release_state"] == HOLD
    monkeypatch.setattr("sys.argv", [
        "model_compare_evidence", "--verify", "--artifact", str(artifact),
    ])
    assert main() == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["status"] == "RECEIPT_DIGEST_AND_SCHEMA_PASS"
    assert checked["release_state"] == HOLD


def test_cli_forged_report_does_not_write_or_log_secret(tmp_path, monkeypatch, capsys):
    from model_compare_evidence import main
    p = tmp_path / "malicious-report.json"
    o = tmp_path / "evidence.json"
    report = full()
    report["provider_key"] = "private-secret-not-for-log"
    p.write_text(json.dumps(report))
    monkeypatch.setattr("sys.argv", [
        "model_compare_evidence", "--build", "--report", str(p), "--out", str(o),
        "--mode", "full_quality", "--slots", SLOTS,
        "--source-commit", SOURCE, "--run-id", "1", "--run-attempt", "1",
    ])
    assert main() == 2
    assert not o.exists()
    output = capsys.readouterr().out
    assert "INVALID_EVIDENCE" in output
    assert "private-secret-not-for-log" not in output


def test_workflow_requires_receipt_integrity_check_and_holds_release():
    from pathlib import Path
    yml = (Path(__file__).resolve().parents[2] /
           ".github/workflows/manual-model-comparison.yml").read_text()
    assert "model_compare_evidence" in yml
    assert "--verify --artifact" in yml
    assert "retention-days: 14" in yml
    assert "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f" in yml
    assert "manual-model-comparison" in yml
    assert "deploy" not in yml.lower() or "not_deployed" in yml.lower()
