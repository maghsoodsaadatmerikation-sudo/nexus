"""Authenticated, non-executing capability disclosure for NEXUS Studio.

This is a source/configuration inventory, NOT a live tool availability probe,
browser attestation, model call, deployment status, or tool execution receipt.
No configured targets, credentials, prompts or user data leave this endpoint.
"""
from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

import studio_connections
import studio_model

HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}

# These are REVIEW DESTINATIONS present in Studio source, not proved successes
# or promises that the public deployment contains the same code revision.
BROWSER_SURFACES = (
    ("research", "public_research_after_review"),
    ("data", "local_browser"),
    ("chart", "local_browser"),
    ("code", "local_browser_javascript_only"),
    ("tasks", "local_browser_javascript_only"),
    ("write", "local_browser"),
    ("export", "browser_download_or_print_after_review"),
    ("music", "local_synthetic_score"),
    ("orchestra", "local_synthetic_score"),
    ("remind", "local_browser"),
    ("sources", "local_browser"),
    ("astrology", "optional_symbolic_browser_tool"),
    ("sky", "optional_symbolic_browser_tool"),
    ("memory", "local_browser"),
)
# Actual provider permissions cannot be inferred from configured secrets.
# Each operation below has a distinct source-level action class and credential.
OPERATION_DEFINITIONS = (
    ("github.pulls", "read", "github_read"),
    ("github.file", "read", "github_read"),
    ("render.deploys", "read", "render_read"),
    ("github.branch_preview", "review", "github_branch"),
    ("github.branch", "write", "github_branch"),
    ("github.file_base", "read", "github_file"),
    ("github.file_preview", "review", "github_file"),
    ("github.file_commit", "write", "github_file"),
    ("model.response", "model", "model"),
)

UNIMPLEMENTED = (
    "unattended_agent",
    "remote_shell",
    "native_image_generation",
    "native_video_generation",
    "unrestricted_web_search",
)


def _record(name: str, readiness: str, boundary: str) -> dict:
    return {
        "id": name,
        "readiness": readiness,
        "data_boundary": boundary,
        "separate_user_review_required": True,
        "execution_observed": False,
    }


def disclosure(request: Request) -> dict:
    """Report only what source and local configuration can establish."""
    model = studio_model.read_model_settings()
    budget = request.app.state.model_budget.snapshot()
    if model is None:
        model_readiness = "not_configured"
    elif budget.get("remaining") is None:
        model_readiness = "local_budget_unavailable"
    elif budget["remaining"] == 0:
        model_readiness = "local_budget_exhausted"
    else:
        model_readiness = "configured_not_live_verified"

    # The connector registry contains private (target, credential) tuples.
    # Reduce it to booleans; never expose or serialize either tuple element.
    connector_config = studio_connections.configured()
    github = connector_config.get("github")
    render = connector_config.get("render")
    github_ready = bool(github and github[1])
    render_ready = bool(render and render[1])
    branch_ready = bool(github and os.getenv("NEXUS_CONNECTOR_GITHUB_BRANCH_TOKEN", "").strip())
    file_ready = bool(github and os.getenv("NEXUS_CONNECTOR_GITHUB_FILE_TOKEN", "").strip())
    configured_gates = {
        "github_read": github_ready,
        "render_read": render_ready,
        "github_branch": branch_ready,
        "github_file": file_ready,
    }
    operations = []
    for name, phase, gate in OPERATION_DEFINITIONS:
        readiness = (
            model_readiness if gate == "model" else
            "configured_not_live_verified" if configured_gates[gate] else
            "not_configured"
        )
        operations.append({
            "id": name,
            "phase": phase,
            "configuration_readiness": readiness,
            "potential_account_mutation": phase == "write",
            "permission_verified": False,
            "execution_observed": False,
            "receipt_observed": False,
            "separate_user_review_required": True,
            "proof_boundary": "independent_action_receipt_required",
        })

    capabilities = [
        _record(name, "source_defined_browser_surface_not_runtime_verified", boundary)
        for name, boundary in BROWSER_SURFACES
    ]
    capabilities.extend((
        _record("github", "configured_not_live_verified" if github_ready
                else "not_configured", "external_account_after_review"),
        _record("render", "configured_not_live_verified" if render_ready
                else "not_configured", "external_account_after_review"),
        _record("model", model_readiness, "model_provider_after_review"),
    ))
    capabilities.extend(
        _record(name, "not_implemented_in_this_gateway", "unavailable")
        for name in UNIMPLEMENTED
    )
    return {
        "schema_version": 2,
        "kind": "non_authoritative_capability_disclosure",
        "authority": "none",
        "scope": "reviewed_source_and_local_configuration_only",
        "deployment_revision_verified": False,
        "browser_runtime_verified": False,
        "provider_contact_attempted": False,
        "tools_executed": 0,
        "model_adapter": model.adapter if model else None,
        "model_streaming_configured": bool(model and model.streaming),
        "capabilities": capabilities,
        "operation_gates": operations,
    }


def register(app) -> None:
    @app.get("/studio-api/assistant/capabilities", tags=["assistant"])
    async def assistant_capabilities(request: Request):
        studio_connections.operator_auth(request)
        return JSONResponse(disclosure(request), headers=HEADERS)
