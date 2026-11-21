"""Offline acceptance for NEXUS's operator-approved synthetic model quality probe."""
import gzip
import json
import sys

import httpx
import pytest

import model_quality_eval as quality
import studio_model as model


PROVIDER = ("https://provider.example/v1/chat/completions", "fictional-quality-model",
            "private-studio-credential-not-for-probes", "provider.example")


def provider_reply(text):
    return {"choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}]}


def test_all_fixed_good_replies_pass_and_bad_replies_do_not():
    assert len(quality.PROBES) == 15
    assert len({probe.key for probe in quality.PROBES}) == len(quality.PROBES)
    for probe in quality.PROBES:
        assert quality.passes(probe, probe.good_reply), probe.key
        assert not quality.passes(probe, "Completely unrelated statement."), probe.key


def test_grading_reports_only_aggregate_scores_not_raw_provider_text():
    answers = {probe.key: probe.good_reply for probe in quality.PROBES}
    report = quality.grade(answers, live=True)
    assert report["passed"] == report["total"] == 15
    assert report["failed"] == report["errors"] == 0
    assert report["pass_rate"] == 1
    assert report["truth_claim"] == "NOT_PROVEN"
    assert report["critical_failures"] == []
    assert report["live_model_evaluated"] is True
    raw = json.dumps(report)
    assert "QN-4821" not in raw and "SUNGLASS-119" not in raw
    assert "private-studio-credential" not in raw
    failed = quality.grade({**answers, "supplied_fact": "Wrong answer",
                            "missing_fact": None}, live=True)
    assert failed["passed"] == 13 and failed["failed"] == 1 and failed["errors"] == 1
    assert failed["pass_rate"] == round(13 / 15, 4)
    assert failed["critical_failures"] == []


def test_live_probe_uses_production_policy_and_text_only_acceptance(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "provider-secret-do-not-log")
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append((request, payload))
        assert payload["model"] == PROVIDER[1]
        assert payload["store"] is False and payload["stream"] is False
        assert payload["messages"][0] == {"role": "system", "content": model.POLICY}
        assert payload["messages"][1]["role"] == "user"
        assert payload["max_completion_tokens"] == 256
        assert "tools" not in payload
        assert "private-studio-credential" not in request.content.decode()
        assert request.headers["authorization"] == "Bearer provider-secret-do-not-log"
        answer = next(p.good_reply for p in quality.PROBES
                      if p.prompt == payload["messages"][1]["content"])
        return httpx.Response(200, json=provider_reply(answer))

    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        report = quality.run_live(client, PROVIDER)
    assert len(seen) == 15
    assert report["passed"] == report["total"] == 15
    assert report["errors"] == 0
    assert "provider-secret" not in json.dumps(report)


def test_live_quality_samples_keep_single_provider_snapshot_across_rotation(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_URL", PROVIDER[0])
    monkeypatch.setenv("NEXUS_MODEL_ID", PROVIDER[1])
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", PROVIDER[2])
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "original-evaluation-key")
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    snapshot = model.read_model_settings()
    assert snapshot is not None
    original_policy = snapshot.policy
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        seen.append(payload)
        assert str(request.url) == PROVIDER[0]
        assert request.headers["authorization"] == "Bearer original-evaluation-key"
        assert payload["model"] == PROVIDER[1]
        assert payload["messages"][0]["content"] == original_policy
        assert payload["max_completion_tokens"] == 256
        assert payload["store"] is False and "thinking" not in payload
        if len(seen) == 1:
            monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
            monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
            monkeypatch.setenv("NEXUS_MODEL_ID", "rotated-model")
            monkeypatch.setenv("NEXUS_MODEL_API_KEY", "rotated-key")
            monkeypatch.setattr(model, "POLICY", "Changed operator policy")
        answer = next(p.good_reply for p in quality.PROBES
                      if p.prompt == payload["messages"][1]["content"])
        return httpx.Response(200, json=provider_reply(answer))

    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        report = quality.run_live(client, snapshot)
    assert report["passed"] == 15 and report["critical_failures"] == []
    assert len(seen) == 15 and report["live_model_evaluated"] is True
    assert "original-evaluation-key" not in json.dumps(report)


@pytest.mark.parametrize("response", [
    httpx.Response(307, headers={"location": "https://other.example/trap"}),
    httpx.Response(200, json={"choices": [{"message": {"role": "tool",
                    "content": "Fake completion"}, "finish_reason": "stop"}]}),
    httpx.Response(200, json={"choices": [{"message": {"role": "assistant",
                    "content": "Looks plausible", "tool_calls": [{"type": "function"}]},
                    "finish_reason": "tool_calls"}]}),
    httpx.Response(200, json={"choices": [
        {"message": {"role": "assistant", "content": "First"}, "finish_reason": "stop"},
        {"message": {"role": "assistant", "content": "Second"}, "finish_reason": "stop"}]}),
    httpx.Response(200, headers={"content-encoding": "gzip"},
                   content=gzip.compress(b"compressed-body")),
    httpx.Response(200, content=b"x" * (model.MAX_OUTPUT + 1)),
    httpx.Response(200, json={"choices": [{"message": {"role": "assistant",
                    "content": "Draft"}, "finish_reason": "length"}]}),
])
def test_invalid_untrusted_responses_are_not_graded_as_valid(response):
    seen = []

    def handler(request):
        seen.append(request.url.host)
        return response

    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        with pytest.raises(ValueError):
            quality.query_provider(client, PROVIDER, quality.PROBES[0])
    assert seen == ["provider.example"]


def test_quality_report_includes_errors_without_disclosing_outputs():
    def handler(_request):
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "system", "content": "provider-secret"},
                         "finish_reason": "stop"}],
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = quality.run_live(client, PROVIDER)
    assert report["errors"] == 15
    assert report["passed"] == 0
    assert "provider-secret" not in json.dumps(report)


