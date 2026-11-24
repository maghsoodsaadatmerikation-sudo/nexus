"""Bounded DOCX package privacy inventory and optional core-property reset."""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import re
import stat
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_peer_review import digest
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
MAX_ARCHIVE = 2 * 1024 * 1024
MAX_PART = 2 * 1024 * 1024
MAX_EXPANDED = 8 * 1024 * 1024
MAX_ENTRIES = 128
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
MAIN_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
CORE = "docProps/core.xml"
EMPTY_CORE = ('<?xml version="1.0" encoding="UTF-8"?>'
              '<cp:coreProperties xmlns:cp="' + CP + '"/>').encode("utf-8")
REVISIONS = {"ins", "del", "moveFrom", "moveTo", "rPrChange", "pPrChange",
             "tblPrChange", "trPrChange", "tcPrChange", "sectPrChange"}
IDENTITY_ATTRS = {"author", "initials", "date", "userId"}


class PrivacyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    docx_base64: str = Field(min_length=4, max_length=2796204)
    reset_core_properties: bool = False
    reset_zip_metadata: bool = False


class ApprovedPrivacy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    plan: PrivacyPlan
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    consent: bool = False


def parse_xml(data):
    text = data.decode("utf-8-sig", errors="strict")
    if "\x00" in text or re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
        raise ValueError("Unsupported XML declaration")
    declared = re.match(r"\s*<\?xml[^?]*encoding\s*=\s*(['\"])([^'\"]+)\1", text, re.I)
    if declared and declared.group(2).lower() not in ("utf-8", "utf8"):
        raise ValueError("Only UTF-8 XML is supported")
    return ET.fromstring(text)


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def load(plan):
    data = base64.b64decode(plan.docx_base64, validate=True)
    if not data or len(data) > MAX_ARCHIVE:
        raise ValueError("Archive size outside bounds")
    parts, trees, infos = {}, {}, []
    expanded = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries = z.infolist()
        if not 1 <= len(entries) <= MAX_ENTRIES:
            raise ValueError("Unsupported entry count")
        archive_comment = bool(z.comment)
        seen = set()
        for info in entries:
            name = info.orig_filename
            if (not name or len(name) > 240 or name != info.filename
                    or any(ord(ch) < 32 or ord(ch) == 127 for ch in name)
                    or any(ch in name for ch in "\\:%?#")
                    or any(p in ("", ".", "..") for p in name.split("/"))
                    or name.casefold() in seen or info.is_dir()
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 1
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError("Unsupported or ambiguous archive entry")
            seen.add(name.casefold())
            expanded += info.file_size
            if info.file_size > MAX_PART or expanded > MAX_EXPANDED:
                raise ValueError("Expanded package too large")
            with z.open(info) as entry:
                content = entry.read(MAX_PART+1)
            if len(content) != info.file_size or len(content) > MAX_PART:
                raise ValueError("Invalid part size")
            parts[name] = content
            infos.append(info)
            if name.lower().endswith((".xml", ".rels")):
                trees[name] = parse_xml(content)
    if not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"} <= trees.keys():
        raise ValueError("Required DOCX parts absent")
    types = trees["[Content_Types].xml"]
    if (types.tag != f"{{{CT}}}Types" or
            trees["word/document.xml"].tag != f"{{{W}}}document" or
            trees["_rels/.rels"].tag != f"{{{REL}}}Relationships"):
        raise ValueError("Unsupported DOCX package")
    main = [n for n in types if n.tag == f"{{{CT}}}Override"
            and n.get("PartName") == "/word/document.xml"]
    if len(main) != 1 or main[0].get("ContentType") != MAIN_TYPE:
        raise ValueError("Only non-macro DOCX main content is supported")
    if CORE in trees and trees[CORE].tag != f"{{{CP}}}coreProperties":
        raise ValueError("Unexpected core properties")
    return data, parts, trees, infos, archive_comment


def inventory(parts, trees, infos, archive_comment):
    counts = Counter()
    for name in parts:
        lower = name.lower()
        if lower.startswith("_xmlsignatures/") or "vbaproject" in lower:
            counts["signature_or_macro_parts"] += 1
        if lower.startswith("docprops/") and name != CORE:
            counts["other_property_parts"] += 1
        if lower.startswith("customxml/"):
            counts["custom_xml_parts"] += 1
        if lower.startswith("word/comments") or lower.startswith("word/people"):
            counts["comment_or_people_parts"] += 1
        if lower.startswith(("word/header", "word/footer")):
            counts["header_footer_parts"] += 1
        if lower.startswith(("word/media/", "word/embeddings/", "word/activex/")):
            counts["media_or_embedded_parts"] += 1
    if CORE in trees:
        root = trees[CORE]
        counts["core_property_elements"] = len(root)
        if root.attrib or (root.text or "").strip():
            counts["core_root_extra_content"] += 1
    for name, tree in trees.items():
        for element in tree.iter():
            tag = local_name(element.tag)
            if element.tag.startswith("{" + W + "}"):
                if tag in REVISIONS:
                    counts["tracked_change_elements"] += 1
                if tag in ("vanish", "webHidden", "specVanish"):
                    counts["hidden_text_markers"] += 1
            if any(local_name(k) in IDENTITY_ATTRS for k in element.attrib):
                counts["identity_attribute_elements"] += 1
            if name.lower().endswith(".rels") and element.get("TargetMode", "").casefold() == "external":
                counts["external_relationships"] += 1
            if name == "[Content_Types].xml":
                kind = element.get("ContentType", "").lower()
                if "digital-signature" in kind or "macroenabled" in kind or "vbaproject" in kind:
                    counts["signature_or_macro_content_types"] += 1
    counts["zip_entry_metadata"] = sum(bool(info.comment or info.extra or
        info.date_time != (1980, 1, 1, 0, 0, 0)) for info in infos)
    counts["zip_archive_comment"] = int(archive_comment)
    return dict(sorted(counts.items()))


def inspect(plan):
    data, parts, trees, infos, comment = load(plan)
    counts = inventory(parts, trees, infos, comment)
    sha = hashlib.sha256(data).hexdigest()
    reviewed = {
        "schema_version": 1,
        "review_sha256": digest(b"nexus-docx-privacy-v1", {
            "archive_sha256": sha, "reset_core_properties": plan.reset_core_properties,
            "reset_zip_metadata": plan.reset_zip_metadata}),
        "archive_sha256": sha, "status": "review_only",
        "entry_count": len(parts), "findings": counts,
        "core_properties_present": CORE in parts,
        "reset_core_properties": plan.reset_core_properties,
        "reset_zip_metadata": plan.reset_zip_metadata,
        "rewrite_allowed": not (counts.get("signature_or_macro_parts") or
                                counts.get("signature_or_macro_content_types")),
        "anonymity_verified": False, "execution_authorized": False,
        "limitations": [
            "Inventory counts are heuristics, not a complete OOXML conformance or identity audit.",
            "No text, property values, relationship targets or part filenames are returned by review.",
            "Core reset removes all core properties including legitimate title, timestamps and keywords.",
            "Other properties, body text, comments, revisions, relationships, embedded objects and media remain untouched.",
            "Only bounded UTF-8 XML DOCX packages are supported; PDF, encrypted files and general Office formats are not supported.",
            "No external relationships are followed and no document code is executed.",
        ],
    }
    return reviewed, parts, infos, comment


def preview(plan):
    return inspect(plan)[0]


def run(approved):
    checked, parts, infos, comment = inspect(approved.plan)
    plan = approved.plan
    if approved.consent is not True or checked["review_sha256"] != approved.review_sha256:
        raise ValueError("Changed or unapproved privacy plan")
    if not checked["rewrite_allowed"] or not (plan.reset_core_properties or plan.reset_zip_metadata):
        raise ValueError("Rewrite not allowed or no reset requested")
    if plan.reset_core_properties and CORE in parts:
        parts[CORE] = EMPTY_CORE
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        # Rebuild from validated entries only. Never carry unparsed trailing
        # bytes or local ZIP header metadata into the new package.
        for old in infos:
            if plan.reset_zip_metadata:
                info = zipfile.ZipInfo(old.filename, (1980, 1, 1, 0, 0, 0))
            else:
                info = zipfile.ZipInfo(old.filename, old.date_time)
                info.comment, info.extra = old.comment, old.extra
                info.external_attr, info.internal_attr = old.external_attr, old.internal_attr
                info.create_system = old.create_system
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, parts[old.filename])
        # Preserve the archive comment only when not explicitly resetting ZIP metadata.
        if not plan.reset_zip_metadata and comment:
            # The original comment value is not retained by inspection; fail
            # rather than silently drop metadata outside the approved reset.
            raise ValueError("Archive comment requires ZIP metadata reset")
    output = stream.getvalue()
    if len(output) > MAX_ARCHIVE:
        raise ValueError("Rebuilt archive exceeds bounds")
    encoded = base64.b64encode(output).decode("ascii")
    recheck = preview(PrivacyPlan(docx_base64=encoded))
    if plan.reset_core_properties and (recheck["findings"].get("core_property_elements")
                                       or recheck["findings"].get("core_root_extra_content")):
        raise ValueError("Core reset did not pass reinspection")
    return {
        "schema_version": 1, "status": "redacted_copy_requires_manual_review",
        "review_sha256": checked["review_sha256"],
        "output_sha256": recheck["archive_sha256"],
        "docx_base64": encoded,
        "remaining_findings": recheck["findings"],
        "core_properties_reset": plan.reset_core_properties and CORE in parts,
        "zip_metadata_reset": plan.reset_zip_metadata,
        "anonymity_verified": False, "document_rendering_verified": False,
        "submission_authorized": False, "execution_authorized": False,
    }


def register(app):
    async def parse(request, schema, function):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=3*1024*1024, timeout_seconds=10.0,
            too_large_detail="DOCX privacy request too large",
            timeout_detail="DOCX privacy request timed out", timeout_status=408)
        try:
            result = function(schema.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError, UnicodeError,
                ET.ParseError, zipfile.BadZipFile, binascii.Error, RuntimeError,
                NotImplementedError, OSError):
            raise HTTPException(422, "Invalid or unsupported DOCX privacy request",
                                headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)

    @app.post("/studio/api/documents/privacy/review")
    async def review_endpoint(request: Request):
        return await parse(request, PrivacyPlan, preview)

    @app.post("/studio/api/documents/privacy/run")
    async def run_endpoint(request: Request):
        return await parse(request, ApprovedPrivacy, run)
