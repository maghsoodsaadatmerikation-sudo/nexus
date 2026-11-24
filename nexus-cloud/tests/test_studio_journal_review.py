import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_academic import ManuscriptRequest, review
from studio_journal_review import JournalRequest, compare, register
from test_studio_academic import payload as manuscript_payload


def payload():
    manuscript = manuscript_payload()
    checked = review(ManuscriptRequest.model_validate(manuscript))
    return {
        "manuscript": manuscript,
        "manuscript_review_sha256": checked["manuscript_review_sha256"],
        "manuscript_topic_tags": ["psychology"],
        "fee_budget": {"currency": "USD", "amount_minor": 0},
        "policies": [{
            "journal_id": "fictional-a", "name": "Fictional Journal A",
            "policy_url": "https://example.org/instructions", "policy_date": "2026-01-01",
            "accepted_article_types": ["commentary"], "topic_tags": ["psychology"],
            "title_word_limit": 3, "main_text_word_limit": 9,
            "abstract_required": False, "required_sections": ["discussion"],
            "mandatory_publication_fee": {"currency": "USD", "amount_minor": 0},
            "anonymized_review_required": True,
        }, {
            "journal_id": "fictional-b", "name": "Fictional Journal B",
            "policy_url": "https://example.org/policy", "policy_date": "2026-01-01",
            "accepted_article_types": ["empirical"], "topic_tags": ["biology"],
            "title_word_limit": 2, "main_text_word_limit": 8,
            "abstract_required": True, "required_sections": ["methods"],
        }],
    }


def result(data):
    return compare(JournalRequest.model_validate(data))


def test_reported_rules_and_unknown_fees():
    data = payload()
    out = result(data)
    assert out == result(data)
    a, b = out["journals"]
    assert a["mismatch_count"] == 0
    assert a["status"] == "manual_review_required"
    assert b["mismatch_count"] == 5
    checks = {x["field"]: x for x in a["checks"]}
    assert checks["main_text_words"]["actual"] == 9
    assert checks["topic_tags"]["outcome"] == "literal_overlap"
    assert checks["mandatory_publication_fee"]["outcome"] == "matches_reported_rule"
    assert checks["anonymized_review"]["outcome"] == "manual_review_required"
    assert next(x for x in b["checks"] if x["field"] == "mandatory_publication_fee")["outcome"] == "unknown"
    assert out["unresolved_research_issues"]
    assert not out["policy_verified"] and not out["submission_authorized"]


def test_fee_currency_and_digest():
    data = payload()
    old = result(data)
    data["policies"][0]["mandatory_publication_fee"] = {"currency": "EUR", "amount_minor": 100}
    new = result(data)
    assert next(x for x in new["journals"][0]["checks"] if x["field"] == "mandatory_publication_fee")["outcome"] == "currency_not_comparable"
    assert new["journal_review_sha256"] != old["journal_review_sha256"]
    data["policies"][0]["mandatory_publication_fee"]["currency"] = "USD"
    assert result(data)["journals"][0]["mismatch_count"] == 1


@pytest.mark.parametrize("bad", ["stale", "duplicate", "url", "date", "contradiction", "negative_fee", "duplicate_tag"])
def test_invalid_policy(bad):
    data = payload()
    p = data["policies"][0]
    if bad == "stale":
        data["manuscript_review_sha256"] = "0"*64
    elif bad == "duplicate":
        data["policies"].append(copy.deepcopy(p))
    elif bad == "url":
        p["policy_url"] = "https://user:pass@example.org/"
    elif bad == "date":
        p["policy_date"] = "2026-02-30"
    elif bad == "contradiction":
        p["required_sections"].append("abstract")
    elif bad == "negative_fee":
        p["mandatory_publication_fee"]["amount_minor"] = -1
    else:
        p["topic_tags"].append("psychology")
    with pytest.raises(ValueError):
        result(data)


def test_auth_and_bound(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/journal-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url, content=b"x"*1048577, headers=headers).status_code == 413
