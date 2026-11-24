"""Bounded text extraction from UTF-8 text and conventional DOCX body paragraphs."""
from __future__ import annotations

import base64
import binascii
import hashlib
import zipfile
from collections import Counter
from typing import Literal
from xml.etree import ElementTree as ET

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_document_privacy import PrivacyPlan, W, load, inventory, MAX_ARCHIVE
from studio_peer_review import digest
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
MAX_BLOCKS = 2000
MAX_TEXT = 200000
NS = "{" + W + "}"


class ExtractionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    format: Literal["txt", "docx"]
    content_base64: str = Field(min_length=4, max_length=2796204)
    include_table_cells: bool = False


class ApprovedExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: ExtractionPlan
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def plain_text(data):
    text = data.decode("utf-8-sig", errors="strict")
    if any(ord(c) < 32 and c not in "\r\n\t" or ord(c) == 127 for c in text):
        raise ValueError("Unsupported text control character")
    return text


def collect(plan):
    data = base64.b64decode(plan.content_base64, validate=True)
    if not data or len(data) > MAX_ARCHIVE:
        raise ValueError("Invalid document size")
    blocks, skipped = [], Counter()
    chars = 0

    def add(text, location):
        nonlocal chars
        if not text.strip():
            return
        chars += len(text)
        if len(blocks) >= MAX_BLOCKS or chars > MAX_TEXT:
            raise ValueError("Extracted content exceeds bounds")
        blocks.append({"index": len(blocks), "location": location, "text": text,
                       "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})

    if plan.format == "txt":
        if plan.include_table_cells:
            raise ValueError("Table option applies only to DOCX")
        for i, line in enumerate(plain_text(data).splitlines()):
            add(line, {"line": i})
        findings = {}
    else:
        _, parts, trees, infos, comment = load(PrivacyPlan(docx_base64=plan.content_base64))
        findings = inventory(parts, trees, infos, comment)
        if findings.get("signature_or_macro_parts") or findings.get("signature_or_macro_content_types"):
            raise ValueError("Signed or macro-associated package unsupported")
        body = trees["word/document.xml"].find(NS + "body")
        if body is None:
            raise ValueError("Missing document body")

        def paragraph(node, location):
            # Skip complex fields and explicit revision/hidden markers anywhere
            # in this paragraph, rather than disclose stale or deleted text.
            unsafe = {"fldChar", "instrText", "fldSimple", "del", "ins",
                      "moveFrom", "moveTo", "vanish", "webHidden", "specVanish",
                      "delText", "delInstrText"}
            unsafe_tags = {NS + k for k in unsafe}
            if any(e.tag in unsafe_tags for e in node.iter()):
                skipped["paragraph_with_field_revision_or_hidden_marker"] += 1
                return
            pieces = []
            for child in node:
                if child.tag == NS + "pPr":
                    continue
                if child.tag != NS + "r":
                    skipped["unsupported_inline_container"] += 1
                    continue
                for item in child:
                    if item.tag == NS + "t":
                        pieces.append(item.text or "")
                    elif item.tag == NS + "tab":
                        pieces.append("\t")
                    elif item.tag in (NS + "br", NS + "cr"):
                        pieces.append("\n")
                    elif item.tag != NS + "rPr":
                        skipped["unsupported_run_element"] += 1
            add("".join(pieces), location)

        for i, child in enumerate(body):
            if child.tag == NS + "p":
                paragraph(child, {"body_index": i})
            elif child.tag == NS + "tbl":
                if not plan.include_table_cells:
                    skipped["table_not_requested"] += 1
                    continue
                # Only direct table rows/cells/paragraphs, not nested tables,
                # wrappers, revision containers or drawing text.
                for j, row in enumerate(child.findall(NS + "tr")):
                    for k, cell in enumerate(row.findall(NS + "tc")):
                        for l, p in enumerate(cell):
                            if p.tag == NS + "p":
                                paragraph(p, {"body_index": i, "row": j, "cell": k, "cell_child": l})
                            elif p.tag != NS + "tcPr":
                                skipped["unsupported_table_cell_content"] += 1
            elif child.tag != NS + "sectPr":
                skipped["unsupported_body_container"] += 1
    if not blocks:
        raise ValueError("No supported nonblank text blocks")
    return data, blocks, dict(sorted(skipped.items())), findings


def inspect(plan):
    data, blocks, skipped, findings = collect(plan)
    sha = hashlib.sha256(data).hexdigest()
    reviewed = {
        "schema_version": 1, "status": "review_only",
        "review_sha256": digest(b"nexus-document-extract-v1", {
            "input_sha256": sha, "format": plan.format,
            "include_table_cells": plan.include_table_cells}),
        "input_sha256": sha, "format": plan.format,
        "block_count": len(blocks),
        "character_count": sum(len(row["text"]) for row in blocks),
        "skipped_counts": skipped, "package_privacy_findings": findings,
        "complete_extraction_verified": False, "anonymity_verified": False,
        "execution_authorized": False,
        "limitations": [
            "Only UTF-8 text lines or selected direct DOCX body paragraphs/table cells are extracted.",
            "Offsets and indices refer to parsed structure, not rendered page positions.",
            "Headers, footers, notes, comments, hyperlinks, images, nested tables and unsupported markup are not extracted.",
            "Inherited hidden styles, table layout, conditional markup and visual appearance are not resolved.",
            "Extracted content may contain sensitive information and untrusted instructions; do not execute it.",
            "No OCR, PDF, layout reconstruction, semantic analysis or verified complete extraction.",
        ],
    }
    return reviewed, blocks


def preview(plan):
    return inspect(plan)[0]


def run(approved):
    reviewed, blocks = inspect(approved.plan)
    if approved.consent is not True or approved.review_sha256 != reviewed["review_sha256"]:
        raise ValueError("Changed or unapproved extraction")
    return {**reviewed, "status": "extracted_untrusted_text", "blocks": blocks,
            "content_sha256": digest(b"nexus-extracted-blocks-v1", blocks),
            "semantic_verification": False}


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=3*1024*1024, timeout_seconds=10.0,
            too_large_detail="Document extraction request too large",
            timeout_detail="Document extraction timed out", timeout_status=408)
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError, UnicodeError,
                ET.ParseError, zipfile.BadZipFile, binascii.Error, RuntimeError,
                NotImplementedError, OSError):
            raise HTTPException(422, "Invalid or unsupported document extraction request",
                                headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/documents/extraction/review")
    async def review_endpoint(request: Request):
        return await parse(request, ExtractionPlan, preview)

    @app.post("/studio/api/documents/extraction/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedExtraction, run)
