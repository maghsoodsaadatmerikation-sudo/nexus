import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_anonymization import ApprovedRedaction, RedactionPlan, preview, run, register


def plan():
    return RedactionPlan.model_validate({
        "parts": [
            {"id": "title", "text": "An Example Study"},
            {"id": "author_details", "text": "Private author details"},
            {"id": "discussion", "text": "Example Institute; EXAMPLE. a@example.org; 0000-0002-1825-0097; NCT12345678."},
            {"id": "references", "text": "Example (2020). Unrelated reference."},
        ],
        "literal_rules": [
            {"category": "institution", "text": "Example Institute"},
            {"category": "name", "text": "Example"},
            {"category": "self_citation", "text": "Example (2020)"},
        ],
        "remove_parts": ["author_details"],
        "scan_nct_registration": True,
    })


def approved(p):
    return ApprovedRedaction(plan=p, review_sha256=preview(p)["review_sha256"], consent=True)


def test_preview_hides_text_and_merges_overlaps():
    p = plan()
    out = preview(p)
    assert out == preview(p)
    assert "Example" not in str(out) and "a@example.org" not in str(out)
    first = out["parts"][2]["spans"][0]
    assert first == {"start": 0, "end": 17, "categories": ["institution", "name"]}
    assert out["parts"][1]["remove_entire_part"]
    redacted = run(approved(p))
    assert redacted["removed_parts"] == ["author_details"]
    assert redacted["parts"][0]["text"] == "An [REDACTED] Study"
    assert redacted["parts"][1]["text"] == "[REDACTED]; [REDACTED]. [REDACTED]; [REDACTED]; [REDACTED]."
    assert redacted["parts"][2]["text"] == "[REDACTED]. Unrelated reference."
    assert not redacted["remaining_rule_matches"]
    assert not redacted["anonymity_verified"] and not redacted["document_metadata_inspected"]


def test_literal_metacharacters_unicode_offsets_and_self_overlap():
    p = RedactionPlan.model_validate({
        "parts": [{"id": "discussion", "text": "مریم aaaa a.b aXb"}],
        "literal_rules": [
            {"category": "name", "text": "مریم"},
            {"category": "other", "text": "aaa"},
            {"category": "other", "text": "a.b"},
        ],
    })
    assert run(approved(p))["parts"][0]["text"] == "[REDACTED] [REDACTED] [REDACTED] aXb"


def test_residual_match_not_silently_accepted():
    p = RedactionPlan.model_validate({
        "parts": [{"id": "discussion", "text": "redacted"}],
        "literal_rules": [{"category": "other", "text": "redacted"}],
    })
    out = run(approved(p))
    assert out["status"] == "remaining_rule_matches"
    assert out["remaining_rule_matches"]


def test_optional_registry_pattern_and_consent():
    p = plan().model_copy(update={"scan_nct_registration": False})
    assert "NCT12345678" in run(approved(p))["parts"][1]["text"]
    data = approved(p)
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"plan": plan()}))


@pytest.mark.parametrize("bad", ["duplicate", "unknown", "all", "blank", "match_budget"])
def test_invalid_plans(bad):
    p = plan().model_dump()
    if bad == "duplicate":
        p["parts"].append(p["parts"][0])
    elif bad == "unknown":
        p["remove_parts"] = ["methods"]
    elif bad == "all":
        p["remove_parts"] = [x["id"] for x in p["parts"]]
    elif bad == "blank":
        p["literal_rules"][0]["text"] = "  "
    else:
        p["parts"][0]["text"] = "a"*3000
        p["literal_rules"] = [{"category": "other", "text": "aa"}]
    with pytest.raises(ValueError):
        preview(RedactionPlan.model_validate(p))


def test_endpoint_auth_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/anonymization/"
    headers = {"Authorization": "Bearer " + token}
    data = approved(plan()).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    response = client.post(url+"review", json=data["plan"], headers=headers)
    assert response.status_code == 200
    assert response.json()["review_sha256"] == data["review_sha256"]
    assert "Example Institute" not in response.text
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*1048577, headers=headers).status_code == 413
