import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_workflow import Plan, review_plan
from studio_workflow_revision import RevisionRequest, register, review_revision


def request_data():
    plan = {"goal": "Prepare report", "steps": [
        {"id": "write", "tool": "writing", "description": "Draft", "depends_on": ["analyze"]},
        {"id": "find", "tool": "research", "description": "Find sources"},
        {"id": "analyze", "tool": "analysis", "description": "Analyze", "depends_on": ["find"]},
        {"id": "independent", "tool": "human_review", "description": "Review scope"},
    ]}
    return {"previous": {"plan": plan, "plan_sha256": review_plan(Plan.model_validate(plan))["plan_sha256"],
                        "acknowledged": ["find", "analyze", "independent"]},
            "proposed": copy.deepcopy(plan)}


def result(data):
    return review_revision(RevisionRequest.model_validate(data))


def test_downstream_invalidation_and_no_automatic_carry():
    data = request_data()
    data["proposed"]["steps"][1]["description"] = "Find alternative sources"
    review = result(data)
    assert review["changed"] == ["find"]
    assert review["affected"] == ["find", "analyze", "write"]
    assert review["invalidated_acknowledgments"] == ["find", "analyze"]
    assert review["reusable_acknowledgment_candidates"] == ["independent"]
    assert review["carried_acknowledgments"] == []
    assert review["execution_authorized"] is False
    assert review["status"] == "revision_review_required"


def test_goal_change_invalidates_all():
    data = request_data()
    data["proposed"]["goal"] = "Different goal"
    review = result(data)
    assert review["goal_changed"] is True
    assert len(review["affected"]) == 4
    assert review["reusable_acknowledgment_candidates"] == []


def test_removed_and_added_steps():
    data = request_data()
    data["proposed"]["steps"].pop()
    data["proposed"]["steps"].append(
        {"id": "verify", "tool": "human_review", "description": "Verify report",
         "depends_on": ["write"]})
    review = result(data)
    assert review["removed"] == ["independent"]
    assert review["added"] == ["verify"]
    assert review["invalidated_acknowledgments"] == ["independent"]


def test_unchanged_plan_still_has_no_execution_authority():
    review = result(request_data())
    assert review["status"] == "unchanged"
    assert review["affected"] == []
    assert review["carried_acknowledgments"] == []
    assert review["execution_authorized"] is False


@pytest.mark.parametrize("change", ["stale", "cancelled", "cycle", "missing_dependency", "invalid_ack"])
def test_invalid_revision(change):
    data = request_data()
    if change == "stale":
        data["previous"]["plan_sha256"] = "0" * 64
    elif change == "cancelled":
        data["previous"]["cancelled"] = True
    elif change == "cycle":
        data["proposed"]["steps"][1]["depends_on"] = ["write"]
    elif change == "missing_dependency":
        data["proposed"]["steps"][0]["depends_on"] = ["missing"]
    else:
        data["previous"]["acknowledged"] = ["analyze"]
    with pytest.raises(ValueError):
        result(data)


def test_revision_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/workflow/revision-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=request_data()).status_code == 401
    response = client.post(url, json=request_data(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["execution_authorized"] is False
    bad = request_data()
    bad["execute"] = True
    assert client.post(url, json=bad, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 65537, headers=headers).status_code == 413
