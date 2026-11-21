#!/usr/bin/env python3
"""Bounded, opt-in comparison of 2–3 configured NEXUS text-model routes.

Configuration checks are offline. Real probes are fixed fictional examples,
not user conversations. A successful result is not a guarantee of correctness,
cost, provider uptime, or production readiness.
"""
from __future__ import annotations

import argparse
import json
import os

import httpx

from model_quality_eval import PROBES, meets_gate, run_live, smoke_live
from studio_model import MODEL_SLOTS, read_model_catalog


MAX_PROBES = len(PROBES)
MAX_TOTAL_REQUESTS = 3 * MAX_PROBES
SLOTS = frozenset(MODEL_SLOTS)


def decline(reason: str) -> tuple[int, dict]:
    return 2, {
        "status": "NOT_RUN",
        "reason": reason,
        "provider_contact_attempted": False,
        "quality_gate": "NOT_RUN",
        "truth_claim": "NOT_PROVEN",
        "authority": "none",
    }


def selected_slots(raw: str) -> tuple[str, ...] | None:
    """Strict finite slot names: never URLs, arbitrary model IDs or wildcards."""
    if not isinstance(raw, str) or len(raw) > 30:
        return None
    parts = tuple(raw.split(","))
    if len(parts) < 2 or len(parts) > len(MODEL_SLOTS) or len(set(parts)) != len(parts):
        return None
    if any(slot not in SLOTS for slot in parts):
        return None
    return parts


class AttemptCap:
    """Guard every actual HTTPX stream construction, even if probe code changes.

    Count BEFORE handing the request to HTTPX; failed/cancelled attempts are
    never refunded. No retry or redirect is offered by the comparison runner.
    This limits attempts, not dollars or tokens. Use provider-side hard quotas.
    """

    def __init__(self, client: httpx.Client, limit: int):
        self._client = client
        self.limit = limit
        self.attempted = 0

    def stream(self, *args, **kwargs):
        if self.attempted >= self.limit:
            raise ValueError("comparison attempt ceiling reached")
        self.attempted += 1
        return self._client.stream(*args, **kwargs)


