import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_analysis_audit import AuditRequest, audit, register
from studio_analysis_batch import ApprovedBatch, run
from test_studio_analysis_batch import approved, chained_payload


def request_data():
    batch = approved(chained_payload())
    return {"approved": batch, "candidate": run(ApprovedBatch.model_validate(batch))}


def test_correct_result_is_consistent():
    data = request_data()
    result = audit(AuditRequest.model_validate(data))
    assert result["status"] == "consistent"
    assert result["finding_count"] == 0
    assert result["external_execution_authorized"] is False
    assert "recomputed_result" not in result


@pytest.mark.parametrize("change,code", [
    ("metric", "value_mismatch"), ("boolean", "type_mismatch"),
    ("provenance", "value_mismatch"), ("missing", "missing_field"),
    ("extra", "unexpected_fields"), ("order", "value_mismatch"),
    ("authority", "value_mismatch"), ("digest", "value_mismatch"),
])
def test_tampering_detected_and_recomputed(change, code):
    data = request_data()
    correct = copy.deepcopy(data["candidate"])
    candidate = data["candidate"]
    if change == "metric":
        candidate["results"][0]["metrics"]["characters"] = 0
    elif change == "boolean":
        candidate["results"][0]["metrics"]["lines"] = True
    elif change == "provenance":
        candidate["results"][2]["input_provenance"][0]["value"] = 8
    elif change == "missing":
        del candidate["results"][0]["metrics"]["lines"]
    elif change == "extra":
        candidate["secret_untrusted_field"] = "private"
    elif change == "order":
        candidate["results"][0], candidate["results"][1] = candidate["results"][1], candidate["results"][0]
    elif change == "authority":
        candidate["external_execution_authorized"] = True
    else:
        candidate["review_sha256"] = "0" * 64
    result = audit(AuditRequest.model_validate(data))
    assert result["status"] == "mismatch"
    assert code in {finding["code"] for finding in result["findings"]}
    assert result["recomputed_result"] == correct
    assert result["external_execution_authorized"] is False
    assert "secret_untrusted_field" not in str(result)


def test_reject_stale_or_unapproved_input():
    data = request_data()
    data["approved"]["batch"]["operations"][0]["values"][0] = 100
    with pytest.raises(ValueError):
        audit(AuditRequest.model_validate(data))
    data = request_data()
    data["approved"]["consent"] = False
    with pytest.raises(ValueError):
        audit(AuditRequest.model_validate(data))


def test_findings_bounded():
    data = request_data()
    for row in data["candidate"]["results"]:
        for metric in row["metrics"]:
            row["metrics"][metric] = "wrong"
        row["operation"] = "wrong"
        row["step_id"] = "wrong"
        for ref in row.get("input_provenance", []):
            for key in ref:
                ref[key] = None
    result = audit(AuditRequest.model_validate(data))
    assert len(result["findings"]) == 32
    assert result["finding_count"] > 32
    assert result["findings_truncated"] is True


def test_authenticated_endpoint_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/analysis-batch/audit"
    headers = {"Authorization": "Bearer " + token}
    data = request_data()
    assert client.post(url, json=data).status_code == 401
    response = client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "consistent"
    data["candidate"]["results"].pop()
    response = client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "mismatch"
    assert client.post(url, content=b"x" * 98305, headers=headers).status_code == 413
