"""Frozen, offline tests for opt-in comparison of multiple Studio providers."""
import json

import httpx
import pytest

import model_quality_compare as comparison
import model_quality_eval as quality
import studio_model as model


TOKEN = "private-comparison-studio-token-01234567890123456789"
PRIMARY_SECRET = "primary-private-key-do-not-log"
SECONDARY_SECRET = "secondary-private-key-do-not-log"


@pytest.fixture
def two_models(monkeypatch):
    for slot in ("SECONDARY", "TERTIARY"):
        for name in model._SLOT_FIELDS:
            monkeypatch.delenv(f"NEXUS_MODEL_{slot}_{name}", raising=False)
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://primary.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "private-first-id")
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", PRIMARY_SECRET)
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.delenv("NEXUS_MODEL_STREAMING", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_WORKSPACE_ID", raising=False)
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_URL", model.ANTHROPIC_MESSAGES)
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ID", "private-second-id")
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ADAPTER", "anthropic")
    monkeypatch.setenv("NEXUS_MODEL_SECONDARY_API_KEY", SECONDARY_SECRET)
    return monkeypatch


def reply_for(request, *, wrong_on_primary=False):
    raw = json.loads(request.content)
    is_anthropic = str(request.url) == model.ANTHROPIC_MESSAGES
    if is_anthropic:
        assert request.headers["x-api-key"] == SECONDARY_SECRET
        assert request.headers["anthropic-version"] == model.ANTHROPIC_API_VERSION
        assert "authorization" not in request.headers
        assert raw["model"] == "private-second-id"
        user_prompt = raw["messages"][-1]["content"]
    else:
        assert str(request.url) == "https://primary.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + PRIMARY_SECRET
        assert "x-api-key" not in request.headers
        assert raw["model"] == "private-first-id"
        user_prompt = raw["messages"][-1]["content"]
    fixed = next(p for p in quality.PROBES if p.prompt == user_prompt)
    answer = fixed.good_reply
    if wrong_on_primary and not is_anthropic and fixed.key == "supplied_fact":
        answer = "No usable calibration code is available"
    if is_anthropic:
        return httpx.Response(200, json={
            "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": answer}],
            "stop_reason": "end_turn",
        })
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
    })


def make_factory(handler, calls):
    def factory(**kwargs):
        assert kwargs == {"trust_env": False, "follow_redirects": False}
        def wrapped(request):
            calls.append(request)
            return handler(request)
        return httpx.Client(transport=httpx.MockTransport(wrapped),
                            trust_env=False, follow_redirects=False)
    return factory


@pytest.mark.parametrize("value", [
    "", "primary", "primary,primary", "primary,unknown", "primary,secondary,primary",
    "primary,secondary,tertiary,extra", "https://attacker.example,secondary",
    "primary, secondary", "PRIMARY,secondary", "primary,,secondary",
])
def test_invalid_model_selection_never_creates_provider_client(two_models, value):
    def forbidden(**_):
        pytest.fail("bad model selection created a transport")
    code, out = comparison.compare_models(
        mode="full_quality", slots=value, consent="YES", acknowledgement="I_APPROVE_30_PROVIDER_REQUESTS",
        max_requests="30", client_factory=forbidden,
    )
    assert code == 2 and out["status"] == "NOT_RUN"
    assert out["provider_contact_attempted"] is False


def test_offline_preflight_is_redacted_and_no_network_client(two_models):
    def forbidden(**_):
        pytest.fail("offline preflight used network")
    code, out = comparison.compare_models(
        mode="check_config", slots="primary,secondary", client_factory=forbidden
    )
    assert code == 0 and out == {
        "status": "READY_TO_TEST", "scope": "offline_config_only",
        "models": [{"slot": "primary", "configured": True},
                   {"slot": "secondary", "configured": True}],
        "provider_requests_planned_for_full_quality": 30,
        "provider_contact_attempted": False, "live_model_evaluated": False,
        "quality_gate": "NOT_RUN", "truth_claim": "NOT_PROVEN", "authority": "none",
    }
    raw = json.dumps(out)
    for forbidden_text in (PRIMARY_SECRET, SECONDARY_SECRET, TOKEN, "api.anthropic.com",
                           "private-first-id", "primary.example"):
        assert forbidden_text not in raw


