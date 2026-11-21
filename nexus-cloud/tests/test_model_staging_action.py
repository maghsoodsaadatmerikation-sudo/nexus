"""No-network regression tests for the opt-in mobile-friendly staging runner."""
from pathlib import Path
import json

import httpx
import pytest

import model_staging_action as action
import model_quality_eval as quality
from studio_model import GEMINI_CHAT_COMPLETIONS


KEY = "fictional-secret-not-for-reports-12345"
MODEL = "gemini-operator-reviewed"
BASE = {
    "model_id": MODEL,
    "provider_key": KEY,
    "git_ref": "refs/heads/main",
}


def complete(answer):
    return {"choices": [{"message": {"role": "assistant", "content": answer},
                         "finish_reason": "stop"}]}


@pytest.mark.parametrize("overrides,reason", [
    ({"git_ref": "refs/heads/feature/attempt"}, "main_branch_required"),
    ({"git_ref": "refs/tags/v1"}, "main_branch_required"),
    ({"mode": "all_models"}, "unsupported_mode"),
    ({"mode": "single_smoke", "acknowledgement": ""}, "explicit_billing_acknowledgement_required"),
    ({"mode": "full_quality", "acknowledgement": "I_APPROVE_1_PROVIDER_REQUEST"},
     "explicit_billing_acknowledgement_required"),
    ({"mode": "single_smoke", "acknowledgement": "I_APPROVE_15_PROVIDER_REQUESTS"},
     "explicit_billing_acknowledgement_required"),
    ({"mode": "full_quality", "acknowledgement": "I_APPROVE_15_PROVIDER_REQUESTS "},
     "explicit_billing_acknowledgement_required"),
    ({"model_id": "not a model"}, "invalid_model_id"),
    ({"model_id": "$(cat secrets)"}, "invalid_model_id"),
    ({"model_id": "model\necho SECRET"}, "invalid_model_id"),
    ({"model_id": "A" * 151}, "invalid_model_id"),
    ({"provider_key": ""}, "provider_secret_missing"),
    ({"provider_key": "bad" + chr(10) + "key"}, "provider_secret_invalid"),
    ({"provider_key": "invalid key"}, "provider_secret_invalid"),
    ({"provider_key": "A" * 513}, "provider_secret_invalid"),
])
def test_guard_never_creates_provider_client(overrides, reason):
    args = {**BASE, "mode": "single_smoke",
            "acknowledgement": "I_APPROVE_1_PROVIDER_REQUEST"}
    args.update(overrides)
    def forbid(**_):
        pytest.fail("external client created before manual approval")
    code, result = action.evaluate(**args, client_factory=forbid)
    assert code == 2 and result["reason"] == reason
    assert result["provider_contact_attempted"] is False
    assert KEY not in json.dumps(result) and MODEL not in json.dumps(result)


def test_offline_mode_uses_fixed_endpoint_no_secrets_or_httpx():
    def forbid(**_):
        pytest.fail("offline config check created a network client")
    code, report = action.evaluate(mode="check_config", acknowledgement="", **BASE,
                                   client_factory=forbid)
    assert code == 0
    assert report["status"] == "READY_TO_TEST"
    assert report["provider_contact_attempted"] is False
    assert report["live_model_evaluated"] is False
    assert report["quality_gate"] == "NOT_RUN"
    assert KEY not in json.dumps(report) and MODEL not in json.dumps(report)


