import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_workflow import Plan, register, review_plan


def payload():
    return {"goal": "Prepare a research report", "steps": [
        {"id": "write", "tool": "writing", "description": "Draft report", "depends_on": ["find"]},
        {"id": "find", "tool": "research", "description": "Review sources"},
    ]}


def test_review_order_and_identity():
    first = review_plan(Plan.model_validate(payload()))
    second = review_plan(Plan.model_validate(payload()))
    assert first["review_order"] == ["find", "write"]
    assert first["plan_sha256"] == second["plan_sha256"]
    assert first["execution_authorized"] is False
    assert first["status"] == "review_only"
    changed = payload()
    changed["goal"] = "Different report"
    assert review_plan(Plan.model_validate(changed))["plan_sha256"] != first["plan_sha256"]


@pytest.mark.parametrize("dependencies", [["missing"], ["write"], ["find", "find"]])
def test_invalid_dependencies(dependencies):
    plan = payload()
    plan["steps"][0]["depends_on"] = dependencies
    with pytest.raises(ValueError):
        review_plan(Plan.model_validate(plan))


def test_cycle_and_duplicate_ids():
    plan = payload()
    plan["steps"][1]["depends_on"] = ["write"]
    with pytest.raises(ValueError):
        review_plan(Plan.model_validate(plan))
    plan = payload()
    plan["steps"][1]["id"] = "write"
    with pytest.raises(ValueError):
        review_plan(Plan.model_validate(plan))


def test_endpoint_auth_schema_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/workflow/review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    reply = client.post(url, json=payload(), headers=headers)
    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-store"
    assert reply.json()["execution_authorized"] is False
    bad = payload()
    bad["steps"][0]["tool"] = "shell"
    assert client.post(url, json=bad, headers=headers).status_code == 422
    bad = payload()
    bad["execute"] = True
    assert client.post(url, json=bad, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 32769, headers=headers).status_code == 413