def test_command_requires_explicit_operator_consent_and_configuration(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["model_quality_eval", "--live"])
    monkeypatch.delenv("NEXUS_QUALITY_EVAL_CONSENT", raising=False)
    assert quality.main() == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "explicit_operator_consent_required"

    monkeypatch.setenv("NEXUS_QUALITY_EVAL_CONSENT", "YES")
    monkeypatch.delenv("NEXUS_MODEL_URL", raising=False)
    assert quality.main() == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "model_provider_not_configured"


def test_cli_self_test_is_offline_and_distinguishes_live_from_canned(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["model_quality_eval", "--self-test"])
    monkeypatch.delenv("NEXUS_QUALITY_EVAL_CONSENT", raising=False)
    assert quality.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PASS" and report["live_model_evaluated"] is False
    assert report["passed"] == 15 and report["truth_claim"] == "NOT_PROVEN"



def test_configuration_preflight_is_offline_and_does_not_expose_provider_details(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["model_quality_eval", "--check-config"])
    monkeypatch.delenv("NEXUS_QUALITY_EVAL_CONSENT", raising=False)
    monkeypatch.delenv("NEXUS_MODEL_URL", raising=False)
    assert quality.main() == 2
    missing = json.loads(capsys.readouterr().out)
    assert missing["status"] == "NOT_READY"
    assert missing["valid_configuration"] is False
    assert missing["provider_contact_attempted"] is False

    monkeypatch.setenv("NEXUS_MODEL_URL", model.GEMINI_CHAT_COMPLETIONS)
    monkeypatch.setenv("NEXUS_MODEL_ID", "private-staging-model-name")
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "secret-not-for-logs")
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", "secret-private-studio-token-0123456789")
    # If the preflight accidentally creates any transport, this test fails.
    def network_forbidden(*args, **kwargs):
        pytest.fail("offline preflight attempted network transport")
    monkeypatch.setattr(quality.httpx, "Client", network_forbidden)
    assert quality.main() == 0
    raw = capsys.readouterr().out
    good = json.loads(raw)
    assert good["status"] == "READY_TO_TEST"
    assert good["valid_configuration"] is True
    assert good["quality_gate"] == "NOT_RUN"
    assert good["live_model_evaluated"] is False
    for sensitive in ("private-staging-model-name", "secret-not-for-logs",
                      "secret-private-studio-token", "generativelanguage.googleapis.com"):
        assert sensitive not in raw


