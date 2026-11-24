import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_academic import ManuscriptRequest, review
from studio_peer_review import PeerReviewRequest, peer_review, register
from test_studio_academic import payload as manuscript_payload


def payload(article_type="commentary"):
    manuscript = manuscript_payload()
    manuscript["article_type"] = article_type
    checked = review(ManuscriptRequest.model_validate(manuscript))
    return {"manuscript": manuscript,
            "manuscript_review_sha256": checked["manuscript_review_sha256"]}


def result(data):
    return peer_review(PeerReviewRequest.model_validate(data))


def annotation(**changes):
    return {"criterion": "question", "disposition": "reported_addressed",
            "section": "introduction", "start": 0, "end": 7,
            "rationale": "Caller notes the question.", **changes}


def test_review_preserves_upstream_issues_and_adds_checklist():
    data = payload("empirical")
    checked = review(ManuscriptRequest.model_validate(data["manuscript"]))
    out = result(data)
    assert out == result(data)
    assert out["checklist_counts"]["unreviewed"] == 14
    assert {"design", "analysis", "confounding"} <= {x["criterion"] for x in out["checklist"]}
    assert [x["finding"] for x in out["issues"] if x["origin"] == "manuscript_structural_review"] == checked["findings"]
    assert [x["finding"] for x in out["issues"] if x["origin"] == "research_uncertainty"] == checked["unresolved_research_issues"]
    assert out["publication_recommendation"] is None and not out["scientific_validity_verified"]


def test_anchor_and_caller_dispositions_never_close_upstream_uncertainties():
    data = payload()
    data["annotations"] = [annotation(), {"criterion": "ethics", "disposition": "not_applicable",
                                          "rationale": "Caller reports no participants."}]
    out = result(data)
    assert out["checklist_counts"] == {"unreviewed": 7, "reported_addressed": 1,
                                       "concern": 0, "not_applicable": 1}
    first = out["checklist"][0]
    assert first["anchor"]["span_sha256"] == hashlib.sha256(b"Context").hexdigest()
    assert "Caller notes" not in str(out)
    assert any(row["origin"] == "research_uncertainty" for row in out["issues"])
    assert any(row["finding"].get("disposition") == "not_applicable" for row in out["issues"])
    assert out["peer_review_sha256"] != result(payload())["peer_review_sha256"]
    assert not out["independent_verification"] and not out["submission_authorized"]


@pytest.mark.parametrize("bad", ["stale", "duplicate", "unknown", "partial", "reversed",
                                  "out_of_bounds", "no_anchor", "blank_rationale"])
def test_invalid_annotations(bad):
    data = payload()
    data["annotations"] = [annotation()]
    a = data["annotations"][0]
    if bad == "stale":
        data["manuscript_review_sha256"] = "0"*64
    elif bad == "duplicate":
        data["annotations"].append(dict(a))
    elif bad == "unknown":
        a["criterion"] = "sampling"
    elif bad == "partial":
        del a["start"]
    elif bad == "reversed":
        a["start"] = 8
    elif bad == "out_of_bounds":
        a["end"] = 1000
    elif bad == "no_anchor":
        for k in ("section", "start", "end"):
            del a[k]
    else:
        a["rationale"] = " "
    with pytest.raises(ValueError):
        result(data)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/peer-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["submission_authorized"] is False
    assert client.post(url, content=b"x"*1048577, headers=headers).status_code == 413
