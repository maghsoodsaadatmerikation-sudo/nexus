import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_workflow import Plan, ProgressReview, register, review_plan, review_progress


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


def progress_payload(acknowledged=None, cancelled=False):
    plan = payload()
    return {
        "plan": plan,
        "plan_sha256": review_plan(Plan.model_validate(plan))["plan_sha256"],
        "acknowledged": acknowledged if acknowledged is not None else [],
        "cancelled": cancelled,
    }


@pytest.mark.parametrize(("acknowledged", "ready", "status"), [
    ([], ["find"], "review_pending"),
    (["find"], ["write"], "review_pending"),
    (["write", "find"], [], "all_acknowledged"),
])
def test_progress_is_dependency_ordered(acknowledged, ready, status):
    result = review_progress(ProgressReview.model_validate(progress_payload(acknowledged)))
    assert result["ready_for_review"] == ready
    assert result["status"] == status
    assert result["execution_authorized"] is False
    assert result["evidence"] == "caller_reported_only"
    assert result["acknowledged_count"] == len(acknowledged)
    assert result["total_steps"] == 2
    if len(acknowledged) == 2:
        assert result["acknowledged"] == ["find", "write"]


@pytest.mark.parametrize("acknowledged", [["write"], ["missing"], ["find", "find"]])
def test_invalid_progress_rejected(acknowledged):
    with pytest.raises(ValueError):
        review_progress(ProgressReview.model_validate(progress_payload(acknowledged)))


def test_progress_rejects_changed_plan():
    data = progress_payload(["find"])
    data["plan"]["steps"][1]["description"] = "Changed source scope"
    with pytest.raises(ValueError):
        review_progress(ProgressReview.model_validate(data))


def test_cancelled_progress_has_no_ready_steps():
    result = review_progress(ProgressReview.model_validate(progress_payload(["find"], True)))
    assert result["status"] == "cancelled"
    assert result["ready_for_review"] == []
    assert result["blocked"] == ["write"]
    assert result["execution_authorized"] is False


def test_progress_parallel_dependencies():
    data = progress_payload()
    data["plan"]["steps"].append({"id": "analyze", "tool": "analysis", "description": "Inspect data"})
    data["plan"]["steps"][0]["depends_on"].append("analyze")
    data["plan_sha256"] = review_plan(Plan.model_validate(data["plan"]))["plan_sha256"]
    result = review_progress(ProgressReview.model_validate(data))
    assert result["ready_for_review"] == ["find", "analyze"]
    data["acknowledged"] = ["find"]
    assert review_progress(ProgressReview.model_validate(data))["ready_for_review"] == ["analyze"]


def test_progress_endpoint_auth_bounds_and_no_execution(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/workflow/progress"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=progress_payload()).status_code == 401
    reply = client.post(url, json=progress_payload(), headers=headers)
    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-store"
    assert reply.json()["execution_authorized"] is False
    for bad in [
        progress_payload(["write"]),
        {**progress_payload(), "cancelled": "false"},
        {**progress_payload(), "execute": True},
        {**progress_payload(), "plan_sha256": "0" * 64},
    ]:
        assert client.post(url, json=bad, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 32769, headers=headers).status_code == 413