def test_single_smoke_is_exactly_one_fictional_gemini_request_without_tools():
    seen = []
    def handle(request):
        payload = json.loads(request.content)
        seen.append(request)
        assert str(request.url) == GEMINI_CHAT_COMPLETIONS
        assert request.headers["authorization"] == "Bearer " + KEY
        assert payload["model"] == MODEL
        assert payload["messages"][1:] == [
            {"role": "user", "content": quality.PROBES[0].prompt}]
        assert payload["stream"] is False
        assert payload["max_tokens"] == 256
        assert "store" not in payload and "tools" not in payload
        return httpx.Response(200, json=complete(quality.PROBES[0].good_reply))
    def factory(**kwargs):
        assert kwargs == {"trust_env": False, "follow_redirects": False}
        return httpx.Client(transport=httpx.MockTransport(handle), **kwargs)
    code, result = action.evaluate(**BASE, mode="single_smoke",
        acknowledgement="I_APPROVE_1_PROVIDER_REQUEST", client_factory=factory)
    assert code == 0 and len(seen) == 1
    assert result["status"] == "PASS"
    assert result["provider_requests_maximum"] == 1
    assert result["quality_gate"] == "NOT_RUN"
    assert result["live_model_evaluated"] is False
    assert KEY not in json.dumps(result)
    assert MODEL not in json.dumps(result)
    assert quality.PROBES[0].good_reply not in json.dumps(result)


def test_full_quality_requires_separate_15_request_consent_and_scores_all():
    attempts = []
    def handler(request):
        data = json.loads(request.content)
        assert data["model"] == MODEL
        attempts.append(data["messages"][1]["content"])
        reply = next(p.good_reply for p in quality.PROBES
                     if p.prompt == data["messages"][1]["content"])
        return httpx.Response(200, json=complete(reply))
    def factory(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(handler), **kwargs)
    code, result = action.evaluate(**BASE, mode="full_quality",
        acknowledgement="I_APPROVE_15_PROVIDER_REQUESTS", client_factory=factory)
    assert code == 0
    assert result["status"] == "PASS"
    assert result["provider_requests_maximum"] == 15
    assert result["provider_requests_attempted"] == 15
    assert result["quality_gate"] == "HEURISTIC_ONLY"
    assert result["truth_claim"] == "NOT_PROVEN"
    assert len(attempts) == len(quality.PROBES) == 15
    raw = json.dumps(result)
    assert KEY not in raw and MODEL not in raw
    assert all(p.good_reply not in raw for p in quality.PROBES)


def test_auth_or_quota_failure_cannot_start_following_probes_and_logs_are_redacted():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, content=b'raw upstream secret :' + KEY.encode())
    def factory(**kwargs):
        return httpx.Client(transport=httpx.MockTransport(handler), **kwargs)
    code, result = action.evaluate(**BASE, mode="full_quality",
        acknowledgement="I_APPROVE_15_PROVIDER_REQUESTS", client_factory=factory)
    assert code == 1 and len(calls) == 1
    assert result["provider_requests_attempted"] == 1
    assert result["provider_requests_skipped"] == 14
    assert result["abort_reason"] == "rate_limited"
    assert result["status"] == "FAIL"
    assert KEY not in json.dumps(result)


def test_unexpected_httpx_factory_error_does_not_print_secret_or_throw():
    def factory(**kwargs):
        raise RuntimeError("Sensitive upstream error: " + KEY)
    code, result = action.evaluate(**BASE, mode="single_smoke",
        acknowledgement="I_APPROVE_1_PROVIDER_REQUEST", client_factory=factory)
    assert code == 1 and result["status"] == "ERROR"
    assert "Sensitive upstream error" not in json.dumps(result)
    assert KEY not in json.dumps(result)


def test_manual_workflow_is_not_event_triggered_and_holds_secrets_in_environment():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/manual-gemini-staging.yml"
    source = path.read_text()
    assert "\non:\n  workflow_dispatch:" in source
    assert "\n  push:" not in source and "\n  pull_request:" not in source
    assert "\n  schedule:" not in source and "\n  workflow_run:" not in source
    assert "environment: nexus-model-staging" in source
    assert "needs: source-guard" in source
    assert 'refs/heads/main' in source
    assert "persist-credentials: false" in source
    assert "permissions:\n  contents: read" in source
    assert "cancel-in-progress: false" in source
    assert "secrets.NEXUS_STAGE_GEMINI_API_KEY" in source
    assert "inputs.billing_ack" in source
    assert "uv run --frozen python -m model_staging_action" in source
    assert "actions/upload-artifact" not in source
    assert "echo ${{ secrets." not in source
    assert "NEXUS_STAGE_GEMINI_API_KEY: ${{ inputs." not in source
