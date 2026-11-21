"""Manual, bounded Gemini staging through GitHub Actions.

Runs only when an operator selects an explicit mode. Never reads real user
conversations; only fixed fictional quality probes can leave the runner.
The provider API key is supplied as a protected environment secret, never as
a workflow input, GitHub artifact or log value.
"""
from __future__ import annotations

import json
import os
import re
from secrets import token_urlsafe
from unittest.mock import patch

import httpx

from model_quality_eval import PROBES, meets_gate, run_live, smoke_live
from studio_model import GEMINI_CHAT_COMPLETIONS, read_model_settings


ACKNOWLEDGEMENTS = {
    "single_smoke": "I_APPROVE_1_PROVIDER_REQUEST",
    "full_quality": "I_APPROVE_15_PROVIDER_REQUESTS",
}
MODES = frozenset({"check_config", *ACKNOWLEDGEMENTS})
MODEL_ID_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,149}\Z", re.ASCII)


def declined(reason: str) -> tuple[int, dict]:
    return 2, {
        "status": "NOT_RUN",
        "reason": reason,
        "provider_contact_attempted": False,
        "quality_gate": "NOT_RUN",
        "authority": "none",
    }


def evaluate(
    *,
    mode: str,
    model_id: str,
    acknowledgement: str,
    provider_key: str,
    git_ref: str,
    client_factory=None,
) -> tuple[int, dict]:
    """Never contact a provider before branch, mode and charge consent checks.

    Caller-injected client_factory is for deterministic tests. Real workflow
    uses httpx.Client with trust_env=False, no redirects and no retries.
    """
    if git_ref != "refs/heads/main":
        return declined("main_branch_required")
    if mode not in MODES:
        return declined("unsupported_mode")
    if mode != "check_config" and acknowledgement != ACKNOWLEDGEMENTS[mode]:
        return declined("explicit_billing_acknowledgement_required")
    if not MODEL_ID_PATTERN.fullmatch(model_id):
        return declined("invalid_model_id")
    if not provider_key.strip():
        return declined("provider_secret_missing")

    # Only the exact Gemini compatibility URL is used. Never accept an
    # operator-supplied endpoint or an untrusted provider host in this workflow.
    # Mint a separate ephemeral Studio credential per runner execution.
    server_settings = {
        "NEXUS_MODEL_URL": GEMINI_CHAT_COMPLETIONS,
        "NEXUS_MODEL_ID": model_id,
        "NEXUS_MODEL_ADAPTER": "gemini",
        "NEXUS_MODEL_API_KEY": provider_key.strip(),
        "NEXUS_STUDIO_TOKEN": token_urlsafe(48),
        "NEXUS_MODEL_STREAMING": "0",
    }
    with patch.dict(os.environ, server_settings):
        provider = read_model_settings()
    if provider is None:
        return declined("model_configuration_invalid")

    if mode == "check_config":
        return 0, {
            "status": "READY_TO_TEST",
            "scope": "offline_gemini_configuration_only",
            "provider_contact_attempted": False,
            "quality_gate": "NOT_RUN",
            "live_model_evaluated": False,
            "truth_claim": "NOT_PROVEN",
            "authority": "none",
        }

    # The only network-capable path is below this point; all upstream data is
    # fictional and fixed in source, not conversation or repository content.
    factory = httpx.Client if client_factory is None else client_factory
    try:
        with factory(trust_env=False, follow_redirects=False) as client:
            report = (smoke_live(client, provider) if mode == "single_smoke"
                      else run_live(client, provider))
        if mode == "full_quality":
            report["status"] = ("PASS" if meets_gate(report, minimum_pass_rate=0.85)
                                else "FAIL")
            report["quality_gate"] = "HEURISTIC_ONLY"
        report["run_mode"] = mode
        report["provider_requests_maximum"] = 1 if mode == "single_smoke" else len(PROBES)
        return (0 if report["status"] == "PASS" else 1), report
    except Exception:
        # Avoid provider URLs, Python request data and secrets in runner logs.
        return 1, {
            "status": "ERROR",
            "reason": "runner_or_provider_failure",
            "run_mode": mode,
            "provider_contact_attempted": True,
            "quality_gate": "NOT_RUN",
            "authority": "none",
        }


def main() -> int:
    code, report = evaluate(
        mode=os.getenv("NEXUS_STAGE_MODE", ""),
        model_id=os.getenv("NEXUS_STAGE_MODEL_ID", ""),
        acknowledgement=os.getenv("NEXUS_STAGE_BILLING_ACK", ""),
        provider_key=os.getenv("NEXUS_STAGE_GEMINI_API_KEY", ""),
        git_ref=os.getenv("GITHUB_REF", ""),
    )
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
