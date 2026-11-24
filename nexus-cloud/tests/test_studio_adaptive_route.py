import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import studio_model as model
from studio_adaptive_route import RouteRequest, RouteProgress, route, progress, register
from test_studio_multi_model import configured, AUTH, set_secondary


def request(**updates):
    return RouteRequest.model_validate({
        "task": "document_answer", "goal": "Review a document", "document_count": 1,
        **updates})


def test_local_and_studio_privacy_boundaries():
    local = route(request(privacy="device_only"), {})
    assert local["blockers"] == ["device_execution_not_assessed"]
    assert all(h["boundary"] == "human" for h in local["handoffs"])
    studio = route(request(quality="comparative"), {})
    assert studio["blockers"] == ["external_provider_disclosure_not_allowed"]
    assert all(h["boundary"] != "provider" for h in studio["handoffs"])
    normal = route(request(), {})
    assert normal["status"] == "review_only" and not normal["execution_authorized"]
    assert [h["step_id"] for h in normal["handoffs"]] == ["extract", "retrieve", "evidence", "final_review"]


def test_comparative_route_and_stale_progress(monkeypatch):
    def handler(_):
        pytest.fail("Adaptive planning must not call provider")
    with configured(monkeypatch, handler) as client:
        p = request(privacy="provider_allowed", quality="comparative", preferred_slot="secondary")
        out = route(p, model.read_model_catalog())
        assert out["blockers"] == ["insufficient_configured_model_slots"]
        set_secondary(monkeypatch)
        out = route(p, model.read_model_catalog())
        assert not out["blockers"]
        assert [h["model_slot"] for h in out["handoffs"] if h["boundary"] == "provider"] == [
            "secondary", "secondary", "primary"]
        data = RouteProgress(request=p, route_sha256=out["route_sha256"])
        next_steps = progress(data, model.read_model_catalog())
        assert [h["step_id"] for h in next_steps["next_review_handoffs"]] == ["extract"]
        data = data.model_copy(update={"acknowledged": ["extract"]})
        assert progress(data, model.read_model_catalog())["next_review_handoffs"][0]["step_id"] == "retrieve"
        with pytest.raises(ValueError):
            progress(data.model_copy(update={"acknowledged": ["retrieve"]}), model.read_model_catalog())
        assert not progress(data.model_copy(update={"cancelled": True}), model.read_model_catalog())["next_review_handoffs"]
        monkeypatch.setenv("NEXUS_MODEL_SECONDARY_ID", "changed")
        with pytest.raises(ValueError):
            progress(data, model.read_model_catalog())
        assert client.app.state.model_budget.snapshot()["attempted"] == 0


@pytest.mark.parametrize("task", ["document_privacy", "manuscript_review", "research_synthesis", "paired_statistics", "general_chat"])
def test_other_task_routes(task):
    p = request(task=task, document_count=1 if task == "document_privacy" else 0)
    out = route(p, {})
    assert out["workflow"]["review_order"][-1] == "final_review"
    assert not out["automatic_dispatch"]


def test_endpoint_handoffs_exist_and_auth(monkeypatch):
    with configured(monkeypatch, lambda _: pytest.fail("Unexpected provider call")) as client:
        set_secondary(monkeypatch)
        paths = {r.path for r in client.app.routes}
        for p in (request(privacy="provider_allowed", quality="comparative"),
                  request(task="document_privacy"), request(task="research_synthesis", document_count=0),
                  request(task="manuscript_review", document_count=0),
                  request(task="paired_statistics", document_count=0),
                  request(task="general_chat", privacy="provider_allowed", document_count=0)):
            for h in route(p, model.read_model_catalog())["handoffs"]:
                assert h["review_endpoint"] is None or h["review_endpoint"] in paths, h
        url = "/studio/api/workflow/adaptive/"
        data = request().model_dump()
        assert client.post(url+"review", json=data).status_code == 401
        resp = client.post(url+"review", json=data, headers=AUTH)
        assert resp.status_code == 200, resp.text
        assert resp.headers["cache-control"] == "no-store"
        out = resp.json()
        response = client.post(url+"progress", json={"request": data, "route_sha256": out["route_sha256"]}, headers=AUTH)
        assert response.status_code == 200
        assert response.json()["next_review_handoffs"][0]["step_id"] == "extract"
        assert client.post(url+"review", content=b"x"*16385, headers=AUTH).status_code == 413
