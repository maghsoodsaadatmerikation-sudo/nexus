import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_critique import CritiqueRequest, critique
from studio_research_memory import (
    ChangeRequest, RecallRequest, Snapshot, change, digest, recall, register,
)
from test_studio_research_critique import payload as critique_data


def scope(snapshot):
    return {"snapshot": snapshot, "project_id": snapshot["project_id"],
            "expected_sha256": digest(Snapshot.model_validate(snapshot))}


def add_data():
    snapshot = Snapshot(project_id="research", revision=0).model_dump()
    reference = critique_data()
    checked = critique(CritiqueRequest.model_validate(reference))
    return {**scope(snapshot), "consent": True, "operation": {
        "kind": "add", "reference": reference, "record": {
            "id": "note_a", "note": "بررسي روش پژوهش cohort",
            "reference_draft_sha256": checked["reference_draft_sha256"],
            "claim_ids": ["claim:first"],
        }
    }}


def updated():
    return change(ChangeRequest.model_validate(add_data()))


def test_add_recall_remove_and_clear():
    out = updated()
    snapshot = out["snapshot"]
    assert snapshot["revision"] == 1 and len(snapshot["records"]) == 1
    assert out["server_persistence"] is False
    assert "Unverified excerpt" not in str(out)
    data = {**scope(snapshot), "query": "بررسی پژوهش", "enabled": True}
    match = recall(RecallRequest.model_validate(data))
    assert match["matches"][0]["record_id"] == "note_a"
    assert match["matches"][0]["matched_terms"] == 2
    assert recall(RecallRequest.model_validate({**data, "enabled": False}))["matches"] == []
    assert recall(RecallRequest.model_validate({**data, "isolated": True}))["matches"] == []
    for op in ({"kind": "remove", "record_id": "note_a"}, {"kind": "clear"}):
        result = change(ChangeRequest.model_validate({**scope(snapshot), "consent": True,
                                                     "operation": op}))
        assert result["snapshot"]["records"] == [] and result["snapshot"]["revision"] == 2
        assert result["snapshot_sha256"] != out["snapshot_sha256"]
    assert len(snapshot["records"]) == 1


@pytest.mark.parametrize("bad", ["consent", "scope", "digest", "claim", "reference", "duplicate_claim"])
def test_invalid_change(bad):
    data = add_data()
    if bad == "consent":
        data["consent"] = False
    elif bad == "scope":
        data["project_id"] = "other"
    elif bad == "digest":
        data["expected_sha256"] = "0" * 64
    elif bad == "claim":
        data["operation"]["record"]["claim_ids"] = ["claim:missing"]
    elif bad == "reference":
        data["operation"]["record"]["reference_draft_sha256"] = "0" * 64
    else:
        data["operation"]["record"]["claim_ids"] = ["claim:first", "claim:first"]
    with pytest.raises(ValueError):
        change(ChangeRequest.model_validate(data))


def test_scope_and_digest_bind_exact_snapshot():
    snapshot = updated()["snapshot"]
    data = {**scope(snapshot), "query": "cohort", "enabled": True}
    with pytest.raises(ValueError):
        recall(RecallRequest.model_validate({**data, "project_id": "other"}))
    snapshot["records"][0]["note"] = "Changed"
    with pytest.raises(ValueError):
        recall(RecallRequest.model_validate(data))


def test_endpoint_auth_consent_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token}
    base = "/studio/api/research/memory/"
    data = add_data()
    assert client.post(base + "change", json=data).status_code == 401
    response = client.post(base + "change", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    query = {**scope(response.json()["snapshot"]), "query": "cohort", "enabled": True}
    assert client.post(base + "recall", json=query).status_code == 401
    assert client.post(base + "recall", json=query, headers=headers).json()["matches"]
    assert client.post(base + "change", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(base + "recall", content=b"x" * 131073, headers=headers).status_code == 413
    assert client.post(base + "change", content=b"x" * 524289, headers=headers).status_code == 413
