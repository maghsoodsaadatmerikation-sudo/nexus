import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_critique import CritiqueRequest, critique
import studio_research_improvement as engine
from test_studio_research_critique import candidate_data


def payload():
    data = candidate_data()
    reference = critique(CritiqueRequest.model_validate(data))["reference_draft_sha256"]
    return {"review": data, "reference_draft_sha256": reference, "repair_consent": True}


def result(data):
    return engine.improve(engine.ImprovementRequest.model_validate(data))


def damage(data):
    draft = data["review"]["candidate"]
    draft["claims"][0]["status"] = "verified"
    draft["claims"][0]["sources"].pop()
    draft["unresolved_item_ids"].pop()
    draft["execution_authorized"] = True


def test_repair_rechecks_complete_reference_and_preserves_input():
    data = payload()
    expected = copy.deepcopy(data["review"]["candidate"])
    damage(data)
    original = copy.deepcopy(data)
    out = result(data)
    assert out == result(data)
    assert data == original
    assert out["status"] == "structural_repair_consistent"
    assert out["repair_rounds"] == 1
    assert out["initial_finding_count"] >= 4
    assert out["final_finding_count"] == 0
    assert out["initial_candidate_sha256"] != out["final_candidate_sha256"]
    assert out["final_draft"] == expected
    assert out["human_review_required"] and not out["independent_verification"]
    assert not out["execution_authorized"] and not out["server_persistence"]
    data["review"]["candidate"] = out["final_draft"]
    fixed = result(data)
    assert fixed["status"] == "already_consistent" and fixed["repair_rounds"] == 0
    assert fixed["initial_candidate_sha256"] == out["final_candidate_sha256"]


def test_no_consent_means_no_repaired_draft():
    data = payload()
    damage(data)
    data["repair_consent"] = False
    out = result(data)
    assert out["status"] == "repair_consent_required"
    assert out["repair_rounds"] == 0 and out["final_draft"] is None
    assert not out["repair_applied_to_returned_draft"]


def test_failed_recheck_rejects_repair(monkeypatch):
    data = payload()
    damage(data)
    real = engine.critique
    calls = []
    def fail_second(request):
        checked = real(request)
        calls.append(checked)
        if len(calls) == 2:
            checked["finding_count"] = 1
            checked["status"] = "revision_required"
        return checked
    monkeypatch.setattr(engine, "critique", fail_second)
    out = result(data)
    assert len(calls) == 2
    assert out["status"] == "repair_rejected" and out["final_draft"] is None
    assert not out["repair_applied_to_returned_draft"]


@pytest.mark.parametrize("change", ["stale", "missing", "consent_type"])
def test_invalid_request(change):
    data = payload()
    if change == "stale":
        data["reference_draft_sha256"] = "0" * 64
    elif change == "missing":
        data["review"]["candidate"] = None
    else:
        data["repair_consent"] = "true"
    with pytest.raises(ValueError):
        result(data)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    engine.register(app)
    client = TestClient(app)
    url = "/studio/api/research/improvement"
    headers = {"Authorization": "Bearer " + token}
    data = payload()
    damage(data)
    assert client.post(url, json=data).status_code == 401
    response = client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "structural_repair_consistent"
    assert client.post(url, content=b"x" * 393217, headers=headers).status_code == 413
