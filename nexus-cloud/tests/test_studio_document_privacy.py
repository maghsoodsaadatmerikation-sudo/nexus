import base64
import io
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studio_document_privacy import (
    ApprovedPrivacy, PrivacyPlan, preview, run, register, CP, CT, W, REL, MAIN_TYPE,
)


def fixture(extra=None, comment=b"", **options):
    parts = {
        "[Content_Types].xml": f'<Types xmlns="{CT}"><Override PartName="/word/document.xml" ContentType="{MAIN_TYPE}"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{REL}"/>',
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:body><w:ins w:author="Private Person"><w:r><w:rPr><w:vanish/></w:rPr><w:t>Body text</w:t></w:r></w:ins></w:body></w:document>',
        "docProps/core.xml": f'<cp:coreProperties xmlns:cp="{CP}"><cp:lastModifiedBy>Private Person</cp:lastModifiedBy></cp:coreProperties>',
        "docProps/custom.xml": "<Properties>Other private value</Properties>",
        "word/comments.xml": f'<w:comments xmlns:w="{W}"><w:comment w:author="Private Person"/></w:comments>',
        "word/_rels/document.xml.rels": f'<Relationships xmlns="{REL}"><Relationship TargetMode="External" Target="https://example.org/private"/></Relationships>',
    }
    parts.update(extra or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.comment = comment
        for name, content in parts.items():
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            z.writestr(info, content)
    return PrivacyPlan(docx_base64=base64.b64encode(stream.getvalue()).decode(), **options)


def approved(plan):
    return ApprovedPrivacy(plan=plan, review_sha256=preview(plan)["review_sha256"], consent=True)


def test_inventory_without_sensitive_values_and_explicit_copy():
    plan = fixture(reset_core_properties=True, reset_zip_metadata=True, comment=b"Private Person")
    out = preview(plan)
    assert out == preview(plan)
    assert "Private Person" not in str(out) and "example.org" not in str(out)
    assert out["findings"]["core_property_elements"] == 1
    assert out["findings"]["tracked_change_elements"] == 1
    assert out["findings"]["hidden_text_markers"] == 1
    assert out["findings"]["external_relationships"] == 1
    assert out["findings"]["zip_archive_comment"] == 1
    result = run(approved(plan))
    assert result["core_properties_reset"] and result["zip_metadata_reset"]
    assert not result["remaining_findings"]["core_property_elements"]
    assert not result["remaining_findings"]["zip_entry_metadata"]
    assert result["remaining_findings"]["tracked_change_elements"] == 1
    assert result["remaining_findings"]["other_property_parts"] == 1
    assert not result["anonymity_verified"] and not result["document_rendering_verified"]
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(plan.docx_base64))) as old, \
         zipfile.ZipFile(io.BytesIO(base64.b64decode(result["docx_base64"]))) as new:
        assert not new.comment
        assert old.namelist() == new.namelist()
        for name in old.namelist():
            if name != "docProps/core.xml":
                assert old.read(name) == new.read(name)


def test_signed_package_refuses_rewrite():
    plan = fixture({"_xmlsignatures/sig1.xml": "<Signature/>"}, reset_core_properties=True)
    assert not preview(plan)["rewrite_allowed"]
    with pytest.raises(ValueError):
        run(approved(plan))


def test_consent_digest_and_archive_comment_gate():
    plan = fixture(reset_core_properties=True, comment=b"metadata")
    with pytest.raises(ValueError):
        run(approved(plan))
    data = approved(fixture(reset_core_properties=True))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"consent": False}))
    with pytest.raises(ValueError):
        run(data.model_copy(update={"review_sha256": "0"*64}))
    with pytest.raises(ValueError):
        run(approved(fixture()))


@pytest.mark.parametrize("extra", [
    {"../escape.xml": "<x/>"}, {"word/DOCUMENT.xml": "<x/>"},
    {"customXml/item.xml": '<!DOCTYPE x [<!ENTITY a "data">]><x>&a;</x>'},
    {"customXml/item.xml": b"\xff\xfe<\x00x\x00/\x00>\x00"},
    {"word/media/large.bin": b"x"*(2*1024*1024+1)},
])
def test_reject_ambiguous_or_unsupported_packages(extra):
    with pytest.raises((ValueError, UnicodeError)):
        preview(fixture(extra))


def test_endpoint_auth_no_store_and_bounds(monkeypatch):
    token = "test-token-" + "x"*40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    register(app)
    client = TestClient(app)
    url = "/studio/api/documents/privacy/"
    headers = {"Authorization": "Bearer " + token}
    data = approved(fixture(reset_zip_metadata=True)).model_dump()
    assert client.post(url+"review", json=data["plan"]).status_code == 401
    response = client.post(url+"review", json=data["plan"], headers=headers)
    assert response.status_code == 200
    assert response.json()["review_sha256"] == data["review_sha256"]
    response = client.post(url+"run", json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert client.post(url+"run", json={**data, "consent": "true"}, headers=headers).status_code == 422
    assert client.post(url+"review", json={"docx_base64": "!!!!"}, headers=headers).status_code == 422
    assert client.post(url+"run", content=b"x"*(3*1024*1024+1), headers=headers).status_code == 413
