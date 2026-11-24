import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_research_perspectives import PerspectiveRequest, compare_perspectives
from studio_research_critique import CritiqueRequest, critique, register
from test_studio_research_perspectives import payload as perspective_data


def payload():
    data = perspective_data()
    return {"perspective_request": data,
            "perspective_review_sha256": compare_perspectives(
                PerspectiveRequest.model_validate(data))["perspective_review_sha256"]}


def result(data):
    return critique(CritiqueRequest.model_validate(data))


def candidate_data():
    data = payload()
    data["candidate"] = result(data)["reference_draft"]
    return data


def test_reference_draft_and_exact_round_trip():
    data = payload()
    out = result(data)
    assert out["status"] == "reference_draft"
    assert out == result(data)
    data["candidate"] = out["reference_draft"]
    reviewed = result(data)
    assert reviewed["status"] == "structurally_consistent"
    assert reviewed["finding_count"] == 0
    assert reviewed["reference_draft_sha256"] == out["reference_draft_sha256"]
    assert reviewed["human_review_required"] is True
    assert reviewed["semantic_verification"] is False
    assert reviewed["independent_verification"] is False
    assert reviewed["execution_authorized"] is False
    assert "Unverified excerpt" not in str(reviewed)


@pytest.mark.parametrize("change,code", [
    ("claim", "missing_claim"),
    ("status", "unsupported_verification_status"),
    ("source", "missing_source_link"),
    ("relation", "altered_source_relation_or_kind"),
    ("metadata", "altered_source_relation_or_kind"),
    ("invented_source", "unexpected_source_link"),
    ("view", "missing_perspective"),
    ("membership", "missing_perspective_membership"),
    ("issue", "missing_uncertainty_item"),
    ("duplicate", "duplicate_uncertainty_item"),
    ("authority", "unsupported_authority_or_verification"),
])
def test_tampering_requires_revision(change, code):
    data = candidate_data()
    draft = data["candidate"]
    row = draft["claims"][0]
    if change == "claim":
        draft["claims"].pop()
    elif change == "status":
        row["status"] = "verified"
    elif change == "source":
        row["sources"].pop()
    elif change == "relation":
        row["sources"][0]["relation"] = "caller_reported_mixed"
    elif change == "metadata":
        row["sources"][0]["metadata_only"] = not row["sources"][0]["metadata_only"]
    elif change == "invented_source":
        row["sources"][0]["source_id"] = "source:" + "0" * 64
    elif change == "view":
        draft["perspectives"].pop()
    elif change == "membership":
        draft["perspectives"][0]["claim_ids"] = []
    elif change == "issue":
        draft["unresolved_item_ids"].pop()
    elif change == "duplicate":
        draft["unresolved_item_ids"].append(draft["unresolved_item_ids"][0])
    elif change == "authority":
        draft["execution_authorized"] = True
    out = result(data)
    assert out["status"] == "revision_required"
    assert code in {item["code"] for item in out["findings"]}
    assert out["execution_authorized"] is False


def test_stale_review_and_extra_prose_are_rejected():
    data = candidate_data()
    data["perspective_review_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Stale"):
        result(data)
    data = candidate_data()
    data["candidate"]["conclusion"] = "Unsupported conclusion"
    with pytest.raises(ValueError):
        result(data)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/draft-critique"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=candidate_data(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "structurally_consistent"
    assert client.post(url, content=b"x" * 393217, headers=headers).status_code == 413
