import csv
import hashlib
import io
import json
import zipfile
from xml.etree import ElementTree as ET

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import studio_analysis_export as exports
from test_studio_analysis_batch import approved, chained_payload


def request_data(fmt="json"):
    data = chained_payload()
    data["operations"][1]["text"] = "=HYPERLINK(\"private\") <script>secret</script>"
    return {"approved": approved(data), "format": fmt, "export_consent": True}


def test_json_is_deterministic_and_omits_raw_input():
    req = exports.ExportRequest.model_validate(request_data())
    first, _ = exports.build_export(req)
    second, _ = exports.build_export(req)
    assert first == second
    result = json.loads(first)
    assert result["consistency"] == "consistent"
    assert result["external_execution_authorized"] is False
    assert len(result["results"]) == 4
    assert result["results"][2]["input_provenance"]
    assert b"HYPERLINK" not in first and b"secret" not in first


def test_csv_has_provenance_and_no_formula_text():
    data, _ = exports.build_export(exports.ExportRequest.model_validate(request_data("csv")))
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    assert any(row["kind"] == "input" and row["source_step"] == "text" for row in rows)
    assert all(row["consistency"] == "consistent" for row in rows)
    assert b"HYPERLINK" not in data and b"secret" not in data


def test_html_has_no_raw_text_or_active_content():
    data, _ = exports.build_export(exports.ExportRequest.model_validate(request_data("html")))
    assert b"<table>" in data and b"Content-Security-Policy" in data
    assert b"<script>" not in data and b"secret" not in data


def test_mismatch_blocks_export(monkeypatch):
    monkeypatch.setattr(exports, "audit", lambda request: {"status": "mismatch"})
    with pytest.raises(exports.InconsistentResult):
        exports.build_export(exports.ExportRequest.model_validate(request_data()))


