"""Bounded evidence inventory for Studio public research cards. No retrieval."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
DOI = re.compile(r"10\.\d{4,9}/[!-~]+", re.I)


class SourceCard(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    engine: Literal["wikipedia", "crossref", "europepmc"]
    title: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(min_length=1, max_length=2400)
    url: str = Field(min_length=1, max_length=1000)
    kind: Literal["encyclopedia-excerpt", "bibliographic-metadata-only", "abstract-excerpt"]
    query: str = Field(min_length=1, max_length=250)
    at: str = Field(min_length=1, max_length=64)
    license: str = Field(max_length=500)
    queries: list[str] = Field(default_factory=list, max_length=4)


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_index: int = Field(ge=0, le=59)
    stance: Literal["supports", "challenges", "unclear"]


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim: str = Field(min_length=1, max_length=1000)
    cards: list[SourceCard] = Field(min_length=1, max_length=60)
    assessments: list[Assessment] = Field(default_factory=list, max_length=60)


def clean(value, limit):
    if (not value.strip() or len(value) > limit
            or any(0xD800 <= ord(c) <= 0xDFFF or
                   (ord(c) < 32 and c not in "\n\t\r") for c in value)):
        raise ValueError("Invalid research text")


def identity(card):
    url = card.url
    if any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("Invalid source URL")
    u = urlsplit(url)
    if u.scheme != "https" or u.username or u.password or u.fragment or u.port is not None:
        raise ValueError("Invalid source URL")
    host = u.netloc.lower()
    if card.engine == "wikipedia":
        if (card.kind != "encyclopedia-excerpt"
                or host not in {f"{lang}.wikipedia.org" for lang in ("en", "fa", "es", "fr", "de", "ar")}
                or u.path != "/" or not re.fullmatch(r"curid=[1-9]\d{0,19}", u.query)):
            raise ValueError("Invalid Wikipedia card")
        return f"wiki:{host}:{u.query[6:]}"
    if card.engine == "crossref" and card.kind != "bibliographic-metadata-only":
        raise ValueError("Crossref provides metadata only")
    if card.engine == "europepmc" and card.kind not in ("abstract-excerpt", "bibliographic-metadata-only"):
        raise ValueError("Invalid Europe PMC card kind")
    if host == "doi.org" and not u.query:
        doi = unquote(u.path.removeprefix("/"), errors="strict")
        if len(doi) <= 200 and DOI.fullmatch(doi):
            return "doi:" + doi.lower()
    if (card.engine == "europepmc" and host == "europepmc.org" and not u.query
            and re.fullmatch(r"/article/(MED/\d{1,12}|PMC/PMC\d{1,12})", u.path)):
        return "epmc:" + u.path
    raise ValueError("Unsupported source identity")


def review(request):
    clean(request.claim, 1000)
    groups = {}
    for index, card in enumerate(request.cards):
        for value, limit in ((card.title, 300), (card.excerpt, 2400),
                             (card.query, 250), (card.at, 64), (card.license, 500)):
            clean(value, limit)
        for query in card.queries:
            clean(query, 250)
        key = identity(card)
        group = groups.setdefault(key, {"identity": key, "source_indices": [],
                                       "providers": [], "kinds": [], "stances": []})
        group["source_indices"].append(index)
        if card.engine not in group["providers"]:
            group["providers"].append(card.engine)
        if card.kind not in group["kinds"]:
            group["kinds"].append(card.kind)
    by_index = {index: group for group in groups.values() for index in group["source_indices"]}
    seen = set()
    for item in request.assessments:
        index = item.source_index
        if index not in by_index or index in seen:
            raise ValueError("Invalid or duplicate assessment")
        seen.add(index)
        if (request.cards[index].kind == "bibliographic-metadata-only"
                and item.stance != "unclear"):
            raise ValueError("Metadata cannot substantiate a stance")
        group = by_index[index]
        group["stances"].append(item.stance)
    counts = {"supports": 0, "challenges": 0, "mixed": 0, "unassessed_or_unclear": 0}
    inventory = []
    for group in groups.values():
        stances = set(group.pop("stances"))
        if {"supports", "challenges"} <= stances:
            stance = "mixed"
        elif "supports" in stances:
            stance = "supports"
        elif "challenges" in stances:
            stance = "challenges"
        else:
            stance = "unassessed_or_unclear"
        counts[stance] += 1
        inventory.append({**group, "caller_reported_stance": stance,
                          "metadata_only": group["kinds"] == ["bibliographic-metadata-only"]})
    canonical = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=True,
                           separators=(",", ":")).encode("ascii")
    return {
        "schema_version": 1,
        "review_sha256": hashlib.sha256(b"nexus-evidence-inventory-v1\x00" + canonical).hexdigest(),
        "received_cards": len(request.cards),
        "distinct_source_identities": len(inventory),
        "duplicate_cards": len(request.cards) - len(inventory),
        "inventory": inventory,
        "stance_counts": counts,
        "reported_disagreement": bool(counts["mixed"] or (counts["supports"] and counts["challenges"])),
        "evidence": "caller_supplied_unverified_source_leads_and_assessments",
        "independent_verification": False,
        "execution_authorized": False,
    }


def register(app):
    @app.post("/studio/api/research/evidence-review")
    async def evidence_review(request: Request):
        operator_auth(request)
        body = await read_bounded_body(
            request, max_bytes=262144, timeout_seconds=10.0,
            too_large_detail="Evidence inventory too large",
            timeout_detail="Evidence inventory timed out", timeout_status=408,
        )
        try:
            result = review(EvidenceRequest.model_validate_json(body))
        except (ValidationError, ValueError, RecursionError):
            raise HTTPException(422, "Invalid evidence inventory", headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
