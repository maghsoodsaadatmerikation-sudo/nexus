"""Consent-gated, deterministic preview of user-authored assistant workflows.

This is deliberately *not* an agent planner or a tool executor. It only maps
explicit, bounded human-authored steps to already-reviewed Studio surfaces.
"""
from __future__ import annotations

import re
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from studio_connections import operator_auth
from transport_bounds import read_bounded_body

NO_STORE = {"Cache-Control": "no-store"}
MAX_BODY = 8192
MAX_GOAL = 1800
MAX_STEPS = 6
MAX_STEP = 260


class PlanPreviewRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    consent: Literal[True]
    goal: str = Field(min_length=8, max_length=MAX_GOAL)

    @field_validator("consent", mode="before")
    @classmethod
    def require_literal_true(cls, value):
        if value is not True:
            raise ValueError("explicit boolean consent required")
        return value


# Only an exact, affirmative, human-written action is eligible. These are UI
# destinations, not callable provider operations. Do not include destructive
# operations, broad shell commands, email sends, purchases or account writes.
ROUTES = (
    ("research", re.compile(r"^(?:/research\b|research\b|search\s+(?:the\s+web\s+)?(?:for\s+)?|پژوهش\b|جست\s*[‌ ]*و\s*[‌ ]*جو(?:\s+کن)?\b)", re.I)),
    ("data", re.compile(r"^(?:/data\b|analy[sz]e\b|تحلیل\s*(?:داده|فایل|csv)\b)", re.I)),
    ("write", re.compile(r"^(?:/write\b|draft\b|write\b|بنویس\b|نوشتن\b|پیش\s*نویس\b)", re.I)),
    # Route to the existing writing canvas. This never generates or exports a file.
    ("export", re.compile(r"^(?:/export\b|(?:export|download)\s+(?:(?:the|this)\s+)?(?:document|draft|report|file|markdown|docx|word|pdf)\b|خروجی\s*(?:سند|فایل|گزارش)\b|(?:دانلود|دریافت)\s*(?:سند|فایل|گزارش)\b)", re.I)),
    ("code", re.compile(r"^(?:/code\b|run\s+(?:this\s+)?(?:javascript|js)\b|کدنویسی\b|اجرا\s*ی?\s*کد\b)", re.I)),
    ("music", re.compile(r"^(?:/music\b|compose\b|آهنگ\s+بساز\b|موسیقی\s+بساز\b)", re.I)),
    ("remind", re.compile(r"^(?:/remind\b|remind\s+me\b|set\s+(?:a\s+)?reminder\b|یادآوری\s+کن\b)", re.I)),
    ("github", re.compile(r"^(?:/github(?:\s+(?:pulls|prs))?$|(?:review|list|show|check)\s+github\s+(?:pull\s+requests|prs)\b)", re.I)),
    ("render", re.compile(r"^(?:/render(?:\s+deploys)?$|(?:check|list|show)\s+render\s+deploy(?:ment)?s\b)", re.I)),
)
SPLIT = re.compile(r"\s+(?:and\s+then|then|و\s+سپس|سپس|بعد\s+از\s+آن)\s+", re.I)
NUMBERING = re.compile(r"^(?:\d{1,2}[.)]|[-*])\s+")
# More than one distinct action in a step must be separated explicitly.
HIDDEN_ACTION = re.compile(r"(?:\s+(?:and|&)\s+(?:research|search|analy[sz]e|write|draft|export|download|run|compose|remind|list|check)\b|\s+و\s+(?:پژوهش|تحلیل|بنویس|نوشتن|کدنویسی|خروجی|دانلود|دریافت)\b)", re.I)
INVALID_CHAR = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def preview(goal: str) -> dict:
    if INVALID_CHAR.search(goal) or len(goal) > MAX_GOAL:
        raise ValueError("invalid characters or size")
    source = goal.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.strip() for line in source.split("\n")]
    if lines and lines[0].lower() in {"/plan", "plan:", "برنامه:", "برنامه"}:
        lines.pop(0)
    if any(not line for line in lines):
        raise ValueError("empty workflow step")
    # Explicit 'then' permits a natural sentence without risking arbitrary
    # splitting on 'and', Persian 'و', punctuation in URLs or quoted prompts.
    items = [part.strip() for line in lines for part in SPLIT.split(line)]
    if not 2 <= len(items) <= MAX_STEPS:
        raise ValueError("provide 2 to 6 distinct ordered steps")
    steps = []
    for number, raw in enumerate(items, start=1):
        instruction = NUMBERING.sub("", raw).strip()
        if (not instruction or len(instruction) > MAX_STEP or
            INVALID_CHAR.search(instruction) or HIDDEN_ACTION.search(instruction)):
            raise ValueError("invalid or compound workflow step")
        matches = [tool for tool, pattern in ROUTES if pattern.match(instruction)]
        if len(matches) != 1:
            raise ValueError("unrecognized or ambiguous workflow step")
        tool = matches[0]
        # Slash commands beyond the reviewed exact routes are never inferred.
        if instruction.startswith("/") and not re.fullmatch(rf"/{tool}\b.*", instruction, re.I):
            raise ValueError("unsupported command")
        steps.append({"number": number, "tool": tool, "command": "/" + tool,
                      "instruction": instruction, "status": "not_started",
                      "requires_separate_user_review": True})
    return {"kind": "review_only", "authority": "none", "execution": "not_started",
            "provider_requests": 0, "tools_executed": 0, "steps": steps}


def register(app) -> None:
    @app.post("/studio-api/assistant/plan-preview")
    async def plan_preview(request: Request):
        # Independent Studio credential, even without a configured model.
        operator_auth(request)
        content_types = request.headers.getlist("content-type")
        if (len(content_types) != 1 or
            content_types[0].split(";", 1)[0].strip().lower() != "application/json"):
            raise HTTPException(415, "JSON required", headers=NO_STORE)
        body = await read_bounded_body(request, max_bytes=MAX_BODY,
                                       timeout_seconds=15,
                                       too_large_detail="Plan request too large",
                                       timeout_detail="Plan request timed out",
                                       timeout_status=408)
        try:
            data = PlanPreviewRequest.model_validate_json(body)
            result = preview(data.goal)
        except (ValidationError, ValueError):
            raise HTTPException(422, "Review 2–6 supported, explicit workflow steps",
                                headers=NO_STORE) from None
        return JSONResponse(result, headers=NO_STORE)