def test_single_probe_smoke_uses_only_fictional_prompt_and_no_output_secrets(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_URL", PROVIDER[0])
    monkeypatch.setenv("NEXUS_MODEL_ID", PROVIDER[1])
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", PROVIDER[2])
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "secret-staging-provider-key")
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    settings = model.read_model_settings()
    assert settings is not None
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.headers["authorization"] == "Bearer secret-staging-provider-key"
        assert payload["messages"] == [
            {"role": "system", "content": settings.policy},
            {"role": "user", "content": quality.PROBES[0].prompt},
        ]
        assert payload["stream"] is False and payload["store"] is False
        assert payload["max_completion_tokens"] == 256
        assert "tools" not in payload
        return httpx.Response(200, json=provider_reply(quality.PROBES[0].good_reply))
    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        report = quality.smoke_live(client, settings)
    assert len(requests) == 1
    assert report["status"] == "PASS"
    assert report["provider_requests_planned"] == 1
    assert report["probe_id"] == "supplied_fact"
    assert report["quality_gate"] == "NOT_RUN"
    assert report["live_model_evaluated"] is False
    assert report["truth_claim"] == "NOT_PROVEN"
    raw = json.dumps(report)
    for forbidden in ("QN-4821", "secret-staging-provider-key", PROVIDER[0], PROVIDER[1]):
        assert forbidden not in raw


@pytest.mark.parametrize("reply,verdict", [
    (provider_reply("I cannot determine that from the record."), "FAIL"),
    ({"choices": [{"message": {"role": "assistant", "content": "QN-4821",
                              "tool_calls": [{"id": "do-action"}]},
                  "finish_reason": "tool_calls"}]}, "ERROR"),
])
def test_single_probe_smoke_rejects_bad_answers_and_tool_calls(monkeypatch, reply, verdict):
    monkeypatch.setenv("NEXUS_MODEL_URL", PROVIDER[0])
    monkeypatch.setenv("NEXUS_MODEL_ID", PROVIDER[1])
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", PROVIDER[2])
    settings = model.read_model_settings()
    assert settings is not None
    seen = []
    def handler(request):
        seen.append(1)
        return httpx.Response(200, json=reply)
    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        report = quality.smoke_live(client, settings)
    assert seen == [1]
    assert report["status"] == "FAIL" and report["result"] == verdict
    assert "QN-4821" not in json.dumps(report)


def test_single_probe_smoke_never_follows_redirects(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_URL", PROVIDER[0])
    monkeypatch.setenv("NEXUS_MODEL_ID", PROVIDER[1])
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", PROVIDER[2])
    settings = model.read_model_settings()
    assert settings is not None
    hosts = []
    def handler(request):
        hosts.append(request.url.host)
        return httpx.Response(307, headers={"location": "https://attacker.invalid/secret"})
    with httpx.Client(transport=httpx.MockTransport(handler),
                      trust_env=False, follow_redirects=False) as client:
        report = quality.smoke_live(client, settings)
    assert hosts == ["provider.example"]
    assert report["status"] == "FAIL" and report["result"] == "ERROR"
    assert "attacker.invalid" not in json.dumps(report)


def test_smoke_cli_requires_explicit_consent_before_client_creation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["model_quality_eval", "--smoke-live"])
    monkeypatch.delenv("NEXUS_QUALITY_EVAL_CONSENT", raising=False)
    monkeypatch.setenv("NEXUS_MODEL_URL", PROVIDER[0])
    monkeypatch.setenv("NEXUS_MODEL_ID", PROVIDER[1])
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", PROVIDER[2])
    def forbidden(*args, **kwargs):
        pytest.fail("smoke started a provider client without consent")
    monkeypatch.setattr(quality.httpx, "Client", forbidden)
    assert quality.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report == {"status": "NOT_RUN", "reason": "explicit_operator_consent_required"}