def test_endpoint_auth_consent_digest_and_download_headers(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    exports.register(app)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token}
    url = "/studio/api/analysis-batch/export"
    assert client.post(url, json=request_data()).status_code == 401
    for fmt in ("json", "csv", "html", "xlsx", "docx", "pdf", "pptx"):
        response = client.post(url, json=request_data(fmt), headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-disposition"] == f'attachment; filename="nexus-analysis.{fmt}"'
        assert response.headers["x-nexus-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    for consent in (False, "true", 1):
        data = request_data()
        data["export_consent"] = consent
        assert client.post(url, json=data, headers=headers).status_code == 422
    data = request_data()
    data["approved"]["review_sha256"] = "0" * 64
    assert client.post(url, json=data, headers=headers).status_code == 422
    assert client.post(url, content=b"x" * 65537, headers=headers).status_code == 413
    monkeypatch.setattr(exports, "audit", lambda request: {"status": "mismatch"})
    assert client.post(url, json=request_data(), headers=headers).status_code == 409


@pytest.mark.parametrize("fmt,required", [
    ("xlsx", "xl/worksheets/sheet1.xml"),
    ("docx", "word/document.xml"),
])
def test_office_packages_are_deterministic_and_static(fmt, required):
    req = exports.ExportRequest.model_validate(request_data(fmt))
    data, media = exports.build_export(req)
    assert data == exports.build_export(req)[0]
    assert media.startswith("application/vnd.openxmlformats-officedocument.")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        assert required in archive.namelist()
        assert "[Content_Types].xml" in archive.namelist()
        for name in archive.namelist():
            raw = archive.read(name)
            ET.fromstring(raw)
            assert b"HYPERLINK" not in raw and b"secret" not in raw
            assert b'TargetMode="External"' not in raw
            assert b"vbaProject" not in raw
        assert b"source_step" in archive.read(required)
        assert b"numeric.from_metrics" in archive.read(required)
        if fmt == "xlsx":
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            sheet = ET.fromstring(archive.read(required))
            assert sheet.find(".//s:f", ns) is None
            assert sheet.find(".//s:c/s:v", ns) is not None
            assert b"review_sha256" in archive.read("xl/worksheets/sheet2.xml")
        else:
            assert b"Review SHA-256" in archive.read(required)
            assert b"w:tblHeader" in archive.read(required)


def test_pdf_objects_and_xref_are_consistent():
    req = exports.ExportRequest.model_validate(request_data("pdf"))
    data, media = exports.build_export(req)
    assert data == exports.build_export(req)[0]
    assert media == "application/pdf"
    assert data.startswith(b"%PDF-1.4") and data.endswith(b"%%EOF\n")
    offset = int(data.split(b"startxref\n")[1].splitlines()[0])
    assert data[offset:].startswith(b"xref\n")
    lines = data[offset:].splitlines()
    count = int(lines[1].split()[1])
    for index in range(1, count):
        position = int(lines[index + 2].split()[0])
        assert data[position:].startswith(f"{index} 0 obj\n".encode())
    assert b"Review SHA-256" in data
    assert b"HYPERLINK" not in data and b"secret" not in data


def test_pptx_package_contains_all_rows_and_no_active_content():
    req = exports.ExportRequest.model_validate(request_data("pptx"))
    data, media = exports.build_export(req)
    assert data == exports.build_export(req)[0]
    assert media.endswith("presentation")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        slides = [name for name in archive.namelist()
                  if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
        assert len(slides) >= 2
        for name in archive.namelist():
            raw = archive.read(name)
            ET.fromstring(raw)
            assert b"HYPERLINK" not in raw and b"secret" not in raw
            assert b'TargetMode="External"' not in raw
        combined = b"".join(archive.read(name) for name in slides)
        assert b"numeric.from_metrics" in combined
        assert b"input text.characters" in combined


def chart_request(metric="sum"):
    data = request_data("svg")
    data["chart_metric"] = metric
    return data


def test_svg_explicit_metric_and_static_content():
    req = exports.ExportRequest.model_validate(chart_request())
    data, media = exports.build_export(req)
    assert media == "image/svg+xml"
    assert data == exports.build_export(req)[0]
    root = ET.fromstring(data)
    ns = {"s": "http://www.w3.org/2000/svg"}
    assert root.find("s:title", ns).text == "sum by analysis step"
    assert b"HYPERLINK" not in data and b"secret" not in data
    assert b"<script" not in data and b"foreignObject" not in data
    assert b"Review SHA-256" in data
    assert b">numbers<" in data and b">combined<" in data
    assert b">text<" not in data


def test_svg_negative_and_zero_values():
    from studio_analysis_chart import chart_svg
    result = {"review_sha256": "a" * 64, "results": [
        {"step_id": "negative", "metrics": {"sum": -5}},
        {"step_id": "zero", "metrics": {"sum": 0}},
        {"step_id": "positive", "metrics": {"sum": 5}},
    ]}
    root = ET.fromstring(chart_svg(result, "sum"))
    ns = {"s": "http://www.w3.org/2000/svg"}
    bars = root.findall("s:rect", ns)[1:]
    assert [float(bar.attrib["width"]) for bar in bars] == [320, 0, 320]
    assert [float(bar.attrib["x"]) for bar in bars] == [260, 580, 580]
    result["results"] = [{"step_id": "zero", "metrics": {"sum": 0}}]
    assert ET.fromstring(chart_svg(result, "sum")).find("s:rect", ns) is not None
    with pytest.raises(ValueError):
        chart_svg(result, "characters")


def test_svg_requires_metric_and_consent_and_validates_download(monkeypatch):
    token = "test-token-" + "x" * 40
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    app = FastAPI()
    exports.register(app)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + token}
    url = "/studio/api/analysis-batch/export"
    data = chart_request()
    assert client.post(url, json=data).status_code == 401
    response = client.post(url, json=data, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.headers["content-disposition"] == 'attachment; filename="nexus-analysis.svg"'
    assert response.headers["x-nexus-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    for bad in (request_data("svg"), {**data, "format": "json"},
                {**data, "chart_metric": "unknown"}, {**data, "export_consent": False}):
        assert client.post(url, json=bad, headers=headers).status_code == 422
    monkeypatch.setattr(exports, "audit", lambda request: {"status": "mismatch"})
    assert client.post(url, json=data, headers=headers).status_code == 409
