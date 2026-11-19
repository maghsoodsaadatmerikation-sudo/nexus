"""Validated, immutable operator configuration for the non-authoritative model edge.

A request must never combine the reviewed model URL with adapter or credentials
re-read later from mutable process configuration. This module holds no policy or
authorization decisions and does not expose provider credentials to clients.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Literal, Mapping
from urllib.parse import urlsplit


ModelAdapter = Literal["generic", "deepseek"]


@dataclass(frozen=True, slots=True)
class ModelConfig:
    endpoint: str
    model_id: str
    studio_token: str = field(repr=False)
    provider_api_key: str = field(repr=False)
    provider_host: str
    adapter: ModelAdapter


def configuration_fingerprint(
    endpoint: str, model_id: str, adapter: str, policy: str
) -> str:
    """Bind client review to model identity, adapter semantics and system policy.

    Credentials are deliberately excluded: rotating a secret does not change
    what the user has reviewed, and no secret is disclosed through this digest.
    """
    adapter_suffix = "" if adapter == "generic" else "\nadapter:" + adapter
    policy_digest = hashlib.sha256(policy.encode("utf-8")).hexdigest()
    identity = endpoint + "\n" + model_id + adapter_suffix + "\npolicy-sha256:" + policy_digest
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def read_model_config(environment: Mapping[str, str] | None = None) -> ModelConfig | None:
    """Validate the complete provider configuration and snapshot it once.

    Public URLs must use HTTPS. Only literal loopback addresses may use HTTP
    for local self-hosted development. Invalid configuration disables the
    optional provider bridge rather than quietly relaxing transport security.
    """
    env = os.environ if environment is None else environment
    endpoint = env.get("NEXUS_MODEL_URL", "").strip()
    model_id = env.get("NEXUS_MODEL_ID", "").strip()
    studio_token = env.get("NEXUS_STUDIO_TOKEN", "").strip()
    provider_api_key = env.get("NEXUS_MODEL_API_KEY", "").strip()
    adapter = env.get("NEXUS_MODEL_ADAPTER", "generic").strip()
    try:
        parsed = urlsplit(endpoint)
        _ = parsed.port
    except ValueError:
        return None

    if (
        adapter not in {"generic", "deepseek"}
        or not model_id
        or len(model_id) > 150
        or len(studio_token) < 32
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in endpoint)
        or not (
            parsed.scheme == "https"
            or (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"})
        )
    ):
        return None
    return ModelConfig(
        endpoint=endpoint,
        model_id=model_id,
        studio_token=studio_token,
        provider_api_key=provider_api_key,
        provider_host=parsed.hostname,
        adapter=adapter,
    )