def compare_models(
    *,
    mode: str,
    slots: str,
    consent: str = "",
    acknowledgement: str = "",
    max_requests: str = "",
    client_factory=None,
) -> tuple[int, dict]:
    """Fail closed BEFORE creating any network client or requesting a provider.

    Full comparisons have exactly 15 fixed probes per selected model.
    Failure, malformed replies or rate limits abort the rest of the comparison,
    rather than probing further accounts after an upstream rejection.
    """
    if mode not in {"check_config", "single_smoke", "full_quality"}:
        return decline("unsupported_mode")
    selection = selected_slots(slots)
    if selection is None:
        return decline("invalid_model_selection")
    planned = (1 if mode == "single_smoke" else MAX_PROBES) * len(selection)
    if planned > MAX_TOTAL_REQUESTS:
        return decline("comparison_scope_too_large")

    # A single immutable snapshot keeps model/key/URL combinations together.
    catalog = read_model_catalog()
    if mode == "check_config":
        return 0, {
            "status": "READY_TO_TEST" if all(x in catalog for x in selection) else "NOT_READY",
            "scope": "offline_config_only",
            "models": [{"slot": slot, "configured": slot in catalog} for slot in selection],
            "provider_requests_planned_for_full_quality": MAX_PROBES * len(selection),
            "provider_contact_attempted": False,
            "live_model_evaluated": False,
            "quality_gate": "NOT_RUN",
            "truth_claim": "NOT_PROVEN",
            "authority": "none",
        }
    if consent != "YES":
        return decline("explicit_comparison_consent_required")
    # An exact call-count acknowledgement, NOT a monetary estimate.
    if acknowledgement != f"I_APPROVE_{planned}_PROVIDER_REQUESTS":
        return decline("exact_request_count_acknowledgement_required")
    if (not isinstance(max_requests, str) or not max_requests.isascii()
        or not max_requests.isdecimal() or max_requests != str(planned)):
        return decline("exact_global_attempt_cap_required")
    if any(slot not in catalog for slot in selection):
        return decline("selected_model_unconfigured")

    factory = httpx.Client if client_factory is None else client_factory
    results: list[dict] = []
    cap = None
    try:
        with factory(trust_env=False, follow_redirects=False) as client:
            cap = AttemptCap(client, planned)
            for slot in selection:
                provider = catalog[slot]
                report = smoke_live(cap, provider) if mode == "single_smoke" else run_live(cap, provider)
                if mode == "full_quality":
                    report["status"] = (
                        "PASS" if meets_gate(report, minimum_pass_rate=0.85) else "FAIL"
                    )
                # Never include model ID, URL, secret, raw prompt or raw answer.
                result = {
                    "slot": slot,
                    "status": report["status"],
                    "evaluated": 1 if mode == "single_smoke" else report["evaluated"],
                    "passed": (1 if report["status"] == "PASS" else 0)
                              if mode == "single_smoke" else report["passed"],
                    "failed": (0 if report["status"] == "PASS" else 1)
                              if mode == "single_smoke" else report["failed"],
                    "errors": (1 if report.get("result") == "ERROR" else 0)
                              if mode == "single_smoke" else report["errors"],
                    "critical_failures": [] if mode == "single_smoke" else report["critical_failures"],
                    "aborted_early": report.get("aborted_early", False),
                    "abort_reason": report.get("abort_reason") or report.get("error_reason"),
                }
                results.append(result)
                if result["aborted_early"] or result["errors"]:
                    break
    except Exception:
        # An unexpected client or runner exception can include private endpoint
        # information. Discard it entirely, including from logs and artifacts.
        return 1, {
            "status": "ERROR",
            "reason": "comparison_runner_failure",
            "run_mode": mode,
            "provider_requests_attempted": cap.attempted if cap else 0,
            "provider_contact_attempted": bool(cap and cap.attempted),
            "quality_gate": "NOT_RUN",
            "truth_claim": "NOT_PROVEN",
            "authority": "none",
        }

    complete = len(results) == len(selection) and (
        mode == "single_smoke" or all(
            r["evaluated"] == MAX_PROBES and not r["aborted_early"] for r in results
        )
    )
    all_pass = complete and all(r["status"] == "PASS" for r in results)
    compared = mode == "full_quality" and complete
    report = {
        "status": "PASS" if all_pass else "FAIL",
        "scope": "fictional_text_probe_comparison",
        "run_mode": mode,
        "models_requested": list(selection),
        "models_evaluated": len(results),
        "models": results,
        "comparison_complete": complete,
        "comparable": compared,
        # Ranking describes only this 15-probe heuristic, never model truth.
        "heuristic_order": (
            [r["slot"] for r in sorted(results, key=lambda x: (-x["passed"], selection.index(x["slot"])))]
            if compared else []
        ),
        "provider_requests_cap": planned,
        "provider_requests_attempted": cap.attempted,
        "provider_contact_attempted": cap.attempted > 0,
        "live_model_evaluated": compared,
        "quality_gate": "HEURISTIC_ONLY" if compared else "NOT_RUN",
        "billing_limit": "REQUEST_COUNT_ONLY_NOT_A_CURRENCY_CAP",
        "truth_claim": "NOT_PROVEN",
        "authority": "none",
    }
    return (0 if all_pass else 1), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-config", action="store_true",
                      help="Offline check; never opens a model network connection")
    mode.add_argument("--smoke", action="store_true",
                      help="One fixed fictional probe per selected model")
    mode.add_argument("--full", action="store_true",
                      help="15 fixed fictional probes per selected model")
    parser.add_argument("--slots", required=True,
                        help="Strict two or three slots, e.g. primary,secondary")
    parser.add_argument("--max-requests", default="",
                        help="Must equal the exact planned count (2-3 or 30-45)")
    args = parser.parse_args()
    code, report = compare_models(
        mode="check_config" if args.check_config else "single_smoke" if args.smoke else "full_quality",
        slots=args.slots,
        consent=os.getenv("NEXUS_MODEL_COMPARE_CONSENT", ""),
        acknowledgement=os.getenv("NEXUS_MODEL_COMPARE_ACK", ""),
        max_requests=args.max_requests,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
