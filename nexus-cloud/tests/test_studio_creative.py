import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_creative import ReviewRequest, review, register


def payload():
    return {"brief": {"required_phrases": ["Café"], "excluded_phrases": ["forbidden"],
                      "max_characters": 12},
            "candidates": [{"id": "first", "text": "Cafe\u0301"},
                           {"id": "second", "text": "CAFÉ"},
                           {"id": "third", "text": "forbidden words"}]}


def test_literal_checks_duplicates_and_no_quality_claim():
    data = payload()
    out = review(ReviewRequest.model_validate(data))
    assert out == review(ReviewRequest.model_validate(data))
    a, b, c = out["candidates"]
    assert a["literal_constraints_met"] and b["literal_constraints_met"]
    assert b["duplicate_of"] == "first"
    assert a["text_sha256"] != b["text_sha256"]
    assert c["missing_required_phrase_indices"] == [0]
    assert c["matched_excluded_phrase_indices"] == [0]
    assert c["characters_over_limit"] == 3
    assert not c["literal_constraints_met"]
    assert out["aesthetic_quality_verified"] is False
    assert out["originality_verified"] is False
    assert out["execution_authorized"] is False
    assert "forbidden words" not in str(out)


@pytest.mark.parametrize("bad", ["duplicate", "contradiction", "blank", "control", "id"])
def test_invalid_constraints(bad):
    data = payload()
    if bad == "duplicate":
        data["brief"]["required_phrases"].append("CAFÉ")
    elif bad == "contradiction":
        data["brief"]["excluded_phrases"].append("caf")
    elif bad == "blank":
        data["brief"]["required_phrases"] = [" "]
    elif bad == "control":
        data["candidates"][0]["text"] = "a\x00b"
    else:
        data["candidates"][1]["id"] = "first"
    with pytest.raises(ValueError):
        review(ReviewRequest.model_validate(data))


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/creative/review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["candidates"][0]["literal_constraints_met"]
    assert client.post(url, content=b"x" * 524289, headers=headers).status_code == 413
