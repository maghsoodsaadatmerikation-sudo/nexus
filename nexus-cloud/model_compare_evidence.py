"""Offline, fail-closed audit receipt for an opt-in model comparison.

Never authorizes deployment or attests independently to provider contact. The
receipt hashes only allowlisted synthetic benchmark counts, fixed status codes
and source/run IDs; raw prompts, completions, URLs and keys are not accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from model_quality_compare import MAX_PROBES, selected_slots
from model_quality_eval import PROBES


SCHEMA = "nexus.model-comparison-evidence.v1"
HOLD = "HOLD_INDEPENDENT_PROVIDER_COST_DEPLOY_AND_ROLLBACK_EVIDENCE"
HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")
NUMBER = re.compile(r"[1-9][0-9]{0,14}\Z")
REASONS = frozenset({
    "authentication", "billing", "rate_limited", "upstream_unavailable",
    "request_rejected", "invalid_response", "transport_or_validation",
})
CRITICAL_IDS = frozenset(p.key for p in PROBES if p.critical)
CORE = frozenset({
    "status", "scope", "run_mode", "models_requested", "models_evaluated",
    "models", "comparison_complete", "comparable", "heuristic_order",
    "provider_requests_cap", "provider_requests_attempted",
    "provider_contact_attempted", "live_model_evaluated", "quality_gate",
    "billing_limit", "truth_claim", "authority",
})
MODEL = frozenset({
    "slot", "status", "evaluated", "passed", "failed", "errors",
    "critical_failures", "aborted_early", "abort_reason",
})
PREFLIGHT = frozenset({
    "status", "scope", "models", "provider_requests_planned_for_full_quality",
    "provider_contact_attempted", "live_model_evaluated", "quality_gate",
    "truth_claim", "authority",
})
DECLINED = frozenset({
    "status", "reason", "provider_contact_attempted", "quality_gate",
    "truth_claim", "authority",
})
RUNNER_ERROR = frozenset({
    "status", "reason", "run_mode", "provider_requests_attempted",
    "provider_contact_attempted", "quality_gate", "truth_claim", "authority",
})
DECLINE_REASONS = frozenset({
    "unsupported_mode", "invalid_model_selection", "comparison_scope_too_large",
    "explicit_comparison_consent_required", "exact_request_count_acknowledgement_required",
    "exact_global_attempt_cap_required", "selected_model_unconfigured",
})


class InvalidEvidence(ValueError):
    pass


def _require(condition: bool) -> None:
    if not condition:
        raise InvalidEvidence("benchmark receipt format or claims are invalid")


def _fields(value: Any, expected: frozenset[str]) -> dict:
    _require(type(value) is dict and set(value) == expected)
    return value


def _int(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    found: dict = {}
    for key, val in pairs:
        _require(key not in found)
        found[key] = val
    return found


def _load(path: str) -> dict:
    raw = Path(path).read_bytes()
    _require(0 < len(raw) <= 32768)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
        raise InvalidEvidence("invalid JSON") from None
    _require(type(value) is dict)
    return value


def _validate_report(report: dict, *, mode: str, slots: tuple[str, ...]) -> dict:
    _require(mode in {"check_config", "single_smoke", "full_quality"})
    n = len(slots)
    planned = (1 if mode == "single_smoke" else MAX_PROBES) * n
    if report.get("status") == "NOT_RUN":
        _fields(report, DECLINED)
        _require(report["reason"] in DECLINE_REASONS)
        _require(report["provider_contact_attempted"] is False and
                 report["quality_gate"] == "NOT_RUN" and
                 report["truth_claim"] == "NOT_PROVEN" and
                 report["authority"] == "none")
        return report.copy()
    if report.get("status") == "ERROR":
        _fields(report, RUNNER_ERROR)
        _require(mode != "check_config" and report["run_mode"] == mode and
                 report["reason"] == "comparison_runner_failure" and
                 _int(report["provider_requests_attempted"], 0, planned) and
                 report["provider_contact_attempted"] is
                 (report["provider_requests_attempted"] > 0) and
                 report["quality_gate"] == "NOT_RUN" and
                 report["truth_claim"] == "NOT_PROVEN" and
                 report["authority"] == "none")
        return report.copy()
    if mode == "check_config":
        _fields(report, PREFLIGHT)
        _require(report["scope"] == "offline_config_only" and
                 report["provider_contact_attempted"] is False and
                 report["live_model_evaluated"] is False and
                 report["quality_gate"] == "NOT_RUN" and
                 report["truth_claim"] == "NOT_PROVEN" and
                 report["authority"] == "none" and
                 report["provider_requests_planned_for_full_quality"] == MAX_PROBES * n)
        entries = report["models"]
        _require(type(entries) is list and len(entries) == n)
        for actual, slot in zip(entries, slots):
            _fields(actual, frozenset({"slot", "configured"}))
            _require(actual["slot"] == slot and type(actual["configured"]) is bool)
        expected_status = "READY_TO_TEST" if all(x["configured"] for x in entries) else "NOT_READY"
        _require(report["status"] == expected_status)
        return {
            **{k: value for k, value in report.items() if k != "models"},
            "models": [{"slot": x["slot"], "configured": x["configured"]} for x in entries],
        }
    _fields(report, CORE)
    _require(report["scope"] == "fictional_text_probe_comparison" and
             report["run_mode"] == mode and report["status"] in {"PASS", "FAIL"} and
             report["models_requested"] == list(slots) and
             type(report["models"]) is list and
             _int(report["models_evaluated"], 0, n) and
             report["models_evaluated"] == len(report["models"]) and
             type(report["comparison_complete"]) is bool and
             type(report["comparable"]) is bool and
             type(report["heuristic_order"]) is list and
             _int(report["provider_requests_cap"], planned, planned) and
             _int(report["provider_requests_attempted"], 0, planned) and
             report["provider_contact_attempted"] is
             (report["provider_requests_attempted"] > 0) and
             type(report["live_model_evaluated"]) is bool and
             report["quality_gate"] in {"NOT_RUN", "HEURISTIC_ONLY"} and
             report["billing_limit"] == "REQUEST_COUNT_ONLY_NOT_A_CURRENCY_CAP" and
             report["truth_claim"] == "NOT_PROVEN" and report["authority"] == "none")
    answers = []
    for pos, entry in enumerate(report["models"]):
        _fields(entry, MODEL)
        maximum = 1 if mode == "single_smoke" else MAX_PROBES
        _require(entry["slot"] == slots[pos] and
                 entry["status"] in {"PASS", "FAIL"} and
                 _int(entry["evaluated"], 0, maximum) and
                 _int(entry["passed"], 0, maximum) and
                 _int(entry["failed"], 0, maximum) and
                 _int(entry["errors"], 0, maximum) and
                 entry["passed"] + entry["failed"] + entry["errors"] == entry["evaluated"] and
                 type(entry["critical_failures"]) is list and
                 len(entry["critical_failures"]) <= len(CRITICAL_IDS) and
                 all(type(q) is str and q in CRITICAL_IDS for q in entry["critical_failures"]) and
                 len(set(entry["critical_failures"])) == len(entry["critical_failures"]) and
                 type(entry["aborted_early"]) is bool and
                 (entry["abort_reason"] is None or
                  (type(entry["abort_reason"]) is str and entry["abort_reason"] in REASONS)))
        if mode == "single_smoke":
            _require(entry["critical_failures"] == [] and
                     not entry["aborted_early"] and
                     entry["status"] == ("PASS" if entry["passed"] == 1 else "FAIL") and
                     (entry["abort_reason"] is not None) == (entry["errors"] > 0))
        else:
            passed_gate = (entry["evaluated"] == MAX_PROBES and
                           entry["errors"] == 0 and not entry["critical_failures"] and
                           not entry["aborted_early"] and
                           entry["passed"] / MAX_PROBES >= 0.85)
            _require(entry["status"] == ("PASS" if passed_gate else "FAIL") and
                     entry["aborted_early"] == (entry["abort_reason"] is not None))
        answers.append({k: entry[k] for k in MODEL})
    # The comparator never lets a smoke run declare heuristic comparability.
    complete = len(answers) == n and (mode == "single_smoke" or all(
        x["evaluated"] == MAX_PROBES and not x["aborted_early"] for x in answers
    ))
    comparable = mode == "full_quality" and complete
    ordered = [e["slot"] for e in sorted(answers, key=lambda x: (
        -x["passed"], slots.index(x["slot"]))) ] if comparable else []
    all_pass = complete and all(x["status"] == "PASS" for x in answers)
    _require(report["comparison_complete"] is complete and
             report["comparable"] is comparable and
             report["live_model_evaluated"] is comparable and
             report["quality_gate"] == ("HEURISTIC_ONLY" if comparable else "NOT_RUN") and
             report["heuristic_order"] == ordered and
             report["status"] == ("PASS" if all_pass else "FAIL"))
    return {**{k: report[k] for k in CORE if k != "models"}, "models": answers}


def build_receipt(*, report: dict, mode: str, slots: str, source_commit: str,
                  run_id: str, run_attempt: str) -> dict:
    selection = selected_slots(slots)
    _require(selection is not None and bool(HEX_SHA.fullmatch(source_commit)) and
             bool(NUMBER.fullmatch(run_id)) and
             bool(NUMBER.fullmatch(run_attempt)))
    reviewed = _validate_report(report, mode=mode, slots=selection)
    proof = {
        "schema": SCHEMA,
        "source_commit": source_commit,
        "github_run_id": run_id,
        "github_run_attempt": run_attempt,
        "run_mode": mode,
        "model_slots": list(selection),
        "comparison": reviewed,
        "release_state": HOLD,
        "deploy_authorized": False,
        "public_origin_verified": False,
        "provider_billing_verified": False,
        "provider_response_independently_attested": False,
        "rollback_artifact_verified": False,
        "synthetic_comparison_is_not_production_readiness": True,
        "authority": "none",
        "integrity_type": "unkeyed_sha256_not_an_independent_signature",
    }
    return {**proof, "receipt_sha256": hashlib.sha256(_canonical(proof)).hexdigest()}


def verify_receipt(receipt: dict) -> bool:
    _require(type(receipt) is dict and
             set(receipt) == {
                 "schema", "source_commit", "github_run_id", "github_run_attempt",
                 "run_mode", "model_slots", "comparison", "release_state",
                 "deploy_authorized", "public_origin_verified",
                 "provider_billing_verified", "provider_response_independently_attested",
                 "rollback_artifact_verified", "synthetic_comparison_is_not_production_readiness",
                 "authority", "integrity_type", "receipt_sha256",
             })
    _require(receipt["schema"] == SCHEMA and receipt["release_state"] == HOLD and
             receipt["deploy_authorized"] is False and
             receipt["public_origin_verified"] is False and
             receipt["provider_billing_verified"] is False and
             receipt["provider_response_independently_attested"] is False and
             receipt["rollback_artifact_verified"] is False and
             receipt["synthetic_comparison_is_not_production_readiness"] is True and
             receipt["authority"] == "none" and
             receipt["integrity_type"] == "unkeyed_sha256_not_an_independent_signature")
    _require(type(receipt["model_slots"]) is list and
             all(type(s) is str for s in receipt["model_slots"]))
    selection = selected_slots(",".join(receipt["model_slots"]))
    _require(selection == tuple(receipt["model_slots"]) and
             bool(HEX_SHA.fullmatch(receipt["source_commit"])) and
             bool(NUMBER.fullmatch(receipt["github_run_id"])) and
             bool(NUMBER.fullmatch(receipt["github_run_attempt"])))
    _validate_report(receipt["comparison"], mode=receipt["run_mode"], slots=selection)
    digest = receipt["receipt_sha256"]
    _require(type(digest) is str and bool(re.fullmatch("[a-f0-9]{64}", digest)))
    actual = hashlib.sha256(_canonical({k: v for k, v in receipt.items()
                                        if k != "receipt_sha256"})).hexdigest()
    _require(digest == actual)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    work = parser.add_mutually_exclusive_group(required=True)
    work.add_argument("--build", action="store_true")
    work.add_argument("--verify", action="store_true")
    parser.add_argument("--report", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--artifact", default="")
    parser.add_argument("--mode", default="")
    parser.add_argument("--slots", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", default="")
    args = parser.parse_args()
    try:
        if args.build:
            _require(args.report and args.out and not args.artifact)
            report = _load(args.report)
            receipt = build_receipt(
                report=report, mode=args.mode, slots=args.slots,
                source_commit=args.source_commit, run_id=args.run_id,
                run_attempt=args.run_attempt)
            verify_receipt(receipt)
            Path(args.out).write_bytes(_canonical(receipt) + b"\n")
            print(json.dumps({"status": "EVIDENCE_RECORDED_NOT_DEPLOYED",
                              "release_state": HOLD, "receipt_sha256": receipt["receipt_sha256"]},
                             sort_keys=True))
        else:
            _require(args.artifact and not args.report and not args.out)
            receipt = _load(args.artifact)
            verify_receipt(receipt)
            print(json.dumps({"status": "RECEIPT_DIGEST_AND_SCHEMA_PASS",
                              "release_state": HOLD, "source_commit": receipt["source_commit"],
                              "receipt_sha256": receipt["receipt_sha256"]},
                             sort_keys=True))
        return 0
    except (InvalidEvidence, OSError, TypeError, ValueError, KeyError, AttributeError):
        # All exception and source values discarded, because file paths,
        # malformed JSON or provider replies could contain private content.
        print(json.dumps({"status": "INVALID_EVIDENCE",
                          "release_state": HOLD, "authority": "none"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
