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


def test_export_preview_parity_with_reviewed_browser_workflow():
    # An export route is a review surface, never a file-delivery assertion.
    en = preview("Draft a report then export document as DOCX")
    assert [s["command"] for s in en["steps"]] == ["/write", "/export"]
    fa = preview("برنامه:\n۱. بنویس گزارش\n۲. خروجی سند به PDF")
    assert [s["tool"] for s in fa["steps"]] == ["write", "export"]
    assert all(s["status"] == "not_started" for s in fa["steps"])
    assert fa["provider_requests"] == fa["tools_executed"] == 0
    direct = preview("/plan\n/write a report\n/export document as markdown")
    assert [s["tool"] for s in direct["steps"]] == ["write", "export"]


@pytest.mark.parametrize("goal", [
    "Write a report and export document",
    "بنویس گزارش و خروجی سند",
    "Research a topic then run python",
    "/plan\n/write a report\n/run python",
    "/plan\n/code run python\n/write a report",
    "/plan\n/write a report\n/export account secrets",
])
def test_export_and_execution_boundaries_fail_closed(goal):
    with pytest.raises(ValueError):
        preview(goal)


def test_export_gateway_response_is_only_review(monkeypatch):
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", TOKEN)
    with TestClient(main.app) as client:
        response = client.post(URL, headers=AUTH, json={
            "consent": True, "goal": "Draft a report then export document as Word"
        })
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert [s["command"] for s in payload["steps"]] == ["/write", "/export"]
        assert payload["execution"] == "not_started"
        assert payload["tools_executed"] == payload["provider_requests"] == 0


def test_orchestra_review_only_preview_in_english_and_persian():
    for goal in (
        "Orchestrate a synthetic score then write a report",
        "/plan\\n/orchestra hypnotic choir piano\\n/write notes",
        "برنامه:\\n۱. ارکستر بساز با پیانو\\n۲. بنویس گزارش",
    ):
        p = preview(goal)
        assert [s["tool"] for s in p["steps"]] == ["orchestra", "write"]
        assert p["tools_executed"] == p["provider_requests"] == 0
        assert all(s["status"] == "not_started" for s in p["steps"])
        assert all(s["requires_separate_user_review"] for s in p["steps"])


@pytest.mark.parametrize("goal", [
    "Orchestrate a score and write a report",
    "/plan\\n/orchestra piano\\n/upload my voice to a server",
    "/plan\\n/orchestra piano\\n/email everyone",
])
def test_orchestra_preview_rejects_compound_or_unauthorized_actions(goal):
    with pytest.raises(ValueError):
        preview(goal)
