"""Reconcile explicitly supplied bibliography metadata without inventing fields."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_evidence import clean
from studio_research_synthesis import SynthesisRequest, synthesize
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class Author(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    family: str = Field(min_length=1, max_length=100)
    initials: str = Field(pattern=r"^[A-Z](?: [A-Z]){0,7}$")


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reference_number: int = Field(ge=1, le=60)
    source_id: str = Field(pattern=r"^source:[a-f0-9]{64}$")
    origin: Literal["crossref", "europepmc", "publisher", "manual"]
    title: str | None = Field(default=None, min_length=1, max_length=300)
    authors: list[Author] | None = Field(default=None, min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1000, le=9999)
    journal: str | None = Field(default=None, min_length=1, max_length=200)
    journal_abbreviation: str | None = Field(default=None, min_length=1, max_length=100)
    volume: str | None = Field(default=None, min_length=1, max_length=30)
    issue: str | None = Field(default=None, min_length=1, max_length=30)
    locator: str | None = Field(default=None, min_length=1, max_length=80)


class BibliographyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    synthesis: SynthesisRequest
    report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata: list[Metadata] = Field(default_factory=list, max_length=120)


FIELDS = ("title", "authors", "year", "journal", "journal_abbreviation",
          "volume", "issue", "locator")


def normalized(value):
    if isinstance(value, str):
        return unicodedata.normalize("NFC", " ".join(value.split())).casefold()
    if isinstance(value, list):
        return tuple((normalized(a["family"]), a["initials"]) for a in value)
    return value


def format_drafts(fields, url):
    authors = fields["authors"]
    # Restricted journal-article drafts: initials are supplied, not inferred.
    apa_names = [a["family"] + ", " + ". ".join(a["initials"].split()) + "." for a in authors]
    if len(apa_names) > 20:
        apa = ", ".join(apa_names[:19]) + ", … " + apa_names[-1]
    elif len(apa_names) > 1:
        apa = ", ".join(apa_names[:-1]) + ", & " + apa_names[-1]
    else:
        apa = apa_names[0]
    v_names = [a["family"] + " " + a["initials"].replace(" ", "") for a in authors]
    vancouver = ", ".join(v_names[:6]) + (", et al." if len(v_names) > 6 else "")
    issue = "(" + fields["issue"] + ")" if fields.get("issue") else ""
    return {
        "apa_like_plain_text": (f'{apa} ({fields["year"]}). {fields["title"]}. '
                                f'{fields["journal"]}, {fields["volume"]}{issue}, '
                                f'{fields["locator"]}. {url}'),
        "vancouver_like_plain_text": (
            f'{vancouver}. {fields["title"]}. '
            f'{fields.get("journal_abbreviation") or fields["journal"]}. '
            f'{fields["year"]};{fields["volume"]}{issue}:{fields["locator"]}. {url}'),
    }


def reconcile(request):
    report = synthesize(request.synthesis)
    if report["report_sha256"] != request.report_sha256:
        raise ValueError("Stale synthesis")
    refs = {row["number"]: row for row in report["references"]}
    records = {}
    seen = set()
    for index, item in enumerate(request.metadata):
        ref = refs.get(item.reference_number)
        if ref is None or ref["source_id"] != item.source_id:
            raise ValueError("Unassociated metadata")
        key = (item.reference_number, item.origin)
        if key in seen:
            raise ValueError("Duplicate origin for reference")
        seen.add(key)
        values = item.model_dump(include=set(FIELDS), exclude_none=True)
        for value in values.values():
            if isinstance(value, str):
                clean(value, 300)
            elif isinstance(value, list):
                for author in value:
                    clean(author["family"], 100)
        records.setdefault(item.reference_number, []).append((index, values))
    entries = []
    for number, ref in refs.items():
        alternatives = {field: [] for field in FIELDS}
        titles = ref["conflicting_titles"] if ref["title_conflict"] else [ref["title"]]
        for title in titles:
            if title:
                alternatives["title"].append({"value": title, "origin": "synthesis"})
        for index, values in records.get(number, []):
            for field, value in values.items():
                alternatives[field].append({"value": value, "origin": request.metadata[index].origin,
                                            "metadata_index": index})
        resolved = {}
        conflicts = {}
        for field, options in alternatives.items():
            if len({normalized(option["value"]) for option in options}) > 1:
                conflicts[field] = options
            elif options:
                resolved[field] = options[0]["value"]
        is_doi = ref["identity"].startswith("doi:")
        # DOI alone does not establish article type. The rendering is only a
        # proposed journal-article layout when full article fields are supplied.
        required = ("title", "authors", "year", "journal", "volume", "locator")
        missing = [field for field in required if field not in resolved]
        csl = {"id": f"ref-{number:03d}", "URL": ref["url"]}
        if is_doi:
            csl["DOI"] = ref["identity"][4:]
        for field, key in (("title", "title"), ("journal", "container-title"),
                           ("volume", "volume"), ("issue", "issue"), ("locator", "page")):
            if field in resolved:
                csl[key] = resolved[field]
        if "authors" in resolved:
            csl["author"] = [{"family": a["family"], "given": a["initials"]}
                             for a in resolved["authors"]]
        if "year" in resolved:
            csl["issued"] = {"date-parts": [[resolved["year"]]]}
        formats = (format_drafts(resolved, ref["url"])
                   if is_doi and not missing and not conflicts else {})
        entries.append({
            "number": number, "source_id": ref["source_id"], "identity": ref["identity"],
            "resolved_fields": resolved, "field_observations": alternatives,
            "conflicts": conflicts, "missing_journal_layout_fields": missing,
            "csl_like_metadata": csl, "citation_drafts": formats,
            "status": "layout_draft_available" if formats else "manual_review_required",
            "independent_verification": False,
        })
    canonical = json.dumps(request.model_dump(), ensure_ascii=True, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1, "report_sha256": report["report_sha256"],
        "bibliography_review_sha256": hashlib.sha256(
            b"nexus-bibliography-v1\x00" + canonical).hexdigest(),
        "entries": entries, "status": "human_review_required",
        "metadata_retrieved": False, "independent_verification": False,
        "style_compliance_verified": False, "submission_authorized": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/bibliography-review")
    async def bibliography_review(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=786432, timeout_seconds=10.0,
            too_large_detail="Bibliography review too large",
            timeout_detail="Bibliography review timed out", timeout_status=408,
        )
        try:
            result = reconcile(BibliographyRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid bibliography review", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