def test_offline_preflight_reports_incomplete_catalog_without_upstream(two_models):
    two_models.setenv("NEXUS_MODEL_SECONDARY_API_KEY", "")
    code, out = comparison.compare_models(mode="check_config", slots="primary,secondary")
    assert code == 0 and out["status"] == "NOT_READY"
    assert out["models"][1] == {"slot": "secondary", "configured": False}
    assert out["provider_contact_attempted"] is False


@pytest.mark.parametrize("consent,ack,cap,reason", [
    ("", "I_APPROVE_2_PROVIDER_REQUESTS", "2", "explicit_comparison_consent_required"),
    ("YES", "", "2", "exact_request_count_acknowledgement_required"),
    ("YES", "I_APPROVE_30_PROVIDER_REQUESTS", "2", "exact_request_count_acknowledgement_required"),
    ("YES", "I_APPROVE_2_PROVIDER_REQUESTS", "", "exact_global_attempt_cap_required"),
    ("YES", "I_APPROVE_2_PROVIDER_REQUESTS", "30", "exact_global_attempt_cap_required"),
    ("YES", "I_APPROVE_2_PROVIDER_REQUESTS", "02", "exact_global_attempt_cap_required"),
    ("YES", "I_APPROVE_2_PROVIDER_REQUESTS", "2.0", "exact_global_attempt_cap_required"),
    ("YES", "I_APPROVE_2_PROVIDER_REQUESTS", "-1", "exact_global_attempt_cap_required"),
])
def test_no_live_network_before_exact_consent_and_request_ceiling(two_models, consent, ack, cap, reason):
    def forbidden(**_):
        pytest.fail("unapproved comparison created network transport")
    code, out = comparison.compare_models(
        mode="single_smoke", slots="primary,secondary", consent=consent,
        acknowledgement=ack, max_requests=cap, client_factory=forbidden,
    )
    assert code == 2 and out["reason"] == reason
    assert out["provider_contact_attempted"] is False


def test_two_provider_smoke_contacts_each_once_but_does_not_rank(two_models):
    calls = []
    code, out = comparison.compare_models(
        mode="single_smoke", slots="primary,secondary", consent="YES",
        acknowledgement="I_APPROVE_2_PROVIDER_REQUESTS", max_requests="2",
        client_factory=make_factory(reply_for, calls),
    )
    assert code == 0 and out["status"] == "PASS"
    assert out["provider_requests_cap"] == out["provider_requests_attempted"] == 2
    assert out["comparison_complete"] is True and out["comparable"] is False
    assert out["heuristic_order"] == [] and out["quality_gate"] == "NOT_RUN"
    assert out["live_model_evaluated"] is False
    assert out["billing_limit"] == "REQUEST_COUNT_ONLY_NOT_A_CURRENCY_CAP"
    assert len(calls) == 2
    for text in [PRIMARY_SECRET, SECONDARY_SECRET, TOKEN, "QN-4821", "private-second-id"]:
        assert text not in json.dumps(out)


def test_full_comparison_bounded_to_30_exact_fixed_probes(two_models):
    calls = []
    code, out = comparison.compare_models(
        mode="full_quality", slots="primary,secondary", consent="YES",
        acknowledgement="I_APPROVE_30_PROVIDER_REQUESTS", max_requests="30",
        client_factory=make_factory(reply_for, calls),
    )
    assert code == 0 and out["status"] == "PASS"
    assert out["comparison_complete"] and out["comparable"]
    assert out["heuristic_order"] == ["primary", "secondary"]
    assert out["provider_requests_cap"] == out["provider_requests_attempted"] == 30
    assert out["quality_gate"] == "HEURISTIC_ONLY" and out["truth_claim"] == "NOT_PROVEN"
    assert [item["passed"] for item in out["models"]] == [15, 15]
    assert len(calls) == 30
    assert not any("query" in str(req.url) for req in calls)


