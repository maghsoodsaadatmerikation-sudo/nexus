import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_bibliography import BibliographyRequest, reconcile, register
from studio_research_synthesis import SynthesisRequest, synthesize
from test_studio_research_synthesis import payload as synthesis_data


def payload():
    data = synthesis_data()
    report = synthesize(SynthesisRequest.model_validate(data))
    ref = report["references"][0]
    return {"synthesis": data, "report_sha256": report["report_sha256"],
            "metadata": [{"reference_number": ref["number"], "source_id": ref["source_id"],
                          "origin": "manual", "title": ref["title"],
                          "authors": [{"family": "Example", "initials": "A B"}],
                          "year": 2020, "journal": "Example Journal",
                          "volume": "3", "issue": "2", "locator": "10-12"}]}


def result(data):
    return reconcile(BibliographyRequest.model_validate(data))


def test_complete_layout_is_a_draft_and_incomplete_reference_remains():
    data = payload()
    out = result(data)
    assert out == result(data)
    first, second = out["entries"]
    assert first["citation_drafts"]["apa_like_plain_text"].startswith("Example, A. B. (2020).")
    assert "2020;3(2):10-12" in first["citation_drafts"]["vancouver_like_plain_text"]
    assert first["csl_like_metadata"]["DOI"] == "10.1234/abc"
    assert not second["citation_drafts"]
    assert "authors" in second["missing_journal_layout_fields"]
    assert not out["independent_verification"] and not out["style_compliance_verified"]
    assert not out["metadata_retrieved"] and not out["submission_authorized"]


def test_conflicting_fields_are_not_silently_selected():
    data = payload()
    data["metadata"].append({**data["metadata"][0], "origin": "publisher", "year": 2021})
    out = result(data)
    first = out["entries"][0]
    assert "year" in first["conflicts"] and "year" not in first["resolved_fields"]
    assert len(first["conflicts"]["year"]) == 2
    assert not first["citation_drafts"]
    assert out["bibliography_review_sha256"] != result(payload())["bibliography_review_sha256"]


@pytest.mark.parametrize("bad", ["stale", "source", "duplicate", "initials", "blank"])
def test_invalid_metadata(bad):
    data = payload()
    if bad == "stale":
        data["report_sha256"] = "0" * 64
    elif bad == "source":
        data["metadata"][0]["source_id"] = "source:" + "0" * 64
    elif bad == "duplicate":
        data["metadata"].append(data["metadata"][0])
    elif bad == "initials":
        data["metadata"][0]["authors"][0]["initials"] = "?"
    else:
        data["metadata"][0]["journal"] = " "
    with pytest.raises(ValueError):
        result(data)


def test_auth_and_body_limit(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/research/bibliography-review"
    headers = {"Authorization": "Bearer " + token}
    assert client.post(url, json=payload()).status_code == 401
    response = client.post(url, json=payload(), headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url, content=b"x" * 786433, headers=headers).status_code == 413
