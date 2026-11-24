"""Traceable reference records from reviewed Studio source cards, without invention."""
from __future__ import annotations

from typing import Annotated
from urllib.parse import quote

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from studio_research_evidence import EvidenceRequest, review
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}


class CitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence: EvidenceRequest
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_indices: list[Annotated[int, Field(ge=0, le=59)]] = Field(
        min_length=1, max_length=60
    )


def canonical_url(identity):
    if identity.startswith("doi:"):
        return "https://doi.org/" + quote(identity[4:], safe="/")
    if identity.startswith("wiki:"):
        _, host, page = identity.split(":")
        return f"https://{host}/?curid={page}"
    if identity.startswith("epmc:"):
        return "https://europepmc.org" + identity[5:]
    raise ValueError("Unsupported identity")


def citations(request: CitationRequest):
    checked = review(request.evidence)
    if checked["review_sha256"] != request.review_sha256:
        raise ValueError("Stale evidence review")
    indices = request.selected_indices
    if len(set(indices)) != len(indices) or any(i >= len(request.evidence.cards) for i in indices):
        raise ValueError("Invalid source selection")
    chosen = set(indices)
    entries = []
    csl = []
    numbered = []
    for group in checked["inventory"]:
        selected = [i for i in group["source_indices"] if i in chosen]
        if not selected:
            continue
        cards = [request.evidence.cards[i] for i in selected]
        # Preserve source order and do not parse bibliographic fields from excerpts.
        # Conflicting titles are not resolved by assuming the longest is correct.
        titles = list(dict.fromkeys(" ".join(card.title.split()) for card in cards))
        title_conflict = len({title.casefold() for title in titles}) > 1
        title = None if title_conflict else titles[0]
        url = canonical_url(group["identity"])
        number = len(entries) + 1
        item_id = f"ref-{number:03d}"
        record = {"id": item_id, "type": "webpage" if group["identity"].startswith("wiki:")
                  else "article", "URL": url}
        if title is not None:
            record["title"] = title
        if group["identity"].startswith("doi:"):
            record["DOI"] = group["identity"][4:]
        # Missing author/date/container are explicit, not guessed from provider or excerpt.
        missing = ["author", "issued"]
        if record["type"] == "article":
            missing.append("container-title")
        if title_conflict:
            missing.append("title")
        csl.append(record)
        label = title if title is not None else "[Title conflict — review required]"
        numbered.append(f"[{number}] {label}. {url} [Incomplete; unverified source lead]")
        entries.append({
            "citation_id": item_id, "number": number, "identity": group["identity"],
            "selected_source_indices": selected,
            "related_source_indices": group["source_indices"],
            "url": url, "title": title,
            "title_conflict": title_conflict,
            "conflicting_titles": titles if title_conflict else [],
            "missing_metadata": missing,
            "record_type_is_generic": True,
            "status": "incomplete_unverified",
        })
    return {
        "schema_version": 1,
        "review_sha256": checked["review_sha256"],
        "status": "reference_draft",
        "entries": entries,
        "csl_json": csl,
        "numbered_reference_draft": numbered,
        "independent_verification": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/citations")
    async def citation_endpoint(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Citation request too large",
            timeout_detail="Citation request timed out", timeout_status=408,
        )
        try:
            result = citations(CitationRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid citation request", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
