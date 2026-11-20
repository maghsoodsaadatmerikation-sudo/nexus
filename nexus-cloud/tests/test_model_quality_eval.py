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
    assert len(quality.PROBES) == 7
    assert len({probe.key for probe in quality.PROBES}) == len(quality.PROBES)
    for probe in quality.PROBES:
        assert quality.passes(probe, probe.good_reply), probe.key
        assert not quality.passes(probe, "Completely unrelated statement."), probe.key


def test_grading_reports_only_aggregate_scores_not_raw_provider_text():
    answers = {probe.key: probe.good_reply for probe in quality.PROBES}
    report = quality.grade(answers, live=True)
    assert report["passed"] == report["total"] == 7
    assert report["failed"] == report["errors"] == 0
    assert report["pass_rate"] == 1
    assert report["truth_claim"] == "NOT_PROVEN"
    assert report["live_model_evaluated"] is True
    raw = json.dumps(report)
    assert "QN-4821" not in raw and "SUNGLASS-119" not in raw
    assert "private-studio-credential" not in raw
    failed = quality.grade({**answers, "supplied_fact": "Wrong answer",
                            "missing_fact": None}, live=True)
    assert failed["passed"] == 5 and failed["failed"] == 1 and failed["errors"] == 1
    assert failed["pass_rate"] == round(5 / 7, 4)


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
    assert len(seen) == 7
    assert report["passed"] == report["total"] == 7
    assert report["errors"] == 0
    assert "provider-secret" not in json.dumps(report)


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
    assert report["errors"] == 7
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
    assert report["passed"] == 7 and report["truth_claim"] == "NOT_PROVEN"


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