def test_full_comparison_ranks_only_heuristic_answers_and_never_claims_truth(two_models):
    calls = []
    code, out = comparison.compare_models(
        mode="full_quality", slots="primary,secondary", consent="YES",
        acknowledgement="I_APPROVE_30_PROVIDER_REQUESTS", max_requests="30",
        client_factory=make_factory(
            lambda req: reply_for(req, wrong_on_primary=True), calls
        ),
    )
    assert code == 1 and out["status"] == "FAIL"
    assert out["comparison_complete"] and out["comparable"]
    assert out["heuristic_order"] == ["secondary", "primary"]
    assert [x["passed"] for x in out["models"]] == [14, 15]
    assert out["quality_gate"] == "HEURISTIC_ONLY"
    assert out["truth_claim"] == "NOT_PROVEN"
    assert len(calls) == 30


@pytest.mark.parametrize("status", [401, 429, 503])
def test_upstream_rejection_aborts_remaining_routes_without_leaks(two_models, status):
    calls = []
    def bad_provider(request):
        return httpx.Response(status, content=b'{"private":"should not leak"}',
                              headers={"x-private": "secret-provider-diagnostics"})
    code, out = comparison.compare_models(
        mode="full_quality", slots="primary,secondary", consent="YES",
        acknowledgement="I_APPROVE_30_PROVIDER_REQUESTS", max_requests="30",
        client_factory=make_factory(bad_provider, calls),
    )
    assert code == 1 and out["status"] == "FAIL"
    assert out["models_evaluated"] == 1 and out["comparison_complete"] is False
    assert out["provider_requests_attempted"] == 1
    assert out["comparable"] is False and out["heuristic_order"] == []
    assert len(calls) == 1
    assert "should not leak" not in json.dumps(out)
    assert "secret-provider-diagnostics" not in json.dumps(out)


def test_missing_selected_model_denies_all_external_calls(two_models):
    two_models.setenv("NEXUS_MODEL_SECONDARY_URL", "https://unsafe.example/messages")
    def forbidden(**_):
        pytest.fail("invalid provider config created transport")
    code, out = comparison.compare_models(
        mode="single_smoke", slots="primary,secondary", consent="YES",
        acknowledgement="I_APPROVE_2_PROVIDER_REQUESTS", max_requests="2",
        client_factory=forbidden,
    )
    assert code == 2 and out["reason"] == "selected_model_unconfigured"


def test_global_attempt_cap_blocks_second_request_before_transport():
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: (
            calls.append(request), httpx.Response(200, json={})
        )[1]), trust_env=False,
    ) as client:
        guard = comparison.AttemptCap(client, 1)
        with guard.stream("GET", "https://synthetic.example") as response:
            assert response.status_code == 200
        with pytest.raises(ValueError, match="attempt ceiling reached"):
            guard.stream("GET", "https://synthetic.example")
        assert guard.attempted == 1 and len(calls) == 1


def test_three_model_preflight_and_ack_are_exact(two_models):
    two_models.setenv("NEXUS_MODEL_TERTIARY_URL", model.GEMINI_CHAT_COMPLETIONS)
    two_models.setenv("NEXUS_MODEL_TERTIARY_ID", "third-private-id")
    two_models.setenv("NEXUS_MODEL_TERTIARY_API_KEY", "third-private-key")
    two_models.setenv("NEXUS_MODEL_TERTIARY_ADAPTER", "gemini")
    code, out = comparison.compare_models(mode="check_config", slots="primary,secondary,tertiary")
    assert code == 0 and out["provider_requests_planned_for_full_quality"] == 45
    assert [m["configured"] for m in out["models"]] == [True, True, True]
    cap, refused = comparison.compare_models(
        mode="full_quality", slots="primary,secondary,tertiary",
        consent="YES", acknowledgement="I_APPROVE_45_PROVIDER_REQUESTS",
        max_requests="30",
        client_factory=lambda **_: pytest.fail("wrong 45-request ceiling opened transport"),
    )
    assert cap == 2 and refused["reason"] == "exact_global_attempt_cap_required"


def test_runner_exception_does_not_print_provider_secrets(two_models):
    def failing(**_):
        raise RuntimeError("upstream-secret-value leaked in raw transport error")
    code, out = comparison.compare_models(
        mode="single_smoke", slots="primary,secondary", consent="YES",
        acknowledgement="I_APPROVE_2_PROVIDER_REQUESTS", max_requests="2",
        client_factory=failing,
    )
    assert code == 1 and out["reason"] == "comparison_runner_failure"
    assert "upstream-secret-value" not in json.dumps(out)
    assert out["provider_contact_attempted"] is False
