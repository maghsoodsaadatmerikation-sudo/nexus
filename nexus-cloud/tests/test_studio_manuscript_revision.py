import copy
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_academic import ManuscriptRequest, review
from studio_peer_review import PeerReviewRequest, peer_review
from studio_manuscript_revision import RevisionRequest, compare, register
from test_studio_peer_review import payload as peer_payload


def checked(data):
    data["manuscript_review_sha256"] = review(
        ManuscriptRequest.model_validate(data["manuscript"]))["manuscript_review_sha256"]
    return peer_review(PeerReviewRequest.model_validate(data))


def payload():
    previous = peer_payload()
    current = copy.deepcopy(previous)
    current["manuscript"]["sections"][0]["text"] += " New research question."
    current["annotations"] = [{
        "criterion": "question", "disposition": "reported_addressed",
        "section": "introduction", "start": 22, "end": 43,
        "rationale": "Caller reports revised question.",
    }]
    old, new = checked(previous), checked(current)
    issue = next(row["issue_id"] for row in old["issues"]
                 if row["finding"].get("criterion") == "question")
    return {
        "previous": previous, "previous_peer_review_sha256": old["peer_review_sha256"],
        "current": current, "current_peer_review_sha256": new["peer_review_sha256"],
        "responses": [{"issue_id": issue, "action": "revised", "response": "We added the question.",
                       "section": "introduction", "start": 22, "end": 43}],
    }


def result(data):
    return compare(RevisionRequest.model_validate(data))


def test_revision_tracks_both_versions_and_never_certifies_resolution():
    data = payload()
    out = result(data)
    assert out == result(data)
    assert out["sections"][0]["status"] == "changed"
    assert out["sections"][0]["text_changed"]
    assert not out["sections"][0]["citation_mapping_changed"]
    assert all(row["status"] == "unchanged" for row in out["sections"][1:])
    row = next(r for r in out["issue_ledger"] if r["author_response"])
    assert row["status"] == "not_reported_in_current_review"
    assert row["current_issue"] is None and not row["resolution_verified"]
    text = data["current"]["manuscript"]["sections"][0]["text"][22:43]
    assert row["author_response"]["anchor"]["span_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert "We added the question." not in str(out)
    assert not out["submission_authorized"] and not out["reviewer_acceptance_verified"]
    assert any(r["previous_issue"] and r["previous_issue"]["origin"] == "research_uncertainty"
               and r["current_issue"] for r in out["issue_ledger"])


def test_explicit_response_disclosure_and_unchanged_issue_tracking():
    data = payload()
    data["include_response_text"] = True
    out = result(data)
    assert "We added the question." in str(out)
    assert out["previous_issues_without_author_response"]
    assert out["issue_counts"]["persisting_unchanged"] > 0


@pytest.mark.parametrize("bad", ["stale", "duplicate", "unknown", "old_span", "missing_span", "unchanged_section"])
def test_invalid_response(bad):
    data = payload()
    reply = data["responses"][0]
    if bad == "stale":
        data["current_peer_review_sha256"] = "0"*64
    elif bad == "duplicate":
        data["responses"].append(dict(reply))
    elif bad == "unknown":
        reply["issue_id"] = "p-" + "0"*64
    elif bad == "old_span":
        reply.update(start=0, end=7)
    elif bad == "missing_span":
        del reply["end"]
    else:
        reply.update(section="discussion", start=0, end=7)
    with pytest.raises(ValueError):
        result(data)


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/revision-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url, content=b"x"*2097153, headers=headers).status_code == 413
