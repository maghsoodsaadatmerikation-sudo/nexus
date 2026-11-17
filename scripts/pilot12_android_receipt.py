#!/usr/bin/env python3
"""Strict, offline-only validator for *self-reported* Android Pilot 12 evidence.

This validator never authenticates physical hardware, network isolation,
CacheStorage or public-source identity on the device. Even a complete receipt
cannot authorize a deployment, close a device acceptance gate, or say PASS.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

SCHEMA = "nexus.pilot12.android-device-self-report.v1"
ORIGIN = "https://nexus-offline-pilot.onrender.com/"
SOURCE_HASH = "7e205bf30f8c2347845fc03a3578676d46f22e83d2897a17fcf1bd34bd058dd1"
STAGES = (
    "online_exact_origin",
    "offline_opt_in_ready",
    "shortcut_created",
    "physical_radio_cut",
    "independent_network_unreachable",
    "reopen_one",
    "fictional_demo",
    "reopen_two",
    "remove_after_network_restore",
    "unrelated_workspace_unchanged",
)
REQUIRED = frozenset({
    "schema", "origin", "app", "browser", "created_at", "stages",
    "self_attested_physical_android", "self_attested_fictional_only",
    "reviewed_public_html_sha256", "device_sha256_measured",
    "independent_hardware_verified", "production_release_authorized",
    "authority", "transmission", "status",
})
BROWSERS = frozenset({"not_specified", "chrome", "firefox", "edge", "other"})
STAGE_VALUES = frozenset({"pass", "fail", "not_tested"})
MAX_BYTES = 16384


class InvalidReceipt(ValueError):
    """Untrusted or incompatible self-report. Never implies release readiness."""


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidReceipt("duplicate-json-field")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise InvalidReceipt("nonfinite-json-constant")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise InvalidReceipt(label)


def validate(data: object) -> dict:
    require(type(data) is dict and frozenset(data) == REQUIRED,
            "invalid-outer-field-set")
    require(data["schema"] == SCHEMA and type(data["schema"]) is str,
            "invalid-schema")
    require(data["origin"] == ORIGIN and type(data["origin"]) is str,
            "invalid-published-origin")
    require(data["app"] == "legacy-public-pilot12", "invalid-app-variant")
    require(type(data["browser"]) is str and data["browser"] in BROWSERS,
            "invalid-browser-category")

    instant = data["created_at"]
    require(type(instant) is str and bool(re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", instant)),
        "invalid-utc-timestamp")
    try:
        timestamp = datetime.fromisoformat(instant.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidReceipt("invalid-calendar-timestamp") from exc
    require(timestamp <= datetime.now(timezone.utc).replace(microsecond=999999),
            "future-dated-receipt")
    require(timestamp.year >= 2026, "invalid-receipt-year")

    stages = data["stages"]
    require(type(stages) is dict and frozenset(stages) == frozenset(STAGES),
            "invalid-stage-set")
    for stage in STAGES:
        require(type(stages[stage]) is str and stages[stage] in STAGE_VALUES,
                "invalid-stage-value")

    for key in ("self_attested_physical_android", "self_attested_fictional_only",
                "device_sha256_measured", "independent_hardware_verified",
                "production_release_authorized"):
        require(type(data[key]) is bool, "invalid-boolean-field")
    require(data["device_sha256_measured"] is False,
            "fabricated-device-hash-proof")
    require(data["independent_hardware_verified"] is False,
            "fabricated-independent-hardware-proof")
    require(data["production_release_authorized"] is False,
            "attempted-release-authority")
    require(data["reviewed_public_html_sha256"] == SOURCE_HASH,
            "invalid-reviewed-public-hash")
    require(data["authority"] == "none" and data["transmission"] == "none",
            "unauthorized-authority-or-network-claim")
    complete = (all(stages[step] == "pass" for step in STAGES)
                and data["self_attested_physical_android"] is True
                and data["self_attested_fictional_only"] is True)
    claimed = "USER_REPORTED_PASS_UNVERIFIED" if complete else "INCOMPLETE_OR_FAILED"
    require(data["status"] == claimed, "forged-or-inconsistent-status")

    # The maximum self-report outcome is PENDING_INDEPENDENT_REVIEW.
    # In particular, this tool NEVER emits independent acceptance PASS.
    return {
        "schema": "nexus.pilot12.android-receipt-validation.v1",
        "receipt_well_formed": True,
        "reported_steps": sum(stages[k] == "pass" for k in STAGES),
        "total_steps": len(STAGES),
        "self_report_complete": complete,
        "reported_status": claimed,
        "review_verdict": "PENDING_INDEPENDENT_REVIEW" if complete
                          else "INCOMPLETE_OR_FAILED",
        "real_android_hardware_independently_verified": False,
        "network_cut_independently_verified": False,
        "device_source_hash_independently_verified": False,
        "release_authorized": False,
        "production_mutation": False,
        "authority": "none",
    }


def parse_document(raw: bytes) -> dict:
    require(len(raw) > 0 and len(raw) <= MAX_BYTES, "invalid-report-size")
    try:
        data = json.loads(raw.decode("utf-8", errors="strict"),
                          object_pairs_hook=unique_pairs,
                          parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidReceipt("invalid-json") from exc
    return validate(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.receipt.read_bytes()
        result = parse_document(raw)
    except (InvalidReceipt, OSError) as error:
        # Do not echo arbitrary receipt contents, filenames or OS path errors.
        label = str(error) if isinstance(error, InvalidReceipt) else "unreadable-receipt"
        print(json.dumps({"schema": "nexus.pilot12.android-receipt-validation.v1",
                          "review_verdict": "INVALID_SELF_REPORT",
                          "reason": label, "release_authorized": False,
                          "authority": "none"}), file=sys.stdout)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