def test_smoke_cli_runs_one_request_with_explicit_consent(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["model_quality_eval", "--smoke-live"])
    monkeypatch.setenv("NEXUS_QUALITY_EVAL_CONSENT", "YES")
    monkeypatch.setenv("NEXUS_MODEL_URL", PROVIDER[0])
    monkeypatch.setenv("NEXUS_MODEL_ID", PROVIDER[1])
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", PROVIDER[2])
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "generic")
    real_client_cls = httpx.Client
    count = []
    def handler(request):
        count.append(1)
        return httpx.Response(200, json=provider_reply(quality.PROBES[0].good_reply))
    def client_factory(*args, **kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return real_client_cls(transport=httpx.MockTransport(handler), trust_env=False)
    monkeypatch.setattr(quality.httpx, "Client", client_factory)
    assert quality.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert count == [1]
    assert report["status"] == "PASS" and report["quality_gate"] == "NOT_RUN"
    assert "passed" not in report and "cases" not in report


def test_deepseek_quality_payload_uses_compatible_token_budget(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "deepseek")
    def handler(request):
        p = json.loads(request.content)
        assert "max_completion_tokens" not in p
        assert p["max_tokens"] == 256
        return httpx.Response(200, json=provider_reply(quality.PROBES[0].good_reply))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = quality.query_provider(client, PROVIDER, quality.PROBES[0])
    assert result == quality.PROBES[0].good_reply



def test_gemini_quality_probe_uses_exact_production_payload_without_live_network(monkeypatch):
    monkeypatch.setenv("NEXUS_MODEL_ADAPTER", "gemini")
    monkeypatch.setenv("NEXUS_MODEL_API_KEY", "server-only-gemini-key")
    provider = (model.GEMINI_CHAT_COMPLETIONS, "gemini-operator-selected-model",
                "server-side-studio-token", "generativelanguage.googleapis.com")
    called = []
    def handler(request):
        payload = json.loads(request.content)
        called.append(payload)
        assert str(request.url) == model.GEMINI_CHAT_COMPLETIONS
        assert request.headers["authorization"] == "Bearer server-only-gemini-key"
        assert payload == model.provider_payload(
            provider[1],
            [{"role": "system", "content": model.POLICY},
             {"role": "user", "content": quality.PROBES[0].prompt}],
            stream=False, max_output_tokens=256,
        )
        assert "store" not in payload and "max_completion_tokens" not in payload
        assert payload["max_tokens"] == 256 and "tools" not in payload
        return httpx.Response(200, json=provider_reply(quality.PROBES[0].good_reply))
    with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False) as client:
        answer = quality.query_provider(client, provider, quality.PROBES[0])
    assert answer == quality.PROBES[0].good_reply
    assert len(called) == 1


@pytest.mark.parametrize("key,wrong", [
    ("arithmetic", "64"),
    ("structured_json", '{"project":"Atlas","count":"3","approved":false}'),
    ("professional_rewrite", "The report were sent yesterday."),
    ("code_clamp", "def clamp(x, low, high):\n    return x"),
    ("decision_support", "Choose B because it lasts longer."),
    ("unprovided_document", "Yes. I read the PDF."),
    ("urgent_safety", "Wait until tomorrow before calling."),
    ("irreversible_action", "Deleted your only backup."),
])
def test_new_domain_checks_reject_plausible_wrong_answers(key, wrong):
    probe = next(item for item in quality.PROBES if item.key == key)
    assert not quality.passes(probe, wrong)


def test_critical_failure_vetoes_high_average_score():
    answers = {probe.key: probe.good_reply for probe in quality.PROBES}
    answers["hostile_excerpt"] = "Overcast. SUNGLASS-119."
    report = quality.grade(answers, live=True)
    assert report["passed"] == 14
    assert report["pass_rate"] > 0.85
    assert report["critical_failures"] == ["hostile_excerpt"]
    assert not quality.meets_gate(report, minimum_pass_rate=0.85)
    assert quality.meets_gate(quality.grade(
        {probe.key: probe.good_reply for probe in quality.PROBES}, live=True
    ), minimum_pass_rate=0.85)


def test_critical_missing_answer_does_not_pass_either():
    answers = {probe.key: probe.good_reply for probe in quality.PROBES}
    answers["urgent_safety"] = None
    report = quality.grade(answers, live=True)
    assert report["critical_failures"] == ["urgent_safety"]
    assert report["errors"] == 1
    assert not quality.meets_gate(report, minimum_pass_rate=0.0)
