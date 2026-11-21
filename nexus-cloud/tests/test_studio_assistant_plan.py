"""Regression contract for the non-executing assistant plan preview."""
from fastapi.testclient import TestClient
import pytest
import main
from studio_assistant_plan import preview

TOKEN = "assistant-plan-test-access-token-123456789"
AUTH = {"authorization": "Bearer " + TOKEN}
URL = "/studio-api/assistant/plan-preview"


def test_english_natural_language_and_persian_ordered_preview():
    p = preview("Research renewable energy then analyze CSV data then draft a report")
    assert [x["tool"] for x in p["steps"]] == ["research", "data", "write"]
    assert [x["number"] for x in p["steps"]] == [1, 2, 3]
    assert all(x["requires_separate_user_review"] for x in p["steps"])
    assert p["execution"] == "not_started" and p["tools_executed"] == 0
    fa = preview("برنامه:\n۱. پژوهش درباره انرژی\n۲. تحلیل داده‌های CSV\n۳. بنویس گزارش")
    assert [x["tool"] for x in fa["steps"]] == ["research", "data", "write"]


def test_slash_commands_and_read_only_account_surfaces():
    p = preview("/plan\n/github pulls\n/render deploys\n/remind review the outcome")
    assert [x["command"] for x in p["steps"]] == ["/github", "/render", "/remind"]


@pytest.mark.parametrize("goal", [
    "Research", "Research a thing and write a summary", "Research a thing\nDelete everything",
    "Open my inbox\nSend email to everyone", "/plan\n/research topic\n/shell rm -rf /",
    "Research a thing\n\nWrite report", "Research a thing\nWrite report\n" + "A" * 270,
    "Research a thing\nWrite \u202e report", "Analyze a CSV and draft a report\nResearch something",
    "Research a thing then ", "Research something\nWrite report\n" * 7,
])
def test_unsafe_or_ambiguous_goals_fail_closed(goal):
    with pytest.raises(ValueError):
        preview(goal)


def test_auth_and_no_network_or_model_calls(monkeypatch):
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    monkeypatch.delenv("NEXUS_MODEL_URL", raising=False)
    with TestClient(main.app) as client:
        async def no_provider(*args, **kwargs):
            pytest.fail("preview must not contact any provider")
        client.app.state.client.request = no_provider
        assert client.post(URL, headers={"authorization": "Bearer wrong"},
                           json={"consent": True, "goal": "Research this\nWrite summary"}).status_code == 401
        r = client.post(URL, headers=AUTH,
                        json={"consent": True, "goal": "Research this\nWrite summary"})
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-store"
        assert r.json()["kind"] == "review_only"
        assert "token" not in r.text.lower()
        assert [step["tool"] for step in r.json()["steps"]] == ["research", "write"]


def test_strict_consent_and_transport_validation(monkeypatch):
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    body = {"consent": True, "goal": "Research this\nWrite summary"}
    with TestClient(main.app) as client:
        for wrong in (False, 1, "true", None):
            assert client.post(URL, headers=AUTH, json={**body, "consent": wrong}).status_code == 422
        assert client.post(URL, headers=AUTH, json={**body, "execute": True}).status_code == 422
        assert client.post(URL, headers=AUTH, content=b"{}").status_code == 415
        assert client.post(URL, headers=AUTH, content=b"x" * 8193).status_code == 415
        assert client.post(URL, headers={**AUTH, "content-type": "application/json"},
                           content=b"x" * 8193).status_code == 413
        assert client.post(URL, headers={**AUTH, "content-type": "application/json"},
                           content=b"not-json").status_code == 422
        assert client.post(URL, headers=AUTH, json={**body, "goal": "Research X\nWrite Y\n/unknown"}).status_code == 422
